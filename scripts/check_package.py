"""Smoke-test a built wheel in an isolated venv.

Usage: python scripts/check_package.py dist/famulix-0.1.0-py3-none-any.whl

Uses only stdlib + pip, so it works in bare slim containers.
"""

from __future__ import annotations

import os
import subprocess
import sys
import tempfile
from pathlib import Path


def main(argv: list[str]) -> int:
    if len(argv) < 2:
        print("usage: check_package.py <wheel-path>", file=sys.stderr)
        return 2
    wheel = Path(argv[1]).resolve()
    if not wheel.exists():
        print(f"wheel not found: {wheel}", file=sys.stderr)
        return 2
    with tempfile.TemporaryDirectory(prefix="famulix-check-") as tmp:
        venv = Path(tmp) / "venv"
        subprocess.check_call([sys.executable, "-m", "venv", str(venv)])
        pip = venv / "bin" / "pip"
        py = venv / "bin" / "python"
        env = dict(os.environ, PIP_DISABLE_PIP_VERSION_CHECK="1")
        subprocess.check_call([str(pip), "install", "--quiet", str(wheel)], env=env)
        result = subprocess.run(
            [str(py), "-c", "import famulix; print(famulix.__version__)"],
            capture_output=True,
            text=True,
            env=env,
        )
        if result.returncode:
            print(result.stderr, file=sys.stderr)
            return 1
        version = result.stdout.strip()
        print(f"imported famulix {version}")
        result2 = subprocess.run(
            [str(py), "-m", "famulix.cli", "--help"],
            capture_output=True,
            text=True,
            env=env,
        )
        if result2.returncode:
            print(result2.stderr, file=sys.stderr)
            return 1
        print("famulix CLI loads")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
