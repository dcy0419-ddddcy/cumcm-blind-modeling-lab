from pathlib import Path
import datetime
import hashlib
import json


WORKSPACE = Path(r"C:\Users\admin\OneDrive\Desktop\26国赛-单题盲解区\A-P8C3")
PACKAGE = WORKSPACE / "工作记录/冻结候选/盲解-v001"
OUT = Path(__file__).resolve().parent / "冻结成果复核-v001.json"


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(4 * 1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


manifest_path = PACKAGE / "文件清单-v001.json"
checksum_path = PACKAGE / "SHA256SUMS.txt"
manifest = json.loads(manifest_path.read_text(encoding="utf-8-sig"))

manifest_failures = []
for row in manifest["files"]:
    path = PACKAGE / row["path"]
    if not path.is_file() or path.stat().st_size != row["bytes"] or sha256(path) != row["sha256"]:
        manifest_failures.append(row["path"])

checksum_failures = []
checksum_lines = checksum_path.read_text(encoding="utf-8-sig").splitlines()
for line in checksum_lines:
    expected, relative = line.split("  ", 1)
    path = PACKAGE / relative
    if not path.is_file() or sha256(path) != expected:
        checksum_failures.append(relative)

result = {
    "checked_at": datetime.datetime.now().astimezone().isoformat(),
    "scope": "冻结候选包内文件；不重新计算模型或结果",
    "manifest_sha256": sha256(manifest_path),
    "checksum_file_sha256": sha256(checksum_path),
    "expected_manifest_sha256": "ed23098187e4479ab250744f6cc35fc84e1ec5bb25afe7e6b4ac21851c0da357",
    "expected_checksum_file_sha256": "9e6b950d124e16454aaf1715d21d2be183432e2703f4b92ff9a10d0d01820439",
    "manifest_entries_checked": len(manifest["files"]),
    "manifest_entry_failures": manifest_failures,
    "checksum_lines_checked": len(checksum_lines),
    "checksum_failures": checksum_failures,
}
result["passed"] = (
    not manifest_failures
    and not checksum_failures
    and result["manifest_sha256"] == result["expected_manifest_sha256"]
    and result["checksum_file_sha256"] == result["expected_checksum_file_sha256"]
)
OUT.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
print(json.dumps(result, ensure_ascii=False))
