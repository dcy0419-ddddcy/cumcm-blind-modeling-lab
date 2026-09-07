"""Preserve each S03 PDF rendering attempt; no old paper output touched."""
from pathlib import Path
import sys,json
ROOT=Path(r'C:\Users\admin\OneDrive\Desktop\26国赛-单题盲解区\A-P8C3').resolve()
sys.path.insert(0,str(ROOT/'工作记录/诊断代码'))
import q02_repair_paper_render_v001 as r
O=ROOT/'工作记录/论文/全题整合'
def run():
    assert Path.cwd().resolve()==ROOT
    r.ROOT=ROOT;r.TEX_DIR=O;r.STEM='完整论文-v001'
    r.PDF=O/(r.STEM+'.pdf');r.TEX=O/(r.STEM+'.tex');r.LOG=O/(r.STEM+'.log');r.SOURCE=O/(r.STEM+'.md')
    r.QA_BASE=O/'页面核验';r.DIAGNOSTICS=O;r.CORRESPONDENCE=O/'Markdown与LaTeX对应-v001.json';r.LATEST=O/'PDF自动核验-v001.json'
    result=r.render();return {k:result[k]for k in ['pages','rendered_pages','render_directory','tex_log_flags','pdf_sha256']}
if __name__=='__main__':print(json.dumps(run(),ensure_ascii=False))
