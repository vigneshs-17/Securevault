#!/usr/bin/env python3
"""One-command quality gate: lint, types, tests, dependency audit.

    python scripts/check.py            full run (what CI runs)
    python scripts/check.py --fast     lint + tests only (pre-commit)
    python scripts/check.py --install-hooks   enable .githooks/pre-commit
"""
import argparse
import os
import shutil
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BACKEND = ROOT / "backend"
FRONTEND = ROOT / "frontend"
_venv = BACKEND / "venv" / ("Scripts" if os.name == "nt" else "bin") / ("python.exe" if os.name == "nt" else "python")
NPM = shutil.which("npm") or "npm"  # npm is npm.cmd on Windows
PY = str(_venv) if _venv.exists() else sys.executable


def run(name, command, cwd, optional=False):
    started = time.time()
    print(f"\n==> {name}", flush=True)
    try:
        code = subprocess.call(command, cwd=cwd)
    except FileNotFoundError:
        code = 127
    status = "ok" if code == 0 else ("skipped" if optional and code == 127 else "FAILED")
    print(f"<== {name}: {status} ({time.time() - started:.1f}s)", flush=True)
    return code == 0 or (optional and code == 127)


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--fast", action="store_true", help="skip type check and dependency audits")
    parser.add_argument("--install-hooks", action="store_true")
    args = parser.parse_args()

    if args.install_hooks:
        subprocess.check_call(["git", "config", "core.hooksPath", ".githooks"], cwd=ROOT)
        print("Pre-commit hook enabled (.githooks/pre-commit).")
        return 0

    steps = [
        ("backend lint (ruff)", [PY, "-m", "ruff", "check", "app", "tests", "scripts"], BACKEND, False),
        ("backend tests (pytest)", [PY, "-m", "pytest", "-q", "-x"], BACKEND, False),
        ("frontend tests (node --test)", [NPM, "test", "--silent"], FRONTEND, False),
    ]
    if not args.fast:
        steps += [
            ("backend types (mypy)", [PY, "-m", "mypy", "app"], BACKEND, False),
            ("backend dependency audit (pip-audit)", [PY, "-m", "pip_audit", "-r", "requirements.txt", "--progress-spinner", "off"], BACKEND, False),
        ]
    results = [run(*step) for step in steps]
    print("\nAll checks passed." if all(results) else "\nSome checks failed.")
    return 0 if all(results) else 1


if __name__ == "__main__":
    sys.exit(main())
