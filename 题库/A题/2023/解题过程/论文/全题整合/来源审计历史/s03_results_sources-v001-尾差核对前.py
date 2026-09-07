"""S03 read-only result authority and workbook field audit; no model imports/rays."""
from pathlib import Path
from datetime import datetime
from collections import Counter
import json, hashlib, math, csv, os, sys
import openpyxl

ROOT=Path(r'C:\Users\admin\OneDrive\Desktop\26国赛-单题盲解区\A-P8C3').resolve()
OUT=ROOT/'工作记录/论文/全题整合'
P1='工作记录/诊断结果/Q01-全场-v001'
P2='工作记录/诊断结果/Q02-修复-v001'
P3='工作记录/诊断结果/Q03-实施-v001'
CHECKS={}

def safe(rel):
    p=(ROOT/rel).resolve()
    if not p.is_relative_to(ROOT):raise ValueError('OUTSIDE_TASK')
    return p
def read(rel):return json.loads(safe(rel).read_text(encoding='utf-8-sig'))
def sha(rel):return hashlib.sha256(safe(rel).read_bytes()).hexdigest()
def check(k,value,evidence=None):
    CHECKS[k]={'passed':bool(value),'evidence':evidence}
    if not value:raise AssertionError(k)
def near(a,b,atol=1e-10,rtol=2e-14):return math.isclose(float(a),float(b),abs_tol=atol,rel_tol=rtol)
def same_matrix(a,b):return len(a)==len(b) and all(len(x)==len(y) and all(near(v,w) for v,w in zip(x,y)) for x,y in zip(a,b))
def workbook(rel):
    w=openpyxl.load_workbook(safe(rel),read_only=True,data_only=True)
    data={s.title:list(s.values) for s in w};w.close();return data
def source_paths(primary,additional):
    paths={'confirmation_summary':primary,**additional}
    return paths,{k:sha(v) for k,v in paths.items() if safe(v).is_file()}
def annual(s,u,area,rated):
    p=s['point'][-1]
    r={'point':p,'U':u[-1],'power_kw':p[4],'power_mw':p[4]/1000,'q_kw_m2':p[5],
       'U_power_kw':u[-1][4],'U_q_kw_m2':u[-1][5]}
    check('P_equals_Aq_'+str(area),near(p[4],area*p[5],1e-8))
    if rated:r.update(rating_lower_kw=p[4]-u[-1][4],rating_margin_kw=p[4]-u[-1][4]-60000)
    else:r.update(rating_lower_kw=None,rating_margin_kw=None)
    return r
def entry(did,s,u,N,area,tower,dims,paths,sampling,rated=True):
    pp,ss=source_paths(paths.pop('confirmation_summary'),paths)
    check(did+'_matrix_shape',len(s['point'])==13 and all(len(row)==6 for row in s['point']))
    check(did+'_annual_equals_month_mean',all(near(s['point'][-1][j],sum(row[j] for row in s['point'][:12])/12,1e-8) for j in range(6)))
    return dict(design_id=did,N=N,tower_xy_m=tower,total_area_m2=area,dimensions=dims,
      paths=pp,sha256=ss,annual=annual(s,u,area,rated),rows=s['rows'],point=s['point'],U=u,
      sampling=sampling,accepted_source='用户已验收的该阶段有效确认结果；S03只读取及交叉核对，未重跑光学',
      quality={k:s.get(k) for k in ['formal_decision','formal_ready','all_table_items_precision_met','work_targets_all_met','numeric_validation_pass','required_table_na_locations','pooled_state_counts','coverage','numeric_checks'] if k in s})

