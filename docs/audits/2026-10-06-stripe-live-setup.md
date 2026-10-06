# BetBoy: Stripe-Live-Einrichtung, 06.10.2026

## Umfang und Berechtigungen

Nutzerauftrag: bestehendes BetBoy-Live-Konto prüfen, Einrichtung korrigieren.
Nur der bereits geöffnete **interne** Browser wurde verwendet; nach Abbruch
keine erneute MCP/OAuth-Verbindung oder externe Browseranmeldung gestartet.
Keine Zahlungen, Abonnements für Kunden, neuen Zugangsschlüssel,
Steuerregistrierungen, Sportscans oder Sicherungen erzeugt.

Die drei bestätigten Monatspreise wurden im BetBoy-Live-Konto gespeichert.
Die Steuerkategorie `txcd_10103000` wurde nach ausdrücklicher Bestätigung
„BetBoy ist für Privatkunden; diese Kategorie verwenden“ übernommen.
Das ist keine Bestätigung steuerlicher Registrierungspflichten oder weltweiter
Verkaufszulässigkeit. Geschäftskunden und spätere native Apps neu prüfen.

## Frisch am Dashboard nachgewiesen

- BetBoy: Zahlungen und Auszahlungen aktiv; keine offenen Pflichtaufgaben.
- Drei separate aktive Produkte, jeweils ein monatlicher CHF-Standardpreis,
  ohne Testzeitraum. Keine tatsächlichen Kundenabos; Katalog ist kein Verkaufsstart.
- Preissteuerverhalten ausdrücklich **Inklusive**, nicht nur Währungs-Automatik.
- Produktkategorie bei allen drei Produkten SaaS / privater Gebrauch / keine
  mobile App oder Plugin, `txcd_10103000`; globale Voreinstellung
  „Beratungsleistungen“ nicht für andere Produkte oder Konten verändert.
- Billing-Portal: Kündigung zum Ende des Abrechnungszeitraums bereits ausgewählt;
  nicht als neue Änderung oder Beleg einer eingerichteten API-Portal-Konfiguration zählen.
- Noch kein Live-Webhook-Ziel. Steuerregistrierungen noch nicht verifiziert.
- Alpha Station/Punkt Zukunft und vorhandene Kundendaten unverändert.

| Tarif | CHF/Monat | Produkt-ID | Live-Preis-ID |
| --- | ---: | --- | --- |
| Starter | 9.90 | `prod_VOLQ6uXM3ZKdt6` | `price_1UNYjMCbq4sqDu4cJKdpgxyn` |
| Plus | 19.90 | `prod_VOLS3xoFf5pGME` | `price_1UNYlJCbq4sqDu4cIGT8X5bv` |
| Pro | 29.90 | `prod_VOLTbz1EG5cWiJ` | `price_1UNYmrCbq4sqDu4cbtdXhwbk` |

Nur IDs, keine Schlüssel. Nicht in einer Testumgebung als Testpreise verwenden.
Protected `portal.env` bleibt separat; keine gefüllte Konfiguration in Git.

## Eng begrenzte Codekorrekturen

`portal/members/billing.py` akzeptiert jetzt richtige `rk_test_`/`rk_live_`
Restricted Keys zusätzlich zu `sk_test_`/`sk_live_`. Publishable Keys, Leerwerte
und falsche Umgebungen bleiben gesperrt; sonstige Konfigurationsgates unverändert.
Hosted Checkout erzwingt nicht mehr `payment_method_types=["card"]`;
Stripe wählt passende aktivierte Dashboard-Methoden dynamisch aus.
Stabile Flow-Kennung `betboy-web-cbafrqop` ergänzt, Idempotenz-Namensraum für
den veränderten Request auf `v2` angehoben. Der Portalservice existiert noch
nicht in Produktion, deshalb kein Wechsel für aktive Checkout-Sessions.

