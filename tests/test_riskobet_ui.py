from __future__ import annotations

from contextlib import AbstractContextManager
from dataclasses import replace
from datetime import datetime, timedelta, timezone
import hashlib
import re

import pytest

import riskobet_ui as ui
from riskobet_domain import (
    ContextState,
    EventModelSnapshot,
    EvidenceStage,
    FactorEvidence,
    FactorRole,
    RiskCandidate,
)
from riskobet_surface import SPORT_FILTERS, build_riskobet_card


START = datetime(2030, 1, 2, 18, 0, tzinfo=timezone.utc)
MODELED = START - timedelta(hours=2)


class _Context(AbstractContextManager):
    def __init__(self, streamlit, kind, key):
        self.streamlit = streamlit
        self.kind = kind
        self.key = key

    def __enter__(self):
        self.streamlit.context_stack.append((self.kind, self.key))
        return self.streamlit

    def __exit__(self, *_args):
        assert self.streamlit.context_stack.pop() == (self.kind, self.key)
        return False


class RecordingStreamlit:
    def __init__(self, *, session_state=None, widget_values=None):
        self.session_state = dict(session_state or {})
        self.widget_values = dict(widget_values or {})
        self.context_stack = []
        self.containers = []
        self.column_groups = []
        self.expanders = []
        self.popovers = []
        self.segmented_controls = []
        self.text_inputs = []
        self.messages = []
        self.markdown_calls = []
        self.event_log = []

    def container(self, *, key=None, **_kwargs):
        self.containers.append(key)
        return _Context(self, "container", key)

    def columns(self, spec, **_kwargs):
        count = spec if isinstance(spec, int) else len(spec)
        group = tuple(f"column-{len(self.column_groups)}-{i}" for i in range(count))
        self.column_groups.append((spec, group))
        return tuple(_Context(self, "column", key) for key in group)

    def expander(self, label, *, expanded=False, key=None, **_kwargs):
        self.expanders.append((label, expanded, key))
        self.event_log.append(("expander", key))
        return _Context(self, "expander", key)

    def popover(self, label, **_kwargs):
        self.popovers.append(label)
        self.event_log.append(("popover", label))
        return _Context(self, "popover", label)

    def segmented_control(self, label, options, *, default=None, key=None, **_kwargs):
        options = tuple(options)
        self.segmented_controls.append((label, options, default, key))
        return self.widget_values.get(key, default)

    def text_input(self, label, *, key=None, **_kwargs):
        self.text_inputs.append((label, key))
        return self.widget_values.get(key, self.session_state.get(key, ""))

    def _message(self, kind, value):
        self.messages.append((kind, value, tuple(self.context_stack)))
        self.event_log.append((kind, value))

    def caption(self, value, **_kwargs):
        self._message("caption", value)

    def error(self, value, **_kwargs):
        self._message("error", value)

    def info(self, value, **_kwargs):
        self._message("info", value)

    def warning(self, value, **_kwargs):
        self._message("warning", value)

    def subheader(self, value, **_kwargs):
        self._message("subheader", value)

    def write(self, value, **_kwargs):
        self._message("write", value)

    def markdown(self, value, **kwargs):
        self.markdown_calls.append((value, kwargs, tuple(self.context_stack)))
        self._message("markdown", value)


