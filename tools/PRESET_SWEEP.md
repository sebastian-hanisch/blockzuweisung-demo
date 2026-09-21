# Preset-Abstimmung (AP 6)

Werkzeug: `tools/tune_presets.py` (Modi `population`, `seeds`, `shown`); Kriterien in `blz_stories.py`, Abnahme in `tests/test_preset_stories.py` (echte Daten, 40 Wochen) und `tests/test_stories.py` (künstliche
Werte an den Schwellen). Deterministisch, kein Zeitlimit: geprüft werden Kennzahlen mit Abstand zur Schwelle, nie die Aufteilung des LP (bei mehreren gleichwertigen Plänen lösungsabhängig).

Messbasis: je Preset 100 Wochen (Seeds 1000 bis 1099) als Grundgesamtheit, 60 Kandidaten (Seeds 2000 bis 2059) für den gemeinsamen Seed; Bewertung an 30 Testszenarien, Planung an 10 anderen. Die Rechenpläne sind
wie in der App **auf ganze Container gerundet** (die Messreihe `hafen-planung/messreihe_blockzuweisung/presets_*.json` rechnete mit den ungerundeten LP-Plänen): die Mediane weichen davon um höchstens etwa 0,1 min und 1 m ab
(Stoßwoche, Gerechnet, Wartezeit pünktlich: Median 0,1 statt 0,0 min).

## Grundgesamtheit (100 Wochen je Preset; Median [10.; 90. Perzentil])

| Preset | Verfahren | Weg (m) | Wartezeit pünktlich (min) | Wartezeit bei Verspätung (min) |
|---|---|---|---|---|
| Stoßwoche | Bündeln | 263 [259; 292] | 125,8 [63,9; 192,9] | 162,4 [97,6; 229,3] |
| Stoßwoche | Verteilen | 458 [455; 463] | 0,0 [0,0; 0,6] | 2,6 [0,2; 9,9] |
| Stoßwoche | Kranrate passend | 264 [258; 271] | 21,2 [5,7; 79,9] | 52,0 [28,4; 110,0] |
| Stoßwoche | Gierig | 348 [331; 363] | 5,2 [0,0; 17,0] | 22,8 [12,0; 38,9] |
| Stoßwoche | Gerechnet | 260 [255; 274] | 0,1 [0,0; 0,7] | 42,1 [26,2; 57,7] |
| Stoßwoche | Abgesichert | 303 [283; 332] | 0,0 [0,0; 0,9] | 8,4 [3,5; 15,8] |
| Späte Schiffe | Bündeln | 263 [259; 292] | 125,8 [63,9; 192,9] | 189,6 [118,9; 253,5] |
| Späte Schiffe | Verteilen | 458 [455; 463] | 0,0 [0,0; 0,6] | 5,9 [0,9; 14,2] |
| Späte Schiffe | Kranrate passend | 264 [258; 271] | 21,2 [5,7; 79,9] | 73,4 [49,1; 124,8] |
| Späte Schiffe | Gierig | 348 [331; 363] | 5,2 [0,0; 17,0] | 38,6 [23,5; 58,0] |
| Späte Schiffe | Gerechnet | 260 [255; 274] | 0,1 [0,0; 0,7] | 70,7 [49,0; 93,2] |
| Späte Schiffe | Abgesichert | 331 [299; 372] | 0,0 [0,0; 1,4] | 13,3 [6,6; 23,5] |
| Voller Platz | Bündeln | 280 [267; 304] | 127,0 [64,8; 353,6] | 153,3 [87,0; 370,2] |
| Voller Platz | Verteilen | 458 [455; 463] | 0,0 [0,0; 0,6] | 2,6 [0,2; 9,9] |
| Voller Platz | Kranrate passend | 291 [276; 309] | 24,6 [5,1; 228,0] | 49,5 [24,8; 238,6] |
| Voller Platz | Gierig | 352 [328; 378] | 10,2 [1,4; 22,9] | 27,2 [14,9; 44,6] |
| Voller Platz | Gerechnet | 267 [262; 285] | 0,0 [0,0; 0,7] | 25,4 [12,0; 42,8] |
| Voller Platz | Abgesichert | 305 [286; 334] | 0,0 [0,0; 1,0] | 8,1 [3,4; 15,3] |
| Starke Kräne | Bündeln | 265 [258; 297] | 132,0 [80,8; 205,8] | 165,7 [103,5; 243,8] |
| Starke Kräne | Verteilen | 453 [449; 466] | 0,2 [0,0; 15,8] | 5,9 [0,7; 30,8] |
| Starke Kräne | Kranrate passend | 271 [261; 297] | 51,5 [27,2; 109,0] | 80,4 [47,8; 133,4] |
| Starke Kräne | Gierig | 347 [323; 378] | 7,8 [0,5; 34,3] | 22,2 [11,2; 55,0] |
| Starke Kräne | Gerechnet | 278 [265; 315] | 0,2 [0,0; 15,8] | 31,3 [16,6; 58,1] |
| Starke Kräne | Abgesichert | 327 [295; 384] | 0,7 [0,0; 17,1] | 12,3 [3,7; 33,6] |
| Ruhige Woche | Bündeln | 256 [251; 262] | 0,0 [0,0; 0,0] | 0,0 [0,0; 0,2] |
| Ruhige Woche | Verteilen | 463 [444; 468] | 0,0 [0,0; 0,0] | 0,0 [0,0; 0,0] |
| Ruhige Woche | Kranrate passend | 256 [251; 262] | 0,0 [0,0; 0,0] | 0,0 [0,0; 0,2] |
| Ruhige Woche | Gierig | 256 [251; 262] | 0,0 [0,0; 0,0] | 0,0 [0,0; 0,1] |
| Ruhige Woche | Gerechnet | 247 [245; 251] | 0,0 [0,0; 0,0] | 0,0 [0,0; 0,3] |
| Ruhige Woche | Abgesichert | 247 [245; 251] | 0,0 [0,0; 0,0] | 0,0 [0,0; 0,2] |

