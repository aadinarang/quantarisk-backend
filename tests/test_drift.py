import pandas as pd
import numpy as np
from app.services.drift import compute_drift


def test_no_drift_on_stable_data():
    # Perfectly flat series — statistically guaranteed no drift
    vol = pd.Series([0.02] * 250)
    flag, score = compute_drift(vol)
    assert flag == False



def test_drift_detected_on_regime_shift():
    rng = np.random.default_rng(42)
    # Reference: calm with small noise
    calm = pd.Series(0.01 + rng.normal(0, 0.001, 200))
    # Recent: much higher volatility regime
    volatile = pd.Series(0.10 + rng.normal(0, 0.001, 30))
    vol = pd.concat([calm, volatile], ignore_index=True)
    flag, score = compute_drift(vol)
    assert flag == True


def test_drift_score_higher_on_volatile_data():
    rng = np.random.default_rng(42)
    calm = pd.Series(0.01 + rng.normal(0, 0.001, 200))
    volatile = pd.Series(0.10 + rng.normal(0, 0.001, 30))
    vol_shifted = pd.concat([calm, volatile], ignore_index=True)
    vol_stable = pd.Series(0.02 + rng.normal(0, 0.001, 230))
    _, score_shifted = compute_drift(vol_shifted)
    _, score_stable = compute_drift(vol_stable)
    assert score_shifted > score_stable


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

