from __future__ import annotations

import hashlib
import json
import urllib.request
from datetime import datetime
from pathlib import Path

from PIL import Image


REVIEW_ROOT = Path(r"C:\Users\admin\OneDrive\Desktop\26国赛\题库\B题\2023\揭晓后参考")
PAPER_ROOT = REVIEW_ROOT / "02-原始论文"
AUDIT_PATH = REVIEW_ROOT / "10-审计结果" / "官方论文下载清单-v001.json"

PAPERS = [
    {
        "id": "P01-B477",
        "display_id": "B477",
        "page_url": "https://dxs.moe.gov.cn/zx/a/hd_sxjm_sxjmlw_2023qgdxssxjmjslwzs_2023btlw/231104/1865120.shtml",
        "image_ids": list(range(8439973, 8440023)),
    },
    {
        "id": "P02-B311",
        "display_id": "B311",
        "page_url": "https://dxs.moe.gov.cn/zx/a/hd_sxjm_sxjmlw_2023qgdxssxjmjslwzs_2023btlw/231104/1865118.shtml",
        "image_ids": list(range(8439939, 8439973)),
    },
    {
        "id": "P03-B226",
        "display_id": "B226",
        "page_url": "https://dxs.moe.gov.cn/zx/a/hd_sxjm_sxjmlw_2023qgdxssxjmjslwzs_2023btlw/231104/1865116.shtml",
        "image_ids": list(range(8439888, 8439939)),
    },
]


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def download(url: str, destination: Path) -> None:
    request = urllib.request.Request(
        url,
        headers={
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
            "Referer": "https://dxs.moe.gov.cn/",
        },
    )
    with urllib.request.urlopen(request, timeout=60) as response:
        data = response.read()
    if len(data) < 4096 or data[:2] != b"\xff\xd8":
        raise RuntimeError(f"Downloaded object is not a plausible JPEG: {url}, bytes={len(data)}")
    destination.write_bytes(data)


def build_pdf(image_paths: list[Path], output_path: Path) -> None:
    images: list[Image.Image] = []
    try:
        for image_path in image_paths:
            with Image.open(image_path) as source:
                images.append(source.convert("RGB"))
        if not images:
            raise RuntimeError("No images supplied")
        first, rest = images[0], images[1:]
        first.save(output_path, "PDF", save_all=True, append_images=rest, resolution=150.0)
    finally:
        for image in images:
            image.close()


def main() -> None:
    records = []
    for paper in PAPERS:
        paper_dir = PAPER_ROOT / paper["id"]
        image_dir = paper_dir / "官方页图"
        image_dir.mkdir(parents=True, exist_ok=True)
        image_paths: list[Path] = []
        page_records = []
        for page_no, image_id in enumerate(paper["image_ids"], start=1):
            url = f"https://univs-news-1256833609.file.myqcloud.com/123/upload/resources/image/{image_id}.jpg"
            destination = image_dir / f"page-{page_no:03d}-{image_id}.jpg"
            if not destination.exists():
                download(url, destination)
            with Image.open(destination) as im:
                width, height = im.size
            image_paths.append(destination)
            page_records.append(
                {
                    "page": page_no,
                    "image_id": image_id,
                    "url": url,
                    "relative_path": destination.relative_to(REVIEW_ROOT).as_posix(),
                    "size_bytes": destination.stat().st_size,
                    "width_px": width,
                    "height_px": height,
                    "sha256": sha256(destination),
                }
            )
        pdf_path = paper_dir / f"{paper['id']}-官方页图合订-v001.pdf"
        build_pdf(image_paths, pdf_path)
        records.append(
            {
                "id": paper["id"],
                "display_id": paper["display_id"],
                "official_page_url": paper["page_url"],
                "page_count": len(image_paths),
                "pdf_relative_path": pdf_path.relative_to(REVIEW_ROOT).as_posix(),
                "pdf_size_bytes": pdf_path.stat().st_size,
                "pdf_sha256": sha256(pdf_path),
                "pages": page_records,
            }
        )
        print(f"{paper['id']}: pages={len(image_paths)}, pdf={pdf_path}, sha256={records[-1]['pdf_sha256']}")

    audit = {
        "schema_version": "official-paper-image-download-v001",
        "generated_at": datetime.now().astimezone().isoformat(timespec="seconds"),
        "source": "中国大学生在线 2023高教社杯全国大学生数学建模竞赛论文展示",
        "preservation_note": "PDF is a local page-order compilation of the downloaded official JPEG pages; image content was not edited.",
        "papers": records,
    }
    AUDIT_PATH.parent.mkdir(parents=True, exist_ok=True)
    AUDIT_PATH.write_text(json.dumps(audit, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