def run():
    OUT.mkdir(parents=True,exist_ok=True)
    for name in ['结果与来源-v001.json','结果与来源表-v001.md']:
        if (OUT/name).exists():raise FileExistsError(OUT/name)
    s1=read(P1+'/汇总与数值核验-v001.json');cfg1=read('工作记录/诊断代码/Q01-全场配置-v001.json')
    map1=read(P1+'/输入映射与时间.json');low1=read('工作记录/诊断结果/Q01-论文收尾-v001/低存活全量核查-v002.json')
    check('Q1_config_binding',s1['config_sha256']==sha('工作记录/诊断代码/Q01-全场配置-v001.json'))
    check('Q1_original_fixed_population',len(map1['rows'])==1745 and len(map1['times'])==60 and len({x['mirror_id'] for x in map1['rows']})==1745 and all(x['excel_row']==x['mirror_id']+1 for x in map1['rows']))
    q1=entry('Q1-fixed',s1,s1['work_uncertainty_indicator'],len(map1['rows']),map1['total_area_m2'],[0.0,0.0],
      {'uniform_width_m':6.0,'uniform_height_m':6.0,'uniform_installation_height_m':4.0,'source':'第1问有效正文§1、输入映射及q01_core_v003.load_centers，不通过效率反推尺寸'},
      {'confirmation_summary':P1+'/汇总与数值核验-v001.json','configuration':'工作记录/诊断代码/Q01-全场配置-v001.json','input_mapping':P1+'/输入映射与时间.json','statistics_directory':P1+'/confirmation','saved_rebuild':P1+'/汇总重建一致性.json','low_survival_supplement':'工作记录/诊断结果/Q01-论文收尾-v001/低存活全量核查-v002.json','accepted_result':'工作记录/阶段记录/Q01-第1问结果初稿-v001.md','paper':'工作记录/论文/第1问-模型建立与求解-v001.md','evidence_map':'工作记录/论文/第1问-正文证据映射-v001.md'},
      {'rng':cfg1['rng'],'root_seed':cfg1['seed_root'],'namespace':cfg1['ensembles']['confirmation']['code'],'B':8,'n':256,'levels':[128,256],'seed_words':cfg1['seed_words'],'initial_reference':cfg1['ensembles']['initial'],'combinations':1745*60,'unique_confirmation_samples':cfg1['total_unique_final_rays'],'prefix_relation':'128 is correlated prefix of256; not counted twice; separate128 initial group excluded from final point'},False)
    q1['uncertainty_definition']=cfg1['work_indicator']
    q1['retrospective_low_survival']={k:low1[k] for k in ['scope','count_below100','minimum','cases','effect_diameter_bound','supplementary_U_plus_bound','supports_original_targets','max_efficiency_U_plus_bound','max_power_relative_U_plus_bound','limits']}
    check('Q1_supplement_frozenU_unchanged',same_matrix(low1['frozen_U'],s1['work_uncertainty_indicator']))

    s2=read(P2+'/frozen/confirmation/summary.json');r2=read(P2+'/结果数据.json');b2=read(P2+'/frozen/confirmation/binding.json')
    meta2=read(P2+'/frozen/design.metadata.json');bun2=read(P2+'/frozen/design.bundle.json')
    with safe(P2+'/frozen/'+bun2['mirrors_file']).open(encoding='utf-8-sig',newline='') as f:csv2=list(csv.DictReader(f))
    check('Q2_metadata_bundle_sha',bun2['metadata_sha256']==sha(P2+'/frozen/'+bun2['metadata_file']))
    check('Q2_mirrors_bundle_sha',bun2['mirrors_sha256']==sha(P2+'/frozen/'+bun2['mirrors_file']))
    check('Q2_result_summary_sha',r2['sources']['confirmation_summary_sha256']==sha(P2+'/frozen/confirmation/summary.json'))
    check('Q2_result_workbook_sha',r2['sources']['result2_excel_sha256']==sha(P2+'/result2.xlsx'))
    check('Q2_result_values',r2['annual_point_internal_units']==s2['point'][-1] and r2['annual_work_indicator_internal_units']==s2['conservative_work_indicator'][-1])
    x2=workbook(P2+'/result2.xlsx');f2=x2['镜场设计'][1:];small2=x2['逐镜设计'][1:]
    check('Q2_excel_row_count',len(f2)==len(csv2)==meta2['declared_n']==2981)
    check('Q2_excel_all_fields',all(list(row)==[meta2['tower_xy'][0],meta2['tower_xy'][1],i+1,meta2['width'],meta2['height'],float(c['x']),float(c['y']),meta2['installation_height']] for i,(row,c) in enumerate(zip(f2,csv2))))
    check('Q2_auxiliary_sheet_all_fields',all(list(row)==[i+1,float(c['x']),float(c['y']),meta2['installation_height'],meta2['width'],meta2['height']] for i,(row,c) in enumerate(zip(small2,csv2))))
    area2=math.fsum(row[3]*row[4] for row in f2)
    check('Q2_excel_area',near(area2,r2['actual_design']['total_area_m2'],1e-8))
    samp2={k:b2[k] for k in ['rng','root_seed','namespace','B','n','levels']};samp2.update(combinations=len(f2)*60,unique_confirmation_samples=len(f2)*60*b2['B']*b2['n'],seed_identity='stable position_key / standard time index / namespace / batch; see binding.json')
    q2=entry('R027-Q2-original',s2,s2['conservative_work_indicator'],len(f2),r2['actual_design']['total_area_m2'],meta2['tower_xy'],
      {'uniform_width_m':meta2['width'],'uniform_height_m':meta2['height'],'uniform_installation_height_m':meta2['installation_height']},
      {'confirmation_summary':P2+'/frozen/confirmation/summary.json','result_data':P2+'/结果数据.json','confirmation_binding':P2+'/frozen/confirmation/binding.json','design_bundle':P2+'/frozen/design.bundle.json','design_metadata':P2+'/frozen/design.metadata.json','mirror_rows':P2+'/frozen/design.mirrors.csv','formal_excel':P2+'/result2.xlsx','statistics_directory':P2+'/frozen/confirmation','freeze':P2+'/最终拟提交候选冻结.json','saved_rebuild':P2+'/独立重建核验.json','saved_U_rebuild':P2+'/独立工作指标重建.json','accepted_result':'工作记录/阶段记录/Q02-第2问结果初稿-v001.md','paper':'工作记录/论文/第2问-模型建立与求解-v002.md','evidence_map':'工作记录/论文/第2问-正文证据映射-v002.md'},samp2)
    q2['uncertainty_definition']=s2['work_indicator_definition'];q2['low_survival']=s2['low_survival']
    q2['tables']=r2['tables']

    r3=read(P3+'/delivery/结果数据-v001.json');s3=read(P3+'/candidates/Q3F013/confirmation/summary.json');b3=read(P3+'/candidates/Q3F013/confirmation/binding.json')
    d3=read(P3+'/candidates/Q3F013/design.json');d0=read(P3+'/candidates/Q3R000/design.json');s0=read(P3+'/candidates/Q3R000/confirmation/summary.json');b0=read(P3+'/candidates/Q3R000/confirmation/binding.json')
    fr3=read(P3+'/最终候选与确认冻结-v001.json');cmp=read(P3+'/delivery/paired-comparison-v001.json');ver3=read(P3+'/delivery/独立重建核验-v001.json')
    x3=workbook(P3+'/delivery/result3.xlsx');f3=x3['完整清单'][1:];ident3=x3['身份映射'][1:]
    check('Q3_frozen_design_file_sha',b3['design_file_sha256']==sha(P3+'/candidates/Q3F013/design.json'))
    check('Q3_actual_export_sha',fr3['xlsx_sha256']==sha(P3+'/delivery/result3.xlsx'))
    check('Q3_result_point_U',same_matrix(r3['point'],s3['point']) and same_matrix(r3['work_indicator'],s3['conservative_work_indicator']))
    check('Q3_excel_row_count',len(f3)==len(d3['mirrors'])==r3['N']==2981)
    check('Q3_excel_all_fields',all(list(row)==[d3['tower_xy'][0],d3['tower_xy'][1],i+1,m['width'],m['height'],m['x'],m['y'],m['z']] for i,(row,m) in enumerate(zip(f3,d3['mirrors']))))
    check('Q3_excel_identity',all(list(row)==[i+1,m['mirror_id'],m['position_key'],m['group']] for i,(row,m) in enumerate(zip(ident3,d3['mirrors']))))
    check('Q3_excel_all_declared_areas',all(near(m['area'],row[3]*row[4]) for row,m in zip(f3,d3['mirrors'])))
    area3=math.fsum(row[3]*row[4] for row in f3)
    check('Q3_excel_area',near(area3,r3['total_area'],1e-8))
    check('R027_same_design_new_representation',d0['tower_xy']==meta2['tower_xy'] and len(d0['mirrors'])==len(csv2) and all(m['x']==float(c['x']) and m['y']==float(c['y']) and m['mirror_id']==int(c['mirror_id']) and m['position_key']==c['position_key'] and m['width']==meta2['width'] and m['height']==meta2['height'] and m['z']==meta2['installation_height'] for m,c in zip(d0['mirrors'],csv2)))
    check('Q3_fixed_position_and_identity',d3['tower_xy']==d0['tower_xy'] and all(all(m[k]==n[k] for k in ['x','y','mirror_id','position_key']) for m,n in zip(d3['mirrors'],d0['mirrors'])) and len(d3['mirrors'])==len(d0['mirrors']))
    check('new_paired_rng_binding',all(b3[k]==b0[k] for k in ['rng','root_seed','namespace','B','n','levels','times']) and b3['root_seed']!=b2['root_seed'])
    samp3={k:b3[k] for k in ['rng','root_seed','namespace','B','n','levels']};samp3.update(combinations=len(f3)*60,unique_confirmation_samples=len(f3)*60*b3['B']*b3['n'],seed_identity='stable position_key / standard time index / namespace / batch; Q3F013 and Q3R000 paired, not independent of each other within matching block')
    groups=[]
    for g in sorted({m['group'] for m in d3['mirrors']}):
        mm=[m for m in d3['mirrors'] if m['group']==g]
        groups.append({'group':g,'count':len(mm),'width_m':sorted({m['width'] for m in mm}),'height_m':sorted({m['height'] for m in mm}),'installation_height_m':sorted({m['z'] for m in mm}),'area_m2':math.fsum(m['area'] for m in mm)})
    q3=entry('Q3F013',s3,s3['conservative_work_indicator'],len(f3),r3['total_area'],d3['tower_xy'],{'groups':groups},
      {'confirmation_summary':P3+'/candidates/Q3F013/confirmation/summary.json','result_data':P3+'/delivery/结果数据-v001.json','confirmation_binding':P3+'/candidates/Q3F013/confirmation/binding.json','design':P3+'/candidates/Q3F013/design.json','formal_excel':P3+'/delivery/result3.xlsx','statistics_directory':P3+'/candidates/Q3F013/confirmation','freeze':P3+'/最终候选与确认冻结-v001.json','saved_rebuild':P3+'/delivery/独立重建核验-v001.json','accepted_result':'工作记录/阶段记录/Q03-第3问结果初稿-v001.md','paper':'工作记录/论文/第3问-模型建立与求解-v001.md','evidence_map':'工作记录/论文/第3问-正文证据映射-v001.md'},samp3)
    q3['uncertainty_definition']=s3['work_indicator_definition'];q3['low_survival']=s3['low_survival'];q3['tables']=r3['tables'];q3['area_weighted']=r3['area_weighted'];q3['energy_total_ratios']=r3['energy_total_ratios']
    q0=entry('R027-Q3-new-paired-baseline',s0,s0['conservative_work_indicator'],len(d0['mirrors']),q2['total_area_m2'],d0['tower_xy'],q2['dimensions'],
      {'confirmation_summary':P3+'/candidates/Q3R000/confirmation/summary.json','confirmation_binding':P3+'/candidates/Q3R000/confirmation/binding.json','design':P3+'/candidates/Q3R000/design.json','statistics_directory':P3+'/candidates/Q3R000/confirmation','saved_rebuild':P3+'/delivery/独立重建核验-v001.json'},samp3)
    q0['usage_restriction']='Only Q3 paired comparison baseline; does not replace Q2 original accepted results.'
    q0['uncertainty_definition']=s0['work_indicator_definition']
    check('paired_q_delta_same_experiment',near(cmp['delta_q_kw_m2'],q3['annual']['q_kw_m2']-q0['annual']['q_kw_m2']))
    check('paired_power_delta_same_experiment',near(cmp['delta_power_kw'],q3['annual']['power_kw']-q0['annual']['power_kw'],1e-8))
    check('paired_relative_same_experiment',near(cmp['relative_q_difference'],cmp['delta_q_kw_m2']/q0['annual']['q_kw_m2']))
    check('previous_verifications_and_gates',ver3['all_pass'] and ver3['formal_ready'] and s2['formal_decision']=='PASS' and s3['formal_decision']=='PASS' and s1['work_targets_all_met'])
    check('Q3_small_margin_source',near(q3['annual']['rating_margin_kw'],r3['rating_margin_kw'],1e-8))
    cmp.update(path=P3+'/delivery/paired-comparison-v001.json',sha256=sha(P3+'/delivery/paired-comparison-v001.json'),baseline_annual=q0['annual'],
      baseline_new_minus_Q2_original={'power_kw':q0['annual']['power_kw']-q2['annual']['power_kw'],'q_kw_m2':q0['annual']['q_kw_m2']-q2['annual']['q_kw_m2']},
      area_difference_m2=q3['total_area_m2']-q0['total_area_m2'],
      source_warning='Differences are taken from original paired file; candidate_q differs from summary by ~5.6e-17 due to summation path, no physical/numeric re-estimation.')
    result={'schema':'s03-result-authorities-v001','created':datetime.now().astimezone().isoformat(),'scope':'Read accepted saved statistics, result data and full Excel fields. No optical rays, no geometry rerun, no optimization.',
      'labels':s1['labels'],'units':['1','1','1','1','kW','kW/m2'],'rows':s1['rows'],'questions':{'q1':q1,'q2':q2,'q3':q3},'paired_baseline':q0,'comparison':cmp,
      'statistical_interfaces':{'all_required_efficiencies':'count mean across fixed mirror population; equal5 times per month/equal60 annually','area_weighted':'auxiliary; equals count mean only when areas equal, cannot replace required Q3 means','power':'sum actual area_i*eta_i*DNI_k, then equal times; unit power divides actual fixed design total area','Q1_U':'Original max of t7 JK, prefix change, independent-initial change, raw alternative shift; five-object retrospective diameter supplement retained separately.','Q2_Q3_U':'max(t7 JK, prefix change, raw shift)+registered low-survival full-range effect.','all_U_limit':'Numerical work diagnostics, not strict/joint confidence or physical-error bounds; zero sampling cosine indicator is not zero physical uncertainty.'},
      'workbook_readback':{'q2':{'file':P2+'/result2.xlsx','actual_rows':len(f2),'area_fsum_m2':area2,'identity_mapping':'row order matched frozen design.mirrors.csv; all six/eight common fields exact','sha256':sha(P2+'/result2.xlsx')},'q3':{'file':P3+'/delivery/result3.xlsx','actual_rows':len(f3),'area_fsum_m2':area3,'stable_id_unique':len({row[1] for row in ident3})==len(ident3),'all_fields_exact':True,'sha256':sha(P3+'/delivery/result3.xlsx')}},
      'checks':CHECKS,'all_pass':all(v['passed'] for v in CHECKS.values()),'script_path':str(Path(__file__).relative_to(ROOT)).replace('\\','/'),'script_sha256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
      'limitations':['No full optical or geometry rerun this stage; prior accepted verification reused.','The candidate margin is small; no statement of ample engineering headroom.','Q2 and Q3 comparison baseline remain distinct experiments of the same R027 design.','Three questions belong to one problem, not cross-problem independent validation.']}
    (OUT/'结果与来源-v001.json').write_text(json.dumps(result,ensure_ascii=False,indent=2,allow_nan=False)+'\n',encoding='utf-8')
    write_md(result)
    check('output_JSON_readback',read('工作记录/论文/全题整合/结果与来源-v001.json')['all_pass'])
    print(json.dumps({'all_pass':result['all_pass'],'check_count':len(result['checks']),'annual':{k:v['annual'] for k,v in result['questions'].items()},'source_file':str(OUT/'结果与来源-v001.json')},ensure_ascii=False))

