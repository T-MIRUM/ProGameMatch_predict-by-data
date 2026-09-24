"""Phase 0 데이터 감사 스크립트.

ETL 설계를 '가정'이 아니라 '측정'에 근거하게 하려고 만든다.
원본 CSV를 읽기만 하고 아무것도 수정하지 않으며, 결과를
reports/data_audit_stats.json 으로 남겨 리포트 수치의 출처를 재현 가능하게 한다.

실행: python scripts/audit_data.py [--raw data/raw]
"""
from __future__ import annotations

import argparse
import json
import re
from pathlib import Path

import pandas as pd

# 소스 전체에서 경기를 식별할 수 있는 유일한 공통 컬럼 조합.
KEY = ["Tournament", "Stage", "Match Type", "Match Name"]
MAP_KEY = KEY + ["Map"]
ROUND_KEY = MAP_KEY + ["Round Number"]

# 라운드 승리 방식 중 진영을 확정해 주는 것들.
# 스파이크 폭발 = 공격 승리, 해체 = 수비 승리, 설치 없이 시간 종료 = 수비 승리.
# 'Elimination'은 양 진영 모두 가능하므로 진영 정보를 주지 않는다.
SIDE_BY_WIN_METHOD = {
    "Detonated": "atk",
    "Defused": "def",
    "Time Expiry (No Plant)": "def",
}
MONEY_RE = re.compile(r"^\d+(\.\d+)?k$")


def find_root(raw: Path) -> Path:
    """Kaggle zip 해제 방식에 따라 vct_* 폴더가 한 단계 아래(archive/)에 있을 수 있어 탐색한다."""
    for cand in [raw, *sorted(p for p in raw.iterdir() if p.is_dir())]:
        if any(cand.glob("vct_*")):
            return cand
    raise FileNotFoundError(f"{raw} 아래에서 vct_* 폴더를 찾지 못함")


def audit_schema(root: Path, years: list[str]) -> dict:
    files = sorted({p.relative_to(root / y).as_posix() for y in years for p in (root / y).rglob("*.csv")})
    out = {}
    for f in files:
        headers = {}
        for y in years:
            p = root / y / f
            headers[y] = list(pd.read_csv(p, nrows=0).columns) if p.exists() else None
        uniq = {json.dumps(h) for h in headers.values()}
        out[f] = {"consistent": len(uniq) == 1, "headers": headers if len(uniq) > 1 else next(iter(headers.values()))}
    return out


def infer_sides(wl: pd.DataFrame) -> dict:
    """승리 방식으로 각 하프의 공격 팀을 역산하고, 하프 내 모순 여부를 측정한다.

    발로란트는 1~12R / 13~24R 동안 진영이 고정되므로 하프 안에서 결정적 라운드가
    하나만 있어도 그 하프 전체 진영을 알 수 있다. 연장(25R~)은 매 라운드 교대라 따로 센다.
    """
    win = wl[wl["Outcome"] == "Win"].copy()
    win["side"] = win["Method"].map(SIDE_BY_WIN_METHOD)
    r = win["Round Number"]
    win["half"] = pd.cut(r, [0, 12, 24, 10_000], labels=["H1", "H2", "OT"])
    # 승리 팀이 수비였다면 공격 팀은 상대 팀 -> 맵 단위로 두 팀 이름이 필요
    teams = wl.groupby(MAP_KEY)["Team"].agg(lambda s: tuple(sorted(s.unique())))
    win = win.join(teams.rename("teams"), on=MAP_KEY)
    win = win[win["teams"].map(len) == 2]
    dec = win[win["side"].notna()].copy()
    dec["attacker"] = [
        t if s == "atk" else (ts[1] if ts[0] == t else ts[0])
        for t, s, ts in zip(dec["Team"], dec["side"], dec["teams"])
    ]
    reg = dec[dec["half"] != "OT"]
    per_half = reg.groupby(MAP_KEY + ["half"], observed=True)["attacker"].nunique()
    n_maps = win.groupby(MAP_KEY).ngroups
    halves_total = n_maps * 2
    h = per_half.unstack("half")
    both = h.dropna()
    # H1 공격팀 == H2 공격팀 이면 하프 교대 규칙과 모순
    att = reg.groupby(MAP_KEY + ["half"], observed=True)["attacker"].first().unstack("half").dropna()
    swap_ok = (att["H1"] != att["H2"]).mean() if len(att) else None
    return {
        "maps": int(n_maps),
        "decisive_round_share": round(float(win["side"].notna().mean()), 4),
        "halves_with_side_known": round(len(per_half) / halves_total, 4) if halves_total else None,
        "halves_conflicting": int((per_half > 1).sum()),
        "maps_both_halves_known": round(len(both) / n_maps, 4) if n_maps else None,
        "halftime_swap_consistent": None if swap_ok is None else round(float(swap_ok), 4),
    }


