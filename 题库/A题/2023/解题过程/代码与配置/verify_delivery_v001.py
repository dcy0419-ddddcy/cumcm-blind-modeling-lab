"""交付核验：只检查本单题的文件、哈希、引用及已保存诊断，不运行题目求解。"""
from pathlib import Path
import ast
import csv
import hashlib
import json
import re
import sys
from datetime import datetime
from urllib.parse import unquote

sys.stdout.reconfigure(encoding='utf-8')
ROOT=Path(__file__).resolve().parents[2]
WORK=ROOT/'工作记录'
OUT=WORK/'诊断结果'/'交付核验-v001.json'
issues=[]
required=['00-任务状态.md','记录索引.md','方法库查阅记录.md','阶段记录/S00-材料审计-v001.md','阶段记录/S01-题目理解-v001.md','06-更新记录.md','归档清单.md','决策记录.md']
for name in required:
    p=WORK/name
    if not p.is_file() or not p.read_text(encoding='utf-8').strip():issues.append(f'缺少正式记录：{name}')

inventory=json.loads((WORK/'诊断结果'/'原始材料清单-v001.json').read_text(encoding='utf-8'))
hash_checks=[]
for item in inventory:
    p=(ROOT/item['path']).resolve()
    if not p.is_relative_to(ROOT):raise RuntimeError('输入文件越界')
    digest=hashlib.sha256(p.read_bytes()).hexdigest()
    ok=digest==item['sha256'] and p.stat().st_size==item['bytes']
    hash_checks.append({'path':item['path'],'unchanged':ok,'sha256':digest})
    if not ok:issues.append('原件已变更：'+item['path'])

pdf=json.loads((WORK/'诊断结果'/'题目结构-v001.json').read_text(encoding='utf-8'))
audit=json.loads((WORK/'诊断结果'/'附件数据诊断-v001.json').read_text(encoding='utf-8'))
coord=next(b['sheets'][0] for b in audit if b['file']=='附件/附件03.xlsx')
with (WORK/'诊断结果'/'坐标诊断明细-v001.csv').open(encoding='utf-8-sig',newline='') as f:
    details=list(csv.DictReader(f))
checks={'pdf_pages_4':pdf['page_count']==4,'rendered_pages_4':all((WORK/'诊断结果'/'题目页面'/f'page-{i}.png').is_file() for i in range(1,5)), 'coordinate_rows_1745':coord['coordinate_count']==len(details)==1745,'coordinate_missing_0':coord['empty_cells_below_header']==0,'coordinate_duplicates_0':len(coord['duplicate_coordinate_groups'])==0,'radius_checks_clear':not coord['radius_below_100_rows'] and not coord['radius_above_350_rows'],'spacing_checks_clear':coord['pairs_at_or_below_11_m']==0,'template_hashes_equal':inventory[-3]['sha256']==inventory[-2]['sha256'],'no_result_workbooks':not (ROOT/'result2.xlsx').exists() and not (ROOT/'result3.xlsx').exists()}
for k,v in checks.items():
    if not v:issues.append('核验不通过：'+k)
for p in (WORK/'诊断代码').glob('*.py'):
    ast.parse(p.read_text(encoding='utf-8'))

# 先建立自引用的结果文件，再核对文档中的相对文件链接。
OUT.write_text('{}',encoding='utf-8')
link_count=0
for p in WORK.rglob('*.md'):
    content=p.read_text(encoding='utf-8')
    for target in re.findall(r'\]\(([^)]+)\)',content):
        target=unquote(target.strip('<>').split('#')[0])
        if not target:continue
        if re.match(r'^[a-z]+://',target):
            issues.append(f'记录出现远程链接（未访问）：{p.relative_to(ROOT)}')
            continue
        dest=(p.parent/target).resolve()
        link_count+=1
        if not dest.is_relative_to(ROOT):issues.append('文档引用越界：'+str(p.relative_to(ROOT)))
        elif not dest.exists():issues.append(f'失效链接：{p.relative_to(ROOT)} -> {target}')

archive=(WORK/'归档清单.md').read_text(encoding='utf-8')
archive_entries=re.findall(r'^\| `([^`]+)` \|',archive,re.M)
for rel in archive_entries:
    if not (ROOT/rel).is_file():issues.append('归档文件不存在：'+rel)
work_files=[p.relative_to(ROOT).as_posix() for p in WORK.rglob('*') if p.is_file()]
for rel in work_files:
    if rel not in archive_entries:issues.append('归档清单未覆盖：'+rel)
report={'checked_at':datetime.now().astimezone().isoformat(),'scope':'当前单题材料与文件交付核验；不代表用户验收、管理员归档或模型验证','required_markdown_files':required,'original_files':hash_checks,'diagnostic_consistency_checks':checks,'markdown_links_checked':link_count,'archive_entries_checked':len(archive_entries),'work_files_count':len(work_files),'syntax_checks':'两份本轮Python代码已通过ast.parse静态语法检查','issues':issues,'all_checks_passed':len(issues)==0,'files_saved':True,'user_accepted':False,'admin_archived':False}
OUT.write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
print(json.dumps(report,ensure_ascii=False,indent=2))
if issues:sys.exit(1)
