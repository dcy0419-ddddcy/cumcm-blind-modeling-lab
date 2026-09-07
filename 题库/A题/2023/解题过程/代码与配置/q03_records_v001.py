"""Gated Q03 records from saved delivery artifacts; no optics or optimizer.

Call run(existing_budget). All formal files are write-once, or byte-identical
idempotent. Missing/failed gates create a separate partial attempt, never a
formal result with invented values. This script does not edit control records.
"""
from pathlib import Path
import hashlib
import json
import math
import re
import time
import traceback

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
OUT = ROOT / '工作记录/诊断结果/Q03-实施-v001'
VERSION = 'q03-records-v001'
EXPECTED_PROTOTYPE_IDS = frozenset({
    'P01_identity_and_preregistration',
    'P02_roundtrip_0', 'P02_roundtrip_1',
    'P03_old_new_0', 'P03_old_new_1', 'P03_old_new_2',
    'P03_old_new_3', 'P03_old_new_4', 'P03_old_new_5',
    'P04_heterogeneous_0_0', 'P04_heterogeneous_0_1', 'P04_heterogeneous_0_2',
    'P04_heterogeneous_1_0', 'P04_heterogeneous_1_1', 'P04_heterogeneous_1_2',
    'P05_immutable_cache_checkpoint',
    'P06_real_runner_zero_certificate_0', 'P06_real_runner_zero_certificate_1',
})


def _inside(path):
    path = Path(path).resolve()
    if not path.is_relative_to(ROOT.resolve()):
        raise ValueError('OUTSIDE_AUTHORIZED_WORKSPACE')
    return path


def _load(path):
    return json.loads(_inside(path).read_text(encoding='utf-8-sig'))


def _sha(path):
    return hashlib.sha256(_inside(path).read_bytes()).hexdigest()


def _link(path, label=None):
    path = _inside(path)
    return '[' + (label or path.name) + '](' + path.as_posix() + ')'


def _number(value):
    if value is None:
        return 'NA'
    if isinstance(value, bool):
        return '是' if value else '否'
    if isinstance(value, float):
        if not math.isfinite(value):
            raise ValueError('NONFINITE_FORMAL_DISPLAY_VALUE')
        return format(value, '.12g')
    return str(value)


def _table(header, rows):
    def cell(x):
        return _number(x).replace('|', r'\|').replace('\n', ' ')
    return '\n'.join(['| ' + ' | '.join(map(cell, header)) + ' |',
                      '| ' + ' | '.join(['---'] * len(header)) + ' |'] +
                     ['| ' + ' | '.join(map(cell, row)) + ' |' for row in rows])


def _matrix(value, rows, cols, nonnegative=False):
    return (isinstance(value, list) and len(value) == rows and
            all(isinstance(row, list) and len(row) == cols and
                all(isinstance(x, (int, float)) and not isinstance(x, bool) and
                    math.isfinite(x) and (not nonnegative or x >= 0) for x in row)
                for row in value))


def _write_all(contents):
    """Check the complete output set before writing any missing formal file."""
    encoded = {_inside(p): (s.rstrip() + '\n').encode('utf-8') for p, s in contents.items()}
    for path, data in encoded.items():
        if path.exists() and path.read_bytes() != data:
            raise FileExistsError('REFUSE_DIFFERENT_EXISTING_RECORD: ' + str(path))
    for path, data in encoded.items():
        if not path.exists():
            path.parent.mkdir(parents=True, exist_ok=True)
            with path.open('xb') as handle:
                handle.write(data)
    return [{'path': str(p), 'sha256': _sha(p), 'bytes': len(data)} for p, data in encoded.items()]


