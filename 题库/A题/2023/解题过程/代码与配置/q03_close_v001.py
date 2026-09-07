"""Close Q3 evidence and controls only after actual document and numerical QA."""
from pathlib import Path
import sys,json,time,hashlib
sys.path.insert(0,str(Path(__file__).resolve().parent))
import q03_common_v001 as io
R=io.ROOT;O=io.OUT;W=R/'工作记录'
def append(p,t):
    with p.open('a',encoding='utf-8',newline='\n')as f:f.write('\n\n'+t.strip()+'\n')
def main():
    q=io.load(O/'delivery/交付文件核验-v001.json');v=io.load(O/'delivery/PDF人工页面核验-v001.json')
    assert q['passed']and v['passed']and v['all_pages_reviewed']
    for fn,tag in [('决策记录.md','D047'),('06-更新记录.md','U054')]:
        assert not ('## '+tag in (W/fn).read_text(encoding='utf-8-sig'))
    b=io.load(O/'累计计算预算.json');assert not any(x['status']=='RUNNING'for x in b['records'])
    io.save(O/'delivery/结算前预算快照-v001.json',b)
    measured=b['used_seconds'];allowance=30.
    b['used_seconds']+=allowance;b['records'].append({'mode':'unmetered_overhead_allowance','phase':'accounting','elapsed_seconds':allowance,'status':'CONSERVATIVE_ALLOWANCE','start':io.now(),'finish':io.now(),'scope':'not measured computation: conservative charge for early unwrapped interpreter startup, standalone post-process startup and small final bookkeeping/readback; ordinary writing/typesetting separate'})
    assert b['used_seconds']<=5400
    io.save(O/'累计计算预算.json',b)
    modes={}
    for x in b['records']:modes[x['mode']]=modes.get(x['mode'],0)+x['elapsed_seconds']
    cpu=[]
    for p in (O/'candidates').glob('*/**/parallel-audit/*/run.json'):
        r=io.load(p);cpu.append({'path':str(p.relative_to(O)),'parent_cpu':r.get('parent_cpu_seconds',0),'worker_cpu_cumulative':r.get('worker_cpu_cumulative_sum',0),'scope':r.get('cpu_scope')})
    settlement={'metered_job_wall_seconds':measured,'additional_conservative_allowance_seconds':allowance,'charged_seconds':b['used_seconds'],'limit_seconds':5400,'remaining_seconds':5400-b['used_seconds'],'by_mode':modes,'cpu_lower_bound_records':cpu,'worker_cpu_lower_bound_sum':sum(x['worker_cpu_cumulative']for x in cpu),'cpu_not_added_to_wall':True,'no_new_optical_rays_after_confirmation':True,'text_and_typesetting':'recorded separately in manuscript recovery/compilation/rendering receipts; no optical budget reset'}
    io.save(O/'delivery/预算最终结算-v001.json',settlement)
    timeword=f"作业墙钟已计{measured:.3f}秒，另保守计入未逐项实测启动/收尾开销30秒，预算扣款合计{b['used_seconds']:.3f}秒（{b['used_seconds']/60:.2f}分钟），小于5400秒；30秒不是实测值。"
    resultword='Q3F013：2981面，塔位(0,-15)m；各组宽6.69m、安装高6m，组4的582面镜高6.05m，其余2399面镜高6.65m；总面积130284.0705m²。年均P=60020.32210427637kW，U=7.8759060468305115kW，额定工作余量12.446198229539732kW。年单位面积q=0.4606881092518243kW/m²；新配对R027的q=0.45635300283703945，差0.004335106414784906，差工作量0.00002639934494221077kW/m²，约提高0.94995%。'
    append(W/'决策记录.md','## D047 — 2026-09-05 — Q3独立确认、文件核验与条件式论文交付\n\n'+resultword+'\n\n候选和新R027基线各2981×60组合、8个独立批次×256；128仅相关前缀。必需效率/功率共78个汇总工作目标通过，几何/适用域、额定、配对改善、独立落盘重建、实际Excel读回分别通过。候选仍有2个低存活组合（39、62），已按实际面积保守影响量计入工作指标，未删镜或当作单镜精度证明。\n\n依据用户G35的预授权条件继续完成第3问正文、图表、LaTeX与PDF；本轮全部仍待用户验收。有限6组固定布局搜索，不认定全局最优或物理误差量化；管理员归档未确认。原型计数更正为18项，未改变测试或模型。来源见本轮搜索阶段、结果初稿、delivery独立核验/配对/文件与页面核验。\n\n'+timeword)
    append(W/'06-更新记录.md','## U054 — 2026-09-05 — Q3条件衔接完成与收尾更正\n\n原状态：D046冻结Q3R013→Q3F013，确认与写作未完成。新依据：两份8批完整确认、独立重建和实际清单/题表检查通过；论文实际编译及全部页面检查通过。'+resultword+'\n\n新增异尺寸原型v001、分组搜索确认v001、结果初稿v001、正文/映射/修订v001及本地LaTeX/PDF；同步六份控制及本题经验。更正原型草稿19→18、零计数非互斥列名、单位与数学显示；前文/源码保留在对应before快照。Excel values调用失败、缺Matplotlib、图轴范围断言、论文换行哈希与记录计数门禁失败均保存，未修改有效光学设计或确认数据。详细原判断/新依据/差异与范围见交付收尾更正记录、论文修订和records差异JSON。早期两新文件相对路径越界事件已记录和移回，不掩盖。\n\n'+timeword+'\n\n现有报告中的预算、页面“待核验”是生成时快照，当前以最终结算、PDF人工页面核验和本条为准。没有重跑前两问或改变其学术结论；不进行全题揭晓、论文统一冻结或GitHub操作。')
    (W/'00-任务状态.md').write_text('# 当前任务状态\n\n2026-09-05：**第3问求解、独立确认及论文初稿完成，待用户验收。**\n\n第1、2问已验收；第3问准备已验收，本轮计算与论文尚未获用户验收。管理员归档未确认，全题盲解未冻结。\n\n'+resultword+'\n\n18项限定原型及人工设计/汇总测试通过；6组固定布局，14低样本候选和4较精比较，最终候选与R027分别8批×256完整确认。78个汇总数值工作目标、额定判据、配对改善、全部几何/适用域、独立重建与实际Excel读回通过。仍有2个低存活组合，影响界计入工作指标；不推断局部估计精确或物理偏差很小。\n\n正式文件见[当前索引](记录索引.md)最新D047/U054节；论文MD、LaTeX、PDF及全部'+str(v['pages'])+'页的渲染和实际查看完成。文件核验与数值验证分别保存。\n\n'+timeword+'\n\n停止点：等待用户验收；没有待修复的必需表项或功率阻塞。不自动释放塔位/镜位/镜数、不扩展Q3-B/C、不加载优秀论文或操作GitHub。局限仍为有限搜索、所选异宽解释、N04分项约定和未量化物理偏差。当前D047/U054。\n',encoding='utf-8',newline='\n')
    entries=[('异尺寸原型','阶段记录/Q03-异尺寸原型验证-v001.md'),('分组搜索与独立确认','阶段记录/Q03-分组搜索与独立确认-v001.md'),('第3问结果初稿','阶段记录/Q03-第3问结果初稿-v001.md'),('正式逐镜清单','诊断结果/Q03-实施-v001/delivery/result3.xlsx'),('第3问正文','论文/第3问-模型建立与求解-v001.md'),('正文证据映射','论文/第3问-正文证据映射-v001.md'),('正文修订记录','论文/第3问-写稿修订记录-v001.md'),('LaTeX源码','论文/LaTeX/第3问-模型建立与求解-v001.tex'),('PDF','论文/LaTeX/第3问-模型建立与求解-v001.pdf'),('独立重建','诊断结果/Q03-实施-v001/delivery/独立重建核验-v001.json'),('配对改善证据','诊断结果/Q03-实施-v001/delivery/paired-comparison-v001.json'),('交付文件核验','诊断结果/Q03-实施-v001/delivery/交付文件核验-v001.json'),('PDF实际页面核验','诊断结果/Q03-实施-v001/delivery/PDF人工页面核验-v001.json'),('最终预算结算','诊断结果/Q03-实施-v001/delivery/预算最终结算-v001.json'),('复现说明','诊断结果/Q03-实施-v001/复现说明-v001.md'),('收尾更正','诊断结果/Q03-实施-v001/交付收尾更正记录-v001.md')]
    table='| 当前有效文件 | 版本与状态 |\n|---|---|\n'+'\n'.join(f'| [{name}]({path}) | v001；已保存，待用户验收 |'for name,path in entries)
    append(W/'记录索引.md','## Q03实施完整交付（D047/U054；2026-09-05）\n\n本节为当前有效状态：准备阶段已验收；本轮计算、结果和论文已完成，待用户验收。旧“进行中”及“待批准”保留历史，不覆盖本节已批准/完成状态。管理员归档未确认。\n\n'+table+'\n\n实现见诊断代码/q03*.py及q03_job_v001.ps1，全部冻结配置/完整分块/种子/失败/新确认在Q03-实施-v001；哈希总清单见delivery/交付哈希清单-v001.json。图表当前q03_figures_v002，v001为失败保留；原型19项文字已纠正18，不修改原测试。正文/阶段初稿生成后修订的before版本与记录源哈希保留，当前以正式路径和最后文件核验绑定为准。')
    append(W/'方法库查阅记录.md','## Q03实施与论文实际使用接续（2026-09-05，D047）\n\n方法范围沿Q03准备阶段已阅读且固定审核资料；本次定点回读本地约束、授权、模型/接口、R027有效数据和准备复用的代码、配置、验证证据，实施逐镜参数、异面积汇总、完整批次配对与独立重建。收尾回读第2问正文v002第2.1节/第4节公共模型和本地写作规范v001，并核对本轮源代码、冻结记录、结果、论文及图表。未将未再次阅读的M/P/Datawhale全文登记为再次完整学习；没有访问上游资料、参考论文或新工程输入。\n\n本题实现与自行推导包括几何宽上限、6组展开、状态证据、实际面积低存活界、删整批配对比较；其证据及适用条件见本轮阶段。绘图实际使用已有ReportLab/Poppler，缺Matplotlib没有联网补齐。用户粘贴请求仅作授权，抽象写作规范不是参考论文全文。')
    append(W/'归档清单.md','## Q03实施完整交接（D047/U054；2026-09-05）\n\n'+table+'\n\n还须整体保存诊断结果/Q03-实施-v001（全部14低样本/4较精/两份确认分块、清单、种子、配置、并行CPU、账本、所有失败及before快照）、诊断代码/q03系列、本地图表/Q03-v001、PDF页面核验目录、六份控制和经验。统计分块不重复计前缀；原Q1/Q2依赖保持既有版本。逐文件大小/SHA见本轮交付哈希清单；控制记录与最终预算的结算绑定另存delivery/控制记录最终绑定-v001.json。\n\n本轮均文件已保存，尚待用户验收；管理员是否归档未知，不自动标记已归档，不进行GitHub操作。')
    append(W/'经验.md','## 第3问异尺寸实施经验（2026-09-05）\n\n| 编号/类别 | 本题证据支持的认识 | 证据与边界 |\n|---|---|---|\n| E014 几何与搜索 | 固定镜位时每镜宽度上限由全部邻距减5给出，组上限取成员最小；本题共同上限约6.70m | groups-v001及全镜对；这是G31解释下的推导，换间距定义须重新核对 |\n| E015 本题计算 | 按镜数平均效率与面积加权效率在异面积设计中不同，实际面积须进入功率 | 最终镜均光学0.472360、面积加权0.472923及人工例/独立重建；不能推广为任意方向偏差 |\n| E016 本题计算 | 减少面积伴随总功率下降仍可能提高单位面积目标，但须单独保留额定判据 | Q3F013相对新基线P下降139.450kW、q约提高0.95%，余量12.446kW；仅限该确认设计/模型，不表示一般缩镜必然改善 |\n| E017 实现与追溯 | 报告硬编码的检查数量和不互斥零计数列名会造成错误门禁或叙述 | 19→18更正、原始零接收2包含零存活1；原数据不变，按明确ID和各分母状态核对 |\n\n未量化物理误差、固定布局有限分组、N04分项非唯一等限制保留；不更新工作区外总经验库。')
    append(W/'论文/第3问-正文证据映射-v001.md','## 最终文件与页面核验接续（D047/U054）\n\n此前“尚未生成/待核验”为生成时快照；现在正文、TeX、PDF、两图和题表已完成并核对。公式Q3-1—Q3-14逐项对照固定约束、设计、能量/统计接口；必需表1/2显示值逐项对照有效结果，表3身份/总面积核对。实际PDF共'+str(v['pages'])+'页，全部渲染并逐页查看。见[文件核验](../诊断结果/Q03-实施-v001/delivery/交付文件核验-v001.json)、[页面核验](../诊断结果/Q03-实施-v001/delivery/PDF人工页面核验-v001.json)及[最终预算](../诊断结果/Q03-实施-v001/delivery/预算最终结算-v001.json)。\n\n源生成记录绑定的是各生成时快照；收尾更正及最终字节以当前控制绑定为准，不将修订前哈希冒充最终哈希。文件一致性不能独立验证物理模型。所有成果待用户验收。')
    controls=[W/x for x in ['00-任务状态.md','记录索引.md','方法库查阅记录.md','决策记录.md','06-更新记录.md','归档清单.md','经验.md']]+[W/'论文/第3问-正文证据映射-v001.md',O/'累计计算预算.json']
    append(W/'06-更新记录.md','U054文件核验补记：首个文件检查器把独立公式中以绝对值符号开头的行误当Markdown表，门禁显式失败；保留旧源码与“公式误判”JSON后，在数学块内跳过表头识别，重跑通过9张表、73处链接、10页和当前数值绑定。未放宽数据比较或改变公式。图表排版从11页变为10页，所有原页面保留；PDF存在的本地LaTeX组件release提示已记录，无缺字或溢出，未升级依赖。')
    io.save(O/'delivery/控制记录最终绑定-v001.json',{'status':'Q3 calculation and paper complete; pending user acceptance; administrator archive unconfirmed','files':{p.relative_to(R).as_posix():io.sha(p)for p in controls},'budget':settlement,'file_qa_sha':io.sha(O/'delivery/交付文件核验-v001.json')})
    print(json.dumps({'state':'COMPLETE_PENDING_USER','charged_seconds':b['used_seconds'],'pages':v['pages']},ensure_ascii=False))
if __name__=='__main__':main()
