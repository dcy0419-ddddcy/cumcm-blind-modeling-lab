"""Render the local paper for document QA; no original question rendering or optical computation."""
from pathlib import Path
import subprocess,json,hashlib,re
from PIL import Image,ImageDraw
from pypdf import PdfReader
R=Path(__file__).resolve().parents[2];T=R/'工作记录/论文/LaTeX';out=T/'第2问-未完成草稿页面-v001';out.mkdir(exist_ok=True)
pdf=T/'第2问-模型建立与求解-v001.pdf'
log=(T/'第2问-模型建立与求解-v001.log').read_text(encoding='utf-8',errors='replace')
assert not re.search(r'^! ',log,re.M), 'TeX compilation failure; do not render truncated PDF as complete'
assert not list(out.glob('page-*.png')), 'Use a fresh final rendering directory to avoid stale pages'
page_count=len(PdfReader(pdf).pages)
p=subprocess.run(['pdftoppm','-r','90','-png',str(pdf),str(out/'page')],capture_output=True);(out/'渲染日志.txt').write_bytes(p.stderr);assert p.returncode==0
q=subprocess.run(['pdftotext','-layout',str(pdf),str(out/'PDF文本.txt')],capture_output=True);(out/'文本提取日志.txt').write_bytes(q.stderr);assert q.returncode==0
files=sorted(out.glob('page-*.png'))
assert len(files)==page_count
assert [int(x.stem.split('-')[1]) for x in files]==list(range(1,page_count+1))
for start in range(0,len(files),4):
    sheet=Image.new('RGB',(1320,1860),'#ddd')
    for j,f in enumerate(files[start:start+4]):
        im=Image.open(f).convert('RGB');im.thumbnail((620,877));c=Image.new('RGB',(660,930),'white');c.paste(im,((660-im.width)//2,32));ImageDraw.Draw(c).text((12,8),f.name,fill='black');sheet.paste(c,((j%2)*660,(j//2)*930))
    sheet.save(out/f'contact-{start+1:02d}.png')
log=(T/'第2问-模型建立与求解-v001.log').read_text(encoding='utf-8',errors='replace')
flags=[x for x in ['Overfull','Underfull','Missing character','Infinite glue','LaTeX Warning','! LaTeX Error'] if x in log]
a={'pdf_sha256':hashlib.sha256(pdf.read_bytes()).hexdigest(),'pages':len(PdfReader(pdf).pages),'rendered_pages':len(files),'tex_log_flags':flags,'render_stderr_bytes':len(p.stderr),'text_stderr_bytes':len(q.stderr),'render_directory':str(out.relative_to(R)),'visual_inspection':'pending human/model inspection, not certified by this script','new_optical_rays':0}
(R/'工作记录/诊断结果/Q02-搜索-v001/Q02-PDF自动核验-v001.json').write_text(json.dumps(a,ensure_ascii=False,indent=2),encoding='utf-8')
print(json.dumps(a,ensure_ascii=False))