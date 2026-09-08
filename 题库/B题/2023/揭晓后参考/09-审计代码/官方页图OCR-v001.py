from __future__ import annotations

import hashlib
import json
from datetime import datetime
from pathlib import Path

import cv2
import numpy as np
from rapidocr_onnxruntime import RapidOCR


REVIEW_ROOT = Path(r"C:\Users\admin\OneDrive\Desktop\26国赛\题库\B题\2023\揭晓后参考")
PAPER_ROOT = REVIEW_ROOT / "02-原始论文"
OCR_ROOT = REVIEW_ROOT / "03-论文提取" / "OCR"
AUDIT_PATH = REVIEW_ROOT / "10-审计结果" / "官方论文OCR审计-v001.json"


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def ordered_page_images(paper_dir: Path) -> list[Path]:
    return sorted((paper_dir / "官方页图").glob("page-*.jpg"))


def main() -> None:
    OCR_ROOT.mkdir(parents=True, exist_ok=True)
    engine = RapidOCR()
    paper_records = []

    for paper_dir in sorted(p for p in PAPER_ROOT.iterdir() if p.is_dir() and p.name.startswith("P")):
        page_images = ordered_page_images(paper_dir)
        if not page_images:
            continue
        page_records = []
        text_blocks = []
        for page_number, image_path in enumerate(page_images, start=1):
            image = cv2.imdecode(np.fromfile(image_path, dtype=np.uint8), cv2.IMREAD_COLOR)
            if image is None:
                raise RuntimeError(f"Cannot read {image_path}")
            enlarged = cv2.resize(image, None, fx=2.0, fy=2.0, interpolation=cv2.INTER_CUBIC)
            result, elapsed = engine(enlarged)
            lines = []
            if result:
                for box, text, score in result:
                    lines.append({
                        "text": text,
                        "score": float(score),
                        "box": [[float(x), float(y)] for x, y in box],
                    })
            page_text = "\n".join(line["text"] for line in lines)
            text_blocks.append(f"===== PAGE {page_number:03d} =====\n{page_text}\n")
            page_records.append({
                "page": page_number,
                "image_relative_path": image_path.relative_to(REVIEW_ROOT).as_posix(),
                "image_sha256": sha256(image_path),
                "line_count": len(lines),
                "mean_confidence": (sum(line["score"] for line in lines) / len(lines)) if lines else None,
                "elapsed_seconds": elapsed,
                "lines": lines,
            })
            print(f"{paper_dir.name} page {page_number}/{len(page_images)} lines={len(lines)}")

        text_path = OCR_ROOT / f"{paper_dir.name}-全文OCR-v001.txt"
        text_path.write_text("\n".join(text_blocks), encoding="utf-8")
        paper_records.append({
            "paper_id": paper_dir.name,
            "page_count": len(page_images),
            "ocr_text_relative_path": text_path.relative_to(REVIEW_ROOT).as_posix(),
            "ocr_text_sha256": sha256(text_path),
            "pages": page_records,
        })

    audit = {
        "schema_version": "official-paper-image-ocr-v001",
        "generated_at": datetime.now().astimezone().isoformat(),
        "engine": "RapidOCR ONNX Runtime",
        "preprocessing": "2x bicubic resize; page order follows official sequential image ids",
        "interpretation": "OCR is a navigation aid. All consequential numbers and claims must be checked against page images.",
        "papers": paper_records,
    }
    AUDIT_PATH.write_text(json.dumps(audit, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
