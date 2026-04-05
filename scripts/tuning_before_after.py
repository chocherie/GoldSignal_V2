#!/usr/bin/env python3
"""Print before/after OOS-concat metrics; write .md + Excel-pasteable .tsv; open .tsv on macOS."""

from __future__ import annotations

import os
import platform
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))
os.chdir(ROOT)
os.environ.setdefault("GOLD_DATA_DIR", str(ROOT / "data"))


def main() -> None:
    from gold_signal.tuning.compare_report import (
        before_after_to_markdown,
        load_before_after_compare,
        write_compare_reports,
    )

    c = load_before_after_compare()
    print(before_after_to_markdown(c))
    md_p, tsv_p = write_compare_reports(data=c)
    print(f"\nWrote: {md_p}\n       {tsv_p}  (paste TSV into Excel or open in Excel)", file=sys.stderr)
    if platform.system() == "Darwin":
        subprocess.run(["open", str(tsv_p)], check=False)


if __name__ == "__main__":
    main()
