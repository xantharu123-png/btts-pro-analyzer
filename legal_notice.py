"""Rechtliche Pflichthinweise im Streamlit-Footer (Audit 16.10.2026, H11).

Keine Betreiberdaten im Code. Anbieterinformationen, Datenschutz und AGB kommen
ausschliesslich aus den Umgebungsvariablen ``BETBOY_LEGAL_URL``,
``BETBOY_PRIVACY_URL`` und ``BETBOY_TERMS_URL``; dieselben Namen liest das
Django-Portal in ``portal/siteconfig/settings.py``. Fehlt eine der drei oder ist
sie weder ein https-Link noch ein seitenrelativer Pfad, sagt der Footer ehrlich,
dass die Seiten noch nicht veröffentlicht sind. Nichts wird geraten oder
ersetzt (fail-closed).
"""
from __future__ import annotations

import html
import os
from typing import Mapping
from urllib.parse import urlsplit

LEGAL_ENV = {
    "legal": "BETBOY_LEGAL_URL",
    "privacy": "BETBOY_PRIVACY_URL",
    "terms": "BETBOY_TERMS_URL",
}
LEGAL_LABELS = {"legal": "Anbieterinformationen", "privacy": "Datenschutz", "terms": "AGB"}
LEGAL_PENDING = "Anbieterinformationen und Datenschutz: noch nicht veröffentlicht"
AGE_RISK = "18+ · Modellwerte sind Schätzungen. Wetten können zum Verlust des Einsatzes führen."
HELP_INTRO = "Hilfe bei Spielsucht:"
# Echte Schweizer Anlaufstellen; keine erfundenen Nummern oder Adressen.
HELP_CONTACTS = (
    {
        "name": "SOS Spielsucht",
        "url": "https://www.sos-spielsucht.ch/",
        "phone": "0800 040 080",
        "phone_note": "kostenlos und anonym",
    },
    {"name": "Sucht Schweiz", "url": "https://www.suchtschweiz.ch/"},
)
PERSONAL_MODE = "Persönlicher Modus · kein Kundenzugang aktiv"

_STYLE = (
    "<style>"
    ".bb-legal{color:var(--bb-muted,#66707a);font-size:0.78rem;line-height:1.5;margin:0.25rem 0 0.75rem;}"
    ".bb-legal p{margin:0 0 0.3rem;}"
    ".bb-legal a{color:inherit;text-decoration:underline;}"
    ".bb-legal nav a{margin-right:0.35rem;}"
    ".bb-legal nav a+a::before{content:'· ';}"
    ".bb-legal-mode{border:1px solid var(--bb-amber,#a45f00);border-radius:999px;"
    "color:var(--bb-amber,#a45f00);display:inline-block;font-weight:650;"
    "padding:0.1rem 0.6rem;}"
    "</style>"
)


def _valid_url(value: str) -> bool:
    parts = urlsplit(value)
    if parts.scheme == "https" and parts.hostname:
        return True
    # Seitenrelativer Pfad (z. B. /de/legal/ auf demselben Host), nie //host.
    return not parts.scheme and not parts.netloc and value.startswith("/") and not value.startswith("//")


def legal_links(environ: Mapping[str, str] | None = None) -> dict[str, str]:
    """Alle drei Links oder keiner: unvollständige oder unsichere Werte zählen als nicht veröffentlicht."""
    environ = os.environ if environ is None else environ
    links: dict[str, str] = {}
    for key, name in LEGAL_ENV.items():
        value = (environ.get(name) or "").strip()
        if not value or not _valid_url(value):
            return {}
        links[key] = value
    return links


def legal_ready(environ: Mapping[str, str] | None = None) -> bool:
    return bool(legal_links(environ))


def _link(url: str, label: str) -> str:
    # Externe Seiten in neuem Tab; tel:-Links bleiben ohne target.
    attrs = ' target="_blank" rel="noopener noreferrer"' if not url.startswith("tel:") else ""
    return f'<a href="{html.escape(url, quote=True)}"{attrs}>{html.escape(label)}</a>'


def _help_line() -> str:
    parts = []
    for contact in HELP_CONTACTS:
        text = _link(contact["url"], contact["name"])
        phone = contact.get("phone")
        if phone:
            tel = "tel:" + phone.replace(" ", "")
            note = contact.get("phone_note")
            text += f" (Beratungstelefon {_link(tel, phone)}"
            text += f", {html.escape(note)})" if note else ")"
        parts.append(text)
    return f"{html.escape(HELP_INTRO)} " + " · ".join(parts)


def footer_html(links: Mapping[str, str], access_mode: str) -> str:
    """Reines HTML ohne Streamlit, damit der Inhalt testbar bleibt."""
    blocks = [_STYLE, '<div class="bb-legal">']
    if access_mode != "enforced":
        blocks.append(f'<p><span class="bb-legal-mode">{html.escape(PERSONAL_MODE)}</span></p>')
    blocks.append(f"<p>{html.escape(AGE_RISK)}</p>")
    blocks.append(f"<p>{_help_line()}</p>")
    if links:
        items = "".join(_link(links[key], LEGAL_LABELS[key]) for key in LEGAL_ENV)
        blocks.append(f'<nav aria-label="Rechtliches">{items}</nav>')
    else:
        blocks.append(f'<nav aria-label="Rechtliches"><span>{html.escape(LEGAL_PENDING)}</span></nav>')
    blocks.append("</div>")
    return "".join(blocks)


def render_legal_footer(st_module, access_mode: str | None = None) -> None:
    """Footer mit 18+, Risikosatz, Spielsucht-Hilfe, Rechtslinks und Zugangsmodus."""
    if access_mode is None:
        from customer_access import access_mode as current_access_mode

        access_mode = current_access_mode()
    st_module.markdown(footer_html(legal_links(), access_mode), unsafe_allow_html=True)
