"""Independent MD table/source audit and PDF numeric presence, no generator/model imports."""
from pathlib import Path
from datetime import datetime
from collections import Counter
import re,json,hashlib,math
from pypdf import PdfReader
R=Path(r'C:\Users\admin\OneDrive\Desktop\26国赛-单题盲解区\A-P8C3').resolve()
O=R/'工作记录/论文/全题整合'
CHECKS={};CELLS=[];TEXTS=[];SOURCES={}
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def read(p):SOURCES[str(p.relative_to(R)).replace('\\','/')]=sha(p);return json.loads(p.read_text(encoding='utf-8-sig'))
def ck(k,b,ev=None):
 CHECKS[k]={'passed':bool(b),'evidence':ev}
def norm(s):return re.sub(r'\s+','',s).replace('−','-').replace('–','-')
def numbercell(table,row,col,value,digits=4):
 actual=T[table]['rows'][row][col];expected=f'{value:.{digits}f}'
 result=norm(actual)==expected
 CELLS.append({'table':table,'row_1based':row+1,'column_1based':col+1,'source_value':value,'display_digits':digits,'expected':expected,'actual':actual,'passed':result})
 ck(f't{table}_r{row+1}_c{col+1}',result)
def exactcell(table,row,col,expected):
 actual=T[table]['rows'][row][col];result=norm(actual)==norm(expected)
 CELLS.append({'table':table,'row_1based':row+1,'column_1based':col+1,'expected':expected,'actual':actual,'passed':result});ck(f't{table}_r{row+1}_c{col+1}',result)
def scicell(table,row,col,value):
 expected='\\('+f'{value*1e5:.5f}'+'\\times10^{-5}\\)';exactcell(table,row,col,expected)
def prose(id,fragment,value,digits,section):
 expected=f'{value:.{digits}f}';part=SECTIONS.get(section,MD)
 good=norm(fragment.replace('{v}',expected)) in norm(part)
 TEXTS.append({'id':id,'section':section,'source_value':value,'display_digits':digits,'expected_fragment':fragment.replace('{v}',expected),'passed':good});ck('prose_'+id,good)
def extract_tables(text):
 lines=text.splitlines();tables={};i=0
 while i<len(lines):
  mat=re.match(r'^表(\d+)\s+(.+)$',lines[i])
  if not mat:i+=1;continue
  n=int(mat.group(1));caption=lines[i];j=i+1
  while j<len(lines) and not lines[j].strip():j+=1
  raw=[]
  while j<len(lines) and lines[j].startswith('|'):raw.append(lines[j]);j+=1
  ck('table'+str(n)+'_header_separator',len(raw)>=3 and re.fullmatch(r'[|:\- ]+',raw[1]) is not None)
  rows=[[c.strip() for c in line.strip()[1:-1].split('|')] for line in raw]
  tables[n]={'caption':caption,'header':rows[0],'rows':rows[2:],'line_1based':i+1}
  i=j
 return tables
