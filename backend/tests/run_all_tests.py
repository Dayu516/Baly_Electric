"""一鍵跑所有測試。

Usage:
    cd backend
    .venv/Scripts/python.exe tests/run_all_tests.py
"""

import subprocess
import sys
import time


def run_pytest(label: str, path: str) -> bool:
    print(f"\n{'='*60}")
    print(f"  {label}")
    print(f"{'='*60}\n")

    result = subprocess.run(
        [sys.executable, "-m", "pytest", path, "-v", "--tb=short"],
        env={**__import__("os").environ, "PYTHONIOENCODING": "utf-8", "PYTHONPATH": "."},
        cwd=str(__import__("pathlib").Path(__file__).resolve().parent.parent),
    )
    return result.returncode == 0


def run(label: str, script: str) -> bool:
    print(f"\n{'='*60}")
    print(f"  {label}")
    print(f"{'='*60}\n")

    result = subprocess.run(
        [sys.executable, script],
        env={**__import__("os").environ, "PYTHONIOENCODING": "utf-8", "PYTHONPATH": "."},
        cwd=str(__import__("pathlib").Path(__file__).resolve().parent.parent),
    )
    return result.returncode == 0


def main():
    start = time.time()
    results = []

    results.append(("Smoke Test (核心流程)", run("Smoke Test", "tests/smoke_test.py")))
    results.append(("Permission Test (權限 + 審計 + 分類樹)", run("Permission Test", "tests/test_permissions.py")))
    results.append(("Integration Tests (Service 級)", run_pytest("Integration Test", "tests/integration/")))

    elapsed = time.time() - start
    print(f"\n{'='*60}")
    print(f"  ALL TESTS SUMMARY ({elapsed:.1f}s)")
    print(f"{'='*60}")
    all_pass = True
    for name, ok in results:
        mark = "PASS" if ok else "FAIL"
        print(f"  [{mark}] {name}")
        if not ok:
            all_pass = False

    print(f"{'='*60}")
    sys.exit(0 if all_pass else 1)


if __name__ == "__main__":
    main()