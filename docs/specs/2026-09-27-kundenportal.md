# BetBoy Kundenportal – bestätigter Umfang und Liefergrenzen

## Problem und Ziele

BetBoy besitzt bisher einen persönlichen Streamlit-Zugang mit browserlokalen
Kontokennungen, aber keine Kundenanmeldung und keine Abo-Abrechnung. Kunden
sollen ein persönliches Konto verwenden und nach bestätigter Zahlung die
gebuchten Funktionen erhalten – später auch in nativen Store-Apps.

Ziele: deutsch/englische Landingpage und Kontoseiten; überprüfbare serverseitige
Zugangsrechte; keine Übernahme fremder Browser-Wettkonten; ein nachvollziehbarer
Kauf-/Kündigungsablauf ohne Doppelabschluss.

## Bestätigt am 27.09.2026

| Abo | CHF / Monat | Enthalten |
| --- | ---: | --- |
| Starter | 9.90 | Automatischer Wettfinder, gespeicherte Tipps |
| Plus | 19.90 | Starter plus eigene Suche und RisikoBet |
| Pro | 29.90 | Plus plus Live, Daily3 und 15K |

Alle Stufen verwenden dieselbe Modellqualität. Die Preise sind die bestätigten
monatlichen Web-Preise in CHF; keine automatische Umrechnung oder erfundene
Store-Preise. Stripe wurde ausgewählt, ein Händlerkonto besteht noch nicht.
Internationaler Verkauf und englische Website sind gewünscht. Dies ist keine
globale Anbieter-, Glücksspiel-, Steuer- oder Store-Freigabe.

## Nutzerabläufe / P0

- Als Interessent vergleiche ich drei klar benannte Stufen auf Deutsch/Englisch.
- Als Kunde registriere ich mich, bestätige meine E-Mail und kann mich anmelden.
  Auch ohne Abo ist mein Kontobereich zugänglich; die Analysefunktionen nicht.
- Als Käufer bezahle ich in einem von Stripe gehosteten Zahlungsfenster.
  Rückkehr aus Checkout allein gibt niemals Zugriff; nur signierte Ereignisse
  und serverseitig abgefragte, passende Zahlungen/Abos tun das.
- Als Kunde verwalte ich Kündigung, Rechnungen und Zahlungsmittel über Stripe.
  Kündigung zum Periodenende erhält den bereits bezahlten Zugang.
- Als Bestandsnutzer verliere ich nicht stillschweigend meine persönlichen
  Wettkonten. Browserkonten werden keinem registrierten Konto automatisch
  zugeordnet. Ein Übernahmeverfahren braucht einen eigenen Besitznachweis.

Abnahme: falsche/fehlende Zahlung, abgelaufenes Abo, fremdes Konto, Rückerstattung,
doppelte und verspätete Ereignisse, geänderte Preisparameter, CSRF und gefälschte
Zugangsangaben werden getestet. Desktop und schmale Smartphone-Ansichten prüfen.

## P1: native Apps (Bestandteil des Auftrags, noch nicht implementiert)

- Apple und Google verwenden dieselbe Kundenidentität und dieselben Funktionsstufen.
- StoreKit/Play Billing und serverseitige Transaktionsprüfung statt Stripe im
  nativen Kaufdialog, soweit die jeweiligen Store-/Länderregeln dies verlangen.
- Kaufwiederherstellung, Rückerstattung, Ablauf, Kontolöschung und kein doppelter
  Kauf bei vorhandenem Abo; Kontobindung darf nicht über behauptete E-Mail erfolgen.
- Echte native Projekte, Geräte-/Storetests, Signierung und Einreichung fehlen.
  Eine responsive Website oder WebView allein ist kein Store-Release.
- Vor globaler Freigabe ist zu klären, welche Funktionen (insbesondere Live,
  Echtgeld-Aufzeichnungen/Challenges) in den Zielregionen zulässig sind.

## Nicht enthalten / P2

- Keine automatische Wettabgabe, keine Einnahme von Wetteinsätzen, keine Gewinnzusage.
- Keine Erfindung nachgewiesener Verletzungs-/Wetter-/Müdigkeitseffekte.
- Keine neue Sicherung, kein weiterer Sportscan, kein Umbau der Sportdatenbanken.
- Keine Google-/Apple-/Stripe-Konten im Namen des Nutzers eröffnen, keine Verträge
  akzeptieren und keine Live-Preise oder Zahlungen ohne eingerichteten Anbieter.
- Jahresabos, Rabatte, Affiliate-/Glücksspielwerbung und sofortige anteilige
  Tarifwechsel sind nicht für diesen ersten Web-Verkauf implementiert.

## Umsetzung und Messung

Bestehendes Repo/VPS weiterverwenden. Separater Django-Prozess mit kleiner
Kundendatenbank; Stripe ist die Zahlungsquelle, die eigene Datenbank speichert
nur notwendige Konten-/Abozustände und Ereignis-IDs. Keine wiederholten großen
Rohantworten. Streamlit prüft Kundensitzung und Funktionsrechte serverseitig;
dieser Weg bleibt bis zum expliziten Cutover ausgeschaltet.

Technische Abnahmeziele: alle Rechte-/Kontotrennungstests bestanden, kein
horizontaler Überlauf ab 320 px, kein Freischalten durch Clientparameter.
Vor Verkauf: ein echter Ende-zu-Ende-Nachweis von Registrierung bis Zugang und
Kündigung, keine offene Abweichung zwischen Zahlung und Zugang. Nach Start:
Checkout-Erfolgsquote und Abbruchgründe messen; keine erfundenen Umsatz-/Retention-
Benchmarks und keine Behauptung besserer Wettqualität aus Softwaretests.

## Offene Entscheidungen / Abhängigkeiten

- Nutzer: Domain, öffentlicher Anbieter-/Firmenname, Anbieteradresse,
  Support-E-Mail, Stripe-Aktivierung und erforderliche Händlerprüfung.
- Betreiber: rechtlich geprüfte AGB/Datenschutz/Anbieterinformationen,
  Steuerkonfiguration und zulässige Vertriebsländer; native Store-Einstufung.
- Technik: SMTP-Zustellnachweis; Stripe-Sandbox mit echten Testereignissen;
  Proxy-Cutover und Mehrkontenprüfung am Zielserver; tägliche Abgleichkontrolle
  für verlorene Zahlungsereignisse vor unbetreutem Kundenbetrieb.
- Native Apps: tatsächliche Apple-/Google-Konten und Produkt-/Bundle-Kennungen
  bestätigen; native Projekte und Zahlungsadapter implementieren und testen.

## Primärquellen (27.09.2026 geprüft)

- [Stripe Webhooks](https://docs.stripe.com/webhooks)
- [Stripe Subscriptions](https://docs.stripe.com/billing/subscriptions/webhooks)
- [Apple Review Guidelines, 3.1](https://developer.apple.com/app-store/review/guidelines/)
- [Google Play Payments](https://support.google.com/googleplay/android-developer/answer/9858738?hl=en)
- [Google Play Purchase Verification](https://developer.android.com/google/play/billing/security)

Diese Quellen sind Regeln zur Implementierung, keine Zusage einer Anbieter- oder
Store-Zulassung für BetBoy. Länderspezifische Ausnahmen nicht pauschal übertragen.
