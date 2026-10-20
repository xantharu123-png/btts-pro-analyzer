# Rechtshinweise in der App und fail-closed Kundenzugang (20.10.2026, Claude)

Grundlage: `AUDIT_BERICHT_2026-10-16_CLAUDE.md` H11 (keine Pflichthinweise) und H14
(Kundenzugang opt-in), Gegenabgleich 17.10.2026 («Default ohne Migration umstellen
würde den Nutzer aussperren»). Branch `claude/audit-repairs-20261019`, nichts
committet, gepusht oder deployt. Kein Rechtsrat; keine Betreiberdaten erfunden.

## Was

### H11: Pflichthinweise im Streamlit-Footer

- Neues Modul `legal_notice.py`, `render_legal_footer(st)`; `app.py` ruft es am Ende
  von `main()` anstelle des bisherigen Einzelsatzes auf.
- Inhalt: «18+ · Modellwerte sind Schätzungen. Wetten können zum Verlust des
  Einsatzes führen.»; Hilfe bei Spielsucht mit klickbaren Links zu SOS Spielsucht
  (Beratungstelefon 0800 040 080 als `tel:`-Link, sos-spielsucht.ch) und Sucht
  Schweiz (suchtschweiz.ch); Rechtslinks «Anbieterinformationen», «Datenschutz»,
  «AGB».
- Die drei Links kommen nur aus `BETBOY_LEGAL_URL`, `BETBOY_PRIVACY_URL`,
  `BETBOY_TERMS_URL` – dieselben Namen liest das Portal in
  `portal/siteconfig/settings.py`. Fail-closed: alle drei müssen gesetzt und https
  oder seitenrelativ (`/de/legal/`) sein, sonst steht «Anbieterinformationen und
  Datenschutz: noch nicht veröffentlicht». Unterschied zum Portal: dort schaltet
  zusätzlich `BETBOY_LEGAL_READY=1` (`legal_ready`) die Links frei und öffnet den
  Verkauf; die App braucht diesen Schalter nicht, weil sie nichts verkauft.
- Vorlagen mit `[PLATZHALTER]`-Feldern und Owner-Checkliste (DSG, UWG, BGS je als
  Prüfpunkt, nicht als Aussage): `docs/legal/impressum-vorlage.md`,
  `docs/legal/datenschutz-vorlage.md`.

### H14: Kundenzugang fail-closed mit Migration

- `customer_access.access_mode()` liefert `enforced` | `personal` |
  `personal_explicit`; `enabled()` ist `access_mode() == "enforced"`.
  `BETBOY_CUSTOMER_ACCESS_REQUIRED=1` erzwingt (jeder andere nicht-leere Wert
  ausser `0` ebenfalls), `0` ist der ausdrückliche persönliche Modus; ohne Flag
  wird genau dann erzwungen, wenn `BETBOY_PORTAL_INTERNAL_TOKEN` gesetzt ist.
- Sichtbarkeit: Solange nicht erzwungen, steht direkt im Footer die kleine
  Markierung «Persönlicher Modus · kein Kundenzugang aktiv».
- Migration: Der heutige persönliche VPS bleibt im persönlichen Modus, solange die
  App-Umgebung keinen Portal-Token trägt. Trägt `betboy.env` den Token bereits,
  ohne dass der Portal-Cutover live ist, muss vor dem Deploy
  `BETBOY_CUSTOMER_ACCESS_REQUIRED=0` gesetzt oder der Token aus der App-Umgebung
  entfernt werden; sonst stoppt die App beim Login-Hinweis (gewollt fail-closed,
  Browser-ID wird nicht mehr geladen). Dokumentiert in `deploy/README.md`,
  Abschnitt «Secrets and environment flags».

## Wo

| Datei | Änderung |
|---|---|
| `legal_notice.py` | neu: `legal_links`, `legal_ready`, `footer_html`, `render_legal_footer` |
| `customer_access.py` | `access_mode()`, `enabled()` fail-closed, Docstring |
| `app.py` | Import; Footer-Aufruf am Ende von `main()` |
| `tests/test_legal_notice.py` | neu, AppTest: 18+, Spielsucht-Links, Links/Platzhalter mit und ohne Env, unsichere URLs, Modus-Hinweis, `main`-Quelle |
| `tests/test_customer_access.py` | drei Modi parametrisiert, Token ohne Flag sperrt und leert den Browser-Scope, `0` hält den Owner drin |
| `tests/test_unified_navigation.py` | Namensraum des Navigationstests kennt `render_legal_footer` (nur Fixture) |
| `deploy/README.md` | Abschnitt «Secrets and environment flags» |
| `docs/legal/impressum-vorlage.md`, `docs/legal/datenschutz-vorlage.md` | Vorlagen mit Platzhaltern und Checkliste |

## Wie testen

```powershell
..\..\.venv\Scripts\python.exe -m pytest tests/test_legal_notice.py tests/test_customer_access.py tests/test_daily3_ui.py tests/test_workflow_integrity.py -q
..\..\.venv\Scripts\python.exe -m py_compile app.py legal_notice.py customer_access.py
```

Manuell: App ohne die Env-Variablen starten → Footer zeigt 18+, Hilfelinks,
Platzhaltertext und «Persönlicher Modus». Mit `BETBOY_LEGAL_URL`,
`BETBOY_PRIVACY_URL`, `BETBOY_TERMS_URL` (https) erscheinen die drei Links. Mit
`BETBOY_CUSTOMER_ACCESS_REQUIRED=1` verschwindet die Modus-Markierung und ohne
gültiges Portal-Cookie stoppt die App beim Login-Hinweis.

## Was der Owner noch tun muss

1. Vor dem nächsten Deploy `/etc/betboy/betboy.env` prüfen: Portal-Token vorhanden?
   Dann `BETBOY_CUSTOMER_ACCESS_REQUIRED=0` setzen, bis der Kundenstart gewollt ist.
2. Anbieterinformationen, Datenschutzerklärung und AGB aus den Vorlagen fertig
   stellen, juristisch prüfen lassen (Schweizer Zulassung), veröffentlichen und
   die drei URLs in `betboy.env` und `portal.env` eintragen (Portal zusätzlich
   `BETBOY_LEGAL_READY=1`).
3. Entscheiden, ob die Streamlit-App zusätzlich den Portal-Schalter
   `BETBOY_LEGAL_READY` beachten soll (heute bewusst nicht).
4. Weiterhin offen aus H11: Onboarding-Panel «So liest du eine Auswahl» und
   Glossar; nicht Teil dieser Änderung.
