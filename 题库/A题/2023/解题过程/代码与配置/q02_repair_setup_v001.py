"""File-only setup: preserve accepted inputs and bind new offline repair round."""
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]; W=ROOT/'工作记录'; H=Path(__file__).parent
s=(H/'q02_search_common_v001.py').read_text(encoding='utf-8').replace('Q02-搜索-v001','Q02-修复-v001')
s=s.replace("'scope':'each process", "'round':'new user-authorized 3600sec repair; old round ledger untouched','scope':'each process")
(H/'q02_repair_common_v001.py').write_text(s,encoding='utf-8')
s=(H/'q02_search_engine_v002.py').read_text(encoding='utf-8').replace('import q02_search_common_v001 as io','import q02_repair_common_v001 as io')
s=s.replace(' for ti in range(len(times)):\n  with np.load', ' for ti in range(len(times)):\n  budget.guard(12)\n  with np.load')
s=s.replace(" for k in ['sums','counts','unknown_weights']:arrays[k]", " budget.guard(15)\n for k in ['sums','counts','unknown_weights']:arrays[k]")
(H/'q02_repair_engine_v001.py').write_text(s,encoding='utf-8')
stage=W/'阶段记录/Q02-可行性修复与独立确认-v001.md'
stage.write_text('''# 第2问可行性修复与独立确认 v001

状态：进行中。用户已验收前轮受控搜索的过程记录，第2问仍未完成；管理员归档未确认。

## 本轮授权与历史接续

2026-09-05：沿用 C21—C24。旧候选 C22 是候选编号，不是批准条款 C22。新候选从 R023 连续编号。前轮 C22 功率 59721.991034192215 kW，工作指标 6.012495858928212 kW，额定余量 −284.02146166671446 kW；旧确认已作为本轮搜索依据，不再是新设计的独立确认。

本轮新累计计算上限3600秒，搜索和前置最多2400秒，至少保留1200秒独立确认及重建。旧预算账本与代码、失败确认、论文v001均保留。新输出目录为[Q02-修复-v001](../诊断结果/Q02-修复-v001/)。

## 实施边界

先修复可行性，再在保留候选的条件下比较单位面积功率。新候选全部镜子及60时点评分，完整障碍集合；不以部分镜场外推。原几何、物理、N04、统计核不改，新engine仅改输出绑定并补充收尾预算门禁。正式确认前冻结实际导出精度设计与未使用的随机命名空间。

## 当前进度

历史回读已完成：AGENTS、任务状态、记录索引、前轮阶段、决策D030、更新U036、fast/hex/search engine/runner/summary相关接口及C22确认结果。旧几何与物理验证仍有效，不重做Q1全年计算。新搜索、确认、清单重建和论文v002尚未执行；将在有意义进展后追加证据。
''',encoding='utf-8')
for filename,text in {
'决策记录.md':'''\n## D031 — 2026-09-05 — 接受旧搜索记录并启动可行性修复\n\n用户接受Q02受控搜索v001作为过程交付，不认定Q2完成。新增独立3600秒计算预算，搜索最多2400秒、确认与重建至少1200秒；旧轮账本不变。明确允许从未达标候选启动局部改进，功率缺口用于寻找可行解，不改可行域内最大化单位面积功率的目标。新候选R023起，与批准条款C21—C24区分。通过完整评价、独立确认、清单重建后直接写论文v002；当前未有新的成功结论。见[新阶段](阶段记录/Q02-可行性修复与独立确认-v001.md)。\n''',
'06-更新记录.md':'''\n## U037 — 2026-09-05 — 接续验收与新预算登记\n\n原D030/旧阶段为额定FAIL且待阶段验收；本次用户接受其记录但要求继续修复。原数值结论不变。新阶段v001进行中，修复输出另目录、engine另版本。旧代码/数据/未完成论文不覆盖。修改范围仅本轮搜索策略与预算；物理、目标和工作阈值不改，管理员归档未确认。\n''',
'记录索引.md':'''\n## 第2问可行性修复：当前进行中\n\n- [Q02-可行性修复与独立确认-v001](阶段记录/Q02-可行性修复与独立确认-v001.md)：本轮有效阶段，进行中。\n- 前轮受控搜索v001已获过程验收，额定FAIL历史保留，不被本阶段开始而替代成成功。\n''',
'归档清单.md':'''\n## 2026-09-05 可行性修复开工\n\n新阶段及repair系列代码写入本工作区；旧阶段过程已验收，管理员归档未确认。新增计算与论文尚未完成，不预先登记验收。\n''',
'方法库查阅记录.md':'''\n## 2026-09-05 第2问可行性修复回读\n\n实际回读本题已有搜索/确认记录、hex层带表示、参数化光学与汇总代码相应接口；本次没有重新完整阅读Datawhale或参考论文，没有新增工程参数。局部邻域及不确定性排序依照已授权一般数学知识和本题实测证据，来源为独立推导/计算经验，不冒称来自未读教程。\n'''
}.items():
 with (W/filename).open('a',encoding='utf-8')as f:f.write(text)
(W/'00-任务状态.md').write_text('''# 当前任务状态

2026-09-05：第1问论文与收尾已验收；第2问原型与前轮受控搜索过程已验收，但额定条件未通过。

当前阶段：[Q02-可行性修复与独立确认-v001](阶段记录/Q02-可行性修复与独立确认-v001.md)，进行中。

新计算预算3600秒，至少1200秒留给独立确认及重建；先修复可行性，再比较单位面积目标。C22旧确认功率约59.722 MW，不能称第2问完成。旧版本与失败证据保留。

当前待执行：冻结新规则、局部全60时点评分、较精比较、满足入场条件后的独立确认；通过后直接完整结果与论文v002。无联网/GitHub/Q3授权。管理员归档仍未确认。
''',encoding='utf-8')
print('Setup files saved; no numerical evaluation performed.')
