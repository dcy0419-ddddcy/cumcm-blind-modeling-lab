from pathlib import Path
R=Path(__file__).resolve().parents[2];W=R/'工作记录';H=W/'诊断代码';O=W/'诊断结果/Q02-搜索-v001'
f=H/'q02_search_delivery_v001.py';s=f.read_text(encoding='utf-8-sig')
a="  lines=s.splitlines()\n  for i,line in enumerate(lines):\n   if line.startswith('|')"
z="  lines=s.splitlines();in_math=False\n  for i,line in enumerate(lines):\n   if line.strip()==r'\\[':in_math=True;continue\n   if line.strip()==r'\\]':in_math=False;continue\n   if in_math:continue\n   if line.startswith('|')"
assert a in s;s=s.replace(a,z).replace('交付文件核验-v001.json','交付文件核验-v002.json').replace('归档哈希清单-v001.json','归档哈希清单-v002.json').replace("'delivery_file_audit'","'delivery_file_audit_v002'")
(H/'q02_search_delivery_v002.py').write_text(s,encoding='utf-8')
f=W/'记录索引.md';s=f.read_text(encoding='utf-8-sig');s=s.replace('诊断结果/Q02-搜索-v001/交付文件核验-v001.json','诊断结果/Q02-搜索-v001/交付文件核验-v002.json').replace('诊断结果/Q02-搜索-v001/归档哈希清单-v001.json','诊断结果/Q02-搜索-v001/归档哈希清单-v002.json');f.write_text(s,encoding='utf-8')
f=W/'00-任务状态.md';s=f.read_text(encoding='utf-8-sig').replace('更新U035','更新U036');f.write_text(s,encoding='utf-8')
