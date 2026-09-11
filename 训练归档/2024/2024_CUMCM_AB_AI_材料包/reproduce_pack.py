"""Portable, read-only verification entry point for this material package.

Run from any directory after moving or renaming the package:
    python reproduce_pack.py

The script does not recompute and overwrite frozen outputs. It verifies every
frozen A/B file against the freeze manifest, then executes the packaged A and B
test suites in memory with bytecode generation disabled.
"""

from __future__ import annotations

import hashlib
import importlib.util
import io
import json
import os
from pathlib import Path
import sys
import time
import traceback
import types
import unittest


ROOT = Path(__file__).resolve().parent
A_ROOT = ROOT / "03_A题_独立成果"
B_ROOT = ROOT / "04_B题_独立成果"
AUDIT_ROOT = ROOT / "06_审计"


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def load_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Cannot create an import spec for {path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def install_namespace(name: str, path: Path) -> None:
    module = types.ModuleType(name)
    module.__path__ = [str(path)]
    module.__package__ = name
    sys.modules[name] = module


def verify_frozen_ab() -> dict:
    manifest_path = AUDIT_ROOT / "freeze_manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8-sig"))
    checked = []
    errors = []
    for item in manifest["files"]:
        source_path = item["path"]
        if source_path.startswith("independent/A/"):
            candidate = A_ROOT / source_path.removeprefix("independent/A/")
        elif source_path.startswith("independent/B/"):
            candidate = B_ROOT / source_path.removeprefix("independent/B/")
        else:
            continue
        if not candidate.is_file():
            errors.append({"path": source_path, "error": "missing"})
            continue
        actual = sha256_file(candidate)
        checked.append(source_path)
        if actual != item["sha256"]:
            errors.append(
                {
                    "path": source_path,
                    "error": "sha256_mismatch",
                    "expected": item["sha256"],
                    "actual": actual,
                }
            )
    return {
        "freeze_id": manifest["freeze_id"],
        "files_checked": len(checked),
        "expected_ab_files": 45,
        "status": "pass" if len(checked) == 45 and not errors else "fail",
        "errors": errors,
    }


def run_a_tests() -> dict:
    # The frozen test file imports the original namespace. Recreate that
    # namespace in memory and point it at the package-local frozen module.
    install_namespace("work_independent", ROOT)
    install_namespace("work_independent.A", A_ROOT)
    install_namespace("work_independent.A.src", A_ROOT / "src")
    load_module(
        "work_independent.A.src.bench_dragon",
        A_ROOT / "src" / "bench_dragon.py",
    )
    tests = load_module("portable_a_tests", A_ROOT / "tests" / "test_models.py")
    names = sorted(
        name
        for name, value in vars(tests).items()
        if name.startswith("test_") and callable(value)
    )
    failures = []
    started = time.perf_counter()
    for name in names:
        try:
            getattr(tests, name)()
        except BaseException:  # Preserve the exact failing test and traceback.
            failures.append({"test": name, "traceback": traceback.format_exc()})
    duration = time.perf_counter() - started
    return {
        "framework": "direct execution of packaged pytest-style test functions",
        "tests_run": len(names),
        "expected_tests": 5,
        "duration_seconds": round(duration, 6),
        "status": "pass" if len(names) == 5 and not failures else "fail",
        "failures": failures,
    }


def run_b_tests() -> dict:
    tests = load_module("portable_b_tests", B_ROOT / "tests" / "test_solver.py")
    suite = unittest.defaultTestLoader.loadTestsFromModule(tests)
    stream = io.StringIO()
    started = time.perf_counter()
    result = unittest.TextTestRunner(stream=stream, verbosity=2).run(suite)
    duration = time.perf_counter() - started
    return {
        "framework": "unittest",
        "tests_run": result.testsRun,
        "expected_tests": 6,
        "duration_seconds": round(duration, 6),
        "status": "pass"
        if result.testsRun == 6 and result.wasSuccessful()
        else "fail",
        "failures": len(result.failures),
        "errors": len(result.errors),
        "details": stream.getvalue(),
    }


def check_required_outputs() -> dict:
    paths = [
        A_ROOT / "outputs" / "result1.xlsx",
        A_ROOT / "outputs" / "result2.xlsx",
        A_ROOT / "outputs" / "result4.xlsx",
        B_ROOT / "results" / "summary.json",
        ROOT / "07_文档成品" / "2024_CUMCM_A题_独立论文.pdf",
        ROOT / "07_文档成品" / "2024_CUMCM_B题_独立论文.pdf",
        ROOT / "07_文档成品" / "官方范例对比与下次比赛方法手册.pdf",
    ]
    missing = [str(path.relative_to(ROOT)).replace("\\", "/") for path in paths if not path.is_file()]
    return {
        "files_checked": len(paths),
        "status": "pass" if not missing else "fail",
        "missing": missing,
    }


def main() -> int:
    os.environ["PYTHONDONTWRITEBYTECODE"] = "1"
    sys.dont_write_bytecode = True
    try:
        import numpy
        import scipy

        dependencies = {
            "python": sys.version.split()[0],
            "numpy": numpy.__version__,
            "scipy": scipy.__version__,
        }
        report = {
            "schema_version": "1.0.0",
            "package_root_name": ROOT.name,
            "read_only_run": True,
            "dependencies": dependencies,
            "freeze_integrity": verify_frozen_ab(),
            "A_tests": run_a_tests(),
            "B_tests": run_b_tests(),
            "required_outputs": check_required_outputs(),
        }
    except BaseException:
        report = {
            "schema_version": "1.0.0",
            "package_root_name": ROOT.name,
            "status": "error",
            "traceback": traceback.format_exc(),
        }
        print(json.dumps(report, ensure_ascii=False, indent=2))
        return 1

    statuses = [
        report["freeze_integrity"]["status"],
        report["A_tests"]["status"],
        report["B_tests"]["status"],
        report["required_outputs"]["status"],
    ]
    report["status"] = "pass" if all(item == "pass" for item in statuses) else "fail"
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0 if report["status"] == "pass" else 1


if __name__ == "__main__":
    raise SystemExit(main())
