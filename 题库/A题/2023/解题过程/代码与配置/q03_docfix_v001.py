"""Pre-delivery wording correction; numerical evidence is never modified."""
from pathlib import Path
import json,hashlib
ROOT=Path(__file__).resolve().parents[2];O=ROOT/'工作记录/诊断结果/Q03-实施-v001'
def run():
    paths=[ROOT/'工作记录/阶段记录/Q03-分组搜索与独立确认-v001.md',ROOT/'工作记录/阶段记录/Q03-第3问结果初稿-v001.md']
    dest=O/'records/计数口径与单位更正前';dest.mkdir(exist_ok=False)
    report=[]
    for p in paths:
        before=p.read_text(encoding='utf-8-sig');(dest/p.name).write_bytes(p.read_bytes());after=before
        replacements={'低样本q评分':'低样本q评分／(kW/m²)','抽样零存活计数':'合并存活数为0组合数','抽样零接收计数':'合并接收数为0组合数（含前列）','较精q点':'较精q点／(kW/m²)','与基线q差':'与基线q差／(kW/m²)','配对搜索SE |':'配对搜索SE／(kW/m²) |','年单位面积影响量 |':'年单位面积影响量／(kW/m²) |','| Pi1/Pi0 |':r'| \(\Pi_1/\Pi_0\) |','| Pi2/Pi1 |':r'| \(\Pi_2/\Pi_1\) |','| Pi2/Pi0 |':r'| \(\Pi_2/\Pi_0\) |'}
        changes=[]
        for a,b in replacements.items():
            if a in after:changes.append({'before':a,'after':b});after=after.replace(a,b)
        after=after.replace('这些是启发式评分；零计数按原报告保存，','两列零计数是可重叠的原始计数：接收数为0包含存活数为0的组合，不能将二者相加当作互斥状态数。例如Q3R000低样本互斥状态为1个抽样零存活、1个正存活但抽样零接收。这些是启发式评分；零计数按原报告保存，')
        p.write_text(after,encoding='utf-8',newline='\n');report.append({'file':str(p.relative_to(ROOT)),'changes':changes,'before_sha256':hashlib.sha256((dest/p.name).read_bytes()).hexdigest(),'after_sha256':hashlib.sha256(p.read_bytes()).hexdigest()})
    (O/'records/计数口径与单位修订-v001.json').write_text(json.dumps({'changes':report,'reason':'non-exclusive raw zero counts mislabeled as potentially exclusive statuses; add units and render energy labels; no number changed','before_location':str(dest.relative_to(ROOT))},ensure_ascii=False,indent=2),encoding='utf-8')
    return report
if __name__=='__main__':print(json.dumps(run(),ensure_ascii=False))
