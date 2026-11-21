"""Read-only presentation of original slips. No generation, pricing, training or booking in the UI."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
import json
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


def customer_cards(slips, artifact, *, as_of, chance):
    now = _time(as_of)
    day = now.astimezone(ZURICH).date()
    cards = []
    for slip in slips:
        try:
            size, legs = slip["size"], slip["legs"]
            if (size not in (3, 4, 5, 6) or len(legs) != size or len({leg["event_key"] for leg in legs}) != size
                    or slip["day"] != day.isoformat() or slip["arm"] != "reference"
                    or _time(slip["captured_at"]) > now or
                    any(not now < _time(leg["starts_at"]) or _time(leg["starts_at"]).astimezone(ZURICH).date() != day
                        for leg in legs)):
                continue
            p = chance(slip, artifact, as_of=now)
            if p is None or isinstance(p, bool) or not math.isfinite(p) or not 0 < p < 1:
                continue
            cards.append(dict(size=size, chance=p, legs=sorted(legs, key=lambda leg: _time(leg["starts_at"])),
                              price_observed=quote_status(slip, now)))
        except (KeyError, ValueError, TypeError, OverflowError):
            continue
    return sorted(cards, key=lambda card: card["size"])


def render_daily_accumulators(st, *, as_of=None, directory=None):
    from daily_accumulator_publication import DB_NAME
    from daily_accumulator_quality import chance_for_slip
    from daily_accumulator_receipts import load_day
    from runtime_paths import RUNTIME_STATE_DIR
    now = _time(as_of or datetime.now(timezone.utc))
    root = Path(directory or RUNTIME_STATE_DIR)
    cards = []
    try:
        artifact_path = root / "daily_accumulator_quality.json"
        if artifact_path.is_file() and artifact_path.stat().st_size <= 2_000_000:
            artifact = json.loads(artifact_path.read_text(encoding="utf-8"))
            slips = load_day(root / DB_NAME, day=now.astimezone(ZURICH).date(), arm="reference")
            cards = customer_cards(slips, artifact, as_of=now, chance=chance_for_slip)
    except (OSError, sqlite3.Error, ValueError, TypeError, KeyError):
        logging.getLogger(__name__).warning("Daily accumulator rail unavailable")
    with st.container(key="editorial_accumulator_rail"):
        st.subheader("Kombis des Tages")
        if not cards:
            st.caption("Heute noch kein geprüfter Kombischein.")
        for card in cards:
            st.markdown("**Jackpot 6er**" if card["size"] == 6 else f"**{card['size']}er-Kombi**")
            label = f"Alle {card['size']} richtig: {card['chance']:.1%}".replace(".", ",")
            st.progress(card["chance"], text=label)
            for leg in card["legs"]:
                start = _time(leg["starts_at"]).astimezone(ZURICH).strftime("%H:%M")
                st.text(f"{start}  {leg['event_label']}\n{leg['selection']}")
                if leg.get("reason"):
                    st.caption(leg["reason"])
            st.caption("Einzelquoten beim selben Buchmacher beobachtet." if card["price_observed"]
                       else "Gemeinsamer Preis nicht aktuell bestätigt.")
