"""Convert the current, undelivered Q2 manuscript v002 to local TeX only.

Prepared without execution.  The root separately compiles and verifies the PDF.
No old v001 manuscript, TeX, PDF, rendering or numerical output is modified.
"""
from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
PAPER = ROOT / "工作记录/论文"
TEX_DIR = PAPER / "LaTeX"
SOURCE = PAPER / "第2问-模型建立与求解-v002.md"
TARGET = TEX_DIR / "第2问-模型建立与求解-v002.tex"
RECORD = ROOT / "工作记录/诊断结果/Q02-修复-v001/Q02-修复稿Markdown与TeX对应-v001.json"
TABLE_CAPTION = re.compile(r"^表(?:[A-Za-z]+)?\d+(?:\s|\u3000|[:：])")
FIGURE_CAPTION = re.compile(r"^图(?:[A-Za-z]+)?\d+(?:\s|\u3000|[:：])")
INLINE_TOKEN = re.compile(r"(\\\(.*?\\\)|\*\*.+?\*\*|`[^`]+`|\[[^\]]+\]\([^\n]*?\))")


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def within_root(path: Path) -> Path:
    path = path.resolve()
    if not path.is_relative_to(ROOT):
        raise ValueError(f"Path is outside the authorized workspace: {path}")
    return path


def escape_text(value: str) -> str:
    mapping = {
        "\\": r"\textbackslash{}", "&": r"\&", "%": r"\%", "#": r"\#",
        "_": r"\_", "$": r"\$", "{": r"\{", "}": r"\}",
        "~": r"\textasciitilde{}", "^": r"\textasciicircum{}",
        "²": r"\textsuperscript{2}", "³": r"\textsuperscript{3}",
        "⁻": r"\textsuperscript{-}", "×": r"\(\times\)",
        "≤": r"\(\le\)", "≥": r"\(\ge\)", "−": r"\(-\)",
    }
    return "".join(mapping.get(char, char) for char in value)


def inline(value: str) -> str:
    parts, cursor = [], 0
    for token in INLINE_TOKEN.finditer(value):
        parts.append(escape_text(value[cursor:token.start()]))
        item = token.group(0)
        if item.startswith(r"\("):
            parts.append(item)  # Preserve authored math rather than rewriting it.
        elif item.startswith("**"):
            parts.append(r"\textbf{" + inline(item[2:-2]) + "}")
        elif item.startswith("`"):
            parts.append(r"\texttt{" + escape_text(item[1:-1]) + "}")
        else:
            label = item[1:item.index("](")]
            parts.append(inline(label))  # Keep readable label; no external fetch.
        cursor = token.end()
    parts.append(escape_text(value[cursor:]))
    return "".join(parts)


def table_cells(line: str) -> list[str]:
    """Split Markdown columns while retaining pipes in inline math/code."""
    line = line.strip()
    cells, current = [], []
    math_mode = code_mode = False
    pos = 0
    while pos < len(line):
        pair = line[pos:pos + 2]
        if pair == r"\(" and not code_mode:
            math_mode = True
            current.append(pair)
            pos += 2
            continue
        if pair == r"\)" and not code_mode:
            math_mode = False
            current.append(pair)
            pos += 2
            continue
        if pair == r"\|" and not math_mode and not code_mode:
            current.append("|")
            pos += 2
            continue
        char = line[pos]
        if char == "`" and not math_mode:
            code_mode = not code_mode
        if char == "|" and not math_mode and not code_mode:
            cells.append("".join(current).strip())
            current = []
        else:
            current.append(char)
        pos += 1
    cells.append("".join(current).strip())
    if cells and cells[0] == "":
        cells.pop(0)
    if cells and cells[-1] == "":
        cells.pop()
    if math_mode or code_mode:
        raise ValueError("Unclosed inline math/code inside a table row")
    return cells


def check_formula(body: list[str], start_line: int) -> list[str]:
    joined = "\n".join(body)
    if not joined.strip():
        raise ValueError(f"Empty display formula near source line {start_line}")
    stack = []
    for match in re.finditer(r"\\(begin|end)\{([^}]+)\}", joined):
        action, env = match.groups()
        if action == "begin":
            stack.append(env)
        elif not stack or stack.pop() != env:
            raise ValueError(f"Unbalanced math environments near source line {start_line}")
    if stack:
        raise ValueError(f"Unclosed math environment near source line {start_line}: {stack}")
    return re.findall(r"\\tag\{([^}]+)\}", joined)


