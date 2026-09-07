"""Build integrated manuscript and scientific figures from saved evidence only.

No evaluator imports, ray generation, optimization or modification of old stages.
All output is new S03 work; default task root is explicit and verified.
"""
from pathlib import Path
import hashlib,json,re,sys,subprocess,math
ROOT=Path(r'C:\Users\admin\OneDrive\Desktop\26国赛-单题盲解区\A-P8C3').resolve()
HERE=ROOT/'工作记录/诊断代码'
OUT=ROOT/'工作记录/论文/全题整合'
sys.path.insert(0,str(HERE))
import q02_repair_paper_tex_v002 as converter
from reportlab.graphics.shapes import Drawing,Line,Circle,String,PolyLine
from reportlab.graphics import renderPDF
from reportlab.lib.colors import HexColor,black

def load(p):return json.loads(p.read_text(encoding='utf-8-sig'))
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def save(p,t):
    assert p.resolve().is_relative_to(ROOT)
    p.parent.mkdir(parents=True,exist_ok=True);p.write_text(t,encoding='utf-8')
def table(caption,header,rows):
    return caption+'\n\n|'+'|'.join(header)+'|\n|'+'|'.join(['---']*len(header))+'|\n'+'\n'.join('|'+'|'.join(str(c) for c in row)+'|' for row in rows)
def sci(v):
    m,e=f'{v:.5e}'.split('e');return rf'\({m}\times10^{{{int(e)}}}\)'
def figures(s):
    folder=OUT/'图表';folder.mkdir(exist_ok=True)
    cols=[HexColor('#2d657f'),HexColor('#b85e31'),HexColor('#387a61')]
    grey=HexColor('#dfdfdf');d=Drawing(475,265)
    L,R,B,T=53,457,40,216;y0,y1=.30,.68
    def xy(m,y):return L+(m-1)*(R-L)/11,B+(y-y0)*(T-B)/(y1-y0)
    for j in range(8):
        val=.30+j*.05;y=xy(1,val)[1]
        d.add(Line(L,y,R,y,strokeColor=grey,strokeWidth=.5));d.add(String(L-8,y-3,f'{val:.2f}',fontSize=9,textAnchor='end'))
    for m in range(1,13):d.add(String(xy(m,.3)[0],24,str(m),fontSize=9,textAnchor='middle'))
    d.add(Line(L,B,L,T,strokeColor=black,strokeWidth=.6));d.add(Line(L,B,R,B,strokeColor=black,strokeWidth=.6))
    for j,q in enumerate(['q1','q2','q3']):
        vals=[row[5] for row in s['questions'][q]['point'][:12]]
        assert all(y0<=v<=y1 for v in vals)
        pts=[xy(m+1,v) for m,v in enumerate(vals)]
        d.add(PolyLine([v for p in pts for v in p],strokeColor=cols[j],strokeWidth=1.1,strokeDashArray=None if j!=1 else [3,2]))
        for x,y in pts:d.add(Circle(x,y,2,strokeColor=None,fillColor=cols[j]))
        x=58+j*138;d.add(Line(x,231,x+16,231,strokeColor=cols[j],strokeWidth=1.1));d.add(String(x+21,228,['Q1 fixed field','Q2 R027 original','Q3 Q3F013'][j],fontSize=9))
    d.add(String(14,249,'Sample mean thermal power per mirror area (kW/m2)',fontSize=10))
    d.add(String(250,7,'Specified month (21st)',fontSize=10,textAnchor='middle'))
    art=[('图1-三问月度功率',d)]
    des=load(ROOT/s['questions']['q3']['paths']['design']);d=Drawing(460,386)
    cx,cy,scale=224,190,.43
    def xy2(x,y):return cx+x*scale,cy+y*scale
    for v in range(-300,301,100):
        x,y=xy2(v,v);d.add(Line(x,39,x,341,strokeColor=grey,strokeWidth=.5));d.add(Line(74,y,375,y,strokeColor=grey,strokeWidth=.5))
        d.add(String(x,24,str(v),fontSize=8,textAnchor='middle'));d.add(String(65,y-3,str(v),fontSize=8,textAnchor='end'))
    d.add(Circle(cx,cy,350*scale,fillColor=None,strokeColor=black,strokeWidth=.7))
    tx,ty=xy2(*des['tower_xy']);d.add(Circle(tx,ty,100*scale,fillColor=None,strokeColor=HexColor('#777777'),strokeDashArray=[4,3],strokeWidth=.8))
    for m in des['mirrors']:
        x,y=xy2(m['x'],m['y']);d.add(Circle(x,y,.68,fillColor=cols[1] if m['height']==6.05 else cols[0],strokeColor=None))
    d.add(Line(tx-4,ty,tx+4,ty,strokeColor=black));d.add(Line(tx,ty-4,tx,ty+4,strokeColor=black))
    d.add(String(224,7,'East x (m)',fontSize=10,textAnchor='middle'));d.add(String(8,344,'North y (m)',fontSize=10))
    for j,(label,col) in enumerate([('h = 6.05 m; 582 mirrors',cols[1]),('h = 6.65 m; 2399 mirrors',cols[0])]):
        x=68+j*185;d.add(Circle(x,368,3,fillColor=col,strokeColor=None));d.add(String(x+8,365,label,fontSize=9))
    art.append(('图2-异尺寸镜场',d));results=[]
    for name,d in art:
        pdf=folder/(name+'.pdf');png=folder/(name+'.png');renderPDF.drawToFile(d,str(pdf))
        cmd=['pdftoppm','-r','170','-singlefile','-png',str(pdf),str(folder/name)]
        p=subprocess.run(cmd,capture_output=True,cwd=ROOT)
        save(folder/(name+'-生成.log'),(p.stdout+p.stderr).decode('utf-8',errors='replace'))
        assert p.returncode==0 and png.is_file()
        results.append({'file':png.relative_to(ROOT).as_posix(),'sha256':sha(png),'pdf_sha256':sha(pdf),'command':cmd})
    return results