COMMON_MODEL = r"""## 数学口径与接口限制

G31采用全部镜对的平面中心间距及逐镜全俯仰严格净空：

\[
D_{ij}\ge\max(w_i,w_j)+5,\qquad z_i>h_i/2.
\]

题给宽高范围为2—8米，安装高度范围为2—6米；中心场界和随塔禁布区按既有批准基准。固定R027塔位、2981面镜及平面镜位、6个确定性组，以及逐镜宽不小于高，是本轮Q3-A搜索限制，不写成第3问原始条件，也不自动扩展到Q3-B／Q3-C。

须区分四种统计对象：主表按镜数平均的四项效率；辅助按实际面积加权的四项效率；初始、存活、净接收三层能量总量构成的三个比值；以及实际总功率除以实际总面积的原目标。设实际面积为\(A_i=w_i h_i\)，则

\[
\eta_{N,t}=\frac1N\sum_i\eta_{it},\qquad
\eta_{A,t}=\frac{\sum_i A_i\eta_{it}}{\sum_i A_i},\qquad
P_t=\operatorname{DNI}_t\sum_i A_i\eta_{\mathrm{opt},it},\qquad
q=\frac{\frac1{60}\sum_tP_t}{\sum_iA_i}.
\]

每月5个规定时点、全年60时点等权。这不是连续全年发电量。不能将主表镜均效率乘总面积计算异面积功率，也不能将各因子分别平均后相乘。三层能量已包含反射率而尚未乘大气透射；各能量比只检查自身分子、分母定义及合计分母为正，不能把其误称为包含全部大气损失的最终效率。

旧光学核保持有限矩形、理想反射和有限圆柱接收几何；逐镜宽高、安装高实际进入三维中心、法向、包围半径、有限镜面采样、传播距离及缓存。完整障碍集合保留。N04继续作为未接收射线的有限遮挡终点约定，分别约束联合阴影遮挡与条件截断的分项解释；它不是题面唯一指定的物理分解，不以分项变化偷换净接收能量。

主表四效率的固定总体NA严格传播；几何证明确实为零、有限抽样零、条件比值未定义及数值边界未知分别处理，不能补0、补1或删镜。汇总真零证书必须有当前场景身份、镜索引及可信证明源；本轮独立重建实现如遇不支持的真零证书会显式失败，不默认为普通估计。原型中的人工真零通过不表示任意真实场景的证书均已独立验证。

最终完整8批×256仅合并最大样本层，\(n_{\mathrm{tot}}=8\times256\)；128样本为同批相关前缀，不能再次并入分母。确认数值工作量为

\[
U_Q=\max\{t_{7,0.975}\operatorname{SE}_{\mathrm{JK}}(Q),
|Q-Q_{\mathrm{prefix}}|,|Q-Q_{\mathrm{raw}}|\}+L_Q.
\]

整批删批Jackknife重新计算比值和聚合。低存活按合并存活数小于100筛查，\(L_Q\)为相应对象的全范围影响量；功率及面积辅助使用实际逐镜面积，镜均项使用镜数权重。100是管理性筛查值，不是单镜精度保证。主表效率绝对工作目标0.001，功率和单位面积功率相对工作目标0.5%；辅助面积效率工作量单独保存，不增加必需主表门禁。

额定判据与改善判据分开：\(\widehat{\overline P}-U_{\overline P}\ge60000\ \mathrm{kW}\)；候选与新同流基线的\(\Delta q>U_{\Delta q}\)。配对工作量使用整批配对删批差值、配对前缀与原始积分差，再加两设计年单位面积低存活影响量之和。近似逐项数值工作量不是严格置信区间、同时覆盖或物理误差界。

反射率0.92、4.65毫弧度参考光锥及H01—H04、N01—N05保持批准定义。光源分布、参考面、单次理想反射、有效接收边界、塔身和支架省略、镜面与跟踪误差及接收器热损失等物理限制没有通过增加样本消除。当前结论仅属于有限固定布局分组搜索及既定模型，不证明全局最优。
"""


