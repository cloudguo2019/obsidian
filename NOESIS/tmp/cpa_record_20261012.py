from pathlib import Path
import re
from datetime import date, timedelta

root = Path(r'C:\Users\cg\Desktop\Nietzsche\obsidian\NOESIS')
names = ['00-NOESIS控制台.md', '90-学习错误与问题台账.md', '92-CG-CPA长期记忆.md', '09-10月逐日教学计划.md', '08-会计税法四个月并行计划.md', '91-公式与精确规则表.md']
raw = {n: (root / n).read_bytes() for n in names}
docs = {n: b.decode('utf-8-sig').replace('\r\n', '\n') for n, b in raw.items()}

def once(s, old, new):
    assert s.count(old) == 1, (old[:70], s.count(old))
    return s.replace(old, new, 1)

def change_error(s, ident, review, repeat=None):
    pat = rf'(?m)^\| {re.escape(ident)} \|[^\n]+$'
    m = re.search(pat, s)
    assert m, ident
    cells = m.group().split('|')
    cells[-3] = ' ' + review + ' '
    if repeat is not None:
        cells[-2] = ' ' + str(repeat) + ' '
    return s[:m.start()] + '|'.join(cells) + s[m.end():]

# The learner explicitly deferred the new accounting applications. Reserve
# the next three accounting slots for them; shift unexecuted accounting only.
pname = '09-10月逐日教学计划.md'
p = docs[pname]
assert '2026-10-12会计应用延后衔接' not in p
matches = list(re.finditer(r'(?m)^### (10-\d{2})｜[^\n]+\n', p))
blocks = {}
for i, m in enumerate(matches):
    end = matches[i+1].start() if i+1 < len(matches) else p.index('## 四、')
    blocks[m.group(1)] = (m.start(), end, p[m.start():end])
old_codes = {}
for day in range(12, 29):
    key = f'10-{day:02d}'
    body = blocks[key][2]
    area = re.search(r'\*\*会计\*\*\n\n(.*?)\n\*\*税法\*\*', body, re.S)
    assert area, key
    old_codes[key] = re.findall(r'\*\*(A\d{2}-\d{2})\*\*', area.group(1))

def prereq(body, kind):
    m = re.search(r'(?m)^\*\*前置\*\*：([^\n]+)', body)
    if not m:
        return '沿已有独立应用证据'
    pieces = [x.strip() for x in re.split('[；。]', m.group(1)) if x.strip()]
    chosen = [x for x in pieces if ('T02' in x) == (kind == 'tax')]
    return '；'.join(chosen) or '沿本编号已列前置与90实际证据'

