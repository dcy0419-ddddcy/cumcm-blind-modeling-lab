"""Final artifact/data correspondence and scoped archive; no optical rays."""
import time
START=time.perf_counter()
from pathlib import Path
import json,hashlib,re,sys
sys.path.insert(0,str(Path(__file__).resolve().parent))
import q03_common_v001 as io
ROOT=io.ROOT;O=io.OUT
def main():
    budget=io.Budget('final_file_audit','confirmation',START)
    checks={};details={}
    def ck(k,v):
        checks[k]=bool(v)
        if not v:raise ValueError(k)
    try:
        report=io.load(O/'delivery/report.json')
        for p,h in report['sha256'].items():ck('delivery_hash:'+p,io.sha(O/p)==h)
        audit=io.load(O/'delivery/独立重建核验-v001.json');ck('numeric_gate',audit['all_pass']and audit['formal_ready']and audit['improvement_supported'])
        paper=ROOT/'工作记录/论文/第3问-模型建立与求解-v001.md';text=paper.read_text(encoding='utf-8-sig')
        tex=ROOT/'工作记录/论文/LaTeX/第3问-模型建立与求解-v001.tex';pdf=tex.with_suffix('.pdf')
        binding=io.load(O/'delivery/正式Markdown与TeX对应-v001.json');ck('markdown_tex_binding',io.sha(paper)==binding['source_sha256']and io.sha(tex)==binding['tex_sha256'])
        page=io.load(O/'delivery/PDF自动核验-v001.json');ck('pdf_current',io.sha(pdf)==page['pdf_sha256']);ck('all_pages',page['pages']==page['rendered_pages']and page['page_numbers']==list(range(1,page['pages']+1)))
        for p in page['page_files']:ck('page_hash:'+p['file'],io.sha(ROOT/p['file'])==p['sha256'])
        visual=io.load(O/'delivery/PDF人工页面核验-v001.json');ck('actual_visual_review',visual['all_pages_reviewed']and visual['passed']and visual['pdf_sha256']==io.sha(pdf))
        tables=[];ls=text.splitlines();j=0
        while j<len(ls):
            if ls[j].strip()==chr(92)+'[':
                j+=1
                while j<len(ls)and ls[j].strip()!=chr(92)+']':j+=1
                j+=1
                continue
            if ls[j].startswith('|'):
                block=[]
                while j<len(ls)and ls[j].startswith('|'):block.append(ls[j]);j+=1
                rows=[[v.strip()for v in r.strip().strip('|').split('|')]for r in block]
                ck('table_header_'+str(len(tables)),len(rows)>1 and all(re.fullmatch(r':?-+:?',x.replace(' ',''))for x in rows[1]))
                ck('table_width_'+str(len(tables)),all(len(r)==len(rows[0])for r in rows))
                tables.append(rows)
            else:j+=1
        required=io.load(O/'delivery/结果数据-v001.json')['tables']
        def table_after(title):
            pos=text.index(title);lines=text[pos:].splitlines();rows=[]
            for line in lines[1:]:
                if line.startswith('|'):rows.append([v.strip()for v in line.strip().strip('|').split('|')])
                elif rows:break
            return rows[2:]
        a=table_after('表1　');b=table_after('表2　');c=table_after('表3　')
        expect=[[r[0]]+[f'{v:.4f}'for v in r[1:]]for r in required['table1']['rows']]
        ck('table1_all60_display_values',a==expect)
        r=required['table2']['rows'][0];expect=[[*(f'{v:.4f}'for v in r[:4]),f'{r[4]:.3f}',f'{r[5]:.4f}']]
        ck('table2_all6_display_values',b==expect)
        ck('table3_N_area',len(c)==1 and c[0][-2:] == ['2981','130284.0705'])
        ck('balanced_display_math',text.count(chr(92)+'[')==text.count(chr(92)+']'))
        ck('no_double_math_escape',chr(92)*2+'('not in text and chr(92)*2+'['not in text)
        ck('no_result_placeholders',not any(w in text for w in ['待填','TODO','未完成草稿','19项']))
        docs=[paper,ROOT/'工作记录/论文/第3问-正文证据映射-v001.md',ROOT/'工作记录/论文/第3问-写稿修订记录-v001.md',ROOT/'工作记录/阶段记录/Q03-异尺寸原型验证-v001.md',ROOT/'工作记录/阶段记录/Q03-分组搜索与独立确认-v001.md',ROOT/'工作记录/阶段记录/Q03-第3问结果初稿-v001.md']
        broken=[];links=0
        for doc in docs:
            ck('document_exists:'+doc.name,doc.is_file())
            txt=doc.read_text(encoding='utf-8-sig')
            for target in re.findall(r'!?\[[^\]\n]*\]\(([^\)\n]*)\)',txt):
                target=target.strip('<>');target=target.split('#')[0]
                if not target or target.startswith(('http:','https:')):continue
                p=Path(target);p=p if p.is_absolute() else doc.parent/p
                links+=1
                if not p.resolve().is_relative_to(ROOT) or not p.exists():broken.append({'doc':doc.name,'target':target})
        details.update(tables=len(tables),links_checked=links,broken_links=broken,numerical_validation_checks=len(audit['checks']),pages=page['pages'])
        ck('document_links',not broken)
        files=set()
        files.update(p for p in O.rglob('*')if p.is_file()and p.name not in ['累计计算预算.json','交付文件核验-v001.json','交付哈希清单-v001.json'])
        files.update((ROOT/'工作记录/诊断代码').glob('q03*'))
        files.update((ROOT/'工作记录/阶段记录').glob('Q03*'))
        files.update((ROOT/'工作记录/论文').glob('第3问*'))
        files.update(p for p in (ROOT/'工作记录/论文/图表/Q03-v001').rglob('*')if p.is_file())
        files.update((ROOT/'工作记录/论文/LaTeX').glob('第3问-模型建立与求解-v001.*'))
        files.update(p for p in (ROOT/'工作记录/论文/LaTeX/第3问-v001-页面核验').rglob('*')if p.is_file())
        manifest=[]
        for p in sorted(files):
            if p.is_file():manifest.append({'path':p.relative_to(ROOT).as_posix(),'bytes':p.stat().st_size,'sha256':io.sha(p)})
        io.save(O/'delivery/交付哈希清单-v001.json',{'scope':'Q03 new artifacts and retained failures; controls and evolving budget excluded, separately bound at closure','files':manifest,'bytes':sum(p['bytes']for p in manifest)})
        ck('round_budget',budget.used()<5400)
        answer={'passed':True,'checks':checks,'details':details,'artifact_count':len(manifest),'numeric_validation':'separate saved-statistics reconstruction passed; this audit itself emits no rays','elapsed_seconds':time.perf_counter()-START}
        io.save(O/'delivery/交付文件核验-v001.json',answer);budget.finish();print(json.dumps({'passed':True,'details':details,'artifact_count':len(manifest)},ensure_ascii=False))
    except BaseException as exc:
        io.save(O/'delivery/交付文件核验-v001-失败.json',{'passed':False,'checks':checks,'details':details,'error':str(exc)});budget.finish('FAILED');raise
if __name__=='__main__':main()
