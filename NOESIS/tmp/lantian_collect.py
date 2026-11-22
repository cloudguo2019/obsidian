import urllib.request, re, json, hashlib, concurrent.futures, sys
from pathlib import Path
from html.parser import HTMLParser

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'output' / '蓝田股份_CPA财务分析打印包_2026-11-02'
RAW = OUT / '原始资料'
RAW.mkdir(parents=True, exist_ok=True)

def get(url):
    req = urllib.request.Request(url, headers={'User-Agent':'Mozilla/5.0'})
    with urllib.request.urlopen(req, timeout=35) as res:
        b = res.read()
        return b

def decode(b):
    try: return b.decode('utf-8')
    except UnicodeDecodeError: return b.decode('gb18030', 'replace')

def indices():
    pairs=[('ndbg',1),('ndbg',2),('zqbg',1),('zqbg',2),('ndbgzy',1),('ndbgzy',2),('zgsmsyxs',1),('ssggs',1),('gzbc',1),('gzbc',2)]
    def one(pair):
        f,p=pair
        u=f'https://money.finance.sina.com.cn/corp/view/vCB_AllBulletin.php?stockid=600709&ftype={f}&Page={p}'
        try:
            b=get(u);s=decode(b)
            (ROOT/'tmp'/f'lantian_index_{f}_{p}.html').write_bytes(b)
            rows=re.findall(r'(\d{4}-\d\d-\d\d)&nbsp;<a[^>]+href=[\"\x27]([^\"\x27]+)[\"\x27][^>]*>(.*?)</a>',s)
            return {'url':u,'rows':[r for r in rows if r[0]<'2004']}
        except Exception as e: return {'url':u,'error':str(e)}
    results=list(concurrent.futures.ThreadPoolExecutor(max_workers=6).map(one,pairs))
    (ROOT/'tmp'/'lantian_indices.json').write_text(json.dumps(results,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps(results,ensure_ascii=False,indent=2))

def probe():
    urls=[
      'https://stock.qianzhan.com/hs/sourcefiles_600709.SH.html',
      'https://finance.sina.com.cn/stock/company/sh/600709/24/19.shtml',
      'https://finance.sina.com.cn/stock/company/sh/600709/24/1.shtml',
      'https://finance.sina.com.cn/stock/company/600709/9.html',
      'https://money.finance.sina.com.cn/corp/view/vCB_AllBulletinDetail.php?id=13247&stockid=600709',
    ]
    def one(pair):
        i,u=pair
        try:
            b=get(u);s=decode(b);(ROOT/'tmp'/f'lantian_probe_{i}.html').write_text(s,encoding='utf-8')
            if i==0:
                lines=[x for x in s.splitlines() if any(k in x.lower() for k in ['pdf','download','2000','script src','sourcefile'])]
            else:
                lines=[x for x in s.splitlines() if any(k in x.lower() for k in ['pdf','download','2000','2001','24/','9.html'])]
            return {'url':u,'lines':lines[-40:]}
        except Exception as e:return {'url':u,'error':str(e)}
    print(json.dumps(list(concurrent.futures.ThreadPoolExecutor(max_workers=5).map(one,enumerate(urls))),ensure_ascii=False))

def oldindex():
    urls=[f'https://finance.sina.com.cn/stock/company/sh/600709/{n}.shtml' for n in [7,8,9,10,24]]
    def one(pair):
        i,u=pair
        try:
            b=get(u);s=decode(b);(ROOT/'tmp'/f'lantian_oldindex_{i}.html').write_text(s,encoding='utf-8')
            return {'url':u,'links':re.findall(r'<a[^>]+href=[\"\x27]?([^\"\x27> ]+)[\"\x27]?[^>]*>([^<]*(?:报告|说明|公告)[^<]*)</a>',s)}
        except Exception as e:return {'url':u,'error':str(e)}
    print(json.dumps(list(concurrent.futures.ThreadPoolExecutor(max_workers=5).map(one,enumerate(urls))),ensure_ascii=False))

def reportprobe():
    urls=[f'https://finance.sina.com.cn/stock/company/sh/600709/{t}/{n}.shtml' for t in [9,10] for n in range(1,9)]
    def one(u):
        try:
            b=get(u);s=decode(b)
            title=re.findall(r'<meta name="description" content="(.*?)"',s)
            name='old_'+u.split('/')[-2]+'_'+u.split('/')[-1]
            (RAW/name).write_bytes(b)
            return {'url':u,'title':title,'size':len(b),'path':name}
        except Exception as e:return {'url':u,'error':str(e)}
    result=list(concurrent.futures.ThreadPoolExecutor(max_workers=6).map(one,urls))
    (ROOT/'tmp'/'lantian_reportprobe.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps(result,ensure_ascii=False))

def cninfo():
    import urllib.parse
    urls=['https://www.cninfo.com.cn/new/hisAnnouncement/query']
    for stock in ['600709,gssh0600709']:
        data=urllib.parse.urlencode({'pageNum':1,'pageSize':100,'tabName':'fulltext','column':'sse','stock':stock,'searchkey':'','secid':'','plate':'sh','category':'','trade':'','seDate':'1995-01-01~2001-08-31','sortName':'time','sortType':'desc','isHLtitle':'true'}).encode()
        try:
            req=urllib.request.Request(urls[0],data=data,headers={'User-Agent':'Mozilla/5.0','Referer':'https://www.cninfo.com.cn/'})
            b=urllib.request.urlopen(req,timeout=30).read()
            d=json.loads(b);print(json.dumps({'total':d.get('totalAnnouncement'),'items':[(r['announcementTitle'],r['adjunctUrl']) for r in d.get('announcements',[])]},ensure_ascii=False))
            (ROOT/'tmp'/'lantian_cninfo_all.json').write_bytes(b)
        except Exception as e:print(str(e))

SOURCES=[
 ('S01','2001年中期报告_巨潮原PDF','https://static.cninfo.com.cn/finalpage/2001-08-20/516153.PDF','pdf','原始披露'),
 ('S02','2001年年度报告_巨潮原PDF','https://static.cninfo.com.cn/finalpage/2002-04-29/587536.PDF','pdf','原始披露'),
 ('S03','2002年年度报告_巨潮原PDF','https://static.cninfo.com.cn/finalpage/2003-04-29/10670936.PDF','pdf','原始披露'),
 ('S04','1996招股说明书概要_巨潮','https://static.cninfo.com.cn/finalpage/1996-05-23/148811.html','html','原始披露_概要'),
 ('S05','1996股票上市公告书_巨潮','https://static.cninfo.com.cn/finalpage/1996-06-18/148936.html','html','原始披露'),
 ('S06','2001中期报告补充说明_巨潮','https://static.cninfo.com.cn/finalpage/2001-08-29/509343.html','html','原始披露'),
 ('S07','2000中报摘要_上交所供稿新浪转载','https://finance.sina.com.cn/2000-08-01/2612.html','html','披露转载_摘要'),
 ('S08','1999关联披露及处罚主要内容_公司大事记','https://finance.sina.com.cn/stock/company/600709/7.html','html','披露转载_非处罚书原件'),
 ('S09','1999审计师处罚决定_法规库转载','https://law1.110.com/law_79493.html','html','处罚文书转载_非官网原件'),
 ('S10','刘姝威蓝田之谜_北京青年报新浪原网页','https://finance.sina.com.cn/t/20020211/172261.html','html','作者观点_媒体转载'),
 ('S11','优秀业绩引出五大疑问_全景','https://www.p5w.net/zt/dissertation/finance/201012/t3353487.htm','html','独立评论_历史转载'),
 ('S12','刑事终审日期与案号_第一财经日报','https://finance.sina.com.cn/stock/t/20060906/0552907166.shtml','html','媒体_未取得原判决'),
 ('S13','1312函证准则_中注协','https://www.cicpa.org.cn/ztzl1/Professional_standards/xxzztx/zyzz/sjzz/202105/P020210507610919165177.pdf','pdf','官方准则_现代方法'),
 ('S14','1313分析程序准则_中注协','https://www.cicpa.org.cn/ztzl1/Professional_standards/xxzztx/zyzz/sjzz/202105/P020240412542529330962.pdf','pdf','官方准则_现代方法'),
 ('S15','2001民生银行年报_银行官网','https://ir.cmbc.com.cn/media/qgeg23oq/中国民生银行股份有限公司2001年年度报告.pdf','pdf','独立交易对手原始披露'),
 ('S16','2000资产负债表_新浪结构化转录','https://money.finance.sina.com.cn/corp/go.php/vFD_BalanceSheet/stockid/600709/ctrl/2000/displaytype/4.phtml','html','平台财务表_非年报全文'),
 ('S17','2000利润表_新浪结构化转录','https://money.finance.sina.com.cn/corp/go.php/vFD_ProfitStatement/stockid/600709/ctrl/2000/displaytype/4.phtml','html','平台财务表_非年报全文'),
 ('S18','2000现金流量表_新浪结构化转录','https://money.finance.sina.com.cn/corp/go.php/vFD_CashFlow/stockid/600709/ctrl/2000/displaytype/4.phtml','html','平台财务表_非年报全文'),
]

def download():
    def one(row):
        sid,title,url,ext,grade=row
        path=RAW/f'{sid}_{title}.{ext}'
        try:
            # Percent-encode only non-ASCII characters in official IR paths.
            import urllib.parse
            url=urllib.parse.quote(url,safe=':/?=&;%')
            b=get(url)
            if ext=='pdf' and not b.startswith(b'%PDF'):raise ValueError('非PDF响应')
            path.write_bytes(b)
            d={'id':sid,'title':title,'url':url,'file':str(path.relative_to(OUT)),'grade':grade,'bytes':len(b),'sha256':hashlib.sha256(b).hexdigest(),'retrieved':'2026-11-02'}
            if ext=='html':
                s=decode(b)
                (ROOT/'tmp'/f'{sid}.html').write_text(s,encoding='utf-8')
                d['title_tag']=re.findall(r'<title[^>]*>(.*?)</title>',s,re.S)[:1]
            return d
        except Exception as e:return {'id':sid,'title':title,'url':url,'grade':grade,'error':str(e)}
    result=list(concurrent.futures.ThreadPoolExecutor(max_workers=6).map(one,SOURCES))
    (OUT/'来源清单.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
    for r in result:print(r['id'],r.get('bytes'),r.get('error','OK'),r.get('title_tag',''))

if __name__=='__main__':
    if 'download' in sys.argv: download()
    elif 'cninfo' in sys.argv: cninfo()
    elif 'reportprobe' in sys.argv: reportprobe()
    elif 'oldindex' in sys.argv: oldindex()
    elif 'probe' in sys.argv: probe()
    else: indices()
