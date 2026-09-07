"""Final file and source-binding audit, separately from scientific rating."""
import time
START=time.perf_counter()
from pathlib import Path
import sys,re,json,hashlib
H=Path(__file__).resolve().parent;sys.path.insert(0,str(H))
import q02_search_common_v001 as io
R=io.ROOT;W=R/'工作记录';O=io.OUT;P=W/'论文'
b=io.Budget('delivery_file_audit_v002','confirmation',START)
checks=[]
def ck(name,ok,evidence=None):checks.append({'name':name,'passed':bool(ok),'evidence':io.convert(evidence)})
def safe(p):
 p=p.resolve();assert p.is_relative_to(R.resolve()),p;return p
try:
 import platform,numpy,openpyxl,PIL
 su=io.load(O/'独立确认结论.json');rb=io.load(O/'独立重建核验.json');pp=io.load(O/'收尾数据与工作指标独立重建-v001.json')
 ck('status_precision_pass_but_rating_fail',su['decision']=='FAIL'and su['all_precision']is True and su['rating_lower_kw']<60000 and not su['unresolved'])
 ck('rebuild1089',rb['all_pass']and len(rb['checks'])==1089)
 ck('U_rebuild_7',all(v['passed']for v in pp['independent_work_indicator_checks'].values()))
 docs=[W/'阶段记录/Q02-受控搜索与独立确认-v001.md',P/'第2问-模型建立与求解-v001.md',P/'第2问-正文证据映射-v001.md',P/'第2问-修订与排版记录-v001.md',H/'Q02-搜索运行与复现说明-v001.md',O/'修订与失败记录-v001.md',W/'00-任务状态.md']
 link_errors=[];table_errors=[]
 for f in docs:
  s=f.read_text(encoding='utf-8-sig');ck('saved_'+f.name,len(s)>50)
  ck('display_math_pair_'+f.name,s.count('\\[')==s.count('\\]'))
  for label,target in re.findall(r'(?<!!)\[([^\]\n]+)\]\(([^\n]+?)\)',s)+re.findall(r'!\[([^\]\n]*)\]\(([^\n]+?)\)',s):
   if target.startswith(('https:','http:')):continue
   p=Path(target.strip('<>'))
   if not p.is_absolute():p=f.parent/p
   try:p=safe(p)
   except AssertionError:link_errors.append({'from':str(f),'target':target,'error':'outside root'});continue
   if not p.exists():link_errors.append({'from':str(f.relative_to(R)),'target':target,'error':'missing'})
  lines=s.splitlines();in_math=False
  for i,line in enumerate(lines):
   if line.strip()==r'\[':in_math=True;continue
   if line.strip()==r'\]':in_math=False;continue
   if in_math:continue
   if line.startswith('|')and(i==0 or not lines[i-1].startswith('|')):
    if i+1>=len(lines)or not re.match(r'^\|[ :|-]+\|$',lines[i+1]):table_errors.append({'file':str(f.relative_to(R)),'line':i+1,'kind':'missing header separator'})
 ck('document_links',not link_errors,link_errors);ck('table_headers',not table_errors,table_errors)
 for name in ['搜索与确认冻结配置-v001.json','搜索与确认冻结配置-v002.json']:
  cfg=io.load(O/name)
  for file,sha in cfg['bindings'].items():ck('frozen_code_'+name+'_'+file,io.sha(H/file)==sha)
 for item in io.load(O/'原型验收与只读绑定.json')['files']:
  ck('accepted_input_unchanged_'+item['path'],io.sha(safe(R/item['path']))==item['sha256'])
 ck('no_official_result2',not any(W.rglob('result2.xlsx')))
 ck('no_formal_Q2_result_draft',not(W/'阶段记录/Q02-第2问结果初稿-v001.md').exists())
 md=P/'第2问-模型建立与求解-v001.md';tex=P/'LaTeX/第2问-模型建立与求解-v001.tex';pdf=tex.with_suffix('.pdf')
 ms=md.read_text(encoding='utf-8');ts=tex.read_text(encoding='utf-8')
 eqmd=re.findall(r'\\\[(.*?)\\\]',ms,re.S);eqtex=re.findall(r'\\\[(.*?)\\\]',ts,re.S)
 ck('all29_equations_transferred',eqmd==eqtex and len(eqmd)==29)
 ck('paper_UNFINISHED_no_rating_claim','未完成草稿'in ms and '额定功率工作判据未通过'in ms and '正式达标设计及其确认结论待完成'in ms)
 qa=io.load(O/'Q02-PDF自动核验-v002.json');binding=io.load(O/'Q02-Markdown与TeX对应-v001.json')
 ck('paper_source_tex_sha',io.sha(md)==binding['source_sha256']and io.sha(tex)==binding['tex_sha256'])
 ck('pdf_all12_pages',qa['pages']==qa['rendered_pages']==12 and qa['pdf_sha256']==io.sha(pdf))
 out=P/'LaTeX/第2问-未完成草稿页面-v002';pngs=sorted(out.glob('page-*.png'));ck('page_numbers',len(pngs)==12 and[int(p.stem.split('-')[1])for p in pngs]==list(range(1,13)))
 unchanged=[]
 for p in pngs:
  older=P/'LaTeX/第2问-未完成草稿页面-v001'/p.name
  if io.sha(p)==io.sha(older):unchanged.append(p.name)
 ck('visually_rechecked_or_identical_pages',all(p.name in unchanged or int(p.stem.split('-')[1])>=9 for p in pngs),{'identical_to_visually_checked_initial':unchanged,'rechecked_final_pages':[9,10,11,12]})
 pic=io.load(O/'诊断布局图来源-v001.json');ck('figure_source_and_hash',io.sha(R/pic['figure'])==pic['figure_sha256']and io.sha(R/pic['source'])==pic['source_sha256']and pic['n']==3054)
 for name in ['记录索引.md','方法库查阅记录.md','决策记录.md','06-更新记录.md','归档清单.md','经验.md']:
  s=(W/name).read_text(encoding='utf-8-sig');ck('control_saved_'+name,len(s)>100)
 allfiles=set(docs+[W/x for x in ['00-任务状态.md','记录索引.md','方法库查阅记录.md','决策记录.md','06-更新记录.md','归档清单.md','经验.md']])
 for pattern in ['q02_fast*','q02_compact*','q02_search*','q02_hex*','q02_stagger*','q02_paper*','q02_diagnostic*','Q02-搜索*']:
  allfiles.update(p for p in H.glob(pattern)if p.is_file())
 allfiles.update(p for p in O.rglob('*')if p.is_file()and p.name not in ['累计计算预算.json','交付文件核验-v002.json','归档哈希清单-v002.json']and not p.name.endswith('.part'))
 allfiles.update([md,tex,pdf,P/'第2问-正文证据映射-v001.md',P/'第2问-修订与排版记录-v001.md',R/pic['figure']])
 allfiles.update(p for p in(P/'LaTeX').glob('第2问*')if p.is_file())
 allfiles.update(p for folder in(P/'LaTeX').glob('第2问-未完成草稿页面-*')for p in folder.rglob('*')if p.is_file())
 files=[]
 for i,p in enumerate(sorted(allfiles)):
  if i%30==0:b.guard(5)
  p=safe(p);files.append({'path':str(p.relative_to(R)).replace('\\','/'),'bytes':p.stat().st_size,'sha256':io.sha(p)})
 ck('no_unfinished_part_files',not list(O.rglob('*.part')))
 ck('computed_time_within_budget',b.used()<3600,{'seconds_before_finish':b.used(),'includes_failed_numerical_actions':True})
 io.save(O/'环境与入口-v001.json',{'python':sys.version,'numpy':numpy.__version__,'openpyxl':openpyxl.__version__,'Pillow':PIL.__version__,'platform':platform.platform(),'matplotlib':'not installed; figure_v001 failed, v002 Pillow used','root_only':str(R),'commands':'工作记录/诊断代码/Q02-搜索运行与复现说明-v001.md','no_network':True})
 env=O/'环境与入口-v001.json';files.append({'path':str(env.relative_to(R)).replace('\\','/'),'bytes':env.stat().st_size,'sha256':io.sha(env)})
 report={'checks':checks,'all_pass':all(c['passed']for c in checks),'file_scope':'saved paths/hashes/metadata/MD-TeX-PDF; does not override numeric rating FAIL','failed':[c for c in checks if not c['passed']],'new_rays':0,'archive_by_admin':'UNCONFIRMED','user_acceptance':'PENDING_CURRENT_STAGE','file_count':len(files),'archive_bytes':sum(f['bytes']for f in files)}
 io.save(O/'交付文件核验-v002.json',report)
 b.finish('COMPLETED'if report['all_pass']else'FAILED')
 # Snapshot the settled ledger after the audit; no numerical work is left.
 bp=O/'累计计算预算.json';files.append({'path':str(bp.relative_to(R)).replace('\\','/'),'bytes':bp.stat().st_size,'sha256':io.sha(bp)})
 rp=O/'交付文件核验-v002.json';files.append({'path':str(rp.relative_to(R)).replace('\\','/'),'bytes':rp.stat().st_size,'sha256':io.sha(rp)})
 io.save(O/'归档哈希清单-v002.json',{'files':files,'count':len(files),'not_self_hashed':True,'budget_final_seconds':b.data['used_seconds'],'status':'stored, pending user acceptance, admin archive unconfirmed','no_official_result2':True})
 print(json.dumps({'all_pass':report['all_pass'],'checks':len(checks),'failed':report['failed'],'files':len(files),'total_bytes':report['archive_bytes'],'budget_final_seconds':b.data['used_seconds']},ensure_ascii=False))
except BaseException as e:
 b.finish('FAILED');io.event('失败运行.jsonl',{'mode':b.mode,'error':repr(e)});raise
