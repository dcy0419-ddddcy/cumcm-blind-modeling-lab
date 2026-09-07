"""Q3 pre-delivery page corrections from actual rendered PDF inspection."""
from pathlib import Path
import sys,json,re,hashlib,shutil
sys.path.insert(0,str(Path(__file__).resolve().parent))
import q03_paper_finalize_v001 as f
R=f.ROOT;O=f.Q3_OUT;W=R/'工作记录';md=f.paper.FORMAL_MD;tex=f.paper.FORMAL_TEX
def main():
    snap=O/'delivery/layout-before-v001';snap.mkdir(exist_ok=True)
    for p in [md,tex,tex.with_suffix('.pdf'),f.CORRESPONDENCE,O/'delivery/PDF自动核验-v001.json']:
        target=snap/p.name
        if target.exists():assert target.read_bytes()==p.read_bytes(),'snapshot conflicts'
        else:shutil.copyfile(p,target)
    before=md.read_text(encoding='utf-8-sig');after=before.replace('<!-- Q03-PAPER-FINALIZE-V001 -->\n','')
    old='| 逐镜见 result3.xlsx | 逐镜见 result3.xlsx | 2981 | 130284.0705 |'
    new='|  |  | 2981 | 130284.0705 |'
    assert old in after;after=after.replace(old,new+'\n\n表3的统一尺寸、安装高度栏按第3问允许方式留空；实际逐镜参数完整列于 result3.xlsx，并由表S1说明分组取值。')
    def sci(m):
        value=float(m.group(1));exponent=int(m.group(2));return r'\('+f'{value:g}'+r'\times10^{'+str(exponent)+r'}\)'
    after=re.sub(r'\b([0-9]+\.[0-9]+)e([+-][0-9]+)\b',sci,after)
    md.write_text(after,encoding='utf-8',newline='\n')
    result=f._make_final_tex(md,tex,f.CORRESPONDENCE)
    t=tex.read_text(encoding='utf-8-sig')
    token=r'\includegraphics[width=\linewidth,height=0.72\textheight,keepaspectratio]'
    assert t.count(token)==2
    t=t.replace(token,r'\includegraphics[width=0.68\linewidth,height=0.72\textheight,keepaspectratio]',1)
    t=t.replace(token,r'\includegraphics[width=0.90\linewidth,height=0.72\textheight,keepaspectratio]',1)
    tex.write_text(t,encoding='utf-8',newline='\n');result['tex_sha256']=f._sha(tex);result['layout_override']={'first_figure_width':'.68 linewidth','second_figure_width':'.90 linewidth','reason':'actual page inspection: remove printed internal marker, avoid oversized map breaking from its table; no data change','source':str(Path(__file__).relative_to(R))}
    f.CORRESPONDENCE.write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n',encoding='utf-8',newline='\n')
    revision=W/'论文/第3问-写稿修订记录-v001.md'
    with revision.open('a',encoding='utf-8',newline='\n')as h:
        h.write('\n\n## 页面实际查看后的排版修订\n\n修改原因：首版11页PDF第5页印出了内部HTML标记，首图尺寸偏大导致题表与图分开；第8页表3两统一栏文字紧挤，且与正式数据留空口径呈现不一致。\n\n修改位置及内容：第5.1节删除内部标记，首图显示宽度改0.68行宽；第5.2节表3两个统一栏留空，表后明确逐镜清单完整；第二图宽度改0.90行宽。搜索标准误的科学记数转为可渲染数学。\n\n修改前原文：`<!-- Q03-PAPER-FINALIZE-V001 -->`；表3两栏为“逐镜见 result3.xlsx”；两图均整行宽度。\n\n修改后原文：内部标记无正文内容；“表3的统一尺寸、安装高度栏按第3问允许方式留空；实际逐镜参数完整列于 result3.xlsx，并由表S1说明分组取值。”\n\n验证依据：正式表3数据两栏为空、首轮实际页面、图像原数据。模型公式、数据值与确认设计不变。修改前MD/TeX/PDF及对应记录在delivery/layout-before-v001，后续编译/页面报告绑定当前版本；先前生成记录的哈希为当时快照。\n')
    receipt={'md_sha256':f._sha(md),'tex_sha256':f._sha(tex),'source_sha256':f._sha(Path(__file__)),'correspondence_sha256':f._sha(f.CORRESPONDENCE),'before_folder':str(snap.relative_to(R)),'numerical_changes':False}
    (O/'delivery/页面排版修订-v001.json').write_text(json.dumps(receipt,ensure_ascii=False,indent=2),encoding='utf-8');print(json.dumps(receipt,ensure_ascii=False))
if __name__=='__main__':main()