replacement_blocks = {}
for day in range(13, 29):
    key, prev = f'10-{day:02d}', f'10-{day-1:02d}'
    body, previous = blocks[key][2], blocks[prev][2]
    area = re.search(r'\*\*会计\*\*\n\n(.*?)\n\*\*税法\*\*', body, re.S)
    prior_area = re.search(r'\*\*会计\*\*\n\n(.*?)\n\*\*税法\*\*', previous, re.S).group(1)
    if day == 13:
        new_area = ('本日三个会计名额用于10-12已教模块的首次闭卷提取与独立应用，已教内容不重讲。\n\n'
                    '- **A11-01**：首次应用借款费用四类组成、折溢价方向、专门/一般借款、合格资产、资本化/费用化对象及分录影响。\n'
                    '- **A11-02**：首次应用资产支出三种形式、开始/暂停/停止、正常中断与超过3个月门槛、独立完工与整体完工时间线。\n'
                    '- **A11-03**：首次应用专门借款净利息、多笔一般借款本金及超额支出加权、资本化率、实际利息上限、辅助费用及实际利率折溢价。\n')
    else:
        new_area = prior_area
    body = body[:area.start(1)] + new_area + body[area.end(1):]
    old_head = body.splitlines()[0]
    parts = old_head.split('｜', 2)
    tax_title = parts[2].split('；', 1)[-1]
    account_title = '借款费用首次提取与应用' if day == 13 else previous.splitlines()[0].split('｜', 2)[2].split('；', 1)[0]
    new_head = parts[0] + '｜' + parts[1] + '｜' + account_title + '；' + tax_title
    body = once(body, old_head, new_head)
    body = re.sub(r'(?m)^\*\*模块数\*\*：会计\d+个、税法(\d+)个。', lambda m: '**模块数**：会计' + str(3 if day == 13 else len(old_codes[prev])) + '个、税法' + m.group(1) + '个。', body, count=1)
    new_pre = '**前置**：会计：' + prereq(previous, 'account') + '。税法：' + prereq(blocks[key][2], 'tax') + '。'
    body = re.sub(r'(?m)^\*\*前置\*\*：[^\n]+', lambda _: new_pre, body, count=1)
    note = ('**2026-10-12会计应用延后衔接**：' + ('今日仅做A11-01—03首次应用，占会计3个名额；原A13-01—03移10-14。' if day == 13 else '本日会计完整编号来自原' + prev + '；原本日会计编号移至下一日，税法沿本日原安排。') + '\n\n')
    body = body.replace(new_head + '\n\n', new_head + '\n\n' + note, 1)
    # Move only accounting task-table rows, preserving tax tasks in place.
    prior_rows = re.findall(r'(?m)^\| A\d{2}-\d{2} \|[^\n]+$', previous)
    body = re.sub(r'(?m)^\| A\d{2}-\d{2} \|[^\n]+\n', '', body)
    first_tax = re.search(r'(?m)^\| T\d{2}-\d{2} \|', body)
    assert first_tax, key
    body = body[:first_tax.start()] + '\n'.join(prior_rows) + '\n' + body[first_tax.start():]
    if day == 14:
        body = re.sub(r'(?m)^\*\*W2检查\*\*：[^\n]+', '**W2检查**：按90检查实际已教、已答及来源债务；A11-04/A29-01/A13-04移10-15，A13-05移10-16，尚未执行部分不得提前核销。首周来源审计仍10-14；相关移期子项10-15/16完成后补核。来源合格章节题与应用/出口合用，查93且不取终验收保留题。', body, count=1)
    if day == 28:
        body = body.replace('**W4检查**：', '**W4检查**：先完成A13-23完整教学与首次应用，再进行会计覆盖检查；', 1)
    replacement_blocks[key] = body

for day in range(28, 12, -1):
    key = f'10-{day:02d}'
    start, end, _ = blocks[key]
    p = p[:start] + replacement_blocks[key] + p[end:]

# The overview and review calendar are the execution indexes.
for day in range(13, 29):
    key, prev = f'10-{day:02d}', f'10-{day-1:02d}'
    pat = rf'(?m)^\| {key} \| ([^|]+) \| ([^|]+) \| (\d+)/([012]) \|$'
    m = re.search(pat, p)
    assert m, ('overview', key)
    codes = ['A11-01', 'A11-02', 'A11-03'] if day == 13 else old_codes[prev]
    text_codes = '、'.join(codes) + ('（已教，首次应用）' if day == 13 else '')
    new = f'| {key} | {text_codes} | {m.group(2).strip()} | {len(codes)}/{m.group(4)} |'
    p = p[:m.start()] + new + p[m.end():]
p = p.replace('计划新模块数（会计/税法）', '完整模块名额（会计/税法）', 1)
for day in range(12, 29):
    key = f'10-{day:02d}'
    pat = rf'(?m)^\| {key} \| ([^|]+) \| (1[01]-\d{{2}}) \| (1[01]-\d{{2}}) \| (1[01]-\d{{2}}) \| (1[01]-\d{{2}}) \| (1[12]-\d{{2}}) \|$'
    m = re.search(pat, p)
    assert m, ('calendar', key)
    tax_codes = re.findall(r'T\d{2}-\d{2}', m.group(1))
    ac = ['A11-01', 'A11-02', 'A11-03'] if day == 12 else ([] if day == 13 else old_codes[f'10-{day-1:02d}'])
    combined = '、'.join(ac + tax_codes)
    new = f'| {key} | {combined} | ' + ' | '.join(m.group(i) for i in range(2, 7)) + ' |'
    p = p[:m.start()] + new + p[m.end():]

