from lantian_collect import ROOT,OUT,RAW,decode
from pypdf import PdfReader
from html.parser import HTMLParser
import re,json

class Plain(HTMLParser):
    def __init__(self):super().__init__();self.text=[];self.skip=0
    def handle_starttag(self,t,a):
        if t in ['script','style']:self.skip+=1
        if t in ['p','br','tr','div','pre']:self.text.append('\n')
        if t in ['td','th']:self.text.append(' | ')
    def handle_endtag(self,t):
        if t in ['script','style']:self.skip=max(0,self.skip-1)
    def handle_data(self,s):
        if not self.skip:self.text.append(s)

for p in RAW.glob('*'):
    if p.suffix.lower()=='.pdf':
        r=PdfReader(str(p));txt='\n'.join(f'\n=== PDF第{i+1}页 ===\n'+(page.extract_text() or '') for i,page in enumerate(r.pages));print(p.name,len(r.pages),'pages',len(txt),'chars')
    else:
        s=decode(p.read_bytes());parser=Plain();parser.feed(s);txt=''.join(parser.text);txt=txt.replace('\x7f',' ');txt=re.sub(r'\n[ \t]*\n+','\n',txt)
        print(p.name,len(txt),'chars',txt[:70].strip())
    (ROOT/'tmp'/f'{p.name.split("_")[0]}.txt').write_text(txt,encoding='utf-8')
