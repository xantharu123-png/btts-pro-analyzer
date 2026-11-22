"""A league's provider capabilities are metadata, never today's injury/odds feed."""
from concurrent.futures import ThreadPoolExecutor
from types import SimpleNamespace

import pytest

import challenge_15k
import football_coverage_cache as cache
import shadow_clv_automation as shadow
from challenge_15k import ChallengeDataProvider
from shadow_clv_automation import ShadowProvider


def payload(league=39, season=2026, injuries=False, lineups=True):
    return [{"league": {"id": league}, "seasons": [{"year": season, "coverage": {
        "injuries": injuries, "fixtures": {"lineups": lineups}}}]}]


def provider(kind, get):
    result = kind("test-key", None)
    setattr(result, "_football_get" if kind is ChallengeDataProvider else "_get", get)
    return result


@pytest.mark.parametrize("first,second", [(ChallengeDataProvider, ShadowProvider),
                                          (ShadowProvider, ChallengeDataProvider)])
@pytest.mark.parametrize("covered", [False, True])
def test_new_provider_uses_same_validated_disk_observation(first, second, covered):
    def fetch(path, params, label):
        assert path == "leagues" and params == {"id": 39, "season": 2026}
        return payload(injuries=covered, lineups=covered)

    expected = {"injuries": covered, "lineups": covered}
    assert provider(first, fetch).coverage(39, 2026) == expected
    assert provider(second, lambda *_: pytest.fail("repeated coverage request")).coverage(39, 2026) == expected


@pytest.mark.parametrize("age", [-1, 24 * 3600 - 1, 24 * 3600, 24 * 3600 + 1])
def test_read_does_not_renew_clock_and_rejects_future_or_expired_metadata(monkeypatch, age):
    now = 100_000
    monkeypatch.setattr(cache, "time", lambda: now)
    calls = []

    def fetch(*args):
        calls.append(args)
        return payload(injuries=len(calls) > 1)

    owner = provider(ShadowProvider, fetch)
    assert owner.coverage(39, 2026)["injuries"] is False
    now += 42
    assert owner.coverage(39, 2026)["injuries"] is False
    now = 100_000 + age
    expect_refresh = age != 24 * 3600 - 1
    assert owner.coverage(39, 2026)["injuries"] is expect_refresh
    assert len(calls) == (2 if expect_refresh else 1)


@pytest.mark.parametrize("kind", [ShadowProvider, ChallengeDataProvider])
@pytest.mark.parametrize("bad", [
    None, [], [{}], payload(league=40), payload(season=2025), payload(league=39.0),
    payload(season=2026.0), payload(injuries=1), payload(lineups=None),
    payload() + payload(), [{"league": {"id": 39}, "seasons": payload()[0]["seasons"] * 2}],
    [{"seasons": payload()[0]["seasons"]}],
    [{"league": {"id": 39}, "seasons": [{"year": 2026, "coverage": {"injuries": False}}]}],
])
def test_bad_or_ambiguous_provider_answer_never_prevents_next_real_attempt(kind, bad):
    provider(kind, lambda *_: bad).coverage(39, 2026)
    assert not cache.CACHE_PATH.exists()
    calls = []

    def fetch(*args):
        calls.append(args)
        return payload(injuries=True)

    assert provider(kind, fetch).coverage(39, 2026) == {"injuries": True, "lineups": True}
    assert len(calls) == 1


def test_other_leagues_and_seasons_are_separate_and_reads_do_not_mutate_prior_errors():
    def fetch(_, params, __):
        return payload(params["id"], params["season"], injuries=params["id"] == 40, lineups=params["season"] == 2026)

    initial = provider(ShadowProvider, fetch)
    assert initial.coverage(39, 2026) == {"injuries": False, "lineups": True}
    assert initial.coverage(39, 2025) == {"injuries": False, "lineups": False}
    assert initial.coverage(40, 2026) == {"injuries": True, "lineups": True}
    owner = provider(ChallengeDataProvider, lambda *_: pytest.fail("unexpected source call"))
    owner.last_request_budget_deferred = owner.last_request_rate_limited = True
    owner.errors.append("earlier request failed")
    assert owner.coverage(39, 2026) == {"injuries": False, "lineups": True}
    assert owner.last_request_budget_deferred is owner.last_request_rate_limited is False
    assert owner.errors == ["earlier request failed"]


def test_corrupt_disk_cache_cannot_fail_or_replace_a_valid_provider_response():
    cache.CACHE_PATH.parent.mkdir(parents=True)
    cache.CACHE_PATH.write_bytes(b"not a sqlite database")
    owner = provider(ShadowProvider, lambda *_: payload())
    assert owner.coverage(39, 2026) == {"injuries": False, "lineups": True}
    assert cache.CACHE_PATH.read_bytes() == b"not a sqlite database"


def test_capacity_eviction_preserves_newest_keys(monkeypatch):
    monkeypatch.setattr(cache, "MAX_ENTRIES", 2)
    for league in (39, 40, 41):
        cache.remember_coverage(league, 2026, payload(league))
    assert cache.load_coverage(39, 2026) is None
    assert cache.load_coverage(40, 2026) == {"injuries": False, "lineups": True}
    assert cache.load_coverage(41, 2026) == {"injuries": False, "lineups": True}


def test_concurrent_short_writes_do_not_discard_other_league_keys():
    def remember(league):
        return cache.remember_coverage(league, 2026, payload(league))

    with ThreadPoolExecutor(max_workers=2) as pool:
        list(pool.map(remember, range(35, 45)))
    assert all(cache.load_coverage(league, 2026) == {"injuries": False, "lineups": True}
               for league in range(35, 45))


@pytest.mark.parametrize("module,kind", [(challenge_15k, ChallengeDataProvider), (shadow, ShadowProvider)])
def test_provider_error_envelope_with_rows_does_not_become_shared_metadata(monkeypatch, module, kind):
    documents = iter([
        {"errors": {"provider": "unavailable"}, "response": payload()},
        {"errors": [], "response": payload()},
    ])
    errors = []
    monkeypatch.setattr(shadow, "errors", errors)

    def get(url, *, params, **_):
        assert url == "https://v3.football.api-sports.io/leagues" and params == {"id": 39, "season": 2026}
        return SimpleNamespace(status_code=200, raise_for_status=lambda: None, json=lambda: next(documents))

    monkeypatch.setattr(module, "api_football_get", get)
    owner = kind("test-key", None)
    assert owner.coverage(39, 2026) == {"injuries": False, "lineups": False}
    assert any("unavailable" in error for error in getattr(owner, "errors", errors))
    assert not cache.CACHE_PATH.exists()
    assert kind("test-key", None).coverage(39, 2026) == {"injuries": False, "lineups": True}
    assert kind("test-key", None).coverage(39, 2026) == {"injuries": False, "lineups": True}