def table_tex(rows: list[list[str]], caption: str) -> list[str]:
    n = len(rows[0])
    if n == 3 and any("含义" in cell for cell in rows[0]):
        ratios = [0.29, 0.54, 0.17]
    elif caption.startswith("表S5"):
        ratios = [.07,.08,.12,.06,.15,.12,.105,.09,.09,.115]
    elif caption.startswith("表S6"):
        ratios = [.07,.06,.14,.14,.12,.11,.14,.10,.12]
    else:
        ratios = [1.0 / n] * n
    columns = "".join(
        r">{\raggedright\arraybackslash}p{" + f"{ratio:.6f}"
        + r"\dimexpr\linewidth-" + str(2 * n) + r"\tabcolsep\relax}"
        for ratio in ratios
    )
    header = " & ".join(inline(cell) for cell in rows[0]) + r" \\"
    result = [r"\par\medskip\noindent\begin{minipage}{\linewidth}",
              r"\footnotesize" if n >= 7 else r"\small",
              r"\textbf{" + inline(caption) + r"}\par\smallskip",
              r"\begin{tabular}{" + columns + "}",
              r"\toprule", header, r"\midrule"]
    result.extend(" & ".join(inline(cell) for cell in row) + r" \\" for row in rows[1:])
    result.extend([r"\bottomrule",r"\end{tabular}", r"\end{minipage}\par\medskip"])
    return result