def shift_date_tokens(s):
    return re.sub(r'10-(1[3-9]|2[0-7])', lambda m: f'10-{int(m.group(1))+1:02d}', s)
lines = p.splitlines()
for i, line in enumerate(lines):
    if line.startswith('| 会计') and ' | ' in line:
        cells = line.split('|')
        if len(cells) == 6:
            if '会计11：' in cells[1]:
                cells[3] = ' 10-12教学/10-13首次应用、10-15外币 '
                cells[4] = ' 10-15（以实际独立证据为准） '
            else:
                cells[3] = shift_date_tokens(cells[3])
                if '会计29（一）' in cells[1]:
                    cells[4] = ' 10-15 '
            lines[i] = '|'.join(cells)
p = '\n'.join(lines) + '\n'
p = p.replace('会计新课至10-27', '会计新课至10-28')
change = '| 2026-10-12 | A11-01—03今日独立题及10-13起会计排期 | 用户完成合并教学，要求独立应用留到后续提取；仅今天合并交付，不改skill | 10-13三个会计名额先做A11-01—03首次应用；原10-13—27会计编号逐组顺延一天至10-14—28，税法日期保留 | A11-04/A29-01/A13-04→10-15，A13-05→10-16，A07末项→10-20，A13-23→10-28；周检查仍按实际证据，月测/复盘及01-25目标保留；A11按用户要求于教学后10-13 D1首次提取、10-15 D3、10-19 D7验证，不另加10-14整轮 |\n'
p = once(p, '\n本月完成的最终判断以真实教学与首次独立答案为准，不能从计划完整推定学习已经完成。', '\n' + change + '\n本月完成的最终判断以真实教学与首次独立答案为准，不能从计划完整推定学习已经完成。')
p = once(p, '对象为第三节该日实际安排的完整新模块。', '对象为第三节该日实际安排的完整新模块。A11-01—03于10-12完成教学；按用户指定教学日锚，10-13 D1为首次闭卷应用，10-15 D3、10-19 D7继续提取，不另加10-14整轮。首次应用与之后延迟保持分开记录，其他模块仍按实际应用日重算。')
docs[pname] = p

route = docs['08-会计税法四个月并行计划.md']
route = once(route, '## 第一个月及后续周路线', '### 10-12会计独立应用衔接\n\n用户要求今日会计教学归档，首次独立作答留后续提取。10-13会计三个名额用于A11-01—03首次应用；原10-13—27会计模块逐组顺延至10-14—28，税法日期保留，完整范围见09。A11-04/A29-01/A13-04改10-15、A13-05改10-16；A07首轮末项改10-20，公允价值进阶改10-22/23，金融披露A13-23改10-28。10-14/21/28仍作实际覆盖检查，移期项按新日期补核；10-30月测、10-31复盘、01-25首轮及01-26—31真题验收目标保留，未把教学完成等同独立应用通过。\n\n## 第一个月及后续周路线')
route = route.replace('A13-05移10-15', 'A13-05移10-16').replace('A13-04初始计量；', 'A13-04初始计量（移10-15）；').replace('第29章公允价值基本概念        |', '第29章公允价值基本概念（移10-15）        |')
docs['08-会计税法四个月并行计划.md'] = route

