"""Wochenreport Tennis (montags): Satz-Markt-Fair-Preise fuer alle Karten
mit komplett gruenen Gates.

Standalone - laeuft ohne Kimi/Agent (Windows-Aufgabenplanung).
Liest die Shadow-DB und das letzte Kalibrierungs-Waechter-Ergebnis,
rendert reports/weekly_<datum>.html (+ reports/weekly_latest.html).

Nur Karten, bei denen ALLE Modell-Gates gruen sind, werden als wettbar
gelistet.  WTA bleibt Shadow-only (kein Edge) und taucht daher nie in
der Wettliste auf - nur als Info-Zeile.

Mindestquote = 1 / (p - MIN_EDGE). Nur wetten, wenn die Buchmacher-
Quote mindestens diesen Preis erreicht; der Edge ist als absolute
Wahrscheinlichkeitsdifferenz definiert.
"""

from __future__ import annotations

import argparse
import json
import os
import sqlite3
import sys
from datetime import date, datetime, timedelta
from html import escape
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DB = ROOT / "tennis" / "data" / "tennis_shadow.db"
WATCH_JSON = ROOT / "tennis" / "data" / "calibration_watch_latest.json"
REPORTS = ROOT / "reports"

MIN_EDGE = 0.15          # Mindest-Edge gegen die Buchmacher-Quote
WATCH_MAX_AGE_DAYS = 8   # danach gilt das Waechter-Ergebnis als veraltet

# (Label, Key in markets_json) - Reihenfolge = Spaltenreihenfolge
MARKETS = [
    ("Sieg A", "p_a_cal"),
    ("Sieg B", "p_b_cal"),
    ("&Uuml; 2,5 S&auml;tze", "over_2_5_sets"),
    ("U 2,5 S&auml;tze", "under_2_5_sets"),
    ("A &minus;1,5 S&auml;tze", "set_handicap_a_minus_1_5"),
    ("B &minus;1,5 S&auml;tze", "set_handicap_b_minus_1_5"),
]

WATCH_LABELS = {
    "over_2_5_sets": "&Uuml; 2,5 S&auml;tze",
    "under_2_5_sets": "U 2,5 S&auml;tze",
    "set_a_2_0": "Satz A 2:0",
    "set_b_2_0": "Satz B 2:0",
    "over_21_5_games": "&Uuml; 21,5 Games (Referenz, nicht angeboten)",
}


def load_cards(day_from: date, days: int) -> list[dict]:
    day_to = day_from + timedelta(days=days - 1)
    with sqlite3.connect(str(DB)) as conn:
        conn.row_factory = sqlite3.Row
        rows = conn.execute(
            "SELECT * FROM predictions WHERE match_date BETWEEN ? AND ? "
            "ORDER BY match_date, tournament, player_a",
            (day_from.isoformat(), day_to.isoformat()),
        ).fetchall()
    return [dict(r) for r in rows]


def gates_all_green(card: dict) -> bool:
    try:
        gates = json.loads(card.get("gates_json") or "{}")
    except ValueError:
        return False
    return bool(gates) and all(g.get("passed") for g in gates.values())


def load_watch() -> tuple[dict | None, str]:
    """Return (watch_json, hinweis). hinweis == '' wenn frisch."""
    if not WATCH_JSON.exists():
        return None, "Noch kein W&auml;chter-Ergebnis vorhanden (l&auml;uft montags automatisch)."
    try:
        data = json.loads(WATCH_JSON.read_text(encoding="utf-8"))
    except ValueError:
        return None, "W&auml;chter-Datei korrupt."
    run_date = data.get("run_date", "")
    try:
        age = (date.today() - date.fromisoformat(run_date[:10])).days
    except ValueError:
        age = 999
    if age > WATCH_MAX_AGE_DAYS:
        return data, f"W&auml;chter-Ergebnis ist {age} Tage alt (vom {escape(run_date[:10])}) - veraltet."
    return data, ""


def _minimum_odds(p: float | None) -> float | None:
    if p is None or p <= MIN_EDGE or p > 1.0:
        return None
    return 1.0 / (p - MIN_EDGE)


def _fmt_odds(p: float | None) -> str:
    if not p or p <= 0:
        return "&ndash;"
    fair = 1.0 / p
    minq = _minimum_odds(p)
    if minq is None:
        return f"&ndash;<span class='fair'>fair {fair:,.2f}</span>".replace(",", " ").replace(".", ",")
    return f"<b>{minq:,.2f}</b><span class='fair'>fair {fair:,.2f}</span>".replace(",", " ").replace(".", ",")


