# Plan: BetBoy in den Google Play Store

Stand 10.11.2026. Owner-Auftrag: Impressum und Rechtsseiten über die Website bmmestudios.com, dazu ein App-Icon und
ein Plan, wer was macht. Dieser Plan ändert noch keinen Code und keine Website.

## Ausgangslage

- **bmmestudios.com:** Die Website (Projekt `C:\Projekt\BmmeStudios`) ist schon die Heimat aller BMME-Apps. Jede
  App bekommt dort:
  - eine Produktseite, eine Support-Seite und eine Datenschutzerklärung;
  - bei Bedarf Nutzungsbedingungen.
  - Das Impressum gilt für die ganze Website (`/legal/`).
  - Die Postfächer `support@`, `privacy@` und `legal@bmmestudios.com` laufen.
- **Rechtshinweise in BetBoy:** Die App liest die drei Links aus `BETBOY_LEGAL_URL`, `BETBOY_PRIVACY_URL` und
  `BETBOY_TERMS_URL` (`legal_notice.py`). Solange sie fehlen, sagt der Footer „noch nicht veröffentlicht“. 18+ und
  die Hilfe bei Spielsucht (SOS Spielsucht, Sucht Schweiz) stehen schon im Footer.
- **Google Play:** Eine reine Tipp-App ist ein Graubereich. Erlaubt ist sie nur ohne Wetten in der App, ohne Links
  zu Wettanbietern und ohne Glücksspielwerbung. Die App zeigt keine Buchmacherquoten, das passt dazu.
- **Ehrlichkeit:** Die Tipps schlagen den Buchmacher bisher nicht: Treffer etwa 59 %, Marktvergleich 0 von 112.
  Store-Texte und Website versprechen deshalb keinen Gewinn.
- **Bereits geprüft:** Open-Meteo wird im App-Code nicht verwendet. Im Code liegen keine Schlüssel. Die alten
  Schlüssel stehen aber noch in der öffentlichen Git-Historie (Audit K1).

## Phase 0: Entscheide (Owner)

| Frage | Vorschlag |
|---|---|
| Icon | Entwurf 1 „Chance-Ring“: weisser Ball in einem zu 70 % gefüllten Ring auf BetBoy-Grün `#16784b`. Alternativen: „Datenbalken“, „Mittelkreis“. Dateien: `output/betboy-store-20261110/icon-entwurf-*.svg` |
| Name im Store | „BetBoy“ bleibt. Wegen „Bet“ prüft Google genauer, das ist in Ordnung. |
| Preis | kostenlos, ohne Werbung, ohne Käufe. Glücksspielwerbung ist in Tipp-Apps ohnehin verboten. |
| Adresse der App | `betboy.bmmestudios.com` statt `vps-a30a123f.vps.ovh.net`, weil sie zur Marke passt und die Android-App sie bestätigen muss |
| Entwicklerkonto | das bestehende Konto von Odzak und Iri. Zu klären: privates Konto oder Organisation. Bei einem privaten Konto braucht jede neue App vor der Freigabe einen geschlossenen Test mit 12 Testern während 14 Tagen. |

## Phase 1: Rechtsseiten auf bmmestudios.com

Gearbeitet wird im Projekt BmmeStudios, nicht in BetBoy. Dort läuft die Session „BMME Studios Website Design“.
Damit nicht zwei gleichzeitig an `content/apps.mjs` schreiben, liefert BetBoy Texte und Fakten, und die Website-Seite
trägt sie ein.

1. **Eintrag `betboy` in `content/apps.mjs`:**
   - Felder: `kind: "app"`, Genre „Football predictions“, `status: "test"`, Plattformen Android und Web, Farbe
     `#16784b`, Icon `betboy.svg`.
   - Beschreibung ehrlich: Die App zeigt Modellchancen, sie verspricht keinen Gewinn und ist erst ab 18.
2. **Datenschutz `/betboy/privacy/`:** abgeleitet aus dem BetBoy-Code. Ich liefere diese Fakten, nach Prüfung im
   Code:
   - Serverstandort (OVH-VPS, Land bestätigen) und Zugriffsprotokolle von Caddy (IP-Adresse, Zeit, Aufbewahrung).
   - Cookies von Streamlit (Sitzung, XSRF-Schutz). Kein Konto im persönlichen Modus, keine Analyse, keine Werbung,
     keine Push-Nachrichten.
   - Bilder von Dritten: Spielerfotos über Wikimedia, Logos über NHL-Server. Werden sie direkt im Browser geladen,
     geht die IP-Adresse an diese Server. Prüfen; wenn ja, nennen oder über den eigenen Server ausliefern.
   - Datenquellen der Prognosen (API-Football und weitere). Dorthin gehen keine Nutzerdaten.
3. **Nutzungsbedingungen `/betboy/terms/`:**
   - Erst ab 18. Keine Wettberatung und keine Gewinngarantie. Modellwerte sind Schätzungen.
   - Keine Verbindung zu Wettanbietern. Hinweis auf Hilfe bei Spielsucht. Schweizer Recht.
   - Vorlage sind die Odzak-Bedingungen.
4. **Support-FAQ:**
   - Was bedeutet die Modellchance?
   - Warum keine Quoten?
   - Wie oft wird aktualisiert?
   - Wo melde ich Fehler (`support@`)?
