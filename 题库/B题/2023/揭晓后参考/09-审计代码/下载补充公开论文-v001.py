from __future__ import annotations

import hashlib
import json
import urllib.parse
import urllib.request
from datetime import datetime
from pathlib import Path

from pypdf import PdfReader


REVIEW_ROOT = Path(r"C:\Users\admin\OneDrive\Desktop\26国赛\题库\B题\2023\揭晓后参考")
PAPER_ROOT = REVIEW_ROOT / "02-原始论文"
AUDIT_PATH = REVIEW_ROOT / "10-审计结果" / "补充公开论文下载清单-v001.json"

PAPERS = [
    {
        "id": "P04-张泽宇等",
        "title": "基于多目标规划的多波束测线布设模型",
        "repository_page": "https://github.com/zhangzeyu2002/2023_CUMCM_Problem_B",
        "filename": "基于多目标规划的多波束测线布设模型.pdf",
        "raw_base": "https://raw.githubusercontent.com/zhangzeyu2002/2023_CUMCM_Problem_B/main/",
        "award_claim": "作者仓库声明2023年全国大学生数学建模竞赛B题国家二等奖；论文后发表于《实验科学与技术》",
    },
    {
        "id": "P05-史鸿宇等",
        "title": "多波束测深系统的条带覆盖宽度及重叠率的数值模拟与分析",
        "repository_page": "https://github.com/qfpqhyl/CUMCM2023B",
        "filename": "B 多波束测深系统的条带覆盖宽度及重叠率的数值模拟与分析 史鸿宇 郭心仪 田博松.pdf",
        "raw_base": "https://raw.githubusercontent.com/qfpqhyl/CUMCM2023B/main/",
        "award_claim": "作者仓库声明2023年全国大学生数学建模竞赛B题河北省一等奖",
    },
]


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def download(url: str, destination: Path) -> None:
    request = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(request, timeout=120) as response:
        data = response.read()
    if len(data) < 10000 or not data.startswith(b"%PDF"):
        raise RuntimeError(f"Not a plausible PDF: {url}, bytes={len(data)}")
    destination.write_bytes(data)


def main() -> None:
    records = []
    for paper in PAPERS:
        paper_dir = PAPER_ROOT / paper["id"]
        paper_dir.mkdir(parents=True, exist_ok=True)
        output_path = paper_dir / paper["filename"]
        raw_url = paper["raw_base"] + urllib.parse.quote(paper["filename"])
        download(raw_url, output_path)
        reader = PdfReader(str(output_path))
        records.append(
            {
                **paper,
                "raw_url": raw_url,
                "local_relative_path": output_path.relative_to(REVIEW_ROOT).as_posix(),
                "size": output_path.stat().st_size,
                "page_count": len(reader.pages),
                "encrypted": reader.is_encrypted,
                "sha256": sha256(output_path),
            }
        )
        print(f"{paper['id']}: pages={len(reader.pages)}, bytes={output_path.stat().st_size}, sha256={sha256(output_path)}")
    AUDIT_PATH.write_text(
        json.dumps(
            {
                "schema_version": "supplementary-public-paper-download-v001",
                "downloaded_at": datetime.now().astimezone().isoformat(),
                "records": records,
            },
            ensure_ascii=False,
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )


if __name__ == "__main__":
    main()
