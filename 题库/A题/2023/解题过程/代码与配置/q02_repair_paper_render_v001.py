"""Render an already compiled local Q2 v002 PDF into a fresh repair QA folder.

Prepared without execution.  This script does not compile, inspect fonts, run
optics, or render the original question.  Every invocation preserves old pages.
"""
from __future__ import annotations

import hashlib
import json
import re
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
TEX_DIR = ROOT / "工作记录/论文/LaTeX"
STEM = "第2问-模型建立与求解-v002"
PDF = TEX_DIR / (STEM + ".pdf")
TEX = TEX_DIR / (STEM + ".tex")
LOG = TEX_DIR / (STEM + ".log")
SOURCE = ROOT / "工作记录/论文" / (STEM + ".md")
QA_BASE = TEX_DIR / "第2问-修复稿-v002-页面核验"
DIAGNOSTICS = ROOT / "工作记录/诊断结果/Q02-修复-v001"
CORRESPONDENCE = DIAGNOSTICS / "Q02-修复稿Markdown与TeX对应-v001.json"
LATEST = DIAGNOSTICS / "Q02-修复稿PDF自动核验-v001.json"


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def local(path: Path) -> Path:
    path = path.resolve()
    if not path.is_relative_to(ROOT):
        raise ValueError(f"Path outside the authorized workspace: {path}")
    return path


def fresh_attempt() -> Path:
    local(QA_BASE).mkdir(parents=True, exist_ok=True)
    number = 1
    while True:
        destination = QA_BASE / f"attempt-{number:03d}"
        try:
            local(destination).mkdir(exist_ok=False)
            return destination
        except FileExistsError:
            number += 1


def render() -> dict:
    from PIL import Image, ImageDraw
    from pypdf import PdfReader

    for path in (PDF, TEX, LOG, SOURCE, CORRESPONDENCE):
        if not local(path).is_file():
            raise FileNotFoundError(path)
    binding = json.loads(CORRESPONDENCE.read_text(encoding="utf-8"))
    if binding["source_sha256"] != sha(SOURCE) or binding["tex_sha256"] != sha(TEX):
        raise ValueError("Manuscript/TeX changed after conversion; regenerate before rendering")
    if PDF.stat().st_mtime_ns < TEX.stat().st_mtime_ns or LOG.stat().st_mtime_ns < TEX.stat().st_mtime_ns:
        raise ValueError("PDF or compilation log predates the current TeX")
    log = LOG.read_text(encoding="utf-8", errors="replace")
    log_digest = sha(LOG)
    if re.search(r"^!\s|Emergency stop|Fatal error|No pages of output", log, re.M):
        raise ValueError("Compilation failure; do not render a truncated PDF as complete")
    if "Output written on" not in log:
        raise ValueError("Compilation log has no successful PDF output marker")
    reader = PdfReader(PDF)
    page_count = len(reader.pages)
    if page_count <= 0:
        raise ValueError("PDF has no pages")
    pdf_digest = sha(PDF)
    out = fresh_attempt()
    command = ["pdftoppm", "-r", "90", "-png", str(PDF), str(out / "page")]
    raster = subprocess.run(command, capture_output=True, cwd=ROOT)
    (out / "渲染日志.txt").write_bytes(raster.stdout + raster.stderr)
    if raster.returncode:
        raise RuntimeError(f"pdftoppm failed: {raster.returncode}; logs retained in {out}")
    text_command = ["pdftotext", "-layout", str(PDF), str(out / "PDF文本.txt")]
    extracted = subprocess.run(text_command, capture_output=True, cwd=ROOT)
    (out / "文本提取日志.txt").write_bytes(extracted.stdout + extracted.stderr)
    if extracted.returncode:
        raise RuntimeError(f"pdftotext failed: {extracted.returncode}; logs retained in {out}")
    files = sorted(out.glob("page-*.png"), key=lambda p: int(p.stem.split("-")[-1]))
    page_numbers = [int(path.stem.split("-")[-1]) for path in files]
    if page_numbers != list(range(1, page_count + 1)):
        raise ValueError("Rendered page sequence does not match PDF page count")
    contacts = []
    for start in range(0, len(files), 4):
        sheet = Image.new("RGB", (1320, 1860), "#dddddd")
        for index, path in enumerate(files[start:start + 4]):
            with Image.open(path) as original:
                picture = original.convert("RGB")
            picture.thumbnail((620, 877))
            tile = Image.new("RGB", (660, 930), "white")
            tile.paste(picture, ((660 - picture.width) // 2, 32))
            ImageDraw.Draw(tile).text((12, 8), path.name, fill="black")
            sheet.paste(tile, ((index % 2) * 660, (index // 2) * 930))
        target = out / f"contact-{start + 1:02d}.png"
        sheet.save(target)
        contacts.append(target.relative_to(ROOT).as_posix())
    if sha(PDF) != pdf_digest:
        raise ValueError("PDF changed during rendering; this attempt cannot certify it")
    if (sha(SOURCE) != binding["source_sha256"] or sha(TEX) != binding["tex_sha256"]
            or sha(LOG) != log_digest):
        raise ValueError("Manuscript, TeX or compilation log changed during rendering")
    flags = [value for value in ("Overfull", "Underfull", "Missing character", "Infinite glue",
                                "LaTeX Warning", "! LaTeX Error") if value in log]
    record = {"source": SOURCE.relative_to(ROOT).as_posix(), "source_sha256": sha(SOURCE),
              "tex": TEX.relative_to(ROOT).as_posix(), "tex_sha256": sha(TEX),
              "pdf": PDF.relative_to(ROOT).as_posix(), "pdf_sha256": pdf_digest,
              "log_sha256": log_digest, "pages": page_count, "rendered_pages": len(files),
              "page_numbers": page_numbers, "render_directory": out.relative_to(ROOT).as_posix(),
              "contact_sheets": contacts,
              "page_files": [{"file": p.relative_to(ROOT).as_posix(), "sha256": sha(p)} for p in files],
              "tex_log_flags": flags, "render_stderr_bytes": len(raster.stderr),
              "text_stderr_bytes": len(extracted.stderr), "commands": [command, text_command],
              "markdown_counts": {key: binding[key] for key in ("math_display_blocks", "tables", "figures")},
              "visual_inspection": "pending human/model inspection; page counting is not visual QA",
              "old_renderings_overwritten": False, "new_optical_rays": 0}
    serialized = json.dumps(record, ensure_ascii=False, indent=2)
    (out / "PDF自动核验.json").write_text(serialized, encoding="utf-8")
    local(DIAGNOSTICS).mkdir(parents=True, exist_ok=True)
    LATEST.write_text(serialized, encoding="utf-8")
    return record


if __name__ == "__main__":
    result = render()
    print(json.dumps({key: result[key] for key in
                      ("pdf", "pages", "rendered_pages", "render_directory", "tex_log_flags")}, ensure_ascii=False))
