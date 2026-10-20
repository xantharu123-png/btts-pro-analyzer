# Vorlage: Datenschutzerklärung (BetBoy)

**Status: Vorlage mit Platzhaltern. Kein Rechtsrat.** Alle Felder in eckigen
Klammern `[PLATZHALTER …]` muss der Owner selbst ausfüllen; die technischen
Angaben unten beschreiben, was der Code heute tut, und sind vor der
Veröffentlichung gegen den tatsächlichen Betrieb (Hosting, Logs, Mail,
Zahlungsanbieter) zu verifizieren. Der fertige Text ist von einer Anwältin
oder einem Anwalt mit Schweizer Zulassung zu prüfen. Massstab ist das
Bundesgesetz über den Datenschutz (DSG, in Kraft seit 1. September 2023) mit
der Datenschutzverordnung (DSV); für Kundinnen und Kunden in der EU/EWR kann
zusätzlich die DSGVO anwendbar sein (prüfen lassen).

Die veröffentlichte Seite wird über `BETBOY_PRIVACY_URL` (App und Portal)
verlinkt. Solange die Variable fehlt, zeigt die App ehrlich
«Anbieterinformationen und Datenschutz: noch nicht veröffentlicht».

---

## Datenschutzerklärung

### 1. Verantwortliche Stelle

[PLATZHALTER Firma oder Name]
[PLATZHALTER Strasse und Nummer, PLZ Ort, Schweiz]
E-Mail: [PLATZHALTER Datenschutz-Kontaktadresse]

[PLATZHALTER: Datenschutzberater/-in nach Art. 10 DSG, falls bestellt; sonst
Absatz streichen. Vertretung in der EU nach Art. 14 DSG / Art. 27 DSGVO, falls
erforderlich – prüfen lassen.]

### 2. Was BetBoy ist

[PLATZHALTER kurze Beschreibung, identisch mit den Anbieterinformationen.]
Zugelassen ab 18 Jahren. BetBoy nimmt [PLATZHALTER: keine Wetten an und
führt keine Geldspiele durch – nur wenn das zutrifft].

### 3. Welche Daten wir bearbeiten und wozu

**3.1 Kundenkonto im Portal** (nur wenn der Kundenzugang aktiv ist)

- E-Mail-Adresse, Passwort (nur als Hash gespeichert), gewählte Sprache,
  akzeptierte AGB-Version, Zeitpunkt der Registrierung.
- Zweck: Vertragserfüllung (Login, Abo), Pflichtkommunikation per E-Mail
  (Bestätigung, Passwort-Zurücksetzen, Rechnungen).
- Aufbewahrung: [PLATZHALTER Frist nach Kündigung].

**3.2 Abo und Zahlung**

- Abo-Plan, Status, Laufzeit, Zahlungsereignisse (Referenznummern des
  Zahlungsanbieters). Kartendaten werden nicht bei uns gespeichert, sondern
  beim Zahlungsanbieter [PLATZHALTER Stripe Payments Europe, Ltd. (Irland)
  oder tatsächlicher Anbieter; Sitz und Datenübermittlung ins Ausland
  prüfen lassen].
- Zweck: Vertragsabwicklung, Buchführung (gesetzliche Aufbewahrungspflicht
  [PLATZHALTER 10 Jahre nach OR prüfen]).

**3.3 Nutzung der App**

- Ohne Kundenkonto («persönlicher Modus»): Die App legt im Browser eine
  zufällige Kennung (`betboy_account_identity`, Local Storage) ab, damit
  gespeicherte Tipps, Guthaben der 15K-Challenge und Daily3-Einträge beim
  nächsten Besuch wiedergefunden werden. Diese Kennung ist keine Person,
  sondern ein Browser; sie verlässt den Server nicht.
- Mit Kundenkonto: Dieselben Daten werden dem Konto zugeordnet; die
  Zuordnung erfolgt über das Sitzungs-Cookie des Portals (siehe 4).
- Gespeicherte Inhalte: eigene Tipps, Einsätze und Ergebnisse, die du selbst
  einträgst (Daily3, 15K, «Meine Tipps»). Zweck: die Funktion, die du nutzt.
- Aufbewahrung: [PLATZHALTER; heute: bis zur Löschung durch den Owner].

**3.4 Server-Protokolle**

[PLATZHALTER: Welche Zugriffsprotokolle der Reverse Proxy (Caddy) und das
Betriebssystem schreiben (IP-Adresse, Zeitpunkt, aufgerufene Adresse,
Browser), wie lange sie aufbewahrt werden und wozu (Betriebssicherheit,
Fehlersuche, Abwehr von Angriffen). Vor Veröffentlichung auf dem Server
prüfen.]

**3.5 E-Mail**

[PLATZHALTER Mailanbieter (SMTP-Dienst), Sitz, Vertrag zur
Auftragsbearbeitung. Betrifft nur Portal-Mails.]

### 4. Cookies und Browser-Speicher

