from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
from threading import Barrier

import pytest


DAY = "2026-11-21"
BASE = "2026-11-21T09:00:00+00:00"
START = "2026-11-21T18:00:00+00:00"


@pytest.fixture
def ledger(monkeypatch):
    import daily_accumulator_receipts
    monkeypatch.setattr(daily_accumulator_receipts, "_now", lambda: datetime.fromisoformat(BASE))
    return daily_accumulator_receipts


def leg(n, **changes):
    return {
        "event_key": f"football:event:{n}", "forecast_id": f"{n:064x}",
        "aliases": [f"football:fixture:{n}"], "participants": [f"home:{n}", f"away:{n}"],
        "sport": "football", "market_key": "match", "selection": "home", "evidence_selection": "1",
        "signal_key": f"S{n}",
        "starts_at": START, "model_version": "v1", "probability": 0.8,
        "event_label": f"Home {n} vs Away {n}", "reason": "home form",
        "offers": {
            book: {"odds": odds, "observed_at": BASE, "fetched_at": BASE}
            for book, odds in [("a", 1.25), ("b", 1.30)]
        },
        **changes,
    }


def slip(legs, *, book="a"):
    return {"size": len(legs), "legs": list(legs), "bookmaker_id": book,
            "price_status": "confirmed" if book else "unconfirmed",
            "reference_probability": 0.8 ** len(legs)}


def test_missing_read_does_not_create_any_path(ledger, tmp_path):
    db = tmp_path / "not-created" / "receipts.sqlite"
    assert ledger.load_day(db, day=DAY) == []
    assert not db.parent.exists()


def test_original_persists_and_future_sizes_see_it(ledger, tmp_path):
    db = tmp_path / "receipts.sqlite"
    first = [leg(i) for i in range(1, 4)]
    other = [leg(i) for i in range(10, 14)]
    original = ledger.capture_day(db, day=DAY, as_of=BASE, pool=first,
                                  select=lambda legs, *, frozen: [slip(legs)])
    assert [x["event_key"] for x in original[0]["legs"]] == [f"football:event:{n}" for n in (1,2,3)]
    assert original[0]["captured_at"] == BASE
    assert original[0]["decision_at"] == BASE
    assert original[0]["legs"][0]["evidence_selection"] == "1"
    assert list(original[0]["legs"][0]["offers"]) == ["a"]

    def choose(pool, *, frozen):
        assert [row["size"] for row in frozen] == [3]
        return [slip(pool[:3]), slip(pool)]

    twice = ledger.capture_day(db, day=DAY, as_of=BASE, pool=other, select=choose)
    assert [s["size"] for s in twice] == [3, 4]
    assert twice[0] == original[0]
    assert list(twice[1]["legs"][0]["offers"]) == ["a"]
    assert twice == ledger.load_day(db, day=DAY)
    assert ledger.load_day(db, day=DAY, arm="candidate") == []


def test_capture_also_checks_wall_clock_after_select(ledger, tmp_path, monkeypatch):
    db = tmp_path / "receipts.sqlite"
    pool = [leg(i) for i in range(3)]
    def late_builder(legs, *, frozen):
        monkeypatch.setattr(ledger, "_now", lambda: datetime.fromisoformat(START))
        return [slip(legs)]
    assert ledger.capture_day(db, day=DAY, as_of=BASE, pool=pool, select=late_builder) == []
    assert ledger.load_day(db, day=DAY) == []


@pytest.mark.parametrize(("day","as_of"), [
    ("2026-11-20","2026-11-20T10:00:00+00:00"),
    (DAY,"2026-11-21T09:01:00+00:00"),  # future snapshot
    (DAY,"2026-11-20T22:59:00+00:00"),  # before Zurich midnight
    (DAY,"2026-11-21T09:00:00"),         # ambiguous local time
])
def test_no_backfill_or_future_and_naive_decisions(ledger, tmp_path, day, as_of):
    db = tmp_path / "receipts.sqlite"
    with pytest.raises(ValueError):
        ledger.capture_day(db, day=day, as_of=as_of, pool=[], select=lambda *a, **kw: [])
    assert not db.exists()


