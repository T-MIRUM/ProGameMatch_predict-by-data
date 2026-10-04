"""보정기 테스트: 서빙 출력이 지켜야 할 성질(단조·0/1 미도달·연속)과 선택 로직."""

import numpy as np
import pytest

from propredict.ml.calibration import (
    BetaCalibrator,
    IdentityCalibrator,
    IsotonicCalibrator,
    PlattCalibrator,
    select_calibrator,
)


def _sample(n: int = 4000, seed: int = 0, bias: float = 0.0):
    """원출력 p와 실제 결과 y. bias > 0이면 원출력이 과신(실제보다 극단적)하도록 만든다."""
    rng = np.random.default_rng(seed)
    true_p = rng.uniform(0.05, 0.95, n)
    logit = np.log(true_p / (1 - true_p)) * (1 + bias)
    p = 1 / (1 + np.exp(-logit))
    y = (rng.random(n) < true_p).astype(int)
    groups = np.repeat(np.arange(n // 20), 20)  # 경기 하나 = 라운드 20개
    return p, y, groups


@pytest.mark.parametrize("cls", [PlattCalibrator, BetaCalibrator])
def test_parametric_output_is_monotone_and_never_certain(cls):
    p, y, _ = _sample()
    cal = cls().fit(p, y)
    grid = np.linspace(0.001, 0.999, 999)
    out = cal.predict(grid)
    assert np.all(np.diff(out) >= -1e-12), "보정 후에도 원출력 순서가 유지돼야 한다"
    assert out.min() > 0 and out.max() < 1, "라운드 승패에 0%·100%는 없다"
    # 계단이 아니라 연속: 입력이 다르면 출력도 (거의 모두) 다르다
    assert len(np.unique(np.round(out, 6))) > 900


def test_isotonic_is_a_step_function():
    """isotonic을 기각한 이유를 테스트로 고정: 출력값 종류가 입력보다 훨씬 적다."""
    p, y, _ = _sample()
    out = IsotonicCalibrator().fit(p, y).predict(np.linspace(0.001, 0.999, 999))
    assert len(np.unique(np.round(out, 6))) < 200


def test_platt_fixes_overconfidence():
    """과신한 원출력(bias=0.5)을 Platt가 바로잡으면 Brier가 내려가고 기울기가 1보다 작다."""
    p, y, _ = _sample(bias=0.5, n=20000)
    cal = PlattCalibrator().fit(p, y)
    slope, _ = cal.slope_intercept
    assert 0.5 < slope < 0.8
    brier = lambda q: float(np.mean((q - y) ** 2))  # noqa: E731
    assert brier(cal.predict(p)) < brier(p)


def test_select_prefers_simplest_when_already_calibrated():
    """원출력이 이미 보정돼 있으면 none 또는 2-파라미터 Platt가 뽑혀야 한다(유연한 isotonic이 아니라)."""
    p, y, g = _sample(n=6000)
    cal, table = select_calibrator(p, y, g)
    assert cal.name in {"none", "platt"}
    assert sum(r["selected"] for r in table) == 1
    assert {r["method"] for r in table} == {"none", "platt", "beta", "isotonic"}


def test_select_picks_a_real_calibrator_when_overconfident():
    p, y, g = _sample(n=20000, bias=0.6)
    cal, table = select_calibrator(p, y, g)
    assert not isinstance(cal, IdentityCalibrator)
    chosen = next(r for r in table if r["selected"])
    none = next(r for r in table if r["method"] == "none")
    assert chosen["cv_brier"] < none["cv_brier"]
