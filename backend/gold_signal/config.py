"""Paths and walk-forward defaults (aligned with project plan)."""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path

try:
    from dotenv import load_dotenv

    # Load <repo_root>/.env if present so SUPABASE_* vars are available without
    # needing the user to export them in every shell.
    _repo_root = Path(__file__).resolve().parents[2]
    load_dotenv(_repo_root / ".env")
except Exception:
    pass


def default_project_root() -> Path:
    # backend/gold_signal/config.py -> parents[2] = repo root
    return Path(__file__).resolve().parents[2]


@dataclass
class Settings:
    project_root: Path = field(default_factory=default_project_root)
    fred_api_key: str = field(default_factory=lambda: os.environ.get("FRED_API_KEY", ""))
    cot_release_lag_bdays: int = field(
        default_factory=lambda: int(os.environ.get("GOLD_COT_LAG_BDAYS", "3"))
    )
    gld_flow_lag_bdays: int = field(
        default_factory=lambda: int(os.environ.get("GOLD_GLD_LAG_BDAYS", "1"))
    )
    wf_is_days: int = field(default_factory=lambda: int(os.environ.get("GOLD_WF_IS", "378")))
    wf_oos_days: int = field(default_factory=lambda: int(os.environ.get("GOLD_WF_OOS", "42")))
    wf_step_days: int = field(default_factory=lambda: int(os.environ.get("GOLD_WF_STEP", "42")))
    z_window: int = 252
    z_clip: float = 4.0
    threshold: float = field(
        default_factory=lambda: float(os.environ.get("GOLD_Z_THRESHOLD", "0.1"))
    )
    include_gpr: bool = field(
        default_factory=lambda: os.environ.get("GOLD_INCLUDE_GPR", "").lower() in ("1", "true", "yes")
    )
    # When true (default), use latest ``data/tuning_runs/<run>/`` (or ``tuning_run_dir``) for WF τ / weights.
    # Set ``GOLD_USE_LATEST_TUNING=0`` to force production ``discrete_from_z`` only.
    use_latest_tuning: bool = field(
        default_factory=lambda: os.environ.get("GOLD_USE_LATEST_TUNING", "1").strip().lower()
        not in ("0", "false", "no", "off")
    )
    tuning_run_dir: str = field(
        default_factory=lambda: (os.environ.get("GOLD_TUNING_RUN_DIR") or "").strip()
    )
    supabase_url: str = field(default_factory=lambda: os.environ.get("SUPABASE_URL", ""))
    supabase_service_key: str = field(
        default_factory=lambda: os.environ.get("SUPABASE_SERVICE_KEY", "")
    )
    supabase_table: str = field(
        default_factory=lambda: os.environ.get("GOLD_SUPABASE_TABLE", "daily_prices")
    )
    supabase_observation_start: str = field(
        default_factory=lambda: os.environ.get("GOLD_SUPABASE_START", "1990-01-01")
    )

    def resolved_data_dir(self) -> Path:
        env = os.environ.get("GOLD_DATA_DIR")
        if env:
            p = Path(env)
            return p if p.is_absolute() else self.project_root / p
        return self.project_root / "data"


settings = Settings()
