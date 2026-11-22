from lantian_collect import RAW,ROOT
from pypdf import PdfReader
import re
for sid,terms in [('S01',['会计估计','在建工程','关联方关系','未经审计','货币资金']),('S02',['会计差错更正','审计报告','合并资产负债表']),('S03',['审计报告','虚记','会计差错更正','合并资产负债表']),('S15',['湖北江湖','湖北蓝田'])]:
    p=next(RAW.glob(sid+'_*.pdf'));r=PdfReader(str(p))
    for i,pg in enumerate(r.pages):
        s=pg.extract_text() or ''
        keys=[k for k in terms if k in s]
        if keys: print(sid,i+1,','.join(keys),s[:30].replace('\n',' '))
for sid in ['S04','S05','S06','S07','S08','S16','S17','S18']:
    s=(ROOT/'tmp'/f'{sid}.txt').read_text(encoding='utf-8')
    lines=[x.strip() for x in s.splitlines() if x.strip()]
    (ROOT/'tmp'/f'{sid}_compact.txt').write_text('\n'.join(lines),encoding='utf-8')
    if sid in ['S16','S17','S18']:
        start=next((i for i,x in enumerate(lines) if '报表日期' in x),0)
        print(sid,'\n'.join(lines[start:start+90]))
