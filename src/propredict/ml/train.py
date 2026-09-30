"""학습 파이프라인: 분할 → (train만) 증강 → 베이스라인·로지스틱·LightGBM → 보정 → 평가 → 저장.

    uv run python -m propredict.ml.train

평가 대상 행: 두 팀의 구매유형이 모두 있는 라운드. 모든 모델(베이스라인 포함)을 '같은 행'으로 비교한다.
"""

from __future__ import annotations

import argparse
import json
import time
from datetime import UTC, datetime
from pathlib import Path

import joblib
import lightgbm as lgb
import numpy as np
import pandas as pd
from sklearn.compose import ColumnTransformer
from sklearn.impute import SimpleImputer
from sklearn.isotonic import IsotonicRegression
from sklearn.linear_model import LogisticRegression
from sklearn.pipeline import Pipeline, make_pipeline
from sklearn.preprocessing import OneHotEncoder, StandardScaler

from propredict.config import get_settings
from propredict.db import get_engine
from propredict.ml.baselines import ConstantBaseline, LookupTableBaseline
from propredict.ml.dataset import load_rounds
from propredict.ml.evaluate import calibration_bins, evaluate, paired_bootstrap_brier_diff
from propredict.ml.features import (
    CATEGORICAL_FEATURES,
    FEATURES,
    LOADOUT_FEATURES,
    NUMERIC_FEATURES,
    build_features,
    flip_ab,
    latest_team_strength,
)
from propredict.ml.model import RoundWinModel, fit_categories, to_model_frame
from propredict.ml.report import write_report
from propredict.ml.split import split_by_season, split_matches

SEED = 42
# 2026년은 장비가치(loadout)가 전부 결측이다. 학습 데이터(2021–23)에는 결측이 거의 없어서, 그대로 학습하면
# 모델이 '장비가치 없는 라운드'를 한 번도 보지 못한다. 학습 행의 일부에서 장비가치를 일부러 지워
# 구매유형·크레딧만으로도 예측하는 경로를 배우게 한다 (docs/decisions.md D14).
LOADOUT_MASK_FRAC = 0.25

LGBM_PARAMS = dict(
    objective="binary", learning_rate=0.03, n_estimators=3000, num_leaves=31, min_child_samples=500,
    subsample=0.8, subsample_freq=1, colsample_bytree=0.8, reg_lambda=1.0, random_state=SEED, verbose=-1,
)  # fmt: skip


def augment_train(train: pd.DataFrame, seed: int = SEED) -> tuple[pd.DataFrame, pd.Series]:
    """train 전용 증강: A/B 반전본 추가 + 장비가치 무작위 마스킹. valid/test에는 절대 적용하지 않는다."""
    X, y = train[FEATURES], train["y"]
    Xf, yf = flip_ab(X, y)
    Xa = pd.concat([X, Xf], ignore_index=True)
    ya = pd.concat([y, yf], ignore_index=True)
    rng = np.random.default_rng(seed)
    mask = rng.random(len(Xa)) < LOADOUT_MASK_FRAC
    Xa.loc[mask, LOADOUT_FEATURES] = np.nan
    return Xa, ya


def logistic_pipeline() -> Pipeline:
    pre = ColumnTransformer([
        # 결측은 중앙값으로 채우되 '결측이었다'는 지시자 컬럼을 함께 넣어 정보 손실을 막는다
        ("num", make_pipeline(SimpleImputer(strategy="median", add_indicator=True), StandardScaler()),
         NUMERIC_FEATURES),
        ("cat", OneHotEncoder(handle_unknown="ignore", min_frequency=50), CATEGORICAL_FEATURES),
    ])  # fmt: skip
    return make_pipeline(pre, LogisticRegression(C=1.0, max_iter=2000))


