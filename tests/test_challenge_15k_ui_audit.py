from __future__ import annotations

from datetime import date
import math

import pytest

import challenge_15k


class _Context:
    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, traceback):
        return False


class _FakeStreamlit:
    def __init__(
        self,
        *,
        selected_result: str,
        number_inputs: dict[str, float],
        text_inputs: dict[str, str] | None = None,
        confirmed: bool = True,
    ):
        self.selected_result = selected_result
        self.number_inputs = number_inputs
        self.text_inputs = text_inputs or {}
        self.confirmed = confirmed
        self.session_state: dict[str, str] = {}
        self.warnings: list[str] = []
        self.reruns: list[dict[str, str]] = []

    def form(self, *_args, **_kwargs):
        return _Context()

    def container(self, *_args, **_kwargs):
        return _Context()

    def columns(self, count, *_args, **_kwargs):
        return [self for _ in range(count)]

    def date_input(self, *_args, **_kwargs):
        return date(2026, 8, 24)

    def text_input(self, label, *_args, **_kwargs):
        return self.text_inputs.get(label, "")

    def number_input(self, label, *_args, **_kwargs):
        return self.number_inputs[label]

    def selectbox(self, *_args, **_kwargs):
        return self.selected_result

    def checkbox(self, *_args, **_kwargs):
        return self.confirmed

    def form_submit_button(self, *_args, **_kwargs):
        return True

    def button(self, *_args, **_kwargs):
        return True

    def caption(self, *_args, **_kwargs):
        return None

    def subheader(self, *_args, **_kwargs):
        return None

    def markdown(self, *_args, **_kwargs):
        return None

    def warning(self, message, *_args, **_kwargs):
        self.warnings.append(str(message))

    def rerun(self, **kwargs):
        self.reruns.append(kwargs)


class _HistoricalLedger:
    def __init__(self):
        self.recorded = None

    def settings(self):
        return {
            "current_balance": 100.0,
            "starting_balance": 100.0,
            "target_balance": 15_000.0,
            "stake_fraction": 0.05,
        }

    def pending_tickets(self):
        return []

    def record_manual_result(self, *args, **kwargs):
        self.recorded = (args, kwargs)
        return 17


class _PendingLedger:
    def __init__(self):
        self.settled = None

    def pending_tickets(self):
        return [
            {
                "id": 4,
                "analysis_date": "2026-08-24",
                "stake": 5.0,
                "total_odds": 2.25,
                "legs": [
                    {
                        "match": "A vs B",
                        "market": "Beide Teams treffen",
                        "selection": "Ja",
                    },
                    {
                        "match": "C vs D",
                        "market": "Über/Unter",
                        "selection": "Über 2,5",
                    },
                ],
            }
        ]

    def settle_ticket(self, *args, **kwargs):
        self.settled = (args, kwargs)
        return {"id": 4}

    def settings(self):
        return {"current_balance": 102.5}


def test_challenge_times_are_always_rendered_in_europe_zurich():
    winter = challenge_15k._zurich_datetime("2026-01-15T12:00:00+00:00")
    summer = challenge_15k._zurich_datetime("2026-07-15T12:00:00Z")
    legacy_naive = challenge_15k._zurich_datetime("2026-01-15T12:00:00")

    assert winter is not None and winter.tzinfo.key == "Europe/Zurich"
    assert summer is not None and summer.tzinfo.key == "Europe/Zurich"
    assert challenge_15k._format_time(winter) == "15.01.2026 13:00"
    assert challenge_15k._format_time(summer) == "15.07.2026 14:00"
    assert challenge_15k._format_time(legacy_naive) == "15.01.2026 13:00"
    assert challenge_15k._format_kickoff("2026-07-15T12:00:00Z") == "15.07. 14:00"
    assert challenge_15k._format_time(None) == "n/a"
    assert challenge_15k._format_time("kaputt") == "kaputt"


@pytest.mark.parametrize(
    ("label", "payout", "expected"),
    [
        ("Gewonnen", 12.34, ("WON", 12.34)),
        ("Verloren", math.nan, ("LOST", None)),
        ("Storniert", 999.0, ("VOID", None)),
    ],
)
def test_manual_history_result_keeps_actual_credit_only_for_wins(
    label,
    payout,
    expected,
):
    assert challenge_15k._manual_history_result(label, payout) == expected


@pytest.mark.parametrize("payout", [None, 0, -1, math.nan, math.inf, True])
def test_manual_history_win_requires_a_real_positive_credit(payout):
    with pytest.raises(ValueError, match="tatsächliche Gutschrift"):
        challenge_15k._manual_history_result("Gewonnen", payout)


def test_first_manual_settlement_reason_is_normalized_and_has_a_safe_default():
    assert challenge_15k._manual_settlement_reason("  Leg 2   storniert  ") == (
        "Leg 2 storniert"
    )
    assert challenge_15k._manual_settlement_reason("") == (
        challenge_15k.DEFAULT_MANUAL_SETTLEMENT_REASON
    )
    with pytest.raises(ValueError, match="500 Zeichen"):
        challenge_15k._manual_settlement_reason("x" * 501)


def test_historical_win_ui_passes_the_actual_bookmaker_credit(monkeypatch):
    fake_st = _FakeStreamlit(
        selected_result="Gewonnen",
        number_inputs={
            "Tatsächlicher Einsatz": 5.0,
            "Tatsächliche Gesamtquote": 2.0,
            "Tatsächliche Buchmacher-Gutschrift bei Gewinn": 10.0,
        },
        text_inputs={"Gespielte Wette": "A vs B: Beide Teams treffen"},
    )
    ledger = _HistoricalLedger()
    monkeypatch.setattr(challenge_15k, "st", fake_st)

    challenge_15k._render_manual_result_dialog.__wrapped__(ledger)

    assert ledger.recorded is not None
    args, kwargs = ledger.recorded
    assert args == (
        "2026-08-24",
        "A vs B: Beide Teams treffen",
        5.0,
        2.0,
        "WON",
    )
    assert kwargs == {"actual_payout": 10.0}
    assert fake_st.reruns == [{"scope": "app"}]


def test_first_manual_settlement_persists_optional_leg_status(monkeypatch):
    fake_st = _FakeStreamlit(
        selected_result="Gewonnen",
        number_inputs={
            "Tatsächliche Auszahlungsquote": 1.50,
            "Tatsächliche Buchmacher-Gutschrift": 7.50,
        },
        text_inputs={
            "Abrechnungsgrund / Legstatus (optional)": (
                "  Auswahl 2 storniert;   Auswahl 1 gewonnen  "
            )
        },
    )
    ledger = _PendingLedger()
    monkeypatch.setattr(challenge_15k, "st", fake_st)

    assert challenge_15k._render_pending_ticket_actions(
        ledger,
        key_prefix="audit",
    )

    assert ledger.settled is not None
    args, kwargs = ledger.settled
    assert args == (4, "WON")
    assert kwargs["settlement_odds"] == 1.50
    assert kwargs["actual_payout"] == 7.50
    assert kwargs["source"] == "MANUAL_CONFIRMED"
    assert kwargs["reason"] == "Auswahl 2 storniert; Auswahl 1 gewonnen"
