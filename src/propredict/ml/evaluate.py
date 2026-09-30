"""확률 예측 평가 지표.

정확도(accuracy)를 주 지표로 쓰지 않는 이유: 0.51과 0.99를 똑같이 '맞음'으로 세기 때문에
'70%라고 한 라운드가 실제로 70% 이겼는가'(확률의 신뢰성)를 전혀 측정하지 못한다.
- Brier score: (p - y)^2 평균. 낮을수록 좋고, 항상 0.5를 내면 0.25.
- LogLoss: 확신하고 틀리면 크게 벌한다.
- AUC: 순위(변별력)만 본다. 보정과는 무관하다.
- ECE: 확률 구간별 |평균 예측 - 실제 승률|의 가중 평균. 보정 정도를 한 숫자로 본다.
"""
from __future__ import annotations

import numpy as np
from sklearn.metrics import brier_score_loss, log_loss, roc_auc_score


def calibration_bins(y: np.ndarray, p: np.ndarray, n_bins: int = 10) -> list[dict]:
    edges = np.linspace(0, 1, n_bins + 1)
    idx = np.clip(np.digitize(p, edges[1:-1]), 0, n_bins - 1)
    out = []
    for b in range(n_bins):
        m = idx == b
        if m.any():
            out.append({
                "bin_lower": round(float(edges[b]), 2), "bin_upper": round(float(edges[b + 1]), 2),
                "mean_predicted": round(float(p[m].mean()), 4), "observed_rate": round(float(y[m].mean()), 4),
                "count": int(m.sum()),
            })  # fmt: skip
    return out


def expected_calibration_error(y: np.ndarray, p: np.ndarray, n_bins: int = 10) -> float:
    bins = calibration_bins(y, p, n_bins)
    n = sum(b["count"] for b in bins)
    return float(sum(b["count"] / n * abs(b["mean_predicted"] - b["observed_rate"]) for b in bins))


def evaluate(y: np.ndarray, p: np.ndarray) -> dict:
    y = np.asarray(y, dtype=int)
    p = np.clip(np.asarray(p, dtype=float), 1e-6, 1 - 1e-6)
    return {
        "n": int(len(y)),
        "brier": round(float(brier_score_loss(y, p)), 5),
        "log_loss": round(float(log_loss(y, p, labels=[0, 1])), 5),
        "auc": round(float(roc_auc_score(y, p)), 5) if len(np.unique(y)) == 2 else None,
        "ece": round(expected_calibration_error(y, p), 5),
    }
