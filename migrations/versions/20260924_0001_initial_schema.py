"""initial schema: matches, map_games, rounds

설계 근거는 src/propredict/models.py 모듈 docstring 참고.

Revision ID: 0001
Revises:
Create Date: 2026-09-24
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0001"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

BUY = "'Eco: 0-5k', 'Semi-eco: 5-10k', 'Semi-buy: 10-20k', 'Full buy: 20k+'"
SIDE = "'atk', 'def'"


def upgrade() -> None:
    op.create_table(
        "matches",
        sa.Column("match_id", sa.Integer(), primary_key=True),
        sa.Column("source_match_id", sa.Integer(), nullable=True),
        sa.Column("season", sa.SmallInteger(), nullable=False),
        sa.Column("tournament", sa.Text(), nullable=False),
        sa.Column("stage", sa.Text(), nullable=True),
        sa.Column("match_type", sa.Text(), nullable=True),
        sa.Column("match_name", sa.Text(), nullable=True),
        sa.Column("team_a", sa.Text(), nullable=False),
        sa.Column("team_b", sa.Text(), nullable=False),
        sa.Column("score_a", sa.SmallInteger(), nullable=True),
        sa.Column("score_b", sa.SmallInteger(), nullable=True),
        sa.UniqueConstraint("source_match_id", name="matches_source_match_id_key"),
        sa.UniqueConstraint("season", "tournament", "stage", "match_type", "match_name", name="uq_matches_natural_key"),
    )
    op.create_index("idx_matches_season", "matches", ["season"])

    op.create_table(
        "map_games",
        sa.Column("map_game_id", sa.Integer(), primary_key=True),
        sa.Column("match_id", sa.Integer(), sa.ForeignKey("matches.match_id", ondelete="CASCADE"), nullable=False),
        sa.Column("source_game_id", sa.Integer(), nullable=True),
        sa.Column("map_name", sa.Text(), nullable=False),
        sa.Column("map_order", sa.SmallInteger(), nullable=True),
        sa.Column("total_rounds", sa.SmallInteger(), nullable=True),
        sa.Column("score_a", sa.SmallInteger(), nullable=True),
        sa.Column("score_b", sa.SmallInteger(), nullable=True),
        sa.Column("team_a_first_half_side", sa.String(3), nullable=True),
        sa.UniqueConstraint("match_id", "map_name", name="uq_map_games_match_map"),
        sa.CheckConstraint(
            f"team_a_first_half_side IS NULL OR team_a_first_half_side IN ({SIDE})", name="ck_map_games_first_half_side"
        ),
    )

    op.create_table(
        "rounds",
        sa.Column("round_id", sa.BigInteger(), primary_key=True),
        sa.Column(
            "map_game_id", sa.Integer(), sa.ForeignKey("map_games.map_game_id", ondelete="CASCADE"), nullable=False
        ),
        sa.Column("round_number", sa.SmallInteger(), nullable=False),
        sa.Column("team_a_side", sa.String(3), nullable=True),
        sa.Column("team_a_loadout", sa.Integer(), nullable=True),
        sa.Column("team_b_loadout", sa.Integer(), nullable=True),
        sa.Column("team_a_credits", sa.Integer(), nullable=True),
        sa.Column("team_b_credits", sa.Integer(), nullable=True),
        sa.Column("team_a_buy_type", sa.Text(), nullable=True),
        sa.Column("team_b_buy_type", sa.Text(), nullable=True),
        sa.Column("winner", sa.String(1), nullable=False),
        sa.Column("win_method", sa.Text(), nullable=True),
        # UNIQUE가 (map_game_id, round_number) 인덱스를 만들므로 map_game_id 단독 인덱스는 두지 않는다
        sa.UniqueConstraint("map_game_id", "round_number", name="uq_rounds_map_round"),
        sa.CheckConstraint("winner IN ('A', 'B')", name="ck_rounds_winner"),
        sa.CheckConstraint("round_number >= 1", name="ck_rounds_round_number"),
        sa.CheckConstraint(f"team_a_side IS NULL OR team_a_side IN ({SIDE})", name="ck_rounds_side"),
        sa.CheckConstraint(f"team_a_buy_type IS NULL OR team_a_buy_type IN ({BUY})", name="ck_rounds_buy_type_a"),
        sa.CheckConstraint(f"team_b_buy_type IS NULL OR team_b_buy_type IN ({BUY})", name="ck_rounds_buy_type_b"),
    )


def downgrade() -> None:
    # FK 의존 순서의 역순으로 제거
    op.drop_table("rounds")
    op.drop_table("map_games")
    op.drop_index("idx_matches_season", table_name="matches")
    op.drop_table("matches")
