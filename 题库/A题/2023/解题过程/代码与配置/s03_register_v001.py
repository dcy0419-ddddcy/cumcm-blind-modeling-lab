"""Register S03 and the pre-reference baseline. No optical evaluation."""
from pathlib import Path
import hashlib, json, shutil, datetime
ROOT = Path(r'C:\Users\admin\OneDrive\Desktop\26国赛-单题盲解区\A-P8C3').resolve()
REC = ROOT / '工作记录'
OUT = REC / '论文/全题整合'
BASE = OUT / '整合与参考学习前基线-v001'
def sha(p): return hashlib.sha256(p.read_bytes()).hexdigest()
def write(p,t):
    assert p.resolve().is_relative_to(ROOT)
    p.parent.mkdir(parents=True,exist_ok=True)
    p.write_text(t,encoding='utf-8')
def append(p,t):
    assert p.resolve().is_relative_to(ROOT)
    with p.open('a',encoding='utf-8') as f:f.write('\n\n'+t+'\n')
def main():
    assert not BASE.exists(), 'Registration already exists; inspect rather than repeat'
    BASE.mkdir(parents=True)
    controls=['00-任务状态.md','记录索引.md','方法库查阅记录.md','决策记录.md','06-更新记录.md','归档清单.md','经验.md']
    for n in controls:
        if (REC/n).exists():shutil.copy2(REC/n,BASE/n)
    files=[]
    for q,v in [(1,1),(2,2),(3,1)]:
        stem=f'第{q}问-模型建立与求解-v{v:03d}'
        for p in [REC/'论文'/f'{stem}.md',REC/'论文/LaTeX'/f'{stem}.tex',REC/'论文/LaTeX'/f'{stem}.pdf', REC/'论文'/f'第{q}问-正文证据映射-v{v:03d}.md']:
            assert p.is_file(),p
            files.append({'path':p.relative_to(ROOT).as_posix(),'sha256':sha(p),'bytes':p.stat().st_size})
    for rel in ['诊断结果/Q02-修复-v001/result2.xlsx','诊断结果/Q03-实施-v001/delivery/result3.xlsx','诊断结果/Q03-实施-v001/delivery/paired-comparison-v001.json','论文/写作规范-v001.md']:
        p=REC/rel;assert p.is_file(),p
        files.append({'path':p.relative_to(ROOT).as_posix(),'sha256':sha(p),'bytes':p.stat().st_size})
    manifests=[]
    for folder in ['方法库','补充资料']:
        for n in ['资料清单-v001.md','manifest-v001.json']:
            p=ROOT/folder/n
            manifests.append({'path':p.relative_to(ROOT).as_posix(),'sha256':sha(p)})
    baseline={'version':'v001','created_at':datetime.datetime.now().astimezone().isoformat(),'purpose':'三问已验收单问成果；整合及参考学习前的追溯基线，不是全题正式冻结','reference_reading_status':'参考原文学习待材料','reference_papers_read':[],'files':files,'checked_manifests':manifests,'notes':'仅保存路径及哈希；未复制全部计算数据。实际未阅读任何参考论文原文。'}
    write(BASE/'baseline.json',json.dumps(baseline,ensure_ascii=False,indent=2))
    rows='\n'.join(f"| [{x['path']}]({(ROOT/x['path']).as_posix()}) | `{x['sha256']}` |" for x in files)
    write(OUT/'整合与参考学习前基线-v001.md','# 整合与参考学习前基线 v001\n\n2026-09-05。三问阶段已获用户验收；本记录只证明当前单问文件版本，不构成完整论文已验收或正式盲解冻结。实际参考原文阅读尚未开始。\n\n| 当前有效文件 | SHA-256 |\n|---|---|\n'+rows+'\n\n原控制文件另存于[基线快照](整合与参考学习前基线-v001/baseline.json)。有效结果的四类来源由本轮结果与来源表另行绑定，保留第2问原确认与第3问新配对基线的区别。\n')
    learning=REC/'论文/参考论文写作学习-v001.md'
    assert not learning.exists()
    write(learning,'# 参考论文写作学习 v001\n\n**状态：参考原文学习待材料。实际阅读参考论文：0篇、0页。**\n\n## 1 授权与检查\n\n用户本轮专门允许已审核、在本工作区内的指定非目标题参考论文，用于写作学习。此授权不包括本题解答、联网或工作区外文件。本次检查工作区根目录、方法库与补充资料清单v001及manifest，另核对工作区内PDF与参考清单文件名。实际可用内容为方法卡M01—M05、Datawhale限定选段、P01/P02及本题自产PDF；没有发现指定参考论文正文或对应非目标题审核清单。没有沿清单URL访问上游，也没有读取工作区外文件。\n\n## 2 阅读范围分类\n\n| 材料 | 本次实际范围 | 状态与限制 |\n|---|---|---|\n| 方法库、补充资料清单v001 | 清单正文与manifest来源/许可字段 | 仅范围核对，不是参考论文学习 |\n| 写作规范-v001.md | 全文 | 用户提供的管理员整理规范；不是参考论文全文 |\n| 三问当前有效正文 | 整合回读；具体版本见基线 | 自身成果，不是外部参考论文 |\n| 指定非目标题参考论文 | 尚无可核对编号、正文、页码 | 未阅读；待材料 |\n\n## 3 学习前基线与待办\n\n阅读前基线见[整合与参考学习前基线](全题整合/整合与参考学习前基线-v001.md)。管理员需要提供论文编号、标题、来源、本地路径、版本、SHA-256、非目标题判定、允许页码/章节及完整性说明；多篇时指定主参考。待材料后才能逐项记录摘要、分析、假设符号、推导、实现、结果、检验局限、图表、全文衔接的实际来源位置与可迁移认识。此处不虚构页码、不提前填入所谓学习结论。\n\n本次可以继续不依赖参考原文的全文整合和一致性检查；参考学习与应用均不标记完成。\n')
    app=REC/'论文/参考写作应用对照-v001.md'; assert not app.exists()
    write(app,'# 参考写作应用对照 v001\n\n**状态：参考原文尚未交付，基于参考原文的应用未开展。**\n\n没有把既有写作规范、个人写作判断或自己的单问论文登记为参考原文学习成果。没有借用参考论文的结果、方法、参数或结论。\n\n| 来源类别 | 本轮允许的实际应用 | 对应位置 | 验证办法 |\n|---|---|---|---|\n| 用户提供的写作规范v001 | 合并公共模型，按任务组织三问，结果先行并解释取舍 | 新建完整论文各章 | 对照自己的有效数据与模型证据 |\n| 三问已验收正文与代码 | 更正抽样零接收等状态表述、统一符号及同分布采样表达 | 公共模型与数值方法 | 见公共模型一致性审查和独立修订记录 |\n| 指定非目标题参考论文原文 | 未开展，无来源页码可登记 | 无 | 待正文与审核清单 |\n\n上表前两项是独立整合，不声称参考原文启发。后续实际学习发生后另建新版本，保留当前未开展记录；新技术认识只登记待验证，不自动改模或重算。\n')
    write(REC/'00-任务状态.md','# 当前任务状态\n\n2026-09-05：**三问阶段成果已获用户验收；全题论文整合与冻结候选准备进行中。**\n\nD048/U055登记第3问Q3F013计算、正式清单、论文及核验获用户验收，原件保持不动。完整论文尚未验收，正式盲解未冻结，管理员归档未确认。\n\n本轮仅整合、保存统计与清单的一致性核对、本地排版和候选包准备，不重跑光学积分、不搜索、不联网、不操作GitHub。R027原确认与Q3新配对基线分开使用；Q3额定工作余量约12.446 kW，不作工程充分裕度解释。\n\n补充写作授权已登记，但工作区未发现指定参考论文及审核清单：**参考原文学习待材料**。继续不依赖参考原文的全文整合，不声称读过或应用参考原文。\n\n现有数据无须因整合重算。静态审查发现状态与同分布采样的文字修正，详见全题整合/公共模型一致性审查；最终文件和PDF逐页核验尚在进行。\n')
    append(REC/'决策记录.md','## D048 — 2026-09-05 — 第3问验收与全题整合授权\n\n依据本轮用户消息，Q3F013的计算、独立确认、result3.xlsx及论文配套记录已验收；不扩展为全局最优、充分工程余量、物理误差量化或管理员归档。三问原件只读，另建全题整合，完整论文与冻结候选待用户整体验收。\n\n用户补充专门允许阅读工作区内指定、已审核非目标题参考论文，仅用于写作。当前实际检查未见正文与对应审核清单，登记参考原文学习待材料，保持0篇0页，不自行找材料。学习前单问基线保存路径与哈希。所有本轮命令显式指定任务目录、编辑使用核对后的绝对路径。\n\nR027原确认值用于第2问正式结果；Q3提升采用新配对数据；旧数值不人为统一。Q3越界事件按现有证据保留于实验记录，不能隐去或无证据认定题解污染。')
    append(REC/'06-更新记录.md','## U055 — 2026-09-05 — 第3问验收登记与整合起点\n\n原任务状态为第3问待验收；用户现已验收计算及论文，更新为三问阶段已验收、全题整合进行中。旧控制快照及单问正文/TeX/PDF/映射/清单哈希见论文/全题整合/整合与参考学习前基线-v001。原阶段和数值成果未覆盖。新增参考论文写作学习、参考写作应用对照v001，均明确参考原文待材料；其内容不是虚构学习。关联D048，后续全题正文/核验/冻结候选尚在编制。')
    append(REC/'记录索引.md','## S03全题整合起点 — D048/U055\n\n三问阶段成果已验收，完整论文与冻结候选尚在准备。\n\n- [整合与参考学习前基线v001](论文/全题整合/整合与参考学习前基线-v001.md)：当前单问版本及哈希。\n- [参考论文写作学习v001](论文/参考论文写作学习-v001.md)：参考原文学习待材料，0篇0页。\n- [参考写作应用对照v001](论文/参考写作应用对照-v001.md)：实际参考原文应用未开展。')
    append(REC/'方法库查阅记录.md','## 2026-09-05 S03整合与补充写作材料检查\n\n实际回读方法库/补充资料的资料清单v001及manifest来源与许可字段、写作规范v001全文；未登记为再次完整阅读方法卡或上游教程。未见指定非目标题参考论文或对应审核清单。参考原文学习待材料，实际参考原文阅读0篇0页；详见论文/参考论文写作学习-v001.md。补充授权只覆盖本工作区指定审核材料，不沿URL联网补齐。自身三问正文与证据回读见基线及S03来源审查。')
    append(REC/'归档清单.md','## S03起点新增记录 — D048/U055\n\n已保存学习前基线（原控制快照及文件SHA）、参考论文写作学习v001和应用对照v001、s03_register_v001.py。三问单问阶段用户已验收；本轮全题记录尚待验收。参考原文待材料，管理员归档未确认；此处不是正式盲解冻结。')
    print(json.dumps({'status':'registered','baseline_files':len(files),'reference_papers_read':0},ensure_ascii=False))
if __name__=='__main__':main()
