"""Offline S03 file validation and a once-created blind-freeze candidate.

Large statistics remain in their original authorized workspace directories.
This script neither evaluates optics nor formally freezes an accepted paper.
"""
from pathlib import Path
import argparse,datetime,hashlib,json,re,shutil,sys
ROOT=Path(r'C:\Users\admin\OneDrive\Desktop\26国赛-单题盲解区\A-P8C3').resolve()
O=ROOT/'工作记录/论文/全题整合'
PACK=ROOT/'工作记录/冻结候选/盲解-v001'
def sha(p):
    h=hashlib.sha256()
    with p.open('rb')as f:
        for b in iter(lambda:f.read(1024*1024),b''):h.update(b)
    return h.hexdigest()
def local(p):
    p=p.resolve();assert p.is_relative_to(ROOT),p;return p
def load(p):return json.loads(local(p).read_text(encoding='utf-8-sig'))
def save(p,t):
    local(p).parent.mkdir(parents=True,exist_ok=True);p.write_text(t,encoding='utf-8')
def stamp():return datetime.datetime.now().astimezone().isoformat()
def verify():
    checks=[]
    def check(name,ok,detail=None):checks.append({'name':name,'pass':bool(ok),'detail':detail})
    old=load(O/'整合与参考学习前基线-v001/baseline.json')
    for f in old['files']:check('unchanged accepted baseline: '+f['path'],sha(ROOT/f['path'])==f['sha256'])
    s=load(O/'结果与来源-v001.json');e=load(O/'实际搜索比较与检验证据-v001.json')
    check('source registry validated',s['all_pass'])
    for name,q in list(s['questions'].items())+[('paired',s['paired_baseline'])]:
        for key,digest in q['sha256'].items():
            if key in q['paths']:check(f'current source {name}/{key}',sha(ROOT/q['paths'][key])==digest)
    check('paired delta source unchanged',sha(ROOT/s['comparison']['path'])==s['comparison']['sha256'])
    gen=load(O/'正文生成证据-v001.json');con=load(O/'Markdown与LaTeX对应-v001.json');pdf=load(O/'PDF自动核验-v001.json')
    for suffix,k in [('md','source_sha256'),('tex','tex_sha256'),('pdf','pdf_sha256')]:
        check('render current '+suffix,sha(O/f'完整论文-v001.{suffix}')==pdf[k])
    check('generator manuscript binding',gen['paper_sha256']==pdf['source_sha256'])
    check('converter tex binding',con['tex_sha256']==pdf['tex_sha256'])
    check('source and search generation binding',gen['source_registry_sha256']==sha(O/'结果与来源-v001.json') and gen['search_registry_sha256']==sha(O/'实际搜索比较与检验证据-v001.json'))
    check('complete raster coverage',pdf['pages']==pdf['rendered_pages']==20 and pdf['page_numbers']==list(range(1,21)))
    visual=load(O/'PDF人工核验-v001.json');check('all pages actually inspected or identical raster inheritance',visual['status']=='PASS' and visual['pdf_sha256']==pdf['pdf_sha256'] and visual['page_count']==pdf['pages'])
    nums=load(O/'正文数值独立核验-v001.json')
    check('independent table checks',nums.get('all_pass',nums.get('status')=='PASS'),nums.get('check_count',len(nums.get('checks',[]))))
    body=(O/'完整论文-v001.md').read_text(encoding='utf-8')
    tags=re.findall(r'\\tag\{(\d+)\}',body)
    check('global equation ids',tags==[str(i)for i in range(1,30)])
    captions=re.findall(r'^表(\d+)\s',body,re.M)
    check('global table ids by occurrence',captions==[str(i)for i in range(1,13)])
    check('no unresolved author tokens',not re.search(r'@[A-Z0-9_]+@',body))
    check('math delimiters',body.count(r'\[')==body.count(r'\]') and body.count(r'\(')==body.count(r'\)'))
    log=(O/'完整论文-v001.log').read_text(encoding='utf-8',errors='replace')
    check('no missing glyph/overflow/compile failure',not re.search('Missing character|Overfull|Underfull|Fatal error|Emergency stop',log))
    check('Q3 small margin retained','12.45 kW' in body and '0.0207%' in body)
    check('two R027 experiments retained','不同随机样本' in body and '旧第2问R027确认数据' in body)
    check('NA handling and finite domains retained','无证书的该状态仍为数值未决' in body and r'Z\in\{76,84\}' in body)
    check('all final source numeric/rating states retained',all(q['quality'].get('formal_ready',True)for q in s['questions'].values()))
    for f in gen['figures']:check('current figure: '+f['file'],sha(ROOT/f['file'])==f['sha256'])
    links=[]
    for p in [*O.glob('*.md'),ROOT/'工作记录/论文/参考论文写作学习-v001.md',ROOT/'工作记录/论文/参考写作应用对照-v001.md']:
        for match in re.finditer(r'!?\[[^\]\n]*\]\(([^\n]+?)\)',p.read_text(encoding='utf-8')):
            raw=match.group(1).strip('<>').split('#')[0]
            if not raw:continue
            if re.match(r'^[a-z]+://',raw,re.I):
                links.append({'source':p.relative_to(ROOT).as_posix(),'target':raw,'external_url_not_fetched':True});continue
            target=Path(raw);target=target if target.is_absolute()else p.parent/target
            check('document local link',target.resolve().is_relative_to(ROOT) and target.exists(),{'source':p.relative_to(ROOT).as_posix(),'target':raw})
            links.append({'source':p.relative_to(ROOT).as_posix(),'target':target.resolve().relative_to(ROOT).as_posix()})
    result={'kind':'S03_FILE_AND_DOCUMENT_VALIDATION','created_at':stamp(),'all_pass':all(x['pass']for x in checks),'check_count':len(checks),'checks':checks,'local_link_count':sum('external_url_not_fetched'not in x for x in links),'links':links,'paper_sha256':sha(O/'完整论文-v001.md'),'pdf_sha256':sha(O/'完整论文-v001.pdf'),'new_optical_rays':0,'physical_model_independently_validated':False,'reference_original_learning':'待材料','limits':'独立表值核对、既有来源及清单字节核验、PDF视觉检查。不是新的三问光学或物理验证。'}
    save(O/'文件与整合一致性核验-v001.json',json.dumps(result,ensure_ascii=False,indent=2))
    assert result['all_pass'],json.dumps([x for x in checks if not x['pass']],ensure_ascii=False)
    return {'all_pass':True,'checks':len(checks),'links':result['local_link_count']}