def run(budget):
    """Read completed artifacts, check gates, write four records; no own Budget."""
    import q03_common_v001 as io
    started = time.perf_counter()
    budget.guard(15)
    attempt = OUT / 'records' / ('attempt-%s' % time.time_ns())
    report = {'version': VERSION, 'all_pass': False, 'formal_records': False,
              'scope': 'saved-artifact record generation; no optical rays, geometry program, optimization or new estimator',
              'checks': {}, 'source_sha256': {}, 'outputs': []}
    def check(name, ok):
        report['checks'][name] = bool(ok)
        if not ok:
            raise ValueError('RECORD_GATE_FAILED: ' + name)
    def read(rel):
        path = _inside(OUT / rel)
        budget.guard(10)
        data = _load(path)
        report['source_sha256'][rel] = _sha(path)
        return data
    try:
        manifest = read('delivery/report.json')
        check('manifest_success', manifest['status'] == 'CONFIRMED_IMPROVEMENT' and manifest['global_optimum_claim'] is False)
        required_paths = {'result_data':'delivery/结果数据-v001.json',
                          'comparison_report':'delivery/paired-comparison-v001.json',
                          'rebuild_report':'delivery/独立重建核验-v001.json',
                          'search_trace':'scores.jsonl','excel_file':'delivery/result3.xlsx'}
        for field, expected in required_paths.items():
            check('manifest_path:'+field, manifest[field].replace('\\','/') == expected)
        for rel, digest in manifest['sha256'].items():
            budget.guard(10)
            check('manifest_sha:'+rel, _sha(OUT / rel) == digest)
        for field in (*required_paths,'design_file','candidate_confirmation_summary','baseline_confirmation_summary'):
            check('manifest_covers:'+field, manifest[field] in manifest['sha256'])
        data = read('delivery/结果数据-v001.json')
        paired = read('delivery/paired-comparison-v001.json')
        audit = read('delivery/独立重建核验-v001.json')
        fine = read('comparison-fine-v001.json')
        freeze = read('最终候选与确认冻结-v001.json')
        ledger = read('累计计算预算.json')
        proto = read('prototype/report-v001.json')
        groups = read('groups-v001.json')
        scores_path = OUT/'scores.jsonl'
        scores = [json.loads(s) for s in scores_path.read_text(encoding='utf-8-sig').splitlines() if s.strip()]
        report['source_sha256']['scores.jsonl'] = _sha(scores_path)
        name = freeze['candidate']
        check('selected_identity', name == manifest['selected_design'] == data['selected_design'] == paired['candidate'])
        check('independent_gates', audit['all_pass'] is True and audit['formal_ready'] is True and audit['improvement_supported'] is True)
        check('independent_each_check', bool(audit['checks']) and all(c['passed'] is True for c in audit['checks'].values()))
        check('audit_current_freeze', audit['freeze_sha256']==report['source_sha256']['最终候选与确认冻结-v001.json'])
        check('paired_gates', paired['improvement_supported'] is True and paired['paired_identity_valid'] is True and paired['baseline']=='Q3R000')
        check('point_dimensions', _matrix(data['point'],13,6) and _matrix(data['work_indicator'],13,6,True))
        check('annual_consistency', data['annual_point_internal_units']==data['point'][-1] and data['annual_work_indicator_internal_units']==data['work_indicator'][-1])
        check('rating_and_improvement', data['rating_margin_kw']>=0 and paired['delta_q_kw_m2']>paired['work_indicator_delta_q'])
        check('population_groups', data['N']==2981 and len(data['groups'])==6 and sum(g['n']for g in data['groups'])==2981 and groups['nonempty_group_count']==6)
        plan=freeze['planned_confirmation']
        check('frozen_sampling', plan['B']==8 and plan['n']==256 and plan['levels']==[128,256] and plan['max_n']==256 and plan['namespace']==3190 and plan['root_seed']==2026090506)
        check('frozen_geometry', freeze['readback_geometry']['accepted'] is True and freeze['fixed_xy_tower_N_identity'] is True)
        lows=[s for s in scores if s['tag']=='low']; fines=[s for s in scores if s['tag']=='fine']
        check('actual_search_count', len(lows)==len({s['name']for s in lows})==14 and len(fines)==len({s['name']for s in fines})==4 and len(fine)==4)
        check('full_field_search', all(s['score']['actual_time_count']==60 and s['score']['actual_mirror_count']==2981 for s in lows+fines))
        prototype_ids=[c['name'] for c in proto['checks']]
        check('prototype_exact_ids', len(prototype_ids)==len(set(prototype_ids)) and
              set(prototype_ids)==EXPECTED_PROTOTYPE_IDS)
        check('prototype', proto['all_pass'] is True and all(c['passed'] is True for c in proto['checks']) and proto['compatibility_combinations_completed']==6 and proto['new_design_combinations_completed']==6)
        report['prototype_expected_ids']=sorted(EXPECTED_PROTOTYPE_IDS)
        report['prototype_actual_check_count']=len(prototype_ids)
        check('tables_schema', len(data['tables']['table1']['rows'])==12 and len(data['tables']['table2']['rows'])==1 and len(data['tables']['table3']['rows'])==1)
        for key, cols in [('table1',6),('table2',6),('table3',5)]:
            check('table_columns:'+key, len(data['tables'][key]['header'])==cols and all(len(r)==cols for r in data['tables'][key]['rows']))
        check('budget_under_limit_at_generation', float(ledger['used_seconds'])<=float(ledger['limit_seconds'])==5400.)
        decision_path=ROOT/'工作记录/决策记录.md'
        decision_text=decision_path.read_text(encoding='utf-8-sig')
        match=re.search(r'^## D046\b.*?(?=^## D\d+\b|\Z)',decision_text,re.M|re.S)
        check('decision_D046_present', match is not None)
        decision=match.group(0).strip()
        check('selection_matches_decision', freeze['search_parent'] in decision and name in decision)
        report['source_sha256']['工作记录/决策记录.md']=_sha(decision_path)
        candidate=audit['reconstructed'][name]; baseline=audit['reconstructed']['Q3R000']
        for key, expected in [('point',candidate['point']),('work_indicator',candidate['U'])]:
            check('result_vs_independent:'+key, all(math.isclose(a,b,rel_tol=2e-9,abs_tol=2e-9)
                  for row1,row2 in zip(data[key],expected) for a,b in zip(row1,row2)))
        point=data['point'][-1]; work=data['work_indicator'][-1]
        check('table1_point_mapping', all(r[1:5]==data['point'][j][:4] and r[5]==data['point'][j][5]
                                         for j,r in enumerate(data['tables']['table1']['rows'])))
        check('table2_point_mapping', data['tables']['table2']['rows'][0]==[*point[:4],point[4]/1000,point[5]])
        check('table3_identity', data['tables']['table3']['rows'][0][3:]==[data['N'],data['total_area']])
        gtable=_table(['组号','镜数','宽／m','高／m','安装高／m'],[[g['group'],g['n'],g['width'],g['height'],g['z']]for g in data['groups']])
        lowtable=_table(['设计','低样本P评分／kW','低样本q评分','抽样零存活计数','抽样零接收计数','未知计数'],
            [[s['name'],s['score']['P_score_kw'],s['score']['q_score_kw_m2'],s['score']['zero_survivor'],s['score']['zero_capture'],s['score']['unknown']]for s in lows])
        finetable=_table(['设计','较精P点／kW','较精q点','与基线q差','配对搜索SE','搜索余量／kW'],
            [[s['name'],s['annual_formal_point'][4],s['annual_formal_point'][5],s['delta_q'],s['paired_search_se'],s['power_search_margin']]for s in fine])
        confirmed=_table(['量','点量或工作指标','含义'],[
            ['候选年平均总功率／kW',point[4],'全60时点等权，实际面积求和'],
            ['总功率工作量／kW',work[4],'数值工作量，不含物理误差'],
            ['额定工作余量／kW',data['rating_margin_kw'],'扣除工作量及60000后'],
            ['候选单位面积功率',point[5],'kW/m²'],['新同流基线单位面积功率',paired['baseline_q_kw_m2'],'kW/m²'],
            ['配对单位面积差',paired['delta_q_kw_m2'],'kW/m²'],['配对差工作量',paired['work_indicator_delta_q'],'kW/m²'],
            ['配对差扣工作量',paired['difference_minus_work_indicator'],'kW/m²'],
            ['相对单位面积改善',paired['relative_q_difference'],'比例，不是百分数']])
        lowrows=[]
        for nm,item in [(name,candidate),('Q3R000',baseline)]:
            cases=item['low_survival_cases']
            lowrows.append([nm,len(cases),min((c['survive']for c in cases),default='无筛查对象'),item['low'][-1][4],item['low'][-1][5]])
        lowbound=_table(['设计','低存活组合数','最小存活数','年功率影响量／kW','年单位面积影响量'],lowrows)
        tables='\n\n'.join('### 表%d\n\n%s'%(i,_table(data['tables']['table%d'%i]['header'],data['tables']['table%d'%i]['rows']))for i in (1,2,3))
        aux=data['area_weighted'];energy=data['energy_total_ratios']
        auxtable=_table(['统计口径','光学','余弦','阴影遮挡','截断'],[
            ['主表镜均',*point[:4]],['辅助面积加权',*aux['point'][-1]]])
        energytable=_table(['能量比','年合计分子／分母之比'],list(zip(energy['labels'],energy['values'][-1])))
        statlinks='\n'.join('- '+_link(OUT/manifest[k])for k in ['design_file','candidate_confirmation_summary','baseline_confirmation_summary','comparison_report','rebuild_report','excel_file','result_data'])
        budgettext=('记录生成时账本已计 '+_number(ledger['used_seconds'])+' 秒，限额5400秒；本值是生成时快照，不是最终结算。'
            '计算包含测试、搜索、失败、进程启动与等待、读写和重建；4个工作进程重叠墙钟只由父作业计一次，CPU另记。'
            '包装器未逐项实测的早期启动及收尾开销须按最终保守扣款单独说明，不能改称实测。'
            '本脚本自身读写由传入预算接续；最终文件核验、普通文字与排版状态仍由主线程完成后记录。')
        history=('首次Excel冻结在身份表读回处将只读工作表的values生成器误作函数，产生TypeError，确认射线尚未发射。'
            '修订为迭代values属性后复用本次未确认工作簿，完整读回；冻结记录实际字段变化数为 '+str(len(freeze['readback_changes']))+'。'
            '失败日志、FAILED预算记录和修订前新源保留，不把该失败写成错误数值确认。'
            '另有两份新源因相对补丁路径暂写至授权目录外的路径事件，按已存专项记录披露；没有将其描述为未发生。')
        history+='\n\n'+_link(OUT/'确认前接口修订-v001.md')+'；'+_link(OUT/'failures.jsonl')+'；'+_link(OUT/'边界事件记录-v001.md')
        history+='\n\n原型报告的实际检查为18项：身份1、读回2、旧新6、异参数6、缓存1、人工零2。此前文字及记录脚本误写19，原依据是人工合计失准，不是缺失了测试。首次记录生成因此在门禁处停止，仅保存partial；修订为核对18个明确ID集合、拒绝重复或缺项，并逐项要求passed。原始原型报告和数值不变。失败记录：'+_link(OUT/'records/attempt-1788617442352851300/report.json')+'；修改前记录源：'+_link(OUT/'records/q03_records_v001-before-prototype-count-fix.py')+'。'
        history+='\n\n图表v001因缺少matplotlib未生成，未联网安装；实际使用 '+_link(HERE/'q03_figures_v002.py')+' 的ReportLab绘制及Poppler渲染，图片位置不变，来源凭据为 '+_link(OUT/'delivery/图表生成核验-v001.json')+'。图表生成凭据不替代最终页面核验。'
        intro=('已完成本轮批准的固定R027镜位、6组Q3-A搜索及冻结后的新数据确认。'
            '交付manifest、独立重建、额定与配对改善门禁已通过；阶段待最终用户验收，管理员归档未确认。'
            '结论仅为已探索范围内获得经数值工作判据支持的改进，不是全局最优或工程物理保证。')
        stages=ROOT/'工作记录/阶段记录';paper=ROOT/'工作记录/论文'
        stage_path=stages/'Q03-分组搜索与独立确认-v001.md'
        result_path=stages/'Q03-第3问结果初稿-v001.md'
        map_path=paper/'第3问-正文证据映射-v001.md'
        repro_path=OUT/'复现说明-v001.md'
        stage='\n\n'.join(['# 第3问分组搜索与独立确认 v001',intro,
            '## 授权、原型与实际搜索范围\n\n'+_link(OUT/'本轮用户授权.md')+'批准G31—G34及新增5400秒。实际14个全场低样本候选（含基线）、4个全场较精比较；均为2981镜×60时点、完整障碍。低样本2批×16、8前缀，较精4批×64、32前缀；命名空间分别3100、3110。确认预留1800秒，未进入Q3-B／C。原型18项通过：6旧新组合每组合2批×64，2诊断共6新组合每组合2批×256，另2人工零夹具；不扩写为原型全年验证。\n\n'+_link(stages/'Q03-异尺寸原型验证-v001.md'),
            '## 全场低样本搜索记录\n\n'+lowtable+'\n\n这些是启发式评分；零计数按原报告保存，正式NA没有被评分零替换。每次修改包括未改镜的遮挡影响，未仅累加被改组响应。',
            '## 较精比较与选择\n\n'+finetable+'\n\n以下原样摘录选择时的D046，不以独立确认数据改写选择理由。\n\n'+decision,
            '## 实际冻结设计\n\n'+gtable+'\n\n镜数2981，总面积 '+_number(data['total_area'])+' 平方米。全部镜对、中心边界、禁布区与严格净空按实际Excel读回参数核验。\n\n'+_link(OUT/'最终候选与确认冻结-v001.json'),
            '## 新独立确认与基线配对\n\n冻结后根种子2026090506、命名空间3190，候选和Q3R000各自完整8批×256、128相关前缀，共用稳定身份／标准时点／批次对应的底层均匀数。确认数据未用于当前设计选择；旧R027确认仅为搜索先验，不冒充本次新比较。\n\n'+confirmed,
            '## 低存活影响及状态\n\n'+lowbound+'\n\n未裁掉上述组合；实际面积进入其功率及面积辅助影响界。通过交付门禁表示必需主表项按冻结工作目标通过，不表示每个低存活镜已达到相同局部精度。',COMMON_MODEL,
            '## 修订、失败与预算\n\n'+history+'\n\n'+budgettext,
            '## 交付与剩余状态\n\n'+statlinks+'\n\n正式结果、正文、图表和页面最终一致性由主线程接续核查；本记录不提前登记论文排版PASS或用户验收。'])
        initial='\n\n'.join(['# 第3问结果初稿 v001',intro,'## 冻结设计\n\n'+gtable,
            '## 题目表1—3\n\n以下直接引用门禁通过的结果JSON；显示值保留12位有效数字，完整精度保留在源数据及Excel中。表3统一尺寸和安装高度栏按题面允许留空，逐镜值与组值另存；不能据空栏认为数据缺失。\n\n'+tables,
            '## 额定与改进证据\n\n'+confirmed,'## 面积辅助和能量总量比\n\n'+auxtable+'\n\n'+energytable,
            '## 低存活记录\n\n'+lowbound,COMMON_MODEL,'## 原始证据与状态\n\n'+statlinks+'\n\n'+budgettext])
        targets=[('正式正文',paper/'第3问-模型建立与求解-v001.md'),('LaTeX源',paper/'LaTeX/第3问-模型建立与求解-v001.tex'),
                 ('PDF',paper/'LaTeX/第3问-模型建立与求解-v001.pdf'),('镜高分组图',paper/'图表/Q03-v001/Q03-镜高分组.png'),
                 ('月度单位面积功率图',paper/'图表/Q03-v001/Q03-月度单位面积功率.png'),('图表来源报告',OUT/'delivery/图表生成核验-v001.json')]
        targettable=_table(['目标','路径','生成时文件状态'],[[label,_link(path),'已存在；内容及页面待最终核验' if path.is_file() else '尚未生成；链接待文件核验']for label,path in targets])
        mapping=_table(['正文主题／表图','首要证据','映射含义'],[
            ['问题、约束与批准',_link(OUT/'本轮用户授权.md'),'G31—G34及本轮范围；固定镜位/分组是搜索限制'],
            ['分组几何与可用宽度',_link(OUT/'groups-v001.json'),'6组、实际镜数、逐镜及组内宽度上限'],
            ['逐镜接口与原型',_link(OUT/'prototype/report-v001.json'),'18个明确检查ID实际通过，6旧+6新及2人工零'],
            ['14低样本与4较精',_link(OUT/'scores.jsonl')+'；'+_link(OUT/'comparison-fine-v001.json'),'完整场景，同口径层内比较；不能把启发式评分写成确认'],
            ['选择Q3R013',_link(decision_path)+'的D046','q优先与较窄正余量风险；额外30kW是软偏好'],
            ['冻结精度与确认配置',_link(OUT/'最终候选与确认冻结-v001.json'),'Q3F013，固定8×256；设计/Excel/代码/规则绑定'],
            ['表1—3、面积辅助',_link(OUT/'delivery/结果数据-v001.json'),'直接引用tables、area_weighted、energy_total_ratios'],
            ['额定、误差及低存活',_link(OUT/'delivery/独立重建核验-v001.json'),'独立点量/U/状态/面积及几何、Excel核验'],
            ['与R027同口径改善',_link(OUT/'delivery/paired-comparison-v001.json'),'新的3190配对批次差与工作量'],
            ['镜高分组图',_link(OUT/manifest['design_file']),'从实际冻结逐镜字段绘制'],
            ['月度单位面积功率图',_link(OUT/manifest['candidate_confirmation_summary'])+'；'+_link(OUT/manifest['baseline_confirmation_summary']),'候选和基线新确认月值，不采用搜索评分'],
            ['限制、失败、预算',_link(stage_path)+'；'+_link(OUT/'边界事件记录-v001.md'),'N04/物理限制、Excel失败及修订、实际账本和保守附加分开']])
        evidence='\n\n'.join(['# 第3问正文证据映射 v001',
            '数值来源门禁已通过；本文件仅建立主题到证据的映射。正文、公式编号、图表编号及PDF实际页面仍由主线程最终回读，以下链接存在不等于排版或内容PASS。',mapping,
            '## 计划交付文件状态\n\n'+targettable,'## 精度与结论边界\n\n'+COMMON_MODEL,
            '## 生成来源\n\n记录生成器 '+_link(Path(__file__))+'；来源SHA和门禁详见 '+_link(attempt/'report.json')+'。未对正文/TeX/PDF/图表提前填写PASS。'])
        sources=_table(['输入','SHA-256'],[[k,v]for k,v in report['source_sha256'].items()])
        repro='\n\n'.join(['# Q03复现说明 v001',
            '唯一工作区为 '+str(ROOT)+'。保持离线，不读取其他目录题解或Git历史。正式源与结果已冻结，复现须有剩余或新增计算授权，并保留旧文件。',
            '## 入口与执行顺序\n\n'+_table(['阶段','入口','语义'],[
                ['原型','q03_prototype_v001.run(existing_budget)','生成新attempt；不得覆盖report-v001'],
                ['搜索','q03_job_v001.ps1 score specs/设计-low或fine.json','主入口实际完整镜场/60时点；逐份spec和launch-binding记录'],
                ['确认','q03_job_v001.ps1 confirm specs/设计-confirmation.json','先核最终冻结；固定候选与基线的3190流，禁止调参'],
                ['重建与交付','q03_job_v001.ps1 deliver','独立读已存统计和实际Excel，门禁通过才生成manifest/题表'],
                ['本记录','q03_records_v001.run(existing_budget)','读取已完成交付，检查manifest SHA及门禁；不产生射线']]),
            '所有命令由主线程在唯一工作区内显式指定工作目录执行。上述为历史入口说明，不建议直接重跑并覆盖已有顶层报告。更换模型或正式设计必须使用后续版本及新的冻结记录；同一目录仅可在完全相同绑定下恢复未完成时点，不能改变样本数后复用同tag。新确认流不允许返回当前搜索；失败若重新搜索须记录原确认数据已被使用。',
            '## 种子与总体\n\n根种子2026090506；低样本3100、较精3110、独立确认3190。标准12×5时点、全部2981镜及完整障碍；批次独立，跨设计按稳定位置键配对。配置与源码版本详见冻结记录及每个评价目录的binding/launch-binding。',
            '## 预算和失败接续\n\n'+budgettext+'\n\n'+history,
            '## 来源清单\n\n'+sources,'## 已生成文件\n\n'+_link(stage_path)+'；'+_link(result_path)+'；'+_link(map_path),
            '## 本记录重建的边界\n\n本脚本只做已存结果的一致性门禁、排版与追溯。正式四文件如已存在且内容不同则拒绝覆盖；缺少交付证据或门禁失败，输出到独立partial目录，不生成成功表值。该操作不替代独立光学核验，也不自行登记用户验收。'])
        contents={stage_path:stage,result_path:initial,map_path:evidence,repro_path:repro}
        budget.guard(10)
        report['outputs']=_write_all(contents)
        report.update(all_pass=True,formal_records=True,status='GENERATED_PENDING_FINAL_FILE_AND_PAGE_REVIEW')
    except Exception:
        report['failure']=traceback.format_exc()
        partial=attempt/'partial'
        body=('# 第3问记录生成未完成\n\n状态：未完成，未生成正式阶段数字、表1—3或改善结论。\n\n'
              '已执行的门禁及失败信息见同目录上级report.json；完整交付manifest或门禁不足不能用现有搜索评分代替。'
              '原记录、冻结文件、确认分块及失败历史保留。待主线程处理具体缺口后，以新attempt和新版本接续。\n')
        report['partial_outputs']=_write_all({partial/name:body for name in [
            'Q03-分组搜索与独立确认-v001.md','Q03-第3问结果初稿-v001.md','第3问-正文证据映射-v001.md','复现说明-v001.md']})
        report['status']='PARTIAL_ONLY'
    finally:
        report['elapsed_seconds']=time.perf_counter()-started
        report['implementation_sha256']=_sha(Path(__file__))
        io.save(attempt/'report.json',report)
        budget.tick()
    return report


if __name__ == '__main__':
    raise SystemExit('Call run(existing_budget) from the authorized parent; no automatic computation budget is created.')