def render(cards: list[dict], green: list[dict], watch: dict | None,
           watch_note: str, day_from: date, days: int) -> str:
    day_to = day_from + timedelta(days=days - 1)
    n_wta = sum(1 for c in cards if c.get("tour") == "WTA")
    n_atp = sum(1 for c in cards if c.get("tour") == "ATP")

    # --- Waechter-Block ---
    if watch is None:
        watch_html = f"<div class='box warn'>Kalibrierungs-W&auml;chter: {watch_note}</div>"
    else:
        status = watch.get("status", "?")
        limits = watch.get("limits", {})
        rows = []
        for mk, info in watch.get("markets", {}).items():
            label = WATCH_LABELS.get(mk, escape(mk))
            flag = "<span class='drift'>DRIFT</span>" if info.get("drift") else "<span class='ok'>ok</span>"
            ref = " ref" if mk == "over_21_5_games" else ""
            rows.append(
                f"<tr class='{ref}'><td>{label}</td><td>{info.get('n', 0)}</td>"
                f"<td>{info.get('rms', 0):.4f}</td><td>{info.get('max_mid_bias', 0):.4f}</td><td>{flag}</td></tr>"
            )
        cls = "ok" if status == "ok" else "drift"
        title = ("Satz-M&auml;rkte kalibriert - Modell stabil."
                 if status == "ok" else
                 "W&Auml;CHTER-ALARM: Satz-M&auml;rkte driften - keine Satz-Wetten, Kalibrierung pr&uuml;fen!")
        watch_html = (
            f"<div class='box {cls}'><b>Kalibrierungs-W&auml;chter ({escape(str(watch.get('run_date', '?'))[:10])}):</b> {title}"
            f"<br><span class='fair'>n={watch.get('n_scored', 0)} Matches &middot; "
            f"Limits: RMS &le; {limits.get('rms', '?')} &middot; Mid-Bias &le; {limits.get('mid_bias', '?')}</span>"
            f"<table><tr><th>Markt</th><th>n</th><th>RMS</th><th>max. Mid-Bias</th><th>Status</th></tr>"
            + "".join(rows) + "</table></div>"
        )
    if watch_note and watch is not None:
        watch_html += f"<div class='box warn'>{watch_note}</div>"

    # --- Karten-Tabelle ---
    if not green:
        cards_html = (
            "<div class='box warn'><b>Keine Karte mit komplett gr&uuml;nen Gates "
            "im Zeitraum.</b> Das ist normal und gewollt - das Modell wettet nur, "
            "wenn Belag, Erfahrung und Aufschlag-Daten alle passen. "
            "<b>Keine Karte = keine Wette.</b></div>"
        )
    else:
        header = "".join(f"<th>{lbl}</th>" for lbl, _ in MARKETS)
        rows = []
        last_day = None
        for c in green:
            try:
                mk = json.loads(c.get("markets_json") or "{}")
            except ValueError:
                mk = {}
            d = c.get("match_date", "")
            if d != last_day:
                try:
                    lbl = datetime.strptime(d, "%Y-%m-%d").strftime("%a %d.%m.")
                except ValueError:
                    lbl = escape(d)
                rows.append(f"<tr class='day'><td colspan='{3 + len(MARKETS)}'>{lbl}</td></tr>")
                last_day = d
            cells = "".join(f"<td>{_fmt_odds(mk.get(key))}</td>" for _, key in MARKETS)
            p_cal = c.get("p_cal")
            p_txt = f"{p_cal * 100:.0f} %".replace(".", ",") if p_cal is not None else "&ndash;"
            tour = escape(c.get("tour") or "")
            rows.append(
                f"<tr><td><b>{escape(c.get('player_a', '?'))}</b> vs <b>{escape(c.get('player_b', '?'))}</b>"
                f"<span class='fair'>{tour}</span></td>"
                f"<td>{escape(c.get('tournament') or '&ndash;')}</td>"
                f"<td>{escape(c.get('surface') or '?')}</td>"
                f"<td>{p_txt}</td>{cells}</tr>"
            )
        cards_html = (
            f"<table><tr><th>Match</th><th>Turnier</th><th>Belag</th><th>p(A)</th>{header}</tr>"
            + "".join(rows) + "</table>"
        )

    skipped = len(cards) - len(green)
    info = (
        f"<p class='meta'>{len(cards)} Karten im Zeitraum ({n_atp} ATP / {n_wta} WTA) &middot; "
        f"{len(green)} mit gr&uuml;nen Gates &middot; {skipped} verworfen (Gate nicht erf&uuml;llt = keine Wette)"
        + (" &middot; WTA l&auml;uft nur im Shadow-Tracking (kein nachgewiesener Edge)" if n_wta else "")
        + "</p>"
    )

    return f"""<!doctype html>
<html lang="de"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>BetBoy &middot; Tennis Wochenreport {day_from.strftime('%d.%m.%Y')}</title>
<style>
 body {{ background:#0e1117; color:#e6e9ef; font-family:'Segoe UI',system-ui,sans-serif; margin:0; padding:24px; }}
 .wrap {{ max-width:1180px; margin:0 auto; }}
 h1 {{ font-size:20px; margin:0 0 4px; }}
 .meta {{ color:#8b93a5; font-size:13px; }}
 .box {{ border-radius:10px; padding:12px 16px; margin:14px 0; font-size:14px; }}
 .box.ok {{ background:#0f2b1d; border:1px solid #1f7a4d; }}
 .box.warn {{ background:#2b230f; border:1px solid #8a6d1f; }}
 .box.drift {{ background:#2b0f14; border:1px solid #a13a3a; }}
 span.ok {{ color:#3ddc84; font-weight:600; }}
 span.drift {{ color:#ff6b6b; font-weight:700; }}
 .fair {{ display:block; color:#8b93a5; font-size:11px; }}
 table {{ border-collapse:collapse; width:100%; margin:10px 0 4px; font-size:13px; }}
 th, td {{ border-bottom:1px solid #232a38; padding:8px 10px; text-align:left; }}
 th {{ color:#8b93a5; font-weight:600; white-space:nowrap; }}
 td {{ vertical-align:top; }}
 tr.day td {{ background:#171d29; color:#8b93a5; font-weight:600; }}
 tr.ref td {{ color:#8b93a5; }}
 .rule {{ background:#101828; border:1px solid #2b6ea1; }}
 .foot {{ color:#5b6373; font-size:12px; margin-top:18px; }}
 .tablewrap {{ overflow-x:auto; }}
</style></head><body><div class="wrap">
<h1>BetBoy &middot; Tennis Wochenreport</h1>
<p class="meta">Erstellt {datetime.now().strftime('%d.%m.%Y %H:%M')} &middot;
Zeitraum {day_from.strftime('%d.%m.')}&ndash;{day_to.strftime('%d.%m.%Y')} &middot;
alle Zeiten lokal</p>
{watch_html}
<div class="box rule"><b>Wettregel:</b> Die Zahl in <b>fett</b> ist die
<b>Mindestquote</b> (fair + {MIN_EDGE:.0%} Edge). Nur wetten, wenn die Quote beim
Buchmacher <b>&ge; Mindestquote</b> liegt &mdash; darunter ist die Wette
langfristig Verlustgesch&auml;ft. <i>fair</i> = reine Modell-Wahrscheinlichkeit (1/p).</div>
<h2>Karten mit gr&uuml;nen Gates</h2>
{info}
<div class="tablewrap">{cards_html}</div>
<p class="foot">Erinnerung: N1Bet-Aufgaberegel pr&uuml;fen (Annahme: 1 Satz gespielt
= Wette gilt) &middot; Games-M&auml;rkte werden bewusst nicht angeboten
(Over-/Favoriten-Bias im Kalibrierungs-Test) &middot; Quellen: ManTennisData,
tennis-data.co.uk, Tennis Abstract, ESPN.</p>
</div></body></html>"""


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--days", type=int, default=2, help="Vorschau in Tagen (Standard 2)")
    ap.add_argument("--open", action="store_true", help="Report im Browser oeffnen")
    ap.add_argument("--out", default="", help="Alternativer Ausgabepfad")
    args = ap.parse_args()

    day_from = date.today()
    cards = load_cards(day_from, args.days)
    green = [c for c in cards if gates_all_green(c) and (c.get("tour") or "").upper() == "ATP"]
    watch, watch_note = load_watch()

    html = render(cards, green, watch, watch_note, day_from, args.days)
    REPORTS.mkdir(exist_ok=True)
    out = Path(args.out) if args.out else REPORTS / f"weekly_{day_from.isoformat()}.html"
    out.write_text(html, encoding="utf-8")
    latest = REPORTS / "weekly_latest.html"
    if out.resolve() != latest.resolve():
        latest.write_text(html, encoding="utf-8")

    print(f"REPORT={out}")
    print(f"Karten: {len(cards)} | gruene Gates: {len(green)} | "
          f"Waechter: {'vorhanden' if watch else 'noch kein Ergebnis'}")
    if args.open:
        try:
            os.startfile(str(out))  # type: ignore[attr-defined]
        except OSError as exc:
            print(f"Browser-Start fehlgeschlagen: {exc}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
