"""File integrity verification, distinct from numeric validation; no optical rerun."""
import sys,ast,re,json
from pathlib import Path
from urllib.parse import unquote
sys.path.insert(0,str(Path(__file__).resolve().parent))
import q01_full_run_v002 as r
budget=r.Budget('delivery-file-verification')
W=r.ROOT/'工作记录';dest=r.OUT/'交付文件核验-v002.json'
checks=[]
def add(name,passed,details):checks.append({'name':name,'passed':bool(passed),'details':details})
try:
    old=r.load(W/'诊断结果/Q01-原型交付核验-v002.json')
    skip={'工作记录/00-任务状态.md','工作记录/记录索引.md','工作记录/方法库查阅记录.md','工作记录/决策记录.md','工作记录/06-更新记录.md','工作记录/归档清单.md'}
    preserved=[]
    for item in old['artifacts']:
        if item['path'] in skip:continue
        p=r.ROOT/item['path'];preserved.append({'path':item['path'],'unchanged':r.sha(p)==item['sha256']})
    add('historical_stage_code_evidence_preserved',all(x['unchanged'] for x in preserved),preserved)
    r.check_bindings(r.load(r.CFG));add('frozen_inputs_and_execution_revision',True,'Original configuration v001 retained; v002 execution-only bindings verified')
    result=r.load(r.OUT/'汇总与数值核验-v001.json');regen=r.load(r.OUT/'汇总重建一致性.json')
    add('numeric_evidence_present_and_scope',result['numeric_validation_pass'] and result['coverage']['completed_combinations']==104700 and regen['passed'],{'coverage':result['coverage'],'numeric_checks':result['numeric_checks'],'work_targets_met':result['work_targets_all_met']})
    shard_details=[{'path':x['path'],'match':r.sha(r.ROOT/x['path'])==x['sha256']} for x in result['shards']]
    add('120_immutable_shard_hashes',len(shard_details)==120 and all(x['match'] for x in shard_details),shard_details)
    import numpy as np
    backup=r.OUT/'失败时-t005-partial.npz'
    with np.load(backup) as oldpart, np.load(r.OUT/'initial/t005.npz') as newfull:
        nold=int(oldpart['completed'])
        recovered={key:bool(np.array_equal(oldpart[key][:,:,:nold],newfull[key][:,:,:nold])) for key in ['sums','cross','counts','unknown_weights']}
    add('recovery_committed_statistics_preserved',all(recovered.values()),{'committed_mirrors':nold,'checks':recovered})
    docs=[W/'阶段记录/Q01-全场初算与数值精度验证-v001.md',W/'阶段记录/Q01-第1问结果初稿-v001.md']+[W/x for x in ['00-任务状态.md','记录索引.md','方法库查阅记录.md','决策记录.md','06-更新记录.md','归档清单.md']]+[r.CODE/'Q01-全场运行说明-v001.md']
    problems=[];audit=[];deferred_manifest_links=[]
    # Only new stage/run documents undergo full legacy-independent table/layout check.
    newdocs={docs[0],docs[1],docs[-1]}
    for p in docs:
        text=p.read_text(encoding='utf-8');issues=[];nlinks=0
        for target in re.findall(r'\[[^\]]*\]\(([^)]+)\)',text):
            if target.startswith(('http:','https:','app:')):continue
            q=unquote(target.strip('<>').split('#')[0])
            if not q:continue
            path=(p.parent/q).resolve()
            if not path.is_relative_to(r.ROOT):issues.append('outside workspace link '+q);continue
            if path==r.OUT/'归档哈希清单-v002.json':deferred_manifest_links.append(path)
            elif path!=dest and not path.exists():issues.append('missing '+q)
            nlinks+=1
        if p in newdocs:
            math=False;fence=False;table=[]
            for number,line in enumerate(text.splitlines(),1):
                if line.startswith(('~~~','```')):fence=not fence;continue
                if fence:continue
                if line.strip() in ['\\[','\\]']:math=not math;continue
                if math:continue
                if line.startswith('|'):
                    cells=len(re.split(r'(?<!\\)\|',line))-2
                    if table and cells!=table[0][1]:issues.append(f'table column mismatch {number}')
                    table.append((number,cells))
                else:
                    if table and len(table)<2:issues.append(f'incomplete table {table[0][0]}')
                    table=[]
            if math:issues.append('unclosed display math')
            if text.count('\\(')!=text.count('\\)'):issues.append('inline math delimiter mismatch')
            if '\\\\[' in text:issues.append('excess display escape')
        audit.append({'path':str(p.relative_to(r.ROOT)),'links':nlinks,'issues':issues});problems.extend(issues)
    add('documents_saved_links_tables_math',not problems,audit)
    # Parse all new source files without generating bytecode or executing tests.
    sources=[r.CODE/x for x in ['q01_core_v003.py','q01_tests_v003.py','q01_full_run_v001.py','q01_full_run_v002.py','q01_full_summary_v001.py','q01_full_summary_v002.py','q01_checkpoint_repair_v001.py','q01_full_report_v001.py','q01_full_delivery_v001.py','q01_full_delivery_v002.py','q01_rare_audit_v001.py']]
    for p in sources:ast.parse(p.read_text(encoding='utf-8'))
    add('new_source_syntax',True,[p.name for p in sources])
    D=[int(n) for n in re.findall(r'^## D(\d+)',(W/'决策记录.md').read_text(encoding='utf-8'),re.M)]
    U=[int(n) for n in re.findall(r'^## U(\d+)',(W/'06-更新记录.md').read_text(encoding='utf-8'),re.M)]
    add('continuous_decision_update_ids',D==list(range(1,max(D)+1)) and U==list(range(1,max(U)+1)),{'D':D,'U':U})
    st=(W/'00-任务状态.md').read_text(encoding='utf-8')
    add('acceptance_archival_budget_separated','原型v001已用户验收' in st and '待用户验收' in st and '管理员归档未确认' in st and budget.used()<1800,{'charged_before_finish':budget.used(),'scope':'Q1 only'})
    archive=(W/'归档清单.md').read_text(encoding='utf-8')
    add('archive_contains_new_sources_and_data',all(p.name in archive for p in sources) and 'Q01-全场-v001' in archive,'Full data directory includes shards, partials, logs, failure snapshots, rebuilds, and manifest')
    allpass=all(x['passed'] for x in checks)
    budget.finish('done' if allpass else 'verification_failed')
    # Manifest excludes itself and this output. Budget state is final at this point.
    manifest_paths=sources+[r.CFG,r.CODE/'Q01-全场运行说明-v001.md']+docs[:8]+[W/'诊断结果/Q01-全场前核心回归-v001.json']
    manifest_paths+=sorted(p for p in r.OUT.rglob('*') if p.is_file() and p.name not in ['归档哈希清单-v002.json',dest.name])
    unique=sorted(set(manifest_paths),key=str)
    manifest=[{'path':str(p.relative_to(r.ROOT)).replace('\\','/'),'bytes':p.stat().st_size,'sha256':r.sha(p)} for p in unique]
    r.save(r.OUT/'归档哈希清单-v002.json',{'created':r.now(),'files':manifest,'note':'Excludes this manifest and final verification report to avoid self hash cycle'})
    add('generated_manifest_link_exists',all(p.exists() for p in deferred_manifest_links),[str(p.relative_to(r.ROOT)) for p in deferred_manifest_links])
    allpass=all(x['passed'] for x in checks)
    r.save(dest,{'created':r.now(),'all_pass':allpass,'checks':checks,'budget_final':r.load(r.OUT/'累计计算预算.json'),'manifest_entries':len(manifest),'scope':'file/lineage verification, not optical validation'})
    print(json.dumps({'all_pass':allpass,'failed':[x['name'] for x in checks if not x['passed']],'checks':len(checks),'manifest_entries':len(manifest),'budget_seconds':r.load(r.OUT/'累计计算预算.json')['charged_seconds']},ensure_ascii=False))
    if not allpass:raise SystemExit(1)
except BaseException:
    if r.load(r.OUT/'累计计算预算.json').get('active') is not None:budget.finish('failed')
    raise