"""Q2 file/link/version check and archive manifest. No optical or layout evaluation."""
from pathlib import Path
import json,hashlib,re,time,sys
ROOT=Path(__file__).resolve().parents[2];W=ROOT/'工作记录';O=W/'诊断结果/Q02-原型-v001'
def read(p):return json.loads(p.read_text(encoding='utf-8'))
def sha(p):
    h=hashlib.sha256()
    with p.open('rb') as f:
        for chunk in iter(lambda:f.read(1048576),b''):h.update(chunk)
    return h.hexdigest()
def write(p,v):p.write_text(json.dumps(v,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
def main():
    start=time.perf_counter();checks=[]
    def check(name,yes,detail=None):
        checks.append({'name':name,'pass':bool(yes),'detail':detail})
    controls=[W/x for x in ['00-任务状态.md','记录索引.md','方法库查阅记录.md','决策记录.md','06-更新记录.md','归档清单.md']]
    docs=[W/'阶段记录/Q02-参数化与几何原型验证-v001.md',W/'诊断代码/Q02-设计与评价接口-v001.md',W/'诊断代码/Q02-原型运行说明-v001.md',O/'修订与失败记录-v001.md']
    check('stage_status', '第2问参数化与几何原型验证完成，待用户验收；完整搜索尚未开始。' in controls[0].read_text(encoding='utf-8'))
    base=read(O/'只读输入基线-v001.json')
    check('unchanged_baseline',all(sha(ROOT/x['path'])==x['sha256'] for x in base['files']),len(base['files']))
    cfg=read(W/'诊断代码/Q02-原型配置-v002.json');rev=read(O/'执行修订-v003.json')
    check('config_fixed_bindings',all(sha(ROOT/x['path'])==x['sha256'] for x in cfg['bindings']))
    check('execution_overlay',sha(ROOT/rev['runner'])==rev['runner_sha256'] and sha(W/'诊断代码/Q02-原型配置-v002.json')==rev['config_sha256'])
    for prefix,file in [('D',W/'决策记录.md'),('U',W/'06-更新记录.md')]:
        ns=[int(x) for x in re.findall(r'^## '+prefix+r'(\d+)\b',file.read_text(encoding='utf-8'),re.M)]
        check(prefix+'_continuous',ns==list(range(1,max(ns)+1)),{'last':max(ns),'count':len(ns)})
    # Deliveries are created before link validation but are not mistaken for numerical evidence.
    output=O/'交付文件核验-v001.json';manifest=O/'归档哈希清单-v001.json'
    if output.exists() or manifest.exists():raise RuntimeError('Preserve file-check version; use a new version')
    write(output,{'status':'IN_PROGRESS'});write(manifest,{'status':'IN_PROGRESS'})
    missing=[];out_of_scope=[];nlinks=0
    for p in docs+controls:
        content=p.read_text(encoding='utf-8')
        for target in re.findall(r'\[[^\]\n]+\]\(([^)\n]+)\)',content):
            target=target.strip('<>')
            if target.startswith(('http:','https:','app:')):continue
            if target.startswith('#'):continue
            target=target.split('#')[0]
            q=(p.parent/target).resolve()
            if not q.is_relative_to(ROOT):out_of_scope.append({'source':str(p),'target':target});continue
            nlinks+=1
            if not q.exists():missing.append({'source':p.relative_to(ROOT).as_posix(),'target':target})
    check('local_links_exist',not missing,{'count':nlinks,'missing':missing})
    check('links_inside_task',not out_of_scope,out_of_scope)
    tables=[];maths=[]
    for p in docs:
        content=p.read_text(encoding='utf-8');lines=content.splitlines()
        for i,line in enumerate(lines):
            if line.startswith('|') and i+1<len(lines) and re.match(r'^\|[ \t:\-|]+\|$',lines[i+1]):
                n=line.count('|');j=i+2
                while j<len(lines) and lines[j].startswith('|'):
                    if lines[j].count('|')!=n:tables.append([str(p.relative_to(W)),j+1,'column mismatch'])
                    j+=1
        if content.count(r'\(')!=content.count(r'\)') or content.count(r'\[')!=content.count(r'\]'):maths.append(p.name)
        if r'\\(' in content or r'\\[' in content:maths.append(p.name+' repeated escape')
    check('complete_table_headers',not tables,tables)
    check('math_delimiters',not maths,maths)
    artificial=read(O/'人工测试-attempt2.json');old=read(O/'旧场回归-attempt2.json');stats=read(O/'落盘统计独立核验-v001.json');summary=read(O/'诊断重建汇总.json')
    check('actual_tests',artificial['all_pass'] and len(artificial['geometry']['results'])==13 and len(artificial['evaluation']['checks'])==9)
    check('actual_old_regression',old['all_pass'] and len(old['combinations'])==3)
    check('actual_saved_statistics',stats['all_pass'] and stats['check_count']==1707 and stats['unique_combinations']==54 and stats['unique_integral_samples']==55296)
    check('actual_screen_roundtrip',stats['screen_comparisons']==18 and stats['optical_roundtrip_comparisons']==3)
    check('no_full_power_claim',not summary['full_search_started'] and not summary['formal_tables_generated'] and all(x['field_power']=='NOT_COMPUTED_PARTIAL_MIRROR_POPULATION' for x in summary['designs']))
    b=read(O/'累计计算预算.json')
    check('settled_budget',all(x['status']!='RUNNING' for x in b['runs']) and abs(sum(x['elapsed_seconds'] for x in b['runs'])-b['spent_seconds'])<1e-8 and b['spent_seconds']<1800)
    check('preserved_failure_versions',all((W/'诊断代码'/n).exists() for n in ['q02_design_v001.py','q02_eval_v001.py','q02_eval_v002.py','q02_prototype_run_v001.py','q02_prototype_run_v002.py']) and read(O/'运行-old-attempt1.json')['status']=='FAILED_OR_STOPPED' and read(O/'运行-diagnostics-attempt1.json')['status']=='FAILED_OR_STOPPED')
    # Only task-owned current-round files; input archive is referenced by immutable bindings.
    files=set(docs+controls)
    for pattern in ['q02_design*.py','q02_eval*.py','q02_prototype*.py','verify_q02_prototype*.py','Q02-原型*.json','Q02-原型*.md','Q02-设计与评价*.md']:
        files.update((W/'诊断代码').glob(pattern))
    files.update(p for p in O.rglob('*') if p.is_file() and p not in {output,manifest})
    rows=[{'path':p.relative_to(ROOT).as_posix(),'bytes':p.stat().st_size,'sha256':sha(p)} for p in sorted(files)]
    elapsed=time.perf_counter()-start
    result={'all_pass':all(x['pass'] for x in checks),'checks':checks,'check_count':len(checks),'checked_local_links':nlinks,
            'verification_seconds':elapsed,'computation_action_seconds':b['spent_seconds'],'accounted_with_file_verification_seconds':b['spent_seconds']+elapsed,
            'scope':'file/link/hash/version and saved evidence assertions; no new optics; not independent physical validation',
            'stage_user_acceptance':'PENDING','administrator_archive':'UNCONFIRMED','manifest_count_excluding_self':len(rows)+1}
    write(output,result)
    rows.append({'path':output.relative_to(ROOT).as_posix(),'bytes':output.stat().st_size,'sha256':sha(output)})
    write(manifest,{'status':'FILES_SAVED_NOT_ADMIN_ARCHIVED','files':rows,'count':len(rows),'self_hash_excluded':True,'generated_from':'verify_q02_prototype_delivery_v001.py'})
    print(json.dumps(result,ensure_ascii=False))
    if not result['all_pass']:sys.exit(1)
if __name__=='__main__':main()