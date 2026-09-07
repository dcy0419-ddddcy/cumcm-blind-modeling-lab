"""Final readback checks for paper artifacts; never invokes the optical model."""
from pathlib import Path
import sys,json,hashlib,re,csv
from datetime import datetime
import numpy as np
from PIL import Image
from pypdf import PdfReader
import PIL,reportlab,pypdf
sys.stdout.reconfigure(encoding='utf-8')
R=Path(__file__).resolve().parents[2];W=R/'工作记录';D=W/'诊断结果/Q01-论文收尾-v001';P=W/'论文';OLD=W/'诊断结果/Q01-全场-v001'
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def read(p):return p.read_text(encoding='utf-8')
checks=[]
def ck(name,ok,detail=None):checks.append({'name':name,'passed':bool(ok),'detail':detail})
# Preserve accepted evidence and all fixed inputs.
previous=json.loads(read(OLD/'归档哈希清单-v002.json')); controls=['00-任务状态.md','记录索引.md','方法库查阅记录.md','决策记录.md','06-更新记录.md','归档清单.md'];allow={'工作记录/'+n for n in controls}
same=0;bad=[]
for x in previous['files']:
 if x['path'] in allow:continue
 p=R/x['path']
 if not p.exists() or sha(p)!=x['sha256']:bad.append(x['path'])
 else:same+=1
ck('accepted_noncontrol_artifacts_unchanged',not bad,{'same':same,'changed':bad})
cfg=json.loads(read(W/'诊断代码/Q01-全场配置-v001.json'))
bad=[name for name,h in cfg['bindings'].items() if name!='AGENTS.md' and sha(R/name)!=h]
ck('frozen_input_code_method_bindings',not bad,bad)
before=W/'诊断结果/AGENTS-逐问写作规则追加前-v001.md';agents=R/'AGENTS.md'
ck('AGENTS_pure_append_and_old_config_binding',agents.read_bytes().startswith(before.read_bytes()) and sha(before)==cfg['bindings']['AGENTS.md'],{'old_sha256':sha(before),'new_sha256':sha(agents),'added_bytes':agents.stat().st_size-before.stat().st_size})
# Independently parse actual manuscript tables and inspect displayed units.
a=json.loads(read(OLD/'汇总与数值核验-v001.json'));pt=np.array(a['point']);U=np.array(a['work_uncertainty_indicator']);md=read(P/'第1问-模型建立与求解-v001.md')
lines=md.splitlines();tables=[];i=0
while i<len(lines):
 if lines[i].startswith('|') and i+1<len(lines) and re.fullmatch(r'\|[\s:|\-]+\|',lines[i+1]):
  rows=[]
  while i<len(lines) and lines[i].startswith('|'):
   cells=[c.strip() for c in lines[i].strip('|').split('|')]
   if not all(re.fullmatch(r':?-+:?',c) for c in cells):rows.append(cells)
   i+=1
  tables.append(rows)
 else:i+=1
ck('six_full_header_tables',len(tables)==6 and all(all(len(row)==len(t[0]) for row in t) for t in tables))
t1=tables[1][1:];t2=tables[2][1:];cells=[]
for m,row in enumerate(t1):
 for j,col in enumerate([0,1,2,3,5]):cells.append(row[j+1]==format(pt[m,col],'.4f'))
for j in range(6):cells.append(t2[0][j]==(format(pt[12,4]/1000,'.3f') if j==4 else format(pt[12,j],'.4f')))
ck('actual_MD_table1_table2_66_cells',len(t1)==12 and len(t2)==1 and len(cells)==66 and all(cells),{'checked':len(cells),'MW_conversion':True})
with (P/'图表/月度结果与工作指标-v001.csv').open(encoding='utf-8-sig',newline='') as f:rr=list(csv.reader(f))
xx=np.array([row[1:] for row in rr[1:]],float)
ck('plot_CSV_full_precision_data_and_U',xx.shape==(12,12) and np.array_equal(xx[:,:6],pt[:12]) and np.array_equal(xx[:,6:],U[:12]))
lo=json.loads(read(D/'低存活全量核查-v002.json'))
with np.load(D/'全组合存活计数-v002.npz',allow_pickle=False) as z:surv=z['survivors'];cap=z['captured']
ck('low_survivor_saved_counts',surv.shape==(60,1745) and int((surv<100).sum())==5 and int(surv.min())==11 and int((surv==0).sum())==0 and np.all(cap<=surv),{'count':int(surv.size),'less100':int((surv<100).sum()),'min':int(surv.min())})
ck('low_audit_source_hashes',all(sha(R/x['path'])==x['sha256'] for x in lo['sources']))
ck('frozen_U_unchanged_in_closure',np.array_equal(np.array(lo['frozen_U']),U))
ext=U+np.array(lo['effect_diameter_bound']);ck('supplement_kept_separate_and_goals',np.array_equal(ext,np.array(lo['supplementary_U_plus_bound'])) and np.all(ext[:,:4]<=.001) and np.all(ext[:,4:]<=.005*abs(pt[:,4:])),{'max_efficiency':float(ext[:,:4].max()),'max_relative_power':float((ext[:,4:]/abs(pt[:,4:])).max()),'strict_joint_bound':False})
# MD/TeX full math verbatim, not inferred from rendered number of pages.
tex=read(P/'LaTeX/第1问-模型建立与求解-v001.tex');math_md=re.findall(r'\\\[(.*?)\\\]',md,re.S);math_tex=re.findall(r'\\\[(.*?)\\\]',tex,re.S)
ck('twenty_math_blocks_verbatim_MD_TeX',len(math_md)==20 and math_md==math_tex)
ck('no_missing_template_or_raw_code_formula', '@@' not in md and '```' not in md and md.count(r'\(')==md.count(r'\)'))
ck('necessary_limitations_in_body',all(x in md for x in ['不是置信区间','物理模型偏差','未加权射线条数','固定的4.65 mrad','年平均','再辐射','示例','0.001','0.5%']))
# PDF gate: reject compiler errors, stale or incomplete images, wrong current hash.
pdf=P/'LaTeX/第1问-模型建立与求解-v001.pdf';pdfa=json.loads(read(D/'PDF自动核验-v002.json'));render=R/pdfa['render_directory'];pages=sorted(render.glob('page-*.png'));npages=len(PdfReader(pdf).pages);log=read(P/'LaTeX/第1问-模型建立与求解-v001.log')
ck('complete_compilation_and_render',not re.search(r'^! ',log,re.M) and npages==13 and npages==len(pages)==pdfa['rendered_pages'] and sha(pdf)==pdfa['pdf_sha256'],{'pdf_pages':npages,'png_pages':len(pages),'pdf_sha256':sha(pdf)})
ck('render_and_text_no_stderr',pdfa['render_stderr_bytes']==pdfa['text_stderr_bytes']==0)
ck('no_tex_overflow_missing_glyphs',not any(x in log for x in ['Overfull','Underfull','Missing character','Infinite glue']))
ck('known_environment_warnings_reported','LaTeX Warning' in log,{'nonblocking_warning':'local CTeX requests newer LaTeX release; no online upgrade','fontset':'Windows'})
text=read(render/'PDF文本.txt')
ck('PDF_end_and_key_results_present',all(x in text for x in ['0.5766','35.249','0.5611','资料说明']) and '\ufffd' not in text)
figs=[]
for p in sorted((P/'图表').glob('图*.png')):
 with Image.open(p) as im:figs.append({'file':str(p.relative_to(R)),'width':im.width,'height':im.height})
