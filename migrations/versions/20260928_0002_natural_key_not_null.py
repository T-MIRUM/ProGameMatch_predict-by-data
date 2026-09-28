"""matches natural key columns NOT NULL

ETL의 멱등 upsert는 UNIQUE(season, tournament, stage, match_type, match_name)의 ON CONFLICT에 의존한다.
PostgreSQL의 UNIQUE는 NULL을 서로 다른 값으로 취급하므로, 키에 NULL이 들어오면 충돌이 감지되지 않아
재실행할 때마다 같은 경기가 새 행으로 쌓인다. 원본 전체에 결측이 없음을 확인했으므로(2021~2026 0건)
스키마 수준에서 NOT NULL로 막아 이 실패 모드를 원천 차단한다.

Revision ID: 0002
Revises: 0001
Create Date: 2026-09-28
"""

from collections.abc import Sequence

from alembic import op

revision: str = "0002"
down_revision: str | None = "0001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

COLUMNS = ("stage", "match_type", "match_name")


def upgrade() -> None:
    for col in COLUMNS:
        op.alter_column("matches", col, nullable=False)


def downgrade() -> None:
    for col in COLUMNS:
        op.alter_column("matches", col, nullable=True)
