import pandas as pd
import numpy as np
from app.services.drift import compute_drift


def test_no_drift_on_stable_data():
    # Slightly noisy but stable series - no regime change
    import numpy as np
    rng = np.random.default_rng(42)
    vol = pd.Series(0.02 + rng.normal(0, 0.001, 250))
    flag, score = compute_drift(vol)
    assert flag == False



def test_drift_detected_on_regime_shift():
    # First 180 days calm, last 30 days very volatile
    calm = pd.Series([0.01] * 200)
    volatile = pd.Series([0.10] * 30)
    vol = pd.concat([calm, volatile], ignore_index=True)
    flag, score = compute_drift(vol)
    assert flag == True


def test_drift_score_is_float():
    vol = pd.Series([0.02] * 250)
    flag, score = compute_drift(vol)
    assert isinstance(score, float)


def test_drift_returns_false_on_short_series():
    # Not enough data to compute drift
    vol = pd.Series([0.02] * 50)
    flag, score = compute_drift(vol)
    assert flag == False
    assert score == 0.0


def test_drift_score_higher_on_volatile_data():
    calm = pd.Series([0.01] * 200)
    volatile = pd.Series([0.10] * 30)
    vol_shifted = pd.concat([calm, volatile], ignore_index=True)
    vol_stable = pd.Series([0.02] * 230)
    _, score_shifted = compute_drift(vol_shifted)
    _, score_stable = compute_drift(vol_stable)
    assert score_shifted > score_stable
