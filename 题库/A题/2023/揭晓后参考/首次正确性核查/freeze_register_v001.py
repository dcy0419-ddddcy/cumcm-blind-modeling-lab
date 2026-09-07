from pathlib import Path
import ast,json,hashlib,datetime,shutil
R=Path(r'C:\Users\admin\OneDrive\Desktop\26国赛-单题盲解区\A-P8C3').resolve();O=R/'工作记录/揭晓后对照/首次正确性核查-v001';B=R/'工作记录/冻结候选/盲解-v001'
def sha(b):return hashlib.sha256(b).hexdigest()
def load(p):return json.loads(p.read_text(encoding='utf-8-sig'))
def write(p,s):
    assert p.resolve().is_relative_to(O);assert not p.exists();p.parent.mkdir(parents=True,exist_ok=True);p.write_text(s,encoding='utf-8')
def main():
    assert Path.cwd().resolve()==R
    check=load(O/'冻结前全清单核验-v001.json');bind=load(R/'工作记录/论文/全题整合/S03收尾控制绑定-v001.json')
    assert all(x['passed'] for x in check['manifest_checks']) and not check['checksum_failures']
    assert all(x['kind']=='external' and Path(x['path']).name in bind['controls'] for x in check['failures'])
    resolutions=[]
    for e in check['failures']:
        p=R/e['path'];now=p.read_bytes();assert sha(now)==bind['controls'][p.name]
        old=now[:e['expected_bytes']];method='当前文件前缀，与旧清单哈希精确相等；新增部分对应S03收尾追加'
        if sha(old)!=e['expected_sha256']:
            assert p.name=='00-任务状态.md'
            tree=ast.parse((R/'工作记录/诊断代码/s03_register_v001.py').read_text(encoding='utf-8-sig'))
            candidates=[]
            for n in ast.walk(tree):
                if isinstance(n,ast.Call) and isinstance(n.func,ast.Name) and n.func.id=='write' and len(n.args)>1 and isinstance(n.args[1],ast.Constant) and isinstance(n.args[1].value,str) and n.args[1].value.startswith('# 当前任务状态'):
                    s=n.args[1].value;candidates += [s.encode(),s.replace('\n','\r\n').encode()]
            old=next(b for b in candidates if sha(b)==e['expected_sha256'])
            method='由打包前已保存s03_register脚本中的完整字面量恢复；与旧清单SHA-256精确匹配，未执行旧脚本'
        assert sha(old)==e['expected_sha256']
        dest=O/'冻结证据补充/清单原字节'/p.name;dest.parent.mkdir(parents=True,exist_ok=True);assert not dest.exists();dest.write_bytes(old)
        resolutions.append({**e,'resolution':method,'exact_old_bytes_preserved_at':dest.relative_to(R).as_posix(),'explained_by':'S03第7节、U056、S03收尾控制绑定-v001.json和s03_finish_v001.py','current_hash_matches_prior_closeout':True})
    snapshots=[]
    for name,expected in bind['controls'].items():
        p=R/'工作记录'/name;data=p.read_bytes();assert sha(data)==expected
        dest=O/'冻结证据补充/本轮授权前控制快照'/name;dest.parent.mkdir(parents=True,exist_ok=True);assert not dest.exists();dest.write_bytes(data)
        snapshots.append({'original':p.relative_to(R).as_posix(),'preserved':dest.relative_to(R).as_posix(),'sha256':sha(data),'bytes':len(data)})
    now=datetime.datetime.now().astimezone().isoformat()
    declaration={'frozen_at':now,'version':'盲解-v001','formal_blind_freeze':True,'user_acceptance':'本轮用户接受S03/完整论文/冻结候选并授权先冻结后揭晓','package':B.relative_to(R).as_posix(),'package_manifest_sha256':sha((B/'文件清单-v001.json').read_bytes()),'checksum_file_sha256':sha((B/'SHA256SUMS.txt').read_bytes()),'package_manifest_entries':check['package_count'],'package_files_including_two_manifests':len([p for p in B.rglob('*') if p.is_file()]),'external_dependencies':check['external_count'],'external_direct_match':check['external_count']-len(resolutions),'resolved_historical_control_changes':resolutions,'pre_authorization_snapshots':snapshots,'external_answers_first_access':None,'all_dependencies_preserved':True,'self_contained_for_reading':True,'self_contained_for_raw_rebuild':False,'administrator_archived':'未确认','reference_original_writing_learning':'待材料，不阻塞本轮对照','experience_sha256_unchanged':sha((R/'工作记录/经验.md').read_bytes())}
    write(O/'冻结登记绑定-v001.json',json.dumps(declaration,ensure_ascii=False,indent=2))
    text=f'''# 00 正式盲解冻结登记 v001

正式冻结时间：{now}。冻结版本：**盲解-v001**。依据：用户本轮验收S03、完整论文和候选包，并明确授权先正式冻结、后开展指定题目的答案正确性对照。管理员归档未确认，未操作GitHub。

## 核验和依赖

包内原文件保持不变：清单{check['package_count']}个内容条目，另两份清单文件；实际包内文件数{declaration['package_files_including_two_manifests']}。包清单及校验文件均与S03既存交付哈希相符。原目录依赖{check['external_count']}项中{declaration['external_direct_match']}项原位置哈希相同，5项控制记录发生已登记的S03收尾变化。

五项差异为状态、决策、方法查阅、经验、索引。四项从当前文件前缀提取旧字节，状态从既存注册脚本字面量恢复；全部与原清单哈希完全相等，另存冻结证据补充/清单原字节。它们不是新造内容或重新生成哈希，也没有改写原清单。当前收尾版本全部匹配此前S03收尾绑定，另存授权前快照。差异明细和逐项旧新哈希见[绑定](冻结登记绑定-v001.json)，首次不一致原始结果见[全清单核验](冻结前全清单核验-v001.json)。本轮未更新经验正文。

冻结范围为包内文件、未复制依赖清单中的原目录证据及本次明确的五项原字节解析位置；控制文件后续追加不得代替这些快照。依赖解释与补充快照属于包外冻结证据，不回写包内README的历史待验收状态。

文件清单SHA-256：`{declaration['package_manifest_sha256']}`。

SHA256SUMS文件SHA-256：`{declaration['checksum_file_sha256']}`。

包可独立阅读；完整统计重建/计算仍依赖所列原目录文件和既有本地运行环境。这些原目录证据需要一并保留，不能称独立可重算包。不存在未解释哈希变化或关键依赖缺失；全部核对完成后才登记正式冻结。

## 揭晓范围与状态

截至上述冻结时刻尚未打开外部答案。之后只允许本轮指定题目的公开题面/参考论文/官方评述检索、正确性对照与累计最多30分钟必要诊断。外部资料单独存本目录；不改模型、数值、Excel或论文，不搜索优化，不更新经验/方法卡/写作规范。首次联网和首次答案接触时间另行登记。

此前“参考原文写作学习待材料”仍未完成，不作为本轮答案对照前置阻塞。本声明另存包外，正式冻结不等于管理员已归档，也不把揭晓后认识追溯为盲解认识。
'''
    write(O/'00-冻结登记-v001.md',text)
    print(json.dumps({'formal_freeze':True,'time':now,'package_files':declaration['package_files_including_two_manifests'],'external':check['external_count'],'explained_changes':len(resolutions)},ensure_ascii=False))
if __name__=='__main__':main()
