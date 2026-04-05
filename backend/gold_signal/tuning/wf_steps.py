"""Walk-forward step boundaries aligned with ``walk_forward_report`` (iloc ranges)."""

from __future__ import annotations

from dataclasses import dataclass

from gold_signal.config import Settings, settings


@dataclass(frozen=True)
class WfStepBounds:
    """Integer iloc ranges into a Series/DataFrame sharing the walk-forward calendar index."""

    step_idx: int
    is_start: int
    is_end: int  # exclusive; equals oos_start
    oos_start: int
    oos_end: int  # exclusive


def wf_warmup_days(cfg: Settings | None = None) -> int:
    cfg = cfg or settings
    return cfg.wf_is_days + cfg.z_window


def iter_wf_step_bounds(n: int, cfg: Settings | None = None) -> list[WfStepBounds]:
    """
    Same stepping as ``walk_forward_report``: after ``warmup`` bars, each step has
    ``wf_oos_days`` OOS bars and up to ``wf_is_days`` IS bars immediately before OOS.
    """
    cfg = cfg or settings
    is_d, oos_d, step_d = cfg.wf_is_days, cfg.wf_oos_days, cfg.wf_step_days
    warm = wf_warmup_days(cfg)
    if n < warm + oos_d + 5:
        return []
    out: list[WfStepBounds] = []
    start_pos = warm
    step_idx = 0
    while start_pos + oos_d <= n:
        is_start = max(0, start_pos - is_d)
        out.append(
            WfStepBounds(
                step_idx=step_idx,
                is_start=is_start,
                is_end=start_pos,
                oos_start=start_pos,
                oos_end=start_pos + oos_d,
            )
        )
        start_pos += step_d
        step_idx += 1
    return out