def _bundle(
    key: str,
    *,
    sport: str = "football",
    stage: EvidenceStage = EvidenceStage.SHADOW,
    model_probability: float | None = 0.36,
    cautious_probability: float | None = 0.30,
    market_key: str = "underdog_win",
) -> tuple[EventModelSnapshot, RiskCandidate]:
    missing = ("Belastbare aktuelle Kerndaten",) if model_probability is None else ()
    factor = FactorEvidence(
        factor_key=f"form-{key}",
        summary=f"Formfaktor für {key}",
        source="internal-provider-secret",
        observed_at=MODELED - timedelta(hours=1),
        imported_at=MODELED,
        fresh_until=START,
        coverage=0.8,
        sample_size=20,
        role=FactorRole.MODEL,
    )
    snapshot = EventModelSnapshot(
        event_key=f"event-{key}",
        sport=sport,
        competition=f"Liga {key}",
        event_label=f"Außenseiter {key} vs Favorit {key}",
        starts_at=START,
        modeled_at=MODELED,
        input_cutoff_at=MODELED - timedelta(minutes=5),
        model_version="risk-model-v1",
        input_hash=hashlib.sha256(key.encode("utf-8")).hexdigest(),
        factors=(factor,),
        missing_core_data=missing,
    )
    candidate = RiskCandidate(
        snapshot_id=snapshot.snapshot_id,
        event_key=snapshot.event_key,
        sport=snapshot.sport,
        competition=snapshot.competition,
        event_label=snapshot.event_label,
        starts_at=snapshot.starts_at,
        market_key=market_key,
        market_label="Außenseitersieg",
        selection_key=f"selection-{key}",
        selection_label=f"Sieg Außenseiter {key}",
        model_probability=model_probability,
        cautious_probability=cautious_probability,
        stage=stage,
        context_state=(
            ContextState.OPEN
            if model_probability is None
            else ContextState.FRESH
        ),
        policy_version="risk-policy-v1",
        pros=(f"Positiver Matchup-Faktor {key}",),
        cons=(f"Favorit bleibt stärker {key}",),
        missing_core_data=missing,
        settlement_contract=(
            None if stage is EvidenceStage.RESEARCH else "match-winner-v1"
        ),
    )
    return snapshot, candidate


def _payload(*bundles, status="COMPLETE", errors=()):
    return {
        "schema_version": 1,
        "run_id": "run_" + ("b" * 64),
        "started_at": (MODELED - timedelta(minutes=1)).isoformat(),
        "completed_at": MODELED.isoformat(),
        "status": status,
        "snapshots": [snapshot.to_dict() for snapshot, _candidate in bundles],
        "candidates": [
            {
                **candidate.to_dict(),
                "featured": False,
                "stage_history": [],
                "settlements": [],
            }
            for _snapshot, candidate in bundles
        ],
        "errors": list(errors),
    }


def _view(*bundles, status="COMPLETE") -> ui.RiskBetView:
    snapshots = {snapshot.snapshot_id: snapshot for snapshot, _ in bundles}
    candidates = tuple(candidate for _, candidate in bundles)
    return ui.RiskBetView(
        run_id="run_" + ("c" * 64),
        status=status,
        started_at=MODELED - timedelta(minutes=1),
        completed_at=MODELED,
        candidates=candidates,
        cards=tuple(build_riskobet_card(candidate) for candidate in candidates),
        snapshots=snapshots,
    )


def _all_text(fake: RecordingStreamlit) -> str:
    return "\n".join(str(value) for _kind, value, _context in fake.messages)


def _rendered_candidate_ids(fake: RecordingStreamlit) -> list[str]:
    result = []
    for markup, _kwargs, _context in fake.markdown_calls:
        match = re.search(r'data-key="([^"]+)"', markup)
        if match:
            result.append(match.group(1))
    return result


def test_load_uses_read_latest_without_initialising_db_or_provider(monkeypatch, tmp_path):
    bundle = _bundle("load")
    expected_payload = _payload(bundle)
    seen = []

    monkeypatch.setattr(
        ui.RiskBetStore,
        "__init__",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(
            AssertionError("read-only page must not initialise SQLite")
        ),
    )
    monkeypatch.setattr(
        ui.RiskBetStore,
        "read_latest",
        lambda self: seen.append(self.latest_path) or expected_payload,
    )

    path = tmp_path / "latest.json"
    view = ui.load_riskobet_view(path)

    assert view is not None
    assert seen == [path]
    assert isinstance(view.candidates[0], RiskCandidate)
    assert "requests" not in ui.__dict__


def test_default_load_recovers_from_backed_up_database_without_initialising_store(
    monkeypatch,
):
    bundle = _bundle("recovery")
    expected_payload = _payload(bundle)
    seen = []
    monkeypatch.setattr(
        ui.RiskBetStore,
        "__init__",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(
            AssertionError("consumer recovery must stay read-only")
        ),
    )
    monkeypatch.setattr(ui.RiskBetStore, "read_latest", lambda _self: None)
    monkeypatch.setattr(
        ui.RiskBetStore,
        "recover_latest_from_database",
        lambda path: seen.append(path) or expected_payload,
    )

    view = ui.load_riskobet_view()

    assert view is not None
    assert seen == [ui.DEFAULT_DB_PATH]
    assert view.candidates[0].event_key == bundle[1].event_key


