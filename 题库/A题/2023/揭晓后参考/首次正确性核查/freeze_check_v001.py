from pathlib import Path
import json, hashlib, datetime, time
R=Path(r'C:\Users\admin\OneDrive\Desktop\26国赛-单题盲解区\A-P8C3').resolve()
O=R/'工作记录/揭晓后对照/首次正确性核查-v001'
B=R/'工作记录/冻结候选/盲解-v001'
def sha(p):
    h=hashlib.sha256()
    with p.open('rb') as f:
        for b in iter(lambda:f.read(4*1024*1024),b''):h.update(b)
    return h.hexdigest()
def safe(base,s):
    p=(base/s).resolve();assert p.is_relative_to(R);return p
def load(p):return json.loads(p.read_text(encoding='utf-8-sig'))
def main():
    assert Path.cwd().resolve()==R
    start=time.perf_counter();O.mkdir(parents=True,exist_ok=True)
    out=O/'冻结前全清单核验-v001.json';assert not out.exists()
    manifest=load(B/'文件清单-v001.json'); deps=load(B/'未复制依赖清单-v001.json')
    receipt=load(R/'工作记录/论文/全题整合/冻结候选交付核验-v001.json')
    rows=[]
    for kind,base,entries,key in [('package',B,manifest['files'],'path'),('external',R,deps['files'],'workspace_relative_path')]:
        for e in entries:
            p=safe(base,e[key]); exists=p.is_file(); actual=sha(p) if exists else None
            rows.append(dict(kind=kind,path=e[key],expected_sha256=e['sha256'],actual_sha256=actual,exists=exists,pass_hash=actual==e['sha256'],expected_bytes=e['bytes'],actual_bytes=p.stat().st_size if exists else None))
    manifests=[]
    for name,key in [('文件清单-v001.json','manifest_sha256'),('SHA256SUMS.txt','checksum_file_sha256')]:
        actual=sha(B/name);manifests.append(dict(path=name,expected=receipt[key],actual=actual,passed=actual==receipt[key]))
    sums=[]
    for line in (B/'SHA256SUMS.txt').read_text(encoding='utf-8-sig').splitlines():
        expected,rel=line.split('  ',1);p=safe(B,rel);sums.append({'path':rel,'passed':p.is_file() and sha(p)==expected})
    report=dict(created_at=datetime.datetime.now().astimezone().isoformat(),external_answers_accessed=False,manifest_checks=manifests,checksum_lines=len(sums),checksum_failures=[x for x in sums if not x['passed']],files=rows,package_count=sum(x['kind']=='package' for x in rows),external_count=sum(x['kind']=='external' for x in rows),failures=[x for x in rows if not x['pass_hash']],elapsed_seconds=time.perf_counter()-start)
    out.write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps({k:v for k,v in report.items() if k!='files'},ensure_ascii=False))
if __name__=='__main__':main()