def convert() -> dict:
    within_root(SOURCE)
    within_root(TARGET)
    text = SOURCE.read_text(encoding="utf-8")
    lines = text.splitlines()
    if not lines or not any(line.startswith("# ") for line in lines):
        raise ValueError("Manuscript must have a Markdown title")
    if text.count(r"\(") != text.count(r"\)"):
        raise ValueError("Unbalanced inline math delimiters in manuscript")
    for line_number, line in enumerate(lines, 1):
        opened = False
        for token in re.finditer(r"\\([()])", line):
            if token.group(1) == "(":
                if opened:
                    raise ValueError(f"Nested inline math near line {line_number}")
                opened = True
            else:
                if not opened:
                    raise ValueError(f"Closing inline delimiter precedes opening near line {line_number}")
                opened = False
        if opened:
            raise ValueError(f"Inline math must close on the same source line: {line_number}")
    if text.count(r"\[") != text.count(r"\]"):
        raise ValueError("Unbalanced display math delimiters in manuscript")
    if any(line.lstrip().startswith("```") for line in lines):
        raise ValueError("Code-fenced blocks require explicit conversion; do not silently print TeX source")
    out = [r"""\documentclass[UTF8,fontset=windows,zihao=-4]{ctexart}
\usepackage{amsmath,amssymb,graphicx,booktabs,longtable,array,geometry}
\geometry{a4paper,margin=23mm}
\setlength{\parskip}{0.35em}
\setlength{\emergencystretch}{2em}
\setlength{\tabcolsep}{3pt}
\renewcommand{\arraystretch}{1.25}
\setcounter{tocdepth}{2}
\begin{document}
"""]
    blocks, tables, figures, tags = [], [], [], []
    pending_caption = None
    equation_group = False
    i = 0
    while i < len(lines):
        s = lines[i].strip()
        if not s:
            out.append("")
            i += 1
            continue
        if pending_caption is not None and not s.startswith("|"):
            raise ValueError(f"Table caption is not followed by a Markdown table near line {i + 1}")
        if s == r"\[":
            first = i + 1
            body = []
            i += 1
            while i < len(lines) and lines[i].strip() != r"\]":
                if lines[i].strip() == r"\[":
                    raise ValueError(f"Nested display delimiter near line {i + 1}")
                body.append(lines[i])
                i += 1
            if i >= len(lines):
                raise ValueError(f"Unclosed display formula near line {first}")
            block_tags = check_formula(body, first)
            tags.extend(block_tags)
            blocks.append({"start_line": first, "end_line": i + 1, "tags": block_tags})
            out.extend([r"\[", *body, r"\]"])
            if equation_group:
                out.append(r"\end{minipage}\par")
                equation_group = False
            i += 1
            continue
        if r"\[" in s or r"\]" in s:
            raise ValueError(f"Display delimiters must occupy separate lines: {i + 1}")
        if TABLE_CAPTION.match(s):
            pending_caption = s
            i += 1
            continue
        if s.startswith("|"):
            first, raw_rows = i + 1, []
            while i < len(lines) and lines[i].strip().startswith("|"):
                raw_rows.append(table_cells(lines[i]))
                i += 1
            if len(raw_rows) < 2 or not raw_rows[0] or any(not cell for cell in raw_rows[0]):
                raise ValueError(f"Missing/nonempty table header near line {first}")
            n = len(raw_rows[0])
            if len(raw_rows[1]) != n or not all(re.fullmatch(r":?-{3,}:?", c) for c in raw_rows[1]):
                raise ValueError(f"Invalid Markdown header separator near line {first + 1}")
            if any(len(row) != n for row in raw_rows):
                raise ValueError(f"Inconsistent table column count near line {first}")
            if pending_caption is None:
                raise ValueError(f"Missing explicit table caption near line {first}")
            rows = [raw_rows[0], *raw_rows[2:]]
            tables.append({"start_line": first, "caption": pending_caption,
                           "columns": n, "body_rows": len(rows) - 1, "header": rows[0]})
            out.extend(table_tex(rows, pending_caption))
            pending_caption = None
            continue
        if s.startswith("!["):
            match = re.fullmatch(r"!\[(.*?)\]\((.*)\)", s)
            if match is None:
                raise ValueError(f"Unsupported image syntax near line {i + 1}")
            raw_path = match.group(2).strip().removeprefix("<").removesuffix(">")
            if re.match(r"^[A-Za-z]+://", raw_path):
                raise ValueError("Only local workspace images are permitted")
            candidate = Path(raw_path)
            image = within_root(candidate if candidate.is_absolute() else SOURCE.parent / candidate)
            if not image.is_file() or image.suffix.lower() not in {".png", ".jpg", ".jpeg", ".pdf"}:
                raise ValueError(f"Missing/unsupported local image: {image}")
            # Both directories are within ROOT; relative graphics path is portable.
            import os
            relative = Path(os.path.relpath(image, TEX_DIR)).as_posix()
            if any(char in relative for char in "{}\n\r"):
                raise ValueError("Unsupported brace/newline in image filename")
            first = i + 1
            i += 1
            while i < len(lines) and not lines[i].strip():
                i += 1
            if i >= len(lines) or not FIGURE_CAPTION.match(lines[i].strip()):
                raise ValueError(f"Image at line {first} needs a following numbered figure caption")
            caption = lines[i].strip()
            figures.append({"source_line": first, "caption": caption,
                            "file": image.relative_to(ROOT).as_posix(), "sha256": sha(image)})
            out.extend([r"\par\medskip\noindent\begin{minipage}{\linewidth}\centering",
                        r"\includegraphics[width=\linewidth,height=0.72\textheight,keepaspectratio]{\detokenize{"
                        + relative + "}}" + r"\par",
                        r"{\small\raggedright " + inline(caption) + r"\par}\end{minipage}\par\medskip"])
            i += 1
            continue
        if s.startswith("> "):
            s = s[2:]
        heading = next(((prefix, command) for prefix, command in
                        [("#### ", "subsubsection"), ("### ", "subsection"), ("## ", "section")]
                        if s.startswith(prefix)), None)
        if s.startswith("# "):
            out.append(r"\begin{center}{\LARGE\bfseries " + inline(s[2:]) + r"}\end{center}")
        elif heading:
            prefix, command = heading
            out.append("\\" + command + "*{" + inline(s[len(prefix):]) + "}")
        elif re.fullmatch(r"[-*_]{3,}", s):
            out.append(r"\par\medskip\hrule\medskip")
        elif s.startswith("- "):
            out.append(r"\begin{itemize}")
            while i < len(lines) and lines[i].strip().startswith("- "):
                out.append(r"\item " + inline(lines[i].strip()[2:]))
                i += 1
            out.append(r"\end{itemize}")
            continue
        else:
            j = i + 1
            while j < len(lines) and not lines[j].strip():
                j += 1
            if j < len(lines) and lines[j].strip() == r"\[":
                out.append(r"\par\noindent\begin{minipage}{\linewidth}")
                equation_group = True
            out.append(inline(s))
        i += 1
    if pending_caption is not None or equation_group:
        raise ValueError("Unfinished caption or equation group at end of manuscript")
    if len(tags) != len(set(tags)):
        raise ValueError("Duplicate explicitly authored equation tags")
    out.append(r"\end{document}")
    TEX_DIR.mkdir(parents=True, exist_ok=True)
    TARGET.write_text("\n".join(out) + "\n", encoding="utf-8")
    record = {"source": SOURCE.relative_to(ROOT).as_posix(), "source_sha256": sha(SOURCE),
              "tex": TARGET.relative_to(ROOT).as_posix(), "tex_sha256": sha(TARGET),
              "math_display_blocks": len(blocks), "tables": len(tables), "figures": len(figures),
              "display_details": blocks, "equation_tags": tags,
              "table_details": tables, "figure_details": figures,
              "basic_checks": {"title_present": True, "math_delimiters_balanced": True,
                               "math_environments_balanced": True, "unique_equation_tags": True,
                               "table_headers_separators_and_column_counts_valid": True},
              "fixed_equation_or_table_count_required": False,
              "layout": "ordinary ctexart; same fontset as old local workflow; not an official template",
              "compilation_performed": False, "visual_inspection": "pending after root compilation/rendering",
              "old_v001_modified": False, "internet_or_dependency_install": False, "new_optical_rays": 0}
    within_root(RECORD).parent.mkdir(parents=True, exist_ok=True)
    RECORD.write_text(json.dumps(record, ensure_ascii=False, indent=2), encoding="utf-8")
    return record


if __name__ == "__main__":
    result = convert()
    print(json.dumps({key: result[key] for key in
                      ("source", "tex", "math_display_blocks", "tables", "figures")}, ensure_ascii=False))
