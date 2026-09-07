"""Write Q2 interface documents only; no numerical evaluation."""
from pathlib import Path
W=Path(__file__).resolve().parents[1]
def write(p,s): (W/p).write_text(s.strip()+'\n',encoding='utf-8')
write('诊断代码/Q02-设计与评价接口-v001.md',r"""
# 第2问设计与评价接口 v001

日期2026-09-05。当前设计v002、评价v003、运行v003，数值配置v002及I/O执行覆盖v003。仅用于获准原型范围；主记录见[原型阶段](../阶段记录/Q02-参数化与几何原型验证-v001.md)。

## 1. 设计结构及身份

| 字段 | 类型/单位 | 含义与检查 |
|---|---|---|
| name、version | 字符串 | 设计名/版本；参与场景身份和子流 |
| tower_xy | 两个有限数，m | 固定场界内塔中心 |
| width、height | 有限数，m | 各2—8，全镜统一 |
| installation_height | 有限数，m | 统一中心高2—6，严格大于半高 |
| mirrors | 非空记录数组 | N由实际记录数得到，文件声明镜数不符失败 |
| mirror_id | 正整数 | 48位SHA前缀加1；不要求连续，检碰撞 |
| position_key | 字符串 | 环/扇区/槽位身份，不是坐标不变证书 |
| x、y | 有限数，m | 世界坐标；场地不跟塔平移 |
| metadata | 字典 | 参数、名义顺序和裁剪记录 |
| export_row / source_record_index | 整数 | 当前CSV行或JSON记录来源，不称Q1附件行 |

Design.n、total_area取实际行数与 \(Nwh\)。生成顺序另存metadata.nominal_order；镜号由槽位键确定，先前扇区计数变化不改变存续槽位ID。不同设计同槽位可以同ID而坐标不同，必须同时保留设计身份/版本。

generate_ring_design返回Design和生成证据。每环/扇区给稳定名称、半径、半开角域、非负整数名义计数和 \([0,1)\) 相位。非空扇区：
\[
\theta_j=\alpha+(j+\varphi)(\gamma-\alpha)/m,\quad
(x_j,y_j)=(x_T,y_T)+r(\cos\theta_j,\sin\theta_j),\quad 0\le j<m.
\]
空扇区不除零。外场中心越界/塔禁布裁剪是预声明规则，逐点记录且重数N；不修复间距或重复。ID在全部名义点、裁剪前检冲突，碰撞即失败。

validate_design检查展开坐标全部无序镜对，分别返回schema、geometry、search_scope及违规证据。违反几何不移动点。\(w\ge h\)只属搜索范围。离地按 \(z-h/2>0\) 严格符号；其他批准边界按非严格不等式；近界报告带不放行负余量。保存/读回JSON、CSV全字段，CSV17位有效数字；默认不覆盖旧文件。

## 2. 参数化模型链

右手坐标东x、北y、上z；\(s_0\)朝太阳，实际入射传播 \(-s\)。镜中心 \(c_i=(x_i,y_i,z)\)，接收体中心 \(C=(x_T,y_T,80)\)：
\[
t_i=(C-c_i)/\|C-c_i\|,\quad
n_i=(s_0+t_i)/\|s_0+t_i\|,\quad
r_i(s)=-s+2(s\cdot n_i)n_i.
\]
宽边水平，高边与法向正交，正负按旧edge_frame固定。仅严格竖直时宽边向东，触发计数保存。实际源点为
\[
p=c_i+w(\xi-\tfrac12)u_i+h(\upsilon-\tfrac12)v_i .
\]
prepare显式把宽高传make_mirrors，不用旧aim_field的6米默认值；实际高度和塔位贯通目标、法向、接收体与路径。太阳/DNI沿用题式/H01；透射
\[
d_i=\|C-c_i\|,\qquad
\tau_i=0.99321-0.0001176d_i+1.97\times10^{-8}d_i^2
\]
保留旧距离适用域，不改成无来源的射线透射。Scene包含镜面数组、太阳、逐镜目标、有限接收体、DNI、tau、beta、容差、设计/时间/对象顺序及域检查。

## 3. 光源、事件及能量

硬截止半角0.00465 rad、按立体角均匀：
\[
p_\Omega=[2\pi(1-\cos\beta)]^{-1},\quad
\mu=\cos\theta=1-U(1-\cos\beta),\quad\psi=2\pi V .
\]
代码用 \(2\sin^2(\beta/2)\) 表示角域差。N01的DNI参考面垂直中心方向，方向能量份额为上述分布；投影权
\[
g_i(s)=\frac{n_i\cdot s}{s_0\cdot s}.
\]
完整角锥正面、地平线、分母正性是前提；轴对称完整锥才有 \(\mathbb E[g_i]=n_i\cdot s_0\)。镜外/锥外超机器带拒绝，边界附近标未知，不截域重归一。实际随机数数组每行四个均匀数控制两个空间和两个方向维度。

S为入射无镜/接收体遮蔽，B为反射在终点前无其他镜阻挡，R为接收体第一次实体接触有效外入侧面。圆柱半径3.5、高8，顶底不透明非受光。生存/接收为SB与SBR，不乘边际概率，重叠不重复扣除。接收后方障碍不再扣能量。

N04未接收射线的后平面终点：
\[
\lambda_{\rm end}=
\frac{R_c+(C-p)\cdot t_i}{r_i(s)\cdot t_i},\qquad
R_c=\sqrt{3.5^2+4^2}.
\]
反射阻挡查询到首次接收体实体接触与该终点的较近处。分子/分母和完整域不成立时失败，不赋无限反射路径；入射向太阳查询正半射线。N04是批准分项约定，可能影响阴影遮挡/截断分别的数值，不是唯一物理损失定义。

stats保存绑定、样本量、三个和及交叉和、阴影/遮挡/存活/接收/未知计数和未知权重。以
\(A=\sum g_\ell,\ B=\sum g_\ell S_\ell B_\ell,\ C=\sum g_\ell S_\ell B_\ell R_\ell\)，有
\[
\hat f_1=B/A,\quad\hat f_2=C/A,\quad
\eta_{\rm sb}=\hat f_1,\quad \eta_{\rm tr}=C/B,
\]
\[
\Pi_0=\rho\,\mathrm{DNI}\,wh(n_i\cdot s_0),\quad
\hat\Pi_1=\Pi_0\hat f_1,\quad
\hat\Pi_2=\Pi_0\hat f_2,\quad
P_i=\tau_i\hat\Pi_2 .
\]
原始积分 \(\rho\,\mathrm{DNI}\,wh(A,B,C)/L\)、自归一份额及条件比分别保存；combine只合并同Scene/对象的最终批次，不重计前缀，不把单批比值平均当池化。自归一有有限样本偏差，不裁剪效率掩盖错误。五因子是定义有效处的
\(\eta_{\rm sb}(n_i\cdot s_0)\tau_i\eta_{\rm tr}\rho\)，不重复余弦/反射/透射。

## 4. 真零证书及状态

certify_zero从Scene/当前对象自动建立“全镜面、全方向首先穿不受光端面”的充分包围证书，不接受调用者旗标。镜球半径 \(R_i\)，正向端面距离g，锥轴相对竖直夹角加beta为 \(\vartheta\)，当
\[
g>R_i+\epsilon,\quad\vartheta<\pi/2,\quad
\|c_{i,xy}-C_{xy}\|+R_i+(g+R_i)\tan\vartheta<r_{\rm rec}-\epsilon
\]
时，第一次实体接触必为端面。入射满足证明S恒0；反射满足证明接收恒0。“存活恒1”还须无镜候选且入射锥与接收体包围球分离。记录哈希/方向/各值/严格余量，观测矛盾则失败。未得到证书不证明非零；此通道不完备。

| 状态 | 依据 | 输出 |
|---|---|---|
| ESTIMATED | 正分母/接收，无未知 | 估计已定义，非精度认证 |
| TRUE_ZERO_SURVIVOR | 自动证书和统计一致 | 合法功率0、阴影遮挡0、截断NA |
| TRUE_ZERO_CAPTURE | 自动反射端面证书 | 合法功率0，条件分母另判断 |
| SAMPLED_ZERO_SURVIVOR/CAPTURE | 有限样本零且无证书 | 原始零估计另存，合法值保持未决 |
| BOUNDARY_UNCERTAIN | 未知几何/源边界 | 正式数值NA、原始估计和不确定份额保存 |
| 输入/几何/搜索域/模型域/实现失败 | 独立StateError或校验报告 | 不当成零或额定不达标 |

aggregate检查同Scene的完整镜号/索引/面积。缺对象不外推；分项NA不删除，总功率可独立由合法零和正值求和。仅逐时总体接口已实现；月年正式汇总下一阶段再按H02接入，不调用Q1固定1745总体入口。

## 5. 保守筛选与失效

令障碍中心差 \(\Delta\)、锥轴a，镜与障碍球半径和R。若相交，必有
\[
\Delta\cdot a\ge-R,\qquad
\|\Delta-(\Delta\cdot a)a\|\le R+(\|\Delta\|+R)\sin\beta .
\]
这是中心偏差≤R与正射线距离≤中心距加R给出的必要条件；仅取反排除，容差朝保守方向，不是最近几镜。筛后仍有限矩形求交，接收体独立查。

BoundCandidates保存场景哈希、评价索引、入/出候选tuple；Scene身份覆盖几何/尺寸/高度/法向边向/接收体/太阳目标/角尺度/容差/核心版本及完整对象顺序和时间tag。任何相关改变拒绝旧缓存或重建。交给旧核转换为int64一维数组。当前哈希反复计算，安全但偏贵；后续缓存哈希需要设计不可变或完整失效证明。

## 6. 范围

复用Q1-core-v003的太阳、反射、圆锥、有限对象/保守筛选低层；新Q2数据、prepare、身份、状态/证书/汇总独立文件。没有优化/局部改进循环或正式Excel。当前54组合及人工通过不证明任意布局。CSV重复metadata、重复全对/哈希成本、稠密场景、真实零证书不完备及最终精度另需验证。
""")
write('诊断代码/Q02-原型运行说明-v001.md',r"""
# 第2问原型运行与复现说明 v001

日期2026-09-05。工作区为唯一匿名单题目录。无网络、依赖安装、优化或后问。

## 环境和绑定

Python 3.12.14、NumPy 2.3.5，运行时
C:\Users\admin\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe。
每次使用参数 -I -B -X utf8，并明确工作目录。当前design-v002、eval-v003、tests-v002、runner-v003；固定Q1-core-v003只读。Q02配置v002绑定修复代码，执行修订-v003.json额外绑定I/O-only新运行器，原v002配置不改。

## 实际命令顺序

以下脚本均在工作记录/诊断代码，按上面的Python解释器执行；是历史记录，不代表现在再次授权重跑。

| 脚本与参数 | 实际结果 |
|---|---|
| q02_prototype_run_v001.py tests --attempt 1 | 配置v001，13几何+8评价通过 |
| q02_prototype_run_v001.py old --attempt 1 | tuple多轴索引失败 |
| q02_prototype_run_v002.py tests --attempt 2 | 配置v002，13+9通过 |
| q02_prototype_run_v002.py old --attempt 2 | 3同射线组合通过 |
| q02_prototype_run_v002.py prep --attempt 1 | 3几何清单/180轻量域/54预登记，无光学 |
| q02_prototype_run_v002.py diagnostics --attempt 1 | 保存5组合后预算替换拒绝访问 |
| q02_prototype_run_v003.py iotest --attempt 1 | 注入2次I/O失败，有限重试恢复 |
| q02_prototype_run_v003.py diagnostics --attempt 2 | 同配置跳过5，完成其余49 |
| verify_q02_prototype_statistics_v001.py | 1707落盘算术/身份/门槛核验，无新射线 |

完整历史调用形式为：Python解释器后跟 -I -B -X utf8、工作记录/诊断代码/q02_prototype_run_v003.py、diagnostics、--attempt、2。

已有attempt文件拒绝覆盖，prep同名目录也拒绝。交付后复算应另建获准新版本代码/配置/输出目录；不能删除旧证据重跑。本次恢复只处理当前配置未完成组合，不是追加抽样。

## 样本、检查点和失败

PCG64/SeedSequence，根种子2026090503。每组合4批×256源样本，64相关前缀另列不再合并。完整words绑定设计名/槽位/时点/批号并逐批保存，旧场另用namespace701+附件ID。每光学文件包含配置/设计/Scene哈希、全障碍镜数、原始三和与交叉和/计数、层级/删批及同射线对照。

恢复只跳过绑定一致完整组合；未知/失败不能删掉再称覆盖。原子替换最多8尝试，0.05秒起倍增退避、上限0.8秒；超限失败。遗留RUNNING预算不自动当0，先核真实用时才能恢复。本轮全部action结算。普通射线不落盘；异常路径保存batch/sample/源点/方向，本次新布局unknown为0。代码+Scene+seed可在新版本复现。

结果目录为工作记录/诊断结果/Q02-原型-v001，保留所有旧代码、冻结/执行覆盖、人工/回归失败成功、三个非正式清单、预登记、54光学记录、预算、重建和最终文件核验。当前55296积分源样本与56640含穷举/读回重放次数分开；重放不增加独立性。早期测试重跑和旧场失败不得与新布局合并算精度。

预算账本为action内计算及I/O累计，不含解释器导入、文档查阅、分析写作；文件封存时间另记。最终文件核验只检查保存/绑定，不替代几何、数值或物理验证。
""")
print('Interface and runbook saved.')