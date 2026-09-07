"""Q02 preparation evidence only: local file hashes and document checks; no geometry/optics/optimization execution."""
from pathlib import Path
import json, hashlib, re
from datetime import datetime
ROOT=Path.cwd().resolve()
OUT=ROOT/'工作记录/诊断结果/Q02-准备-v001'
OUT.mkdir(exist_ok=True)
def inside(p):
 p=p.resolve()
 if not p.is_relative_to(ROOT): raise ValueError('Outside authorized root')
 return p
def sha(p): return hashlib.sha256(inside(p).read_bytes()).hexdigest()
def write(name,x): (OUT/name).write_text(json.dumps(x,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
full_read=['方法库/原文选段/D01-建模质量观念.md','方法库/原文选段/D03-随机模拟基本思想.md','方法库/M01-输入假设与适用范围-v001.md','方法库/M02-空间方向反射与有限几何-v001.md','方法库/M03-条件能量比与分布归一化-v001.md','方法库/M04-平均权重与非线性汇总-v001.md','方法库/M05-数值误差验证与复现-v001.md','补充资料/P01-角尺度来源与边界-v001.md','补充资料/P02-方向分布与待选假设-v001.md']
records=[]
for folder in ['方法库','补充资料']:
 manifest=json.loads((ROOT/folder/'manifest-v001.json').read_text(encoding='utf-8-sig'))
 for f in manifest['files']:
  rel=folder+'/'+f['path']; p=inside(ROOT/rel)
  records.append({'path':rel,'exists':p.is_file(),'version':f['version'],'content_screened':f['content_screened'],'allowed_scope':f['allowed_scope'],'sha256':sha(p) if p.is_file() else None,'hash_match':p.is_file() and sha(p)==f['sha256'],'read_scope_this_round':'full local text' if rel in full_read else 'metadata/hash only; prior reading not counted again'})
bindings=[]
for rel in ['AGENTS.md','题目.pdf','附件/附件01.xlsx','附件/附件02.xlsx','工作记录/阶段记录/S01-题目理解-v001.md','工作记录/阶段记录/S01-补充澄清-v001.md','工作记录/阶段记录/S02-方法学习与第1问知识准备-v001.md','工作记录/阶段记录/Q01-方案构造-v001.md','工作记录/阶段记录/Q01-建模与原型验证-v001.md','工作记录/阶段记录/Q01-全场初算与数值精度验证-v001.md','工作记录/阶段记录/Q01-第1问结果初稿-v001.md','工作记录/阶段记录/Q01-验收收尾与论文写作-v001.md','工作记录/论文/第1问-模型建立与求解-v001.md','工作记录/论文/LaTeX/第1问-模型建立与求解-v001.tex','工作记录/论文/LaTeX/第1问-模型建立与求解-v001.pdf','工作记录/论文/第1问-正文证据映射-v001.md','工作记录/诊断代码/q01_core_v003.py','工作记录/诊断代码/q01_full_run_v002.py','工作记录/诊断代码/q01_full_summary_v002.py','工作记录/诊断代码/Q01-全场配置-v001.json','工作记录/诊断结果/工作簿结构-v001.json','工作记录/诊断结果/题面公式与表格核对-v001.md']:
 p=inside(ROOT/rel); bindings.append({'path':rel,'bytes':p.stat().st_size,'sha256':sha(p)})
old=json.loads((ROOT/'工作记录/诊断结果/Q01-论文收尾-v001/论文归档哈希清单-v001.json').read_text(encoding='utf-8-sig'))
oldmap={r['path']:r['sha256'] for r in old['files']}
preserved=[{'path':r['path'],'matches_accepted_manifest':r['sha256']==oldmap[r['path']]} for r in bindings if r['path'] in oldmap]
proof={'date':datetime.now().astimezone().isoformat(),'scope':'files, whitelist versions, hashes only; no new optical samples or candidate field','methods':records,'bindings':bindings,'accepted_writing_preservation':preserved,'all_method_files_match':all(r['hash_match'] and r['content_screened'] for r in records),'all_compared_accepted_files_preserved':all(r['matches_accepted_manifest'] for r in preserved)}
write('资料与输入绑定-v001.json',proof)
print(json.dumps({'method_files':len(records),'full_local_read':len(full_read),'hashes_match':proof['all_method_files_match'],'accepted_files_compared':len(preserved),'preserved':proof['all_compared_accepted_files_preserved']},ensure_ascii=False))
stage=ROOT/'工作记录/阶段记录/Q02-约束梳理与候选方案-v001.md'
if stage.exists():
 docs=[stage]+[ROOT/'工作记录'/n for n in ['00-任务状态.md','记录索引.md','方法库查阅记录.md','决策记录.md','06-更新记录.md','归档清单.md','诊断代码/Q02-准备核验说明-v001.md']]
 # These self-referenced reports are atomic workflow drafts until the final checks below.
 for name in ['交付文件核验-v001.json','本轮文件哈希-v001.json']:
  if not (OUT/name).exists(): write(name,{'status':'in_progress','scope':'not yet validated'})
 links=[]; invalid=[]; tables=[]; maths=[]
 for doc in docs:
  s=doc.read_text(encoding='utf-8-sig')
  for m in re.finditer(r'\[[^\]\n]+\]\(([^)\n]+)\)',s):
   target=m.group(1).strip('<>')
   if re.match(r'^[a-zA-Z]+://',target) or target.startswith('#'): continue
   target=target.split('#',1)[0]
   p=inside(doc.parent/target)
   links.append({'document':str(doc.relative_to(ROOT)),'target':target,'exists':p.exists()})
   if not p.exists(): invalid.append(links[-1])
  if doc==stage:
   lines=s.splitlines()
   for i,line in enumerate(lines[:-1]):
    if line.startswith('|') and re.match(r'^\|(?:\s*:?-+:?\s*\|)+\s*$',lines[i+1]):
     cells=line.strip('|').split('|'); tables.append({'line':i+1,'columns':len(cells),'complete_header':all(c.strip() for c in cells)})
   maths=[s.count('\\[')==s.count('\\]'),s.count('\\(')==s.count('\\)'), '\\\\[' not in s]
 final={'date':datetime.now().astimezone().isoformat(),'scope':'document checks only, not numerical/model verification','links_checked':len(links),'broken_links':invalid,'tables':tables,'math_delimiters':maths,'all_pass':not invalid and all(r['complete_header'] for r in tables) and all(maths) and proof['all_method_files_match'] and proof['all_compared_accepted_files_preserved']}
 write('交付文件核验-v001.json',final)
 write('本轮文件哈希-v001.json',{'files':[{'path':str(p.relative_to(ROOT)),'sha256':sha(p),'bytes':p.stat().st_size} for p in docs+[Path(__file__).resolve(),OUT/'资料与输入绑定-v001.json',OUT/'交付文件核验-v001.json']]})
 print(json.dumps({'document_all_pass':final['all_pass'],'links':len(links),'tables':len(tables),'broken_links':invalid},ensure_ascii=False))