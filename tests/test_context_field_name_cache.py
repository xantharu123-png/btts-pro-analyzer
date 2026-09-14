"""Memoize only bounded pure field-name classification, never data validity."""
import re

import pytest

from context_models import contracts


def old_classification(name):
    separated = re.sub(r"([a-z0-9])([A-Z])", r"\1_\2", name)
    lowered = name.casefold()
    return bool(contracts._PRICE_WORDS.search(separated)) or any(
        word in lowered for word in ("odds", "price", "bookmaker", "quote", "quoten"))


def test_field_classification_is_identical_and_bounded():
    cache = contracts._cached_price_name
    cache.cache_clear()
    names = ["player_id", "observed_at", "actual_start", "EV", "rawOdds", "bestPrice",
             "quote2", "modelApproval", "release", "recovery", "éOdds", "prıce"]
    names += [f"field_{index}" for index in range(600)]
    names += ["x"*10000+"Odds", "x"*10000]
    for name in names:
        assert contracts._is_price_name(name) == old_classification(name)
    assert cache.cache_info().currsize <= 512
    cache.cache_clear()
    for _ in range(10):
        assert not contracts._is_price_name("player_id")
    assert cache.cache_info().hits == 9
    assert contracts._is_price_name("x"*10000+"Odds")
    assert cache.cache_info().currsize == 1


def test_cached_name_does_not_skip_validation_of_new_value():
    assert contracts._sport_json({"player_id": "one"}) == {"player_id": "one"}
    with pytest.raises(contracts.ContextContractError):
        contracts._sport_json({"player_id": float("nan")})
