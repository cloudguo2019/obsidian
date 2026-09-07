"""Verify report arithmetic and save honest, scope-limited source audit outputs."""
from decimal import Decimal as D, getcontext
from pathlib import Path
import json, re, subprocess, sys

getcontext().prec = 40
HERE = Path(__file__).resolve().parent
REPORTS = HERE.parents[1]
REPORT = REPORTS/'2026-09-06-3600亿元中央金融企业增资-投资者研究.md'
TOOL = REPORTS/'tools'/'financial_rigor.py'
AUDIT = REPORTS/'tools'/'report_audit.py'

def run_json(script, args):
    p = subprocess.run([sys.executable, str(script), *args], capture_output=True,
                       text=True, encoding='utf-8', check=True)
    return json.loads(p.stdout)

run_json(HERE/'calculate.py', [])
model=json.loads((HERE/'calculations.json').read_text(encoding='utf-8'))
inputs=json.loads((HERE/'bank_inputs.json').read_text(encoding='utf-8'))
checks=[]
def check(name, condition):
    assert condition, name
    checks.append({'check':name,'status':'PASS'})
def close(a,b,tol='0.000001'):
    return abs(D(a)-D(b)) < D(tol)

for name, row in inputs.items():
    b={k:D(v) for k,v in row.items() if k not in ('notes','source')}
    s,e,n,k,p=b['shares'],b['ordinary_equity'],b['annual_profit'],b['capital'],b['reference_price']
    check(name+' A+H=普通股总数', b['a_shares']+b['h_shares']==s)
    for r in model['banks'][name]['price_scenarios']:
        price=D(r['price']); sn=s+k/price
        check(name+' '+r['label']+' EPS保平门槛',close((n+D(r['eps_hurdle_profit']))/sn,n/s))
        check(name+' '+r['label']+' BVPS',close(r['bvps_after'],(e+k)/sn))
        check(name+' '+r['label']+' 稀释率',close(r['dilution'],1-(n/sn)/(n/s)))
        check(name+' '+r['label']+' 财政持股',close(r['mof_after'],(b['mof_shares']+b['mof_capital']/price)/sn))
    for r in model['banks'][name]['profit_scenarios']:
        check(name+' ROIK '+r['roik']+' DPS',close(r['dps'],D(r['eps'])*b['dividend']/n))
    check(name+' CET1静态注资',close(model['banks'][name]['price_scenarios'][0]['cet1_after'],(b['cet1']+k)/b['rwa']))

for r in model['operating_scenarios']:
    x={k:D(v) for k,v in r.items() if k!='name'}
    check(r['name']+' 增量资产负债表平衡',close(x['loans']+x['idle'],D(1000)+x['debt']))
    check(r['name']+' 利润全链条',close(x['profit'],(x['revenue']-x['funding']+x['fee']-x['cost']-x['credit'])*D('.75')))

for r in model['ten_year']:
    irr=D(r['irr']); b=D(1); pv=D(0)
    for year in range(1,11):
        profit=b*D(r['roe']); pv+=profit*D(r['payout'])/(1+irr)**year
        b+=profit*(1-D(r['payout']))
    pv+=b*D(r['pb10'])/(1+irr)**10
    check('十年IRR '+r['roe'],close(pv,r['pb0']))

check('八家3600财政3000烟草600',sum(map(D,['1000','1600','350','150','70','30','300','100']))==D(3600) and sum(map(D,['700','1300','350','150','70','30','300','100']))==D(3000))
check('六行7800财政7000',sum(map(D,['1650','1050','1200','1300','1000','1600']))==D(7800) and sum(map(D,['1650','1050','1124.2006','1175.7994','700','1300']))==D(7000))

source_checks=[]
for field, vals, unit in [
    ('工行2026H1归母利润',{'B1半年报':'1736.82','M8上海证券报':'1736.82'},'亿元'),
    ('农行2026H1归母利润',{'B3半年报':'1463.81','M8上海证券报':'1463.81'},'亿元'),
    ('工行2025普通股利润',{'B2年报':'3567.98','I3摊薄公告历史列':'3567.98'},'亿元'),
    ('农行9月4日H股价格',{'Q5日期行情':'6.54','Q6券商行情':'6.54'},'港元'),
    ('农行PB口径差异_以财报普通权益重算为准',{'本文普通权益PB':model['banks']['农业银行']['pb_reference'],'Q3页面自动PB':'0.73'},'倍'),
]:
    source_checks.append(run_json(TOOL,['cross-validate','--field',field,'--values',json.dumps(vals,ensure_ascii=False),'--unit',unit]))
source_checks.append(run_json(TOOL,['verify-market-cap','--price','8.13','--shares','3564.06257089','--reported','28975.83','--currency','CNY_亿元_全股本A价等价']))

audit_sample=run_json(AUDIT,['extract','--report',str(REPORT),'--sample-pct','15','--seed','20260906'])
audit_result=run_json(AUDIT,['verdict','--report',str(REPORT),'--results',str(HERE/'audit_observed.json')])
for filename, obj in [('audit_sample.json',audit_sample),('audit_verdict.json',audit_result),('financial_checks.json',source_checks),('arithmetic_checks.json',checks)]:
    (HERE/filename).write_text(json.dumps(obj,ensure_ascii=False,indent=2),encoding='utf-8')

text=REPORT.read_text(encoding='utf-8')
defs=set(re.findall(r'^\[([A-Z]\d+)\]:',text,re.M))
refs=set(re.findall(r'\[([A-Z]\d+)\]',text))
check('所有参考编号已定义',not(refs-defs))
check('UTF8无替换字符','\ufffd' not in text)
check('Markdown代码块成对',text.count('```')%2==0)
prose=re.sub(r'\$\$.*?\$\$','',text,flags=re.S)
links=re.findall(r'\[[^\[\]\n]+\]\(([^\n)]+)\)',prose)
local=[p for p in links if not p.startswith(('http:','https:','#'))]
check('附件与本地链接存在',all((REPORT.parent/p).exists() for p in local))
pipe_count=None
for i,line in enumerate(text.splitlines(),1):
    if line.startswith('|'):
        cols=line.count('|')
        if pipe_count is not None: check('表格列数行'+str(i),cols==pipe_count)
        pipe_count=cols
    else: pipe_count=None
(HERE/'arithmetic_checks.json').write_text(json.dumps(checks,ensure_ascii=False,indent=2),encoding='utf-8')
print(json.dumps({'checks':len(checks),'audit':audit_result,'financial_checks':source_checks,'characters':len(text),'source_definitions':len(defs)},ensure_ascii=False,indent=2))
