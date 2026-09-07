"""Generate traceable stage/results records from verified saved data; no rays."""
from pathlib import Path
import json,sys,datetime
H=Path(__file__).resolve().parent;W=H.parent;O=W/'诊断结果/Q02-修复-v001';ROOT=W.parent
def read(p):return json.loads(p.read_text(encoding='utf-8'))
data=read(O/'结果数据.json');ans=read(O/'独立确认结论.json');verify=read(O/'独立重建核验.json');uv=read(O/'独立工作指标重建.json');replay=read(O/'实际Excel同源重放核验.json');cmp=read(O/'实际候选比较.json');geo=read(O/'frozen/交付精度读回.json');budget=read(O/'累计计算预算.json')
if not all([data['decision']=='PASS',verify['all_pass'],uv['all_pass'],replay['all_pass']]):raise RuntimeError('DELIVERY_GATES_NOT_PASSED')
design=data['actual_design'];pt=ans['annual'];u=ans['annual_U'];old=cmp['old_C22']['annual'];low=ans['low_survival']
def fmt(v,d=6):return 'NA' if v is None else f'{v:.{d}f}'
def table(header,rows):return '| '+' | '.join(header)+' |\n| '+' | '.join(['---']*len(header))+' |\n'+'\n'.join('| '+' | '.join(str(x)for x in row)+' |'for row in rows)+'\n'
result='# 第2问结果初稿 v001\n\n状态：当前搜索得到的已确认可行设计，计算与文件交付待用户验收；管理员归档未确认。有限搜索不代表全局最优，物理模型误差未量化。\n\n'
for name,caption in [('table1','表1　每月21日规定5时点平均效率及单位面积功率'),('table2','表2　规定60时点的年平均性能'),('table3','表3　设计参数')]:
 t=data['tables'][name];rr=[]
 for row in t['rows']:
  rr.append([fmt(x,4)if isinstance(x,float)else x for x in row])
 result+=caption+'\n\n'+table(t['header'],rr)+'\n'
result+='## 数值判定与解释\n\n'+f'年功率内部全精度点估计为{pt[4]:.12f} kW，工作指标为{u[4]:.12f} kW，工作下限为{ans["rating_lower_kw"]:.12f} kW，额定余量为{ans["rating_lower_kw"]-60000:.12f} kW。全部月度/年度工作指标通过；独立确认8批、每镜每时点256源样本，128前缀只计一次。\n\n'
result+='工作指标为整批刀切近似半宽、相关前缀差、raw积分差三者最大值加低存活全范围影响量。它是逐项数值诊断，不是严格或同时置信界，不覆盖物理近似误差。N04是所采用有限终点分项记账；阴影遮挡与截断的分解不宣称题面唯一。年平均是规定60时点样本平均。实际完整Excel见[result2.xlsx](../诊断结果/Q02-修复-v001/result2.xlsx)，全精度表和工作指标见[结果数据](../诊断结果/Q02-修复-v001/结果数据.json)。\n'
rp=W/'阶段记录/Q02-第2问结果初稿-v001.md'
if rp.exists():raise RuntimeError('RESULT_STAGE_EXISTS')
rp.write_text(result,encoding='utf-8')
rows=[]
for r in cmp['rows']:
 rows.append([r['name'],r['fidelity'],r['n'],fmt(r['area_m2'],4),fmt(r['P_formal_kw'],3),fmt(r['q_formal_kw_m2'],6),fmt(r['P_heuristic_kw'],3),r['state_counts'].get('SAMPLED_ZERO_SURVIVOR',0),r['fine_gate']])
