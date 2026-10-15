"""Run the repo's checks: the one command CI, pre-commit and agents all use.

    python scripts/check.py          # everything
    python scripts/check.py lint     # black, ruff, mypy, bandit
    python scripts/check.py tests    # pytest, GUI smoke test, coverage gate

Every tool runs under this interpreter, so call it with the venv's python. Each check runs even if an earlier
one failed; the exit status is non-zero if any did.
"""

import os
import subprocess  # nosec B404 - runs fixed dev-tool commands only
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PY = sys.executable

CHECKS = {
    "lint": [
        ("black", [PY, "-m", "black", "--check", "src", "tests", "scripts"]),
        ("ruff", [PY, "-m", "ruff", "check", "src", "tests", "scripts"]),
        ("mypy", [PY, "-m", "mypy"]),
        ("bandit", [PY, "-m", "bandit", "-q", "-c", "pyproject.toml", "-r", "src"]),
    ],
    # The coverage gate (omit, fail_under) lives in pyproject.toml; it reads the data pytest-cov just wrote.
    "tests": [
        ("pytest", [PY, "-m", "pytest", "-q"]),
        ("smoke test", [PY, "scripts/ci_smoke_test.py"]),
        ("coverage gate", [PY, "-m", "coverage", "report"]),
    ],
}


def main(argv: list[str]) -> int:
    groups = argv or list(CHECKS)
    unknown = [g for g in groups if g not in CHECKS]
    if unknown:
        sys.stderr.write(f"unknown group(s) {', '.join(unknown)}; choose from {', '.join(CHECKS)}\n")
        return 2
    env = {**os.environ, "QT_QPA_PLATFORM": os.environ.get("QT_QPA_PLATFORM", "offscreen")}
    failed = []
    for group in groups:
        for name, cmd in CHECKS[group]:
            sys.stdout.write(f"--- {name}\n")
            sys.stdout.flush()
            if subprocess.run(cmd, cwd=ROOT, env=env, check=False).returncode:  # noqa: S603  # nosec B603
                failed.append(name)
    sys.stdout.write(f"--- FAILED: {', '.join(failed)}\n" if failed else "--- all checks passed\n")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