def package():
    assert not PACK.exists(),'Candidate already formed or partial assembly retained: inspect; never overwrite'
    qa=load(O/'文件与整合一致性核验-v001.json');assert qa['all_pass']
    assert sha(O/'完整论文-v001.md')==qa['paper_sha256'] and sha(O/'完整论文-v001.pdf')==qa['pdf_sha256']
    selected=set();raw=set();source=load(O/'结果与来源-v001.json');search=load(O/'实际搜索比较与检验证据-v001.json')
    def add(p):
        p=local(p)
        if p.is_file():selected.add(p)
    # Preserve workspace-relative hierarchy, so included MD/TeX image links work after movement.
    for p in O.iterdir():
        if p.is_file() and p.suffix in {'.md','.json','.tex','.pdf','.log'}:add(p)
    for p in (O/'图表').glob('*'):add(p)
    final_render=ROOT/load(O/'PDF自动核验-v001.json')['render_directory']
    for p in final_render.glob('*'):add(p)
    for rel in ['AGENTS.md','工作记录/论文/写作规范-v001.md','工作记录/论文/参考论文写作学习-v001.md','工作记录/论文/参考写作应用对照-v001.md','工作记录/诊断结果/Q03-实施-v001/边界事件记录-v001.md']:
        add(ROOT/rel)
    for q in [*source['questions'].values(),source['paired_baseline']]:
        for key,rel in q['paths'].items():
            p=local(ROOT/rel)
            if p.is_file():add(p)
            elif key=='statistics_directory':
                for f in p.iterdir():
                    if f.suffix=='.npz':raw.add(local(f))
                    elif f.suffix=='.json':add(f)
    for p in (ROOT/'工作记录/诊断结果/Q01-全场-v001/initial').glob('*.npz'):raw.add(local(p))
    # The source registries carry relative paths throughout; copy their small input evidence.
    def walk(v):
        if isinstance(v,dict):
            for x in v.values():walk(x)
        elif isinstance(v,list):
            for x in v:walk(x)
        elif isinstance(v,str) and v.replace('\\','/').startswith('工作记录/') and len(v)<240:
            p=ROOT/v
            if p.is_file() and p.suffix.lower()in{'.json','.jsonl','.md','.csv','.xlsx','.py'}:add(p)
    walk(source);walk(search)
    for folder in ['方法库','补充资料','附件']:
        for p in (ROOT/folder).rglob('*'):
            if p.is_file():add(p)
    add(ROOT/'题目.pdf')
    for p in (ROOT/'工作记录/诊断代码').iterdir():
        if p.is_file()and p.suffix.lower()in{'.py','.json','.ps1','.md'}:add(p)
    add(O/'整合与参考学习前基线-v001/baseline.json')
    # Every omitted target linked from copied Markdown is explicitly indexed as an original dependency.
    omitted=set(raw)
    for p in list(selected):
        if p.suffix!='.md':continue
        for m in re.finditer(r'!?\[[^\]\n]*\]\(([^\n]+?)\)',p.read_text(encoding='utf-8-sig')):
            v=m.group(1).strip('<>').split('#')[0]
            if not v or re.match(r'^[a-z]+://',v,re.I):continue
            t=Path(v);t=local(t if t.is_absolute() else p.parent/t)
            if t.is_file() and t not in selected:omitted.add(t)
    PACK.mkdir(parents=True)
    entries=[]
    for p in sorted(selected):
        rel=p.relative_to(ROOT);dest=local(PACK/rel);dest.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(p,dest)
        h=sha(p);assert sha(dest)==h
        entries.append({'path':rel.as_posix(),'bytes':dest.stat().st_size,'sha256':h,'copied_exact':True})
    dependencies=[]
    for p in sorted(omitted):
        dependencies.append({'workspace_relative_path':p.relative_to(ROOT).as_posix(),'bytes':p.stat().st_size,'sha256':sha(p),'copied':False,'role':'原始随机统计，重建需要'if p in raw else'既有追溯证据或单问原版'})
    dependency={'created_at':stamp(),'path_base':'original anonymous workspace root, not candidate root','self_contained_for_reading':True,'self_contained_for_raw_statistic_rebuild':False,'files':dependencies,'bytes':sum(x['bytes']for x in dependencies),'optical_rerun_authorized':False}
    save(PACK/'未复制依赖清单-v001.json',json.dumps(dependency,ensure_ascii=False,indent=2))
    save(PACK/'README.md','# 盲解冻结候选 v001\n\n**完整论文与候选包待用户整体验收；不是正式盲解冻结，管理员归档未确认。参考原文学习待材料，未阅读指定参考论文。**\n\n## 阅读入口\n\n- [完整论文PDF](工作记录/论文/全题整合/完整论文-v001.pdf)（20页）\n- [完整论文Markdown](工作记录/论文/全题整合/完整论文-v001.md)与[本地LaTeX](工作记录/论文/全题整合/完整论文-v001.tex)\n- [result2.xlsx](工作记录/诊断结果/Q02-修复-v001/result2.xlsx)、[result3.xlsx](工作记录/诊断结果/Q03-实施-v001/delivery/result3.xlsx)\n- [唯一结果来源表](工作记录/论文/全题整合/结果与来源表-v001.md)、[正文证据映射](工作记录/论文/全题整合/完整论文证据映射-v001.md)\n- [可复现说明](工作记录/论文/全题整合/全题可复现说明-v001.md)、[边界与局限](工作记录/论文/全题整合/盲解边界与局限-v001.md)\n\n## 搬运与校验边界\n\n保持工作区相对目录结构，包内论文/图表/正式清单可独立阅读；对应TeX可在具备本地中文字体、XeLaTeX和相应包的环境中编译，不承诺跨机器编译自动一致。代码与配置作为版本证据一并保存，不授权在旧输出位置运行。\n\n大型原始统计以及部分旧追溯文件未复制，见[未复制依赖清单](未复制依赖清单-v001.json)，其中路径以原匿名工作区根为准。包不是能够独立重建原始统计或重新计算光学的自包含包。复制文档中指向这部分原目录的链接只有原工作区存在时可访问；不能称这些依赖已包含。完整论文自身图表链接为包内相对路径。\n\n文件清单-v001.json列出所有包内文件的SHA-256，不含该清单自身及SHA256SUMS.txt；SHA256SUMS.txt补入JSON清单哈希而不自引用。形成后不得原地修改；后续修订另建版本。原独立单问成果、失败确认和越界事件没有改写。\n')
    # Add non-self-referential entries for package-owned readme/dependency metadata.
    for name in ['README.md','未复制依赖清单-v001.json']:
        p=PACK/name;entries.append({'path':name,'bytes':p.stat().st_size,'sha256':sha(p),'copied_exact':False})
    manifest={'candidate':'盲解-v001','formed_at':stamp(),'status':'完整论文与冻结候选待用户整体验收','formal_blind_freeze':False,'administrator_archived':False,'reference_original_read':False,'reference_learning':'待材料','path_base':'candidate package root','files':entries,'file_count_excluding_manifests':len(entries),'copied_bytes':sum(x['bytes']for x in entries),'excluded_self_files':['文件清单-v001.json','SHA256SUMS.txt'],'external_dependency_count':len(dependencies),'external_dependency_bytes':dependency['bytes'],'portable_for_reading':True,'portable_for_complete_recalculation':False}
    save(PACK/'文件清单-v001.json',json.dumps(manifest,ensure_ascii=False,indent=2))
    lines=[x['sha256']+'  '+x['path']for x in entries]+[sha(PACK/'文件清单-v001.json')+'  文件清单-v001.json']
    save(PACK/'SHA256SUMS.txt','\n'.join(lines)+'\n')
    verified=check_package()
    receipt={'created_at':stamp(),'package':PACK.relative_to(ROOT).as_posix(),'status':'CANDIDATE_READY_NOT_FORMALLY_FROZEN','file_count':len(entries)+2,'bytes_excluding_manifest_files':manifest['copied_bytes'],'external_dependency_count':len(dependencies),'external_dependency_bytes':dependency['bytes'],'manifest_sha256':sha(PACK/'文件清单-v001.json'),'checksum_file_sha256':sha(PACK/'SHA256SUMS.txt'),'all_hashes_pass':verified['all_hashes_pass'],'same_excel_bytes':True,'reference_learning':'待材料','paper_user_accepted':False,'administrator_archived':False}
    save(O/'冻结候选交付核验-v001.json',json.dumps(receipt,ensure_ascii=False,indent=2))
    return receipt

def check_package():
    m=load(PACK/'文件清单-v001.json')
    expected={x['path']for x in m['files']}|set(m['excluded_self_files'])
    actual={p.relative_to(PACK).as_posix() for p in PACK.rglob('*')if p.is_file()}
    assert actual==expected, {'extra':list(actual-expected),'missing':list(expected-actual)}
    for x in m['files']:assert sha(PACK/x['path'])==x['sha256'],x['path']
    for line in (PACK/'SHA256SUMS.txt').read_text(encoding='utf-8').splitlines():
        h,p=line.split('  ',1);assert sha(PACK/p)==h,p
    return {'all_hashes_pass':True,'files':len(actual)}
if __name__=='__main__':
    assert Path.cwd().resolve()==ROOT
    p=argparse.ArgumentParser();p.add_argument('mode',choices=['verify','package','check-package']);args=p.parse_args()
    print(json.dumps({'verify':verify,'package':package,'check-package':check_package}[args.mode](),ensure_ascii=False))