5. **Website hochladen:** Das macht der Owner mit `npm.cmd run deploy`, denn dafür braucht es das FTP-Passwort.
6. **Links in BetBoy setzen:** in `/etc/betboy/betboy.env`, danach die App neu starten. Das ist ein Release-Schritt
   und braucht Owner-OK.
   - `BETBOY_LEGAL_URL=https://bmmestudios.com/legal/`
   - `BETBOY_PRIVACY_URL=https://bmmestudios.com/betboy/privacy/`
   - `BETBOY_TERMS_URL=https://bmmestudios.com/betboy/terms/`

## Phase 2: Sicherheit und Rechte (Owner und Claude)

- **Owner:** die alten API-Schlüssel beim Anbieter sperren oder neu ausstellen (Audit K1, „Widerruf unbewiesen“).
- **Claude:** prüfen, ob die API-Football-Bedingungen eine öffentliche Anzeige der Daten in einer App erlauben.
- **Claude:**
  - Bildrechte prüfen: Wikimedia-Fotos brauchen die Namensnennung nach Lizenz, NHL-Logos sind Marken.
  - Was nicht sauber ist, fällt in der öffentlichen Version weg.
- **Claude:**
  - Prüfen, dass das Öffnen der App keine API-Abrufe auslöst.
  - Prüfen, dass der VPS mehrere gleichzeitige Nutzer trägt.

## Phase 3: Technik (Claude, BetBoy, jeder Schritt per PR, Release nur mit OK)

1. **Subdomain:**
   - DNS-Eintrag `betboy.bmmestudios.com` auf die VPS-Adresse. Das macht der Owner bei hosttech, ich gebe den
     genauen Eintrag vor.
   - Caddy holt das Zertifikat und leitet zur App weiter.
2. **Digital Asset Links:**
   - Caddy liefert `/.well-known/assetlinks.json` aus. Damit bestätigt die Website die Android-App, und die App läuft
     ohne Adressleiste.
   - Dazu kommt ein Web-Manifest (Name, Icons 192/512 und maskierbar, Farbe `#16784b`).
3. **Android-Hülle (Trusted Web Activity):**
   - Bau mit Bubblewrap, Paketname `com.bmmestudios.betboy`.
   - Upload-Schlüssel erzeugen. Der Owner bewahrt ihn sicher auf, Google signiert mit „Play App Signing“.
   - Ergebnis: eine signierte AAB-Datei.
4. **Handy-Prüfung:** Die Oberfläche wird auf einem kleinen Bildschirm geprüft. Hinweise auf Wettanbieter oder
   „jetzt setzen“ darf es nicht geben.
5. **Icon:**
   - Icon für den Store: 512 × 512 PNG ohne eigene Rundung, Google rundet selbst.
   - Launcher-Icon für Android mit Vorder- und Hintergrund.
   - 256er-Icon für bmmestudios.com und Favicon für die Web-App.

## Phase 4: Store-Eintrag (Owner in der Play Console, Texte von Claude)

- App anlegen, Kategorie Sport.
- Kurzbeschreibung und Beschreibung: ehrlich, ohne Gewinnversprechen, mit 18+ und Spielsucht-Hinweis.
- Grafiken: Icon 512, Feature-Grafik 1024 × 500, mindestens zwei Handy-Screenshots.
- Datensicherheit-Formular, ausgefüllt nach der Datenschutzerklärung.
- Inhaltsfragebogen mit Glücksspielbezug, Zielgruppe ab 18.
- Geschlossener Test, bei einem privaten Konto 12 Tester während 14 Tagen. Danach Antrag auf Produktion. Google prüft
  dann einige Tage.

## Reihenfolge und Dauer

| Schritt | Wer | Dauer |
|---|---|---|
| Phase 0 Entscheide | Owner | sofort |
| Phase 1 Texte und Fakten | Claude, danach Website-Projekt | 1 Tag |
| Phase 1 Website hochladen, Links setzen | Owner, Claude | ½ Tag |
| Phase 2 Schlüssel sperren | Owner | ½ Stunde |
| Phase 2 Rechte prüfen | Claude | ½ Tag |
| Phase 3 Technik | Claude, DNS-Eintrag Owner | 1–2 Tage |
| Phase 4 Store und Test | Owner, Texte Claude | 14 Tage Test und Google-Prüfung |

Phase 1 und 2 können gleichzeitig laufen. Phase 3 braucht das gewählte Icon, Phase 4 alle Phasen davor.

## Risiken

- **Google könnte die App als Glücksspiel-Begleitapp ablehnen.** Dagegen helfen:
  - keine Links und Quoten, keine Werbung;
  - 18+, klare Hinweise und ehrliche Texte.
  - Im Zweifel vorher beim Play-Support nachfragen.
- **Streamlit im Store:** Die App ist eine Webseite in einer Hülle und braucht Internet. Google erlaubt das bei
  Trusted Web Activities. Die Oberfläche muss sich auf dem Handy aber wie eine App anfühlen.
- **Rechtstexte:** Sie werden sorgfältig aus dem Code abgeleitet, sind aber keine Rechtsberatung. Für eine
  Glücksspiel-nahe App ist eine Prüfung durch eine Fachperson sinnvoll.
