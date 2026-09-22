# Blockzuweisung: In welchen Block kommen die Exportcontainer? – Streamlit-Demo

**[→ Demo live ausprobieren](https://sebastianhanisch-blockzuweisung-demo.streamlit.app/)**

Interaktive Fall-Demo zur **Blockzuweisung im Export** eines Containerterminals: Welche Exportcontainer eines Schiffs kommen in welchen Block des Lagers? Ein Block nah am Liegeplatz hält den **Fahrweg** der Horizontaltransporter kurz,
aber seine Blockkräne liefern nur so viele Moves je Stunde, wie sie schaffen; verteilt man die Container auf mehrere Blöcke, sinkt die **Wartezeit am Block** und der Weg wächst. Die Demo beantwortet: **Wie viel Fahrweg kostet es,
die Container so zu verteilen, dass die Blockkräne auch bei verspäteten Schiffen nicht zum Nadelöhr werden?**

Teil des Portfolios für die Website „Sebastian Hanisch – Operations Research und Machine Learning“, Zusatz zur Hafen-Linie (koppelt Kai: Schiffskräne rufen ab, Block: Blockkräne liefern, Kran: Fahrweg zum Schiff; setzt die
Kaiplatz-Planung als gegeben voraus und ersetzt weder die Stapelplanung im einen Block noch die Fahrzeug-Disposition). Sechs Verfahren, davon zwei **exakt gerechnet** (lineares Programm, OR-Tools GLOP), auf denselben Wochen verglichen.

## Warum dieses Problem

Naheliegend wäre die Geschichte „Bündeln spart Weg, Verteilen gleicht die Last aus, dazwischen liegt ein Kompromiss“. Gemessen trägt sie **nur an den Rändern**: Bündeln kostet 228 m und im Mittel **1907 min** Wartezeit je Container
(ein Schiff ruft 60 bis 90 Moves/h ab, ein Block schafft 40), Verteilen 457 m bei 0,5 min. Dazwischen liegt eine **sehr scharfe Kante**: Wartezeit null kostet nur 36 m mehr als das Bündeln (16 %), und ein Rechenplan erreicht sie. Dort
gibt es weder einen Zielkonflikt noch ein Knie. Tragend ist etwas anderes, die **Robustheit**: der wartefreie Plan füllt die Blöcke in den Überlappungen der Beladefenster bis an die Grenze und zerbricht, wenn die Schiffe zu anderen
Zeiten kommen (Wartezeit 0,5 auf 46 min bei Verspätung σ = 3 h). Ein Rechenplan, der die Verspätungen mitplant, kostet 24 bis 44 m Fahrweg (9 bis 17 %) und senkt die Wartezeit bei Verspätung auf 13 bis 10 min; keine geprüfte einfache Regel
liegt auf dieser Kurve. Die Demo fragt deshalb nach dem **Preis der Absicherung in Metern**.

Das Muster „der exakte Plan ist nicht robust“ kennt das Portfolio schon aus der Fahrzeugflotte-Demo und der Robusten Kaiplatzplanung; hier unterscheidet es sich durch einen **exakt gerechneten abgesicherten Plan** (Szenario-LP) und einen
bezifferten Preis in Metern.

## Modell

Flüssigkeitsmodell in Stundenschritten. *B* Blöcke im Abstand von 100 m am Kai (Regler 6 bis 10), jeder mit einer Abrufrate μ (Moves je Stunde, alle Blockkräne zusammen; Regler 30 bis 60); *S* Schiffe (3 bis 8) mit 700 bis 1300
Exportcontainern, drei Liegeplätze, Beladefenster in ganzen Stunden; das Schiff ruft seine Container gleichmäßig über das Fenster ab (mit r oder zwei Dritteln von r Moves/h, r = 60 / 90 / 120). **Fahrweg** *d* = 200 m + Abstand Block–Liegeplatz.
Dieselben Container kommen gleichmäßig in den **36 Stunden vor dem Fenster** im Lager an und belasten den Block ebenfalls (ein Move je Container; Annahme, fest). Was der Block nicht schafft, wartet als Rückstand (FIFO):
*q<sub>t</sub>* = max(0, *q<sub>t−1</sub>* + Last − μ). Kennzahlen: mittlerer **Fahrweg** je Container, mittlere **Wartezeit** je Container am Block (min), **Beladeverzug** je Schiff, **Container über der Lagergrenze** (Lagerfüllung im
Spitzenbestand 50 bis 90 %). **Verspätung:** das Beladefenster jedes Schiffs verschiebt sich um gerundet N(0, σ²) Stunden (σ 0 bis 6 h); die Wartezeit „bei Verspätung“ ist das Mittel über 30 Testszenarien, geplant wird mit 10 anderen.
Fahrweg (m) und Wartezeit (min) werden nicht zu einer Zahl vermischt; der Preis λ (Meter je Minute) wählt nur den Punkt auf der Kurve. Formal im Expander „📐 Mathematische Formulierung“.

## Methodik – sechs Verfahren

Alle Verfahren arbeiten dieselbe Woche ab; Referenz aller Deltas ist **Kranrate passend** (so wird von Hand geplant, wenn man die Kranrate kennt).

- **🏗️ Bündeln:** alle Container eines Schiffs in den nächsten Block (bei vollem Lager in den nächsten, in Portionen zu 10). Der Rand „kürzester Weg“.
- **⚖️ Verteilen:** gleichmäßig auf alle Blöcke. Der Rand „keine Wartezeit“.
- **🎚️ Kranrate passend:** so viele nächste Blöcke, wie Abrufrate des Schiffs durch Blockrate verlangt (aufgerundet), reihum; volle Blöcke werden übergangen.
- **🧮 Gierig:** Schiff für Schiff nach Beginn des Fensters, je 10 Container in den nächsten Block, dessen Spitzenauslastung unter 80 % bleibt (sonst der mit der kleinsten): die schiffsweise Regel mit Reserve.
- **🎯 Gerechnet:** lineares Programm über die ganze Woche, minimale Wartezeit für pünktliche Schiffe, bei Gleichstand der kürzeste Weg (lexikographisch: der Zielwert ist eindeutig).
- **🛡️ Gerechnet und abgesichert:** Szenario-LP mit 10 Verspätungsszenarien, minimiert Fahrweg + λ · mittlere Wartezeit über die Szenarien.

Der Löser ist **OR-Tools GLOP** (Simplex, ohne Zeitlimit): das Optimum ist bewiesen und der Zielwert hängt nicht vom Rechner ab; bei mehreren gleichwertigen Plänen kann die *Aufteilung* zwischen Löserversionen abweichen, deshalb prüfen Tests und
Preset-Kriterien Zielwerte und Kennzahlen mit Abstand, nie die Aufteilung. Der LP-Plan wird nach dem Verfahren der größten Reste auf ganze Container gerundet (Zielwert im Mittel 0,8 %, höchstens 3 % darüber), der LP-Wert bleibt als Schranke sichtbar.
Live rechnet die App nur die eingestellte Woche mit allen sechs Verfahren (etwa 0,7 s); die **Kurve** (sieben Szenario-LP, etwa 4 s) und die **Stichprobe** (20 Wochen, etwa 15 s, Fortschrittsbalken) laufen hinter je einem Knopf.

## Befunde (gemessen, keine Behauptungen)

8 Blöcke, 6 Schiffe, Blockrate 40, Schiffe bis 90 Moves/h, Lagerfüllung 70 %, σ = 3 h. Zahlen aus der Vorab-Messreihe (`hafen-planung/messreihe_blockzuweisung/ERGEBNIS.md`, 20 Wochen ohne Lagergrenze). **Im Code dieser Demo nachgerechnet und als Test
festgehalten** (`tests/test_evaluation.py`, Mittel über die Seeds 0 bis 19 auf 0,01 m bzw. 0,01 min für die Regeln, mit Abstand für die von der LP-Aufteilung abhängige Wartezeit bei Verspätung) sind: die Ränder, die Kante, Kranrate passend,
Gierig 80 %, der wartefreie und der abgesicherte Plan für λ = 10, die Befunde „ohne Anlieferlast“ und „Lagergrenze bei 90 %“ sowie die Prüfungen der Rechnung. Alle übrigen Zahlen (die Kurve für andere λ, die einfache Reserve, die gepaarten
Vergleiche, die Empfindlichkeit gegen σ und die Zahl der Szenarien) stammen unverändert aus der Messreihe und sind in dieser Demo nicht nachgerechnet.

| Frage | Befund |
|---|---|
| **Stimmt die Rechnung?** | LP-Zielwert gegen eine unabhängige Nachrechnung der Rückstands-Rekursion: Abweichung unter 10⁻⁹; Kleinstinstanzen (3 × 3, 3 bis 5 Container): LP-Schranke ≤ ganzzahliges Optimum (vollständiges Durchprobieren; in der Messreihe zusätzlich gleich dem SCIP-MIP, 36 Fälle, 0 Abweichungen); Grenzfälle (ein Block, unbegrenzte Rate, σ = 0) treffen; Rundung des Plans höchstens +4 % im Zielwert (Messreihe 3,04 %). |
| **Wo liegen die Ränder?** | Bündeln 228,2 m und 1907 min; Verteilen 457,3 m und 0,50 min (pünktlich). |
| **Wo liegt die Kante?** | Kürzester Weg unter erlaubter Wartezeit 400 / 100 / 20 / 5 / 1 min: 239,5 / 250,6 / 257,3 / 261,4 / 263,8 m (kleinstmögliche Wartezeit 0,50 min): **+36 m (+16 %) gegen Bündeln, 193 m (−42 %) gegen Verteilen**. |
| **Was bringt Rechnen?** | Kranrate passend: 263,4 m, 43,9 min pünktlich; Rechenplan 264,2 m, 0,50 min; Gierig 80 %: 347 m, 9,1 min. |
| **Ist der wartefreie Plan robust?** | Nein: Wartezeit bei Verspätung 46,0 min (Kranrate passend 72,8; Gierig 100 / 80 / 60 %: 68,2 / 27,8 / 10,2; Verteilen 4,0). |
| **Was kostet die Absicherung?** | Szenario-LP mit λ = 1 / 2 / 5 / 10 / 20 / 50 / 100: 268 / 274 / 288 / 308 / 329 / 356 / 373 m bei 20,8 / 16,8 / 12,6 / 9,5 / 7,5 / 5,7 / 5,2 min (Standardfehler 1,1 bis 2,2). Knie bei λ ≈ 5 bis 10: **+24 m (+9 %) bringen die Wartezeit bei Verspätung auf 12,6 statt 46,0 min, +44 m (+17 %) auf 9,5 min**. |
| **Reicht eine einfache Reserve?** | LP mit auf 90 / 80 / 70 % gekürzter Blockrate geplant: 278 m 24,1 min / 296 m 21,4 min / 306 m 43,3 min: schlechter als der Szenario-LP bei gleichem Weg (Messreihe). |
| **Liegt eine Regel auf der Kurve?** | Nein. Gepaart gegen den Szenario-LP bei gleichem Weg: Wartezeit bei Verspätung Kranrate passend +37,8 ± 8,0 min, Gierig 100 / 80 / 60 % +60,5 / +21,2 / +4,6 min; bei gleicher Wartezeit ist der LP-Weg 6 bis 84 m kürzer (Messreihe). |
| **Sind schiffsweise Regeln kurzsichtig?** | Ja, aber nur unter der Annahme der Anlieferlast (siehe unten). Eine gierige Regel, die jeden 20er-Posten nach dem Zuwachs von Weg + λ · Wartezeit über dieselben Szenarien legt, liegt im Zielwert 27 % bis 130 % über dem LP (Messreihe, 10 Wochen; **in dieser Demo nicht enthalten und nicht nachgerechnet**). |
| **Was, wenn das Lager voll ist?** | Bei 90 % Füllung verletzen Bündeln, Kranrate passend und Gierig die Lagergrenze in 30 / 23 / 21 von 30 Wochen (Test), Verteilen und die Rechenpläne nie; bei 91 % Füllung ist der Rechenplan der einzige zulässige Plan mit kurzem Weg (Messreihe: Kranrate passend 287,6 m mit 125,7 min Wartezeit, Verteilen 456,7 m). |
| **Was, wenn σ falsch geschätzt ist?** | Plan für σ = 3 h, getestet bei σ = 1,5 / 3 / 5 h: 2,5 / 7,5 / 15,3 min; ein Plan für σ = 5 h bei σ = 3 h: 361 m, 5,9 min: teurer, sicherer (Messreihe). |
| **Rechenzeit** | Gerechnet 0,02 s; abgesichert mit 10 Szenarien 0,3 bis 0,8 s; eine Woche mit allen sechs Verfahren und 30 Testszenarien 0,7 s; Stichprobe von 20 Wochen 15 s. |
| **Presets** | Ein gemeinsamer Seed (**2017**) für alle fünf; jede Kennzahl zwischen dem 5. und 95. Perzentil der Grundgesamtheit. Von 60 Kandidaten tragen 17 alle fünf Geschichten (`tools/PRESET_SWEEP.md`). |

## Ehrliche Grenzen

- **Die Aussage „schiffsweise Regeln liegen über dem Rechenplan“ gilt nur mit Anlieferlast.** Ohne die Anlieferung der Exportcontainer in den Tagen vor der Beladung trifft die einfache Regel „nächster Block mit Luft“ den Rechenplan in **30 von 30**
  Wochen; mit ihr (Annahme, 36 h) in **0 von 30** (Weg im Mittel +23 %, Wartezeit 35 gegen 0,3 min). Beides ist als Test festgehalten. Bei 12 h Vorlauf ist das Lager schon durch die Anlieferung überlastet (W ≥ 106 min bei jedem Plan); bei 24 und
  48 h bleibt die Rangfolge (Messreihe).
- **Flüssigkeitsmodell:** gleichmäßiger Abruf, Blöcke arbeiten unabhängig; ein Rückstand bremst den Schiffskran nicht zurück (das ist eine **Untergrenze** der echten Kopplung zwischen Kran und Block).
- **Suchaufwand und Umstapeln im Block sind nicht modelliert:** der Bündelungsvorteil ist hier allein der Fahrweg (im Modell höchstens etwa 13 % zwischen den Rändern).
- Fahrweg einfach, ohne Stau (der Fahrzeugbedarf folgt daraus, ist aber nicht gerechnet; Verweis auf die Fahrzeugflotte-Demo); alle Blöcke gleich; Container austauschbar (keine Typen, Gewichte, Kühl- oder Gefahrgutcontainer).
- Anlieferprofil (gleichmäßig in 36 h) und Blockrate sind **Annahmen**, keine Echtdaten; Verspätung nur als Verschiebung des Fensters, nicht als Dehnung; der Plan wird vor der Anlieferung fest gewählt (keine Neuplanung).
- Der abgesicherte Plan ist eine Schätzung aus zehn Planungsszenarien (3 / 5 / 10 / 20 Szenarien: 13,5 / 9,7 / 7,5 / 6,7 min Wartezeit bei Verspätung, Rechenzeit 0,16 / 0,30 / 0,61 / 1,53 s, Messreihe); Überanpassung an die Planungsszenarien
  ist als Abstand zwischen Planungs- und Testszenarien sichtbar (getrennte Zufallszahlen).
- Alle Zahlen sind **Größenordnungen aus einer Simulation, keine Messung an einem echten Terminal**.

## Design-Entscheidungen und Funde

**Erst den richtigen Modellbereich finden, und der Erstversuch lag im falschen Modell.** Ohne Anlieferlast ließ die einfache Regel den Rechenplan in 30 von 30 Wochen bitgleich gewinnen: „exakt gegen Regel“ wäre langweilig gewesen (wie in der
Fahrzeugflotte-Demo). Die Anlieferlast belegt die Blockkräne schon Tage vor der Beladung; sie steht als sichtbare Annahme im Text und im Warnhinweis, nicht als Regler (bei 12 h ist alles überlastet).

**LP ohne Skalierung meldete in der Messreihe fälschlich „unzulässig“.** Ohne Skalierung der Variablen (Container in Einheiten zu 100) meldete GLOP mit Lagerplatzzeilen in 3 bis 4 von 12 Wochen INFEASIBLE oder ABNORMAL, obwohl Verteilen zulässig war. Mit der Skalierung
liegt in allen getesteten Wochen (Test: 15 Wochen bei 90 % Füllung, beide Verfahren) ein Optimum vor. **Neu geprüft in dieser Demo:** mit OR-Tools 9.15 meldet GLOP auch ohne Skalierung in 120 Rechnungen (60 Wochen, Füllung 50 bis 90 %, beide Ziele) ein Optimum; die Skalierung bleibt als Vorsicht für andere Versionen, ist aber mit dieser nicht mehr erzwingbar. Die App prüft den Löserzustand und zeigt bei einem Fehler eine Meldung statt eines leeren Plans (Test mit erzwungenem Fehlerstatus, alle Nicht-Optimal-Zustände).

**„Kranrate passend“ muss den Lagerplatz beachten.** Die erste Fassung teilte gleich und verletzte die Lagergrenze in 17 von 30 (70 % Füllung) bis 30 von 30 Wochen. Die jetzige Fassung übergeht volle Blöcke; der Test stellt beide Fassungen
gegenüber (ohne Prüfung mindestens 10, mit Prüfung höchstens 3 von 30 Wochen).

**Kein einzelner Term als Ziel bei Gleichstand.** „Gerechnet“ hat viele gleichwertige Pläne (Wartezeit 0); der Weg geht mit dem Gewicht 10⁻⁶ als zweites Ziel mit (Muster CP-SAT lexikographisch), ein Test prüft die Lexikographie gegen „kürzester Weg
unter der Wartezeit-Grenze des Optimums“. Zielwerte sind eindeutig, die Aufteilung nicht: das gilt für Tests und Preset-Kriterien.

**Abweichungen vom Plan, die beim Bau aufgefallen sind.**
- Der Hilfetext der Blockrate nannte im Plan für die Ruhige Woche eine Auslastung von 0,6 bis 0,7; gemessen ist der **Spitzenbedarf der Schiffe gleichzeitig gegen die Gesamtrate** dort 29 % (Stoßwoche 72 %, Starke Kräne 91 %). Der Hilfetext nennt jetzt die gemessenen Werte.
- Die bedingte Meldung braucht zwei Schwellen, die der Plan offenließ: die Absicherung gilt als wirksam, wenn sie die Wartezeit bei Verspätung auf höchstens 60 % senkt (Starke Kräne, Woche 2017: 53 %), und „Blöcke zu knapp“ ab 3 min Wartezeit des
  Rechenplans (Starke Kräne, Woche 2017: 1,8 min). Beides nach der Messung gesetzt und dokumentiert (`tools/PRESET_SWEEP.md`).
- Der dritte Satz des Urteils (Abgesichert gegen Gierig, Zielwert Weg + λ · Wartezeit) trennt „kurzsichtig“ nicht von „kennt die Szenarien nicht“; der Text sagt es und verweist für die Trennung auf die Messreihe.
- Bei σ = 0 ist der abgesicherte Plan **nicht** identisch mit dem Gerechnet-Plan (der eine minimiert Wartezeit zuerst, der andere Weg + λ · Wartezeit), nur der Zielwert des Szenario-LP mit zehn gleichen Szenarien gleicht dem des Ein-Szenario-LP
  (getestet); die Meldung nennt beide Werte statt Gleichheit zu behaupten.

**Preset-Disziplin.** Kriterien an der Grundgesamtheit (Median über 100 Wochen, im Test 40) UND an der gezeigten Woche; jedes Kriterium hat einen Test mit künstlichen Werten, der einzeln an seiner Schwelle kippt, und die Schwellen stehen fest im
Test. Der Seed 2017 liegt außerhalb der Stichprobe (3000 bis 3019) und der Grundgesamtheit (1000 bis 1099).

## Tests

`python -m pytest tests/ -v` – 329 Tests, unter Windows rund 4 Minuten, im Linux-Container (Python 3.12, neueste Pakete, `tools/demo_linux_check.py` des Website-Repos) 3,5 Minuten. Zusammensetzung:

- **Woche:** bitgleich zur Messreihe (feste Referenzwerte für Seed 2017), Massenbilanz je Schiff, Anlieferung und Bestand, Lagergrenze aus dem Spitzenbestand, Verschiebungen (auch extreme), Regler-Grenzen.
- **Rückstand und Kennzahlen:** von Hand gerechnetes Beispiel, unabhängige Nachrechnung auf 60 Zufallsplänen, Rückstand nie negativ, Last = 2 Moves je Container, Beladeverzug, Lagerüberstand.
- **Regeln:** je Regel genau *n* Container je Schiff, **unabhängige naive Fassungen** (Bestand und Last jedes Mal aus dem bisherigen Plan gerechnet) liefern dieselben Pläne, kanonische Reihenfolge bei Gleichstand, Lagerprüfung wirkt.
- **LP:** Zielwert gegen unabhängige Nachrechnung (Abweichung unter 10⁻⁹), Kleinstinstanzen gegen Durchprobieren, LP nie schlechter als jede Regel, ein Block, unbegrenzte Rate, σ = 0, Lexikographie, Lagergrenze und Skalierung, Rundung, Löserstatus.
- **Auswertung:** Reproduktion der Messreihe (Ränder, Kante, Kranrate, Preis der Absicherung; Befund 2 „ohne Anlieferlast“), Kurve gegen Direktrechnungen, Urteil genau an der Schwelle, Verteilung, Diagnose in allen sechs Arten.
- **Presets:** Geschichte an der gezeigten Woche und im Median über 40 Wochen (parallel gerechnet), typisch je Kennzahl; alle Kriterien einzeln an ihren Schwellen mit künstlichen Werten.
- **Figuren, PDF, End-to-End (AppTest):** Achsen fest, Ausreißer am Rand, Sonderzeichen im PDF (fpdf2 stürzt bei „–“, „€“, „σ“, „λ“ und Emoji ab), Skelett und Footer, jedes Preset, Permalink, alle Regler an Min und Max, alle Arten der Meldung,
  Knopf-Pfade für Kurve und Stichprobe, Urteil in allen Zuständen, Verfahrensvergleich, PDF, keine toten Dateilinks.

Zusätzlich wurde jedes Modul mit **eingebauten Fehlern** geprüft (`tools/mutation_check.py`, 230 Mutanten, parallel, mit Zeitgrenze je Mutant, in drei Läufen mit zwischendurch ergänzten Tests): 221 gefunden, 9 überlebt. Der erste Lauf über die Mutanten 1 bis 95 ließ 7 Überlebende übrig, der zweite (96 bis 230 und Wiederholung) 15; davon waren **9 echte Lücken der Tests**, sie sind geschlossen und erneut geprüft (der Rückstand wird von Stunde zu Stunde weitergegeben, auch für Kleinstwochen mit Last in Stunde 0; der Löserstatus nur OPTIMAL gilt, nicht nur INFEASIBLE; der Aufschlag der Rundung bei kleinen LP-Werten in Minuten; die Kante rechnet ab der kleinstmöglichen Wartezeit auch dort, wo sie über 1 min liegt; σ = 1 h ist nicht die σ = 0-Meldung; genau 1,5 Container über der Lagergrenze gelten noch nicht als verletzt; die Spalte Wartezeit bei Verspätung im PDF; Schrittweite 2 und Nicht-Zahlen bei einem Zahlenregler in der Adresszeile) und ein Mutant, der die Referenz der Deltas ändert, wird nur von den AppTests gefunden (`--with-app`). **9 Überlebende sind gleichwertig**: die Gleichheit genau auf einer Gleitkommagrenze (`<=` gegen `<` bei der Lagerprüfung, bei der Klarheitsschwelle des Urteils und bei der Achsenkürzung), die Toleranz der Lagerprüfung (10⁻⁹ gegen 10⁻³, die Abstände in den Wochen sind viel größer), eine gelockerte Obergrenze der Summe je Schiff im LP (mehr Container als vorhanden kosten nur Weg und Wartezeit, der Plan bleibt gleich), die Rundung mit Toleranz 10⁻⁹ (die Zuteilung der größten Reste bringt einen knapp unter einer ganzen Zahl liegenden Wert ohnehin zurück), das Vorzeichen des Prozentwerts bei „mehr“ (nur bei negativen Kennzahlen erreichbar), das Gewicht 10⁻³ statt 10⁻⁶ für den Weg beim Gerechnet-Plan (dieselben Pläne in acht geprüften Wochen) und die **Skalierung der LP-Variablen**: in OR-Tools 9.15 meldet GLOP auch ohne sie in allen 120 geprüften Rechnungen (60 Wochen, beide Ziele) ein Optimum, die Skalierung bleibt als Vorsicht (Messreihe) und ist mit dieser Version nicht erzwingbar.

Die CI (Linux) installiert die neuesten Versionen von numpy, OR-Tools, Streamlit und Plotly (`requirements.txt` ist nicht gepinnt); die Tests prüfen deshalb Zielwerte und Kennzahlen mit Abstand und nie die Aufteilung des LP, und es gibt kein Zeitlimit.

## Dateistruktur

| Datei | Inhalt |
|---|---|
| `app.py` | Streamlit-Hauptablauf: Presets, Sidebar, Hauptansicht, Blick in die Woche, Kernabschnitt mit Knöpfen, Verfahrensvergleich, Texte |
| `blz_constants.py` | Regler-Grenzen, `PRESETS`, Verfahren, Schwellen der Meldung, Farben, Festwerte |
| `blz_presets.py` | `SETTING_SPECS`, Permalink (Begrenzen und Einrasten), Presets, Seed-Knopf |
| `blz_scenario.py` | Woche (Schiffe, Liegeplätze, Fenster, Anlieferung, Bestand, Lagergrenze), Verspätungsszenarien |
| `blz_rules.py` | Bündeln, Verteilen, Kranrate passend, Gierig |
| `blz_lp.py` | LP (GLOP): Gerechnet, Szenario-LP, Kante, Skalierung, Rundung, Löserstatus |
| `blz_queue.py` | Rückstands-Rekursion, Kennzahlen, Bewertung bei Verspätung |
| `blz_evaluation.py` | Verfahren je Woche, Kurve, Kante, Stichprobe, gepaarte Differenz, Verteilung, Urteil, Diagnose |
| `blz_visualization.py` | Preis der Absicherung, Kante, Belegung Schiff × Block, Blocklast, Verteilung, Spannweite (alle Achsen fest) |
| `blz_ui_panel.py` | Panel je Verfahren (Kennzahlen 2 × 2, Belegung, Blocklast) |
| `blz_pdf_export.py` | PDF-Ergebnis (`fpdf2`, Kernschrift, Sonderzeichen-Bereinigung) |
| `blz_stories.py` | Abnahmekriterien der Presets (Quelle für Werkzeug und Tests) |
| `tools/tune_presets.py`, `tools/PRESET_SWEEP.md` | Preset-Abstimmung und ihr Bericht |
| `tools/mutation_check.py` | Fehler-Einbau-Test |
| `tests/` | siehe oben |

## Bewusst nicht umgesetzt (mögliche Erweiterungen)

- **Suchaufwand und Umstapeln im Block** (Kopplung an die Stapelplanung), **Rückkopplung des Rückstands auf die Schiffskräne** (geschlossene Kette statt Flüssigkeit).
- **Blockkräne einzeln** (Störungen), Doppelspiele, **Container-Typen** (Kühlcontainer, Gefahrgut, Gewichtsklassen), Anlieferprofil aus Daten.
- **Mehrstufige Neuplanung während der Woche**, ganzzahlige Aufteilung als eigenes Optimierungsproblem, Fahrzeugbedarf aus dem Fahrweg, mehr als 10 Blöcke, Schrittregler durch die Woche.

## Lokal ausführen

```bash
pip install -r requirements-dev.txt
streamlit run app.py
```

Tests: `python -m pytest tests/ -v`. Preset-Abstimmung: `python tools/tune_presets.py population|seeds|shown`. Fehler-Einbau: `python tools/mutation_check.py [--jobs N] [--dry-run]`.

---

Gebaut mit Streamlit, Plotly, OR-Tools (GLOP) und fpdf2.
