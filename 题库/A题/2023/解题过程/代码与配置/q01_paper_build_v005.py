"""Build Q1 manuscript, tables and scientific figures from accepted saved aggregates. No optics."""
from pathlib import Path
import sys, json, csv, hashlib, os, re
ROOT=Path(__file__).resolve().parents[2]
PAPER=ROOT/'工作记录/论文'; FIG=PAPER/'图表'; FIG.mkdir(exist_ok=True)
os.environ['MPLCONFIGDIR']=str(FIG/'缓存')
import numpy as np
import reportlab, subprocess
from reportlab.pdfgen import canvas
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.cidfonts import UnicodeCIDFont
from reportlab.lib.colors import HexColor, Color
pdfmetrics.registerFont(UnicodeCIDFont('STSong-Light'))
sys.stdout.reconfigure(encoding='utf-8')
D=ROOT/'工作记录/诊断结果/Q01-全场-v001'
source=D/'汇总与数值核验-v001.json'; lowpath=ROOT/'工作记录/诊断结果/Q01-论文收尾-v001/低存活全量核查-v002.json'
a=json.loads(source.read_text(encoding='utf-8')); lo=json.loads(lowpath.read_text(encoding='utf-8'))
p=np.array(a['point']); U=np.array(a['work_uncertainty_indicator']); delta=np.array(lo['effect_diameter_bound'])
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def table(headers,rows):return '\n'.join(['| '+' | '.join(headers)+' |','|'+'|'.join(['---']*len(headers))+'|']+['| '+' | '.join(map(str,row))+' |' for row in rows])
def put(p,s):p.write_text(s,encoding='utf-8')
T1=table(['日期','平均光学效率','平均余弦效率','平均阴影遮挡效率','平均截断效率','单位镜面面积平均输出热功率（kW/m²）'],[[f'{i+1}月21日']+[f'{p[i,j]:.4f}' for j in [0,1,2,3,5]] for i in range(12)])
T2=table(['年平均光学效率','年平均余弦效率','年平均阴影遮挡效率','年平均截断效率','年平均输出热功率（MW）','单位镜面面积年平均输出热功率（kW/m²）'],[[*[f'{p[12,j]:.4f}' for j in range(4)],f'{p[12,4]/1000:.3f}',f'{p[12,5]:.4f}']])
UT=table(['月份','光学效率','阴影遮挡效率','截断效率','热功率相对指标（%）'],[[str(i+1) if i<12 else '年平均',*[f'{U[i,j]*1e4:.3f}' for j in [0,2,3]],f'{100*U[i,4]/p[i,4]:.4f}'] for i in range(13)])
LT=table(['日期与时刻','镜号','附件原始行号','存活数','接收数'],[[f"{c['month']}月21日 {int(c['hour']):02d}:{int(c['hour']%1*60):02d}",c['mirror_id'],c['excel_row'],c['survivors'],c['captured']] for c in lo['cases']])
BT=table(['范围','原效率指标最大值','效率扰动界最大值','效率叠加最大值','功率原指标/扰动界/叠加（%）'],[[f'{i+1}月' if i<12 else '全年',f'{U[i,:4].max():.7f}',f'{delta[i,:4].max():.7f}',f'{(U+delta)[i,:4].max():.7f}',f'{100*U[i,4]/p[i,4]:.4f} / {100*delta[i,4]/p[i,4]:.4f} / {100*(U+delta)[i,4]/p[i,4]:.4f}'] for i in [1,9,11,12]])
with (FIG/'月度结果与工作指标-v001.csv').open('w',encoding='utf-8-sig',newline='') as f:
    w=csv.writer(f);w.writerow(['month']+a['labels']+['U_'+s for s in a['labels']]);w.writerows([[i+1,*p[i],*U[i]] for i in range(12)])
