"""Runs the browser harness (tests/harness.py): all three dashboard pages at phone, landscape and
desktop sizes against stubbed Firebase and mock jobs. Needs Playwright's Chromium."""
import subprocess
import sys
from pathlib import Path

import pytest

HARNESS = Path(__file__).resolve().parent / "harness.py"


@pytest.mark.skipif(not HARNESS.exists(), reason="harness missing")
def test_dashboard_pages_render_at_all_sizes(tmp_path):
    proc = subprocess.run([sys.executable, str(HARNESS), str(tmp_path)], capture_output=True, text=True, timeout=300)
    assert proc.returncode == 0, "\n".join(l for l in proc.stdout.splitlines() if l.startswith("FAIL")) or proc.stderr[-2000:]