def test_hydration_rejects_unknown_or_forged_candidate_content(monkeypatch):
    bundle = _bundle("strict")
    unknown = _payload(bundle)
    unknown["candidates"][0]["provider_debug"] = "secret"
    monkeypatch.setattr(ui.RiskBetStore, "read_latest", lambda _self: unknown)

    with pytest.raises(ui.RiskBetViewError, match="schema version"):
        ui.load_riskobet_view()

    forged = _payload(bundle)
    forged["candidates"][0]["candidate_id"] = "candidate_" + ("0" * 64)
    monkeypatch.setattr(ui.RiskBetStore, "read_latest", lambda _self: forged)
    with pytest.raises(ui.RiskBetViewError, match="identity mismatch"):
        ui.load_riskobet_view()


def test_partial_summary_is_safe_and_never_exposes_internal_errors(monkeypatch):
    bundle = _bundle("partial")
    payload = _payload(
        bundle,
        status="PARTIAL",
        errors=("provider API token=secret failed in league 999",),
    )
    monkeypatch.setattr(ui.RiskBetStore, "read_latest", lambda _self: payload)
    view = ui.load_riskobet_view()
    fake = RecordingStreamlit()
    monkeypatch.setattr(ui, "st", fake)
    monkeypatch.setattr(ui, "load_riskobet_view", lambda _path=None: view)

    ui.render_riskobet()

    text = _all_text(fake)
    assert "nicht vollständig aktualisiert" in text
    assert "bereits verarbeitete Daten" in text
    assert "Evidenzstand beachten" in text
    assert "erfolgreich geprüft" not in text
    assert "provider" not in text.casefold()
    assert "token=secret" not in text
    assert "league 999" not in text
    assert "riskobet_summary" in fake.containers


def test_empty_view_has_filter_and_message_but_no_empty_section_heading(monkeypatch):
    view = _view()
    fake = RecordingStreamlit()
    monkeypatch.setattr(ui, "st", fake)
    monkeypatch.setattr(ui, "load_riskobet_view", lambda _path=None: view)

    ui.render_riskobet()

    assert fake.segmented_controls == [
        ("Sport", SPORT_FILTERS, "Alle", "riskobet-sport-filter")
    ]
    assert not [item for item in fake.messages if item[0] == "subheader"]
    assert "keine Szenarien verfügbar" in _all_text(fake)


def test_summary_uses_singular_for_one_scenario_and_one_event(monkeypatch):
    view = _view(_bundle("single"))
    fake = RecordingStreamlit()
    monkeypatch.setattr(ui, "st", fake)
    monkeypatch.setattr(ui, "load_riskobet_view", lambda _path=None: view)

    ui.render_riskobet()

    assert "1 Szenario aus 1 Event · Stand:" in _all_text(fake)
    assert "1 Szenarien aus 1 Events" not in _all_text(fake)


def test_corrupt_view_shows_only_consumer_safe_error(monkeypatch):
    fake = RecordingStreamlit()
    monkeypatch.setattr(ui, "st", fake)
    monkeypatch.setattr(
        ui,
        "load_riskobet_view",
        lambda _path=None: (_ for _ in ()).throw(
            ValueError("API-Football provider token super-secret")
        ),
    )

    ui.render_riskobet()

    text = _all_text(fake)
    assert "nicht sicher angezeigt" in text
    assert "API-Football" not in text
    assert "super-secret" not in text
    assert not fake.segmented_controls


def test_real_latest_integrity_error_is_caught_without_a_streamlit_trace(
    monkeypatch,
    tmp_path,
):
    latest = tmp_path / "riskobet_latest.json"
    latest.write_text('{"schema_version":1}\n', encoding="utf-8")
    fake = RecordingStreamlit()
    monkeypatch.setattr(ui, "st", fake)

    ui.render_riskobet(latest)

    assert "nicht sicher angezeigt" in _all_text(fake)
    assert len([item for item in fake.messages if item[0] == "error"]) == 1


