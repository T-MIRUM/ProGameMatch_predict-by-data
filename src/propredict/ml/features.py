"""피처 생성 — 라운드가 '시작되는 시점'에 알 수 있는 정보만 쓴다.

세 층으로 나눈 이유:
1) sequence_features: 같은 맵의 '이전' 라운드들로 계산 (스코어, 직전 승패, 연승, 최근 3R 승률)
2) team_strength:     해당 경기 '이전' 경기들로만 계산 (expanding window)
3) state_features:    한 라운드의 상태만으로 계산 (이코노미, 맵, 진영, 파생값)
   → API는 요청 한 건으로 3)만 다시 계산하면 되므로, 학습과 서빙이 같은 함수를 쓴다(training-serving skew 방지).

누수 방지 규칙 (tests/ml/test_leakage.py가 검증):
- 1)은 현재 라운드의 승패를 절대 보지 않는다(모두 shift(1)).
- 2)는 현재 경기 결과를 포함하지 않는다(누적합에서 자기 자신을 뺀다).
- win_method와 '진영을 알아냈는지 여부'는 결과 정보라 피처로 쓰지 않는다.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from propredict.etl.normalize import BUY_TYPES

BUY_ORDER = {bt: i for i, bt in enumerate(BUY_TYPES)}  # Eco=0 … Full buy=3 (서열이 있는 범주)
HALF_LENGTH = 12
# 팀 강도 사전분포 강도: 약 2맵(48라운드)만큼의 50% 승률을 미리 더한다.
# 경기 수가 적은 신생팀이 1~2경기 결과로 극단값(0% / 100%)을 갖는 것을 막는 베이지안 수축이다.
STRENGTH_PRIOR_ROUNDS = 48.0

NUMERIC_FEATURES = [
    # 이코노미
    "team_a_loadout", "team_b_loadout", "loadout_diff", "loadout_share",
    "team_a_credits", "team_b_credits", "buy_a", "buy_b", "buy_diff",
    # 경기 맥락
    "round_number", "half", "is_pistol", "score_a", "score_b", "score_diff", "side_a_atk",
    # 모멘텀
    "prev_a_won", "streak", "last3_a_winrate",
    # 팀 강도
    "team_a_strength", "team_b_strength", "strength_diff",
]  # fmt: skip
CATEGORICAL_FEATURES = ["map_name", "buy_matchup", "map_side"]
FEATURES = NUMERIC_FEATURES + CATEGORICAL_FEATURES
LOADOUT_FEATURES = ["team_a_loadout", "team_b_loadout", "loadout_diff", "loadout_share"]


# ---------------------------------------------------------------- 1) 시퀀스
def sequence_features(df: pd.DataFrame) -> pd.DataFrame:
    """df는 map_game_id 안에서 round_number 순으로 정렬돼 있어야 한다."""
    mg = df["map_game_id"]
    a_won = (df["winner"] == "A").astype(float)
    g = a_won.groupby(mg)

    out = pd.DataFrame(index=df.index)
    out["score_a"] = g.cumsum() - a_won  # 현재 라운드 제외: '이전까지' 딴 라운드 수
    out["score_b"] = df.groupby(mg).cumcount() - out["score_a"]
    out["prev_a_won"] = g.shift(1)  # 1라운드는 NaN (정보 없음)
    prev = out["prev_a_won"]
    out["last3_a_winrate"] = prev.groupby(mg).rolling(3, min_periods=1).mean().reset_index(level=0, drop=True)

    # 연승: +n = A가 직전까지 n연승, -n = B가 n연승. 현재 라운드 결과는 쓰지 않도록 한 칸 민다.
    w = df["winner"]
    new_run = w.ne(w.groupby(mg).shift())
    run_len = df.groupby(new_run.cumsum()).cumcount() + 1
    signed = pd.Series(np.where(w == "A", run_len, -run_len), index=df.index, dtype=float)
    out["streak"] = signed.groupby(mg).shift(1).fillna(0.0)
    return out


# ---------------------------------------------------------------- 2) 팀 강도
def _match_results(df: pd.DataFrame) -> pd.DataFrame:
    a_won = (df["winner"] == "A").astype(int)
    m = df.assign(a_won=a_won).groupby("match_id", sort=False).agg(
        season=("season", "first"), source_match_id=("source_match_id", "first"),
        team_a=("team_a", "first"), team_b=("team_b", "first"),
        a_rounds=("a_won", "sum"), n_rounds=("a_won", "size"),
    )  # fmt: skip
    long = pd.concat([
        m.assign(team=m["team_a"], won=m["a_rounds"])[["season", "source_match_id", "team", "won", "n_rounds"]],
        m.assign(team=m["team_b"], won=m["n_rounds"] - m["a_rounds"])[
            ["season", "source_match_id", "team", "won", "n_rounds"]],
    ]).reset_index()  # fmt: skip
    return long.sort_values(["season", "source_match_id", "match_id"], kind="stable", na_position="last")


def _shrunk(won: pd.Series, played: pd.Series) -> pd.Series:
    return (won + STRENGTH_PRIOR_ROUNDS * 0.5) / (played + STRENGTH_PRIOR_ROUNDS)


def team_strength(df: pd.DataFrame) -> pd.DataFrame:
    """경기별 A/B 팀의 '그 경기 이전까지' 라운드 승률 (expanding window + 베이지안 수축)."""
    long = _match_results(df)
    g = long.groupby("team", sort=False)
    prior_won = g["won"].cumsum() - long["won"]  # 자기 경기 제외 = 과거만
    prior_played = g["n_rounds"].cumsum() - long["n_rounds"]
    long["strength"] = _shrunk(prior_won, prior_played)
    s = long.set_index(["match_id", "team"])["strength"]
    keys = df[["match_id", "team_a", "team_b"]].drop_duplicates("match_id")
    out = pd.DataFrame({
        "match_id": keys["match_id"].to_numpy(),
        "team_a_strength": s.reindex(list(zip(keys["match_id"], keys["team_a"], strict=True))).to_numpy(),
        "team_b_strength": s.reindex(list(zip(keys["match_id"], keys["team_b"], strict=True))).to_numpy(),
    })  # fmt: skip
    return out


def latest_team_strength(df: pd.DataFrame) -> dict[str, float]:
    """모든 경기를 반영한 현재 팀 강도 (API가 팀 이름으로 조회할 때 사용)."""
    long = _match_results(df)
    agg = long.groupby("team")[["won", "n_rounds"]].sum()
    return _shrunk(agg["won"], agg["n_rounds"]).round(4).to_dict()


# ---------------------------------------------------------------- 3) 상태
def state_features(s: pd.DataFrame) -> pd.DataFrame:
    """한 라운드 상태 → 파생 피처. API 요청 한 건에도 그대로 쓴다.

    필요한 입력 컬럼: map_name, round_number, score_a, score_b, team_a_side,
    team_a/b_loadout, team_a/b_credits, team_a/b_buy_type,
    prev_a_won, streak, last3_a_winrate, team_a/b_strength
    """
    out = pd.DataFrame(index=s.index)
    for c in ["team_a_loadout", "team_b_loadout", "team_a_credits", "team_b_credits"]:
        out[c] = pd.to_numeric(s[c], errors="coerce").astype(float)
    out["loadout_diff"] = out["team_a_loadout"] - out["team_b_loadout"]
    total = out["team_a_loadout"] + out["team_b_loadout"]
    out["loadout_share"] = (out["team_a_loadout"] / total).where(total > 0)
    out["buy_a"] = s["team_a_buy_type"].map(BUY_ORDER).astype(float)
    out["buy_b"] = s["team_b_buy_type"].map(BUY_ORDER).astype(float)
    out["buy_diff"] = out["buy_a"] - out["buy_b"]

    r = s["round_number"].astype(float)
    out["round_number"] = r
    out["half"] = np.select([r <= HALF_LENGTH, r <= 2 * HALF_LENGTH], [1.0, 2.0], 3.0)  # 3 = 연장
    out["is_pistol"] = r.isin([1, HALF_LENGTH + 1]).astype(float)
    out["score_a"] = s["score_a"].astype(float)
    out["score_b"] = s["score_b"].astype(float)
    out["score_diff"] = out["score_a"] - out["score_b"]
    out["side_a_atk"] = s["team_a_side"].map({"atk": 1.0, "def": 0.0}).astype(float)

    for c in ["prev_a_won", "streak", "last3_a_winrate", "team_a_strength", "team_b_strength"]:
        out[c] = s[c].astype(float)
    out["strength_diff"] = out["team_a_strength"] - out["team_b_strength"]

    out["map_name"] = s["map_name"].astype(str)
    out["buy_matchup"] = _matchup(out["buy_a"], out["buy_b"])
    out["map_side"] = _map_side(out["map_name"], out["side_a_atk"])
    return out[FEATURES]


def _matchup(buy_a: pd.Series, buy_b: pd.Series) -> pd.Series:
    ok = buy_a.notna() & buy_b.notna()
    lab = buy_a.fillna(-1).astype(int).astype(str) + "v" + buy_b.fillna(-1).astype(int).astype(str)
    return lab.where(ok, "unknown")


def _map_side(map_name: pd.Series, side_a_atk: pd.Series) -> pd.Series:
    # 맵별 공수 편차(Ascent 수비 유리, Lotus 공격 유리 등)를 선형 모델도 표현할 수 있게 한 교차 범주
    side = side_a_atk.map({1.0: "atk", 0.0: "def"}).fillna("unk")
    return map_name + "|" + side


# ---------------------------------------------------------------- 조립
def build_features(rounds: pd.DataFrame) -> pd.DataFrame:
    """dataset.load_rounds() 결과 → 키 + 피처 + 라벨(y: Team A 승리)."""
    seq = sequence_features(rounds)
    strength = team_strength(rounds)
    # 입력에 같은 이름(예: 경기 스코어 score_a)이 있어도 '라운드 시점 스코어'가 이기도록 먼저 뺀다
    base = rounds.drop(columns=[c for c in [*seq.columns, *strength.columns[1:]] if c in rounds.columns])
    state_in = pd.concat([base, seq], axis=1).merge(strength, on="match_id", how="left")
    state_in.index = rounds.index
    X = state_features(state_in)
    keys = rounds[["match_id", "season", "map_game_id", "round_number"]].rename(
        columns={"round_number": "round_number_key"}
    )
    has_economy = rounds["team_a_buy_type"].notna() & rounds["team_b_buy_type"].notna()
    return pd.concat([keys, X], axis=1).assign(
        has_economy=has_economy.to_numpy(), y=(rounds["winner"] == "A").astype(int).to_numpy()
    )


# ---------------------------------------------------------------- A/B 반전
_SWAP = [
    ("team_a_loadout", "team_b_loadout"),
    ("team_a_credits", "team_b_credits"),
    ("buy_a", "buy_b"),
    ("score_a", "score_b"),
    ("team_a_strength", "team_b_strength"),
]
_NEGATE = ["loadout_diff", "buy_diff", "score_diff", "strength_diff", "streak"]
_ONE_MINUS = ["loadout_share", "prev_a_won", "last3_a_winrate", "side_a_atk"]


def flip_ab(X: pd.DataFrame, y: pd.Series | None = None):
    """Team A와 B를 바꾼 동일한 라운드를 만든다 (docs/decisions.md D2).

    A/B 배정은 scores.csv 순서라 무작위가 아닐 수 있다. 반전본을 학습에 섞으면 모델이 'A라서 이긴다'를
    배울 수 없고, P(A 승) + P(B 승) = 1 대칭이 데이터 수준에서 보장된다. 분할 '이후' train에만 적용한다.
    """
    F = X.copy()
    for a, b in _SWAP:
        F[a], F[b] = X[b].to_numpy(), X[a].to_numpy()
    for c in _NEGATE:
        F[c] = -X[c]
    for c in _ONE_MINUS:
        F[c] = 1.0 - X[c]
    F["buy_matchup"] = _matchup(F["buy_a"], F["buy_b"])
    F["map_side"] = _map_side(F["map_name"], F["side_a_atk"])
    return F if y is None else (F, 1 - y)