ledger = docs['90-学习错误与问题台账.md']
assert 'ACC-TAX-FORMAL-1012' not in ledger
row = '| 2026-10-12 | ACC-TAX-FORMAL-1012 | A | —（未可靠计时） | 32/32、32/32、40/40、40/40（均单独前置） | 32/32、32/32、37/40、40/40；四项同日修复通过 | 10-05新块实际抽测：税基负债漏项同日补齐，其余按H12；非全章指标 | —（未用真题） | 旧应用/修复M2；A11新补仅教学完成 | 用户仅今天合并会计教学，随后要求会计归档并留D1/D3/D7验证；A11-01—03已教未提交独立题，不填新课分或M3；税法本轮继续T02-05—06。 |\n'
needle = re.search(r'(?m)^\| 2026-10-11 \| ACC-TAX-FORMAL-1011 \|[^\n]+\n', ledger)
assert needle
ledger = ledger[:needle.end()] + row + ledger[needle.end():]
reviews = {
 'E-005': ('2026-10-13 D1（10-12权益净变化再现，重复8；本人同日修复+71；原首次分不改）', 8),
 'E-044': ('2026-10-13 D1（10-12减值多写借准备贷累计折旧，再现1；本人修复分录及余额50/10）', 1),
 'E-023': ('2026-10-14 D3（10-12金额/单位D1首次正确；10-18 D7，不关闭）', None),
 'E-055': ('2026-10-14 D3（10-12文化服务D1首次正确；10-18 D7，不关闭）', None),
 'E-056': ('2026-10-14 D3（10-12结论、应收及存货具体证据D1首次正确；10-18 D7/10-25 D14/11-10 D30，不关闭）', None),
 'E-053': ('2026-10-16 D7（10-12普通股双方准确分类D3正确；10-23 D14/11-08 D30）', None),
}
for ident in ['E-008', 'E-009', 'E-022', 'E-033', 'E-034', 'E-038', 'E-039', 'E-040', 'E-041', 'E-042', 'E-043', 'E-046', 'E-047']:
    reviews[ident] = ('2026-10-19保持/原D14（10-12对应触发器首次正确，具体范围见H12；E-022费用化仍10-16）', None)
for ident, (review, repeat) in reviews.items():
    ledger = change_error(ledger, ident, review, repeat)
