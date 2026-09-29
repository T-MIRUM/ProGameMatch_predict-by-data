"""값 정규화.

원본 파일들은 컬럼 스키마는 연도별로 같지만 '값'의 표기가 다른 곳이 있다(reports/data_audit.md).
정규화 규칙을 코드 곳곳에 흩지 않고 여기 모아 두면, 새 불일치를 발견했을 때 한 곳만 고치면 된다.
"""

from __future__ import annotations

import pandas as pd

BUY_TYPES = ("Eco: 0-5k", "Semi-eco: 5-10k", "Semi-buy: 10-20k", "Full buy: 20k+")

# eco_rounds.csv(2025)만 대회명을 옛 표기로 쓴다. 매핑 후 win_loss와의 맵 조인율이 9.9% → 100%가 된다.
# 규칙(prefix 치환)으로 일반화하지 않고 명시적 표로 둔 이유: Masters처럼 규칙에서 벗어나는 이름이 있고,
# 모르는 새 이름이 생기면 조용히 잘못 바꾸기보다 조인 실패로 드러나는 편이 안전하기 때문이다.
TOURNAMENT_ALIASES: dict[str, str] = {
    "Champions Tour 2025: Americas Kickoff": "VCT 2025: Americas Kickoff",
    "Champions Tour 2025: Americas Stage 1": "VCT 2025: Americas Stage 1",
    "Champions Tour 2025: EMEA Kickoff": "VCT 2025: EMEA Kickoff",
    "Champions Tour 2025: EMEA Stage 1": "VCT 2025: EMEA Stage 1",
    "Champions Tour 2025: Pacific Kickoff": "VCT 2025: Pacific Kickoff",
    "Champions Tour 2025: Pacific Stage 1": "VCT 2025: Pacific Stage 1",
    "Champions Tour 2025: Masters Bangkok": "Valorant Masters Bangkok 2025",
}


def normalize_tournament(s: pd.Series) -> pd.Series:
    return s.replace(TOURNAMENT_ALIASES)


def parse_money(s: pd.Series) -> pd.Series:
    """'14.4k' → 14400 (정수 크레딧). 결측은 <NA>로 유지한다.

    float 곱셈 오차(14.4 * 1000 = 14400.000000000002)를 없애려고 반올림 후 정수로 바꾼다.
    'k' 형식이 아닌 값이 들어오면 조용히 NaN으로 만들지 않고 예외를 낸다:
    감사 단계에서 모든 값이 이 형식임을 확인했으므로, 다른 형식은 새 데이터 문제라는 신호다.
    """
    str_s = s.astype("string").str.strip()
    ok = str_s.isna() | str_s.str.fullmatch(r"\d+(\.\d+)?k").fillna(False)
    if not ok.all():
        bad = str_s[~ok].unique()[:5].tolist()
        raise ValueError(f"알 수 없는 금액 형식: {bad}")
    num = pd.to_numeric(str_s.str.removesuffix("k"), errors="raise") * 1000
    return num.round().astype("Int64")


def validate_buy_type(s: pd.Series) -> pd.Series:
    unknown = set(s.dropna().unique()) - set(BUY_TYPES)
    if unknown:
        raise ValueError(f"알 수 없는 구매 유형: {sorted(unknown)}")
    return s