stage=f'''# 第2问可行性修复与独立确认 v001

状态：第2问求解、独立确认及论文初稿完成，待用户验收。管理员归档未确认。不进入第3问。

## 1 授权、起点与来源

用户已验收前轮受控搜索的过程记录，没有认定第2问完成。本轮独立新增3600秒计算预算，搜索及前置最多2400秒，冻结后至少保留1200秒确认与重建。沿用C21—C24和共同物理/统计基准，不修改已验收原型、Q1、原题或固定资料；新候选R023—R027与批准条款编号分开。

旧C22的独立确认P={old[4]:.9f}kW、q={old[5]:.9f}kW/m²、额定工作余量−284.02146166671446kW。这些旧数据作为本轮搜索依据，不能再称为对新候选未使用过的确认数据。C21保留较小面积/较高q但功率不足的互补参照。本轮先修复可行性，再保留较精正余量基线并比较单位面积目标。

实际回读AGENTS、任务状态、记录索引、旧候选/原型/搜索阶段与对应代码接口、固定模型/统计定义、C21/C22比较与C22确认、决策与更新记录、论文规范及旧正文。没有新增或重新完整阅读Datawhale正文、优秀论文、外部资料；方法认识来源为本题已有证据、获准通用数学和代码审查。

## 2 冻结规则及实际执行

低样本为全镜数×60时点、2独立批×16；较精为4批×64，前缀分别8/32；所有场景均完整障碍集合。生成坐标在评分前保留10位小数，展开后重计N、面积，检查全部镜对和60适用域。候选间共用1900/1910各层流，按稳定位置键、标准时点、批号配对；不同层流独立，前缀不重复池化。

初始R023/R024分别为C22同族6.75m和7m方镜。R023先作较精评价，取得搜索正余量。R025减至6.65m方镜，R026仅将R023镜高减至6.70m，R027在R025基础上塔南移15m，固定场界不移。所有改动在对应评分前保存请求及队列，不由确认结果反调参数。实际完成5个低样本、2个较精候选，不把未执行的分支计入搜索。

表S1　实际全60时点候选比较（low含抽样零时启发式不是正式H02功率）

'''+table(['候选','层级','实际N','总面积m²','正式P/kW','正式q/kW·m⁻²','另存启发式P/kW','抽样零存活数','较精入场'],rows)+f'''

R024低样本P与q均低于R023，未占较精名额；R025/R026作为面积/高度对照，正式量有NA，不能称已确认失败或不可能方案。R027较精P=60165.18262226091kW、q=.4563940486765431，搜索风险余量50kW；保留功率条件下选择更高q。与R023的整批配对比较见[实际候选比较](../诊断结果/Q02-修复-v001/实际候选比较.json)，属于搜索后数值诊断，不是选择校正后的置信结论。没有全局最优证明。

## 3 程序修订、失败与并行验证

原fast-v002、物理核core-v003、参数化eval-v003、设计design-v002、hex-bands-v001、summary-v002均保持。新engine只更换本轮输出绑定并补充末段预算门禁，静态还原后与旧engine逐字一致。

1. Windows命令行JSON一次解析失败，发生在候选生成前，保留失败与耗时；entry改为从本地JSON读取。
2. run-v001误读比较阶段未提供的确认NA字段，R023光学60块已完成后评分失败；保留v001，新v002按固定13×6点量的非有限位置构造NA。不补0/1、不删对象、原分块恢复不重新积分。
3. 恢复动作约7秒不能作为完整候选成本；v003保留该动作时长并用完整分块成本作下一次预测，旧score副本保留。账本始终含首次计算与失败恢复。
4. R027串行较精实耗约788秒，后段光学耗时上升，原因没有证据确定。没有据此改损失/样本/阈值。冻结后新增按时点4worker调度，9项依赖子进程导入前后核验，独立完整镜场缓存，随机流不含调度身份。对2时点×3镜的已有4×64源流，串行/并行/旧分块的源、7事件、统计及局部功率一致。小测试含启动开销，不作为满载提速保证。

配置v001—v003及旧冻结元数据保留，v004在确认前只追加已验证调度哈希；实际设计和确认样本规则不变。每个worker处理完整时点，父进程单写预算/checkpoint；分块原子保存，按标准时间重建。按绝对截止收回子进程，预留90秒做收尾；OS清理并非硬实时保证。工作预算是整项作业墙钟，包含spawn/等待/I/O，内部worker重叠墙钟不重复相加，CPU测得下界另存。

## 4 冻结设计、独立确认与额定结果

最终设计{data['name']}：塔位{design['tower_xy']}m，宽高{design['width_m']}×{design['height_m']}m，安装高{design['installation_height_m']}m，N={design['n']}，总面积{design['total_area_m2']:.8f}m²。实际Excel读回坐标差为0。全镜对检查{geo['geometry']['pair_count_checked']}对，最小中心距{geo['geometry']['minima']['pair_distance']:.12f}m，间距正余量{geo['geometry']['minima']['pair_margin']:.12f}m，离地间隙{geo['geometry']['minima']['ground_margin']}m，场界余量{geo['geometry']['minima']['field_margin']:.12f}m。安装高6m处于允许上边界，该边界报告不是几何未决。

冻结后的1990新流：8独立批×256，全部{ans['full_combinations']}镜—时点组合、{ans['source_samples']}个独立源身份样本；128前缀只作相关诊断。旧搜索与旧C22确认样本不并入点估计。逐对象先池化原始和再成比例，完整H02汇总；未定义与零态沿原规则。

年功率{pt[4]:.12f}kW，工作U={u[4]:.12f}kW，下限{ans['rating_lower_kw']:.12f}kW，额定余量{ans['rating_lower_kw']-60000:.12f}kW；年单位面积功率{pt[5]:.12f}kW/m²，U={u[5]:.12f}。独立确认判定PASS，全部月年数值工作指标通过，必需NA={len(ans['unresolved'])}。低存活记录见[确认结论](../诊断结果/Q02-修复-v001/独立确认结论.json)，所有小于100的组合均纳入工作影响量，不将门槛视为单镜精度保证。

相较旧C22，P变化{pt[4]-old[4]:+.9f}kW，q变化{pt[5]-old[5]:+.9f}kW/m²。新设计修复额定条件，但不能掩盖相对于不可行C22的单位面积值下降；在本轮较精正余量候选中，相较更大面积R023提高q。全局最优及未探索耦合没有证明。

## 5 独立重建与交付

独立核验检查实际Excel与compact全部字段、镜号与身份映射、几何/60域、完整原始统计及H02；另独立重建point/删批/伪值/JK/前缀/raw/低存活界/U。全表工作指标与额定下限按保存数据重算。result2.xlsx是冻结Excel的字节相同副本，官方文件再次逐字段读回；另从实际Excel重建并复放3个固定组合，统计逐位一致。重放不是新增独立确认样本。

- [独立重建核验](../诊断结果/Q02-修复-v001/独立重建核验.json)
- [独立工作指标重建与导出](../诊断结果/Q02-修复-v001/独立工作指标重建.json)
- [实际Excel同源重放](../诊断结果/Q02-修复-v001/实际Excel同源重放核验.json)
- [正式result2.xlsx](../诊断结果/Q02-修复-v001/result2.xlsx)、[结果数据](../诊断结果/Q02-修复-v001/结果数据.json)、[结果初稿](Q02-第2问结果初稿-v001.md)
- [论文v002](../论文/第2问-模型建立与求解-v002.md)、[证据映射](../论文/第2问-正文证据映射-v002.md)、[修订记录](../论文/第2问-修订与排版记录-v002.md)

## 6 数值证据与局限分层

人工解析/几何单元与原型回归提供局部实现证据；同射线并行/筛选核对检查事件一致性；独立随机批次和层级差提供数值诊断；落盘重建检查可复现性和数据一致性。这些都不能量化光源近似、理想反射、N04记账、省略塔身/支架/厂房及未提供光学误差的物理偏差。分项记账不唯一、低存活局部精度、比值估计偏差及近似多指标覆盖均保留限制。

本轮没有修改物理假设、额定条件、工作目标，不添加未知工程常数，不进Q3、不联网、不操作GitHub。后续只待用户验收本轮结果和论文；修改候选或模型时，相应几何、确认、导出、图表、论文必须版本化重新核验。

## 7 运行与预算证据

计算预算主记录为[累计计算预算](../诊断结果/Q02-修复-v001/累计计算预算.json)，当前已结算{budget['used_seconds']:.6f}秒（此处为文档生成时快照，最终以账本和文件核验为准）。旧轮3114.385384300025秒另记未清零。脚本、请求JSON、四版冻结配置、候选分块、冻结清单、确认分块、失败JSONL、parallel-audit与重建结果全部归档；普通射线不全存，种子/原始和/计数足以复现，异常路径独立保存。
'''
sp=W/'阶段记录/Q02-可行性修复与独立确认-v001.md';draft=W/'阶段记录/Q02-可行性修复与独立确认-v001-过程草稿.md'
if not draft.exists():draft.write_bytes(sp.read_bytes())
sp.write_text(stage,encoding='utf-8')
print('Stage and result draft written from verified saved data; controls need final acceptance-state update.')
