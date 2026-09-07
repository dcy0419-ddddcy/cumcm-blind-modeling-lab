"""Record actual page inspections and final source binding; no optical computation."""
from pathlib import Path
import json,hashlib
H=Path(__file__).resolve().parent;W=H.parent;R=W.parent;O=W/'诊断结果/Q02-修复-v001'
qa=json.loads((O/'Q02-修复稿PDF自动核验-v001.json').read_text(encoding='utf-8'))
current=R/qa['render_directory'];prior=current.parent/'attempt-002'
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
matches=[{'page':i,'file':f'page-{i:02d}.png','identical':sha(current/f'page-{i:02d}.png')==sha(prior/f'page-{i:02d}.png')}for i in range(1,19)]
if not all(x['identical']for x in matches)or qa['pages']!=18:raise RuntimeError('UNREVIEWED_PAGE_DIFFERENCE')
record={'pdf_sha256':qa['pdf_sha256'],'all_pages_inspected':True,'all_pass':True,'pages':18,
 'inspection':'Model viewed contact sheets containing all 18 attempt-002 actual pages, plus full page 11,13,17. Attempt-003 regenerated after equivalent Markdown pipe syntax fix; all18 PNGs byte-identical, linked below.',
 'page_identity_evidence':matches,
 'observations':{'pages_1_4':'Title, assumptions, symbols, constraints, finite geometry readable; no clipping or blank page.',
 'pages_5_8':'Energy, H02, band geometry and two-line search criterion readable; old long-formula overflow removed.',
 'pages_9_12':'Pooled denominator and statistical formulas readable; S5/S6 numeric columns separated, no overlay.',
 'page_13':'All12 monthly rows and annual/design tables1-3 complete on same page, units/captions visible.',
 'pages_14_15':'Both images and captions complete, equal-layout axes and U interpretation retained.',
 'pages_16_18':'Low-survival table, 13-row U table, limitations and conclusion present; page18 is continuation, not missing render.'},
 'compile':'XeLaTeX passes5/6 completed, no Overfull/Underfull/Missing character/Infinite glue; existing package-required LaTeX date warning retained without online installation.',
 'history':'attempt001 19-page evidence retained; old v001 accepted/unfinished paper untouched',
 'scope':'Presentation and source binding only, independent from numerical/physical validation.'}
(O/'PDF实际页面检查-v001.json').write_text(json.dumps(record,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
mp=W/'论文/第2问-正文证据映射-v002.md'
text=mp.read_text(encoding='utf-8').replace('其样本没有并入R027的搜索或独立确认。','旧C22确认结果已经作为本轮分析和搜索依据使用，但其原始射线统计未池化进R027的搜索评分或独立确认。')
text+='''

## 5 最终排版与交付核验接续（2026-09-05，当前有效）

上节“尚未编译”是分工收尾时的过程快照；现已用当前正文和tex转换器v002完成XeLaTeX双遍最终编译，PDF共18页，31个展示公式块、29个编号公式、10张表和2张图完整。初次19页渲染因G_P长公式和S5/S6列宽发生溢出；调整仅改变换行和列宽，短表改为整块tabular，当前表1—3完整同页，溢出/缺字/Infinite glue均未再出现。保留编译器现有包/内核日期提示，未联网更新。

- [当前PDF](LaTeX/第2问-模型建立与求解-v002.pdf)、[当前TeX](LaTeX/第2问-模型建立与求解-v002.tex)
- [Markdown与TeX对应](../诊断结果/Q02-修复-v001/Q02-修复稿Markdown与TeX对应-v001.json)、[PDF自动核验](../诊断结果/Q02-修复-v001/Q02-修复稿PDF自动核验-v001.json)
- [实际页面核验](../诊断结果/Q02-修复-v001/PDF实际页面检查-v001.json)、[当前18页](LaTeX/第2问-修复稿-v002-页面核验/attempt-003/)
- [独立模型核查](../诊断结果/Q02-修复-v001/论文模型核查-v001.md)、[复现说明](../诊断代码/Q02-修复运行与复现说明-v001.md)

实际查看了attempt002全部18页，另放大查看第11、13、17页；最后把表内绝对值改为Markdown无歧义写法后再编译渲染，attempt003的18个PNG与已查看页面逐字节相同。视觉证据不替代数值核验，也不证明物理真实性。此后当前正文、TeX、PDF以对应记录中的SHA绑定；本轮计算与论文仍待用户验收，管理员归档未确认。
'''
mp.write_text(text,encoding='utf-8')
rev=W/'论文/第2问-修订与排版记录-v002.md'
with rev.open('a',encoding='utf-8')as f:f.write(r'''

## 修订10：长公式及候选表列宽的实际页面修复

修改原因：首编译日志记录搜索筛选公式溢出约25.11pt，S5/S6中面积数值溢出约8.35/3.17pt，实际第12页出现面积/功率列相邻数值过挤；longtable跨页同时报告Infinite glue。不能仅据“PDF已生成”认定排版通过。

修改位置及内容：第6.1节搜索筛选式只把系数常数另起一行；转换器另建v002，对S5/S6按数据宽度分配列宽，把10张均可单页容纳的短表由跨页longtable改为整块tabular，数值、表头、顺序和公式含义不变。原转换器v001、首轮19页渲染及修订前TeX/正文/日志保存在attempt001。

修改前：搜索筛选式与 (t_{3,0.975}=3.182446305) 位于同一行；S5的“总面积（m²）”和 (P_h) 列使用与其余8列相同宽度。完整原文和生成代码已保留在[首轮证据](LaTeX/第2问-修复稿-v002-页面核验/attempt-001/)，不以重述取代原证据。

修改后：

[
egin{aligned}
G_P&=widehat{overline P}-maxleft{50 mathrm{kW}, 2maxleft[t_{3,0.975}widehat{mathrm{SE}}_P,left|widehat{overline P}-widehat{overline P}_{1/2}ight|,left|widehat{overline P}-widehat{overline P}_{m raw}ight|ight]ight},\
t_{3,0.975}&=3.182446305.
end{aligned}
]

S5/S6列宽按数据与表头分别分配，全部短表不再跨页；表1—3在最终第13页完整显示。表S3中 (lvert a_xvert) 只替换容易被Markdown表格分隔符误读的绝对值写法，不改变不等式。表S8日期写为每月21日，不把代表样本误称整月统计。

验证依据：最终编译passes5/6无Overfull、Underfull、Missing character或Infinite glue；18页全部渲染。已实际查看全部页面及第11、13、17页细节；最终attempt003与已查看attempt002的18张页面逐字节相同。当前[自动核验](../诊断结果/Q02-修复-v001/Q02-修复稿PDF自动核验-v001.json)与[实际查看记录](../诊断结果/Q02-修复-v001/PDF实际页面检查-v001.json)绑定当前PDF和正文，旧v001文件不变。现有本地LaTeX包请求的日期与内核日期不同仍作为环境提示保留，未安装或更新依赖。

影响范围：仅表达、表格布局和对应PDF，不改变光学计算、冻结设计、工作指标、额定判据及科学结论。最终状态为论文初稿已完整编译核验、待用户验收；上节尚未编译为历史过程记录，已由本节接续。
''')
print('ACTUAL_PAGE_QA_SAVED_ALL18_IDENTICAL; mapping/revisions finalized')