# Standard vector plotting with installed ReportLab; no new dependency installation.
def plot_pdf(filename, series, ymin, ymax, yticks, ylabel, error=False):
    path=FIG/filename
    c=canvas.Canvas(str(path),pagesize=(650,390),pageCompression=1)
    L,R,B,T=68,625,52,310
    X=lambda i:L+(R-L)*i/11
    Y=lambda v:B+(T-B)*(v-ymin)/(ymax-ymin)
    def text(x,y,t,size=10):
        c.setFillColor(HexColor('#222222'))
        for ch in t:
            font='Helvetica' if ord(ch)<256 else 'STSong-Light'
            c.setFont(font,size);c.drawString(x,y,ch);x+=pdfmetrics.stringWidth(ch,font,size)
    for v in yticks:
        c.setStrokeColor(HexColor('#dddddd'));c.setLineWidth(.4);c.line(L,Y(v),R,Y(v));text(27,Y(v)-3,f'{v:.2f}')
    c.setStrokeColor(HexColor('#333333'));c.setLineWidth(.7);c.line(L,B,R,B);c.line(L,B,L,T)
    for i in range(12):text(X(i)-3,B-15,str(i+1))
    text(270,16,'月份（每月21日）',11);text(L,368,ylabel,11)
    for j,label,col in series:
        c.setStrokeColor(HexColor(col));c.setFillColor(HexColor(col));c.setLineWidth(1.3)
        for i in range(11):c.line(X(i),Y(p[i,j]),X(i+1),Y(p[i+1,j]))
        for i in range(12):
            c.circle(X(i),Y(p[i,j]),2.1,stroke=1,fill=1)
            if error:
                y0,y1=Y(p[i,j]-U[i,j]),Y(p[i,j]+U[i,j]);c.line(X(i),y0,X(i),y1);c.line(X(i)-3,y0,X(i)+3,y0);c.line(X(i)-3,y1,X(i)+3,y1)
    for q,(j,label,col) in enumerate(series):
        yy=340;xx=68+q*140
        c.setStrokeColor(HexColor(col));c.line(xx,yy,xx+20,yy);text(xx+25,yy-3,label,10)
    c.showPage();c.save()
    proc=subprocess.run(['pdftoppm','-r','150','-singlefile','-png',str(path),str(path.with_suffix(''))],capture_output=True)
    if proc.returncode:raise RuntimeError(proc.stderr.decode('utf-8',errors='replace'))
    old=ROOT/'工作记录/诊断结果/Q01-论文收尾-v001/图形CID原始PDF';old.mkdir(exist_ok=True)
    if not (old/path.name).exists():(old/path.name).write_bytes(path.read_bytes())
    raster=canvas.Canvas(str(path),pagesize=(650,390),pageCompression=1)
    raster.drawImage(str(path.with_suffix('.png')),0,0,width=650,height=390)
    raster.showPage();raster.save()
