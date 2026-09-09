"""Reference type integrity precedes model/price comparison; quotes remain overlays."""
from copy import deepcopy
from datetime import timedelta
import json

import pytest

from context_links import ContextReference
from ev_signal_sources import (
    _load_automated_wettfinder_document, automated_wettfinder_forecasts,
    automated_wettfinder_signals, automated_wettfinder_snapshot,
)
from test_ev_signal_sources import (
    _automatic_document, _model_automatic_candidate, _model_overlay,
    _playable_automatic_candidate,
)
from test_riskobet_store import NOW


COLLECTIONS = ("model_candidates", "candidates", "challenge_release_candidates")


def _reference():
    return ContextReference("a" * 64, "b" * 64).to_dict()


def _document():
    strict = _playable_automatic_candidate()
    strict["context_ref"] = _reference()
    # The actual serialization boundary must remove fixture-only aliases.
    return json.loads(json.dumps(_automatic_document([_model_overlay(strict)], candidates=[strict])))


def _save(tmp_path, document):
    path = tmp_path / "normal.json"
    path.write_text(json.dumps(document), encoding="utf-8")
    return path


@pytest.mark.parametrize("collection", [*COLLECTIONS, "all"])
@pytest.mark.parametrize("schema", [True, 1.0])
def test_bool_or_float_reference_schema_cannot_alias_integer_version(tmp_path, collection, schema):
    document = _document()
    altered = COLLECTIONS if collection == "all" else (collection,)
    for name in altered:
        document[name][0]["context_ref"]["schema"] = schema
        assert type(document[name][0]["context_ref"]["schema"]) is type(schema)
    for name in set(COLLECTIONS) - set(altered):
        assert type(document[name][0]["context_ref"]["schema"]) is int
    path = _save(tmp_path, document)
    assert _load_automated_wettfinder_document(path, now=NOW) is None
    view = automated_wettfinder_snapshot(path, now=NOW)
    assert view.forecasts == () and view.signals == () and view.status is None


@pytest.mark.parametrize("collection", COLLECTIONS)
@pytest.mark.parametrize("invalid", [None, True, [], {}, {**_reference(), "kind": "unknown"},
    {**_reference(), "schema": "1"}, {**_reference(), "key": None},
    {**_reference(), "payload_digest": "A" * 64}, {**_reference(), "verified": True}])
def test_every_present_reference_is_closed_before_document_acceptance(tmp_path, collection, invalid):
    document = _document()
    document[collection][0]["context_ref"] = deepcopy(invalid)
    path = _save(tmp_path, document)
    assert _load_automated_wettfinder_document(path, now=NOW) is None


@pytest.mark.parametrize("collection", COLLECTIONS)
@pytest.mark.parametrize("field", ["key", "payload_digest"])
def test_other_valid_reference_is_still_not_the_same_model_revision(tmp_path, collection, field):
    document = _document()
    document[collection][0]["context_ref"][field] = "c" * 64
    path = _save(tmp_path, document)
    assert _load_automated_wettfinder_document(path, now=NOW) is None


@pytest.mark.parametrize("linked", [False, True])
@pytest.mark.parametrize("price", ["unavailable", "below_minimum", "playable"])
def test_valid_legacy_and_linked_models_remain_visible_independently_of_price(tmp_path, linked, price, monkeypatch):
    if price == "unavailable":
        model = _model_automatic_candidate()
        strict = None
    elif price == "below_minimum":
        observed = _playable_automatic_candidate(odds=("1.20", "1.21", "1.22", "1.23"))
        assert observed["reference_price_status"] != "PLAYABLE"
        model, strict = _model_overlay(observed), None
    else:
        strict = _playable_automatic_candidate()
        model = _model_overlay(strict)
    if linked:
        model["context_ref"] = _reference()
        if strict is not None:
            strict["context_ref"] = _reference()
    original_model = deepcopy(model)
    document = _automatic_document([model], candidates=[strict] if strict else [])
    path = _save(tmp_path, document)
    original_bytes = path.read_bytes()
    def forbidden(*_args, **_kwargs):
        pytest.fail("Reading a saved model or quote must not request new data")
    monkeypatch.setattr("requests.sessions.Session.request", forbidden)
    loaded = _load_automated_wettfinder_document(path, now=NOW)
    assert loaded is not None
    assert loaded[0]["model_candidates"][0] == original_model
    forecasts = automated_wettfinder_forecasts(path, now=NOW)
    assert len(forecasts) == 1 and forecasts[0].probability == .6
    assert forecasts[0].context_ref == (ContextReference.from_dict(_reference()) if linked else None)
    assert len(automated_wettfinder_signals(path, now=NOW)) == int(price == "playable")
    if not linked:
        assert "context_ref" not in loaded[0]["model_candidates"][0]
    assert path.read_bytes() == original_bytes


@pytest.mark.parametrize("linked", [False, True])
def test_price_expiry_does_not_reject_healthy_reference_or_old_document(tmp_path, linked):
    row = _playable_automatic_candidate()
    if linked:
        row["context_ref"] = _reference()
    path = _save(tmp_path, _automatic_document([_model_overlay(row)], candidates=[row]))
    stale_quote_time = NOW + timedelta(minutes=91)
    forecasts = automated_wettfinder_forecasts(path, now=stale_quote_time)
    assert len(forecasts) == 1 and forecasts[0].probability == .6
    assert automated_wettfinder_signals(path, now=stale_quote_time) == []


def test_invalid_later_model_row_cannot_be_hidden_behind_first_valid_row(tmp_path):
    first = _model_automatic_candidate()
    second = deepcopy(first)
    second.update(key="different-model", candidate_id="2:BTTS_YES", fixture_id=2)
    second["context_ref"] = {**_reference(), "schema": True}
    path = _save(tmp_path, _automatic_document([first, second]))
    assert _load_automated_wettfinder_document(path, now=NOW) is None