Lagergrenze verletzt in (von 100 Wochen): **Voller Platz** Bündeln 100, Kranrate passend 64, Gierig 49, Verteilen, Gerechnet und Abgesichert 0; Stoßwoche und Späte Schiffe Bündeln 5, Kranrate passend 1; Starke Kräne Bündeln 11,
Kranrate passend 1; Ruhige Woche keines. Mehrweg der Absicherung gegen Gerechnet (Median): Stoßwoche 42,4 m, Späte Schiffe 68,9 m, Voller Platz 34,9 m, Starke Kräne 37,4 m, Ruhige Woche 0,0 m. Weg-Ersparnis des
Rechenplans gegen Kranrate passend (Median): Stoßwoche 2,0 m, Voller Platz 16,5 m, Ruhige Woche 8,2 m; bei Starke Kräne **−8,2 m** (der Rechenplan ist länger, weil die Alltagsregel dort wartet).

## Kriterien (`blz_stories.py`): alle tragen im Median über 100 Wochen UND an der gezeigten Woche (Seed 2017)

| Preset | Kriterium (Schwelle) | Median 100 Wochen | Woche 2017 |
|---|---|---|---|
| Stoßwoche | Kranrate passend, Wartezeit pünktlich >= 10 min | 21,2 | 20,5 |
| Stoßwoche | Gerechnet, Wartezeit pünktlich <= 2 min | 0,10 | 0,12 |
| Stoßwoche | Gerechnet, Wartezeit bei Verspätung >= 25 min | 42,1 | 50,1 |
| Stoßwoche | abgesichert, Wartezeit bei Verspätung <= 15 min | 8,4 | 9,4 |
| Stoßwoche | Gerechnet / abgesichert bei Verspätung >= 3 | 5,0 | 5,3 |
| Stoßwoche | Mehrweg der Absicherung 25 bis 60 m | 42,4 | 38,8 |
| Späte Schiffe | Gerechnet, Wartezeit bei Verspätung >= 50 min | 70,7 | 83,4 |
| Späte Schiffe | abgesichert, Wartezeit bei Verspätung <= 25 min | 13,3 | 18,2 |
| Späte Schiffe | Mehrweg der Absicherung >= 45 m | 68,9 | 53,0 |
| Voller Platz | Bündeln, Container über der Grenze >= 50 | 366,5 | 177,2 |
| Voller Platz | Gerechnet, Container über der Grenze <= 1 (Rundung) | 0,5 | 0,5 |
| Voller Platz | Rechenpläne verletzen die Grenze in höchstens 5 % der Wochen; Bündeln in mindestens 90 % | 0 % / 100 % | erfüllt |
| Voller Platz | Gerechnet, Wartezeit pünktlich <= 2 min | 0,03 | 0,02 |
| Voller Platz | abgesichert, Wartezeit bei Verspätung <= 15 min | 8,1 | 9,0 |
| Starke Kräne | Kranrate passend, Wartezeit pünktlich >= 25 min | 51,5 | 70,9 |
| Starke Kräne | Gerechnet, Wartezeit bei Verspätung >= 15 min | 31,3 | 37,4 |
| Starke Kräne | abgesichert, Wartezeit bei Verspätung <= 25 min | 12,3 | 19,8 |
| Ruhige Woche | Kranrate passend, Wartezeit pünktlich <= 1 min | 0,00 | 0,00 |
| Ruhige Woche | Gerechnet, Wartezeit bei Verspätung <= 1 min | 0,03 | 0,07 |
| Ruhige Woche | Weg-Ersparnis des Rechenplans gegen Kranrate passend 3 bis 15 m | 8,2 | 6,5 |
| Ruhige Woche | Mehrweg der Absicherung <= 1 m | 0,00 | 0,00 |

