"""Reader regressions for naturally expired automated Wettfinder rows."""

from __future__ import annotations

import json
from datetime import datetime, timezone

from ev_signal_sources import (
    _load_automated_wettfinder_document,
    automated_wettfinder_snapshot,
)
from test_ev_signal_sources import (
    _automatic_document,
    _model_overlay,
    _playable_automatic_candidate,
)


GENERATED = "2030-01-01T10:00:00+00:00"
CURRENT = datetime(2030, 1, 1, 10, 30, tzinfo=timezone.utc)


def _strict_row(index: int, scheduled_start: str) -> dict:
    row = _playable_automatic_candidate(
        generated_at=GENERATED,
        scheduled_start=scheduled_start,
    )
    candidate_id = f"{index}:BTTS_YES"
    row.update(
        candidate_id=candidate_id,
        fixture_id=index,
        key=f"football-auto-{index}",
        label=f"Fußball - Spiel {index} - Beide treffen: Ja",
        event=f"Spiel {index}",
    )
    row["reference_quote"]["candidate_id"] = candidate_id
    row["reference_quote"]["fixture_id"] = index
    return row


def _write_document(path, rows: list[dict]) -> dict:
    document = _automatic_document(
        [_model_overlay(row) for row in rows],
        candidates=rows,
        challenge_release_candidates=rows,
    )
    document["football"]["approved_candidates"] = len(rows)
    document["sources"]["football"].update(
        price_checked_count=len(rows),
        reference_quote_count=len(rows),
        price_status_counts={"PLAYABLE": len(rows)},
    )
    path.write_text(json.dumps(document), encoding="utf-8")
    return document


def test_reader_projects_one_naturally_expired_row_from_all_live_arrays(
    tmp_path,
):
    expired = _strict_row(1, "2030-01-01T10:15:00+00:00")
    active = _strict_row(2, "2030-01-01T15:00:00+00:00")
    artifact = tmp_path / "wettfinder.json"
    persisted = _write_document(artifact, [expired, active])

    loaded = _load_automated_wettfinder_document(artifact, now=CURRENT)

    assert loaded is not None
    document, generated, candidates = loaded
    assert generated.isoformat() == GENERATED
    assert [row["key"] for row in document["model_candidates"]] == [
        active["key"]
    ]
    assert [row["key"] for row in document["candidates"]] == [active["key"]]
    assert [row["key"] for row in document["challenge_release_candidates"]] == [
        active["key"]
    ]
    assert [row["key"] for row in candidates] == [active["key"]]
    assert document["model_candidates"][0]["probability"] == active["probability"]
    assert (
        document["model_candidates"][0]["reference_quote"]["quoted_at"]
        == GENERATED
    )
    assert document["football"]["approved_candidates"] == 2
    assert document["sources"]["football"]["price_checked_count"] == 2
    assert json.loads(artifact.read_text(encoding="utf-8")) == persisted

    snapshot = automated_wettfinder_snapshot(artifact, now=CURRENT)

    assert snapshot.status is not None
    assert snapshot.status.candidate_count == 1
    assert snapshot.status.model_candidate_count == 1
    assert snapshot.status.approved_candidates == 2
    assert snapshot.status.price_checked_count == 2
    assert [row.key for row in snapshot.forecasts] == [active["key"]]
    assert [row.key for row in snapshot.signals] == [active["key"]]


def test_reader_validates_corrupt_expired_row_before_live_projection(tmp_path):
    expired = _strict_row(1, "2030-01-01T10:15:00+00:00")
    expired["reference_quote"]["candidate_id"] = "tampered:BTTS_YES"
    active = _strict_row(2, "2030-01-01T15:00:00+00:00")
    artifact = tmp_path / "wettfinder.json"
    _write_document(artifact, [expired, active])

    assert _load_automated_wettfinder_document(artifact, now=CURRENT) is None
    assert automated_wettfinder_snapshot(artifact, now=CURRENT).status is None


def test_reader_rejects_row_already_started_when_document_was_generated(tmp_path):
    invalid = _strict_row(1, "2030-01-01T09:59:00+00:00")
    active = _strict_row(2, "2030-01-01T15:00:00+00:00")
    artifact = tmp_path / "wettfinder.json"
    _write_document(artifact, [invalid, active])

    assert _load_automated_wettfinder_document(artifact, now=CURRENT) is None


def test_reader_rejects_future_row_outside_chosen_search_day(tmp_path):
    wrong_day = _strict_row(1, "2030-01-02T09:00:00+00:00")
    artifact = tmp_path / "wettfinder.json"
    _write_document(artifact, [wrong_day])

    assert _load_automated_wettfinder_document(artifact, now=CURRENT) is None
