"""Reuse verified local PDF page audit with Q3-only output paths."""
from pathlib import Path
import sys,json,time
sys.path.insert(0,str(Path(__file__).resolve().parent))
import q02_repair_paper_render_v001 as renderer
ROOT=Path(__file__).resolve().parents[2]
def run():
    start=time.perf_counter();stem='第3问-模型建立与求解-v001'
    tex=ROOT/'工作记录/论文/LaTeX';out=ROOT/'工作记录/诊断结果/Q03-实施-v001/delivery'
    renderer.ROOT=ROOT;renderer.TEX_DIR=tex;renderer.STEM=stem
    renderer.PDF=tex/(stem+'.pdf');renderer.TEX=tex/(stem+'.tex');renderer.LOG=tex/(stem+'.log')
    renderer.SOURCE=ROOT/'工作记录/论文'/(stem+'.md')
    renderer.QA_BASE=tex/'第3问-v001-页面核验';renderer.DIAGNOSTICS=out
    renderer.CORRESPONDENCE=out/'正式Markdown与TeX对应-v001.json';renderer.LATEST=out/'PDF自动核验-v001.json'
    result=renderer.render();result['rendering_wall_seconds']=time.perf_counter()-start
    result['render_adapter_sha256']=renderer.sha(Path(__file__));result['reuse_source_sha256']=renderer.sha(Path(renderer.__file__))
    renderer.LATEST.write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    return {k:result[k]for k in ['pages','rendered_pages','render_directory','tex_log_flags','rendering_wall_seconds']}
if __name__=='__main__':print(json.dumps(run(),ensure_ascii=False))
