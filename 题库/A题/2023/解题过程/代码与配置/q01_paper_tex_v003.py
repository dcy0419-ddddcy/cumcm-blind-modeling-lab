"""Translate the fixed manuscript subset of Markdown to local LaTeX, keeping mathematics verbatim."""
from pathlib import Path
import re, json,hashlib
ROOT=Path(__file__).resolve().parents[2];P=ROOT/'工作记录/论文';T=P/'LaTeX';T.mkdir(exist_ok=True)
source=P/'第1问-模型建立与求解-v001.md'; lines=source.read_text(encoding='utf-8').splitlines()
def inline(s):
    parts=re.split(r'(\\\(.*?\\\))',s)
    for i in range(0,len(parts),2):
        x=parts[i]
        x=x.replace('\\',r'\textbackslash{}').replace('&',r'\&').replace('%',r'\%').replace('#',r'\#').replace('_',r'\_')
        x=x.replace('²',r'\textsuperscript{2}').replace('×',r'\(\times\)')
        x=re.sub(r'\*\*(.*?)\*\*',r'\\textbf{\1}',x)
        parts[i]=x
    return ''.join(parts)
out=[r'''\documentclass[UTF8,fontset=windows,zihao=-4]{ctexart}
\usepackage{amsmath,amssymb,graphicx,booktabs,longtable,array,geometry}
\geometry{a4paper,margin=23mm}
\setlength{\parskip}{0.35em}
\setlength{\emergencystretch}{2em}
\setlength{\tabcolsep}{3pt}
\renewcommand{\arraystretch}{1.25}
\setcounter{tocdepth}{2}
\begin{document}
''']
i=0;blocks=0;tables=0;pending_caption=None
while i<len(lines):
    s=lines[i].strip()
    if not s:out.append('');i+=1;continue
    if s==r'\[':
        block=[s];i+=1
        while i<len(lines):
            block.append(lines[i]);i+=1
            if block[-1].strip()==r'\]':break
        out.extend(block);blocks+=1;continue
    if re.match(r'^表S?\d+\u3000',s):
        pending_caption=s;i+=1;continue
    if s.startswith('|'):
        rows=[]
        while i<len(lines) and lines[i].strip().startswith('|'):
            cells=[x.strip() for x in lines[i].strip().strip('|').split('|')]
            if not all(re.match(r'^:?-+:?$',c) for c in cells):rows.append(cells)
            i+=1
        n=len(rows[0]);tables+=1
        # Proportional widths keep the whole table within the text block including padding.
        ratios={3:[.29,.54,.17],5:[.24,.19,.19,.18,.20],6:[.16,.16,.17,.17,.17,.17]}.get(n,[1/n]*n)
        if n==5 and '功率' in rows[0][-1] and '叠加' in rows[0][-1]:ratios=[.10,.20,.20,.20,.30]
        cols=''.join(r'>{\raggedright\arraybackslash}p{'+f'{r:.4f}'+r'\dimexpr\linewidth-'+str(2*n)+r'\tabcolsep\relax}' for r in ratios)
        out.append(r'\par\medskip\noindent\begin{minipage}{\linewidth}\small');out.append(r'\textbf{'+inline(pending_caption)+r'}\par\smallskip')
        pending_caption=None
        out.append(r'\begin{tabular}{'+cols+'}');out.append(r'\toprule')
        header=' & '.join(inline(x) for x in rows[0])+r' \\'
        out += [header,r'\midrule']
        for row in rows[1:]:out.append(' & '.join(inline(x) for x in row)+r' \\')
        out.append(r'\bottomrule\end{tabular}\end{minipage}\par\medskip');continue
    if s.startswith('!['):
        path=Path(re.match(r'!\[.*?\]\((.*)\)$',s).group(1)); rel='../图表/'+path.with_suffix('.png').name
        out.append(r'\par\medskip\noindent\begin{minipage}{\linewidth}\centering\includegraphics[width=\linewidth]{'+rel+r'}\par')
        i+=1
        while i<len(lines) and not lines[i].strip():i+=1
        assert re.match(r'^图\d+\u3000',lines[i].strip())
        out.append(r'{\small\raggedright '+inline(lines[i].strip())+r'\par}\end{minipage}\par\medskip');i+=1;continue
    if s.startswith('# '):out.append(r'\begin{center}{\LARGE\bfseries '+inline(s[2:])+r'}\end{center}');i+=1;continue
    if s.startswith('### '):out.append(r'\subsection*{'+inline(s[4:])+'}');i+=1;continue
    if s.startswith('## '):out.append(r'\section*{'+inline(s[3:])+'}');i+=1;continue
    if re.match(r'^图\d',s):out.append(r'{\small\noindent '+inline(s)+r'\par}');i+=1;continue
    out.append(inline(s));i+=1
out.append(r'\end{document}')
tex=T/'第1问-模型建立与求解-v001.tex';tex.write_text('\n'.join(out)+'\n',encoding='utf-8')
assert blocks==20 and tables==6
rec={'source':source.relative_to(ROOT).as_posix(),'source_sha256':hashlib.sha256(source.read_bytes()).hexdigest(),'tex':tex.relative_to(ROOT).as_posix(),'tex_sha256':hashlib.sha256(tex.read_bytes()).hexdigest(),'math_display_blocks':blocks,'tables':tables,'layout':'ordinary ctexart with installed Windows fonts, not official/reference-paper template','internet_or_dependency_install':False}
(ROOT/'工作记录/诊断结果/Q01-论文收尾-v001/Markdown与TeX对应-v001.json').write_text(json.dumps(rec,ensure_ascii=False,indent=2),encoding='utf-8')
print(json.dumps({'math_blocks':blocks,'tables':tables}))