e57 = '| E-057 | 2026-10-12 | 会计/存货灾害损失批准处理 | 灾害毁损12、保险应收3，批准处理 | 赔款正确，但借管理费用9、贷营业外支出12，未结清待处理 | 灾害净损失借营业外支出；批准时贷待处理财产损溢，赔款借其他应收款 | P | 中 | 2026-10-13 D1（本人同日两步修复正确；原题4首次3/4保留）；10-15 D3/10-19 D7/10-26 D14/11-11 D30 | 0 |\n'
m = re.search(r'(?m)^\| E-056 \|[^\n]+\n', ledger)
assert m
ledger = ledger[:m.end()] + e57 + ledger[m.end():]
h12 = '''### 2026-10-12学习与会计归档｜H12（税法进行中）

用户明确仅今天合并交付会计，并要求将今日会计教学记录为完成，独立应用留后续D1/D3/D7提取；随后要求税法T02-05—06也一次交付。skill未修改，三个A和两个T编号没有合并、扩容或增加。无可靠计时、真题或新增M3。

| 题组 | 前置预测 | 首次 | 实际证据 |
|---|---:|---:|---|
| 10-11会计D1，8题 | 32/32 | 32/32 | 无形辨认/初始、研发36转列、摊销10万=100000元、寿命不确定、处置收益5现金55、列示60/18/17/5、AI去重75及结论/具体证据；E-023/E-056实际抽测通过 |
| 税法D1及细名，8题 | 32/32 | 32/32 | 景区文化/认证鉴证咨询；普通视同/非应税/免税复习；重组、金融50/税3、资管/预付卡、登记515及10-01生效、挂靠/境外扣缴40/2.4；E-055 D1通过；不是全书后T02-02专项回看 |
| 10-05 D7与旧错，10题 | 40/40 | 37/40 | 题1/3/5/7/9/10各4；题2=3.5、题4=3、题6=3.5、题8=3。负债税基/类型漏写、灾害批准两账户错、权益漏全部利润且77/80冲突、多写减值准备转累计折旧。预测偏差+7.5pp；正确题不撤销 |
| 10-09 D3与E-053，10题 | 40/40 | 40/40 | 存货确认归属/个别65/35及成本52、合同准备450/账面7550；设备100/70、测试83/利润3、暂估212/8/204；延期300/63/30/33/330；弃置220/40/4/44；普通股双方和预付款准确；立法概念/权限/施行及17项有效税种、征管/稽查/复议正确 |

第9题第18小项题干直接出现城市维护建设税名，撤出独立证据，税种题按其余17项归一计4分。第10题中央110、地方90合计正确，题干未明确两税分列，歧义不扣分；随后说明增值税50/50、共享所得税60/40。存货商品/指定机关/船舶吨谁及资产处置损溢按明确笔误处理；额外收入分录只有已收款时成立，不据未交代收款事实扣分。五原则教材逐字标签、分类标签及其他教师核源仍10-14。

四项本人同日修复：负债税基0、可抵扣差异24；灾害发现及批准两步正确（其他应收3/营业外9/待处理12）；权益净增加71；减值只借损失10贷固定资产准备10，累计折旧50/准备10。原37/40保留。E-005/E-044再现、E-057新增，次日D1；负债基数漏写只记Q表达分支，不否定资产税基及税款作用的D7正确部分。

| 编号 | 本次状态 | 范围与下一步 |
|---|---|---|
| A11-01 | 教学已完成，已教学待独立应用 | 四类费用、折溢方向、借款类型、合格资产、分录/报表；原待答题并入合稿1—2，尚未作答 |
| A11-02 | 教学已完成，已教学待独立应用 | 资产支出三形式、开始/暂停/停止、正常及3个月边界、分别/整体完工；合稿第3题未答 |
| A11-03 | 教学已完成，已教学待独立应用 | 净专借、多笔一般及超额支出加权、上限、辅助费用、实际利率；合稿4—6未答，例子71.75是教师示范，不是学习者成绩 |
| 会计出口 | 已展示未答 | 合稿第7题未答，不登记出口分或闭环完成 |
| T02-05/T02-06 | 本轮继续完整教学与合并应用 | 税率矩阵/零免进项，税率征收率/兼营与单项主附；待本轮提交后评分，不提前填新课分 |

会计教学完成按用户意愿归档，不等于新增细项已独立应用；历史9月借款基础M2保留。本日借款新补部分没有独立成绩或延迟保持证据，不判学习失败。10-13三个会计名额先做A11首次提取应用，金融A13-01—03顺延10-14，随后会计逐组顺延一天至10-28；税法日期保持，09/08已同步，01-25目标保留。借款按用户要求以教学日10-12为锚，10-13 D1首次提取/应用、10-15 D3、10-19 D7，后续10-26 D14及11-11 D30；不另加10-14整轮、不预记通过，首次应用与延迟保持分开。

E-005/E-044/E-057和负债税基表达分支10-13 D1、10-15 D3、10-19 D7、10-26 D14、11-11 D30。已测10-11块和E-023/E-055/E-056仍10-14 D3/10-18 D7/10-25 D14/11-10 D30；10-09已测块及E-053仍10-16 D7/10-23 D14/11-08 D30。10-05其余正确分支原10-19 D14/11-04 D30；10-06块10-13 D7及未抽债务保留，不将抽测扩大为全章通过。T02-02全书后标记没有执行；93未使用，不提交/同步/推送。

'''
ledger = once(ledger, '## 无法解释清楚的问题', h12 + '## 无法解释清楚的问题')
qpat = r'(?m)^\| Q-001 \|[^\n]+$'
m = re.search(qpat, ledger)
assert m
cells = m.group().split('|')
cells[-2] = ' 10-12资产账面80/税基110/可抵扣30及税款7.5、负债未来减24/税6首次正确；负债基数/类型漏写扣0.5，同日补0及可抵扣24正确，次日只复该表达分支；资产原10-19 D14/11-04 D30保留。未关闭，递延所得税分录未教。 '
ledger = ledger[:m.start()] + '|'.join(cells) + ledger[m.end():]
docs['90-学习错误与问题台账.md'] = ledger