def logistic_coefficients(pipe: Pipeline, top: int = 15) -> list[dict]:
    names = pipe[0].get_feature_names_out()
    coef = pipe[-1].coef_[0]
    order = np.argsort(-np.abs(coef))[:top]
    return [{"feature": str(names[i]), "coef": round(float(coef[i]), 4)} for i in order]


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="라운드 승률 모델 학습")
    ap.add_argument("--out", type=Path, default=get_settings().artifacts_dir)
    ap.add_argument("--report", type=Path, default=Path("reports/model_comparison.md"))
    args = ap.parse_args(argv)
    t0 = time.perf_counter()

    rounds = load_rounds(get_engine())
    F = build_features(rounds)
    print(f"rounds={len(F):,} with_economy={int(F['has_economy'].sum()):,}")
    parts = split_by_season(F[F["has_economy"]])
    valid_es, valid_cal = split_matches(parts["valid"], seed=SEED)
    evals = {"valid_cal": valid_cal, "test_2025": parts["test_2025"], "test_2026": parts["test_2026"]}
    Xtr, ytr = augment_train(parts["train"])
    print("rows:", {"train_aug": len(Xtr), "valid_es": len(valid_es), **{k: len(v) for k, v in evals.items()}})

    preds: dict[str, dict[str, np.ndarray]] = {}

    # 1) 베이스라인
    lookup = LookupTableBaseline()
    for base in (ConstantBaseline(), lookup):
        base.fit(Xtr, ytr)
        preds[base.name] = {k: base.predict_proba(v[FEATURES]) for k, v in evals.items()}

    # 2) 로지스틱 회귀 (해석용)
    logit = logistic_pipeline().fit(Xtr, ytr)
    preds["logistic"] = {k: logit.predict_proba(v[FEATURES])[:, 1] for k, v in evals.items()}

    # 3) LightGBM (valid 절반으로 조기 종료)
    cats = fit_categories(pd.concat([Xtr, valid_es[FEATURES]]))
    clf = lgb.LGBMClassifier(**LGBM_PARAMS)
    clf.fit(
        to_model_frame(Xtr, cats), ytr,
        eval_X=(to_model_frame(valid_es[FEATURES], cats),), eval_y=(valid_es["y"],), eval_metric="binary_logloss",
        callbacks=[lgb.early_stopping(100, verbose=False)],
    )  # fmt: skip
    model = RoundWinModel(classifier=clf, categories=cats)
    preds["lightgbm"] = {k: model.predict_raw(v[FEATURES]) for k, v in evals.items()}

    # 4) 보정: 조기 종료에 쓰지 않은 나머지 valid 절반으로 isotonic 회귀
    iso = IsotonicRegression(out_of_bounds="clip", y_min=0.0, y_max=1.0)
    iso.fit(preds["lightgbm"]["valid_cal"], valid_cal["y"])
    model.calibrator = iso
    preds["lightgbm_calibrated"] = {k: iso.predict(p) for k, p in preds["lightgbm"].items()}

    # ---- 평가
    metrics = {name: {k: evaluate(evals[k]["y"].to_numpy(), p) for k, p in by_split.items()}
               for name, by_split in preds.items()}  # fmt: skip
    calib = {k: {"raw": calibration_bins(evals[k]["y"].to_numpy(), preds["lightgbm"][k]),
                 "calibrated": calibration_bins(evals[k]["y"].to_numpy(), preds["lightgbm_calibrated"][k])}
             for k in evals}  # fmt: skip
    # 개선폭이 우연인지: 경기 단위 부트스트랩으로 Brier 차이의 95% 신뢰구간
    significance = {
        k: {
            f"{m}_vs_lookup": paired_bootstrap_brier_diff(
                evals[k]["y"].to_numpy(), preds[m][k], preds["lookup_buy_matchup"][k], evals[k]["match_id"].to_numpy()
            )
            for m in ("logistic", "lightgbm", "lightgbm_calibrated")
        }
        for k in ("test_2025", "test_2026")
    }
    sample = parts["test_2025"].sample(min(20000, len(parts["test_2025"])), random_state=SEED)
    contrib = model.contributions(sample[FEATURES]).drop(columns="bias")
    importance = contrib.abs().mean().sort_values(ascending=False)

    meta = {
        "trained_at": datetime.now(UTC).isoformat(timespec="seconds"),
        "best_iteration": int(clf.best_iteration_),
        "rows": {"train_augmented": len(Xtr), "valid_es": len(valid_es), **{k: len(v) for k, v in evals.items()}},
        "splits": {"train": [2021, 2022, 2023], "valid": [2024], "test": [2025, 2026]},
        "loadout_mask_frac": LOADOUT_MASK_FRAC,
    }
    model.meta = meta
    out = {
        **meta,
        "models": metrics,
        "calibration": calib,
        "significance": significance,
        "feature_importance": [{"feature": f, "mean_abs_shap": round(float(v), 5)} for f, v in importance.items()],
        "logistic_coefficients": logistic_coefficients(logit),
        "lookup_table": [
            {"buy_a": int(a), "buy_b": int(b), "win_rate": round(float(r["win_rate"]), 4), "count": int(r["count"])}
            for (a, b), r in lookup.table.iterrows()
        ],  # fmt: skip
    }

    args.out.mkdir(parents=True, exist_ok=True)
    joblib.dump(
        {"model": model, "lookup_table": lookup.table, "team_strength": latest_team_strength(rounds),
         "features": FEATURES, "meta": meta},
        args.out / "model.joblib", compress=3,
    )  # fmt: skip
    (args.out / "metrics.json").write_text(json.dumps(out, ensure_ascii=False, indent=2))
    write_report(args.out / "metrics.json", args.report)
    print(json.dumps({m: {k: v["brier"] for k, v in s.items()} for m, s in metrics.items()}, indent=1))
    print(f"done in {time.perf_counter() - t0:.0f}s → {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