def integrate():
    assert Path.cwd().resolve()==ROOT,'Explicit authorized workdir required'
    s=load(OUT/'结果与来源-v001.json');e=load(OUT/'实际搜索比较与检验证据-v001.json')
    assert s['all_pass']
    q=s['questions'];a={k:v['annual'] for k,v in q.items()};c=s['comparison'];vals={}
    for k,v in q.items():
        K=k.upper();aa=a[k]
        vals.update({f'{K}_P_MW':f"{aa['power_mw']:.3f}",f'{K}_Q4':f"{aa['q_kw_m2']:.4f}",f'{K}_Q7':f"{aa['q_kw_m2']:.7f}",f'{K}_P4':f"{aa['power_kw']:.4f}",f'{K}_UP4':f"{aa['U_power_kw']:.4f}",f'{K}_AREA':f"{v['total_area_m2']:.4f}",f'{K}_ETA4':f"{aa['point'][0]:.4f}"})
        if k!='q1':vals.update({f'{K}_LOWER4':f"{aa['rating_lower_kw']:.4f}",f'{K}_MARGIN4':f"{aa['rating_margin_kw']:.4f}"})
    vals.update({'Q3_MARGIN2':f"{a['q3']['rating_margin_kw']:.2f}",'MARGIN_PERCENT':f"{a['q3']['rating_margin_kw']/60000*100:.4f}",'AREA_DROP':f"{-c['area_difference_m2']:.3f}",'PAIR_P_DROP':f"{-c['delta_power_kw']:.4f}",'GAIN_PERCENT':f"{c['relative_q_difference']*100:.5f}",'PAIR_DQ7':f"{c['delta_q_kw_m2']:.7f}",'PAIR_LOWER7':f"{c['difference_minus_work_indicator']:.7f}",'PAIR_U_SCI':sci(c['work_indicator_delta_q']),'BASELINE_SHIFT':f"{c['baseline_new_minus_Q2_original']['power_kw']:.4f}",'Q3_AREA_ETA':f"{q['q3']['area_weighted']['point'][-1][0]:.6f}",'Q3_COUNT_ETA':f"{a['q3']['point'][0]:.6f}"})
    p1=[r[5] for r in q['q1']['point'][:12]]
    vals.update({'Q1_MAX_MONTH':str(1+p1.index(max(p1))),'Q1_MIN_MONTH':str(1+p1.index(min(p1))),'Q1_MAX_Q':f'{max(p1):.6f}','Q1_MIN_Q':f'{min(p1):.6f}'})
    low=q['q1']['retrospective_low_survival'];vals.update({'Q1_POST_EFF':f"{low['max_efficiency_U_plus_bound']:.7f}",'Q1_POST_PCT':f"{low['max_power_relative_U_plus_bound']*100:.4f}"})
    table_data={}
    def add(key,num,title,headers,rows,source):
        rendered=table(f'表{num}　{title}',headers,rows);vals[key]=rendered
        table_data[key]={'number':num,'title':title,'headers':headers,'rows':rows,'source':source,'markdown':rendered}
    add('ANNUAL_TABLE',2,'三问年样本平均结果（对应题目表2）',['问题/设计',r'\(\eta\)',r'\(\eta_{\rm cos}\)',r'\(\eta_{\rm sb}\)',r'\(\eta_{\rm trunc}\)',r'\(\overline P\)（MW）',r'\(\overline q\)（kW/m²）'],[[label,*[f'{x:.4f}'for x in a[k]['point'][:4]],f"{a[k]['power_mw']:.3f}",f"{a[k]['q_kw_m2']:.4f}"]for k,label in [('q1','第1问'),('q2','第2问 R027'),('q3','第3问 Q3F013')]],'questions.q1/q2/q3.annual')
    for k,num in [('q1',3),('q2',6),('q3',9)]:
        add(k.upper()+'_MONTH_TABLE',num,{'q1':'固定镜场','q2':'R027','q3':'Q3F013'}[k]+'每月21日平均效率及单位面积功率（对应题目表1）',['月份',r'\(\eta\)',r'\(\eta_{\rm cos}\)',r'\(\eta_{\rm sb}\)',r'\(\eta_{\rm trunc}\)',r'\(\overline q_m\)（kW/m²）'],[[str(i+1),*[f'{x:.4f}'for x in row[:4]],f'{row[5]:.4f}'] for i,row in enumerate(q[k]['point'][:12])],f'questions.{k}.point[:12]')
    for k,num in [('q2',5),('q3',8)]:
        add(k.upper()+'_DESIGN_TABLE',num,{'q2':'R027','q3':'Q3F013'}[k]+'设计参数（对应题目表3）',['塔位（m）','统一宽×高（m）','统一安装高（m）','镜数','总面积（m²）'],[[r'\((0,-15)\)',r'\(6.65\times6.65\)'if k=='q2'else'', '6.00' if k=='q2'else'',str(q[k]['N']),vals[k.upper()+'_AREA']]],f'questions.{k}; actual workbook readback')
    fine=[x for x in e['q2_repair']['records'] if x['fidelity']=='fine']
    fine.sort(key=lambda x:x['name'])
    add('Q2_SEARCH_TABLE',4,'可行性修复的较精全60时点比较（搜索层）',['候选','镜数','总面积（m²）','功率评分（kW）','单位面积评分（kW/m²）'],[[r['name'],r['n'],f"{r['area_m2']:.4f}",f"{r['P_formal_kw']:.3f}",f"{r['q_formal_kw_m2']:.7f}"]for r in fine],'q2_repair.records[fidelity=fine]')
    add('Q3_GROUP_TABLE',7,'Q3F013的六组参数',['组号','镜数','宽（m）','高（m）','安装高（m）','组面积（m²）'],[[g['group'],g['count'],f"{g['width_m'][0]:.2f}",f"{g['height_m'][0]:.2f}",f"{g['installation_height_m'][0]:.2f}",f"{g['area_m2']:.4f}"]for g in q['q3']['dimensions']['groups']],'questions.q3.dimensions.groups')
    add('PAIRED_TABLE',10,'第3问新配对实验的年度比较',['设计','功率（kW）',r'\(U_P\)（kW）',r'\(\overline q\)（kW/m²）',r'\(U_q\)（kW/m²）'],[[label,f"{aa['power_kw']:.4f}",f"{aa['U_power_kw']:.4f}",f"{aa['q_kw_m2']:.7f}",sci(aa['U_q_kw_m2'])]for label,aa in [('R027新基线',s['paired_baseline']['annual']),('Q3F013',a['q3'])]]+[['差（候选−基线）',f"{c['delta_power_kw']:.4f}",'—',f"{c['delta_q_kw_m2']:.7f}",sci(c['work_indicator_delta_q'])]],'paired_baseline; questions.q3; comparison (same paired source)')
    add('VALIDATION_TABLE',11,'已保存正式确认的汇总数值检查',['问题','组合数','最大效率指标','最大功率相对指标（%）','低存活组合数'],[[k.upper(),v['combination_count'],f"{v['max_efficiency_U']:.7f}",f"{v['max_power_relative_U']*100:.5f}",v['low_survival_count']]for k,v in e['validation'].items()],'validation.q1/q2/q3; Q1 original U, low diagnostic separate')
    add('Q3_SEARCH_TABLE',12,'第3问较精全60时点比较（确认前）',['候选','总面积（m²）','功率评分（kW）','单位面积评分（kW/m²）','功率搜索余量（kW）'],[[r['name'],f"{r['area']:.4f}",f"{r['P_score_kw']:.4f}",f"{r['q_score_kw_m2']:.7f}",f"{r['power_search_margin']:.4f}"]for r in e['q3_search']['fine_records']],'q3_search.fine_records; search only')
    template=(OUT/'完整论文内容模板-v001.md').read_text(encoding='utf-8')
    body=template
    for key,value in vals.items():body=body.replace('@'+key+'@',value)
    assert not re.search(r'@[A-Z0-9_]+@',body),'Unfilled data token'
    # Caption numbering is by first occurrence, independent from question table numbers.
    body=body.replace('表6为较精搜索','表4为较精搜索').replace('表4给出的R027','表5给出的R027').replace('规定月度结果见表5','规定月度结果见表6').replace('月度表3、5、9','月度表3、6、9').replace('表4、8分别','表5、8分别')
    body=body.replace('初轮搜索的最好功率候选C22未通过额定工作判据',f"初轮实际比较{e['q2_initial']['coarse_count']}个12时点粗筛候选，其中{e['q2_initial']['fine_count']}个接受全60时点较精评价；最好功率候选C22未通过额定工作判据")
    save(OUT/'完整论文-v001.md',body)
    fig=figures(s)
    converter.ROOT=ROOT;converter.SOURCE=OUT/'完整论文-v001.md';converter.TEX_DIR=OUT
    converter.TARGET=OUT/'完整论文-v001.tex';converter.RECORD=OUT/'Markdown与LaTeX对应-v001.json'
    def compact_table(rows,caption):
        n=len(rows[0]);ratios=[1/n]*n
        if n==3 and '含义'in rows[0]:ratios=[.34,.49,.17]
        if caption.startswith('表2　'):ratios=[.145,.12,.12,.12,.13,.135,.23]
        if caption.startswith('表10　'):ratios=[.21,.21,.14,.21,.23]
        scale=sum(ratios);ratios=[x/scale for x in ratios]
        columns=''.join(r'>{\raggedright\arraybackslash}p{'+f'{x:.6f}'+r'\dimexpr\linewidth-'+str(2*n)+r'\tabcolsep\relax}'for x in ratios)
        out=[r'\par\medskip\noindent\begin{minipage}{\linewidth}',r'\small',r'\textbf{'+converter.inline(caption)+r'}\par\smallskip',r'\begin{tabular}{'+columns+'}',r'\toprule',' & '.join(converter.inline(c)for c in rows[0])+r' \\',r'\midrule']
        out+=[' & '.join(converter.inline(c)for c in row)+r' \\'for row in rows[1:]]
        return out+[r'\bottomrule',r'\end{tabular}',r'\end{minipage}\par\medskip']
    converter.table_tex=compact_table
    receipt=converter.convert()
    tex=converter.TARGET.read_text(encoding='utf-8')
    # Ordinary local layout, no unverified official typography or page limit.
    tex=tex.replace(r'\begin{document}',r'\usepackage[unicode,hidelinks]{hyperref}'+'\n'+r'\begin{document}')
    save(converter.TARGET,tex)
    receipt['tex_sha256']=sha(converter.TARGET)
    receipt['layout']='ordinary ctexart, zihao -4, 23mm margin; shared symbols and captions; no official template claim'
    receipt['source_registry_sha256']=sha(OUT/'结果与来源-v001.json')
    receipt['search_registry_sha256']=sha(OUT/'实际搜索比较与检验证据-v001.json')
    save(converter.RECORD,json.dumps(receipt,ensure_ascii=False,indent=2))
    evidence={'source_registry_sha256':sha(OUT/'结果与来源-v001.json'),'search_registry_sha256':sha(OUT/'实际搜索比较与检验证据-v001.json'),'template_sha256':sha(OUT/'完整论文内容模板-v001.md'),'script_sha256':sha(Path(__file__)),'paper_sha256':sha(converter.SOURCE),'tex_sha256':sha(converter.TARGET),'tables':table_data,'substitutions':{k:v for k,v in vals.items()if not k.endswith('TABLE')},'figures':fig,'new_optical_rays':0,'reference_papers_read':0,'reference_learning':'待材料，不把既有规范当作原文学习'}
    save(OUT/'正文生成证据-v001.json',json.dumps(evidence,ensure_ascii=False,indent=2))
    return {'paper_chars':len(body),'tables':receipt['tables'],'figures':receipt['figures'],'display_equations':receipt['math_display_blocks'],'status':'generated_not_yet_compiled'}
if __name__=='__main__':print(json.dumps(integrate(),ensure_ascii=False))
