from __future__ import annotations

import argparse
import json
import re
import shutil
import zipfile
from pathlib import Path
from xml.etree import ElementTree as ET

import fitz


YEAR_HEADER = re.compile(r"20\d{2}\s*年.*全国大学生数学建模竞赛题目")


def redact_header(source: Path, destination: Path) -> None:
    destination.parent.mkdir(parents=True, exist_ok=True)
    doc = fitz.open(source)
    page = doc[0]
    matched = False

    page_dict = page.get_text("dict")
    for block in page_dict.get("blocks", []):
        for line in block.get("lines", []):
            text = "".join(span.get("text", "") for span in line.get("spans", []))
            compact = re.sub(r"\s+", "", text)
            if YEAR_HEADER.search(text) or (
                re.search(r"20\d{2}年", compact)
                and "全国大学生数学建模竞赛题目" in compact
            ):
                rect = fitz.Rect(line["bbox"])
                rect.x0 = 0
                rect.x1 = page.rect.width
                rect.y0 = max(0, rect.y0 - 2)
                rect.y1 = min(page.rect.height, rect.y1 + 2)
                page.add_redact_annot(rect, fill=(1, 1, 1))
                matched = True

    if not matched:
        raise RuntimeError(f"未在首页找到年份页眉：{source}")

    page.apply_redactions(images=fitz.PDF_REDACT_IMAGE_NONE)
    if hasattr(doc, "del_xml_metadata"):
        doc.del_xml_metadata()
    doc.set_metadata(
        {
            "title": "",
            "author": "",
            "subject": "Blind mathematical modeling exercise",
            "keywords": "",
            "creator": "CUMCM Blind Modeling Lab",
            "producer": "CUMCM Blind Modeling Lab",
            "creationDate": "",
            "modDate": "",
            "trapped": "",
        }
    )
    doc.save(destination, garbage=4, deflate=True, clean=True)
    doc.close()


def sanitize_xlsx(source: Path, destination: Path) -> None:
    destination.parent.mkdir(parents=True, exist_ok=True)
    namespaces = {
        "dc": "http://purl.org/dc/elements/1.1/",
        "dcterms": "http://purl.org/dc/terms/",
        "cp": "http://schemas.openxmlformats.org/package/2006/metadata/core-properties",
    }
    for prefix, uri in namespaces.items():
        ET.register_namespace(prefix, uri)

    with zipfile.ZipFile(source, "r") as src_zip, zipfile.ZipFile(
        destination, "w", compression=zipfile.ZIP_DEFLATED
    ) as dst_zip:
        for item in src_zip.infolist():
            data = src_zip.read(item.filename)
            if item.filename == "docProps/core.xml":
                root = ET.fromstring(data)
                for tag in (
                    f"{{{namespaces['dc']}}}creator",
                    f"{{{namespaces['cp']}}}lastModifiedBy",
                    f"{{{namespaces['dcterms']}}}created",
                    f"{{{namespaces['dcterms']}}}modified",
                    f"{{{namespaces['dc']}}}title",
                    f"{{{namespaces['dc']}}}subject",
                ):
                    node = root.find(tag)
                    if node is not None:
                        node.text = ""
                data = ET.tostring(root, encoding="utf-8", xml_declaration=True)
            dst_zip.writestr(item, data)


def copy_attachment(source: Path, destination: Path) -> None:
    if source.suffix.lower() == ".xlsx":
        sanitize_xlsx(source, destination)
    else:
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, destination)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--mapping", required=True, type=Path)
    args = parser.parse_args()

    mapping = json.loads(args.mapping.read_text(encoding="utf-8"))
    for entry in mapping:
        target = args.output / entry["blind_id"]
        target.mkdir(parents=True, exist_ok=True)
        redact_header(args.root / entry["pdf"], target / "题目.pdf")

        attachment_dir = entry.get("attachments")
        if attachment_dir:
            source_dir = args.root / attachment_dir
            if source_dir.exists():
                files = sorted(p for p in source_dir.rglob("*") if p.is_file())
                for index, file in enumerate(files, start=1):
                    suffix = file.suffix.lower()
                    copy_attachment(file, target / "附件" / f"附件{index:02d}{suffix}")

        readme = (
            f"# 盲题 {entry['blind_id']}\n\n"
            "本目录是独立盲解输入。不得访问其父目录、年度题库、管理员映射、当年论文或互联网。\n\n"
            "- 主题文件：`题目.pdf`\n"
            "- 数据附件：`附件/`（如存在）\n"
            "- 输出目录：`工作记录/`\n"
        )
        (target / "README.md").write_text(readme, encoding="utf-8")
        (target / "工作记录").mkdir(exist_ok=True)


if __name__ == "__main__":
    main()