console = docs['00-NOESIS控制台.md']
new_console = '''## 最近进度｜2026-10-12（复习完成，会计教学归档，税法进行中）

- [x] 四组提取预测/首次32→32、32→32、40→37、40→40；各实际范围及第9税种提示项撤出评分见90的H12
- [x] E-023单位、E-055细名、E-056报告核查D1及E-053分类D3实际抽测正确；其他原复习日期按具体分支保留
- [x] D7/旧错四项本人同日修复；原37/40不改。E-005/E-044再现、E-057新增，负债税基表达漏项补齐，10-13 D1
- [x] 用户仅今天合并会计：A11-01—03完整教学已完成并归档，skill未改
- [ ] 会计新补内容独立题及出口已展示未答，按用户意愿留后续提取；10-13先占三个会计名额作首次应用，A13-01—03移10-14，后续会计顺延至10-28，税法日期保留
- [ ] 本轮税法T02-05—06合并完整教学及题组，提交后评分；尚无新课分、真题、可靠计时或新增M3
- [ ] 会计按用户要求教学后D1/3/7为10-13/15/19；D1首次提取兼首次应用，后续保持分列，旧分支另按90，不提前记通过

## 先前完成｜2026-10-11（新课、独立应用与退出测验）'''
console = once(console, '## 最近完成｜2026-10-11（新课、独立应用与退出测验）', new_console)
docs['00-NOESIS控制台.md'] = console

memory = docs['92-CG-CPA长期记忆.md']
memory = re.sub(r'(?m)^last-completed: .*', 'last-completed: 2026-10-12四组提取32/32、32/32、37/40、40/40；四项同日修复；A11-01—03教学完成、独立题及出口留后；税法进行中，无真题/可靠计时/M3', memory, count=1)
memory = re.sub(r'(?m)^next-session: .*', 'next-session: 本轮T02-05—06合并教学与应用；10-13会计三个名额先A11-01—03首次提取/应用及旧错D1，A13-01—03移10-14；其余会计顺延一天，税法日期保留', memory, count=1)
row = '| 10-12 | 到期提取、旧错修复、会计合并教学 | —（未可靠计时） | 四组32/32、32/32、37/40、40/40；四项本人同日修复 | A11-01—03教学已完成，独立题/出口留后；税法进行中；仅今日合并，不改skill；无真题/M3 |\n'
m = re.search(r'(?m)^\| 10-11 \|[^\n]+\n', memory)
assert m
memory = memory[:m.end()] + row + memory[m.end():]
for ident, (review, _) in reviews.items():
    pat = rf'(?m)^\| {ident} \|[^\n]+$'
    m = re.search(pat, memory)
    if m:
        c = m.group().split('|')
        c[-2] = ' ' + review + ' '
        memory = memory[:m.start()] + '|'.join(c) + memory[m.end():]