def _attackers(wl: pd.DataFrame) -> pd.DataFrame:
    """결정적 라운드(폭발/해체/설치 없는 시간 종료)마다 공격 팀을 계산한다."""
    win = wl[wl["Outcome"] == "Win"].copy()
    win["side"] = win["Method"].map(SIDE_BY_WIN_METHOD)
    teams = wl.groupby(MAP_KEY)["Team"].agg(lambda s: tuple(sorted(s.unique())))
    win = win.join(teams.rename("teams"), on=MAP_KEY)
    d = win[win["side"].notna() & (win["teams"].map(len) == 2)].copy()
    d["attacker"] = [t if s == "atk" else (ts[1] if ts[0] == t else ts[0])
                     for t, s, ts in zip(d["Team"], d["side"], d["teams"])]
    return d


def check_overtime_rule(wl: pd.DataFrame) -> dict:
    """연장 진영 규칙 검증: 25R부터 매 라운드 교대, 25R은 전반(H1)과 같은 진영이라는 가설.

    가설이 맞으면 H1 공격팀만 알아도 연장 모든 라운드의 진영을 계산할 수 있다.
    """
    d = _attackers(wl)
    h1 = d[d["Round Number"] <= 12].groupby(MAP_KEY)["attacker"].first()
    ot = d[d["Round Number"] >= 25].join(h1.rename("h1_att"), on=MAP_KEY, how="inner")
    if ot.empty:
        return {"ot_decisive_rounds": 0, "ot_rule_match_rate": None}
    same_as_h1 = (ot["Round Number"] - 25) % 2 == 0
    pred_is_h1_att = same_as_h1
    hit = (ot["attacker"] == ot["h1_att"]) == pred_is_h1_att
    return {"ot_decisive_rounds": int(len(ot)), "ot_rule_match_rate": round(float(hit.mean()), 4)}


def check_maps_scores_semantics(wl: pd.DataFrame, ms: pd.DataFrame) -> dict:
    """maps_scores의 'Attacker/Defender Score'가 실제로 무엇을 뜻하는지 두 가설로 검증한다.

    (a) 공격/수비 진영별 승수  vs  (b) 전반(1~12R)/후반(13~24R) 승수.
    컬럼명만 믿고 진영 피처를 만들면 조용히 틀린 피처가 생기므로 반드시 측정으로 확인한다.
    """
    ms = ms.drop_duplicates(MAP_KEY, keep=False)
    reg = wl[(wl["Outcome"] == "Win") & (wl["Round Number"] <= 24)].copy()
    reg["half"] = (reg["Round Number"] > 12).map({False: "H1", True: "H2"})
    by_half = reg.groupby(MAP_KEY + ["Team", "half"]).size().unstack("half", fill_value=0)
    d = _attackers(wl)
    d = d[d["Round Number"] <= 24].assign(half=lambda x: (x["Round Number"] > 12).map({False: "H1", True: "H2"}))
    att = d.groupby(MAP_KEY + ["half"])["attacker"].agg(lambda s: s.iloc[0] if s.nunique() == 1 else None)
    att = att.unstack("half").dropna()
    n = hits_half = hits_side = n_side = 0
    for r in ms.itertuples(index=False):
        mk, team = tuple(r[:5]), r[5]
        k = mk + (team,)
        if k not in by_half.index:
            continue
        h1, h2 = by_half.loc[k].get("H1", 0), by_half.loc[k].get("H2", 0)
        a_s, d_s = r[7], r[8]
        n += 1
        hits_half += int(h1 == a_s and h2 == d_s)
        if mk in att.index:
            a1, a2 = att.loc[mk, "H1"], att.loc[mk, "H2"]
            won_atk = (h1 if a1 == team else 0) + (h2 if a2 == team else 0)
            n_side += 1
            hits_side += int(won_atk == a_s)
    return {
        "maps_checked": n,
        "hyp_first_second_half_match": round(hits_half / n, 4) if n else None,
        "hyp_attacker_defender_match": round(hits_side / n_side, 4) if n_side else None,
    }