def test_featured_grid_flat_rows_and_exact_stable_keys(monkeypatch):
    bundles = (
        _bundle("football", sport="football"),
        _bundle("tennis", sport="tennis"),
        _bundle("basketball", sport="basketball"),
        _bundle("esports", sport="esports"),
    )
    view = _view(*bundles)
    monkeypatch.setattr(ui, "load_riskobet_view", lambda _path=None: view)

    first = RecordingStreamlit()
    monkeypatch.setattr(ui, "st", first)
    ui.render_riskobet()
    second = RecordingStreamlit()
    monkeypatch.setattr(ui, "st", second)
    ui.render_riskobet()

    assert first.column_groups[0][0] == 2
    assert len(first.column_groups) == 2
    assert "riskobet_page" in first.containers
    assert "riskobet_filters" in first.containers
    assert "riskobet_featured_grid" in first.containers
    assert "riskobet_additional" in first.containers
    assert {
        "riskobet_featured_card_0",
        "riskobet_featured_card_1",
        "riskobet_featured_card_2",
        "riskobet_additional_row_0",
    }.issubset(first.containers)
    assert len(first.expanders) == len(bundles)
    assert len({key for _label, _expanded, key in first.expanders}) == len(bundles)
    assert first.expanders == second.expanders
    assert all(key for _label, _expanded, key in first.expanders)
    assert all(label == "Analyse anzeigen" for label, _expanded, _key in first.expanders)
    assert all(not expanded for _label, expanded, _key in first.expanders)
    assert first.popovers == ["Eigene Quote prüfen"] * len(bundles)
    assert first.popovers == second.popovers
    price_containers = [
        key
        for key in first.containers
        if str(key).startswith("riskobet_price_action_")
    ]
    assert len(price_containers) == len(bundles)
    action_order = [
        kind for kind, _value in first.event_log if kind in {"expander", "popover"}
    ]
    assert action_order == ["expander", "popover"] * len(bundles)
    quote_captions = [
        context
        for kind, value, context in first.messages
        if kind == "caption" and "eigene Quote" in str(value)
    ]
    assert len(quote_captions) == len(bundles)
    assert all(
        any(kind == "popover" for kind, _key in context)
        and not any(kind == "expander" for kind, _key in context)
        for context in quote_captions
    )

    first_markup_position = next(
        index for index, event in enumerate(first.event_log) if event[0] == "markdown"
    )
    first_expander_position = next(
        index for index, event in enumerate(first.event_log) if event[0] == "expander"
    )
    assert first_markup_position < first_expander_position
    assert "internal-provider-secret" not in _all_text(first)
    assert "Formfaktor für football" in _all_text(first)
    assert _rendered_candidate_ids(first) == [
        candidate.candidate_id for candidate in view.candidates
    ]
    assert "## Top-Szenarien" in _all_text(first)
    assert "## Weitere Szenarien" in _all_text(first)


def test_public_factor_details_hide_frozen_source_identities(monkeypatch):
    base, _candidate_value = _bundle("identity", sport="esports")
    identity_factors = tuple(
        FactorEvidence(
            factor_key=key,
            summary=summary,
            source="esports_shadow_predictions",
            observed_at=MODELED - timedelta(hours=1),
            imported_at=MODELED,
            fresh_until=START,
            role=FactorRole.DISPLAY_ONLY,
        )
        for key, summary in (
            ("esports_match_id:55", "Eingefrorene PandaScore-Match-ID: 55."),
            ("esports_team1_id:7", "Eingefrorene PandaScore-Team-ID: 7."),
        )
    )
    snapshot = EventModelSnapshot(
        event_key=base.event_key,
        sport=base.sport,
        competition=base.competition,
        event_label=base.event_label,
        starts_at=base.starts_at,
        modeled_at=base.modeled_at,
        input_cutoff_at=base.input_cutoff_at,
        model_version=base.model_version,
        input_hash=base.input_hash,
        factors=base.factors + identity_factors,
    )
    fake = RecordingStreamlit()
    monkeypatch.setattr(ui, "st", fake)

    ui._render_factor_details(snapshot)

    text = _all_text(fake)
    assert "Formfaktor für identity" in text
    assert "Quellzeile" not in text
    assert "PandaScore" not in text
    assert "Team-ID" not in text
    assert "Match-ID" not in text


