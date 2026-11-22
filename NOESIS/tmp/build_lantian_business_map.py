from pathlib import Path
from PIL import Image, ImageDraw, ImageFont
import math

ROOT = Path(__file__).resolve().parent
OUT = ROOT / '蓝田股份_核心业务图_2001_2026-11-06.png'
W, H = 1600, 1350
im = Image.new('RGB', (W, H), '#f5f7fb')
d = ImageDraw.Draw(im)
font_path = r'C:\Windows\Fonts\msyh.ttc'
bold_path = r'C:\Windows\Fonts\msyhbd.ttc'
fonts = {}

def font(size, bold=False):
    key = size, bold
    if key not in fonts:
        fonts[key] = ImageFont.truetype(bold_path if bold else font_path, size)
    return fonts[key]

def txt(x, y, value, size=24, fill='#25334a', bold=False, anchor=None):
    d.text((x,y), value, font=font(size,bold), fill=fill, anchor=anchor)

def arrow(points, color, width=4, both=False, dash=False):
    if dash:
        for p0, p1 in zip(points, points[1:]):
            dx, dy = p1[0]-p0[0], p1[1]-p0[1]
            length = math.hypot(dx,dy)
            for k in range(0, int(length), 17):
                a, b = k/length, min(k+10,length)/length
                d.line((p0[0]+dx*a,p0[1]+dy*a,p0[0]+dx*b,p0[1]+dy*b),fill=color,width=width)
    else:
        d.line(points, fill=color, width=width, joint='curve')
    def tip(a, b):
        theta = math.atan2(b[1]-a[1], b[0]-a[0])
        length, spread = 15, .48
        p1=(b[0]-length*math.cos(theta-spread), b[1]-length*math.sin(theta-spread))
        p2=(b[0]-length*math.cos(theta+spread), b[1]-length*math.sin(theta+spread))
        d.polygon([b,p1,p2],fill=color)
    tip(points[-2],points[-1])
    if both:
        tip(points[1],points[0])

def label(x,y,value,color,size=21):
    lines=value.split('\n')
    heights=(size+9)*len(lines)
    maxw=max(d.textlength(s,font=font(size)) for s in lines)
    d.rounded_rectangle((x-maxw/2-7,y-5,x+maxw/2+7,y+heights),radius=6,fill='#f5f7fb')
    for i,s in enumerate(lines):
        txt(x,y+i*(size+9),s,size,color,anchor='mt')

def node(x,y,w,h,title,body,color,fill):
    d.rounded_rectangle((x+3,y+5,x+w+3,y+h+5),radius=17,fill='#e6ebf2')
    d.rounded_rectangle((x,y,x+w,y+h),radius=17,fill=fill,outline=color,width=2)
    d.rounded_rectangle((x,y,x+8,y+h),radius=4,fill=color)
    txt(x+22,y+18,title,24,color,True)
    for i,s in enumerate(body):
        txt(x+22,y+60+i*33,s,22)
        assert d.textlength(s,font=font(22)) <= w-40, s
    assert d.textlength(title,font=font(24,True)) <= w-40, title

txt(65,36,'蓝田股份：谁生产、谁付款、谁持有资产、谁承担风险',35,'#17263c',True)
txt(65,94,'2001年案例 · 主体以中报披露为主，年报重编及后续风险另作提示',24,'#5e6b7e')

navy,teal,blue,purple,orange = '#355f9c','#18816f','#2d75bb','#8055a0','#ae7030'

# Draw the funding route first so the other labels remain unobstructed.
arrow([(1000,940),(1070,940),(1070,375),(945,375),(945,325)],purple,both=True,dash=True)

# Directional edges. A crossing is not a transaction junction.
arrow([(470,244),(600,244)],navy)
label(535,204,'35.70%',navy)
arrow([(1130,265),(1000,265)],blue)
label(1065,225,'贷款',blue)
arrow([(800,325),(800,480)],blue)
label(800,378,'出资 / 周转资金',blue)

arrow([(600,535),(470,535)],orange)
label(535,495,'生产投入',orange)
arrow([(470,615),(600,615)],teal)
label(535,575,'交售产品',teal)
arrow([(1000,535),(1130,535)],teal)
label(1065,495,'产品',teal)
arrow([(1130,615),(1000,615)],blue)
label(1065,575,'货款',blue)

arrow([(700,680),(700,850)],teal)
label(688,739,'委托代销\n商品',teal)
arrow([(905,850),(905,680)],blue)
label(920,739,'货款\n结算',blue)
arrow([(600,929),(470,929)],purple)
label(535,890,'广告费',purple)

# The funding route bypasses the production company: it is not goods revenue.
label(1070,703,'双向资金\n往来',purple,20)

node(60,180,410,145,'洪湖蓝田经济技术开发公司',[
    '直接控股股东｜持股35.70%',
    '提供资金、以持有股票作质押',
],orange,'#fff5e6')
node(600,180,400,145,'蓝田股份（600709）',[
    '上市公司母公司｜融资与投资',
    '部分借款及对外担保责任',
],navy,'#edf4ff')
node(1130,180,410,145,'银行及其他资金提供方',[
    '贷款、信用与抵质押安排',
    '按合同识别债务人与担保人',
],blue,'#edf6fd')
node(60,480,410,200,'承包农户 / 承包型职工',[
    '实际种养，按约交售产品',
    '公司提供设施、种苗、饲料等',
    '灾害、减产责任需查承包合同',
],teal,'#eaf7f2')
node(600,480,400,200,'洪湖水产品生产体系',[
    '养殖、加工、食品、宾馆旅游',
    '主要生产设施、工程与库存',
    '中报持股100%*',
],teal,'#eaf7f2')
node(1130,480,410,200,'提货客户及其他客户',[
    '购买水产品、食品等',
    '公司称基地销售钱货两清',
    '实际付款人与银行入账待核',
],teal,'#eff8f3')
node(60,850,410,170,'媒体 / 广告服务商',[
    '据公司公告，广告签约付款方',
    '为中国蓝田总公司',
],purple,'#f6effb')
node(600,850,400,170,'中国蓝田总公司及销售网络',[
    '关联代销、广告付款',
    '并与上市公司存在资金往来',
],purple,'#f6effb')
node(1130,850,410,170,'风险沿合同跨主体传递',[
    '生产体系：库存、工程、收款',
    '上市公司：借款及对外担保',
    '控股股东：质押股票受限',
], '#ab5550','#fff0ed')

notes=[
    '其他主体：洪福水产持股18.85%；沈阳蓝田房屋80%；北京蓝田园中报80%，年报称年内转回。',
    '* 版本冲突：洪湖水产品中报100%，年报85.29%；不能直接认定发生股权转让。',
    '年报另披露印铁制罐、生态养殖两家未单列生产单位；饮料及制罐资产拟售，但抵押与转移手续未解决。',
    '证据边界：箭头为披露安排；账面资产不等于已确权，业务关系不等于已验证现金流。年报审计无法表示意见。',
]
d.rounded_rectangle((60,1070,1540,1285),radius=17,fill='#eaf0f7')
for i,s in enumerate(notes):
    txt(82,1090+i*43,s,22,'#43516b')
    assert d.textlength(s,font=font(22))<1440,s
txt(65,1304,'来源：S01第3、11—12、28—31页；S06；S02第15、20—21、28—29、49—52页。整理：2026-11-06。',20,'#627086')
im.save(OUT)
print(OUT)
