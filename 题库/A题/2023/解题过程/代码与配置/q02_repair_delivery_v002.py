"""File/MD/PDF binding audit, separate from optical/numerical verification."""
from pathlib import Path
import json,hashlib,re,urllib.parse
H=Path(__file__).resolve().parent;W=H.parent;ROOT=W.parent;O=W/'诊断结果/Q02-修复-v001'
def load(p):return json.loads(p.read_text(encoding='utf-8'))
def sha(p):
 h=hashlib.sha256()
 with p.open('rb')as f:
  for b in iter(lambda:f.read(1048576),b''):h.update(b)
 return h.hexdigest()
checks=[]
deferred_output_links=[]
own_outputs={(O/'交付文件核验-v002.json').resolve(),(O/'交付哈希清单-v002.json').resolve()}
def check(name,ok,evidence=None):checks.append({'name':name,'pass':bool(ok),'evidence':evidence})
cfg=load(O/'搜索与确认冻结配置-v004.json');fr=load(O/'最终拟提交候选冻结.json');num=load(O/'独立确认结论.json');rb=load(O/'独立重建核验.json');uv=load(O/'独立工作指标重建.json');rp=load(O/'实际Excel同源重放核验.json')
check('numeric_gates_are_separate_and_passed',num['decision']=='PASS'and rb['all_pass']and uv['all_pass']and rp['all_pass'])
for name,digest in cfg['bindings'].items():check('frozen_source_'+name,sha(H/name)==digest)
check('actual_excel_exact_frozen',sha(O/'result2.xlsx')==fr['excel_sha256'])
qa=load(O/'Q02-修复稿PDF自动核验-v001.json');visual=load(O/'PDF实际页面检查-v001.json')
check('all_pages_rendered',qa['pages']==qa['rendered_pages']and qa['page_numbers']==list(range(1,qa['pages']+1)))
check('pdf_matches_render',sha(ROOT/qa['pdf'])==qa['pdf_sha256'])
check('visual_evidence_matches_pdf',visual['pdf_sha256']==qa['pdf_sha256']and visual['all_pages_inspected']and visual['all_pass'])
check('paper_and_tex_bound',sha(ROOT/qa['source'])==qa['source_sha256']and sha(ROOT/qa['tex'])==qa['tex_sha256'])
docs=[W/'阶段记录/Q02-可行性修复与独立确认-v001.md',W/'阶段记录/Q02-第2问结果初稿-v001.md',W/'论文/第2问-模型建立与求解-v002.md',W/'论文/第2问-正文证据映射-v002.md',W/'论文/第2问-修订与排版记录-v002.md']
docs += [W/n for n in ['00-任务状态.md','记录索引.md','方法库查阅记录.md','决策记录.md','06-更新记录.md','归档清单.md','经验.md']]
for p in docs:
 check('document_exists_'+p.name,p.is_file())
 text=p.read_text(encoding='utf-8');math_mode=False;fence=False
 for i,line in enumerate(text.splitlines()):
  if line.lstrip().startswith('```'):fence=not fence
  if fence:continue
  if line.strip()in ['\\[','$$']:math_mode=not math_mode;continue
  if line.strip()=='\\]':math_mode=False;continue
  if not math_mode and line.startswith('| ')and i and not text.splitlines()[i-1].startswith('|'):
   following=text.splitlines()[i+1]if i+1<len(text.splitlines())else''
   check(p.name+':table_header_'+str(i+1),following.startswith('|')and bool(re.search(r'-{3}',following)))
 for target in re.findall(r'!?\[[^\]]*\]\(([^\n]*?)\)',text):
  target=target.strip('<>')
  if target.startswith(('http:','https:','#','mailto:')):continue
  target=urllib.parse.unquote(target.split('#')[0])
  if not target:continue
  q=Path(target)if Path(target).is_absolute()else p.parent/target
  if q.resolve() in own_outputs:
   deferred_output_links.append((p.name+':link:'+target,q))
  else:check(p.name+':link:'+target,q.exists())
paper=(W/'论文/第2问-模型建立与求解-v002.md').read_text(encoding='utf-8')
check('no_result_placeholders',not any(x in paper for x in ['待本轮计算结果填写','本轮冻结设计的确认结论待完成','本稿不构成第2问正式结果交付','待本轮修复搜索和独立确认完成后填写']))
numeric_files=['table1.csv','table2.csv','table3.csv','结果数据.json','实际候选比较.json','图表生成记录.json']
for n in numeric_files:check('required_evidence_'+n,(O/n).exists())
paths=set(docs)
paths.update(p for p in O.rglob('*')if p.is_file()and p.name not in ['交付文件核验-v002.json','交付哈希清单-v002.json','累计计算预算.json'])
paths.update(p for p in H.glob('q02_repair_*.py'))
paths.update(p for p in (W/'论文/图表/Q02-v002').rglob('*')if p.is_file())
paths.update([ROOT/qa['tex'],ROOT/qa['pdf']])
paths.update(ROOT/p['file']for p in qa['page_files'])
manifest=[{'path':p.relative_to(ROOT).as_posix(),'bytes':p.stat().st_size,'sha256':sha(p)}for p in sorted(paths)]
(O/'交付哈希清单-v002.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
(O/'交付文件核验-v002.json').write_text(json.dumps({'status':'in_progress_final_output_link_checks','all_pass':None},ensure_ascii=False)+'\n',encoding='utf-8')
for name,path in deferred_output_links:check(name,path.is_file())
report={'all_pass':all(c['pass']for c in checks),'checks':checks,'file_count':len(manifest),'scope':'File/render/source binding only; numerical and physical evidence are separate','numerical_verification':{'confirmation':num['decision'],'independent_point':rb['all_pass'],'independent_U':uv['all_pass'],'excel_replay':rp['all_pass']}}
(O/'交付文件核验-v002.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
print(json.dumps({'all_pass':report['all_pass'],'checks':len(checks),'files':len(manifest),'failed':[c for c in checks if not c['pass']]},ensure_ascii=False))
