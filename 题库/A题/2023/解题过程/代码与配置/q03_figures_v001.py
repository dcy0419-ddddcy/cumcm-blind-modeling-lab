"""Figures exclusively from delivered Q3 design and confirmation results; no rays."""
from pathlib import Path
import json,sys,hashlib
ROOT=Path(__file__).resolve().parents[2]
O=ROOT/'工作记录/诊断结果/Q03-实施-v001'

def run():
 import matplotlib
 matplotlib.use('Agg')
 import matplotlib.pyplot as plt
 import numpy as np
 report=json.loads((O/'delivery/report.json').read_text(encoding='utf-8-sig'))
 if report['status']!='CONFIRMED_IMPROVEMENT':raise ValueError('FIGURE_REQUIRES_VALID_DELIVERY')
 des=json.loads((O/report['design_file']).read_text(encoding='utf-8-sig'))
 s=json.loads((O/report['candidate_confirmation_summary']).read_text(encoding='utf-8-sig'))
 b=json.loads((O/report['baseline_confirmation_summary']).read_text(encoding='utf-8-sig'))
 out=ROOT/'工作记录/论文/图表/Q03-v001';out.mkdir(parents=True,exist_ok=True)
 xy=np.array([[r['x'],r['y']]for r in des['mirrors']]);hh=np.array([r['height']for r in des['mirrors']]);groups=np.array([r['group']for r in des['mirrors']])
 fig,ax=plt.subplots(figsize=(6.4,5.2));sc=ax.scatter(xy[:,0],xy[:,1],c=hh,s=4,cmap='viridis');ax.add_patch(plt.Circle((0,0),350,fill=False,color='black',lw=.8));ax.add_patch(plt.Circle(des['tower_xy'],100,fill=False,color='grey',ls='--',lw=.8));ax.plot(*des['tower_xy'],'r+',ms=8);ax.set(xlabel='East x (m)',ylabel='North y (m)',aspect='equal');fig.colorbar(sc,ax=ax,label='Mirror height h (m)');fig.tight_layout();fig.savefig(out/'Q03-镜高分组.png',dpi=180);plt.close(fig)
 point=np.array(s['point']);work=np.array(s['conservative_work_indicator']);bp=np.array(b['point']);month=np.arange(1,13)
 fig,ax=plt.subplots(figsize=(6.4,3.6));ax.errorbar(month,point[:12,5],yerr=work[:12,5],fmt='o-',ms=3,lw=1,label='Q3 frozen candidate; numerical work U');ax.plot(month,bp[:12,5],'s--',ms=3,lw=1,label='R027; new paired data');ax.set(xlabel='Specified month (21st)',ylabel='Sample mean thermal power (kW/m²)',xticks=month);ax.grid(alpha=.25);ax.legend(fontsize=8);fig.tight_layout();fig.savefig(out/'Q03-月度单位面积功率.png',dpi=180);plt.close(fig)
 receipt={'sources':{k:report[k]for k in ('design_file','candidate_confirmation_summary','baseline_confirmation_summary')},'source_sha256':report['sha256'],'script_sha256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),'figures':[str(p.relative_to(ROOT))for p in out.glob('*.png')],'scope':'saved monthly specified-sample means; error bar is registered U, not physical or strict confidence interval','matplotlib':matplotlib.__version__}
 (O/'delivery/图表生成核验-v001.json').write_text(json.dumps(receipt,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
 return receipt
if __name__=='__main__':print(json.dumps(run(),ensure_ascii=False))
