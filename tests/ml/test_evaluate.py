import numpy as np
import pytest

from propredict.ml.baselines import LookupTableBaseline
from propredict.ml.evaluate import calibration_bins, evaluate, paired_bootstrap_brier_diff


def test_constant_half_has_brier_quarter():
    y = np.array([0, 1, 1, 0])
    assert evaluate(y, np.full(4, 0.5))["brier"] == pytest.approx(0.25)


def test_perfectly_calibrated_bins_have_zero_ece():
    y = np.array([0, 0, 0, 1] * 25 + [1, 1, 1, 0] * 25)
    p = np.array([0.25] * 100 + [0.75] * 100)
    assert evaluate(y, p)["ece"] == pytest.approx(0.0)
    bins = calibration_bins(y, p)
    assert [b["count"] for b in bins] == [100, 100]


def test_bootstrap_detects_clear_improvement_and_no_difference():
    rng = np.random.default_rng(0)
    groups = np.repeat(np.arange(200), 20)
    y = rng.integers(0, 2, len(groups))
    good = np.where(y == 1, 0.7, 0.3)
    better = paired_bootstrap_brier_diff(y, good, np.full(len(y), 0.5), groups)
    assert better["ci_high"] < 0  # 확실히 나으면 구간 전체가 음수
    same = paired_bootstrap_brier_diff(y, np.full(len(y), 0.5), np.full(len(y), 0.5), groups)
    assert same["ci_low"] == same["ci_high"] == 0


def test_lookup_table_uses_prior_for_rare_cells():
    import pandas as pd

    X = pd.DataFrame({"buy_a": [3.0] * 40 + [0.0] * 5, "buy_b": [0.0] * 40 + [3.0] * 5})
    y = pd.Series([1] * 36 + [0] * 4 + [1] * 5)
    lt = LookupTableBaseline(min_count=30).fit(X, y)
    p = lt.predict_proba(pd.DataFrame({"buy_a": [3.0, 0.0, 1.0], "buy_b": [0.0, 3.0, 1.0]}))
    assert p.tolist() == pytest.approx([0.9, 0.5, 0.5])  # 표본 5개 칸과 처음 보는 조합은 0.5
