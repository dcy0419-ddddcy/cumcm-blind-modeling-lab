"""Preserve first delivery audit and bind final controls to output-aware v002."""
from pathlib import Path
import json
H=Path(__file__).resolve().parent;W=H.parent;O=W/'诊断结果/Q02-修复-v001'
first=json.loads((O/'交付文件核验-v001.json').read_text(encoding='utf-8'))
fails=[x for x in first['checks']if not x['pass']]
if len(fails)!=4 or not all('交付文件核验-v001.json'in x['name']or'交付哈希清单-v001.json'in x['name']for x in fails):raise RuntimeError('Unexpected first-audit failure')
changes=[]
for n in ['00-任务状态.md','记录索引.md','归档清单.md']:
 p=W/n;old=p.read_text(encoding='utf-8');new=old.replace('诊断结果/Q02-修复-v001/交付文件核验-v001.json','诊断结果/Q02-修复-v001/交付文件核验-v002.json').replace('诊断结果/Q02-修复-v001/交付哈希清单-v001.json','诊断结果/Q02-修复-v001/交付哈希清单-v002.json')
 changes.append({'file':n,'before':old,'after':new});p.write_text(new,encoding='utf-8')
log='''

## U047 — 2026-09-05 — 最终交付自引用核验顺序修订

原文件q02_repair_delivery_v001在输出核验报告/哈希清单之前检查控制文件链接，其中4条链接指向该脚本自己尚未生成的两个输出，故476项检查中4项失败。其余数值、源绑定、PDF/实际页面及普通链接检查通过；失败报告和v001哈希清单保留。

新建delivery-v002，只将两个明确的本次输出链接推迟到输出文件实际写入后核对。最终报告先保存为进行中草稿，再补充真实存在性结果；不预先把缺文件判为成功。当前控制记录链接指向v002；原版本、差异和依据见[终检修订证据](诊断结果/Q02-修复-v001/文件终检修订-v001.json)。光学结果、公式、点估计、U、工作判定和PDF未修改，无新增射线。v002是本轮最终文件核验入口，不能用其代替独立数值验证。
'''
with (W/'06-更新记录.md').open('a',encoding='utf-8')as f:f.write(log)
with (W/'记录索引.md').open('a',encoding='utf-8')as f:f.write('\n\nU047接续：当前末编号D041/U047；v001文件核验仅因4条尚未生成的自引用链接失败并保留，当前采用v002。数值/PDF结论不变。\n')
with (W/'归档清单.md').open('a',encoding='utf-8')as f:f.write('\n\nU047：另存delivery-v002、delivery-docfix-v001、文件终检修订-v001及交付文件核验/哈希清单-v002；保留失败v001完整证据。文件保存与数值验证分别报告，用户验收/管理员归档状态不变。\n')
(O/'文件终检修订-v001.json').write_text(json.dumps({'failure':fails,'change':'Defer only exact self-output links until written; all other checks unchanged.','changes':changes,'numerical_or_physical_change':False},ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
print('U047_SELF_OUTPUT_ORDER_FIXED_WITH_HISTORY_RETAINED')
