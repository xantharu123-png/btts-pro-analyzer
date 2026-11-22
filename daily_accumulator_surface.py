"""Read-only presentation of original slips. No generation, pricing, training or booking in the UI."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
import logging
import math
from pathlib import Path
import sqlite3
from zoneinfo import ZoneInfo

ZURICH = ZoneInfo("Europe/Zurich")


def _time(value):
    parsed = datetime.fromisoformat(value) if isinstance(value, str) else value
    if not isinstance(parsed, datetime) or parsed.tzinfo is None or parsed.utcoffset() is None:
        raise ValueError("clock")
    return parsed.astimezone(timezone.utc)


def quote_status(slip, as_of):
    """Whether these individual recorded prices are still recent; no live combo price implied."""
    try:
        now = _time(as_of)
        book = slip["bookmaker_id"]
        if not book or slip["price_status"] != "confirmed" or not slip["legs"]:
            return False
        for leg in slip["legs"]:
            offer = leg["offers"][book]
            price = float(offer["odds"])
            observed, fetched = _time(offer["observed_at"]), _time(offer["fetched_at"])
            if not (math.isfinite(price) and price >= 1.20 and
                    observed <= fetched <= now < _time(leg["starts_at"]) and
                    now - observed <= timedelta(minutes=45) and now - fetched <= timedelta(minutes=35)):
                return False
        return True
    except (TypeError, ValueError, KeyError, OverflowError):
        return False


def customer_cards(slips, artifact=None, *, as_of, chance=None):
    now = _time(as_of)
    day = now.astimezone(ZURICH).date()
    cards = []
    for slip in slips:
        try:
            size, legs, arm = slip["size"], slip["legs"], slip["arm"]
            captured = _time(slip["captured_at"])
            starts = [_time(leg["starts_at"]) for leg in legs]
            if (type(size) is not int or size not in (3, 4, 5, 6) or len(legs) != size
                    or len({leg["event_key"] for leg in legs if leg["event_key"]}) != size
                    or slip["day"] != day.isoformat() or captured.astimezone(ZURICH).date() != day
                    or captured > now or any(start <= captured or start.astimezone(ZURICH).date() != day for start in starts)):
                continue
            started = min(starts) <= now
            estimated = arm == "daily-picks"
            if estimated:
                probabilities = [leg["probability"] for leg in legs]
                if any(type(x) not in (float,int) or not 0 < x < 1 for x in probabilities):
                    continue
                p = math.prod(probabilities)
                if not math.isclose(p, slip["reference_probability"], rel_tol=1e-12):
                    continue
            elif arm == "candidate" and not started and chance is not None:
                p = chance(slip, artifact, as_of=now)
            else:
                continue
            if type(p) not in (float,int) or not 0 < p < 1:
                continue
            cards.append(dict(size=size, chance=p, legs=sorted(legs, key=lambda leg: _time(leg["starts_at"])),
                              price_observed=not started and quote_status(slip, now), started=started, estimated=estimated))
        except (KeyError, ValueError, TypeError, OverflowError):
            continue
    return sorted(cards, key=lambda card: card["size"])


def _selection_label(leg):
    """Use original spellings only when both names match the stored sides, in order."""
    from editorial_rail_labels import rail_selection_label

    sport = leg.get("sport")
    identities = leg.get("participant_names")
    event = leg.get("event_label") or ""
    # E-sports may prefix the game title; tennis appends exclusion aliases AFTER the
    # two side identities. Neither is itself a participant. No lookup or fuzzy join.
    labels = (event, event.partition(" · ")[2]) if sport == "esports" else (event,)
    home = away = ""
    if isinstance(identities, (list, tuple)):
        for label in labels:
            names = [name.strip() for name in label.split(" vs ")]
            if (len(names) == 2 and all(names) and list(identities[:2]) == [
                f"{sport}:name:" + " ".join(name.casefold().split()) for name in names
            ]):
                home, away = names
                break
    key = leg.get("market_key")
    evidence = leg.get("evidence_selection")
    # The archived evidence field may instead be a selection key or plain display
    # text. Only a verbatim H2H participant from the proven pair binds a winner.
    winner = evidence if key == "H2H" and home and away and evidence in (home, away) else ""
    return rail_selection_label(sport=sport, market_key=key, selection=leg["selection"],
                                home=home, away=away, selected_competitor=winner)


def render_daily_accumulators(st, *, as_of=None, directory=None):
    from daily_accumulator_publication import DB_NAME
    from daily_accumulator_receipts import load_daily_picks
    from runtime_paths import RUNTIME_STATE_DIR
    now = _time(as_of or datetime.now(timezone.utc))
    root = Path(directory or RUNTIME_STATE_DIR)
    cards = []
    try:
        slips = load_daily_picks(root / DB_NAME, day=now.astimezone(ZURICH).date())
        cards = customer_cards(slips, as_of=now)
    except (OSError, sqlite3.Error, ValueError, TypeError, KeyError):
        logging.getLogger(__name__).warning("Daily accumulator rail unavailable")
    with st.container(key="editorial_accumulator_rail"):
        st.subheader("Kombis des Tages")
        if not cards:
            st.caption("Heute noch keine passende Tageskombi.")
        for card in cards:
            st.markdown("**Jackpot 6er**" if card["size"] == 6 else f"**{card['size']}er-Kombi**")
            if card["started"]:
                st.caption("Bereits begonnen · kein neuer Wettschein")
            percent = round(100 * math.fsum(leg["probability"] for leg in card["legs"]) / card["size"])
            display = "<1" if percent == 0 else ">99" if percent == 100 else str(percent)
            st.progress(max(1, min(99, percent)), text=f"Ø Modellchance je Einzeltipp: {display} %")
            for leg in card["legs"]:
                start = _time(leg["starts_at"]).astimezone(ZURICH).strftime("%H:%M")
                st.text(f"{start}  {leg['event_label']}\n{_selection_label(leg)}")
                if leg.get("reason"):
                    st.caption(leg["reason"])
            if not card["started"] and card["price_observed"]:
                st.caption("Einzelquoten beim selben Buchmacher beobachtet.")
