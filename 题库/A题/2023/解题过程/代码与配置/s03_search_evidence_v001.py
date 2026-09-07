"""Read saved search comparisons and confirmation diagnostics; no numerical model import."""
from pathlib import Path
from datetime import datetime
from collections import Counter
import json,hashlib,math,os
R=Path(r'C:\Users\admin\OneDrive\Desktop\26国赛-单题盲解区\A-P8C3').resolve()
O=R/'工作记录/论文/全题整合'
P2='工作记录/诊断结果/Q02-搜索-v001'
P2R='工作记录/诊断结果/Q02-修复-v001'
P3='工作记录/诊断结果/Q03-实施-v001'
SOURCES={};CHECKS={}
def p(s):
 x=(R/s).resolve()
 if not x.is_relative_to(R):raise ValueError('Outside task')
 return x
def sh(s):return hashlib.sha256(p(s).read_bytes()).hexdigest()
def rd(s):
 SOURCES[s]=sh(s);return json.loads(p(s).read_text(encoding='utf-8-sig'))
def jl(s):
 SOURCES[s]=sh(s);return [json.loads(t) for t in p(s).read_text(encoding='utf-8-sig').splitlines() if t.strip()]
def ck(n,b):
 CHECKS[n]=bool(b)
 if not b:raise AssertionError(n)
def clean(x):
 if isinstance(x,float) and not math.isfinite(x):return None
 if isinstance(x,list):return [clean(y) for y in x]
 if isinstance(x,dict):return {k:clean(y) for k,y in x.items()}
 return x
def link(s,label=None):return '['+(label or Path(s).name)+']('+os.path.relpath(p(s),O).replace('\\','/')+')'
def metric_max(u,pt,rows):
 eff=max((u[i][j],i,j) for i in range(13) for j in range(4))
 power=max((u[i][j]/abs(pt[i][j]),i,j) for i in range(13) for j in (4,5))
 return {'max_efficiency_U':eff[0],'max_efficiency_at':{'row':rows[eff[1]],'column_index':eff[2]},'max_power_relative_U':power[0],'max_power_relative_at':{'row':rows[power[1]],'column_index':power[2]},'all78_targets_met':all(u[i][j] <= (0.001 if j<4 else .005*abs(pt[i][j])) for i in range(13) for j in range(6))}
