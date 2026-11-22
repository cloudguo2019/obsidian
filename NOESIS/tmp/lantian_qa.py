from pathlib import Path
import json,re
from pypdf import PdfReader
import pypdfium2 as pdfium
from PIL import Image,ImageDraw,ImageFont
from lantian_collect import ROOT,OUT,RAW

QA=ROOT/'tmp'/'lantian_pdf'/'qa';QA.mkdir(parents=True,exist_ok=True)
outputs=json.loads((ROOT/'tmp'/'lantian_outputs.json').read_text(encoding='utf-8'))
font=ImageFont.truetype('C:/Windows/Fonts/msyh.ttc',18)
for part in ['manual','S04_reflow','S05_reflow','S06_reflow','S07_reflow','S08_reflow','S09_reflow','S18_reflow','index']:
    p=ROOT/'tmp'/'lantian_pdf'/f'{part}.pdf';doc=pdfium.PdfDocument(str(p))
    images=[]
    for i in range(len(doc)):
        page=doc[i];im=page.render(scale=1.1).to_pil().convert('RGB');thumb=im.copy();thumb.thumbnail((405,575))
        tile=Image.new('RGB',(425,612),'#c9cfd2');tile.paste(thumb,((425-thumb.width)//2,25));ImageDraw.Draw(tile).text((10,589),f'{part} {i+1}',fill='black',font=font);images.append(tile)
        if part=='manual' and i in [0,3,12,13,14,15,19,22]:im.save(QA/f'manual_p{i+1:02d}.png')
    for j in range(0,len(images),6):
        batch=images[j:j+6];sheet=Image.new('RGB',(425*3,612*2),'#e0e0e0')
        for k,im in enumerate(batch):sheet.paste(im,((k%3)*425,(k//3)*612))
        sheet.save(QA/f'{part}_contact_{j//6+1}.png')
    print(part,len(doc),'pages rendered')

for out in outputs['outputs']:
    p=OUT/out['file'];r=PdfReader(str(p))
    assert len(r.pages)==out['pages']
    assert all(float(pg.mediabox.width)>0 and float(pg.mediabox.height)>0 for pg in r.pages)
    print('FINAL',out['file'],len(r.pages),'pages',len(r.outline),'bookmarks')

for sid,terms in [('S01',['560,713,384.09','649,921,228.09','89,207,844.00']),('S02',['38,094,774.28','38,094,774.78']),('S03',['-0.1216','197,980,106.04'])]:
    p=next(RAW.glob(sid+'_*.pdf'));r=PdfReader(str(p))
    print(sid,{t:[i+1 for i,p in enumerate(r.pages) if t in (p.extract_text() or '')] for t in terms})
