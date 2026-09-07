"""Reproducible Decimal model. CNY amounts in RMB 100 million, shares in 100 million.
All forward parameters are scenarios, never asserted issuance terms or forecasts.
"""
from decimal import Decimal as D, getcontext
from pathlib import Path
import json

getcontext().prec = 40
ROOT = Path(__file__).resolve().parent
ONE = D(1)
def fmt(x, n=4):
    return format(x.quantize(D(10) ** -n), 'f')
def clean(obj):
    if isinstance(obj, D): return fmt(obj, 8)
    if isinstance(obj, dict): return {k: clean(v) for k,v in obj.items()}
    if isinstance(obj, list): return [clean(v) for v in obj]
    return obj

out = {}
out['capital_sensitivity'] = []
for c in ['0.10','0.115','0.125','0.14']:
    c=D(c)
    for w in ['0.5','0.75','1']:
        w=D(w)
        out['capital_sensitivity'].append(dict(c=c,w=w,
            rwa_per_100=D(100)/c, assets_per_100=D(100)/c/w,
            rwa_1000=D(1000)/c, assets_1000=D(1000)/c/w,
            rwa_2600=D(2600)/c, assets_2600=D(2600)/c/w))

# Net income follows actual interest income, debt cost, fees, operating cost, credit loss, tax.
# u is allocated fraction of fresh equity. Unallocated equity earns cash yield z.
SCENARIOS = {
 '压力': ['0.50','0.14','1','0.026','0.013','0.001','0.005','0.008','0.0125'],
 '中性': ['0.80','0.125','0.75','0.029','0.012','0.0015','0.0045','0.005','0.0125'],
 '改善': ['1','0.115','0.65','0.032','0.011','0.002','0.004','0.0035','0.0125'],
}
out['operating_scenarios'] = []
for name, xs in SCENARIOS.items():
    u,c,w,y,f,a,o,l,z=map(D,xs)
    k=D(1000); loans=u*k/c/w; idle=(ONE-u)*k; debt=loans-u*k
    revenue=loans*y+idle*z; funding=debt*f; fee=loans*a; cost=loans*o; credit=loans*l
    profit=(revenue-funding+fee-cost-credit)*D('.75')
    out['operating_scenarios'].append(dict(name=name,u=u,c=c,w=w,y=y,f=f,a=a,o=o,l=l,z=z,
       loans=loans,rwa=loans*w,idle=idle,debt=debt,revenue=revenue,funding=funding,
       fee=fee,cost=cost,credit=credit,profit=profit,roik=profit/k,
       profit_2600=profit*D('2.6')))

out['insurance'] = []
for fraction in ['.10','.20','.30']:
    p=D(fraction)
    out['insurance'].append(dict(fraction=p,amount=D(600)*p,share_of_3600=D(600)*p/D(3600)))

out['fiscal_interest_scenarios'] = []
for rate in ['.015','.02','.025']:
    r=D(rate)
    out['fiscal_interest_scenarios'].append(dict(rate=r,interest_3000=D(3000)*r))