plot_pdf('图1-月度效率-v001.pdf',[(0,'总光学效率','#1f4d78'),(1,'余弦效率','#bb6a27'),(2,'阴影遮挡效率','#287b66'),(3,'截断效率','#856199')],.48,1.01,[.5,.6,.7,.8,.9,1.], '平均效率（无量纲）')
plot_pdf('图2-月度单位面积功率-v001.pdf',[(5,'均值及数值工作指标','#1f4d78')],.40,.68,[.40,.45,.50,.55,.60,.65], '单位镜面面积平均热功率（kW/m²）',True)
maxopt=int(np.argmax(p[:12,0])); minopt=int(np.argmin(p[:12,0])); maxt=int(np.argmax(p[:12,3])); mint=int(np.argmin(p[:12,3]))
analysis=f'由未舍入结果可见，平均光学效率在{maxopt+1}月最高（{p[maxopt,0]:.6f}），在{minopt+1}月最低（{p[minopt,0]:.6f}）；单位面积热功率分别为{p[maxopt,5]:.6f}与{p[minopt,5]:.6f} kW/m²。余弦分量与总效率的月序变化方向相近，但仅凭该关系不能分离各因素的因果贡献。截断分量在{maxt+1}月最高、{mint+1}月最低，与总效率的极值月份不一致，说明不能用单个分量代替整体评价。图1、图2分别给出已计算代表日的效率与单位面积功率。'
lowcon=f'将所有筛出组合纳入后，效率的逐项叠加诊断最大为{lo["max_efficiency_U_plus_bound"]:.7f}，总热功率与单位面积热功率的最大相对叠加诊断为{100*lo["max_power_relative_U_plus_bound"]:.4f}%，仍低于相应0.001和0.5%的工作目标。加入上述保守扰动后，所列汇总数值工作指标仍未超过既定阈值，但不能将表S3各对象的条件效率认定为局部精确结果。'
con=f'在上述计算口径和物理近似下，镜场的年样本平均光学效率为{p[12,0]:.4f}，平均输出热功率为{p[12,4]/1000:.3f} MW，单位镜面面积平均输出热功率为{p[12,5]:.4f} kW/m²。规定总体的全部组合已经计算，汇总量达到所设数值工作目标；物理模型偏差仍未量化。逐镜逐时的姿态、能量份额、效率及状态构成可追溯的评价接口，任何后续复用均应保留本问的适用条件。'
replacements={'TABLE1':T1,'TABLE2':T2,'UTABLE':UT,'LOWTABLE':LT,'BOUND_TABLE':BT,'RESULT_ANALYSIS':analysis,'LOW_CONCLUSION':lowcon,'CONCLUSION':con}
for k in [1,2]:
    img=FIG/('图1-月度效率-v001.png' if k==1 else '图2-月度单位面积功率-v001.png')
    replacements[f'FIG{k}']=f'![图{k}]({img.as_posix()})'
template=ROOT/'工作记录/诊断代码/第1问-正文模板-v001.md';s=template.read_text(encoding='utf-8')
for k,v in replacements.items():s=s.replace('@@'+k+'@@',v)
assert '@@' not in s
put(PAPER/'第1问-模型建立与求解-v001.md',s)
for name,t in [('表1',T1),('表2',T2),('表S2',UT),('表S3',LT),('表S4',BT)]:put(FIG/(name+'-生成内容-v001.md'),t+'\n')
# Machine-check displayed entries against original unrounded source, including MW conversion.
rows1=[r for r in T1.splitlines()[2:]];rows2=T2.splitlines()[2:]
checks=[]
for i,row in enumerate(rows1):
    cells=[t.strip() for t in row.strip('|').split('|')]
    for j,c in enumerate([0,1,2,3,5]):checks.append({'table':1,'row':i+1,'field':a['labels'][c],'display':cells[j+1],'source':float(p[i,c]),'pass':cells[j+1]==f'{p[i,c]:.4f}'})
cells=[t.strip() for t in rows2[0].strip('|').split('|')]
for j in range(6):
    value=float(p[12,j]/1000 if j==4 else p[12,j]);expected=f'{value:.3f}' if j==4 else f'{value:.4f}'
    checks.append({'table':2,'row':1,'field':a['labels'][j],'display':cells[j],'source_display_unit':value,'pass':cells[j]==expected})
assert all(x['pass'] for x in checks) and len(checks)==66
out=ROOT/'工作记录/诊断结果/Q01-论文收尾-v001'
record={'sources':[{'path':x.relative_to(ROOT).as_posix(),'sha256':sha(x)} for x in [source,lowpath,template]],'table_cell_checks':checks,'passed':True,'all_66_cells_matched':True,'source_point_unchanged':sha(source),'figures_from_saved_points':True,'new_optical_rays':0,'environment':{'python':sys.version,'numpy':np.__version__,'reportlab':reportlab.Version},'script_sha256':sha(Path(__file__)),'generated_figures':[str(x.relative_to(ROOT)) for x in FIG.glob('图*.png')]}
put(out/'论文数据生成与逐项核对-v001.json',json.dumps(record,ensure_ascii=False,indent=2))
print(json.dumps({'table_cells_checked':66,'all_match':True,'manuscript_chars':len(s),'point_annual':p[-1].tolist(),'figures':record['generated_figures']},ensure_ascii=False))