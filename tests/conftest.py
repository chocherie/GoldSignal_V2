import sys
from pathlib import Path

# Repo root (contains backend/ and data/)
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))