def eco_team_names(eco: pd.DataFrame, wl: pd.DataFrame, scores: pd.DataFrame) -> dict:
    """eco_rounds의 팀 이름이 같은 맵의 win_loss / scores 팀 이름과 일치하는지.

    A/B 피벗은 팀 이름 매칭에 의존하므로, 불일치가 있으면 라운드를 잘못된 팀에 붙이게 된다.
    """
    wl_teams = wl.groupby(MAP_KEY)["Team"].agg(frozenset)
    eco_teams = eco.groupby(MAP_KEY)["Team"].agg(frozenset)
    j = pd.concat([eco_teams.rename("eco"), wl_teams.rename("wl")], axis=1, join="inner")
    mism = j[j["eco"] != j["wl"]]
    sc = scores.drop_duplicates(KEY, keep=False).set_index(KEY)
    pair = pd.Series([frozenset([a, b]) for a, b in zip(sc["Team A"], sc["Team B"])], index=sc.index)
    ej = eco_teams.reset_index(level="Map", drop=True)
    ej = ej[~ej.index.duplicated()]
    both = pd.concat([ej.rename("eco"), pair.rename("sc")], axis=1, join="inner")
    return {"maps_compared_with_win_loss": int(len(j)), "maps_team_mismatch_vs_win_loss": int(len(mism)),
            "examples": [sorted(x) + ["|"] + sorted(y) for x, y in mism.head(3).itertuples(index=False)],
            "matches_team_mismatch_vs_scores": int((both["eco"] != both["sc"]).sum()),
            "matches_compared_with_scores": int(len(both))}