ck('two_high_resolution_figures',len(figs)==2 and all(f['width']>=2700 and f['height']>=1620 for f in figs),figs)
# All current local Markdown links resolve inside the authorized root.
docs=[W/n for n in controls]+list(P.glob('*.md'))+[W/'阶段记录/Q01-验收收尾与论文写作-v001.md',W/'经验.md']
links=[];missing=[]
outputs={D/'最终文件核验-v002.json',D/'论文归档哈希清单-v001.json'}
for p in docs:
 for target in re.findall(r'\[[^\]\n]*\]\(([^)\n]+)\)',read(p)):
  if target.startswith(('http:','https:','mailto:')):continue
  t=target.split('#')[0].strip('<>');q=Path(t) if Path(t).is_absolute() else p.parent/t;q=q.resolve()
  allowed=q.is_relative_to(R)
  links.append({'source':str(p.relative_to(R)),'target':target,'inside_workspace':allowed})
  if not allowed or (not q.exists() and q not in outputs):missing.append(links[-1])
ck('current_MD_links_exist_within_workspace',not missing,{'count':len(links),'bad':missing})
for doc,prefix in [('决策记录.md','D'),('06-更新记录.md','U')]:
 ids=[int(x) for x in re.findall(r'^## '+prefix+r'(\d{3})\b',read(W/doc),re.M)];ck('continuous_'+prefix+'_ids',ids==list(range(1,max(ids)+1)),{'last':max(ids)})
ck('stage_saves_no_new_optical_rays',lo['new_optical_rays']==0 and pdfa['new_optical_rays']==0)
audit={'created':datetime.now().astimezone().isoformat(),'scope':'file/presentation consistency and existing saved-data closure; not independent physical validation','checks':checks,'passed':all(c['passed'] for c in checks),'environment':{'python':sys.version,'numpy':np.__version__,'pillow':PIL.__version__,'reportlab':reportlab.Version,'pypdf':pypdf.__version__},'script_sha256':sha(Path(__file__)),'links':links,'new_optical_rays':0}
(D/'最终文件核验-v002.json').write_text(json.dumps(audit,ensure_ascii=False,indent=2),encoding='utf-8')
# Save all current paper artifacts, closure evidence and new code. Manifest excludes itself only.
selected=set(docs)|{R/'AGENTS.md',before,Path(__file__)}
for directory in [P,D]:
 selected.update(p for p in directory.rglob('*') if p.is_file())
for pattern in ['q01_paper_*.py','q01_low_survivors_*.py','第1问-正文模板-v001.md']:selected.update((W/'诊断代码').glob(pattern))
manifest=D/'论文归档哈希清单-v001.json';selected.discard(manifest)
files=[{'path':p.relative_to(R).as_posix(),'bytes':p.stat().st_size,'sha256':sha(p)} for p in sorted(selected)]
manifest.write_text(json.dumps({'created':audit['created'],'scope':'new Q1 writing and closure artifacts plus current controls; accepted full-field inputs remain in prior manifest','files':files,'file_count':len(files),'excludes':'this manifest itself','status':'saved, new paper pending user acceptance, administrator archive unconfirmed'},ensure_ascii=False,indent=2),encoding='utf-8')
assert all(p.exists() for p in outputs)
print(json.dumps({'passed':audit['passed'],'checks':len(checks),'failed':[x for x in checks if not x['passed']],'manifest_files':len(files),'links':len(links)},ensure_ascii=False))
sys.exit(0 if audit['passed'] else 1)