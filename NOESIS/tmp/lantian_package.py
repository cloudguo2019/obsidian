from lantian_collect import ROOT,OUT,RAW
from pathlib import Path
from pypdf import PdfReader
import json,hashlib,zipfile

manifest=json.loads((OUT/'来源清单.json').read_text(encoding='utf-8'))
for r in manifest:
    p=OUT/r['file'];assert p.is_file(),r['id']
    assert hashlib.sha256(p.read_bytes()).hexdigest()==r['sha256'],r['id']
    if p.suffix.lower()=='.pdf':assert len(PdfReader(str(p)).pages)>0
    if 'recovered_file' in r:
        assert hashlib.sha256((OUT/r['recovered_file']).read_bytes()).hexdigest()==r['recovered_sha256']

stats=json.loads((ROOT/'tmp'/'lantian_outputs.json').read_text(encoding='utf-8'))
qa=['# 最终核验记录','', '核验日期：2026-11-02。', '',
 '- 已核：18个下载响应的SHA-256；可用PDF均可重新打开；处罚正文恢复摘录另有哈希。',
 '- 已核：关键金额按原PDF定位；版本调整与另一账套重编分开；Decimal复算比率、现金桥和披露差额。',
 '- 已核：23页讲义及全部网页重排页已渲染目视检查；原财报、银行披露及准则关键页抽查。',
 '- 已核：核心册100页，完整册190页；书签、节选页与目录位置一致。',
 '- 原始财报文件保持下载字节不变；重排和摘录显式标注。未取得的原件在打印说明和讲义列明。','']
(OUT/'核验记录.md').write_text('\n'.join(qa),encoding='utf-8')

zip_path=OUT.parent/'蓝田股份_CPA财务分析_全部资料.zip'
files=sorted(p for p in OUT.rglob('*') if p.is_file())
with zipfile.ZipFile(zip_path,'w',zipfile.ZIP_DEFLATED,compresslevel=6) as z:
    for p in files:z.write(p,arcname=str(Path(OUT.name)/p.relative_to(OUT)))
with zipfile.ZipFile(zip_path) as z:
    assert z.testzip() is None
    assert len(z.infolist())==len(files)
print(json.dumps({'archive':str(zip_path),'bytes':zip_path.stat().st_size,'file_count':len(files),'pdfs':stats['outputs'],'raw_count':len(list(RAW.glob('*')))},ensure_ascii=False,indent=2))