Vorher reproduzierter RED: beide Restricted-Key-Unterfälle sowie der Test
gegen erzwungene Kartenmethode scheiterten. Erste Suite **45 Portaltests** lokal
und unabhängig bestanden, je kompletter Lauf; nicht zusammenzählen. Zusätzlich
Flow-/Retry-Tests RED→GREEN; finale vollständige Suite **47 bestanden**, Exit 0,
12,939 Sekunden, Systemcheck ohne Probleme. Finalreview mit 2/2 neuen Tests grün;
keine offenen P0–P2-Regressionsbefunde im eng begrenzten Patch.
Unabhängige In-Memory-Gegenprüfungen: abgeschlossen/unbezahlt kein Zugriff,
verzögerter Zahlungserfolg mit passender Rechnung Zugriff, Misserfolg kein Zugriff.
Keine echten Stripe-API-Aufrufe in diesen Softwaretests.

Das Review änderte keine Länder-, Eigentums-, Signatur-, Preis-, Rechnungsperioden-
oder Ereignis-Deduplizierungsprüfung. Tests bestätigen keinen Live-Verkauf,
keine Mailzustellung und keine verbesserte Prognosequalität.

## VPS und offene Launch-Abnahme

Vor diesem Release frisch lesend geprüft: Commit
`5a5e1b1a6b18d93211164b96193c7d909564af8b`, getrackter Checkout sauber;
App/Caddy aktiv. `betboy-portal.service` fehlt und `/etc/betboy/portal.env` fehlt.
Ein Pull von Portalcode allein installiert/aktiviert keinen Kundenservice.

Noch erforderlich, nicht mit Flags oder Testresultaten als erledigt markieren:

1. Öffentliche Kundenadresse und SMTP-Absender/-Zugang festlegen. Fragen im Chat
   gestellt; bestehende VPS-Adresse nur Vorschlag, noch kein bestätigter Cutover.
2. Restricted Serverkey zuerst im Sandbox-Test, danach im Live-Konto; minimale
   Rechte für Kunden/Checkout/Portal-Sessions und Lesen von Preisen/Abos/Rechnungen/
   Charges. Keine Rechte für Geldbewegungen, Erstattungen, Produkt- oder Preisänderung
   durch die Runtime. Erstellung/Secret-Eingabe übernimmt der Nutzer; kein Chat/Git.
3. HTTPS-Webhook erst nach geschützter Endpoint-Bereitstellung, Signature-Secret
   geschützt speichern; API-Version `2026-08-26.dahlia`, dokumentierte Events.
4. Betreiber-/Rechts-/Datenschutz-/AGB-Daten, tatsächliche Verkaufsländer und
   erforderliche Stripe-Tax-Registrierungen bestätigen. Nichts automatisch registrieren.
5. Echter Pre-Payment-Länderschutz: Hosted Checkout besitzt keine Billing-Country-
   Allowlist. Versandländer oder ein vorgeschalteter Dropdown sind kein Ersatz.
   Der heutige Code prüft das Land erst bei der bezahlten Rechnung: außerhalb
   der Allowlist könnte bezahlt werden, ohne Zugang zu erhalten. Verkauf bleibt
   geschlossen, bis dieser Fall verhindert und im tatsächlichen Zahlungsfluss
   geprüft ist. Bestehende Nachprüfung nicht entfernen. Keine kostenpflichtigen
   Radar-Regeln oder scheinbare Lösung ungefragt aktivieren.
6. Geschützter separater Portalservice, Kunden-DB, `/app/`-Proxy, verborgenes
   `/internal/*`, echte Inboxzustellung, Sandbox-Checkout/Webhook/Kündigung/
   Entzug/Replay/Kontentrennung und Reconciliation. Dann explizite Verkaufsfreigabe.

Offizielle Quellen: [Checkout-Parameter](https://docs.stripe.com/api/checkout/sessions/create),
[dynamische Zahlungsarten](https://docs.stripe.com/payments/payment-methods/dynamic-payment-methods),
[Schlüsseltypen](https://docs.stripe.com/keys),
[Steuercodes](https://docs.stripe.com/tax/tax-codes).

## Belege

Lokal ungetrackt unter `output/stripe-setup-20261006/`: Live-Konto-/Status-,
Katalog- und einzelne Preis-Screenshots. Vollständige Secrets weder dargestellt
noch gespeichert. `betboy-live-subscriptions-created.jpg` zeigt alle drei Tarife.
MCP-Planer blieb wegen nicht abgeschlossener Autorisierung unverfügbar;
keine Alternativübertragung zur Umgehung gestartet. Bestehender freigegebener
Portalvertrag und offizielle Stripe-Dokumentation wurden verwendet.
