"""Re-render the golden stories under examples/ from their committed beats and prose.

Run this deliberately after a template change, look at the diff, then commit.
"""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "skills" / "proudhuman" / "scripts" / "proudhuman.py"

for d in sorted((ROOT / "examples").iterdir()):
    if (d / "beats.json").is_file():
        out = subprocess.run([sys.executable, str(SCRIPT), "render", str(d)], capture_output=True, text=True, encoding="utf-8")
        print(out.stdout.strip() or out.stderr.strip())
