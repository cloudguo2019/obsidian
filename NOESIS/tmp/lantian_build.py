from pathlib import Path
import re,json,html,hashlib,zipfile
from decimal import Decimal as D
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.lib import colors
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.enums import TA_LEFT
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.platypus import SimpleDocTemplate,Paragraph,Spacer,PageBreak,Table,TableStyle,Preformatted,KeepTogether,HRFlowable
from pypdf import PdfReader,PdfWriter
from lantian_collect import ROOT,OUT,RAW

TMP=ROOT/'tmp'/'lantian_pdf';TMP.mkdir(parents=True,exist_ok=True)
pdfmetrics.registerFont(TTFont('YaHei',r'C:\Windows\Fonts\msyh.ttc',subfontIndex=0))
pdfmetrics.registerFont(TTFont('YaHeiBold',r'C:\Windows\Fonts\msyhbd.ttc',subfontIndex=0))
pdfmetrics.registerFont(TTFont('Song',r'C:\Windows\Fonts\simsun.ttc',subfontIndex=0))
W,H=A4;CW=W-38*mm
styles={
 'body':ParagraphStyle('body',fontName='YaHei',fontSize=10.5,leading=17,spaceAfter=10,wordWrap='CJK'),
 'h1':ParagraphStyle('h1',fontName='YaHeiBold',fontSize=20,leading=29,spaceAfter=18,wordWrap='CJK',textColor=colors.HexColor('#183342')),
 'h2':ParagraphStyle('h2',fontName='YaHeiBold',fontSize=14,leading=21,spaceAfter=13,wordWrap='CJK'),
 'small':ParagraphStyle('small',fontName='YaHei',fontSize=8.2,leading=12,spaceAfter=5,wordWrap='CJK'),
 'cell':ParagraphStyle('cell',fontName='YaHei',fontSize=8.5,leading=13,wordWrap='CJK'),
 'url':ParagraphStyle('url',fontName='YaHei',fontSize=7.5,leading=11,wordWrap='CJK',splitLongWords=True),
}

def para(s,style='body'):
    return Paragraph(html.escape(s).replace('\n','<br/>'),styles[style])

def foot(canvas,doc):
    canvas.saveState();canvas.setStrokeColor(colors.HexColor('#9ba9af'));canvas.setLineWidth(.3)
    canvas.line(19*mm,18*mm,W-19*mm,18*mm)
    canvas.setFont('YaHei',8);canvas.setFillColor(colors.HexColor('#52616a'))
    canvas.drawString(19*mm,13*mm,'蓝田股份 / CPA 财务分析案例 / 2026-11-02')
    canvas.drawRightString(W-19*mm,13*mm,str(doc.page));canvas.restoreState()

def build(path,story,caption=''):
    doc=SimpleDocTemplate(str(path),pagesize=A4,rightMargin=19*mm,leftMargin=19*mm,topMargin=20*mm,bottomMargin=24*mm,
       title=caption or path.stem,author='CPA案例材料整理')
    doc.build(story,onFirstPage=foot,onLaterPages=foot)

def table(rows,worksheet=False):
    n=len(rows[0]);widths=([57*mm,CW-57*mm] if n==2 else [CW/n]*n)
    if n==5: widths=[23*mm]+[(CW-23*mm)/4]*4
    dat=[[para(c,'cell') for c in row] for row in rows]
    t=Table(dat,colWidths=widths,repeatRows=1,hAlign='LEFT',minRowHeights=([25]+[42]*(len(rows)-1) if worksheet else None))
    t.setStyle(TableStyle([
      ('VALIGN',(0,0),(-1,-1),'TOP'),('BACKGROUND',(0,0),(-1,0),colors.HexColor('#e9eef0')),
      ('GRID',(0,0),(-1,-1),.35,colors.HexColor('#a2adb3')),
      ('LEFTPADDING',(0,0),(-1,-1),6),('RIGHTPADDING',(0,0),(-1,-1),6),
      ('TOPPADDING',(0,0),(-1,-1),7),('BOTTOMPADDING',(0,0),(-1,-1),7),
    ]));return t

