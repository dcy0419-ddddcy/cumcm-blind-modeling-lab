"""Pre-delivery documentation contract correction; no physical/numerical mutation."""
from pathlib import Path
import json
W=Path(__file__).resolve().parents[1];O=W/'诊断结果/Q02-原型-v001'
changes=[]
def revise(p,old,new,basis):
 q=W/p;text=q.read_text(encoding='utf-8')
 if old not in text:raise RuntimeError('Old text not found '+p)
 q.write_text(text.replace(old,new),encoding='utf-8')
 changes.append({'path':p,'before':old,'after':new,'basis':basis,'scope':'documentation only; no code/config/optical result changed'})
revise('诊断代码/Q02-设计与评价接口-v001.md','设计名/版本；参与场景身份和子流','设计名与版本参与场景身份；本轮子流用设计名/稳定键，版本不单独入种子','eval-v003 prepare tag与runner-v003 seed_words实际调用')
revise('诊断代码/Q02-设计与评价接口-v001.md','combine只合并同Scene/对象的最终批次，不重计前缀，不把单批比值平均当池化。','combine核验同Scene及对象后累加传入统计，并不识别重复批次或层级；本轮runner分别池化64和256层，最终只取256层，未再纳入相关前缀。调用者不得传入重叠统计；单批比值平均也不能冒充池化。','eval-v003 combine只检查绑定；runner-v003按层级组织；落盘1707项审核核对216独立批次')
revise('阶段记录/Q02-参数化与几何原型验证-v001.md','组合成本约0.150—0.245秒。','按三个布局分别计算的每组合平均成本约0.150—0.245秒，并非全部逐组合耗时的最小值与最大值。','落盘核验每布局18个组合内部耗时之和除18')
# Existing delivery file checks are retained as pre-correction snapshots.
for p in ['阶段记录/Q02-参数化与几何原型验证-v001.md','00-任务状态.md','记录索引.md']:
 q=W/p;txt=q.read_text(encoding='utf-8')
 for stem in ['交付文件核验','归档哈希清单']:
  txt=txt.replace('Q02-原型-v001/'+stem+'-v001.json','Q02-原型-v001/'+stem+'-v002.json')
 txt=txt.replace('D024/U028','D024/U029')
 q.write_text(txt,encoding='utf-8')
with (O/'交付前文档合同修订-v001.json').open('x',encoding='utf-8') as f:
 json.dump({'date':'2026-09-05','changes':changes,'old_basis':'本轮接口/成本草稿依据实际代码，原措辞把运行器责任写成函数保证，或省略了子流/平均限定','revalidation':'source read-only review plus all-54 saved-statistics checks; no optical rerun'},f,ensure_ascii=False,indent=2)
p=O/'修订与失败记录-v001.md'
with p.open('a',encoding='utf-8') as f:
 f.write('\n\n## RV07 — 交付前接口合同与成本口径校正\n\n本轮v001仍为未交付草稿。逐项修改前原文、修改后原文、位置与依据见[精确修订记录](交付前文档合同修订-v001.json)。设计版本仅绑定Scene，不单独入种子；combine不自动去重，当前runner按层级选择最终批次保证不重计；0.150—0.245秒是按布局的组合平均。原依据为实际接口，但文字把调用者责任写为函数保障。只改文档，不改任何计算；54份统计审核仍有效，不重跑光学。文件核验/哈希v001保留为修订前快照，v002为当前，不能用旧快照的文档哈希检验新文字。\n')
p=W/'06-更新记录.md'
with p.open('a',encoding='utf-8') as f:
 f.write('\n\n## U029 — 2026-09-05 — 原型交付前文档合同和封存接续\n\n- 原位置/原文/新文及依据见[精确修订](诊断结果/Q02-原型-v001/交付前文档合同修订-v001.json)。接口v001第1/3节误将版本写入随机流、把runner的分层责任写成combine自动去重；阶段第9节未明说每布局平均计时。原依据记录为实际代码，表述过宽。\n- 修改后：Scene包含设计版本，当前子流不包含版本；combine仅检查绑定，runner按层级组织/最终只取256；成本是各布局18组合平均。影响未来调用接口和性能理解，不改变本题数值、物理、代码、配置和已验收Q1。\n- 重验：只读代码核对及原1707项全覆盖统计核验仍有效，无光学重跑。文档v001尚未交付，可修草稿，精确前后文保留；文件核验/哈希v001作为修订前快照保留，当前新建v002。\n- 仍待用户验收原型；完整搜索未开始。当前末编号D024/U029，管理员归档未确认。\n')
p=W/'记录索引.md'
with p.open('a',encoding='utf-8') as f:
 f.write('\n\n### Q02原型交付前文字与文件核验接续（U029）\n\n[精确修订记录](诊断结果/Q02-原型-v001/交付前文档合同修订-v001.json)、[修订入口](诊断代码/q02_prototype_docfix_v001.py)保留接口合同/平均成本前后文。当前[文件核验v002](诊断结果/Q02-原型-v001/交付文件核验-v002.json)与[哈希v002](诊断结果/Q02-原型-v001/归档哈希清单-v002.json)接续修订前v001快照；[核验入口v002](诊断代码/verify_q02_prototype_delivery_v002.py)只核文档/保存证据，无新增光学。D024的有限通过范围不变。\n')
p=W/'归档清单.md'
with p.open('a',encoding='utf-8') as f:
 f.write('\n\n### U029文件封存补充\n\n另保存诊断代码/q02_prototype_docfix_v001.py、verify_q02_prototype_delivery_v002.py，诊断结果/Q02-原型-v001/交付前文档合同修订-v001.json、交付文件核验-v002.json及归档哈希清单-v002.json。v001核验/哈希为修订前快照，不作为当前文档字节绑定；v002当前。原型仍待验收、管理员归档未确认，未重跑光学。\n')
# Current file verification revision, preserving executed v001.
p=W/'诊断代码/verify_q02_prototype_delivery_v001.py'
txt=p.read_text(encoding='utf-8').replace("O/'交付文件核验-v001.json'","O/'交付文件核验-v002.json'").replace("O/'归档哈希清单-v001.json'","O/'归档哈希清单-v002.json'").replace("'generated_from':'verify_q02_prototype_delivery_v001.py'","'generated_from':'verify_q02_prototype_delivery_v002.py'")
(W/'诊断代码/verify_q02_prototype_delivery_v002.py').write_text(txt,encoding='utf-8')
print('Three documentation corrections preserved; current file checks v002 pending.')