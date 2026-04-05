"""Stage-2 combiner: majority vote + agreement-weighted confidence."""

from __future__ import annotations

import numpy as np
import pandas as pd


def majority_combiner(
    directions: list[pd.Series],
    confidences: list[pd.Series],
    labels: list[str],
) -> pd.DataFrame:
    """
    Per row: vote among {-1,0,1} (Stage-1 dirs are ±1; 0 only on long/short tie).
    Confidence = median(conf) * (1 - 0.2 * dispersion), dispersion = fraction of cats not in majority bloc.
    Consensus applies a tie-break on raw z sum when this returns 0.
    """
    _ = labels
    if len(directions) != len(confidences) or not directions:
        raise ValueError("directions and confidences must be same non-empty length")
    idx = directions[0].index
    for d in directions[1:]:
        if not d.index.equals(idx):
            raise ValueError("all series must share index")
    n_c = len(directions)
    votes = np.clip(
        np.rint(np.column_stack([d.to_numpy(dtype=float, copy=False) for d in directions])),
        -1,
        1,
    ).astype(np.int8)
    pos = (votes == 1).sum(axis=1)
    neg = (votes == -1).sum(axis=1)
    neu = (votes == 0).sum(axis=1)
    # Compare long vs short only (neutrals abstain). Requiring pos > neu made
    # 2 long / 1 short / 2 neutral → flat strategy in backtests.
    win = np.where(pos > neg, 1, np.where(neg > pos, -1, 0))
    bloc = np.where(win == 1, pos, np.where(win == -1, neg, np.maximum(np.maximum(pos, neg), neu)))
    dispersion = 1.0 - (bloc / n_c)
    confs = np.column_stack(
        [np.nan_to_num(c.to_numpy(dtype=float, copy=False), nan=0.0, posinf=0.0, neginf=0.0) for c in confidences]
    )
    med = np.median(confs, axis=1)
    out_conf = med * (1.0 - 0.2 * np.clip(dispersion, 0.0, 1.0))
    return pd.DataFrame({"direction": win, "confidence": out_conf}, index=idx)
