# ruff: noqa: E501  -- 마크다운 표 한 줄을 코드 한 줄로 두는 편이 결과 표와 대조하기 쉽다
"""metrics.json → reports/model_comparison.md.

리포트를 손으로 쓰지 않고 학습 결과에서 생성하는 이유: 재학습할 때마다 숫자가 자동으로 맞춰져서
'리포트의 수치와 실제 모델이 다르다'는 문제가 생기지 않는다. 해석(서술)은 docs/decisions.md에 둔다.
"""

from __future__ import annotations

import json
from pathlib import Path

LABELS = {
    "constant_0.5": "① 항상 0.5",
    "lookup_buy_matchup": "② 구매유형 룩업표",
    "logistic": "③ 로지스틱 회귀",
    "lightgbm": "④ LightGBM",
    "lightgbm_calibrated": "⑤ LightGBM + isotonic 보정 (서빙)",
}
SPLITS = [("test_2025", "테스트 2025"), ("test_2026", "테스트 2026 (장비가치 전부 결측)")]


def render(m: dict) -> str:
    out = ["# 모델 비교 (자동 생성: `python -m propredict.ml.train`)", ""]
    out += [f"- 학습 시각: {m['trained_at']} · LightGBM best_iteration={m['best_iteration']}",
            f"- 분할: train {m['splits']['train']} / valid {m['splits']['valid']} (조기종료·보정 절반씩) / "
            f"test {m['splits']['test']} — 시즌 단위라 경기가 섞이지 않는다",
            f"- 행 수: {', '.join(f'{k}={v:,}' for k, v in m['rows'].items())}",
            "- 평가 행: 두 팀 구매유형이 모두 있는 라운드. 모든 모델을 같은 행으로 비교한다.", ""]  # fmt: skip
    for key, title in SPLITS:
        out += [f"## {title}", "", "| 모델 | Brier ↓ | LogLoss ↓ | AUC ↑ | ECE ↓ |", "|---|---:|---:|---:|---:|"]
        base = m["models"]["constant_0.5"][key]["brier"]
        for name, label in LABELS.items():
            r = m["models"][name][key]
            gain = (base - r["brier"]) / base * 100
            out.append(
                f"| {label} | {r['brier']:.4f} ({gain:+.1f}%) | {r['log_loss']:.4f} | {r['auc']:.4f} | {r['ece']:.4f} |"
            )
        out += ["", "Brier 괄호 = 항상 0.5 대비 개선율.", "", "**룩업표 대비 Brier 차이 (경기 단위 부트스트랩 95% CI, 음수 = 모델이 우수)**", "",
                "| 모델 | 차이 | 95% CI |", "|---|---:|---|"]  # fmt: skip
        for name, s in m["significance"][key].items():
            verdict = "유의" if s["ci_high"] < 0 else "유의하지 않음"
            out.append(
                f"| {LABELS[name.removesuffix('_vs_lookup')]} | {s['diff']:+.5f} | [{s['ci_low']:+.5f}, {s['ci_high']:+.5f}] {verdict} |"
            )
        out += [
            "",
            "**Calibration (서빙 모델, 10구간)**",
            "",
            "| 예측 구간 | 평균 예측 | 실제 승률 | 표본 |",
            "|---|---:|---:|---:|",
        ]
        for b in m["calibration"][key]["calibrated"]:
            out.append(
                f"| {b['bin_lower']:.1f}–{b['bin_upper']:.1f} | {b['mean_predicted']:.3f} | {b['observed_rate']:.3f} | {b['count']:,} |"
            )
        out.append("")
    out += ["## 피처 중요도 (LightGBM TreeSHAP, 테스트 2025 표본의 평균 |기여도|, 로그오즈)", "",
            "| 순위 | 피처 | 평균 \\|SHAP\\| |", "|---:|---|---:|"]  # fmt: skip
    for i, f in enumerate(m["feature_importance"], 1):
        out.append(f"| {i} | `{f['feature']}` | {f['mean_abs_shap']:.4f} |")
    out += ["", "## 로지스틱 회귀 계수 상위 (표준화 후, 로그오즈)", "", "| 피처 | 계수 |", "|---|---:|"]
    out += [f"| `{c['feature']}` | {c['coef']:+.3f} |" for c in m["logistic_coefficients"]]
    return "\n".join(out) + "\n"


def write_report(metrics_path: Path, out: Path) -> None:
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(render(json.loads(metrics_path.read_text())))
