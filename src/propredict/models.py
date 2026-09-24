"""ORM 스키마 — Alembic 마이그레이션의 기준(single source of truth).

명세 §4의 초안 대비 변경점과 이유 (근거 수치는 reports/data_audit.md):

1. matches.source_match_id / map_games.source_game_id 추가
   원본 ids/ 파일에 Match ID·Game ID가 있다. 대리키는 그대로 쓰되 원본 ID를 남겨
   "이 행이 원본 어디서 왔는가"를 추적할 수 있게 한다. 2021년 복합키 충돌(같은 이름의
   서로 다른 두 경기)도 이 ID로 판별했다.

2. rounds는 eco_rounds가 아니라 win_loss 기준으로 '모든 라운드'를 적재하고, 이코노미 컬럼은 NULL 허용
   eco_rounds는 맵의 46~100%만 담고 있다. 스코어·연승 같은 맥락 피처는 앞 라운드가
   하나라도 빠지면 틀어지므로, 라운드 시퀀스는 완전한 win_loss에서 만들고 eco는 붙여 넣는다.
   학습 시에는 buy_type이 있는 라운드만 고른다.

3. 진영 컬럼 추가 (map_games.team_a_first_half_side, rounds.team_a_side)
   maps_scores의 Attacker/Defender Score는 실제로 전·후반 점수라서 쓸 수 없다.
   대신 라운드 승리 방식(폭발=공격 승, 해체/무설치 시간종료=수비 승)으로 역산한다. 모르면 NULL.

4. rounds.win_method 추가 — 분석·검증용. 라운드 '결과' 정보이므로 피처로 쓰면 누수다.

5. idx_rounds_map_game 제거
   UNIQUE(map_game_id, round_number)가 map_game_id를 선두 컬럼으로 하는 인덱스를 이미 만든다.
   같은 인덱스를 두 번 두면 쓰기 비용만 늘어난다.

6. 구매 유형·진영은 PostgreSQL ENUM 대신 CHECK 제약
   ENUM은 값 추가/변경 마이그레이션이 번거롭다. CHECK는 제약만 교체하면 된다.
"""

from sqlalchemy import (
    BigInteger,
    CheckConstraint,
    ForeignKey,
    Index,
    Integer,
    SmallInteger,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship

BUY_TYPES = ("Eco: 0-5k", "Semi-eco: 5-10k", "Semi-buy: 10-20k", "Full buy: 20k+")
SIDES = ("atk", "def")


def _in(col: str, values: tuple[str, ...]) -> str:
    return f"{col} IN ({', '.join(repr(v) for v in values)})"


class Base(DeclarativeBase):
    pass


class Match(Base):
    __tablename__ = "matches"

    match_id: Mapped[int] = mapped_column(Integer, primary_key=True)
    source_match_id: Mapped[int | None] = mapped_column(Integer, unique=True)
    season: Mapped[int] = mapped_column(SmallInteger)  # 폴더명 vct_YYYY에서 파싱
    tournament: Mapped[str] = mapped_column(Text)
    stage: Mapped[str | None] = mapped_column(Text)
    match_type: Mapped[str | None] = mapped_column(Text)
    match_name: Mapped[str | None] = mapped_column(Text)
    team_a: Mapped[str] = mapped_column(Text)
    team_b: Mapped[str] = mapped_column(Text)
    score_a: Mapped[int | None] = mapped_column(SmallInteger)  # 세트(맵) 스코어
    score_b: Mapped[int | None] = mapped_column(SmallInteger)

    map_games: Mapped[list["MapGame"]] = relationship(back_populates="match", cascade="all, delete-orphan")

    __table_args__ = (
        # 원본의 복합키. ETL 재실행 시 upsert 기준이 되어 멱등성을 보장한다.
        UniqueConstraint("season", "tournament", "stage", "match_type", "match_name", name="uq_matches_natural_key"),
        Index("idx_matches_season", "season"),
    )


class MapGame(Base):
    __tablename__ = "map_games"

    map_game_id: Mapped[int] = mapped_column(Integer, primary_key=True)
    match_id: Mapped[int] = mapped_column(ForeignKey("matches.match_id", ondelete="CASCADE"))
    source_game_id: Mapped[int | None] = mapped_column(Integer)
    map_name: Mapped[str] = mapped_column(Text)
    # 경기 내 맵 순서. 원본에 명시 컬럼이 없어 Game ID 오름차순으로 매긴다(모르면 NULL).
    map_order: Mapped[int | None] = mapped_column(SmallInteger)
    total_rounds: Mapped[int | None] = mapped_column(SmallInteger)
    score_a: Mapped[int | None] = mapped_column(SmallInteger)  # 이 맵에서 딴 라운드 수
    score_b: Mapped[int | None] = mapped_column(SmallInteger)
    team_a_first_half_side: Mapped[str | None] = mapped_column(String(3))

    match: Mapped[Match] = relationship(back_populates="map_games")
    rounds: Mapped[list["Round"]] = relationship(back_populates="map_game", cascade="all, delete-orphan")

    __table_args__ = (
        UniqueConstraint("match_id", "map_name", name="uq_map_games_match_map"),
        CheckConstraint(
            f"team_a_first_half_side IS NULL OR {_in('team_a_first_half_side', SIDES)}",
            name="ck_map_games_first_half_side",
        ),
    )


class Round(Base):
    __tablename__ = "rounds"

    round_id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    map_game_id: Mapped[int] = mapped_column(ForeignKey("map_games.map_game_id", ondelete="CASCADE"))
    round_number: Mapped[int] = mapped_column(SmallInteger)
    team_a_side: Mapped[str | None] = mapped_column(String(3))

    # 이코노미: eco_rounds가 없는 맵이거나 원본 결측(2026 Loadout Value 전체)이면 NULL
    team_a_loadout: Mapped[int | None] = mapped_column(Integer)
    team_b_loadout: Mapped[int | None] = mapped_column(Integer)
    team_a_credits: Mapped[int | None] = mapped_column(Integer)
    team_b_credits: Mapped[int | None] = mapped_column(Integer)
    team_a_buy_type: Mapped[str | None] = mapped_column(Text)
    team_b_buy_type: Mapped[str | None] = mapped_column(Text)

    winner: Mapped[str] = mapped_column(String(1))
    win_method: Mapped[str | None] = mapped_column(Text)  # 결과 정보: 피처 사용 금지

    map_game: Mapped[MapGame] = relationship(back_populates="rounds")

    __table_args__ = (
        UniqueConstraint("map_game_id", "round_number", name="uq_rounds_map_round"),
        CheckConstraint("winner IN ('A', 'B')", name="ck_rounds_winner"),
        CheckConstraint("round_number >= 1", name="ck_rounds_round_number"),
        CheckConstraint(f"team_a_side IS NULL OR {_in('team_a_side', SIDES)}", name="ck_rounds_side"),
        CheckConstraint(f"team_a_buy_type IS NULL OR {_in('team_a_buy_type', BUY_TYPES)}", name="ck_rounds_buy_type_a"),
        CheckConstraint(f"team_b_buy_type IS NULL OR {_in('team_b_buy_type', BUY_TYPES)}", name="ck_rounds_buy_type_b"),
    )
