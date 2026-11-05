# Wettfinder: Mindest-Modellchance per Schieberegler

Datum: 05.11.2026. Anlass: Im Wettfinder stand „Bayer Leverkusen über 2,5 Teamtore“ mit 29,2 % Modellchance. Der
Wettfinder hatte keine Untergrenze für die Modellwahrscheinlichkeit: Eine Auswahl erschien, wenn das Modell den Markt
gut belegt und die Quote über 1,20 lag. Im Tagespool lagen 52 von 391 Prognosen unter 40 % und 51 zwischen 40 und
50 % (`output/check-20261104/leverkusen_why*.log`).

Owner-Entscheid „ich möchte den filter selber wählen können … schiebe regel“:

- Oben auf der Wettfinder-Seite, unter den Sportarten, steht der Regler „Mindest-Modellchance (%)“: 0–95 %, Schritte
  zu 5 %, Startwert 50 % (`WETTFINDER_MIN_CHANCE_DEFAULT`).
- Er gilt für die Spiele und die Tennisbox. Verglichen wird die angezeigte, auf eine Nachkommastelle gerundete Zahl;
  eine unbekannte Wahrscheinlichkeit besteht keine Grenze.
- Wie der Sportfilter wirkt er erst nach der Kohärenzprüfung (`compose_wettfinder_catalog(min_probability=…)`). Er
  wählt nie eine andere Richtung und verändert keine Karte.
- Doublebet behält seine eigene Regel (Quote um 2,00, wahrscheinlichste Folge) und ist nicht betroffen.
- Das Protokoll der angezeigten Tipps (`record_signal_catalog("wettfinder_automatic", …)`) bleibt ungefiltert wie
  bisher, damit Auswertungen nicht von einem Regler abhängen.
- Ist bei der gewählten Grenze nichts übrig, sagt die Seite „Keine Auswahl ab X % Modellchance. Regler nach links
  schieben, um mehr zu sehen.“

Wirkung am 5.11. (Tagespool, nur lesend, `output/check-20261104/prob_floor_games.log`): ohne Grenze 85 Spiele mit 323
Auswahlen, ab 50 % 83 Spiele mit 221, ab 60 % 63 Spiele mit 148.

Tests: `tests/test_wettfinder_min_chance.py`, darunter ein Lauf mit dem echten Streamlit-Regler (Startwert 50, bei
25 % erscheint das 29-%-Spiel wieder).
