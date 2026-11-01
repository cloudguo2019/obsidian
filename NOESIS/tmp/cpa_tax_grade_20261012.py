from pathlib import Path
import re

root = Path(r'C:\Users\cg\Desktop\Nietzsche\obsidian\NOESIS')
names = ['00-NOESIS控制台.md', '90-学习错误与问题台账.md', '92-CG-CPA长期记忆.md', '91-公式与精确规则表.md']
original = {n: (root/n).read_bytes() for n in names}
docs = {n: b.decode('utf-8-sig').replace('\r\n', '\n') for n, b in original.items()}

def once(s, old, new):
    assert s.count(old) == 1, (old[:65], s.count(old))
    return s.replace(old, new, 1)

for n in names:
    docs[n] = docs[n].replace('39.5/40', '40/40').replace('27.5/28', '28/28')
    docs[n] = docs[n].replace('税法已评分，仅一项订正待答', '税法教学与首次应用完成')

c = docs[names[0]]
c = once(c, '- [ ] 唯一新错E-058：卫星电视信号落地转接应为增值电信6%；一句同日订正待答，10-13 D1/10-15 D3/10-19 D7；无真题、可靠计时或新增M3', '- [x] 税法五组均正确，无需订正；第⑩组有效答案“都是6%”，撤销误判；已应用块M2，无真题、可靠计时或新增M3')
c = once(c, '当前仅E-058一句定向订正；10-13先A11-01—03教学后D1首次提取与应用、T02-05—06 D1/E-058及E-005/E-044/E-057/负债税基表达', '10-13先A11-01—03教学后D1首次提取与应用、T02-05—06 D1及E-005/E-044/E-057/负债税基表达')
docs[names[0]] = c

l = docs[names[1]]
l = re.sub(r'(?m)^\| E-058 \|[^\n]+\n', '', l)
l = once(l, '已应用正确分支M2；A11新补仅教学完成；E-058待订正', '税法已应用块M2；A11新补仅教学完成')
l = once(l, '仅卫星电视信号落地转接误答9%，新增E-058，一句定向订正待答，不追加新课；无新M3。', '五组全部正确，第⑩组“都是6%”有效；撤销误判和订正要求，不追加新课，无新M3。')
l = once(l, '完整税率矩阵、符合条件跨境及境内使用边界、零税率与免税进项；E-058增值电信一分支误答，待一句订正，不撤销其余正确证据', '完整税率矩阵、符合条件跨境及境内使用边界、零税率与免税进项，首次全部正确；第⑩组增值电信6%正确')
l = once(l, '首次23.5/24+4/4+4/4+4/4+4/4=40/40（98.75%）', '首次24/24+4/4+4/4+4/4+4/4=40/40（100%）')
l = once(l, '第1题除⑩卫星电视信号落地转接误答9%（应为增值电信6%）之外全部正确；同组贷款/咨询/独立软件开发6%、基础电信9%、跨境0/0/0/6正确。', '第1题12组全部正确；第⑩组有效原答为“都是6%”，对应卫星电视信号落地转接、贷款、咨询、独立软件开发；第⑧组基础电信9%、第⑫组跨境0/0/0/6正确。')
old = '唯一新错E-058（B）：基础与增值电信边界。法源按91已核2026年第9号范围附件及增值税法10条；2026临时基线待2027复核。反馈给出准确分类与6%，仅要求本人填一句定向订正，不追加教学编号或题组；当前尚未收到该订正，不预记同日修复。税法两模块已教并完成首次题组提交，正确分支M2，错误分支待修复及10-13 D1；不是全章掌握或新增M3。后续D3/7/14/30为10-15/19/26、11-11；既有复习、会计延后提取与T02-02全书后标记保留。'
new = '评分记录校正：本次有效原答第⑩组是“都是6%”，此前记录将其误记成9%，半分扣除及相应错误条目、订正要求全部撤销。正确首次成绩40/40，不把误判当作学习者错误或同日修复。两税法模块教学、首次独立应用及第5组综合出口已完成，已应用块M2，无需订正，不新增M3或全章掌握结论。10-13 D1、10-15 D3、10-19 D7、10-26 D14、11-11 D30；既有复习、会计延后提取与T02-02全书后标记保留。法源仍依91已核2026规则，待2027大纲复核。'
l = once(l, old, new)
docs[names[1]] = l

m = docs[names[2]]
m = once(m, '；E-058一句订正待答，无真题/可靠计时/M3', '；无新税法错误或订正，无真题/可靠计时/M3')
m = once(m, '当前仅E-058卫星电视信号落地转接分类/税率一句订正；', '')
m = once(m, '税法仅E-058一句订正待答', '税法五组全对，无需订正')
m = re.sub(r'(?m)^\| E-058 \|[^\n]+\n', '', m)
m = once(m, '税率矩阵23.5/24', '税率矩阵24/24')
m = once(m, '只错卫星电视信号落地转接9%应为增值电信6%，E-058一句订正待答，不再追加新课', '第⑩组有效原答“都是6%”正确，撤销台账误判和订正指令，无新税法错误，不再追加新课')
m = once(m, 'T02-05—06及E-058、E-005', 'T02-05—06及E-005')
m = once(m, '；E-058尚未收到本人修复。', '。')
docs[names[2]] = m

r = docs[names[3]]
r = once(r, '；卫星电视信号落地转接误答9%，E-058一句本人订正待答。其余所测正确，原首次分保留，不新增M3。', '；第⑩组有效答案“都是6%”，全部所测正确，撤销此前误判及订正要求，不新增M3。')
docs[names[3]] = r

assert 100 * .13 + 30 * .06 == 14.8
assert abs(130 * .13 - 16.9) < 1e-9
assert abs(160 * .13 + 20 * .09 - 22.6) < 1e-9
assert abs(22.6 - 4.6 - 18) < 1e-9
for n, s in docs.items():
    assert 'E-058' not in s
    assert '39.5/40' not in s and '27.5/28' not in s
    assert (root/n).read_bytes() == original[n], 'Concurrent edit: ' + n
for n, s in docs.items():
    ending = '\r\n' if b'\r\n' in original[n] else '\n'
    data = s.replace('\n', ending).encode('utf-8')
    if original[n].startswith(b'\xef\xbb\xbf'):
        data = b'\xef\xbb\xbf' + data
    (root/n).write_bytes(data)
print('Four records reconciled to the current valid answer: tax 40/40, no new error or repair; prior accounting evidence and review dates preserved.')
