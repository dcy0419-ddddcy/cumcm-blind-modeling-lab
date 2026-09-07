"""Draw only the frozen diagnostic layout from persisted compact files; no rays."""
import time
START=time.perf_counter()
from pathlib import Path
import os,sys
H=Path(__file__).resolve().parent;sys.path.insert(0,str(H))
import q02_search_common_v001 as io
b=io.Budget('diagnostic_layout_figure','confirmation',START)
try:
 os.environ['MPLCONFIGDIR']=str(io.OUT/'matplotlib-config')
 import csv,json,matplotlib
 matplotlib.use('Agg')
 import matplotlib.pyplot as plt
 from matplotlib.patches import Circle
 f=io.OUT/'frozen';md=io.load(f/'design.metadata.json')
 with (f/'design.mirrors.csv').open(encoding='utf-8-sig',newline='')as h:rr=list(csv.DictReader(h))
 # Coordinates are saved at the actual evaluated/exported precision.
 xy=[(float(r['x']),float(r['y']))for r in rr]
 fig,ax=plt.subplots(figsize=(6.8,6.8));ax.scatter([p[0]for p in xy],[p[1]for p in xy],s=1.5,color='#226188',rasterized=True)
 ax.add_patch(Circle((0,0),350,fill=False,lw=1.0,color='#333333'));ax.add_patch(Circle((0,0),100,fill=False,lw=1.0,color='#b65a35',linestyle='--'));ax.plot(0,0,'+',color='#b65a35',markersize=12)
 ax.set(xlim=(-370,370),ylim=(-370,370),aspect='equal',xlabel='East x (m)',ylabel='North y (m)',title='C22: frozen diagnostic layout, N = 3054\nRating criterion not met; not a final design')
 ax.grid(alpha=.15);fig.tight_layout()
 p=io.ROOT/'工作记录/论文/图表/第2问-C22-未达标诊断布局-v001.png';p.parent.mkdir(exist_ok=True);fig.savefig(p,dpi=220);plt.close(fig)
 io.save(io.OUT/'诊断布局图来源-v001.json',{'figure':str(p.relative_to(io.ROOT)),'figure_sha256':io.sha(p),'source':str((f/'design.mirrors.csv').relative_to(io.ROOT)),'source_sha256':io.sha(f/'design.mirrors.csv'),'n':len(xy),'kind':'diagnostic centers only; no mirror footprints, no official results','new_rays':0,'matplotlib_version':matplotlib.__version__})
 b.finish();print('diagnostic figure saved; no rays')
except BaseException as e:b.finish('FAILED');io.event('失败运行.jsonl',{'mode':b.mode,'error':repr(e)});raise