def run():
 O.mkdir(parents=True,exist_ok=True)
 for f in ['实际搜索比较与检验证据-v001.json','实际搜索比较与检验证据-v001.md']:
  if (O/f).exists():raise FileExistsError(O/f)
 initial=jl(P2+'/搜索轨迹.jsonl');coarse=[x for x in initial if x['actual_time_count']==12];fine=[x for x in initial if x['actual_time_count']==60]
 dirs=sorted(x.name for x in p(P2+'/candidates').iterdir() if x.is_dir())
 ck('initial19_scores14coarse5fine',len(initial)==19 and len(coarse)==14 and len(fine)==5)
 ck('initial_unique_fine',len({x['name'] for x in fine})==5)
 records=[]
 for x in initial:
  tag='fine' if x['actual_time_count']==60 else 'coarse';sp=P2+'/candidates/'+x['name']+'/'+tag+'/score.json';bs=P2+'/candidates/'+x['name']+'/'+tag+'/binding.json'
  sc=rd(sp);b=rd(bs)
  ck(x['name']+'_'+tag+'_stored_score_binding',sc['name']==x['name'] and sc['actual_time_count']==len(b['times']) and sc['actual_mirror_count']==b['n_mirrors'])
  z={'name':x['name'],'fidelity':tag,'time_count':len(b['times']),'N':b['n_mirrors'],'area_m2':sc['area'],'dimensions':{k:sc['spec'].get(k) for k in ['width','height','installation_height','tower_xy','generator','phi','spacing_margin']},'heuristic_P_kw':sc['P_score_kw'],'heuristic_q_kw_m2':sc['q_score_kw_m2'],'zero_survivor':sc['zero_survivor'],'zero_capture':sc['zero_capture'],'unknown':sc['unknown'],'formal_rating':sc['formal_rating'],'sampling':{k:b[k] for k in ['B','n','levels','namespace','root_seed']},'paths':{'score':sp,'binding':bs}}
  if tag=='fine':
   ss=P2+'/candidates/'+x['name']+'/fine/summary.json';sm=rd(ss);z.update(annual_formal_point=sm['point'][-1],required_na=sm.get('required_table_na_locations'),pooled_state_counts=sm['pooled_state_counts']);z['paths']['summary']=ss
  records.append(z)
 old=rd(P2+'/独立确认结论.json');oldfreeze=rd(P2+'/最终拟提交候选冻结.json')
 ck('C22_failure_current',old['name']=='C22' and old['decision']=='FAIL' and old['all_precision'] and old['rating_lower_kw']<60000)
 repair=rd(P2R+'/实际候选比较.json');rep=[]
 for row in repair['rows']:
  rel=P2R+'/'+row['source'].replace('\\','/');sc=rd(rel);binding=str(Path(rel).with_name('binding.json')).replace('\\','/');b=rd(binding)
  ck(row['name']+'_'+row['fidelity']+'_full60',len(b['times'])==60 and sc['actual_time_count']==60)
  rep.append(dict(row,sampling={k:b[k] for k in ['B','n','levels','namespace','root_seed']},actual_time_count=len(b['times']),paths={'score':rel,'binding':binding}))
 ck('repair_actual5low2fine',Counter(x['fidelity'] for x in rep)=={'low':5,'fine':2} and len({x['name'] for x in rep})==5)
 pair2=repair['paired_fine_comparisons'][0]
 q3trajectory=jl(P3+'/scores.jsonl');q3fine=rd(P3+'/comparison-fine-v001.json');q3groups=rd(P3+'/groups-v001.json')
 q3low=[x for x in q3trajectory if x['tag']=='low'];q3f=[x for x in q3trajectory if x['tag']=='fine'];q3c=[x for x in q3trajectory if x['tag']=='confirmation']
 ck('Q3_actual14low4fine2confirmation',len(q3low)==14 and len(q3f)==4 and len(q3c)==2 and len({x['name'] for x in q3low})==14)
 q3details=[]
 for row in q3fine:
  smpath=P3+'/candidates/'+row['name']+'/fine/summary.json';sp=P3+'/specs/'+row['name']+'-fine.json';bp=P3+'/candidates/'+row['name']+'/fine/binding.json'
  sm=rd(smpath);b=rd(bp)
  ck(row['name']+'_Q3fine_SHA',SOURCES[smpath]==row['summary_sha256'])
  ck(row['name']+'_Q3fine_full60',len(b['times'])==60 and b['n_mirrors']==row['actual_mirror_count'])
  z=dict(row,sampling={k:b[k] for k in ['B','n','levels','namespace','root_seed']},paths={'summary':smpath,'binding':bp})
  if p(sp).exists():z['spec']=rd(sp);z['paths']['spec']=sp
  q3details.append(z)
 authority=rd('工作记录/论文/全题整合/结果与来源-v001.json')
 validation={}
 for k,q in authority['questions'].items():
  sm=rd(q['paths']['confirmation_summary']);u=q['U'];item=metric_max(u,q['point'],q['rows'])
  item.update(N=q['N'],combination_count=q['N']*60,annual_U=q['annual']['U'],source_summary=q['paths']['confirmation_summary'],required_na=sm.get('required_table_na_locations',[]),states=sm.get('pooled_state_counts',sm.get('states')),numerical_checks=sm.get('numeric_checks'),
    count_mean_required=True,area_weighted_auxiliary_only=(k=='q3'),uncertainty_definition=q['uncertainty_definition'])
  if k=='q1':
   ls=q['retrospective_low_survival'];item.update(low_survival_cases=ls['cases'],low_survival_count=ls['count_below100'],low_survival_threshold=100,low_survival_role='Retrospective supplementary diameter; original frozen U unchanged',retrospective_max=metric_max(ls['supplementary_U_plus_bound'],q['point'],q['rows']))
  else:
   item.update(low_survival_cases=q['low_survival']['cases'],low_survival_count=q['low_survival']['screened_count'],low_survival_threshold=q['low_survival']['threshold_exclusive'],low_survival_role='Pre-registered actual-area influence already included in U')
  validation[k]=item
 result={'schema':'s03-search-and-validation-evidence-v001','created':datetime.now().astimezone().isoformat(),'scope':'Saved records only; no geometry/optical rerun.',
  'q2_initial':{'candidate_directories_found':dirs,'evaluated_unique_candidate_count':len({x['name'] for x in initial}),'coarse_count':len(coarse),'fine_count':len(fine),'coarse_names':[x['name'] for x in coarse],'full60_names':[x['name'] for x in fine],'records':records,'C22_failed_confirmation':old,'C22_confirmation_configuration':oldfreeze.get('confirmation_config'),'limits':'12-point scores heuristic; C07 has formal NA even at full60 fine, finite heuristic must not be recast as required annual result. C22 passed numerical precision but failed rating.'},
  'q2_repair':{'new_candidate_count':repair['new_candidates'],'completed_evaluations':repair['completed_evaluations'],'low_count':repair['low_count'],'fine_count':repair['fine_count'],'all_full60':repair['all_new_evaluations_full60'],'records':rep,'paired_fine_comparison':pair2,'paired_annual_difference':pair2['difference_second_minus_first'][-1],'paired_annual_SE':pair2['paired_jackknife_se'][-1],'paired_annual_t3_halfwidth':pair2['approx_pointwise_t3_halfwidth'][-1],'R027_confirmed_change_from_C22':repair['confirmed_change_from_C22'],'limits':repair['limits']},
  'q3_search':{'group_count':len(authority['questions']['q3']['dimensions']['groups']),'group_geometry_source':P3+'/groups-v001.json','group_geometry_report':q3groups,'final_groups':authority['questions']['q3']['dimensions']['groups'],'low_count':len(q3low),'fine_count':len(q3f),'final_confirmation_designs':[x['name'] for x in q3c],'low_records':q3low,'fine_records':q3details,'all_low_full60':all(x['score']['actual_time_count']==60 for x in q3low),'all_fine_full60':all(x['actual_time_count']==60 for x in q3details),'search_identity':'All Q3R names are search candidates; Q3F013 is exported/frozen Q3R013. Q3R000 is the R027 baseline representation.','limits':'6 groups; fixed tower,N,xy; all score volumes include full scene. Search gates and paired SE are not final independent confirmation.'},
  'validation':validation,'sources_sha256':SOURCES,'checks':CHECKS,'all_pass':all(CHECKS.values()),'script':str(Path(__file__).relative_to(R)).replace('\\','/'),'script_sha256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),'missing_inputs':[]}
 result=clean(result)
 (O/'实际搜索比较与检验证据-v001.json').write_text(json.dumps(result,ensure_ascii=False,indent=2,allow_nan=False)+'\n',encoding='utf-8')
 md=['# 实际搜索比较与检验证据 v001','', '仅读取保存源与绑定，不重新运行几何、光学或搜索。搜索评分、较精比较、正式确认与复现检查分列，不能互换。完整逐字段来源及SHA见同名JSON。','',
     '## 第2问实际执行范围','',f"首轮实际评分 {len({x['name'] for x in initial})} 个候选，12时点粗筛 {len(coarse)} 次，全60时点较精 {len(fine)} 次；后者为 "+'、'.join(x['name'] for x in fine)+'。C07较精仍有抽样零和必需NA，不能将其有限启发式功率写成正式结果。','',
     f"C22原确认功率为 {old['annual'][4]:.9f} kW，工作指标 {old['annual_U'][4]:.9f} kW，工作下限 {old['rating_lower_kw']:.9f} kW。数值精度通过而额定失败。原失败与历史确认数据保留，不因后续R027成功而改写。",'',
     '修复阶段新增R023—R027共5个候选，5次低样本、2次较精均使用完整60时点及全部镜子。低样本含抽样零，正式H02量为NA；以下较精点量仅用于候选比较，不是最终独立确认。','',
     '| 候选 | 镜数 | 面积（m²） | 宽×高（m） | 塔位（m） | 较精总功率（kW） | 较精单位面积功率（kW/m²） |','|---|---:|---:|---|---|---:|---:|']
 for x in rep:
  if x['fidelity']=='fine':md.append(f"| {x['name']} | {x['n']} | {x['area_m2']:.4f} | {x['width']}×{x['height']} | {x['tower']} | {x['P_formal_kw']:.6f} | {x['q_formal_kw_m2']:.9f} |")
 md += ['',f"R027减R023的较精年单位面积差 {pair2['difference_second_minus_first'][-1][5]:.12f} kW/m²，配对删批标准误 {pair2['paired_jackknife_se'][-1][5]:.12f}，近似逐项t3半宽 {pair2['approx_pointwise_t3_halfwidth'][-1][5]:.12f}。这是搜索后配对诊断，不能写成选择偏差已消除或物理置信保证。",'',
   '## 第3问实际较精比较','', '14个低样本候选和4个较精比较均覆盖完整2981镜×60时点。6个几何组的镜数依次为497、497、497、497、582、411。最终组参数和面积来自实际冻结设计；完整分组报告按源保存。','',
   '| 候选 | 面积（m²） | 较精总功率（kW） | 较精单位面积功率（kW/m²） | 搜索功率工作量（kW） | 搜索额定余量（kW） |','|---|---:|---:|---:|---:|---:|']
 for x in q3details:md.append(f"| {x['name']} | {x['area']:.4f} | {x['annual_formal_point'][4]:.6f} | {x['annual_formal_point'][5]:.9f} | {x['power_search_work']:.6f} | {x['power_search_margin']:.6f} |")
 md += ['', 'Q3R013在搜索门下有较小正余量，被选为待独立确认对象；Q3R000作为不变基线不属于新设计冻结门的适用对象，其finite_freeze_gate为false不能解读为R027原设计功率失败。最终结果及与新R027的改善只引用结果与来源表中的正式确认及新配对文件。','',
   '## 原确认验证量与低存活','', '| 来源 | 最大效率工作指标 | 最大功率相对工作指标 | 少于100存活组合数 | 口径 |','|---|---:|---:|---:|---|']
 for k,v in validation.items():md.append(f"| {k} | {v['max_efficiency_U']:.12f} | {100*v['max_power_relative_U']:.9f}% | {v['low_survival_count']} | "+('原冻结U；事后补充界另存' if k=='q1' else '已含低存活影响量')+' |')
 md += ['', '阈值100仅是管理性筛查，并非单镜精度标准。所有真实零、抽样零、未知与NA保持源记录；Q1事后5对象补查没有替换其原冻结指标。功率相对工作指标及效率绝对工作指标不是物理误差上界，也不是严格联合置信保证。','',
   '关键来源：'+link(P2+'/搜索轨迹.jsonl')+'、'+link(P2+'/独立确认结论.json')+'、'+link(P2R+'/实际候选比较.json')+'、'+link(P3+'/comparison-fine-v001.json')+'、'+link('工作记录/论文/全题整合/结果与来源-v001.json')+'。', '',
   '本文件重读已保存统计并核对绑定，只支持来源与算术一致性，不冒称再次执行了原测试。']
 (O/'实际搜索比较与检验证据-v001.md').write_text('\n'.join(md)+'\n',encoding='utf-8')
 print(json.dumps({'checks':len(CHECKS),'all_pass':all(CHECKS.values()),'source_count':len(SOURCES),'q2_initial_full60':[x['name'] for x in fine],'validation':{k:{a:v[a] for a in ['max_efficiency_U','max_power_relative_U','low_survival_count']} for k,v in validation.items()}},ensure_ascii=False))
if __name__=='__main__':run()
