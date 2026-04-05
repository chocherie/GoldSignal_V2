# Bloomberg BDH Excel — paste plan (Gold Dashboard V2)

## Data locality

All **on-disk** inputs for `scripts/integrate_bloomberg.py` must stay **inside this project** (the **Gold Dashboard V2** folder). `GOLD_DATA_DIR` and `GOLD_UPLOAD_DIR` are resolved relative to the project root when relative, and absolute paths **outside** the project are rejected. Store exports under e.g. **`data/raw/`** and **`data/raw/Bloomberg/`**. Optional Yahoo fallback is the only **network** data source.

## Goal

Single **paste-at-A1** tab-separated layout that **Bloomberg Terminal Excel** can refresh after **Shift+F9** (calculate sheet), using **native `BDH` spills** only (no `CHOOSECOLS` unless requested).

## Date inputs

- **A1** = start date  
- **A2** = end date (often `=TODAY()`)

All `BDH` formulas reference **`$A$1`** and **`$A$2`**.

## Preferred layout (3-column blocks)

For each series, allocate **three** columns:

1. **Left:** spill column 1 (dates) + **Security** on row 4 + **BDH** on row 5  
2. **Middle:** spill column 2 (values) + **Field** on row 4  
3. **Right:** blank spacer (never put the formula here)

**Row 3:** repeat `Date`, then the Bloomberg **field name** (e.g. `PX_LAST`) for that block, then blank.

**Row 4:** `Security`, `Field`, blank — repeated per block.

**Row 5:** one formula per block in the **first** column of the block:

```text
=BDH(<SecurityCell4>,<FieldCell4>,$A$1,$A$2,"Per","D")
```

Use **`"Per","W"`** for **weekly** COT (`CFFD*`, `GCNCN`, etc.) series.

### On-disk template (full Gold Dashboard set)

| File | Contents |
|------|----------|
| `references/BBG_Gold_Dashboard_3col_BDH_Template.tsv` | **53** BDH blocks (A1/A2 dates; each series = Date + Value columns + spacer): core + **USGG2YR**, optional lease/premia/CB/imports, **COT** + extended (`CFFDUORN`, `GCNCN`), weekly `W` where marked |

### On-disk template (US equities strip)

| File | Contents |
|------|----------|
| `references/BBG_US_Equity_3col_BDH_Template.tsv` | **46** US Equity names; **`PX_LAST`** in the formula (`=BDH(L4,"PX_LAST",$A$1,$A$2,"Per","D")` pattern) |

## Legacy layout (2-column pairs)

Older compact tables: Security **row 5** and Field **row 6** in the **left** column of each pair; **one** `BDH` on **row 7** left; right column of the pair empty for spill. Documented in `~/.cursor/skills/bloomberg-excel-bdh/SKILL.md` as **Layout B**.

## Static vs live

- `references/BBG_BDH_Excel_Paste_Table.tsv` — **historical snapshot** (not a formula template).  
- Use **`*_3col_BDH_Template.tsv`** for **live** `BDH` workflows.

## Saved workbook exports (Excel)

Store Bloomberg-filled workbooks under **`data/raw/Bloomberg/`** with a dated name, e.g. `bbg_bdh_export_YYYYMMDD_vN.xlsx`.

| File | Note |
|------|------|
| `data/raw/Bloomberg/bbg_bdh_export_20260322_v1.xlsx` | **Current** saved pull (2026-03-22). |

An earlier export without the `_v1` suffix may also exist in the same folder; treat **`_v1`** as the user’s labeled revision unless superseded.

## Optional category A blocks (lease + regional + official sector)

Beyond the core template, you can add **3-column** `BDH` blocks for optional physical overlays (see `specs/data-contract.md`):

- `GOLDLNPM Index` → `GOLD_LEASE` (verify ticker; replace if your desk uses another lease/forward series)
- `GOLDIPREM Index` / `GOLDCHPREM Index` → `GOLD_INDIA_PREM` / `GOLD_CHINA_PREM` (**placeholders** — swap for your India/China premium series or a custom index you maintain)
- `GOLDCBH Index` → `GOLD_CB_HOLDINGS`; `CHGLDIMP Index` → `GOLD_CHINA_IMPORT`; `INGLDIMP Index` → `GOLD_INDIA_IMPORT` (**placeholders** — replace with your central-bank total / customs import series or a custom `Index`)

**GC1−GC2** for signals uses **GC1** and **GC2** `PX_LAST` already in the workbook; no extra series.

## Agent skill

Authoritative skill file: **`~/.cursor/skills/bloomberg-excel-bdh/SKILL.md`**.
