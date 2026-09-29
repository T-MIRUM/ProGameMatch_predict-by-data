"""ETL 실행 진입점.

    uv run python -m propredict.etl                 # 모든 시즌
    uv run python -m propredict.etl --seasons 2025 2026

시즌마다 별도 트랜잭션으로 적재한다: 한 시즌이 실패해도 앞서 끝난 시즌은 유지되고,
실패한 시즌은 롤백되어 절반만 들어간 상태가 남지 않는다.
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

from sqlalchemy import text

from propredict.config import get_settings
from propredict.db import get_engine
from propredict.etl.load import TableStats, load_season
from propredict.etl.sources import find_root, list_seasons, read_season
from propredict.etl.transform import transform_season


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="VCT CSV → PostgreSQL ETL")
    ap.add_argument("--raw", type=Path, default=get_settings().raw_data_dir)
    ap.add_argument("--seasons", type=int, nargs="*", help="적재할 시즌 (기본: 전부)")
    ap.add_argument("--report", type=Path, help="요약을 JSON으로 저장할 경로")
    args = ap.parse_args(argv)

    root = find_root(args.raw)
    seasons = args.seasons or list_seasons(root)
    engine = get_engine()
    summary: dict[str, dict] = {}

    for season in seasons:
        t0 = time.perf_counter()
        res = transform_season(read_season(root, season))
        with engine.begin() as conn:
            stats = load_season(conn, season, res)
        summary[str(season)] = {
            "seconds": round(time.perf_counter() - t0, 1),
            "transform": res.report,
            "load": {k: vars(v) for k, v in stats.items()},
        }
        _print_season(season, summary[str(season)])

    with engine.connect() as conn:
        totals = {
            t: conn.execute(text(f"SELECT count(*) FROM {t}")).scalar_one() for t in ("matches", "map_games", "rounds")
        }
    print("\nDB 총계: " + ", ".join(f"{k}={v:,}" for k, v in totals.items()))
    if args.report:
        args.report.parent.mkdir(parents=True, exist_ok=True)
        args.report.write_text(json.dumps({"seasons": summary, "db_totals": totals}, ensure_ascii=False, indent=2))
    return 0


def _print_season(season: int, s: dict) -> None:
    rep, load = s["transform"], s["load"]
    print(f"\n[{season}] {s['seconds']}s")
    for table in ("matches", "map_games", "rounds"):
        st = TableStats(**load[table])
        print(f"  {table:<10} rows={rep[table]:>8,}  +{st.inserted:,} ~{st.updated:,} -{st.deleted:,}")
    excluded = {k: v for k, v in rep.items() if k.endswith(("excluded_ambiguous", "malformed", "mismatch")) and v}
    print(
        f"  economy rounds={rep['rounds_with_economy']:,}  side-known maps={rep['maps_side_known']:,}"
        + (f"  excluded={excluded}" if excluded else "")
    )


if __name__ == "__main__":
    sys.exit(main())