Die Werte der Woche 2017 stimmen mit denen des Plans (Abschnitt 7) überein.

## Gewählt

- **Ein gemeinsamer Seed 2017** für alle fünf Presets (Kandidaten 2000 bis 2059, außerhalb der Grundgesamtheit 1000 bis 1099 und der Stichprobe 3000 bis 3019): Von 60 Kandidaten tragen 17 alle fünf Geschichten; Seed 2017 liegt mit einer
  Summe von 9,17 Interquartilsbreiten (über sechs Kennzahlen und fünf Presets) am nächsten am Median, der schlechteste Einzelabstand ist 0,66 Interquartilsbreiten; danach 2054 (9,25; 0,70) und 2047 (10,31; 0,87).
  Jede der sechs Kennzahlen aus `TYPICAL` (Weg Gerechnet, Weg abgesichert, Wartezeit Kranrate pünktlich, Wartezeit bei Verspätung Gerechnet und abgesichert, Weg Gierig) der gezeigten Woche liegt in jedem Preset
  zwischen dem 5. und 95. Perzentil der Grundgesamtheit (Test `test_the_shown_week_is_typical_for_every_key_measure`); der Rang in den 100 Wochen liegt zwischen 16 und 76 % (Ausnahme: Ruhige Woche, Kranrate passend, Wartezeit: alle Wochen 0, Rang 100 % durch Gleichstände).
- Stoßwoche und Späte Schiffe teilen dieselbe Woche (nur σ ändert sich), das ist gewollt.

## Befunde und Abweichungen vom Plan

- **Voller Platz, Woche 2017:** Kranrate passend wartet pünktlich nur 6,7 min (Rang 16 % der Grundgesamtheit, Median 24,6): die Woche ist dort günstig für die Alltagsregel. Die Geschichte des Presets (Lagergrenze) trägt trotzdem
  (Bündeln 177 Container über der Grenze, Median 366); kein Kriterium hängt an der Wartezeit von Kranrate passend.
- **Starke Kräne, Woche 2017:** die Absicherung senkt die Wartezeit bei Verspätung von 37,4 auf 19,8 min (auf 53 %). Die bedingte Meldung unterscheidet "die Absicherung hilft" (höchstens 60 % der Wartezeit des wartefreien
  Plans, Schwelle `HEDGE_FACTOR`) und "hilft nur teils" (`fragile`); bei 0,5 hätte diese Woche als "hilft nur teils" gegolten. Auch der Rechenplan wartet dort pünktlich 1,8 min (Median 0,2 [0,0; 15,8]): die Schwelle für "Blöcke zu
  knapp" liegt deshalb bei 3 min (`OVERLOAD_WAIT`), nicht bei 2.
- **Spitzenbedarf gegen Gesamtrate** (Hilfetext der Blockrate; Median über 100 Wochen): Stoßwoche 72 %, Starke Kräne 91 %, Ruhige Woche 29 %. Der Plan nannte für die Ruhige Woche "0,6 bis 0,7", das war ein anderes Maß; im Hilfetext
  stehen die gemessenen Werte.
- **Ruhige Woche:** Bündeln, Kranrate passend und Gierig sind gleich (255,7 m im Median, keine Wartezeit), der Rechenplan spart 8,2 m, die Absicherung kostet im Median 0,0 m.
- **Kein Preset musste geändert werden**; kein Schwellenwert wurde nach der Messung an die Zahlen angepasst außer `HEDGE_FACTOR` (0,5 auf 0,6) und `OVERLOAD_WAIT` (2 auf 3), beide für die bedingte Meldung, nicht für die Presets.
