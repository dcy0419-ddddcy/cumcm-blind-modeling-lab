from pathlib import Path
import json
R=Path(__file__).resolve().parents[2];W=R/'工作记录';P=W/'论文';O=W/'诊断结果/Q02-搜索-v001';changes=[]
f=W/'阶段记录/Q02-受控搜索与独立确认-v001.md';s=f.read_text(encoding='utf-8')
for old,new in [('4对象全部保留正分母','涉及3面镜的4个对象—时点组合全部保留正分母'),('每个低存活对象保持0≤f2≤f1≤1的联合可行关系',r'每个低存活对象—时点组合保持 \(0\le f_2\le f_1\le1\) 的联合可行关系'),('低存活对象的全范围变化','低存活对象—时点组合的全范围变化'),('尺寸/相位/塔位/密度耦合','尺寸/相位/塔位/密度耦合')]:
 s=s.replace(old,new)
s=s.replace('全对中心距≥w+5',r'全对中心距 \(\ge w+5\)').replace('严格z>h/2',r'严格 \(z>h/2\)').replace('；w≥h是批准搜索限制',r'；\(w\ge h\) 是批准搜索限制').replace('平方距离为d²(a²+ab+b²)≥d²',r'平方距离为 \(d^2(a^2+ab+b^2)\ge d^2\)')
s=s.replace('C22塔位(0,0)m，统一w=h=6.5 m','C22塔位(0,0)m，统一宽高均为6.5 m')
s += '\n\n### 诊断布局图（非正式设计）\n\n下图由实际冻结清单绘制，仅画镜中心和固定场界/禁区，不表示完整镜面投影。C22额定工作判据未通过。\n\n![图D1 C22未达标诊断布局](C:/Users/admin/OneDrive/Desktop/26国赛-单题盲解区/A-P8C3/工作记录/论文/图表/第2问-C22-未达标诊断布局-v001.png)\n\n图D1　C22冻结诊断布局；坐标单位m，3054个镜中心，场界350 m、禁区100 m。来源为实际CSV，脚本与SHA见正文证据映射。\n'
f.write_text(s,encoding='utf-8')
f=P/'第2问-模型建立与求解-v001.md';s=f.read_text(encoding='utf-8')
for old,new,loc in [('低存活项 \\(U_{Q,\\rm low}\\) 对确认池化后未加权联合存活数小于100的对象计算。','低存活项 \\(U_{Q,\\rm low}\\) 对确认池化后未加权联合存活数小于100的对象—时点组合计算。','第6.4节，式(28)后'),('对这些对象，阴影遮挡和截断分量','对这些对象—时点组合，阴影遮挡和截断分量','第6.4节，式(28)后'),('将各对象的范围直径按式（3）、（15）','将各对象—时点组合的范围直径按式（3）、（15）','第6.4节，式(28)后'),('**最终设计的确认结论待完成。** 当前冻结候选已完成独立确认和落盘重建，','**正式达标设计及其确认结论待完成。** 当前C22的诊断性独立确认和落盘重建已经完成，','第7.2节')]:
 assert old in s,old
 s=s.replace(old,new,1);changes.append({'location':loc,'before':old,'after':new,'reason':'区分对象—时点组合与不同镜面；区分已完成失败确认与尚未取得的正式达标设计。','evidence':'低存活cases包含导出78号两次、83和145；独立确认结论FAIL，重建通过。'})
f.write_text(s,encoding='utf-8')
(O/'正文措辞核查修订-v002.json').write_text(json.dumps(changes,ensure_ascii=False,indent=2),encoding='utf-8')
md=['# 第2问草稿修订与排版记录 v001','\n2026-09-05；本次只修改尚未交付草稿的统计对象和状态说明，不改模型、源数据、数值结果或已验收文档。','\n首次状态更新的前后文见诊断结果/Q02-搜索-v001/正文草稿状态修订-v001.json。']
for i,c in enumerate(changes,1):
 md += [f'\n## 修订{i}', '\n修改原因：'+c['reason'],'\n位置及改动：第2问-模型建立与求解-v001.md，'+c['location']+'，以对应组合/正式达标设计取代易混淆称呼。','\n修改前：\n\n'+c['before'],'\n修改后：\n\n'+c['after'],'\n验证依据：'+c['evidence']]
md += ['\n初次编译12页后全部视觉检查通过；本次措辞修订后重新编译，当前有效渲染为第2问-未完成草稿页面-v002。旧v001渲染及SHA作为修改前页面快照保留，不对应最终PDF。数学29式、3辅助表的结构不变。']
(P/'第2问-修订与排版记录-v001.md').write_text('\n'.join(md)+'\n',encoding='utf-8')
f=W/'诊断代码/q02_paper_render_v001.py';s=f.read_text(encoding='utf-8').replace('第2问-未完成草稿页面-v001','第2问-未完成草稿页面-v002').replace('Q02-PDF自动核验-v001.json','Q02-PDF自动核验-v002.json');(W/'诊断代码/q02_paper_render_v002.py').write_text(s,encoding='utf-8')