def audit_year(root: Path, y: str) -> dict:
    m = root / y / "matches"
    ids = pd.read_csv(root / y / "ids" / "tournaments_stages_matches_games_ids.csv")
    scores = pd.read_csv(m / "scores.csv")
    eco = pd.read_csv(m / "eco_rounds.csv")
    wl = pd.read_csv(m / "win_loss_methods_round_number.csv")
    ms = pd.read_csv(m / "maps_scores.csv")
    draft = pd.read_csv(m / "draft_phase.csv", usecols=KEY + ["Action"])
    rk = pd.read_csv(m / "rounds_kills.csv", usecols=ROUND_KEY + ["Kill Type"])

    # --- 식별자 ---
    key_mid = ids.groupby(KEY)["Match ID"].nunique()
    colliding = key_mid[key_mid > 1].index
    dup_scores = scores[scores.duplicated(KEY, keep=False)]

    # --- eco_rounds 품질 ---
    rows_per_round = eco.groupby(ROUND_KEY).size()
    wins_per_round = eco[eco["Outcome"] == "Win"].groupby(ROUND_KEY).size().reindex(rows_per_round.index, fill_value=0)
    bad_money = {c: int((~eco[c].astype(str).str.match(MONEY_RE)).sum()) for c in ["Loadout Value", "Remaining Credits"]}
    eco_maps = eco.groupby(MAP_KEY).ngroups
    wl_maps = wl.groupby(MAP_KEY).ngroups
    # 맵 단위로 eco가 전체 라운드를 가지고 있는지 (모멘텀·스코어 피처는 빠진 라운드가 있으면 틀어진다)
    eco_rc = eco.groupby(MAP_KEY)["Round Number"].nunique()
    wl_rc = wl.groupby(MAP_KEY)["Round Number"].nunique()
    j = pd.concat([eco_rc.rename("eco"), wl_rc.rename("wl")], axis=1, join="inner")
    # 라운드 번호가 1부터 빈틈없이 이어지는지
    eco_gap = eco.groupby(MAP_KEY)["Round Number"].agg(lambda s: s.max() != s.nunique() or s.min() != 1)

    # --- 밴픽 커버리지 ---
    n_matches = scores.drop_duplicates(KEY).shape[0]
    n_draft = draft.drop_duplicates(KEY).shape[0]

    # --- rounds_kills ---
    rk_per_round = rk.groupby(ROUND_KEY).size()

    return {
        "rows": {"scores": len(scores), "eco_rounds": len(eco), "win_loss_rounds": len(wl),
                 "maps_scores": len(ms), "ids_games": len(ids), "draft_phase": len(draft), "rounds_kills": len(rk)},
        "tournaments": int(scores["Tournament"].nunique()),
        "ids": {
            "has_match_id_column": "Match ID" in ids.columns,
            "composite_keys": int(len(key_mid)),
            "composite_keys_with_multiple_match_ids": int(len(colliding)),
            "colliding_keys": [list(k) for k in colliding],
            "scores_duplicate_rows": int(len(dup_scores)),
        },
        "eco_rounds": {
            "nulls": int(eco.isna().sum().sum()),
            # 완전히 동일한 행: 같은 맵이 Game ID 두 개로 중복 수집된 경우 등. 안전하게 제거 가능.
            "exact_duplicate_rows": int(eco.duplicated().sum()),
            # eco의 (대회,스테이지,매치타입,매치명,맵) 키가 win_loss에 그대로 존재하는 비율.
            # 낮으면 대회명 표기가 파일마다 다르다는 뜻 -> 정규화 레이어 필요.
            "maps_joinable_to_win_loss": round(len(set(map(tuple, eco[MAP_KEY].drop_duplicates().values))
                                                   & set(map(tuple, wl[MAP_KEY].drop_duplicates().values))) / max(eco_maps, 1), 4),
            "tournament_names_not_in_scores": sorted(set(eco["Tournament"]) - set(scores["Tournament"])),
            "unparseable_money": bad_money,
            "types": eco["Type"].value_counts().to_dict(),
            "outcomes": eco["Outcome"].value_counts().to_dict(),
            "rounds": int(len(rows_per_round)),
            "rounds_rows_ne_2": int((rows_per_round != 2).sum()),
            "rounds_wins_ne_1": int((wins_per_round != 1).sum()),
            "maps": int(eco_maps),
            "maps_in_win_loss": int(wl_maps),
            "map_coverage_vs_win_loss": round(eco_maps / wl_maps, 4) if wl_maps else None,
            "maps_with_round_gaps": int(eco_gap.sum()),
            "maps_fewer_rounds_than_win_loss": int((j["eco"] < j["wl"]).sum()),
            "max_round_number": int(eco["Round Number"].max()),
        },
        "draft": {"matches": n_matches, "matches_with_draft": n_draft,
                  "coverage": round(n_draft / n_matches, 4) if n_matches else None,
                  "actions": draft["Action"].value_counts().to_dict()},
        "rounds_kills": {"mean_rows_per_round": round(float(rk_per_round.mean()), 2),
                         "kill_types": sorted(rk["Kill Type"].dropna().unique().tolist())},
        "sides": {**infer_sides(wl), **check_overtime_rule(wl)},
        "maps_scores_semantics": check_maps_scores_semantics(wl, ms),
        "eco_team_names": eco_team_names(eco, wl, scores),
        "loadout_null_by_tournament": eco[eco["Loadout Value"].isna()]["Tournament"].value_counts().to_dict(),
        "maps_scores_attacker_nonnull": round(float(ms["Team A Attacker Score"].notna().mean()), 4),
    }


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--raw", default="data/raw")
    ap.add_argument("--out", default="reports/data_audit_stats.json")
    ap.add_argument("--years", nargs="*")
    a = ap.parse_args()
    root = find_root(Path(a.raw))
    years = a.years or sorted(p.name for p in root.glob("vct_*"))
    result = {"root": str(root), "years": years, "schema": audit_schema(root, years), "per_year": {}}
    for y in years:
        print(f"auditing {y} ...", flush=True)
        result["per_year"][y] = audit_year(root, y)
    Path(a.out).parent.mkdir(parents=True, exist_ok=True)
    Path(a.out).write_text(json.dumps(result, ensure_ascii=False, indent=2, default=str))
    print(f"wrote {a.out}")


if __name__ == "__main__":
    main()