def link(rel,label=None):
    return '['+(label or Path(rel).name)+']('+os.path.relpath(safe(rel),OUT).replace('\\','/')+')'
def write_md(r):
    q=r['questions'];p=r['paired_baseline'];c=r['comparison']
    lines=['# 全题结果与唯一有效来源表 v001','',
      '本文件由现有有效确认统计、结果文件和实际正式清单直接生成。它固定全题摘要、正文、题表、结论及图表使用的数据来源，不改变任何已验收数值或随机配置。三问阶段均已获用户验收；整合论文与冻结候选仍待整体验收，管理员归档未确认。','',
      '## 1 四份确认结果的用途','',
      '| 来源身份 | 用途 | 年平均总热功率（kW） | 单位面积功率（kW/m²） | 总功率工作指标（kW） | 确认主来源 |','|---|---|---:|---:|---:|---|']
    for key,name,use in [('q1','第1问固定镜场','第1问全部正式表项'),('q2','第2问R027原确认','第2问全部正式表项'),('q3','第3问Q3F013','第3问全部正式表项')]:
        x=q[key];a=x['annual'];lines.append(f"| {name} | {use} | {a['power_kw']:.11f} | {a['q_kw_m2']:.14f} | {a['U_power_kw']:.12f} | {link(x['paths']['confirmation_summary'])} |")
    a=p['annual'];lines.append(f"| 第3问R027新配对基线 | 仅用于第3问新配对差，不替换第2问正式值 | {a['power_kw']:.11f} | {a['q_kw_m2']:.14f} | {a['U_power_kw']:.12f} | {link(p['paths']['confirmation_summary'])} |")
    lines += ['', '以上保留较多小数是为了核对来源，并不声称全部显示位可靠。正文显示位数应结合相应工作不确定性。四份结果共用相同列顺序：光学、余弦、联合阴影遮挡、条件截断、总热功率、单位面积功率；效率为无量纲，内部功率均为kW，题表总功率转换为MW。', '',
      '第2问原确认与第3问新基线表示同一R027物理设计，但随机实验不同。新基线相对原确认的总功率差为 '+f"{c['baseline_new_minus_Q2_original']['power_kw']:.12f} kW"+'。本轮没有覆盖或合并两次统计。原第2问结果继续使用原确认值；第3问改进幅度只使用下面的同一配对文件。','',
      '## 2 第3问配对改善与额定边界','',
      '| 量 | 有效值 | 来源或用途 |','|---|---:|---|',
      f"| 单位面积功率差（kW/m²） | {c['delta_q_kw_m2']:.15f} | {link(c['path'])} |",
      f"| 差值工作指标（kW/m²） | {c['work_indicator_delta_q']:.15f} | 同一配对批次删批、前缀/原始积分差及两设计低存活影响量 |",
      f"| 相对提高（%） | {100*c['relative_q_difference']:.10f} | 分母为新配对基线，不用旧第2问值 |",
      f"| 配对总功率变化（kW） | {c['delta_power_kw']:.11f} | 同一新配对实验 |",
      f"| 总面积变化（m²） | {c['area_difference_m2']:.10f} | 两份实际冻结清单 |",
      f"| 第3问额定工作下限（kW） | {q['q3']['annual']['rating_lower_kw']:.11f} | 点值减功率工作指标 |",
      f"| 第3问额定工作余量（kW） | {q['q3']['annual']['rating_margin_kw']:.11f} | 下限减60000 |",'',
      f"第3问工作余量仅相当于60 MW的 {100*q['q3']['annual']['rating_margin_kw']/60000:.6f}%。它支持所定数值工作判据通过，不能写成工程余量充足。减少面积、降低总功率、提高单位面积功率的取舍必须共同保留。配对差的候选q与汇总q在约5.6×10⁻¹⁷的尾数上不同，属于保存统计重建加总路径的浮点尾差；改善一律引用配对文件，不手工改尾数。",'',
      '## 3 设计与清单读回','',
      '| 问题 | 镜数 | 塔位（m） | 总面积（m²） | 参数 |','|---|---:|---|---:|---|']
    for k in ['q1','q2','q3']:
        x=q[k];dims=x['dimensions'];desc=(f"统一宽{dims['uniform_width_m']}m、高{dims['uniform_height_m']}m、安装高{dims['uniform_installation_height_m']}m" if 'uniform_width_m' in dims else '统一宽6.69m、安装高6m；组4的582面高6.05m，其余2399面高6.65m')
        lines.append(f"| {k} | {x['N']} | {x['tower_xy_m']} | {x['total_area_m2']:.4f} | {desc} |")
    lines += ['',f"本轮以openpyxl只读模式逐行读取{link(q['q2']['paths']['formal_excel'],'result2.xlsx')}和{link(q['q3']['paths']['formal_excel'],'result3.xlsx')}。两份均2981行；原始序号、xy、塔位、尺寸、安装高度与相应冻结清单逐字段一致。第3问身份映射含导出序号、稳定镜号、位置身份和组号；全部对应。按每行宽×高重新求和，与冻结总面积相符。这里仅重建字段和面积，没有重跑镜对几何或光学。", '',
      '## 4 随机实验与不确定性不能混用','',
      '| 数值实验 | 根种子 | 命名空间 | 独立批次数 | 每批样本 | 前缀 |','|---|---:|---:|---:|---:|---|']
    for name,x in [('Q1正式',q['q1']),('Q2原正式',q['q2']),('Q3F013与新R027配对',q['q3'])]:
        s=x['sampling'];lines.append(f"| {name} | {s['root_seed']} | {s['namespace']} | {s['B']} | {s['n']} | 128为256相关前缀，不重复合并 |")
    lines += ['', '第1问原冻结工作指标取整批Jackknife近似逐项半宽、确认与相关前缀之差、确认与独立初算之差、原始积分替代差的最大值；事后全部低存活筛查保留5个对象，新增全范围影响量单独保存，没有改写冻结指标。其补充叠加量的最大效率约为 '+f"{q['q1']['retrospective_low_survival']['max_efficiency_U_plus_bound']:.12f}"+'，功率最大相对量约为 '+f"{100*q['q1']['retrospective_low_survival']['max_power_relative_U_plus_bound']:.8f}%"+'，支持原工作目标但不是严格联合置信界。','',
      '第2、3问使用各自预登记的最大项指标，再加少于100存活样本的全范围影响量。少于100是管理性筛查条件，超过100不自动意味着单镜精确。所有工作指标均不覆盖未量化物理模型偏差；余弦抽样指标为0不表示物理误差为0。','',
      '三问必需平均效率均按镜数及规定时点平均。第3问的面积加权效率和能量总量比作为辅助对象分别保存；功率必须按逐镜实际面积与效率逐项求和。只有等面积时，镜数效率平均与面积加权平均才等价；不能据此把第3问主表效率乘总面积代替真实功率。','',
      '## 5 文件版本与SHA-256','',
      '| 来源 | 文件 | SHA-256 |','|---|---|---|']
    for name,x in [('Q1',q['q1']),('Q2原正式',q['q2']),('Q3正式',q['q3']),('Q3新基线',p)]:
        for field in ['confirmation_summary','configuration','confirmation_binding','design','design_bundle','formal_excel']:
            if field in x['sha256']:lines.append(f"| {name} / {field} | {link(x['paths'][field])} | `{x['sha256'][field]}` |")
    lines.append(f"| 配对改善 | {link(c['path'])} | `{c['sha256']}` |")
    lines += ['', '完整13×6点值与指标矩阵、全部来源路径、完整核对项和更多SHA记录在'+link('工作记录/论文/全题整合/结果与来源-v001.json')+'。生成入口为'+link(str(Path(__file__).relative_to(ROOT)).replace('\\','/'))+'。不导入评价核，不生成射线，不修改前阶段输入或输出。','',
      '本轮审计支持有效来源、实际清单字段、面积及已保存汇总的一致性；不等同于再次独立验证物理模型。']
    (OUT/'结果与来源表-v001.md').write_text('\n'.join(lines)+'\n',encoding='utf-8')

if __name__=='__main__':run()
