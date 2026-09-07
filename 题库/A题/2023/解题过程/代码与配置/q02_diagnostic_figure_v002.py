"""Diagnostic coordinate figure using existing Pillow; no optional installs or rays."""
import time
START=time.perf_counter()
from pathlib import Path
import sys
H=Path(__file__).resolve().parent;sys.path.insert(0,str(H))
import q02_search_common_v001 as io
b=io.Budget('diagnostic_layout_figure_v002','confirmation',START)
try:
 import csv,PIL
 from PIL import Image,ImageDraw,ImageFont
 f=io.OUT/'frozen'
 with (f/'design.mirrors.csv').open(encoding='utf-8-sig',newline='')as h:rr=list(csv.DictReader(h))
 xy=[(float(r['x']),float(r['y']))for r in rr]
 im=Image.new('RGB',(1300,1400),'white');d=ImageDraw.Draw(im)
 font=ImageFont.load_default(size=23);small=ImageFont.load_default(size=19);title=ImageFont.load_default(size=28)
 left,top,size=110,160,1080
 def X(x):return left+(x+370)/740*size
 def Y(y):return top+(370-y)/740*size
 for a in range(-300,301,100):
  d.line((X(a),top,X(a),top+size),fill='#eeeeee',width=1);d.line((left,Y(a),left+size,Y(a)),fill='#eeeeee',width=1)
  d.text((X(a),top+size+15),str(a),anchor='mt',font=small,fill='#444444');d.text((left-15,Y(a)),str(a),anchor='rm',font=small,fill='#444444')
 d.rectangle((left,top,left+size,top+size),outline='#777777',width=1)
 for r in [350,100]:d.ellipse((X(-r),Y(r),X(r),Y(-r)),outline='#333333'if r==350 else '#b65a35',width=2)
 for x,y in xy:
  xx,yy=X(x),Y(y);d.ellipse((xx-1.8,yy-1.8,xx+1.8,yy+1.8),fill='#226188')
 d.line((X(-5),Y(0),X(5),Y(0)),fill='#b65a35',width=3);d.line((X(0),Y(-5),X(0),Y(5)),fill='#b65a35',width=3)
 d.text((650,35),'C22 - frozen diagnostic layout',anchor='mt',font=title,fill='#111111');d.text((650,78),'N = 3054; rating criterion not met; not a final design',anchor='mt',font=font,fill='#9b3c22')
 d.text((650,1300),'East x (m)',anchor='mt',font=font,fill='#222222');d.text((110,130),'North y (m)',font=small,fill='#222222')
 d.text((650,1360),'Dots: mirror centers. Outer circle: 350 m. Inner circle: 100 m exclusion.',anchor='mt',font=small,fill='#444444')
 p=io.ROOT/'工作记录/论文/图表/第2问-C22-未达标诊断布局-v001.png';im.save(p,dpi=(220,220))
 io.save(io.OUT/'诊断布局图来源-v001.json',{'figure':str(p.relative_to(io.ROOT)),'figure_sha256':io.sha(p),'source':str((f/'design.mirrors.csv').relative_to(io.ROOT)),'source_sha256':io.sha(f/'design.mirrors.csv'),'n':len(xy),'transform':'X=110+(x+370)/740*1080; Y=160+(370-y)/740*1080; equal scale','kind':'diagnostic center plot, not footprints or formal result','new_rays':0,'Pillow_version':PIL.__version__,'fallback':'matplotlib missing; v001 failure retained; no install'})
 b.finish();print('diagnostic figure saved; no rays')
except BaseException as e:b.finish('FAILED');io.event('失败运行.jsonl',{'mode':b.mode,'error':repr(e)});raise