m = re.search(r'(?m)^\| E-056 \|[^\n]+\n', memory)
assert m
memory = memory[:m.end()] + '| E-057 | 存货灾害批准处理 | 灾害净损失进营业外支出，批准时结清待处理 | 10-13 D1；本人同日修复，原题4分保留3/4 |\n' + memory[m.end():]
checkpoint = '''## 当前检查点：下一次学习

10-12四组提取首次32/32、32/32、37/40、40/40，均有独立前置预测；第三组偏差+7.5pp，其余0。四项同日修复，首次分不改；E-005/E-044再现、E-057新增，负债税基表达漏项只复该分支。实际题目、撤出提示项及精确证据见90的H12，不扩大为全章、真题或M3。

1. 本轮先T02-05—06一次交付完整教学及合并题组，收到实际答案再评分。A11-01—03按用户要求记今日教学完成，七道合稿题及会计出口没有提交答案；新补细项为已教学待独立应用，既有9月已过基础保留。
2. 仅今天合并会计和税法的交付；不改skill，不永久改变每编号一轮偏好。10-13三个会计名额先A11-01—03首次闭卷提取与应用；原A13-01—03移10-14，后续会计逐组顺延至10-28。A11-04/A29-01/A13-04→10-15、A13-05→10-16，税法日期保留。09/08/00/90已同步，01-25目标保留。
3. A11按用户指定教学日锚：10-13 D1首次提取/应用、10-15 D3、10-19 D7、10-26 D14、11-11 D30；不另加10-14整轮，首次提取不冒称已有独立应用后的保持。未答不是学习失败，不编造新课分、出口、计时或M3。
4. E-005/E-044/E-057及负债基数表达分支10-13 D1/10-15 D3/10-19 D7/10-26 D14/11-11 D30。10-11块及E-023/E-055/E-056下一10-14 D3/10-18 D7；10-09已测块/E-053下一10-16 D7；原10-05 D14和10-06 D7及未抽分支保留，以H12和90为准。
5. T02-02全书后回看标记未执行，普通间隔复习不替代该专项。首周教材术语、分类及登记特殊口径教师核源10-14保留；周检查只核实际完成，移期项不得提前通过。93未使用；无可靠计时/新M3，不提交/同步/推送。

'''
memory = re.sub(r'## 当前检查点：下一次学习\n.*?(?=## 每次会话结束时)', lambda _: checkpoint, memory, count=1, flags=re.S)
docs['92-CG-CPA长期记忆.md'] = memory

rules = docs['91-公式与精确规则表.md']
new_rules = '''### 2026-10-12｜借款费用新补规则（教学完成，待首次应用）

- 专门借款定义须关联合格资产；本金及用款购买材料不属于借款费用。折价增加实际利息，溢价抵减；一般借款资本化率按本期实际利息/借款本金时间加权均值，资产超专门借款部分逐笔增量加权；须受实际利息上限约束。[借款费用准则2/6—8条](https://kjs.mof.gov.cn/zt/kjzzss/kuaijizhunzeshishi/200806/t20080618_46231.htm)。本期金额例71.75为教师示范，不是首次成绩。
- 开始的资产支出含现金、转移非现金、承担带息债务；普通无息赊购未付款不构成该口径。独立可用部分分别停止，必须联合使用的等整体可用；不待决算、盈利或还款。[准则5/12—14条](https://kjs.mof.gov.cn/zt/kjzzss/kuaijizhunzeshishi/200806/t20080618_46231.htm)。
- 专门借款辅助费用在合格资产达到目标状态之前资本化、之后费用化；一般借款辅助费用发生时费用化。实际利息=期初净账面价值×实际利率，折溢价摊销为实际与票面利息差额。[准则7/10条](https://kjs.mof.gov.cn/zt/kjzzss/kuaijizhunzeshishi/200806/t20080618_46231.htm)。外币汇差仅讲组成，完整折算A11-04改10-15；2026临时基线待2027复核。

'''
rules = once(rules, '### 后续版本线索与本次评分口径', new_rules + '### 后续版本线索与本次评分口径')
docs['91-公式与精确规则表.md'] = rules

expected = sum((old_codes[f'10-{day:02d}'] for day in range(13, 28)), [])
actual = []
for day in range(14, 29):
    actual.extend(old_codes[f'10-{day-1:02d}'])
assert actual == expected
for n in names:
    assert (root/n).read_bytes() == raw[n], 'Concurrent change: ' + n
for n, s in docs.items():
    ending = '\r\n' if b'\r\n' in raw[n] else '\n'
    payload = s.replace('\n', ending).encode('utf-8')
    if raw[n].startswith(b'\xef\xbb\xbf'):
        payload = b'\xef\xbb\xbf' + payload
    (root/n).write_bytes(payload)
print('Updated 6 project documents; skill and question registry unchanged. Accounting instruction recorded; independent applications remain pending.')