def markdown_pdf():
    text=(OUT/'分析方法与案例讲义.md').read_text(encoding='utf-8')
    story=[]
    for idx,page in enumerate(text.split('---PAGE---')):
        if idx:story.append(PageBreak())
        lines=page.strip().splitlines();i=0
        while i<len(lines):
            line=lines[i].strip()
            if not line:i+=1;continue
            if line.startswith('# '):story.append(para(line[2:],'h1'));i+=1
            elif line.startswith('## '):story.append(para(line[3:],'h2'));i+=1
            elif line.startswith('|'):
                rows=[]
                while i<len(lines) and lines[i].strip().startswith('|'):
                    row=[x.strip() for x in lines[i].strip().strip('|').split('|')]
                    if not all(re.fullmatch('[-: ]+',c) for c in row):rows.append(row)
                    i+=1
                story.append(table(rows,worksheet=2<=idx<=7));story.append(Spacer(1,11))
            elif line.startswith('_____'):
                story.append(HRFlowable(width='100%',thickness=.35,color=colors.HexColor('#a2adb3'),spaceBefore=14,spaceAfter=13));i+=1
            elif re.match(r'^\d+\.',line):
                story.append(para(line));i+=1
            else:
                chunk=[line];i+=1
                while i<len(lines) and lines[i].strip() and not lines[i].startswith(('#','|','_____')) and not re.match(r'^\d+\.',lines[i]):
                    chunk.append(lines[i].strip());i+=1
                story.append(para(' '.join(chunk)))
    path=TMP/'manual.pdf';build(path,story,'蓝田股份：CPA财务分析方法与案例');return path

def recover_penalty():
    text='''中国证监会关于胡丕华、秦凤英违反证券法规行为的处罚决定
发布日期及生效日期：1999-10-15
发布文号：证监罚字（1999）33号
发布部门：中国证监会

获取说明：原网址普通下载返回空壳。本文件根据2026-11-02可读检索页面的正文恢复，非证监会官网原件，非原网页字节副本。原转载入口：https://law1.110.com/law_79493.html 。仅恢复与本案例相关的文书正文，不录转载网页导航及罚款汇款账户。

胡丕华、秦凤英：
中国证券监督管理委员会对胡丕华、秦凤英违反证券法规问题进行了调查。
一、违规事实
1995年末至1996年2月，原沈阳会计师事务所注册会计师胡丕华、秦凤英在为拟公开发行股票的沈阳蓝田股份有限公司（以下简称“蓝田公司”）进行财务审计时，没有按照勤勉尽职原则对公司货币资金进行认真核查和验证，未发现和指出蓝田公司虚增1995年巨额银行存款问题，出具了无保留意见的审计报告，误导投资者。
二、处罚决定
胡丕华、秦凤英的上述行为违反了《股票发行与交易管理暂行条例》第十八条的规定，构成该条例第七十四条第二项所述的行为。
根据该条例第七十四条的规定，对在为蓝田公司出具的审计报告上签字的注册会计师胡丕华、秦凤英分别处以警告并各罚款3万元。
原文另列罚款缴纳和行政复议、诉讼事项。此为有明确删节说明的文书摘录。
'''
    p=RAW/'S09_审计师处罚文书正文恢复摘录.txt';p.write_text(text,encoding='utf-8');return text