def test_production_like_payload_hides_internal_stage_and_factor_status(
    monkeypatch,
):
    base_snapshot, base_candidate = _bundle("production-context")
    raw_factor = FactorEvidence(
        factor_key="football_context_0_weather",
        summary="Wetter: passed",
        source="api-football-context",
        observed_at=MODELED - timedelta(minutes=20),
        imported_at=MODELED,
        fresh_until=START,
        role=FactorRole.MODEL,
    )
    snapshot = replace(base_snapshot, factors=(raw_factor,))
    candidate = replace(
        base_candidate,
        snapshot_id=snapshot.snapshot_id,
        pros=("Wetter: passed",),
        cons=("Aufstellungen: required_missing",),
    )
    payload = _payload((snapshot, candidate))
    monkeypatch.setattr(ui.RiskBetStore, "read_latest", lambda _self: payload)
    view = ui.load_riskobet_view()
    fake = RecordingStreamlit()
    monkeypatch.setattr(ui, "st", fake)
    monkeypatch.setattr(ui, "load_riskobet_view", lambda _path=None: view)

    ui.render_riskobet()

    text = _all_text(fake)
    assert "Im Test · noch nicht historisch bestätigt" in text
    assert "Wetter: geprüft" in text
    assert "Aufstellungen: noch nicht bestätigt" in text
    for internal in ("Shadow", "passed", "required_missing"):
        assert internal not in text


def test_manual_quotes_do_not_change_visibility_or_model_order(monkeypatch):
    bundles = (
        _bundle("football-one", sport="football"),
        _bundle("football-two", sport="football"),
        _bundle("tennis-one", sport="tennis"),
        _bundle("basketball-one", sport="basketball"),
    )
    view = _view(*bundles)
    monkeypatch.setattr(ui, "load_riskobet_view", lambda _path=None: view)

    plain = RecordingStreamlit()
    monkeypatch.setattr(ui, "st", plain)
    ui.render_riskobet()

    quote_state = {}
    for index, candidate in enumerate(view.candidates):
        quote_state[
            f"riskobet-quote-{ui._widget_suffix(candidate)}"
        ] = (1.10, 25.0, 2.0, 8.0)[index]
    repriced = RecordingStreamlit(session_state=quote_state)
    monkeypatch.setattr(ui, "st", repriced)
    ui.render_riskobet()

    assert _rendered_candidate_ids(plain) == _rendered_candidate_ids(repriced)
    assert len(_rendered_candidate_ids(repriced)) == len(bundles)
    assert "Quote beobachtet" in _all_text(repriced)


@pytest.mark.parametrize(
    ("probability", "stage", "expected"),
    (
        (0.36, EvidenceStage.SHADOW, "Implizite Quotechance: 25.0 %"),
        (None, EvidenceStage.RESEARCH, "ehrlich nicht möglich"),
    ),
)
def test_manual_quote_is_only_probability_comparison(
    monkeypatch,
    probability,
    stage,
    expected,
):
    bundle = _bundle(
        "quote",
        stage=stage,
        model_probability=probability,
        cautious_probability=None if probability is None else 0.30,
    )
    view = _view(bundle)
    candidate = view.candidates[0]
    quote_key = f"riskobet-quote-{ui._widget_suffix(candidate)}"
    fake = RecordingStreamlit(session_state={quote_key: "4,00"})
    monkeypatch.setattr(ui, "st", fake)
    monkeypatch.setattr(ui, "load_riskobet_view", lambda _path=None: view)

    ui.render_riskobet()

    text = _all_text(fake)
    assert expected in text
    assert "Mindestquote" not in text
    assert "gesperrt" not in text.casefold()
    assert "Quote beobachtet" in text
    assert "4.00" in text


def test_filter_options_are_exact_and_filtering_does_not_load_again(monkeypatch):
    view = _view(
        _bundle("football-filter", sport="football"),
        _bundle("tennis-filter", sport="tennis"),
    )
    calls = []
    fake = RecordingStreamlit(
        widget_values={"riskobet-sport-filter": "Tennis"}
    )
    monkeypatch.setattr(ui, "st", fake)
    monkeypatch.setattr(
        ui,
        "load_riskobet_view",
        lambda _path=None: calls.append("read") or view,
    )

    ui.render_riskobet()

    assert calls == ["read"]
    assert fake.segmented_controls[0][1] == SPORT_FILTERS
    markup = "\n".join(item[0] for item in fake.markdown_calls)
    assert "Außenseiter tennis-filter" in markup
    assert "Außenseiter football-filter" not in markup
