# Testing strategy — Gold Dashboard V2

## Current

- **Manual / smoke:** `python3 scripts/integrate_bloomberg.py` with real files under `data/raw/` — must complete without error and refresh `data/*.csv`.
- **Unit (planned):** `tests/test_integrate_bloomberg.py` with a tiny synthetic openpyxl workbook mirroring the wide 3-column layout (no need for full Bloomberg data in CI).

## Dependencies

`pytest` optional; core pipeline uses `numpy`, `pandas`, `openpyxl` (see `requirements.txt`).