def test_missing_or_changed_evidence_and_partly_started_slips_leave_valid_sizes(ledger,tmp_path):
    pool = [leg(i) for i in range(1,19)]
    del pool[0]["forecast_id"]
    frozen = ledger.capture_day(tmp_path / "slips", day=DAY, as_of=BASE, pool=pool,
        select=lambda legs, *, frozen: [
            slip(legs[:3]), slip([dict(legs[3], probability=0.99), *legs[4:7]]),
            slip([dict(legs[7], starts_at=BASE), *legs[8:12]]), slip(legs[12:18])])
    assert [s["size"] for s in frozen] == [6]


def test_concurrent_first_writers_never_create_two_revisions(ledger,tmp_path):
    db, barrier = tmp_path / "slips", Barrier(2)
    def capture(n):
        pool = [leg(i) for i in range(n,n+3)]
        barrier.wait(timeout=4)
        return ledger.capture_day(db, day=DAY, as_of=BASE, pool=pool,
                                  select=lambda legs, *, frozen: [slip(legs)])
    with ThreadPoolExecutor(max_workers=2) as workers:
        both = list(workers.map(capture, [1, 10]))
    assert both[0] == both[1] == ledger.load_day(db, day=DAY)
    assert len(both[0]) == 1


def test_failed_capture_is_atomic_and_can_retry(ledger, tmp_path):
    db = tmp_path / "slips"
    pool = [leg(i) for i in range(1,4)]
    def crash(legs, *, frozen):
        yield slip(legs)
        raise RuntimeError("interrupted")
    with pytest.raises(RuntimeError, match="interrupted"):
        ledger.capture_day(db, day=DAY, as_of=BASE, pool=pool, select=crash)
    assert ledger.load_day(db, day=DAY) == []
    assert len(ledger.capture_day(db, day=DAY, as_of=BASE, pool=pool,
                                  select=lambda legs, *, frozen: [slip(legs)])) == 1


def test_unpriced_is_research_only_not_reference_and_source_prices_must_match(ledger,tmp_path):
    db = tmp_path / "slips"
    pool = [leg(i) for i in range(1,4)]
    def unpriced(legs, *, frozen):
        return [slip(legs, book=None)]
    assert ledger.capture_day(db, day=DAY, as_of=BASE, pool=pool, select=unpriced) == []
    research, = ledger.capture_day(db, day=DAY, as_of=BASE, arm="model-observation",
                                   pool=pool, select=unpriced)
    assert research["legs"][0]["offers"] == {}
    changed = dict(pool[0], offers={"a": dict(pool[0]["offers"]["a"], odds=4.5)})
    assert ledger.capture_day(db, day=DAY, as_of=BASE, pool=pool,
                              select=lambda legs, *, frozen: [slip([changed,*legs[1:]])]) == []


@pytest.mark.parametrize(("odds","observed","fetched","accepted"), [
    (1.20, "08:15:00", "08:25:00", True),
    (1.19, "08:15:00", "08:25:00", False),
    (1.20, "08:14:59", "08:25:00", False),
    (1.20, "08:15:00", "08:24:59", False),
    (1.20, "08:45:00", "08:44:59", False),
    (1.20, "09:00:01", "09:00:01", False),
])
def test_book_and_clocks_must_still_qualify_at_publication(ledger, tmp_path, odds, observed, fetched, accepted):
    pool = [leg(n) for n in range(3)]
    pool[0]["offers"]["a"] = {"odds": odds, "observed_at": f"{DAY}T{observed}+00:00",
                              "fetched_at": f"{DAY}T{fetched}+00:00"}
    receipts = ledger.capture_day(tmp_path/"slips", day=DAY, as_of=BASE, pool=pool,
                                  select=lambda legs, *, frozen: [slip(legs)])
    assert len(receipts) == int(accepted)


def test_selector_cannot_modify_already_bound_pool_to_manufacture_a_price(ledger,tmp_path):
    pool = [leg(n) for n in range(3)]
    pool[0]["offers"]["a"]["odds"] = 1.10
    def mutate(legs, *, frozen):
        legs[0]["offers"]["a"]["odds"] = 1.45
        return [slip(legs)]
    assert ledger.capture_day(tmp_path/"slips", day=DAY, as_of=BASE, pool=pool, select=mutate) == []
