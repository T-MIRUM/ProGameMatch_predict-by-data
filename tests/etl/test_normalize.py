import pandas as pd
import pytest

from propredict.etl.normalize import normalize_tournament, parse_money, validate_buy_type


def test_parse_money_handles_k_suffix_and_float_error():
    out = parse_money(pd.Series(["14.4k", "0.3k", "37.5k", "5k"]))
    # 14.4 * 1000 = 14400.000000000002 → 반올림으로 정확한 정수가 되어야 한다
    assert out.tolist() == [14400, 300, 37500, 5000]
    assert str(out.dtype) == "Int64"


def test_parse_money_keeps_missing_as_na():
    out = parse_money(pd.Series(["1.0k", None], dtype="string"))
    assert out.iloc[0] == 1000 and pd.isna(out.iloc[1])


def test_parse_money_rejects_unknown_format():
    # 조용히 NaN으로 만들면 새 데이터 문제가 숨어 버린다
    with pytest.raises(ValueError):
        parse_money(pd.Series(["14,400"]))


def test_tournament_alias_maps_2025_eco_names_and_leaves_others():
    s = pd.Series(
        ["Champions Tour 2025: Masters Bangkok", "Champions Tour 2025: EMEA Kickoff", "Valorant Masters Toronto 2025"]
    )
    assert normalize_tournament(s).tolist() == [
        "Valorant Masters Bangkok 2025",
        "VCT 2025: EMEA Kickoff",
        "Valorant Masters Toronto 2025",
    ]


def test_validate_buy_type_rejects_unknown():
    with pytest.raises(ValueError):
        validate_buy_type(pd.Series(["Full buy: 20k+", "Pistol"]))