def html_body(sid):
    if sid=='S18':
        s=(ROOT/'tmp'/'S18_compact.txt').read_text(encoding='utf-8')
        start=s.find('| 报表日期');end=s.find('| 附注',start)
        return s[start:end]+'\n\n以上为平台现金流主表节选。完整网页及附注在原始资料。单位：万元。\n不能与平台的重编资产负债表、利润表拼接；本表不是2000年报原件。'
    if sid in ['S07','S08']:
        raw=(ROOT/'tmp'/f'{sid}.html').read_text(encoding='utf-8')
        match=re.search(r'<pre[^>]*>([\s\S]*?)</pre>',raw,re.I)
        if match:
            return html.unescape(re.sub(r'<[^>]+>','',match.group(1))).strip()
    s=(ROOT/'tmp'/f'{sid}_compact.txt').read_text(encoding='utf-8')
    if sid in ['S04','S05','S06']:
        title={'S04':'沈阳蓝田股份有限公司招股说明书根要','S05':'沈阳蓝田股份有限公司股票上市公告书','S06':'湖北蓝田股份有限公司2001年中期报告补充说明'}[sid]
        # Remove duplicated webpage title/date/header, retain body heading.
        k=s.find(title);k2=s.find(title,k+len(title));s=s[k2 if k2>=0 else k:]
        ends=[s.find(t) for t in ['关闭窗口','相关信息'] if s.find(t)>=0]
        if ends:s=s[:min(ends)]
    else:
        if sid=='S08':start=s.find('1.99.8.11')
        else:start=s.find('重 要 提 示')
        s=s[start:]
        for end in ['新浪网财经纵横网友意见留言板','新浪简介','网站简介','相关链接','发表评论']:
            k=s.find(end)
            if k>=0:s=s[:k]
    return '\n'.join(x for x in s.splitlines() if x.strip() not in ['|','| |'])

def wrap_pre(s,maxwidth=CW,fs=8.4):
    lines=[]
    for line in s.splitlines():
        if not line.strip():lines.append('');continue
        cur=''
        for ch in line.replace('\t','    '):
            if pdfmetrics.stringWidth(cur+ch,'Song',fs)>maxwidth-3:
                lines.append(cur);cur='  '+ch
            else:cur+=ch
        lines.append(cur)
    return '\n'.join(lines)

def source_html_pdfs(manifest):
    files={}
    for sid in ['S04','S05','S06','S07','S08','S09','S18']:
        r=next(x for x in manifest if x['id']==sid)
        text=recover_penalty() if sid=='S09' else html_body(sid)
        note='公司披露/政府文书网页文字重排；原网页字符与错字保留，非原版面扫描。S09为明确删节的正文恢复摘录。'
        if sid=='S18':note='平台数据质量反例及旧现金流辅助转录。采集于2026-11-02，非原年度报告；单位万元。主表节选供复算，保留原表期间及字段。'
        story=[para(sid+' | '+r['title'],'h2'),para(note,'small'),para('原始来源：'+r['url'],'url'),Spacer(1,8)]
        story.append(Preformatted(wrap_pre(text),ParagraphStyle('pre',fontName='Song',fontSize=8.4,leading=12.5)))
        p=TMP/f'{sid}_reflow.pdf';build(p,story,sid+' '+r['title']);files[sid]=p
    return files

def original(sid):return next(RAW.glob(sid+'_*.pdf'))

def evidence_index(manifest,core_map,full_map):
    story=[para('证据目录与阅读位置','h1'),para('以下均使用PDF物理页码。原财报的印刷页码偶有错位；原件内审计状态和比较数调整优先于转录平台。目录中的核心册/完整册页码可直接用于打印或定位。')]
    rows=[['编号与材料','核心册PDF页','完整册PDF页','重点']]
    focus={'S01':'中报比较数；政策调整；工程；关联方；三表','S02':'摘要与重编；无法表示意见；账套；附注；三表','S03':'继续更正；审计限制；经营现金流指标核验','S04':'上市前资产、发行与业务起点（概要）','S05':'上市时股本、资产与募集安排','S06':'现金结算、工资、折旧、广告的公司解释','S07':'2000中报披露摘要','S08':'1999关联披露和发行处罚主要内容','S09':'审计师处罚文书恢复摘录','S13':'现代函证准则，非当年处罚依据','S14':'现代分析程序准则','S15':'交易对手银行年报相关页','S18':'平台转录现金流主表节选；版本质量反例'}
    for sid in core_map:
        r=next(x for x in manifest if x['id']==sid)
        def span(mp):
            v=mp[sid];return f'{v[0]}-{v[-1]}' if len(v)>1 else str(v[0])
        rows.append([sid+' '+r['title'],span(core_map),span(full_map),focus[sid]])
    story.append(table(rows));story.append(PageBreak());story.append(para('下载来源与资料缺口','h1'))
    for r in manifest:
        story.append(para(r['id']+' '+r['title']+' | '+r.get('grade',''),'small'));story.append(para(r['url'],'url'))
    story.append(para('S10/S11/S12保留下载原网页，分别为作者历史推理、独立评论和司法日期报道，仅作阅读索引；不是监管或法院原件。S16/S17/S18为跨版本数据质量反例，不能合并成一套三表。完整原始网页、完整银行年报及机器可读来源清单均在资料包内。','small'))
    p=TMP/'index.pdf';build(p,story,'蓝田案例证据目录与来源');return p

