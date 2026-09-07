"""Generate stage records and table drafts solely from saved verified summaries."""
import sys,math,csv,json
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parent))
import q01_full_run_v002 as r
ROOT=r.ROOT;WORK=ROOT/'工作记录';RES=r.OUT

def write(p,text): Path(p).write_text(text,encoding='utf-8')
def link(p,label=None):return f'[{label or p.name}]({p.as_posix()})'
def f(x,d=4):return 'NA' if x is None else f'{x:.{d}f}'
def plus(v,u,d=4):return 'NA' if v is None or u is None else f'{v:.{d}f} ± {u:.2g}'
def build():
    a=r.load(RES/'汇总与数值核验-v001.json');re=r.load(RES/'汇总重建一致性.json');budget=r.load(RES/'累计计算预算.json');cfg=r.load(r.CFG)
    stress=r.load(RES/'压力测试与计时.json');sel=r.load(RES/'压力样本预登记.json'); repair=r.load(RES/'检查点修订验证.json')
    point=a['point'];u=a['work_uncertainty_indicator'];half=a['approx_pointwise_95_halfwidth'];met=a['targets_met']
    table1='| 日期 | 平均光学效率 | 平均余弦效率 | 平均阴影遮挡效率（N04） | 平均截断效率（N04） | 单位面积平均输出热功率（kW/m²） | 状态 |\n|---|---|---|---|---|---|---|\n'
    for k in range(12):table1+=f'| {k+1}月21日 | '+ ' | '.join(plus(point[k][j],u[k][j]) for j in [0,1,2,3,5])+' | '+('本轮工作目标达标' if all(met[k]) else '初算：存在未达标/未定义项')+' |\n'
    table2='| 年平均光学效率 | 年平均余弦效率 | 年平均阴影遮挡效率（N04） | 年平均截断效率（N04） | 年平均输出热功率（MW） | 单位面积镜面年平均输出热功率（kW/m²） |\n|---|---|---|---|---|---|\n'
    table2+='| '+' | '.join(plus(point[12][j],u[12][j]) for j in range(4))+' | '+plus(point[12][4]/1000,u[12][4]/1000,3)+' | '+plus(point[12][5],u[12][5])+' |\n'
    uncertainty='| 月/年 | 光学效率近似95%半宽 | 光学效率工作指标 | 截断效率工作指标 | 总热功率工作指标（kW） | 功率相对工作指标 | 六项达标数 |\n|---|---|---|---|---|---|---|\n'
    for k in range(13):
        ratio=u[k][4]/abs(point[k][4]) if point[k][4] and u[k][4] is not None else None
        uncertainty+=f'| {a["rows"][k]} | {half[k][0]:.3g} | {u[k][0]:.3g} | {u[k][3]:.3g} | {u[k][4]:.3g} | {ratio:.3%} | {sum(met[k])}/6 |\n'
    coverage_table='| 覆盖与样本 | 实际值 |\n|---|---|\n'
    cv=a['coverage']
    for label,key in [('应有组合','expected_combinations'),('已完成组合','completed_combinations'),('初算独立批次','initial_independent_batches'),('确认独立批次','confirmation_independent_batches'),('最终点估计所用批次','final_point_batches'),('每组合最终样本','final_samples_per_combination')]:coverage_table+=f'| {label} | {cv[key]} |\n'
    state_table='| 最终池化状态 | 组合数 |\n|---|---|\n'
    for key,value in a['states']['pooled_counts'].items():state_table+=f'| {a["states"]["codes"][key]} | {value} |\n'
    check_table='| 数值核查 | 实际值 |\n|---|---|\n'
    for key,value in a['numeric_checks'].items():check_table+=f'| {key} | {value} |\n'
    passed=a['numeric_validation_pass'] and a['work_targets_all_met'] and re['passed']
    stage_status='第1问全场初算与数值精度验证完成，待用户验收。' if passed else '第1问全场初算已保存，存在未达标或未解决项，待用户验收。'
    results=f'''# 第1问结果初稿 v001

- 状态：{stage_status}
- 本稿按题面表1、表2组织，只属于第1问；依据1745镜×60时点全覆盖实际计算，不使用外推。最终点估计使用8个独立确认批次，每镜每时每批256条；另有8批×128独立初算供复核。
- 表中“±”为本轮**工作不确定性指标**，不是严格置信区间，也不包含尚未量化的物理模型误差。近似逐项95%半宽另列；不宣称所有表项同时95%覆盖。
- 题面表1/表2结构依据[题面核对第5节](../诊断结果/题面公式与表格核对-v001.md)。用户效率0.001绝对量、功率0.5%相对量目标与题面要求分开。

## 1. 采用范围

H01非闰年代表日历、H02镜数/规定时点等权、H03实体省略、H04反射率0.92；P半角0.00465 rad、均匀立体角硬截止；N01参考面及逐方向权重；N02理想单次反射、零厚度不透明镜；N03有限圆柱侧面有效、端面不受光；N05状态与NA，均沿已批准第1问范围。

**N04分项说明：**命中接收体时在首次实体接触终止，未命中时按接收体包围球后界面终止遮挡查询。阴影遮挡和截断分量依此计算，不能解释为题面唯一确定的物理分解。改变未接收路径终点可能改变两分项而不改变净接收；不能只凭乘积相等认证分项。没有为了调节结果修改终点。

## 2. 表1：各月规定代表日结果

{table1}
## 3. 表2：年平均结果

{table2}
本表“年平均”只指题目规定60个样本时点的等权平均，不是全年连续能量积分。总热功率由逐镜、逐时DNI配对计算后汇总，单位面积功率分母为总镜面面积62820 m²。效率以小数报告；余弦项在当前输入下为确定性计算，所示微小浮点差不是物理不确定性。

## 4. 数值精度证据

{uncertainty}
工作指标取：近似95%半宽、确认256相对128前缀的变化、确认相对独立初算的变化、原始积分替代估计差的最大值。前缀相关；最后一项只观察自归一缩放影响，不是有限样本偏差的严格上界。逐项详细指标见[汇总JSON](../诊断结果/Q01-全场-v001/汇总与数值核验-v001.json)。

{state_table}
若出现NA，本规则不删对象、不补0/1，受影响汇总保持NA。独立批次状态及池化前后的区别完整保存在JSON。

## 5. 解释限制与证据

- 物理误差：光源为参考工程近似；省略塔身/支架/厂房及额外光学误差，其影响未量化。数值工作目标达标不证明这些误差很小。
- 数值误差：jackknife/Student近似依赖独立批次、足够样本和局部平滑的比值泛函；8批不是严格覆盖率保证。自归一和条件比值存在有限样本偏差风险。
- 实现问题：本轮曾有检查点原子替换拒绝访问，已另存入口修订、保留失败和恢复证据；没有用修改物理值解决存储错误。
- [阶段记录](Q01-全场初算与数值精度验证-v001.md)、[完整中间结果目录](../诊断结果/Q01-全场-v001/)、[汇总重建一致性](../诊断结果/Q01-全场-v001/汇总重建一致性.json)。平均条件效率与能量总量比另存为不同字段，不相互替代。

文件已保存；待用户验收；管理员归档未确认。本稿不是完整论文，不涉及后两问。
'''
    write(WORK/'阶段记录/Q01-第1问结果初稿-v001.md',results)
    pressure='| 月21日/时刻 | 镜号/Excel行 | 预选依据 | 入射/出射候选 | 相同路径对照 |\n|---|---|---|---|---|\n'
    for q in stress['records']: pressure+=f'| {q["month"]}/{q["hour"]} | {q["mirror_id"]}/{q["excel_row"]} | {q["rule"]} | {q["candidates"][0]}/{q["candidates"][1]} | '+('通过' if all(q['matches'].values()) else '失败')+' |\n'
    entries='| 计算阶段 | 累计预算计入秒数 | 状态 |\n|---|---|---|\n'
    for q in budget['entries']: entries+=f'| {q["mode"]} | {q["charged_seconds"]:.3f} | {q.get("status","完成")} |\n'
    model=r'''## 3. 全场接口、估计器及独立性

正式物理公式沿用[已验收原型第2节](Q01-建模与原型验证-v001.md)。core-v003仅在trace加入候选集缓存；有限实体、接触顺序、光源分布、能量权重及容差不变。缓存由完整1745镜计算，按原包围球必要条件筛选，不按最近若干块截断。

设一个镜—时点为一个对象，原始样本向量为

\[
X=(g,\ gSB,\ gSBR),\qquad g=\frac{\boldsymbol n\cdot\boldsymbol s}{\boldsymbol s_0\cdot\boldsymbol s}.
\]

每个独立批次保存三分量和、交叉乘积和、事件计数与边界权重。最终8批等样本量，先合并原始和，再逐对象取比；不先平均批次条件比。原始加权积分是对应样本均值；自归一估计和条件比一般有有限样本偏差，不宣称三者均无偏。

\[
\widehat\eta_{\rm sb}=\frac{\sum_b S_{b1}}{\sum_b S_{b0}},\quad
\widehat\eta_{\rm trunc}=\frac{\sum_b S_{b2}}{\sum_b S_{b1}},\quad
\widehat\eta=0.92\,c\tau\frac{\sum_b S_{b2}}{\sum_b S_{b0}}.
\]

随后严格按H02：分量逐镜平均；各月5时点等权；全年60时点等权。功率在每个时点使用对应DNI并遍历1745镜，最后汇总。镜面积均36 m²、总面积62820 m²；kW到MW仅在显示时除1000。能量总量比在另一字段单算，不替代平均条件效率。

令 \(T\) 表示从全体逐镜逐时原始和形成某个月/年汇总量的完整函数，\(B=8\)。点估计和删一整批估计为

\[
\widehat\theta=T\left(\sum_{b=1}^{B} S_b\right),\qquad
\widehat\theta_{(-b)}=T\left(\sum_{a\ne b} S_a\right).
\]
\[
J_b=B\widehat\theta-(B-1)\widehat\theta_{(-b)},\qquad
\widehat{\mathrm{SE}}_J=
\sqrt{\frac{\sum_b(J_b-\overline J)^2}{B(B-1)}}.
\]

近似逐项95%半宽为 \(h=t_{7,0.975}\widehat{\mathrm{SE}}_J\)，使用数值2.3646242515927844，另以Student密度数值积分验证分位值。该公式为本轮基于独立批次和一阶比值近似的统计推导，不冒称本地教程已完整讲解jackknife。

原始同一批次中的不同镜/时点用不同SeedSequence子流；相同批号只是把这些子流组成一个完整独立重复。删一整批保留该重复内所有量的关联，不再除以镜数或时点数的平方根。初算和确认使用不同阶段码，确认不参与调参。最终区间针对确认组池化点估计，个别批次均值另存而不偷换为最终点估计。

工作不确定性指标定义为

\[
U=\max\left(h,
|\widehat\theta_{256}^{C}-\widehat\theta_{128}^{C}|,
|\widehat\theta_{256}^{C}-\widehat\theta_{128}^{I}|,
|\widehat\theta_{256}^{C}-\widehat\theta_{\rm raw}^{C}|\right).
\]

其中C为确认组、I为独立初算；C内128是256的相关前缀。仅完整256用于最终合并，不把前缀再加一次。该最大值是用户工作目标所采用的数值诊断指标，不是严格误差上界或同时置信界。粗细差及独立差反映随机与有限样本效应，不能从相邻层级接近单独宣称收敛。

效率要求 \(U\le0.001\)，功率要求 \(U/|\widehat P|\le0.005\)。若 \(|\widehat P|\le10h\) 或功率近机器零，则不判相对达标，只报绝对U。阈值是本轮数值工作规则，不是题面或物理参数。

N05保持：无命中样本不是真实零； pooled后仍零、输入失败、边界不确定均明确标记，受影响固定总体汇总NA。合法直接能量可知时保留合法总量；本轮没有用删除对象或填0/1消解异常。
'''
    stage=f'''# 第1问全场初算与数值精度验证 v001

- 当前状态：**{stage_status}**
- 原型v001已用户阶段验收；原文和历史待批状态保留。D015登记N04本轮延续、用户工作目标及完整评价授权；D016冻结本轮配置。管理员归档未确认。
- 本轮只涉及第1问；[结果初稿](Q01-第1问结果初稿-v001.md)按表1/2组织。未联网、未读取其他题目或Git历史，未操作GitHub。

## 1. 回读与来源范围

回读AGENTS、状态/索引、原型阶段、相关决策/更新/方法查阅与归档、核心v002、测试v002、受限运行入口和配置、原验证结果及运行说明。实际重新全文阅读M05-v001；题面公式核对第4/5节和原有题面文字定点核对。其余M/P/Datawhale原文沿用此前已记录学习，没有重新全文阅读，不重复渲染或全面材料审计。

输入和方法版本见[配置v001](../诊断代码/Q01-全场配置-v001.json)bindings；I/O修订见[执行修订v002](../诊断结果/Q01-全场-v001/执行修订-v002.json)。资料和既有交付只读。

N04核对：附录4给定条件截断分母及联合阴影遮挡效率；现有题面未给未接收射线终点，没有发现明确冲突。按本轮用户批准采用，不认定唯一物理分项；各分项旁保留解释。

## 2. 前置压力检查

全场几何统计先于新增压力样本光学计算：入射候选范围0—4、出射0—3，20米邻域最多8。按候选最大和密度规则固定12组合，稳定排序处理并列，不先看光学结果。样本名单与预登记时间在[压力预登记](../诊断结果/Q01-全场-v001/压力样本预登记.json)。

{pressure}
每组256相同射线比较S、B、R、unknown，12/12一致；接收体独立参与，障碍始终为全镜场。另用各8批×256计时，组合中位约0.004374秒。该代表性估计不作为全年性能保证。

N04另比较原终点和延长50米的终点，分别保存sb、trunc、net，净接收事件一致；原型人工构型已展示sb由1到0.5、trunc由0.5到1而net不变。本轮真实压力样本不发生分量变化也不能覆盖所有场景。压力辅助份额曾有约1e-15的浮点越1，原数值保留，无裁剪；不属于物理超界。

core-v003实际重新运行原11项基础和2个R1/R2交叉，全部通过；其中R2有限边界非单调的旧风险未撤销。汇总新增5项独立人工检查通过（H02、jackknife线性标准误、NA固定总体、Student分位、池化与平均比区别）。不是重复整个材料审计。

{model}
## 4. 配置、模块与恢复

| 模块/数据 | 当前文件 | 职责 |
|---|---|---|
| 物理核心 | q01_core_v003.py | 与v002相同物理/几何/权重，新增可选原候选集缓存 |
| 回归入口 | q01_tests_v003.py | 11基础和2解析构型交叉，新输出不覆盖旧证据 |
| 完整运行 | q01_full_run_v002.py | 输入映射、60时点、独立子流、分块统计与预算；v001失败版保留 |
| 汇总重建 | q01_full_summary_v002.py | 从落盘分块建立H02、删一整批误差、状态与恒等核查 |
| 配置 | Q01-全场配置-v001.json | 冻结数值/物理/资源定义和原绑定；执行修订v002补新入口哈希 |
| I/O验证 | q01_checkpoint_repair_v001.py | 人工拒绝替换及实际写入、数值函数保持检查 |

PCG64，根种子2026090402；SeedSequence为根、阶段码、time_index、mirror_id、batch。初算911，确认912；每批每对象从独立流生成四维均匀数（面积两维、方向两维）。8批×128初算，8批×256确认；固定设计，不用确认数据自适应选择配置。最高单次追迹2048条射线，不载入全年全部射线。

逐时完整分块只写一次；每250镜存partial，每100镜核查累计用时。恢复核配置/哈希，已完整分块跳过，未提交区间用相同种子重算；partial不重复纳入汇总。完整分块存在时对应partial仅保留历史，不视为未完成组合。预算保留启动/停止余量，包含失败运行；不能无限续跑。

## 5. 实际覆盖、结果与数值核验

{coverage_table}

{state_table}

{check_table}

- 全部60完整时间分块唯一，每时1745镜；输入映射保持镜编号1—1745、原Excel行2—1746一一对应。
- 五因子与直接能量、面积关系、逐时DNI和H02月/年对象核查通过情况为：{a['numeric_validation_pass']}。
- 从磁盘在两个独立进程分别加载120个完整分块重新生成汇总，点估计/指标/状态/定义核查一致：{re['passed']}。这不是在原运行内存中自证。
- 工作指标通过：{sum(sum(x) for x in met)}/{len(met)*6}（12个月+年均，各含4效率和2功率；月总功率也额外核查，表1不增加该列）。近似区间逐项，不是整体覆盖。

{uncertainty}
完整独立批次、删一批估计、原始积分替代、细化变化、能量总量比均保存在[汇总与数值核验](../诊断结果/Q01-全场-v001/汇总与数值核验-v001.json)。表1/2位数用于可读初稿，不暗示超出证据的精度。

## 6. 失败与修订追溯

F03：原runner-v001直接原子替换预算文件，第6时点中途发生WinError5。前5时点已完整落盘，第6时点1250镜的partial留存；具体外部占用原因未确认。失败日志、原runner/summary和失败时partial副本均保留。

修订runner/summary-v002只增加有界PermissionError重试及执行版本绑定，不改变数值定义。人工重试与JSON写入、核心数值函数AST及汇总接口重新检查通过。恢复后原完整分块未重跑，partial以后可能重复处理最多249镜×8×128=254976条；这些只计处理成本，不重复合并。原配置v001保持不动，执行修订补充绑定。

原判断—新判断：原型只有限定样本证据，不能声称全场已算；本轮覆盖、精度和状态经实际全量运行得到，按当前证据增加全场数值结论。原型原文仍保留其当时边界，不将当前结果回填为当时已知。

## 7. 预算、误差限制与停止

{entries}
截至汇总重建后累计计入约{budget['charged_seconds']:.3f}秒（含启动/停止保守余量），上限1800秒；后续文档生成/文件核验另计最终账本。新增光学样本：初算107212800、确认214425600；确认前缀不另计独立样本。压力查询33792次、回归人工1003520次，失败恢复最多额外254976次；不保存全部普通射线。

数值目标只评价当前物理模型的数值实现。几何容差是机器尺度处理；物理模型误差（光源、实体省略、理想反射及额外误差省略）仍未知。自归一/条件比偏差无严格上界；R2局部交叉不证明任意复杂镜场的确定性积分收敛。当前近似逐项区间不提供同时覆盖保证。

本阶段完成后停止，待用户验收；不自动进入第2/3问、论文或优秀论文复盘。若物理、N04分项或统计总体改变，逐镜原始事件/积分对应假设需评估失效范围并另版本重算；仅显示位数改变可从保存统计重建，但也记录差异。

## 8. 文件核验与复现

数值验证以第5节及JSON为据；文件核验另见[全场交付核验](../诊断结果/Q01-全场-v001/交付文件核验-v001.json)，不能相互替代。全部代码、配置、日志、分块、状态、恢复证据的哈希清单另存本目录；入口和实际命令见[运行说明](../诊断代码/Q01-全场运行说明-v001.md)。文件已保存，待用户验收，管理员归档未确认。
'''
    write(WORK/'阶段记录/Q01-全场初算与数值精度验证-v001.md',stage)
    # Plain CSV complements Markdown; no Excel/template or physical input modification.
    for name,idxs in [('表1-初稿.csv',range(12)),('表2-初稿.csv',[12])]:
        with (RES/name).open('x',encoding='utf-8-sig',newline='') as stream:
            cw=csv.writer(stream);cw.writerow(['period']+a['labels']+[x+'_U' for x in a['labels']]+['all_targets_met'])
            for k in idxs:cw.writerow([a['rows'][k]]+point[k]+u[k]+[all(met[k])])
    runnotes=r'''# 第1问全场运行与复现说明 v001

唯一工作区为当前匿名任务目录；Python/NumPy环境和哈希绑定见配置v001。以下是本轮已执行命令；成功输出采用独占写入，不能为复跑删除历史结果。未来获准复跑需新输出版本并记录绑定。

~~~powershell
$env:OPENBLAS_NUM_THREADS='1'
& 'C:\Users\admin\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe' -I -B '工作记录/诊断代码/q01_tests_v003.py'
& 'C:\Users\admin\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe' -I -B '工作记录/诊断代码/q01_full_run_v001.py' prepare
& 'C:\Users\admin\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe' -I -B '工作记录/诊断代码/q01_full_run_v001.py' stress
& 'C:\Users\admin\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe' -I -B '工作记录/诊断代码/q01_full_summary_v001.py' selftest
& 'C:\Users\admin\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe' -I -B '工作记录/诊断代码/q01_full_run_v001.py' freeze
# v001 initial失败；保留日志后执行I/O修订验证及恢复：
& 'C:\Users\admin\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe' -I -B '工作记录/诊断代码/q01_full_run_v001.py' initial
& 'C:\Users\admin\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe' -I -B '工作记录/诊断代码/q01_checkpoint_repair_v001.py'
& 'C:\Users\admin\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe' -I -B '工作记录/诊断代码/q01_full_run_v002.py' initial
& 'C:\Users\admin\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe' -I -B '工作记录/诊断代码/q01_full_run_v002.py' confirmation
& 'C:\Users\admin\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe' -I -B '工作记录/诊断代码/q01_full_summary_v002.py' rebuild
& 'C:\Users\admin\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe' -I -B '工作记录/诊断代码/q01_full_summary_v002.py' verify-rebuild
~~~

## 数据结构

- initial/t000.npz—t059.npz：8批×128，每时1745镜；sums/交叉和/事件计数/边界权重及余弦、tau、DNI。层级轴仅128。
- confirmation/t000.npz—t059.npz：8批×256，层级轴128/256，128为相关前缀；最终只取256，不能相加。
- 维度：sums为层级×批×镜×3，cross末两维3×3，counts末维依次阴影、SB存活、SBR接收、边界不确定、出射遮挡、有效侧入；raw状态可由这些字段重建。
- 逐镜逐时合并结果.npz：60×1745，原始池化和、各效率、直接功率、状态码；结合输入映射与时间.json回查Excel行。
- 初算/确认阶段码911/912，根2026090402，子流含time_index、mirror_id、batch，SeedSequence+PCG64。保存环境仅保证指定环境复现，不承诺跨版本位级一致。
- 运行事件.jsonl追加每时点完成、预算和分块哈希；累计计算预算.json为当前账本；失败运行.jsonl保留中断。partial为恢复工作状态，完整分块存在时以完整分块为准。
- 执行修订-v002.json绑定I/O新入口，不替代原配置或改变随机定义。确认运行从未用于调整配置。
- CSV所有效率为小数、power_kw列为kW、单位面积列为kW/m²；Markdown表2按题意将总功率改显示MW。CSV不是原题模板。

## 预算和停止

累计限制1800秒，各计算入口自动计入运行及固定启动余量；单个计算块不能无限扩大，门禁留20秒用于保存停止。文档读取和人工编写的等待时间不属于光学计算；实际进程I/O、失败运行和恢复均计入。预算账本后续每次调用接续，不因进程重启归零。

重建汇总只读取保存统计，不重放光学射线。点估计为逐对象池化比再H02；不确定性对应删一整批同一函数。raw积分、自归一份额、条件比和能量总量比分开保存。样本无命中与真零不混用；发现异常按原定义传播NA。
'''
    write(r.CODE/'Q01-全场运行说明-v001.md',runnotes)
    print(json.dumps({'stage_written':True,'result_written':True,'status':stage_status},ensure_ascii=False))

if __name__=='__main__':
    b=r.Budget('document-generation')
    try:build()
    except BaseException:b.finish('failed');raise
    else:b.finish()