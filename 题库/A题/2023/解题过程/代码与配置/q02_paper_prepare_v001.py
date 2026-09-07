"""Prepare an explicitly unfinished Q2 manuscript from verified records; no numerical evaluation."""
from pathlib import Path
import re,json,hashlib
R=Path(__file__).resolve().parents[2];W=R/'工作记录';P=W/'论文';O=W/'诊断结果/Q02-搜索-v001'
f=P/'第2问-模型建立与求解-v001.md';s=f.read_text(encoding='utf-8-sig')
old=s
revisions=[]
def change(a,b,reason):
 global s
 assert a in s,a[:80]
 s=s.replace(a,b,1);revisions.append({'reason':reason,'before':a,'after':b})
change('> **未完成草稿 v001。** 本稿已整理模型和求解方法；搜索结果、最终设计、独立确认结论及本问小结尚待完成。写作时独立确认正在进行，文中给出的冻结设置不表示确认已完成或设计已达标。本稿不构成第2问正式结果交付。', '> **未完成草稿 v001。** 模型与求解方法已整理。限定搜索和独立确认已经结束，当前冻结候选未通过额定功率工作判据；第2问的最终设计、题表1—3及本问结果结论仍待完成。本稿不构成第2问正式结果交付。', '独立确认已结束且额定失败；更新草稿状态，不能保留“正在进行”或生成达标结论。')
change('**待完成。** 须在独立确认结束并从保存统计重建后，填入确认点估计、工作指标、功率工作下限、精度达成情况及未决状态。当前不作达到额定功率、满足全部精度目标或搜索完成的结论。', '**最终设计的确认结论待完成。** 当前冻结候选已完成独立确认和落盘重建，汇总数值工作目标通过，额定功率工作判据未通过。其诊断统计保存在证据记录中，不据此填入正式达标设计的结果表，也不由有限搜索失败推断题目无可行解。', '区分已完成的失败候选确认与尚未取得的最终设计确认。')
change('**待完成。** 在搜索范围、独立确认和交付清单核验结束后，根据实际证据填写本问结论；若未达到额定条件或规定精度，应保留未完成或未确认状态，不形成可行性或全局最优性结论。', '**待完成。** 当前计算尚未取得满足额定功率工作判据的设计，本问结果与最终结论不予定稿。已确定的参数化、几何检查和独立评价接口可用于后续获准的搜索；现有失败诊断不构成原问题不可行性证明。', '收尾核验结束仍未达60 MW，保持本问未完成。')
marker='\n---\n\n## 写作依据与待补证据（内部衔接，不进入正式正文）'
assert marker in s
body,internal=s.split(marker,1);s=body.rstrip()+'\n'
f.write_text(s,encoding='utf-8')
(O/'正文草稿状态修订-v001.json').write_text(json.dumps({'file':str(f.relative_to(R)),'before_sha256':hashlib.sha256(old.encode()).hexdigest(),'after_sha256':hashlib.sha256(s.encode()).hexdigest(),'revisions':revisions,'removed_internal_notes':internal,'scope':'unsubmitted draft status and removal of internal mapping from main body; no scientific model or numerical change'},ensure_ascii=False,indent=2),encoding='utf-8')
# Adapt the known local converter into a new Q2-only file; never import its Q1 side effects.
src=(W/'诊断代码/q01_paper_tex_v006.py').read_text(encoding='utf-8-sig')
src=src.replace('第1问','第2问').replace('Q01-论文收尾-v001','Q02-搜索-v001').replace('Markdown与TeX对应-v001.json','Q02-Markdown与TeX对应-v001.json').replace('assert blocks==20 and tables==6','assert blocks==29 and tables==3')
src=src.replace("if s.startswith('# '):", "if s.startswith('> '):s=s[2:]\n    if s.startswith('# '):")
src=src.replace("inline(pending_caption)","inline(pending_caption or '表：待补表题')")
(W/'诊断代码/q02_paper_tex_v001.py').write_text(src,encoding='utf-8')
src=(W/'诊断代码/q01_paper_render_v002.py').read_text(encoding='utf-8-sig')
src=src.replace('第1问','第2问').replace('Q01-论文收尾-v001','Q02-搜索-v001').replace('页面核验-最终','第2问-未完成草稿页面-v001').replace('PDF自动核验-v002.json','Q02-PDF自动核验-v001.json')
(W/'诊断代码/q02_paper_render_v001.py').write_text(src,encoding='utf-8')
print(json.dumps({'body_written':str(f),'math_blocks':s.count('\\['),'table_blocks':3,'status':'UNFINISHED_DRAFT; rating_failed'},ensure_ascii=False))
