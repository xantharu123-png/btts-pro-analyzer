"""Exact quote products must not depend on leg enumeration order."""
from dataclasses import replace
from datetime import datetime, timezone
from itertools import permutations

import pytest

from challenge_engine import select_quoted_ticket, ticket_stake
from challenge_store import ChallengeLedger
from tests.test_challenge_integrity import _candidate


def candidates(now):
    return [replace(_candidate(now, probability=.88),
                    candidate_id=f"{i}:BTTS", fixture_id=i,
                    home_team_id=10*i, away_team_id=10*i+1, league_id=39+i)
            for i in (1, 2, 3)]


@pytest.mark.parametrize("odds", list(permutations((1.50, 1.60, 1.25))))
def test_exact_upper_boundary_is_eligible_in_every_leg_order(odds):
    now = datetime.now(timezone.utc)
    items = candidates(now)
    ticket = select_quoted_ticket(items, dict(zip((c.candidate_id for c in items), odds)),
                                  odds_min=3.0, odds_max=3.0, now=now)
    assert ticket is not None
    assert len(ticket.legs) == 3
    assert ticket.total_odds == 3.0


def test_exact_boundary_can_be_recorded_without_exceeding_corridor(tmp_path):
    now = datetime.now(timezone.utc)
    items = candidates(now)
    offers = dict(zip((c.candidate_id for c in items), (1.50, 1.60, 1.25)))
    # The wider construction corridor isolates the store's admission bug.
    ticket = select_quoted_ticket(items, offers, odds_min=3., odds_max=3.00001, now=now)
    assert ticket is not None
    ledger = ChallengeLedger(tmp_path / "boundary.db")
    ticket_id = ledger.place_ticket(now.date().isoformat(), ticket, ticket_stake(ticket, 100),
                                    quote_verified_at=now.isoformat())
    assert ledger.get_ticket(ticket_id)["played_odds"] == 3.0
    assert ledger.verify_financial_ledger() == (True, None)


def test_true_above_corridor_is_not_hidden_by_float_tolerance():
    now = datetime.now(timezone.utc)
    items = candidates(now)
    offers = dict(zip((c.candidate_id for c in items), (1.50, 1.60, 1.2500001)))
    assert select_quoted_ticket(items, offers, odds_min=3., odds_max=3., now=now) is None


def test_overflowing_quote_combination_does_not_abort_other_valid_tickets():
    now = datetime.now(timezone.utc)
    items = candidates(now)
    items.append(replace(_candidate(now, probability=.88), candidate_id="4:BTTS",
                         fixture_id=4, home_team_id=40, away_team_id=41, league_id=43))
    offers = dict(zip((c.candidate_id for c in items), (1e160, 1e160, 1.50, 1.50)))
    ticket = select_quoted_ticket(items, offers, now=now)
    assert ticket is not None
    assert ticket.total_odds == 2.25
    assert {leg.candidate.fixture_id for leg in ticket.legs} == {3, 4}