inputs_path = ROOT/'bank_inputs.json'
if inputs_path.exists():
    banks=json.loads(inputs_path.read_text(encoding='utf-8'))
    out['banks']={}
    for name,raw in banks.items():
        b={k:(D(v) if k not in ['source','notes'] else v) for k,v in raw.items()}
        S,E,N,K,F,H,P=b['shares'],b['ordinary_equity'],b['annual_profit'],b['capital'],b['mof_capital'],b['mof_shares'],b['reference_price']
        eps=N/S; bvps=E/S; roe=N/E
        rows=[]
        for label,p in [('现价假设',P),('0.6PB',bvps*D('.6')),('0.8PB',bvps*D('.8')),('1.0PB',bvps),('1.2PB',bvps*D('1.2'))]:
            new=K/p; s1=S+new; e1=E+K
            rows.append(dict(label=label,price=p,new_shares=new,capital_reserve=K-new,
              total_shares=s1,share_increase=new/S,dilution=new/s1,
              bvps_before=bvps,bvps_after=e1/s1,bvps_change=(e1/s1)/bvps-ONE,
              eps_before=eps,eps_after=N/s1,roe_before=roe,roe_after=N/e1,
              mof_before=H/S,mof_after=(H+F/p)/s1,
              eps_hurdle_profit=eps*new,eps_hurdle_roik=eps/p,
              roe_hurdle_profit=roe*K,roe_hurdle_roik=roe,
              official_roe_after=b['official_roe']/(ONE+K/(N/b['official_roe'])),
              official_roe_hurdle=K*b['official_roe'],
              dps_before=b['dividend']/S,dps_after=b['dividend']/s1,
              dividend_yield_before=b['dividend']/S/P,
              dividend_yield_after=b['dividend']/s1/P,
              cet1_after=(b['cet1']+K)/b['rwa'],cet1_before=b['cet1']/b['rwa'],
              issuance_pb=p/bvps))
        prof=[]
        new=K/P; s1=S+new
        for r in ['0','.04','.08','.12','.16']:
            r=D(r); ni=N+K*r
            prof.append(dict(roik=r,incremental_profit=K*r,eps=ni/s1,
               eps_change=(ni/s1)/eps-ONE,roe=ni/(E+K),
               dps=(ni/s1)*(b['dividend']/N)))
        op=[]
        for row in out['operating_scenarios']:
            r=row['roik']; ni=N+K*r
            op.append(dict(name=row['name'],roik=r,incremental_profit=K*r,
                eps=ni/s1,eps_change=(ni/s1)/eps-ONE))
        out['banks'][name]={'input':b,'price_scenarios':rows,'profit_scenarios':prof,'operating_scenarios':op,
            'pb_reference':P/bvps,'fiscal_dividend_initial':b['dividend']/s1*F/P,
            'eps_hurdle_using_half_annualized':b['half_ordinary_profit']*2/S/P,
            '2027_buffer_extra_if_half_point':b['rwa']*D('.005'),
            'h_price_cny':b['h_price']*D('.86458'),
            'h_pb':b['h_price']*D('.86458')/bvps,
            'a_h_premium':P/(b['h_price']*D('.86458'))-ONE,
            'a_pe':P/eps,'h_pe':b['h_price']*D('.86458')/eps,
            'h_dividend_yield':b['dividend']/S/(b['h_price']*D('.86458')),
            'h_dividend_yield_post':b['dividend']/s1/(b['h_price']*D('.86458')),
            'total_market_cap_class_weighted':b['a_shares']*P+b['h_shares']*b['h_price']*D('.86458'),
            'total_market_cap_all_a_equivalent':S*P,
            'cash_payout_common':b['dividend']/N,
            'retained_2025':N-b['dividend'],
            'rwa_growth_supported_2025_retention':(N-b['dividend'])/b['cet1'],
            'post_issue_price_for_5pct_yield':b['dividend']/s1/D('.05')}

# Stylised 10-year dividend/equity model; no share repurchase, no new issue after t=0.
# Constant ROE on opening book and constant payout. Terminal multiple is a scenario.
out['ten_year'] = []
for roe,payout,pb0,pb10 in [('0.06','.30','.70','.55'),('0.09','.30','.70','.70'),('0.12','.30','.70','.85')]:
    r,d,p0,p10=map(D,[roe,payout,pb0,pb10]); b=ONE; divs=[]
    for t in range(1,11):
        n=b*r; divs.append(n*d); b+=n*(ONE-d)
    terminal=b*p10
    lo=D('-.9'); hi=D(1)
    for _ in range(200):
        mid=(lo+hi)/2
        npv=sum(v/(ONE+mid)**(i+1) for i,v in enumerate(divs))+terminal/(ONE+mid)**10-p0
        if npv>0: lo=mid
        else: hi=mid
    out['ten_year'].append(dict(roe=r,payout=d,pb0=p0,pb10=p10,bvps_year10=b,
       dps_year1=divs[0],dps_year10=divs[-1],cumulative_dividends=sum(divs),
       dividend_growth=r*(ONE-d),terminal_price=terminal,irr=(lo+hi)/2))

(ROOT/'calculations.json').write_text(json.dumps(clean(out),ensure_ascii=False,indent=2),encoding='utf-8')
print(json.dumps(clean(out),ensure_ascii=False,indent=2))