def run():
 global MD,T,SECTIONS
 for f in ['正文数值独立核验-v001.json','正文数值独立核验-v001.md']:
  if (O/f).exists():raise FileExistsError(O/f)
 MD=(O/'完整论文-v001.md').read_text(encoding='utf-8-sig');SOURCES[str((O/'完整论文-v001.md').relative_to(R)).replace('\\','/')]=sha(O/'完整论文-v001.md')
 auth=read(O/'结果与来源-v001.json');e=read(O/'实际搜索比较与检验证据-v001.json');q=auth['questions'];base=auth['paired_baseline'];cmp=auth['comparison']
 T=extract_tables(MD);ck('table_sequence_1_to12',list(T)==list(range(1,13)))
 SECTIONS={}
 for mat in re.finditer(r'^## (.+)$',MD,re.M):
  start=mat.end();end=MD.find('\n## ',start);SECTIONS[mat.group(1)]=MD[start:end if end!=-1 else None]
 for i,k in enumerate(['q1','q2','q3']):
  p=q[k]['annual']['point'];ck('table2_row_count',len(T[2]['rows'])==3)
  for j in range(4):numbercell(2,i,j+1,p[j],4)
  numbercell(2,i,5,p[4]/1000,3);numbercell(2,i,6,p[5],4)
 for t,k in [(3,'q1'),(6,'q2'),(9,'q3')]:
  ck(f'table{t}_12months',len(T[t]['rows'])==12)
  for i in range(12):
   numbercell(t,i,0,i+1,0)
   for c,j in enumerate([0,1,2,3,5],1):numbercell(t,i,c,q[k]['point'][i][j],4)
 repairfine=[x for x in e['q2_repair']['records'] if x['fidelity']=='fine'];ck('table4_fine_count',len(T[4]['rows'])==len(repairfine)==2)
 for i,x in enumerate(repairfine):
  exactcell(4,i,0,x['name']);numbercell(4,i,1,x['n'],0);numbercell(4,i,2,x['area_m2'],4);numbercell(4,i,3,x['P_formal_kw'],3);numbercell(4,i,4,x['q_formal_kw_m2'],7)
 d=q['q2']['dimensions'];exactcell(5,0,0,r'\((0,-15)\)');exactcell(5,0,1,r'\(6.65\times6.65\)');numbercell(5,0,2,d['uniform_installation_height_m'],2);numbercell(5,0,3,q['q2']['N'],0);numbercell(5,0,4,q['q2']['total_area_m2'],4)
 ck('table5_parameter_content_bound',q['q2']['tower_xy_m']==[0.,-15.] and d['uniform_width_m']==d['uniform_height_m']==6.65)
 groups=q['q3']['dimensions']['groups'];ck('table7_six_groups',len(T[7]['rows'])==len(groups)==6)
 for i,g in enumerate(groups):
  numbercell(7,i,0,g['group'],0);numbercell(7,i,1,g['count'],0)
  for col,key in [(2,'width_m'),(3,'height_m'),(4,'installation_height_m')]:ck(f'g{i}_{key}_single',len(g[key])==1);numbercell(7,i,col,g[key][0],2)
  numbercell(7,i,5,g['area_m2'],4)
 exactcell(8,0,0,r'\((0,-15)\)');exactcell(8,0,1,'');exactcell(8,0,2,'');numbercell(8,0,3,q['q3']['N'],0);numbercell(8,0,4,q['q3']['total_area_m2'],4)
 ck('Q3_table3_empty_only_global_fields',len(T[8]['rows'])==1 and T[8]['rows'][0][1:3]==['',''] and len(groups)==6)
 for i,x in enumerate([base,q['q3']]):
  a=x['annual'];numbercell(10,i,1,a['power_kw'],4);numbercell(10,i,2,a['U_power_kw'],4);numbercell(10,i,3,a['q_kw_m2'],7);scicell(10,i,4,a['U_q_kw_m2'])
 numbercell(10,2,1,cmp['delta_power_kw'],4);exactcell(10,2,2,'—');numbercell(10,2,3,cmp['delta_q_kw_m2'],7);scicell(10,2,4,cmp['work_indicator_delta_q'])
 for i,k in enumerate(['q1','q2','q3']):
  x=e['validation'][k];exactcell(11,i,0,k.upper());numbercell(11,i,1,x['combination_count'],0);numbercell(11,i,2,x['max_efficiency_U'],7);numbercell(11,i,3,100*x['max_power_relative_U'],5);numbercell(11,i,4,x['low_survival_count'],0)
 for i,x in enumerate(e['q3_search']['fine_records']):
  exactcell(12,i,0,x['name']);numbercell(12,i,1,x['area'],4);numbercell(12,i,2,x['annual_formal_point'][4],4);numbercell(12,i,3,x['annual_formal_point'][5],7);numbercell(12,i,4,x['power_search_margin'],4)
 # Key narrative values are independently reconstructed from source fields, not re-emitted by paper builder.
 for section in ['摘要','9 全文结论']:
  for k in ['q1','q2']:prose(section+k+'P','{v} MW',q[k]['annual']['power_mw'],3,section)
  prose(section+'q2q','{v} kW/m²',q['q2']['annual']['q_kw_m2'],7,section)
  prose(section+'delta_pct','{v}%',100*cmp['relative_q_difference'],5,section)
  prose(section+'smallmargin','{v} kW',q['q3']['annual']['rating_margin_kw'],2,section)
 prose('abstract_q3P','{v} MW',q['q3']['annual']['power_mw'],3,'摘要');prose('abstract_q3q','{v} kW/m²',q['q3']['annual']['q_kw_m2'],7,'摘要')
 prose('abstract_area_reduce','总面积减少 {v} m²',-cmp['area_difference_m2'],3,'摘要');prose('abstract_power_decline','总功率下降 {v} kW',-cmp['delta_power_kw'],4,'摘要')
 for k,section in [('q2','6 第2问：统一参数设计'),('q3','7 第3问：固定布局下的分组异尺寸设计')]:
  a=q[k]['annual'];prose(k+'P','{v} kW',a['power_kw'],4,section);prose(k+'U','{v} kW',a['U_power_kw'],4,section);prose(k+'lower','{v} kW',a['rating_lower_kw'],4,section)
 prose('Q2margin','比60MW高 {v} kW',q['q2']['annual']['rating_margin_kw'],4,'6 第2问：统一参数设计')
 prose('Q3pct_margin','约为60MW的 {v}%',100*q['q3']['annual']['rating_margin_kw']/60000,4,'7 第3问：固定布局下的分组异尺寸设计')
 prose('R027_two_experiments','功率点估计相差 {v} kW',cmp['baseline_new_minus_Q2_original']['power_kw'],4,'7 第3问：固定布局下的分组异尺寸设计')
 prose('delta_after_U','扣减后仍为 {v} kW/m²',cmp['difference_minus_work_indicator'],7,'7 第3问：固定布局下的分组异尺寸设计')
 prose('Q3areaweighted','面积加权总效率为 {v}',q['q3']['area_weighted']['point'][-1][0],6,'7 第3问：固定布局下的分组异尺寸设计')
 prose('Q3countmean','镜数平均为 {v}',q['q3']['annual']['point'][0],6,'7 第3问：固定布局下的分组异尺寸设计')
 prose('Q1_extra_eff','最大效率为 {v}',e['validation']['q1']['retrospective_max']['max_efficiency_U'],7,'8 验证、数值证据与适用边界')
 prose('Q1_extra_power','功率相对最大量为 {v}%',100*e['validation']['q1']['retrospective_max']['max_power_relative_U'],4,'8 验证、数值证据与适用边界')
 prose('search_margin','正余量约{v}kW',e['q3_search']['fine_records'][-1]['power_search_margin'],3,'7 第3问：固定布局下的分组异尺寸设计')
 ck('narrative_initial_search_count',f"比较{e['q2_initial']['coarse_count']}个12时点" in norm(MD) and f"其中{e['q2_initial']['fine_count']}个接受全60时点" in norm(MD))
 ck('R027_two_sources_not_unified',q['q2']['sampling']['root_seed']!=base['sampling']['root_seed'] and q['q2']['annual']['power_kw']!=base['annual']['power_kw'] and norm('不能为统一数字而覆盖原确认') in norm(MD))
 ck('Q1_extra_not_in_original_U',norm('事后补查的低存活影响单列，不回写式（18）') in norm(MD))
 ck('table2_original_Q2_and_table10_new_R027',T[2]['rows'][1][5]==f"{q['q2']['annual']['power_mw']:.3f}" and T[10]['rows'][0][1]==f"{base['annual']['power_kw']:.4f}")
 # PDF text evidence: each caption must locate one actual page; every decimal token from table
 # rows must appear with at least the required multiplicity on that caption page.
 pdf=O/'完整论文-v001.pdf';reader=PdfReader(pdf);pt=[x.extract_text() for x in reader.pages];pdfchecks=[]
 ck('pdf20pages',len(pt)==20)
 for t in range(2,13):
  caption=norm(T[t]['caption']);hits=[i for i,x in enumerate(pt) if caption in norm(x)]
  ck(f'pdf_table{t}_caption_unique',len(hits)==1,hits)
  if len(hits)!=1:continue
  i=hits[0];allrows=' '.join(' '.join(x) for x in T[t]['rows']);expected=Counter(re.findall(r'[-]?\d+\.\d+',allrows));actual=Counter(re.findall(r'[-]?\d+\.\d+',pt[i].replace('−','-')))
  missing={n:k-actual[n] for n,k in expected.items() if actual[n]<k};ck(f'pdf_table{t}_decimal_tokens_present',not missing,missing)
  pdfchecks.append({'table':t,'page':i+1,'caption':T[t]['caption'],'decimal_token_count':sum(expected.values()),'missing_decimal_tokens':missing,'passed':not missing,'limitation':'Numeric presence/multiplicity on caption page; spatial placement established separately by actual PNG review.'})
 visual=read(O/'页面核验/attempt-002/前10页人工查看-v001.json');ck('current_first10_visual_binding',visual['pdf_sha256']==sha(pdf) and visual['passed'])
 priorread=read(O/'来源审计回读-v001.json');ck('prior_complete_excel_readback',priorread['all_saved_checks_pass'] and priorread['all_source_file_sha_matches'])
 record={'kind':'S03_INDEPENDENT_PAPER_NUMBERS_V001','created':datetime.now().astimezone().isoformat(),'scope':'Independently parse current Markdown tables2–12 and prose, compare saved authorities and original search record extraction; pypdf text presence and separately bound actual PNG review. No paper generator import; no optical/geometry run.',
   'source_sha256':SOURCES,'paper_sha256':sha(O/'完整论文-v001.md'),'pdf_sha256':sha(pdf),'table_schema':{str(k):{'caption':v['caption'],'header':v['header'],'row_count':len(v['rows']),'line_1based':v['line_1based']} for k,v in T.items()},'cells':CELLS,'prose_checks':TEXTS,'pdf_table_checks':pdfchecks,'checks':CHECKS,'all_pass':all(x['passed'] for x in CHECKS.values()),'numeric_cells_checked':len(CELLS),'prose_checks_count':len(TEXTS),'script':str(Path(__file__).relative_to(R)).replace('\\','/'),'script_sha256':sha(Path(__file__)),
   'roundoff_and_display':'Source table retains Q2 rebuilt-data/frozen-summary float tails and Q3 paired/summary tails. Audit checks visible decimal rendering from intended authority, no frozen point/U rewritten. MW=1000kW. More printed digits do not prove physical precision.',
   'not_repeated':['No original workbook rescan: prior39-check readback reused.','No optical rays, optimization, full-pair geometry or original numerical tests rerun.','pypdf text matching does not replace all-page actual visual QA. Root separately records pages11–20.'],
   'environment_note':'fitz was unavailable during preliminary PDF extraction; used already installed pypdf without installing dependencies.','failures':[k for k,v in CHECKS.items() if not v['passed']]}
 (O/'正文数值独立核验-v001.json').write_text(json.dumps(record,ensure_ascii=False,indent=2,allow_nan=False)+'\n',encoding='utf-8')
 lines=['# 正文数值独立核验 v001','', '本核验独立解析当前Markdown，没有导入论文生成器，也没有重跑光学或搜索。表2—12逐单元格对照已保存的唯一结果来源与实际搜索证据，PDF使用已安装pypdf提取文字并核对对应题表数值。','',
  f"检查数：{len(CHECKS)}；表格单元格{len(CELLS)}；正文关键数字{len(TEXTS)}；全部通过：{record['all_pass']}。",'',
  '| 范围 | 核对内容 |','|---|---|','| 表2 | 三问正式年结果，kW转MW，Q2保留原确认 |','| 表3、6、9 | 三问12个月全部效率与单位面积功率，显示四位小数 |','| 表4、12 | 实际较精搜索点量、镜数、面积和功率搜索余量，不混称正式确认 |','| 表5、7、8 | 统一/逐组参数，实际面积和镜数；第3问统一栏保持空白 |','| 表10 | 新R027、新Q3、同一配对差和对应U；不套旧基线 |','| 表11 | 原确认最大工作指标、百分比转换、低存活数量 |','| 摘要、结果与结论 | 三问功率、单位面积目标、配对增幅、面积/功率取舍和小额定余量 |','',
  '第1问事后补充界没有替换原冻结U；第2问原确认与第3问新基线保持不同数据源。对照来源中的浮点加总尾差只作记录，不人为改写源值。当前可见显示位与来源舍入一致不意味着这些位是物理可靠位。','',
  'PDF文字核查定位了各表题所在页面并检查表格小数的出现次数；该检查不能判断空间裁切，因此另结合attempt-002实际页面记录。前10页当前绑定通过，后10页由主线程独立记录。','',
  '原实际Excel逐行读回39项核验继续引用，无重扫；文件一致性不能替代物理模型验证。准备过程中fitz不可用，已使用现有pypdf完成提取，没有安装依赖。','',
  '详细失败项：'+(', '.join(record['failures']) if record['failures'] else '无。')]
 (O/'正文数值独立核验-v001.md').write_text('\n'.join(lines)+'\n',encoding='utf-8')
 print(json.dumps({'all_pass':record['all_pass'],'checks':len(CHECKS),'cells':len(CELLS),'prose':len(TEXTS),'failures':record['failures']},ensure_ascii=False))
if __name__=='__main__':run()
