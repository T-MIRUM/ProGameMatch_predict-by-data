"""Alembic 실행 환경.

target_metadata를 ORM의 Base.metadata로 지정해 `alembic check`/autogenerate가
'모델과 실제 DB가 어긋났는지'를 감지할 수 있게 한다.
"""
from logging.config import fileConfig

from alembic import context
from sqlalchemy import engine_from_config, pool

from propredict.config import get_settings
from propredict.models import Base

config = context.config
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

config.set_main_option("sqlalchemy.url", get_settings().database_url)
target_metadata = Base.metadata


def run_migrations_offline() -> None:
    """DB 접속 없이 SQL만 출력 (`alembic upgrade head --sql`). 리뷰·DBA 전달용."""
    context.configure(url=config.get_main_option("sqlalchemy.url"), target_metadata=target_metadata,
                      literal_binds=True, compare_type=True)
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    # 마이그레이션은 짧게 한 번 실행되므로 커넥션 풀이 필요 없다
    connectable = engine_from_config(config.get_section(config.config_ini_section, {}),
                                     prefix="sqlalchemy.", poolclass=pool.NullPool)
    with connectable.connect() as connection:
        context.configure(connection=connection, target_metadata=target_metadata, compare_type=True)
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
