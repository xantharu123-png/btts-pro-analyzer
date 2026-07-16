# Red Card Alerts

Der Monitor erkennt direkte Rote Karten und Gelb-Rote Karten in laufenden
API-Football-Spielen. Er kann verfuegbare Live-Statistiken abrufen, ein
unkalibriertes Rotkartenmodell ausfuehren und Meldungen per Telegram senden.

## Voraussetzungen

- `API_FOOTBALL_KEY`
- optional `TELEGRAM_BOT_TOKEN`
- optional `TELEGRAM_CHAT_ID`
- installierte Pakete aus `requirements.txt`

Secrets gehoeren in Umgebungsvariablen, Streamlit Secrets oder die lokale
Konfiguration. Sie werden nicht in das Repository geschrieben.

## Lokaler Start

```powershell
$env:API_FOOTBALL_KEY="..."
$env:TELEGRAM_BOT_TOKEN="..."
$env:TELEGRAM_CHAT_ID="..."
python red_card_bot.py
```

Der Stand bereits verarbeiteter Karten liegt lokal in `alerted_cards.json`.
Ein Eintrag wird erst nach erfolgreicher Zustellung gespeichert und nach 24
Stunden verworfen.

## Modellgrenzen

- Die Rotkartenmultiplikatoren sind explizite Priors, keine validierten Effekte.
- Endstaende werden aus aktuellem Spielstand und Poisson-verteilten Resttoren
  berechnet.
- Live-xG wird nur verwendet, wenn beide Teamwerte vorhanden und numerisch sind.
- Fehlende Statistiken werden als `n/a` behandelt, nicht als beobachtete Null.
- Die Ausgabe ist ein Modell-Signal. Ohne kalibriertes Modell und verifizierte
  Marktquote gibt es keine Value-, EV- oder Einsatz-Aussage.

## Betrieb

API- und Telegram-Antworten koennen ausfallen oder verzoegert sein. Der Prozess
sollte ueberwacht werden; API-Fehler muessen sichtbar bleiben. Bei GitHub Actions
ist der Mindestintervall des Schedulers nicht fuer sekundennahe Live-Alarme
geeignet. Fuer kontinuierliche Ueberwachung ist ein dauerhaft laufender Prozess
erforderlich.
