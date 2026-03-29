import numpy as np
import pandas as pd
from scipy.stats import ks_2samp


def compute_drift(
    vol_series: pd.Series,
    reference_days: int = 180,
    recent_days: int = 30,
    ks_threshold: float = 0.05,
    mean_shift_threshold: float = 1.5,
) -> tuple[bool, float]:
    if len(vol_series) < reference_days + recent_days:
        return False, 0.0

    reference = vol_series.iloc[-(reference_days + recent_days):-recent_days]
    recent = vol_series.iloc[-recent_days:]

    ref_std = reference.std()
    mean_diff = abs(recent.mean() - reference.mean())
    mean_shift = mean_diff / ref_std if ref_std > 1e-10 else 0.0

    # Only run KS test if reference has enough variance to be meaningful
    if ref_std > 1e-10:
        ks_stat, p_value = ks_2samp(reference.values, recent.values)
        ks_triggered = p_value < ks_threshold
    else:
        ks_triggered = False

    drift_flag = ks_triggered or (mean_shift > mean_shift_threshold)
    drift_score = round(float(mean_shift), 4)

    return drift_flag, drift_score