"""Offline scientific charts with installed ReportLab/Poppler; saved data only."""
from pathlib import Path
import json,hashlib,subprocess,math
from reportlab.graphics.shapes import Drawing,Line,Circle,String,Rect,PolyLine
from reportlab.graphics import renderPDF
from reportlab.lib.colors import HexColor,black,white
import reportlab
ROOT=Path(__file__).resolve().parents[2]
O=ROOT/'工作记录/诊断结果/Q03-实施-v001'
def load(p):return json.loads(p.read_text(encoding='utf-8-sig'))
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def run():
    r=load(O/'delivery/report.json')
    assert r['status']=='CONFIRMED_IMPROVEMENT'
    for p,h in r['sha256'].items():assert sha(O/p)==h
    des=load(O/r['design_file']);s=load(O/r['candidate_confirmation_summary']);b=load(O/r['baseline_confirmation_summary'])
    out=ROOT/'工作记录/论文/图表/Q03-v001';out.mkdir(parents=True,exist_ok=True)
    blue=HexColor('#24668c');orange=HexColor('#b54d25');grey=HexColor('#aaaaaa')
    d=Drawing(460,390);cx,cy,scale=220,200,.43
    def xy(x,y):return cx+x*scale,cy+y*scale
    for v in [-300,-200,-100,0,100,200,300]:
        xx,yy=xy(v,v);d.add(Line(xx,48,xx,352,strokeColor=HexColor('#eeeeee'),strokeWidth=.4));d.add(Line(68,yy,372,yy,strokeColor=HexColor('#eeeeee'),strokeWidth=.4))
        d.add(String(xx,35,str(v),fontSize=8,textAnchor='middle'));d.add(String(59,yy-3,str(v),fontSize=8,textAnchor='end'))
    d.add(Circle(cx,cy,350*scale,fillColor=None,strokeColor=black,strokeWidth=.7))
    tx,ty=xy(*des['tower_xy']);d.add(Circle(tx,ty,100*scale,fillColor=None,strokeColor=grey,strokeWidth=.8,strokeDashArray=[4,3]))
    for m in des['mirrors']:
        x,y=xy(m['x'],m['y']);d.add(Circle(x,y,.7,fillColor=orange if m['height']==6.05 else blue,strokeColor=None))
    d.add(Line(tx-4,ty,tx+4,ty,strokeColor=black));d.add(Line(tx,ty-4,tx,ty+4,strokeColor=black))
    d.add(String(220,15,'East x (m)',fontSize=10,textAnchor='middle'));d.add(String(10,365,'North y (m)',fontSize=10))
    d.add(Circle(100,378,3,fillColor=orange,strokeColor=None));d.add(String(108,375,'h = 6.05 m (582 mirrors)',fontSize=9))
    d.add(Circle(270,378,3,fillColor=blue,strokeColor=None));d.add(String(278,375,'h = 6.65 m (2399 mirrors)',fontSize=9))
    drawings=[('Q03-镜高分组',d)]
    values=[r[5] for ss in [s,b] for r in ss['point'][:12]]
    u=max(r[5] for r in s['conservative_work_indicator'][:12])
    ymin=math.floor((min(values)-u-.005)/.02)*.02;ymax=math.ceil((max(values)+u+.005)/.02)*.02
    d=Drawing(480,275);left,right,bottom,top=58,463,45,225
    def point(m,v):return left+(m-1)*(right-left)/11,bottom+(v-ymin)*(top-bottom)/(ymax-ymin)
    for v in [ymin+.02*j for j in range(round((ymax-ymin)/.02)+1)]:
        y=point(1,v)[1];d.add(Line(left,y,right,y,strokeColor=HexColor('#dddddd'),strokeWidth=.5));d.add(String(left-7,y-3,f'{v:.2f}',fontSize=9,textAnchor='end'))
    for m in range(1,13):d.add(String(point(m,ymin)[0],29,str(m),fontSize=9,textAnchor='middle'))
    d.add(Line(left,bottom,left,top,strokeColor=black,strokeWidth=.6));d.add(Line(left,bottom,right,bottom,strokeColor=black,strokeWidth=.6))
    for summary,color,dash in [(s,blue,None),(b,orange,[4,3])]:
        pts=[point(m+1,v[5])for m,v in enumerate(summary['point'][:12])]
        assert all(ymin<=v[5]<=ymax for v in summary['point'][:12])
        d.add(PolyLine([v for p in pts for v in p],strokeColor=color,strokeWidth=1,strokeDashArray=dash))
        for x,y in pts:d.add(Circle(x,y,2,fillColor=color,strokeColor=None))
    for m in range(12):
        val=s['point'][m][5];u=s['conservative_work_indicator'][m][5];x,lo=point(m+1,val-u);hi=point(m+1,val+u)[1]
        d.add(Line(x,lo,x,hi,strokeColor=blue,strokeWidth=.8));d.add(Line(x-2,lo,x+2,lo,strokeColor=blue));d.add(Line(x-2,hi,x+2,hi,strokeColor=blue))
    d.add(String(260,10,'Specified month (21st)',fontSize=10,textAnchor='middle'))
    d.add(String(15,256,'Sample mean thermal power per mirror area (kW/m2)',fontSize=10))
    d.add(Line(85,239,105,239,strokeColor=blue));d.add(String(110,236,'Q3F013; bars: numerical work U',fontSize=8))
    d.add(Line(300,239,320,239,strokeColor=orange,strokeDashArray=[4,3]));d.add(String(325,236,'R027; new paired data',fontSize=8))
    drawings.append(('Q03-月度单位面积功率',d));commands=[]
    for stem,d in drawings:
        pdf=out/(stem+'.pdf');renderPDF.drawToFile(d,str(pdf))
        cmd=['pdftoppm','-r','160','-singlefile','-png',str(pdf),str(out/stem)];a=subprocess.run(cmd,capture_output=True,cwd=ROOT);commands.append(cmd)
        (out/(stem+'-render.log')).write_bytes(a.stdout+a.stderr)
        if a.returncode:raise RuntimeError('figure render failed')
    receipt={'sources':{k:r[k]for k in ('design_file','candidate_confirmation_summary','baseline_confirmation_summary')},'source_sha256':r['sha256'],'script_sha256':sha(Path(__file__)),'figures':[str((out/(n+'.png')).relative_to(ROOT))for n,_ in drawings],'reportlab':reportlab.Version,'commands':commands,'scope':'saved specified monthly means; U bars are numerical work diagnostics, not physical error or strict CI','previous_failure':'q03_figures_v001: matplotlib missing; no installation; new v002 uses existing ReportLab'}
    (O/'delivery/图表生成核验-v001.json').write_text(json.dumps(receipt,ensure_ascii=False,indent=2)+'\n',encoding='utf-8');return receipt
