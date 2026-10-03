"""예측·모델 지표 엔드포인트 (DB 불필요: 저장소의 artifacts/model.joblib 사용)."""

import time

import pytest

from propredict.api.service import NEUTRAL_FILLED

SPEC_EXAMPLE = {  # 명세 §6 요청 예시
    "map_name": "Ascent", "round_number": 14, "score_a": 7, "score_b": 6,
    "team_a_buy_type": "Full buy: 20k+", "team_b_buy_type": "Eco: 0-5k",
    "team_a_loadout": 24500, "team_b_loadout": 3900, "team_a_credits": 2100, "team_b_credits": 400,
}  # fmt: skip


def swapped(req: dict) -> dict:
    out = dict(req)
    for a, b in [("score_a", "score_b"), ("team_a_buy_type", "team_b_buy_type"),
                 ("team_a_loadout", "team_b_loadout"), ("team_a_credits", "team_b_credits")]:  # fmt: skip
        out[a], out[b] = req.get(b), req.get(a)
    return out


def test_spec_example_returns_calibrated_probability(client):
    res = client.post("/api/predict", json=SPEC_EXAMPLE)
    assert res.status_code == 200, res.text
    body = res.json()
    assert body["win_probability_a"] + body["win_probability_b"] == pytest.approx(1.0)
    assert 0.8 < body["win_probability_a"] < 0.97  # 풀바이 vs 에코
    assert body["baseline_probability_a"] == pytest.approx(0.9, abs=0.02)  # 명세 룩업표 90.6%


def test_top_factors_are_explained_and_exclude_unprovided_inputs(client):
    factors = client.post("/api/predict", json=SPEC_EXAMPLE).json()["top_factors"]
    assert 1 <= len(factors) <= 5
    assert all(f["label"] for f in factors)
    # 요청에 없는(중립값으로 채운) 모멘텀·팀 강도는 '요인'으로 보이면 안 된다
    assert not {f["feature"] for f in factors} & NEUTRAL_FILLED
    # 풀바이 vs 에코면 구매 관련 요인이 A에게 유리한 방향(+)으로 가장 커야 한다
    assert factors[0]["feature"] in {"buy_diff", "buy_matchup", "loadout_share", "loadout_diff"}
    assert factors[0]["contribution"] > 0


def test_swapping_teams_roughly_mirrors_probability(client):
    p = client.post("/api/predict", json=SPEC_EXAMPLE).json()["win_probability_a"]
    q = client.post("/api/predict", json=swapped(SPEC_EXAMPLE)).json()["win_probability_a"]
    # 학습 시 A/B 반전 증강으로 근사적 대칭 (정확한 대칭화는 이득이 없어 하지 않음, decisions D15)
    assert p + q == pytest.approx(1.0, abs=0.1)


def test_loadout_is_optional_like_2026_data(client):
    req = {k: v for k, v in SPEC_EXAMPLE.items() if "loadout" not in k}
    assert client.post("/api/predict", json=req).status_code == 200


@pytest.mark.parametrize(
    "patch",
    [
        {"score_a": 9},  # 9 + 6 != 14 - 1 : 불가능한 상태
        {"team_a_buy_type": "Pistol"},
        {"round_number": 0, "score_a": 0, "score_b": 0},
        {"team_a_loadout": -1},
        {"team_a_side": "attack"},
    ],
)
def test_invalid_requests_are_rejected(client, patch):
    assert client.post("/api/predict", json={**SPEC_EXAMPLE, **patch}).status_code == 422


def test_unknown_map_is_rejected_with_known_list(client):
    res = client.post("/api/predict", json={**SPEC_EXAMPLE, "map_name": "Ascnet"})
    assert res.status_code == 422 and "Ascent" in res.json()["detail"]


def test_prediction_latency_is_well_under_budget(client):
    # 완료 기준: 입력 변경 → 500ms 안에 화면 갱신 (프론트 디바운스 300ms 포함). API는 그보다 훨씬 빨라야 한다.
    client.post("/api/predict", json=SPEC_EXAMPLE)  # 워밍업
    t = time.perf_counter()
    for _ in range(30):
        client.post("/api/predict", json=SPEC_EXAMPLE)
    assert (time.perf_counter() - t) / 30 < 0.1


def test_model_metrics_match_artifact(client):
    body = client.get("/api/model/metrics").json()
    assert body["serving_model"] == "lightgbm_calibrated"
    serving = body["models"]["lightgbm_calibrated"]["test_2025"]["brier"]
    lookup = body["models"]["lookup_buy_matchup"]["test_2025"]["brier"]
    assert serving < lookup < 0.25  # 완료 기준: 룩업표보다 Brier가 낮다
    assert len(body["calibration"]["test_2025"]["calibrated"]) >= 8
    assert body["feature_importance"][0]["label"]


def test_predict_returns_503_without_model(client):
    model, client.app.state.model = client.app.state.model, None
    try:
        assert client.post("/api/predict", json=SPEC_EXAMPLE).status_code == 503
    finally:
        client.app.state.model = model
