from pathlib import Path
import datetime
import hashlib
import json

W = Path(r"C:\Users\admin\OneDrive\Desktop\26国赛-单题盲解区\A-P8C3")
P = W / "工作记录/揭晓后对照/首次正确性核查-v001"
B = W / "工作记录/冻结候选/盲解-v001"


def sha(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for block in iter(lambda: f.read(4 * 1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


binding = json.loads((P / "冻结登记绑定-v001.json").read_text(encoding="utf-8"))
manifest = json.loads((B / "文件清单-v001.json").read_text(encoding="utf-8-sig"))
failures = []
for row in manifest["files"]:
    path = (B / row["path"]).resolve()
    ok = path.is_file() and sha(path) == row["sha256"] and path.stat().st_size == row["bytes"]
    if not ok:
        failures.append(row["path"])
sums_fail = []
for line in (B / "SHA256SUMS.txt").read_text(encoding="utf-8-sig").splitlines():
    expected, rel = line.split("  ", 1)
    path = (B / rel).resolve()
    if not path.is_file() or sha(path) != expected:
        sums_fail.append(rel)
out = {
    "checked_at": datetime.datetime.now().astimezone().isoformat(),
    "manifest_sha256": sha(B / "文件清单-v001.json"),
    "checksum_file_sha256": sha(B / "SHA256SUMS.txt"),
    "expected_manifest_sha256": "ed23098187e4479ab250744f6cc35fc84e1ec5bb25afe7e6b4ac21851c0da357",
    "expected_checksum_file_sha256": "9e6b950d124e16454aaf1715d21d2be183432e2703f4b92ff9a10d0d01820439",
    "manifest_entries_checked": len(manifest["files"]),
    "manifest_entry_failures": failures,
    "checksum_lines_checked": len((B / "SHA256SUMS.txt").read_text(encoding="utf-8-sig").splitlines()),
    "checksum_failures": sums_fail,
}
out["passed"] = (
    not failures
    and not sums_fail
    and out["manifest_sha256"] == out["expected_manifest_sha256"]
    and out["checksum_file_sha256"] == out["expected_checksum_file_sha256"]
)
(P / "冻结后复核-v001.json").write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")
print(json.dumps(out, ensure_ascii=False))