def build_all():
    manifest=json.loads((OUT/'来源清单.json').read_text(encoding='utf-8'))
    for r in manifest:
        if r['id']=='S09':r['download_status']='原网页空壳；正文另从检索可读页面恢复为摘录';r['usable_as_original']=False
        if r['id'] in ['S16','S17','S18']:r['usage']='数据质量反例；不与其他版本自动拼接'
    (OUT/'来源清单.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2),encoding='utf-8')
    manual=markdown_pdf();reflows=source_html_pdfs(manifest)
    recovery=RAW/'S09_审计师处罚文书正文恢复摘录.txt'
    next(r for r in manifest if r['id']=='S09').update({'recovered_file':str(recovery.relative_to(OUT)),'recovered_sha256':hashlib.sha256(recovery.read_bytes()).hexdigest()})
    (OUT/'来源清单.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2),encoding='utf-8')
    # Preserve original PDFs unchanged; selected pages in the core volume are exact page copies.
    core_select={
     'S01':[1,2,6,11,12,16,17,18,19,22,27,28,35,36,37],
     'S02':[3,5,20,21,28,29,34,35,45,49,52,54,55,56,57,58,59],
     'S03':[4,5,16,22,26,33],
    }
    order=['S04','S05','S08','S09','S06','S07','S18','S01','S02','S03','S15','S13','S14']
    def parts(core):
        result=[]
        for sid in order:
            p=reflows[sid] if sid in reflows else original(sid)
            n=len(PdfReader(str(p)).pages)
            sel=core_select.get(sid,list(range(1,n+1))) if core else list(range(1,n+1))
            if sid=='S15':sel=[37]  # Full 92-page bank report remains in downloaded originals.
            result.append((sid,p,sel))
        return result
    cparts=parts(True);fparts=parts(False)
    nmanual=len(PdfReader(str(manual)).pages)
    nindex=3
    for _ in range(3):
        def mapping(ps,offset):
            m={};pos=offset+1
            for sid,p,sel in ps:m[sid]=list(range(pos,pos+len(sel)));pos+=len(sel)
            return m
        cm=mapping(cparts,nmanual+nindex);fm=mapping(fparts,nindex)
        index=evidence_index(manifest,cm,fm);actual=len(PdfReader(str(index)).pages)
        if actual==nindex:break
        nindex=actual
    else:raise ValueError('目录页数未稳定')
    outputs=[]
    for kind,ps,outname,pre in [
       ('核心册',cparts,'01_核心打印册_方法底稿与关键证据.pdf',[manual,index]),
       ('完整册',fparts,'02_完整原始证据册_已取得资料.pdf',[index])]:
        writer=PdfWriter()
        for p in pre:writer.append(str(p),import_outline=False,outline_item='方法与工作底稿' if p==manual else '证据目录与来源')
        for sid,p,sel in ps:
            writer.append(str(p),pages=[v-1 for v in sel],import_outline=False,outline_item=sid+' '+next(x['title'] for x in manifest if x['id']==sid))
        writer.add_metadata({'/Title':'蓝田股份 CPA财务分析 '+kind,'/Author':'CPA案例材料整理','/Subject':'原始披露、数据版本、现金与资产核验'})
        path=OUT/outname
        with path.open('wb') as f:writer.write(f)
        outputs.append({'file':outname,'pages':len(writer.pages),'bytes':path.stat().st_size})
    srcindex=['# 来源与页码索引','', '下载日期：2026-11-02。页码均为PDF物理页码。','']
    for r in manifest:
        sid=r['id'];srcindex += [f"## {sid} {r['title']}",f"- 来源：{r['url']}",f"- 性质：{r['grade']}",f"- 本地文件：{r.get('file','未下载')}",f"- SHA-256：{r.get('sha256','无')}"]
        if sid in cm:srcindex += [f'- 核心册：{cm[sid][0]}-{cm[sid][-1]}页；完整册：{fm[sid][0]}-{fm[sid][-1]}页']
        if sid in core_select:srcindex += ['- 核心册原件页：'+','.join(map(str,core_select[sid]))]
        if r.get('download_status'):srcindex += ['- 状态：'+r['download_status']]
        if r.get('usage'):srcindex += ['- 用途：'+r['usage']]
        srcindex+=['']
    (OUT/'来源与页码索引.md').write_text('\n'.join(srcindex),encoding='utf-8')
    readme=f'''# 蓝田股份 CPA 财务分析打印包

## 直接打印

- `{outputs[0]['file']}`：{outputs[0]['pages']}页。含六张独立工作底稿、方法与案例讲义、资料目录和关键原始证据。先做底稿，再读分析。
- `{outputs[1]['file']}`：{outputs[1]['pages']}页。含已取得的三份完整巨潮财报，以及指定披露网页的文字重排、两份官方审计准则、民生银行相关原页。用于补查附注，核心册已经重复节选了必要页。

A4黑白，100%或适合可打印区域，双面长边翻页。保留原件页面自动旋转，不要把横向财报强制缩成竖版。无需两册全部重复打印。

## 原始文件

`原始资料`保存3份蓝田/生态年报中报PDF、招股概要和上市等披露网页、历史分析原网页、2份官方准则、完整银行年报及平台数据质量反例。原PDF未改写。HTML重排件明确标注，不是原版面扫描。S09普通下载返回空壳，另有从可读检索页恢复的文书摘录，不能当作官网原件。

## 不可忽略的资料缺口

未取得1999及2000年报全文原件、1999处罚书官网原件、当期内参版面、刑事判决与鉴定原件、全部同业原始报表、实际银行/客户/工程/税务底稿。本包不能替代完整司法案卷。关键缺口、口径及替代来源在讲义和来源索引逐项说明。

2000经营现金流为正；2001中报比较数与年度原披露不同；2001年报改用另一账套重编且审计师无法表示意见。不得把不同版本三表拼接，或把重编差额直接叫司法认定造假金额。

本包按“CPA已经学完”的假设设计，不改动NOESIS日常计划、成绩或学习完成记录。
'''
    (OUT/'00_打印说明.md').write_text(readme,encoding='utf-8')
    metrics={'current_ratio_original':str(D('433106703.98')/D('560713384.09')),
      'quick_ratio_original':str((D('433106703.98')-D('236384086.72'))/D('560713384.09')),
      'nwc_original':str(D('433106703.98')-D('560713384.09')),
      'current_ratio_interim_comparative':str(D('433106703.98')/D('649921228.09')),
      'quick_ratio_interim_comparative':str((D('433106703.98')-D('236384086.72'))/D('649921228.09')),
      'cfo_profit_approx':str(D('785829600')/D('431628612.17')),
      'capex_cfo_approx':str(D('719323400')/D('785829600')),
      'fcf_approx_yuan':str(D('785829600')-D('719323400')),
      '2000_revenue_disclosure_difference':str(D('1840909605.20')-D('38094774.78')),
      '2000_profit_disclosure_difference':str(D('431628612.17')+D('10686569.22')),
      '1999_2000_profit_disclosure_difference':str(D('431628612.17')+D('513027676.07')+D('10686569.22')+D('22879728.64'))}
    (OUT/'计算复核.json').write_text(json.dumps(metrics,ensure_ascii=False,indent=2),encoding='utf-8')
    (ROOT/'tmp'/'lantian_outputs.json').write_text(json.dumps({'outputs':outputs,'manual_pages':nmanual,'index_pages':nindex,'core_map':cm,'full_map':fm},ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps({'outputs':outputs,'manual_pages':nmanual,'index_pages':nindex,'metrics':metrics},ensure_ascii=False,indent=2))

if __name__=='__main__':build_all()
