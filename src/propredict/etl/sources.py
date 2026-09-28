"""원본 CSV 위치 탐색과 읽기.

I/O를 이 모듈에만 모아 두면 transform은 DataFrame만 받는 순수 함수가 되어
작은 가짜 데이터로 단위 테스트할 수 있다.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

import pandas as pd

# 원본 파일 전체에서 경기를 식별하는 유일한 공통 컬럼 조합 (Match ID는 ids/ 파일에만 있다)
MATCH_KEY = ["Tournament", "Stage", "Match Type", "Match Name"]
MAP_KEY = MATCH_KEY + ["Map"]
ROUND_KEY = MAP_KEY + ["Round Number"]

_SEASON_RE = re.compile(r"^vct_(\d{4})$")


@dataclass(frozen=True)
class SeasonFrames:
    """한 시즌(연도 폴더)에서 ETL이 쓰는 원본 테이블 묶음."""

    season: int
    scores: pd.DataFrame
    ids: pd.DataFrame
    win_loss: pd.DataFrame
    eco: pd.DataFrame


def find_root(raw: Path) -> Path:
    """vct_* 폴더가 있는 디렉터리를 찾는다.

    Kaggle zip을 풀면 archive/ 한 단계가 더 생기기도 해서 raw 자체와 바로 아래 하위 폴더를 확인한다.
    """
    for cand in [raw, *sorted(p for p in raw.iterdir() if p.is_dir())]:
        if any(cand.glob("vct_*")):
            return cand
    raise FileNotFoundError(f"{raw} 아래에서 vct_* 폴더를 찾지 못했습니다. scripts/download_data.sh를 먼저 실행하세요.")


def list_seasons(root: Path) -> list[int]:
    return sorted(int(m.group(1)) for p in root.iterdir() if (m := _SEASON_RE.match(p.name)))


def read_season(root: Path, season: int) -> SeasonFrames:
    base = root / f"vct_{season}"
    m = base / "matches"
    # 필요한 컬럼만 읽는다: 2021년 파일은 수십 MB라서 메모리와 시간을 아낀다
    return SeasonFrames(
        season=season,
        scores=pd.read_csv(m / "scores.csv"),
        ids=pd.read_csv(
            base / "ids" / "tournaments_stages_matches_games_ids.csv",
            usecols=MAP_KEY + ["Match ID", "Game ID"],
        ),
        win_loss=pd.read_csv(m / "win_loss_methods_round_number.csv"),
        # 금액은 "14.4k" 문자열이라 파싱 전까지 문자열로 유지한다
        eco=pd.read_csv(m / "eco_rounds.csv", dtype={"Loadout Value": "string", "Remaining Credits": "string"}),
    )
