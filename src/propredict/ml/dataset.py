"""DB에서 모델링용 라운드 테이블을 읽는다.

모든 라운드를 읽는다(이코노미 유무와 무관). 스코어·모멘텀·팀 강도는 이코노미가 없는 라운드까지
포함한 '완전한 시퀀스'로 계산해야 하기 때문이다. 이코노미가 없는 라운드는 피처 계산 후 학습에서 뺀다.
"""

from __future__ import annotations

import pandas as pd
from sqlalchemy import Engine, text

QUERY = text("""
    SELECT m.match_id, m.season, m.source_match_id, m.tournament, m.team_a, m.team_b,
           g.map_game_id, g.map_name, g.map_order,
           r.round_number, r.team_a_side,
           r.team_a_loadout, r.team_b_loadout, r.team_a_credits, r.team_b_credits,
           r.team_a_buy_type, r.team_b_buy_type, r.winner
    FROM rounds r
    JOIN map_games g USING (map_game_id)
    JOIN matches m USING (match_id)
""")

# 시간 순서의 근사: 날짜 컬럼이 없어 (시즌, 원본 Match ID)를 쓴다.
# vlr.gg Match ID는 대진표 진행 순서와 96~99% 일치한다(docs/decisions.md D13).
CHRONO_ORDER = ["season", "source_match_id", "match_id", "map_order", "map_game_id", "round_number"]


def load_rounds(engine: Engine) -> pd.DataFrame:
    with engine.connect() as conn:
        df = pd.read_sql(QUERY, conn)
    int_cols = ["team_a_loadout", "team_b_loadout", "team_a_credits", "team_b_credits", "source_match_id", "map_order"]
    df[int_cols] = df[int_cols].astype("Float64").astype(float)
    return df.sort_values(CHRONO_ORDER, kind="stable", na_position="last").reset_index(drop=True)
