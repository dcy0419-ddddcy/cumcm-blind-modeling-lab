"""Q3 preparation only: metadata, hashes and document checks; never imports evaluators."""
from pathlib import Path
import hashlib
import json
import re
import sys
from datetime import datetime

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / '工作记录/诊断结果/Q03-准备-v001'

def local(rel):
    p = (ROOT / rel).resolve()
    if not p.is_relative_to(ROOT):
        raise ValueError('outside approved task root')
    return p

def sha(p):
    return hashlib.sha256(p.read_bytes()).hexdigest()

def read_json(p):
    return json.loads(p.read_text(encoding='utf-8-sig'))

def save(name, obj):
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / name).write_text(json.dumps(obj, ensure_ascii=False, indent=2), encoding='utf-8')

def baseline():
    checks, protected = [], {}
    for folder in ['方法库', '补充资料']:
        manifest = read_json(local(folder + '/manifest-v001.json'))
        for entry in manifest['files']:
            rel = folder + '/' + entry['path']
            p = local(rel)
            exists = p.is_file()
            actual = sha(p) if exists else None
            checks.append(dict(path=rel, version=entry['version'], exists=exists,
                bytes=p.stat().st_size if exists else None,
                content_screened=entry['content_screened'], allowed_scope=entry['allowed_scope'],
                expected_sha256=entry['sha256'], actual_sha256=actual,
                passed=exists and actual == entry['sha256'] and entry['content_screened'],
                note='Byte hashing is not a claim to have read the body. No source URL opened.'))
            if exists:
                protected[rel] = actual
    rels = ['AGENTS.md', '题目.pdf',
        '工作记录/阶段记录/S01-题目理解-v001.md',
        '工作记录/阶段记录/S01-补充澄清-v001.md',
        '工作记录/阶段记录/Q02-可行性修复与独立确认-v001.md',
        '工作记录/阶段记录/Q02-第2问结果初稿-v001.md',
        '工作记录/论文/第2问-模型建立与求解-v002.md',
        '工作记录/论文/LaTeX/第2问-模型建立与求解-v002.tex',
        '工作记录/论文/LaTeX/第2问-模型建立与求解-v002.pdf',
        '工作记录/论文/第2问-正文证据映射-v002.md']
    base = '工作记录/诊断结果/Q02-修复-v001/'
    rels += [base + x for x in ['result2.xlsx', '最终拟提交候选冻结.json',
        '独立确认结论.json', '搜索与确认冻结配置-v004.json',
        'frozen/design.bundle.json', 'frozen/design.metadata.json', 'frozen/design.mirrors.csv']]
    # Hash only code named in the final, approved binding; do not load or execute it.
    config = read_json(local(base + '搜索与确认冻结配置-v004.json'))
    bindings = config['bindings']
    def visit(value):
        if isinstance(value, dict):
            for key, val in value.items():
                if isinstance(key, str) and key.endswith('.py'):
                    p = local(key if '/' in key or '\\' in key else '工作记录/诊断代码/' + key)
                    if p.is_file():
                        rels.append(p.relative_to(ROOT).as_posix())
                visit(val)
        elif isinstance(value, list):
            for val in value:
                visit(val)
    visit(bindings)
    for rel in sorted(set(rels)):
        protected[rel] = sha(local(rel))
    freeze = read_json(local(base + '最终拟提交候选冻结.json'))
    checks += [dict(path=base + 'result2.xlsx', passed=sha(local(base + 'result2.xlsx')) == freeze['excel_sha256']),
        dict(path=base + 'frozen/design.bundle.json', passed=sha(local(base + 'frozen/design.bundle.json')) == freeze['bundle_sha256'])]
    save('资料与只读基线核验-v001.json', dict(created=datetime.now().isoformat(),
        mode='metadata and file hashes only; no numerical/model execution',
        checks=checks, all_pass=all(x['passed'] for x in checks), protected_sha256=protected))

def verify():
    prior = read_json(OUT / '资料与只读基线核验-v001.json')
    checks = [dict(check='unchanged', path=r, passed=local(r).is_file() and sha(local(r)) == h)
        for r, h in prior['protected_sha256'].items()]
    paths = [ROOT / '工作记录/阶段记录/Q03-约束梳理与候选方案-v001.md'] + list(OUT.glob('*.md'))
    checks.append(dict(check='stage_exists', passed=paths[0].is_file()))
    for p in paths:
        if not p.is_file():
            continue
        text = p.read_text(encoding='utf-8-sig')
        checks.append(dict(check='balanced_math', path=str(p.relative_to(ROOT)),
            passed=text.count('\\[') == text.count('\\]') and text.count('\\(') == text.count('\\)')))
        # Check table structure without confusing escaped norm bars with columns.
        lines = text.splitlines()
        table_rows = []
        for line in lines + ['']:
            if line.lstrip().startswith('|'):
                table_rows.append(line)
            elif table_rows:
                counts = [len(re.split(r'(?<!\\)\|', row)) for row in table_rows]
                header_ok = len(table_rows) >= 2 and bool(re.fullmatch(r'[\s|:\-]+', table_rows[1]))
                checks.append(dict(check='table_header_and_columns', path=str(p.relative_to(ROOT)),
                    first_row=table_rows[0], passed=header_ok and len(set(counts)) == 1))
                table_rows = []
        for label, target in re.findall(r'\[([^\]\n]+)\]\(([^)\n]+)\)', text):
            target = target.strip('<>').split('#')[0]
            if not target or '://' in target:
                continue
            # The unchanged historical snapshot retains links relative to its
            # original control-file location; resolve those at that location.
            parent = ROOT / '工作记录' if p.name == '进入本阶段前任务状态.md' else p.parent
            q = (parent / target).resolve()
            checks.append(dict(check='link', path=str(p.relative_to(ROOT)), target=target,
                passed=q.is_relative_to(ROOT) and q.exists()))
    for name in ['00-任务状态.md','记录索引.md','方法库查阅记录.md','决策记录.md','06-更新记录.md','归档清单.md']:
        p = ROOT / '工作记录' / name
        text = p.read_text(encoding='utf-8-sig')
        checks.append(dict(check='Q3_control_updated', path=name, passed='Q03' in text or '第3问' in text))
        for label, target in re.findall(r'\[([^\]\n]+)\]\(([^)\n]+)\)', text):
            target = target.strip('<>').split('#')[0]
            if 'Q03' not in target and 'q03' not in target:
                continue
            q = (p.parent / target).resolve()
            # This report is written below; do not pre-certify its self link.
            if q == OUT / '交付文件核验-v001.json':
                continue
            checks.append(dict(check='Q3_control_link', path=name, target=target,
                passed=q.is_relative_to(ROOT) and q.exists()))
    artifacts = {p.relative_to(ROOT).as_posix():sha(p) for p in paths if p.is_file()}
    artifacts[Path(__file__).resolve().relative_to(ROOT).as_posix()] = sha(Path(__file__))
    report = dict(created=datetime.now().isoformat(),
        all_pass=all(x['passed'] for x in checks), count=len(checks), checks=checks,
        artifact_sha256=artifacts,
        limit='File integrity/link/math-delimiter checks only. Static scientific review is in Markdown. No Q3 numerical validation performed.')
    save('交付文件核验-v001.json', report)
    checks.append(dict(check='report_written', passed=(OUT / '交付文件核验-v001.json').is_file()))
    report.update(count=len(checks), all_pass=all(x['passed'] for x in checks))
    save('交付文件核验-v001.json', report)

if __name__ == '__main__':
    {'baseline': baseline, 'verify': verify}[sys.argv[1]]()