| Name | Art | Zweck | Dauer |
|---|---|---|---|
| `betboy_customer` | Cookie (HttpOnly, Secure) | Sitzung im Kundenportal und Zugang zur App | 12 Stunden |
| `csrftoken` | Cookie | Schutz von Formularen im Portal vor Fälschung | [PLATZHALTER prüfen] |
| `betboy_account_identity` | Local Storage | Browser-Kennung für gespeicherte Tipps im persönlichen Modus | bis zum Löschen der Website-Daten |
| [PLATZHALTER] | Streamlit-eigene Cookies/Storage | [PLATZHALTER prüfen, z. B. Sitzung, Sprache] | [PLATZHALTER] |

Es werden [PLATZHALTER: keine Tracking- oder Werbe-Cookies] gesetzt. Es gibt
[PLATZHALTER: keine Webanalyse / folgende Webanalyse …].

### 5. Weitergabe an Dritte und ins Ausland

- Hosting: [PLATZHALTER Anbieter, Land des Rechenzentrums, Vertrag zur
  Auftragsbearbeitung].
- Zahlungsanbieter: [PLATZHALTER, siehe 3.2].
- E-Mail-Versand: [PLATZHALTER, siehe 3.5].
- Sportdatenquellen: Die App ruft Spielpläne, Ergebnisse und Quoten von
  Datenanbietern ab. Dabei werden [PLATZHALTER: keine personenbezogenen
  Nutzerdaten] an diese Anbieter übermittelt – prüfen.
- Übermittlung ins Ausland nur [PLATZHALTER Grundlage nach Art. 16 f. DSG:
  Staat mit angemessenem Schutz oder Standardvertragsklauseln].

### 6. Rechtsgrundlagen

[PLATZHALTER: Nach DSG ist eine Rechtsgrundlage nur für Bearbeitungen durch
Bundesorgane nötig; private Bearbeitung muss die Grundsätze (Art. 6 DSG)
einhalten und darf die Persönlichkeit nicht widerrechtlich verletzen. Für
DSGVO-Anwendbarkeit: Art. 6 Abs. 1 lit. b (Vertrag), lit. c (gesetzliche
Pflicht), lit. f (berechtigtes Interesse) ergänzen – prüfen lassen.]

### 7. Deine Rechte

Du hast das Recht auf Auskunft (Art. 25 DSG), Berichtigung, Löschung,
Datenherausgabe bzw. -übertragung (Art. 28 DSG) sowie das Recht, einer
Bearbeitung zu widersprechen. Anfragen an: [PLATZHALTER Kontaktadresse].
Aufsichtsbehörde in der Schweiz ist der Eidgenössische Datenschutz- und
Öffentlichkeitsbeauftragte (EDÖB). [PLATZHALTER: Für EU-Betroffene
zusätzlich Beschwerderecht bei der zuständigen Aufsichtsbehörde.]

### 8. Datensicherheit

[PLATZHALTER kurz und wahr: Transportverschlüsselung (TLS), Zugriff nur für
berechtigte Personen, Passwörter nur als Hash, Server in der Schweiz / im
Ausland … Keine Versprechen, die nicht eingehalten werden.]

### 9. Minderjährige

Das Angebot richtet sich ausschliesslich an Personen ab 18 Jahren.
[PLATZHALTER: Wie Altersangaben geprüft werden, falls überhaupt.]

### 10. Änderungen

Diese Erklärung kann angepasst werden; es gilt die auf dieser Seite
veröffentlichte Fassung. Stand: [PLATZHALTER Datum]

---

## Checkliste für den Owner (vor Veröffentlichung)

Eintragen:

1. Verantwortliche Stelle mit Adresse und Datenschutz-Kontakt (identisch mit
   den Anbieterinformationen).
2. Hosting-Anbieter, Rechenzentrumsland, Mailanbieter, Zahlungsanbieter –
   jeweils mit Vertrag zur Auftragsbearbeitung (Art. 9 DSG).
3. Tatsächliche Protokollierung (Reverse Proxy, Betriebssystem, Streamlit)
   und Aufbewahrungsfristen – auf dem Server nachsehen, nicht raten.
4. Welche Cookies und Speicher die Seiten tatsächlich setzen (im Browser
   prüfen; die Tabelle oben ist der Stand aus dem Code).
5. Aufbewahrungsfristen für Konto, Abo, Buchhaltung und App-Daten.
6. Datum des Standes.

Juristisch prüfen lassen:

- Anwendbarkeit der DSGVO auf EU-Kundschaft (Art. 3 Abs. 2 DSGVO) und ob
  eine EU-Vertretung nötig ist; Umfang der Informationspflicht nach
  Art. 19 DSG.
- Grundlage für Auslandübermittlungen (Art. 16 f. DSG) je Anbieter.
- Formulierung der Betroffenenrechte und der Sicherheitsangaben.
- Ob für Wett-/Geldspielnähe besondere Pflichten gelten (Jugendschutz,
  Spielsuchtprävention) und ob ein Verzeichnis der Bearbeitungstätigkeiten
  (Art. 12 DSG) geführt werden muss.
- Konsistenz mit AGB und Anbieterinformationen.

Technisch nach der Veröffentlichung:

- `BETBOY_PRIVACY_URL` (zusammen mit `BETBOY_LEGAL_URL` und
  `BETBOY_TERMS_URL`) in `/etc/betboy/betboy.env` und `/etc/betboy/portal.env`
  setzen; im Portal zusätzlich `BETBOY_LEGAL_READY=1`.
