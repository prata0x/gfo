"""Lint configuration regression tests."""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent


def _run_ruff(args: list[str]) -> subprocess.CompletedProcess[str]:
    ruff = shutil.which("ruff") or (REPO_ROOT / ".venv" / "bin" / "ruff")
    return subprocess.run(
        [str(ruff), *args],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        check=False,
    )


def test_no_unused_noqa_directives() -> None:
    """RUF100 must be active so dead `# noqa` comments are caught (issue #553).

    Uses ``--extend-select RUF100`` so only ``noqa`` for rules the project
    actually enables (E/F/I/UP/B) are judged dead, matching the project's
    ruff configuration.
    """
    result = _run_ruff(["check", "--extend-select", "RUF100", "."])
    assert result.returncode == 0, (
        "RUF100 found unused noqa directives:\n" + result.stdout + result.stderr
    )
