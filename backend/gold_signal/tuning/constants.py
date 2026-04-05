"""Tuning defaults."""

# Sub-legs where NaN z means no signal → flat (0) in research deadband path.
ABSTAIN_SUBLEG_IDS: frozenset[str] = frozenset(
    {"F_cot_mm", "F_cot_prod", "F_cot_other", "F_imm_legacy", "G_gpr"}
)
