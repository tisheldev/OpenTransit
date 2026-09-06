# POC-5 — place search, human review sheet (checkpoint H4)

Generated 2026-09-04 by `poc/geocoding/run.py`. **Machine-generated — do not hand-edit; rerun the runner.**

Engine: MOTIS v2.11.2 built-in geocoder (ADR 0006), GET /api/v1/geocode
Feed: `Gtfs_10_days.zip` sha256 `08c168da…`

## How to read this

A case **passes** when the geocoder's *first* result is within the corpus tolerance of the corpus coordinate. `top5` says whether the right answer was anywhere in the first five — a real planner shows a dropdown, so a case that fails top-1 but hits at rank 2 is a ranking problem, not a coverage problem.

The corpus coordinates are **hand-entered approximations with a generous tolerance**, not ground truth (P011/P012 were already 1,961 m wrong once). Where the distance is a judgement call rather than a clear miss, the verdict line below is blank and a human fills it in.

## Headline

- **68 / 100** correct at top-1 (PRD §10 bar is 20 — met)
- **89 / 100** correct somewhere in the top 5
- latency p50 3.5 ms, p95 67.6 ms
- status **PARTIAL** — 68/100 top-1 (89/100 in top-5) — clears PRD §10's bar of 20, but Latin-script street addresses do not resolve (4/15 address cases) and the `near` bias point is inert at MOTIS's default placeBias

PRD §10 names two queries in its own prose. Both resolve:

| Case | Query | Result | Distance |
| --- | --- | --- | ---: |
| P035 | `Dizengoff Center` | 32.075129, 34.77537 | 83 m |
| P003 | `HaShalom Station` | 32.073084, 34.793059 | 53 m |

## By category

| Category | top-1 | in top-5 | of |
| --- | ---: | ---: | ---: |
| station | 16 | 18 | 20 |
| poi_university | 8 | 9 | 9 |
| poi_hospital | 2 | 4 | 5 |
| poi_mall | 3 | 4 | 4 |
| poi_landmark | 11 | 12 | 12 |
| address | 4 | 10 | 15 |
| neighborhood | 9 | 10 | 10 |
| misspelling | 8 | 9 | 10 |
| translit | 4 | 8 | 9 |
| near_dependent | 3 | 5 | 6 |

## By language

| Language | top-1 | in top-5 | of |
| --- | ---: | ---: | ---: |
| he | 14 | 18 | 19 |
| en | 54 | 71 | 81 |

## Failure modes, ranked

These are **causes**, assigned by reading each failing case's candidate list. The evidence is the `top5` array kept for every case in `poc-5.json`, so any assignment here can be checked. `engine?` says whether the cause is a defect in the geocoder — three of them are not.

| # | Cause | Count | engine? | Cases |
| ---: | --- | ---: | :---: | --- |
| 1 | street addresses in Latin script return no address candidate at all (the address index answers Hebrew) | 9 | yes | P051, P053, P056, P058, P059, P060, P062, P063, P064 |
| 2 | a bus stop on a street named after the target outranks the target itself (KDP-010's trap, beyond railway stations) | 6 | yes | P005, P030, P031, P049, P086, P093 |
| 3 | a generic word in the query (Station / Mall / Medical Center / City / תחנת רכבת) outranks the distinctive word beside it | 5 | yes | P002, P013, P033, P038, P074 |
| 4 | the engine's answer is plausible and the hand-entered corpus point is the less certain of the two — a human verdict, not an engine failure | 2 | no | P065, P081 |
| 5 | the `near` bias point has no effect at MOTIS's default placeBias | 2 | yes | P095, P099 |
| 6 | two OSM features carry the city's name and the higher-ranked one is kilometres away, in a different municipality | 2 | no | P087, P088 |
| 7 | a satellite stop of the POI outranks the POI itself | 2 | yes | P023, P089 |
| 8 | the city qualifier in an address query is matched as another name token, not as a locality filter | 1 | yes | P057 |
| 9 | a large POI's centroid is a legitimate answer but is kilometres from the transit access point a traveller departs from | 1 | no | P012 |
| 10 | the `near` bias point was applied but landed on a different same-named feature inside the biased region | 1 | yes | P097 |
| 11 | a transliterated Hebrew word (Merkaz) is absent from the feed's Latin names, which use the translation (Center) | 1 | yes | P083 |

Shape of the miss, measured rather than judged:

| Shape | Count | Cases |
| --- | ---: | --- |
| correct_answer_outranked | 21 | P002, P013, P023, P030, P031, P038, P049, P051, P057, P058, P060, P062, P065, P074, P081, P087, P088, P089, P093, P097, P099 |
| different_locality | 9 | P005, P033, P053, P056, P059, P064, P083, P086, P095 |
| near_miss_outside_tolerance | 1 | P012 |
| same_locality_wrong_feature | 1 | P063 |

## The `near` pairs

Same query string, different correct answer by bias point. An engine that ignores `near` cannot pass both halves.

| Pair | Query | At MOTIS default placeBias |
| --- | --- | --- |
| P095 / P096 | `Central Station` | **one** |
| P097 / P098 | `Herzl` | **one** |

Sweeping `placeBias` (separate experiment, not part of the headline):

| Pair | `no_place` | `1` | `2` | `3` | `5` | `10` | `20` |
| --- | --- | --- | --- | --- | --- | --- | --- |
| P095/P096 | one | one | one | one | both | one | one |
| P097/P098 | neither | one | one | one | one | one | both |

## Two targeted probes

**does MOTIS's address index answer Latin-script street queries, or only Hebrew ones?** 10 streets, each queried in Latin and in Hebrew; count ADDRESS-type candidates in the first 10 results.

Latin script returned **1** ADDRESS-type candidates across the ten streets. Hebrew returned **45**.

| Street, Latin | ADDRESS results | Street, Hebrew | ADDRESS results |
| --- | ---: | --- | ---: |
| Dizengoff 100 Tel Aviv | 0 | דיזנגוף 100 תל אביב | 5 |
| Rothschild 1 Tel Aviv | 0 | רוטשילד 1 תל אביב | 8 |
| Ibn Gabirol 30 Tel Aviv | 1 | אבן גבירול 30 תל אביב | 3 |
| King George 15 Jerusalem | 0 | המלך ג'ורג' 15 ירושלים | 5 |
| Herzl 50 Haifa | 0 | הרצל 50 חיפה | 1 |
| Ben Yehuda 20 Tel Aviv | 0 | בן יהודה 20 תל אביב | 10 |
| Allenby 40 Tel Aviv | 0 | אלנבי 40 תל אביב | 2 |
| Sokolov 30 Ramat Gan | 0 | סוקולוב 30 רמת גן | 3 |
| Jaffa 97 Jerusalem | 0 | יפו 97 ירושלים | 5 |
| Bialik 20 Ramat Gan | 0 | ביאליק 20 רמת גן | 3 |

**are house numbers interpolated along the street, or ignored?** one Hebrew street, house numbers 1/50/100/200/300. Coordinate walks monotonically up the street: **True** — so house numbers are honoured, in Hebrew.

| Query | Type | Returned | Lat | Lon |
| --- | --- | --- | ---: | ---: |
| דיזנגוף 1 תל אביב | ADDRESS | דיזנגוף 1 | 32.07348 | 34.78158 |
| דיזנגוף 50 תל אביב | ADDRESS | דיזנגוף 50 | 32.07522 | 34.7757 |
| דיזנגוף 100 תל אביב | ADDRESS | דיזנגוף 100 | 32.07925 | 34.77411 |
| דיזנגוף 200 תל אביב | ADDRESS | דיזנגוף 200 | 32.08632 | 34.775 |
| דיזנגוף 300 תל אביב | ADDRESS | דיזנגוף 300 | 32.09437 | 34.77683 |

## What this means

- PRD §10's bar (>=20 correct) is cleared more than three times over, and both queries PRD §10 names by hand resolve: 'Dizengoff Center' to 32.075129, 34.77537 (83 m) and 'HaShalom Station' to 32.073084, 34.793059 (53 m). Status is PARTIAL despite that, because two of PRD §10's listed requirements are not met: street addresses in Latin script, and biasing by current location.
- MOTIS's address index is effectively Hebrew-only. Ten streets queried in both scripts returned 1 ADDRESS-type candidates in Latin and 45 in Hebrew. House numbers themselves work correctly once the query is Hebrew — walking דיזנגוף 1/50/100/200/300 walks the coordinate monotonically up the street. This is the single largest failure cluster (9 of 32) and is what a Phase 1 Photon deployment would buy.
- The `near` bias point is inert at MOTIS's default placeBias, and no single placeBias value satisfies all six near cases: P095/P096 pass together only at placeBias=5, P097/P098 only at placeBias=20, and placeBias=20 breaks P100. Both pairs therefore report 'one' at the default. See `place_bias_sweep`.
- The `language` parameter had no observed effect on this build — Hebrew and English queries return the same candidates in the same order whether language=he, language=en or nothing is sent.
- Seven corpus coordinates were proved wrong against the feed during this run and corrected in poc/corpora/build_places.py, not absorbed by widening a tolerance: P013 (778 m), P016 (3,244 m), P017 (2,626 m), P020 (1,386 m), P032 (966 m), P034 (2,562 m) and P084 (1,961 m). P084 still carried the identical stale Ben Gurion Airport coordinate that was fixed in P011/P012 in Wave 0 but never propagated. Correcting them moved the score from 62/100 to 68/100; the pre-correction number is stated here so the change is visible.
- P059/P065 ('Herzl 50 Haifa' / 'הרצל 50 חיפה') were NOT corrected. MOTIS and Nominatim independently agree on 32.8075, 35.0008, which is 1,089 m from the hand-entered corpus point, but a street house number cannot be proved against a GTFS feed. Left failing and flagged for a human verdict at H4.
- Bounded Nominatim comparison (PRD §10, ADR 0006, 15 requests at <=1/s, address category only, poc/results/poc-5-nominatim.json): Nominatim scores 7/15 against MOTIS's 4/15, and 4/11 against MOTIS's 2/11 on the Latin-script half. Nominatim returns house-level results for 'Dizengoff 100 Tel Aviv' and 'King George 15 Jerusalem' where MOTIS returns no address candidate at all. Evidence about relative quality only — Nominatim is a different OSM extract and is never ground truth here.
- Four findings were appended to poc/docs/known-data-problems.md: KDP-012 (stops on a street named after a place outrank the place — KDP-010's trap is not specific to railway stations; 6 of 32 failures), KDP-013 (the feed's English stop names mix translation and transliteration with no rule — מרכז is rendered 'Center' for 885 stops and 'Merkaz' for 63), KDP-014 (two OSM features carry Petach Tikva's name, 3.3 km apart, and the wrong one outranks the city) and KDP-015 (the corpus-coordinate corrections, including the stale airport value that survived the Wave 0 fix).
- Scoring is top-1. The top-5 figure (89/100) is reported alongside because a real planner shows a dropdown, but it is never substituted for the headline.

## Every case

`verdict` is blank on purpose for cases where "correct enough to start routing" is a judgement rather than a distance — a human fills those in at H4.

| ID | Lang | Category | Query | Returned (top-1) | Source | City | Dist m | Tol m | Scored | Rank of correct | Verdict |
| --- | --- | --- | --- | --- | --- | --- | ---: | ---: | --- | --- | --- |
| P001 | en | station | Tel Aviv Savidor Center | Tel Aviv Savidor Center | osm | תל־אביב–יפו | 67 | 400 | PASS | 1 | ok |
| P002 | he | station | תחנת רכבת תל אביב סבידור מרכז | תחנת רכבת קוממיות | gtfs | חולון | 9825 | 400 | fail | 2 |   |
| P003 | en | station | HaShalom Station | HaShalom Rail Station | gtfs | תל־אביב–יפו | 53 | 400 | PASS | 1 | ok |
| P004 | he | station | תחנת השלום | ת. רכבת השלום | gtfs | תל־אביב–יפו | 53 | 400 | PASS | 1 | ok |
| P005 | en | station | Yitzhak Navon | Yitzhak Navon/Herzl | gtfs | מגדל העמק | 100014 | 500 | fail | — |   |
| P006 | he | station | תחנת יצחק נבון | תחנת הרכבת ירושלים – יצחק נבון | osm | ירושלים / القدس | 93 | 500 | PASS | 1 | ok |
| P007 | en | station | Haifa Center HaShmona | Haifa Center HaShmona Train Station | gtfs | חיפה | 158 | 500 | PASS | 1 | ok |
| P008 | he | station | חיפה מרכז השמונה | תחנת רכבת חיפה מרכז השמונה | gtfs | חיפה | 158 | 500 | PASS | 1 | ok |
| P009 | en | station | Beersheba Central Station | Be'er Sheva Central Station/Alight | gtfs | באר שבע | 206 | 500 | PASS | 1 | ok |
| P010 | he | station | באר שבע מרכז | באר שבע מרכז | gtfs | באר שבע | 27 | 500 | PASS | 1 | ok |
| P011 | en | station | Ben Gurion Airport | Ben Gurion Airport | gtfs | — | 5 | 1500 | PASS | 1 | ok |
| P012 | he | station | נמל תעופה בן גוריון | נמל התעופה בן-גוריון | osm | — | 3431 | 1500 | fail | — |   |
| P013 | en | station | Herzliya Station | Herzliya Center MDA Station | osm | הרצליה | 2974 | 500 | fail | 2 |   |
| P014 | en | station | Modi'in Center | Modi'in Railway Station/Center | gtfs | מודיעין-מכבים-רעות | 135 | 600 | PASS | 1 | ok |
| P015 | en | station | Nahariya | Nahariya | gtfs | נהריה | 555 | 700 | PASS | 1 | ok |
| P016 | en | station | Ashdod Ad Halom | Ashdod Ad Halom – Metropolin | gtfs | אשדוד | 0 | 600 | PASS | 1 | ok |
| P017 | en | station | Bat Galim | Bat Galim | gtfs | חיפה | 0 | 500 | PASS | 1 | ok |
| P018 | en | station | Jerusalem Central Bus Station | Jerusalem Central Bus Station/Alight | gtfs | ירושלים / القدس | 121 | 500 | PASS | 1 | ok |
| P019 | he | station | תחנה מרכזית ירושלים | ת. מרכזית ירושלים/יפו | gtfs | ירושלים / القدس | 121 | 500 | PASS | 1 | ok |
| P020 | en | station | Petah Tikva Kiryat Arye | Kiryat Arye Railway Station | gtfs | פתח תקווה | 57 | 500 | PASS | 1 | ok |
| P021 | en | poi_university | Technion | Technion Center | gtfs | חיפה | 560 | 900 | PASS | 1 | ok |
| P022 | he | poi_university | הטכניון | דרך הטכניון/עמוס | gtfs | נשר | 899 | 900 | PASS | 1 | ok |
| P023 | en | poi_university | Tel Aviv University | Tel Aviv University – Expo | gtfs | תל־אביב–יפו | 1088 | 900 | fail | 2 |   |
| P024 | he | poi_university | אוניברסיטת תל אביב | אוניברסיטת תל אביב | osm | תל־אביב–יפו | 69 | 900 | PASS | 1 | ok |
| P025 | en | poi_university | Hebrew University Mount Scopus | Hebrew University Mount Scopus/Martin Buber | gtfs | ירושלים / القدس | 251 | 900 | PASS | 1 | ok |
| P026 | en | poi_university | Ben Gurion University | Ben Gurion University Sports Center | gtfs | באר שבע | 384 | 900 | PASS | 1 | ok |
| P027 | en | poi_university | Bar-Ilan University | Bar Ilan University | gtfs | קריית אונו | 567 | 900 | PASS | 1 | ok |
| P028 | en | poi_university | Haifa University | Haifa University | gtfs | חיפה | 447 | 900 | PASS | 1 | ok |
| P029 | en | poi_university | Weizmann Institute | Weizmann Institute | gtfs | רחובות | 411 | 900 | PASS | 1 | ok |
| P030 | en | poi_hospital | Ichilov | Weizmann/Ichilov | gtfs | נתניה | 29630 | 700 | fail | 3 |   |
| P031 | he | poi_hospital | איכילוב | ההסתדרות/איכילוב | gtfs | פתח תקווה | 9012 | 700 | fail | 3 |   |
| P032 | en | poi_hospital | Beilinson Hospital | Beilinson Hospital/Jabotinsky | gtfs | פתח תקווה | 124 | 700 | PASS | 1 | ok |
| P033 | en | poi_hospital | Rambam Medical Center | Medical Center/Ramat Yam | gtfs | הרצליה | 75030 | 700 | fail | — |   |
| P034 | en | poi_hospital | Hadassah Ein Kerem | Main Entry/Hadassah Ein Kerem | gtfs | ירושלים / القدس | 124 | 900 | PASS | 1 | ok |
| P035 | en | poi_mall | Dizengoff Center | Dizengoff Center/Dizengoff | gtfs | תל־אביב–יפו | 83 | 500 | PASS | 1 | ok |
| P036 | he | poi_mall | דיזנגוף סנטר | דיזנגוף סנטר/דיזנגוף | gtfs | תל־אביב–יפו | 83 | 500 | PASS | 1 | ok |
| P037 | en | poi_mall | Azrieli Center | Azrieli Center | osm | תל־אביב–יפו | 85 | 500 | PASS | 1 | ok |
| P038 | en | poi_mall | Malha Mall | Mall/HaGalil | gtfs | צפת | 138865 | 700 | fail | 2 |   |
| P039 | en | poi_landmark | Mahane Yehuda Market | Mahane Yehuda Market/Agripas | gtfs | ירושלים / القدس | 181 | 500 | PASS | 1 | ok |
| P040 | en | poi_landmark | Western Wall | Western Wall | gtfs | ירושלים / القدس | 134 | 500 | PASS | 1 | ok |
| P041 | he | poi_landmark | הכותל המערבי | הכותל המערבי | gtfs | ירושלים / القدس | 134 | 500 | PASS | 1 | ok |
| P042 | en | poi_landmark | Jaffa Clock Tower | Jaffa Clock Tower- Pop Up Center | osm | תל־אביב–יפו | 448 | 500 | PASS | 1 | ok |
| P043 | he | poi_landmark | מגדל השעון יפו | מגדל השעון יפו | osm | תל־אביב–יפו | 395 | 500 | PASS | 1 | ok |
| P044 | en | poi_landmark | Yad Vashem | Yad VaShem | gtfs | ירושלים / القدس | 187 | 700 | PASS | 1 | ok |
| P045 | en | poi_landmark | Mount Herzl | Mount Herzl | gtfs | ירושלים / القدس | 322 | 600 | PASS | 1 | ok |
| P046 | en | poi_landmark | Sarona Market | Sarona Market | osm | תל־אביב–יפו | 67 | 500 | PASS | 1 | ok |
| P047 | en | poi_landmark | Habima Theatre | Habima/Tarsat Blvd | gtfs | תל־אביב–יפו | 153 | 500 | PASS | 1 | ok |
| P048 | en | poi_landmark | Bloomfield Stadium | Bloomfield Stadium | gtfs | תל־אביב–יפו | 279 | 600 | PASS | 1 | ok |
| P049 | en | poi_landmark | Masada | Masada | gtfs | חיפה | 169582 | 2000 | fail | 3 |   |
| P050 | en | poi_landmark | Mitzpe Ramon | Mitzpé Ramón | osm | מצפה רמון | 224 | 2000 | PASS | 1 | ok |
| P051 | en | address | Dizengoff 100 Tel Aviv | Tel Aviv Harbor/Disengoff | gtfs | תל־אביב–יפו | 1962 | 700 | fail | 2 |   |
| P052 | he | address | דיזנגוף 100 תל אביב | דיזנגוף 100 | other | תל־אביב–יפו | 12 | 700 | PASS | 1 | ok |
| P053 | en | address | Rothschild Boulevard 1 Tel Aviv | Shazar Boulevard/Rothschild | gtfs | באר שבע | 91163 | 700 | fail | — |   |
| P054 | he | address | שדרות רוטשילד 1 תל אביב | שדרות רוטשילד 1 | other | תל־אביב–יפו | 118 | 700 | PASS | 1 | ok |
| P055 | en | address | Ibn Gabirol 30 Tel Aviv | Tel Aviv City Hall/Ibn Gabirol | gtfs | תל־אביב–יפו | 225 | 700 | PASS | 1 | ok |
| P056 | en | address | Jaffa Street 97 Jerusalem | Jerusalem/Palmah A | gtfs | קרית ים | 119206 | 700 | fail | — |   |
| P057 | he | address | יפו 97 ירושלים | ירושלים 97 | other | תל־אביב–יפו | 51635 | 700 | fail | 2 |   |
| P058 | en | address | King George 15 Jerusalem | Jerusalem/Palmah A | gtfs | קרית ים | 119904 | 700 | fail | 5 |   |
| P059 | en | address | Herzl 50 Haifa | Herzl/Gan HaIr | gtfs | רחובות | 103905 | 800 | fail | — |   |
| P060 | en | address | Ben Yehuda 20 Tel Aviv | Dizengoff/Ben Yehuda | gtfs | תל־אביב–יפו | 2045 | 700 | fail | 5 |   |
| P061 | en | address | Allenby 40 Tel Aviv | Allenby LRT Station/Yavne | gtfs | תל־אביב–יפו | 475 | 700 | PASS | 1 | ok |
| P062 | en | address | HaNevi'im 20 Jerusalem | Jerusalem Gate/Bahad 20 | gtfs | באר יעקב | 40453 | 700 | fail | 2 |   |
| P063 | en | address | Sokolov 30 Ramat Gan | Sokolov/Ephraim Katzir | gtfs | הוד השרון | 12520 | 800 | fail | — |   |
| P064 | en | address | Rager Boulevard Beersheba | Afeka/KKL Boulevard | gtfs | תל־אביב–יפו | 96424 | 900 | fail | — |   |
| P065 | he | address | הרצל 50 חיפה | הרצל 50 | other | חיפה | 1089 | 800 | fail | 2 |   |
| P066 | en | neighborhood | Florentin | Herzl/Florentin | gtfs | תל־אביב–יפו | 208 | 1200 | PASS | 1 | ok |
| P067 | he | neighborhood | פלורנטין | הרצל/פלורנטין | gtfs | תל־אביב–יפו | 208 | 1200 | PASS | 1 | ok |
| P068 | en | neighborhood | Neve Tzedek | Neve Tzedek | osm | תל־אביב–יפו | 731 | 1000 | PASS | 1 | ok |
| P069 | en | neighborhood | Ramat Aviv | Ramat Aviv Mall/Einstein | gtfs | תל־אביב–יפו | 316 | 1500 | PASS | 1 | ok |
| P070 | en | neighborhood | Rehavia | Rehavia | osm | ירושלים / القدس | 104 | 1200 | PASS | 1 | ok |
| P071 | en | neighborhood | Nachlaot | Nachla'ot | osm | ירושלים / القدس | 227 | 1000 | PASS | 1 | ok |
| P072 | en | neighborhood | Hadar HaCarmel | Hadar HaCarmel | osm | חיפה | 243 | 1500 | PASS | 1 | ok |
| P073 | en | neighborhood | Ramot | Ramot/Ma'oz | gtfs | ירושלים / القدس | 1331 | 2000 | PASS | 1 | ok |
| P074 | en | neighborhood | Old City Jerusalem | Weizmann/Jerusalem City Hall | gtfs | קרית ביאליק | 117232 | 1200 | fail | 4 |   |
| P075 | he | neighborhood | העיר העתיקה ירושלים | העיר העתיקה | osm | ירושלים / القدس | 255 | 1200 | PASS | 1 | ok |
| P076 | en | misspelling | Dizengof Center | Dizengoff Center/Dizengoff | gtfs | תל־אביב–יפו | 83 | 500 | PASS | 1 | ok |
| P077 | en | misspelling | Technyon | Technion Center | gtfs | חיפה | 560 | 900 | PASS | 1 | ok |
| P078 | en | misspelling | Jerusalim | Jerusalim | osm | ירושלים / القدس | 1592 | 3000 | PASS | 1 | ok |
| P079 | en | misspelling | Beer Sheva | Beer Sheva | osm | באר שבע | 629 | 2000 | PASS | 1 | ok |
| P080 | en | misspelling | Herzliyya | Hertzliya | gtfs | הרצליה | 778 | 2000 | PASS | 1 | ok |
| P081 | en | misspelling | Netania | Netania | osm | נתניה | 2161 | 2000 | fail | 2 |   |
| P082 | en | misspelling | Rishon Lezion | Rishon LeZion | osm | ראשון לציון | 579 | 3000 | PASS | 1 | ok |
| P083 | en | misspelling | Savidor Merkaz | Merkaz Horev/Pica | gtfs | חיפה | 79884 | 400 | fail | — |   |
| P084 | en | misspelling | Ben Gurion Airoport | Ben Gurion Airport | gtfs | — | 5 | 1500 | PASS | 1 | ok |
| P085 | en | misspelling | Machne Yehuda | Mah̠ane Yehuda | gtfs | ירושלים / القدس | 108 | 500 | PASS | 1 | ok |
| P086 | en | translit | Petah Tikva | Petah Tikva A | gtfs | ירושלים / القدس | 44218 | 3000 | fail | — |   |
| P087 | en | translit | Petach Tikwa | Petach Tikwa | osm | מועצה אזורית דרום השרון | 3193 | 3000 | fail | 3 |   |
| P088 | en | translit | Petah Tiqwa | Petah Tiqwa | osm | מועצה אזורית דרום השרון | 3193 | 3000 | fail | 3 |   |
| P089 | en | translit | Rishon LeTsiyon | Rishon LeTsiyon Beach | gtfs | ראשון לציון | 7532 | 3000 | fail | 2 |   |
| P090 | en | translit | Rishon LeZion | Rishon LeZion | osm | ראשון לציון | 579 | 3000 | PASS | 1 | ok |
| P091 | en | translit | Kfar Saba | Kfar Saba | gtfs | הוד השרון | 1297 | 3000 | PASS | 1 | ok |
| P092 | en | translit | Kefar Sava | Walk In - Kefar Sava | osm | כפר סבא | 1940 | 3000 | PASS | 1 | ok |
| P093 | en | translit | Akko | Akko Road/HaGefen | gtfs | קרית ביאליק | 10902 | 3000 | fail | 4 |   |
| P094 | en | translit | Acre | Acre | gtfs | עכו | 99 | 3000 | PASS | 1 | ok |
| P095 | en | near_dependent | Central Station | Central Station | gtfs | ירושלים / القدس | 49822 | 1500 | fail | — |   |
| P096 | en | near_dependent | Central Station | Central Station | gtfs | ירושלים / القدس | 44 | 1500 | PASS | 1 | ok |
| P097 | en | near_dependent | Herzl | HaRo'e/Herzl | gtfs | רמת גן | 4349 | 3000 | fail | 2 |   |
| P098 | en | near_dependent | Herzl | Herzl/Yo'el | gtfs | חיפה | 367 | 3000 | PASS | 1 | ok |
| P099 | en | near_dependent | HaTachana | Hatachana | osm | מטולה | 155333 | 2000 | fail | 2 |   |
| P100 | en | near_dependent | University | Haifa University | gtfs | חיפה | 447 | 3000 | PASS | 1 | ok |

## Cases needing a human verdict

Every row above whose `Scored` is `fail`. For each, the question is not "is it within N metres" but "would a user starting a journey here get where they meant to go".

### P002 — `תחנת רכבת תל אביב סבידור מרכז`  (he, station)

- expected: **TA Savidor** at 32.0836, 34.7981 (tol 400 m)
- returned: **תחנת רכבת קוממיות** (STOP, gtfs, id `mot10day_23561`) at 32.001109, 34.760742 — **9825 m** away
- next candidates: תחנת רכבת סבידור מרכז/גשר מודעי (gtfs, תל־אביב–יפו); ת. רכבת יוספטל (gtfs, חולון); ת. רכבת אוניברסיטה/הורדה (gtfs, תל־אביב–יפו)
- cause: `generic_word_outranks_distinctive_word` — a generic word in the query (Station / Mall / Medical Center / City / תחנת רכבת) outranks the distinctive word beside it
- shape of the miss: `correct_answer_outranked`

**Verdict (human):** _______________________

### P005 — `Yitzhak Navon`  (en, station)

- expected: **JLM Navon** at 31.7888, 35.2027 (tol 500 m)
- returned: **Yitzhak Navon/Herzl** (STOP, gtfs, id `mot10day_37603`) at 32.687932, 35.231012 — **100014 m** away
- next candidates: Yitzhak Navon/HaBanim (gtfs, מגדל העמק); Golda Meir/Yitzhak Navon (gtfs, מודיעין-מכבים-רעות); Yitzhak Navon/Shibolim (gtfs, עפולה)
- cause: `street_named_after_target_outranks_it` — a bus stop on a street named after the target outranks the target itself (KDP-010's trap, beyond railway stations)
- shape of the miss: `different_locality`

**Verdict (human):** _______________________

### P012 — `נמל תעופה בן גוריון`  (he, station)

- expected: **TLV Airport** at 32.0004, 34.8705 (tol 1500 m)
- returned: **נמל התעופה בן-גוריון** (PLACE, osm, id `way/[198356187]`) at 32.021939, 34.896555 — **3431 m** away
- next candidates: שדה תעופה בן גוריון/טרמינל 1 (gtfs, ?); בן גוריון (gtfs, חיפה); בן גוריון (gtfs, נס ציונה)
- cause: `large_poi_centroid_vs_transit_access_point` — a large POI's centroid is a legitimate answer but is kilometres from the transit access point a traveller departs from
- shape of the miss: `near_miss_outside_tolerance`
- corpus note: see P011

**Verdict (human):** _______________________

### P013 — `Herzliya Station`  (en, station)

- expected: **Herzliya** at 32.163558, 34.817406 (tol 500 m)
- returned: **Herzliya Center MDA Station** (PLACE, osm, id `way/[171523436]`) at 32.166798, 34.848765 — **2974 m** away
- next candidates: Hertsliya Railway Station (gtfs, הרצליה); Mount Herzl Light Rail Station (gtfs, ירושלים / القدس); Gas Station (gtfs, دالية الكرمل)
- cause: `generic_word_outranks_distinctive_word` — a generic word in the query (Station / Mall / Medical Center / City / תחנת רכבת) outranks the distinctive word beside it
- shape of the miss: `correct_answer_outranked`
- corpus note: corrected 4 Sep (POC-5) from GTFS stop 10943 הרצליה; the hand-entered coordinate was 778 m out

**Verdict (human):** _______________________

### P023 — `Tel Aviv University`  (en, poi_university)

- expected: **TAU** at 32.1133, 34.8044 (tol 900 m)
- returned: **Tel Aviv University – Expo** (STOP, gtfs, id `mot10day_10944`) at 32.103515, 34.804499 — **1088 m** away
- next candidates: Tel Aviv University (osm, תל־אביב–יפו); Tel Aviv University (osm, תל־אביב–יפו); Tel Aviv University (osm, תל־אביב–יפו)
- cause: `satellite_stop_preferred_over_the_poi` — a satellite stop of the POI outranks the POI itself
- shape of the miss: `correct_answer_outranked`

**Verdict (human):** _______________________

### P030 — `Ichilov`  (en, poi_hospital)

- expected: **Sourasky** at 32.08, 34.79 (tol 700 m)
- returned: **Weizmann/Ichilov** (STOP, gtfs, id `mot10day_24347`) at 32.339836, 34.859845 — **29630 m** away
- next candidates: HaHistadrut/Ichilov (gtfs, פתח תקווה); Ichilov Hospital/Weizmann (gtfs, תל־אביב–יפו); Yehoshua Tahon/Ichilov (gtfs, נתניה)
- cause: `street_named_after_target_outranks_it` — a bus stop on a street named after the target outranks the target itself (KDP-010's trap, beyond railway stations)
- shape of the miss: `correct_answer_outranked`
- corpus note: colloquial name, not the official one

**Verdict (human):** _______________________

### P031 — `איכילוב`  (he, poi_hospital)

- expected: **Sourasky** at 32.08, 34.79 (tol 700 m)
- returned: **ההסתדרות/איכילוב** (STOP, gtfs, id `mot10day_16579`) at 32.086035, 34.885385 — **9012 m** away
- next candidates: וייצמן/איכילוב (gtfs, נתניה); ביה"ח איכילוב/ויצמן (gtfs, תל־אביב–יפו); יהושע טהון/איכילוב (gtfs, נתניה)
- cause: `street_named_after_target_outranks_it` — a bus stop on a street named after the target outranks the target itself (KDP-010's trap, beyond railway stations)
- shape of the miss: `correct_answer_outranked`

**Verdict (human):** _______________________

### P033 — `Rambam Medical Center`  (en, poi_hospital)

- expected: **Rambam** at 32.8347, 34.9857 (tol 700 m)
- returned: **Medical Center/Ramat Yam** (STOP, gtfs, id `mot10day_14865`) at 32.177795, 34.802879 — **75030 m** away
- next candidates: Lin Medical Center (gtfs, חיפה); Galil Medical Center (gtfs, נהריה); Al-Razi Medical Center (gtfs, טייבה)
- cause: `generic_word_outranks_distinctive_word` — a generic word in the query (Station / Mall / Medical Center / City / תחנת רכבת) outranks the distinctive word beside it
- shape of the miss: `different_locality`

**Verdict (human):** _______________________

### P038 — `Malha Mall`  (en, poi_mall)

- expected: **Malha** at 31.7513, 35.1875 (tol 700 m)
- returned: **Mall/HaGalil** (STOP, gtfs, id `mot10day_31916`) at 32.971107, 35.504439 — **138865 m** away
- next candidates: Malcha Mall (osm, ירושלים / القدس); Lev Ha'Ir Mall (gtfs, הרצליה); Nahariya Mall (gtfs, נהריה)
- cause: `generic_word_outranks_distinctive_word` — a generic word in the query (Station / Mall / Medical Center / City / תחנת רכבת) outranks the distinctive word beside it
- shape of the miss: `correct_answer_outranked`

**Verdict (human):** _______________________

### P049 — `Masada`  (en, poi_landmark)

- expected: **Masada** at 31.3156, 35.3539 (tol 2000 m)
- returned: **Masada** (STOP, gtfs, id `mot10day_10999`) at 32.80953, 34.991994 — **169582 m** away
- next candidates: Masada (gtfs, מעלות תרשיחא); Masada (gtfs, מועצה אזורית תמר); Hasida/Masada (gtfs, פרדס חנה - כרכור)
- cause: `street_named_after_target_outranks_it` — a bus stop on a street named after the target outranks the target itself (KDP-010's trap, beyond railway stations)
- shape of the miss: `correct_answer_outranked`
- corpus note: remote; large tolerance

**Verdict (human):** _______________________

### P051 — `Dizengoff 100 Tel Aviv`  (en, address)

- expected: **Dizengoff St** at 32.0793, 34.774 (tol 700 m)
- returned: **Tel Aviv Harbor/Disengoff** (STOP, gtfs, id `mot10day_13753`) at 32.096871, 34.775888 — **1962 m** away
- next candidates: Dizenghoff Center/King Goerge (gtfs, תל־אביב–יפו); Dizengoff Center/Dizengoff (gtfs, תל־אביב–יפו); Dizengoff Square/Reines (gtfs, תל־אביב–יפו)
- cause: `latin_address_index_missing` — street addresses in Latin script return no address candidate at all (the address index answers Hebrew)
- shape of the miss: `correct_answer_outranked`

**Verdict (human):** _______________________

### P053 — `Rothschild Boulevard 1 Tel Aviv`  (en, address)

- expected: **Rothschild** at 32.0637, 34.7699 (tol 700 m)
- returned: **Shazar Boulevard/Rothschild** (STOP, gtfs, id `mot10day_10859`) at 31.244415, 34.805504 — **91163 m** away
- next candidates: Rothschild/Shazar Boulevard (gtfs, באר שבע); Rothschild/HaAtzmaut Boulevard (gtfs, בת ים); Ha'Atsma'ut Boulevard/Rothschild (gtfs, בת ים)
- cause: `latin_address_index_missing` — street addresses in Latin script return no address candidate at all (the address index answers Hebrew)
- shape of the miss: `different_locality`

**Verdict (human):** _______________________

### P056 — `Jaffa Street 97 Jerusalem`  (en, address)

- expected: **Jaffa St JLM** at 31.7857, 35.211 (tol 700 m)
- returned: **Jerusalem/Palmah A** (STOP, gtfs, id `mot10day_27306`) at 32.85182, 35.077851 — **119206 m** away
- next candidates: Jerusalem/Shlomo Levi (gtfs, ראשון לציון); Shlomo Levy/Jerusalem (gtfs, ראשון לציון); Jerusalem Gate/4313 (gtfs, באר יעקב)
- cause: `latin_address_index_missing` — street addresses in Latin script return no address candidate at all (the address index answers Hebrew)
- shape of the miss: `different_locality`
- corpus note: 'Jaffa St' exists in several cities

**Verdict (human):** _______________________

### P057 — `יפו 97 ירושלים`  (he, address)

- expected: **Jaffa St JLM** at 31.7857, 35.211 (tol 700 m)
- returned: **ירושלים 97** (ADDRESS, other, id ``) at 32.046868, 34.758658 — **51635 m** away
- next candidates: יפו 97 (other, ירושלים / القدس); יפו 97 (other, ירושלים / القدس); יפו 97 (other, ירושלים / القدس)
- cause: `city_qualifier_matched_as_a_name_token` — the city qualifier in an address query is matched as another name token, not as a locality filter
- shape of the miss: `correct_answer_outranked`

**Verdict (human):** _______________________

### P058 — `King George 15 Jerusalem`  (en, address)

- expected: **King George** at 31.78, 35.2178 (tol 700 m)
- returned: **Jerusalem/Palmah A** (STOP, gtfs, id `mot10day_27306`) at 32.85182, 35.077851 — **119904 m** away
- next candidates: Jerusalem/Shlomo Levi (gtfs, ראשון לציון); Shlomo Levy/Jerusalem (gtfs, ראשון לציון); Jerusalem Gate/4313 (gtfs, באר יעקב)
- cause: `latin_address_index_missing` — street addresses in Latin script return no address candidate at all (the address index answers Hebrew)
- shape of the miss: `correct_answer_outranked`

**Verdict (human):** _______________________

### P059 — `Herzl 50 Haifa`  (en, address)

- expected: **Herzl Haifa** at 32.8156, 34.9942 (tol 800 m)
- returned: **Herzl/Gan HaIr** (STOP, gtfs, id `mot10day_19847`) at 31.893974, 34.811615 — **103905 m** away
- next candidates: Herzl/En HaKore (gtfs, ראשון לציון); Herzl/Ets Ha'Afarsek (gtfs, יהוד מונוסון); Herzl/HaHagana (gtfs, עפולה)
- cause: `latin_address_index_missing` — street addresses in Latin script return no address candidate at all (the address index answers Hebrew)
- shape of the miss: `different_locality`
- corpus note: 'Herzl' street in most cities

**Verdict (human):** _______________________

### P060 — `Ben Yehuda 20 Tel Aviv`  (en, address)

- expected: **Ben Yehuda TA** at 32.079, 34.7686 (tol 700 m)
- returned: **Dizengoff/Ben Yehuda** (STOP, gtfs, id `mot10day_13800`) at 32.096302, 34.775963 — **2045 m** away
- next candidates: Ben Yehuda/Shapira (gtfs, אשקלון); Ironi He/Ben Yehuda (gtfs, תל־אביב–יפו); Yehuda Stein/David Razi'el Blvd (gtfs, רמלה)
- cause: `latin_address_index_missing` — street addresses in Latin script return no address candidate at all (the address index answers Hebrew)
- shape of the miss: `correct_answer_outranked`
- corpus note: also a Jerusalem street

**Verdict (human):** _______________________

### P062 — `HaNevi'im 20 Jerusalem`  (en, address)

- expected: **HaNeviim** at 31.7828, 35.22 (tol 700 m)
- returned: **Jerusalem Gate/Bahad 20** (STOP, gtfs, id `mot10day_18617`) at 31.956, 34.843278 — **40453 m** away
- next candidates: HaNevi'im/HaRav Kook (gtfs, ירושלים / القدس); HaNevi'im/Ha'Ayin Het (gtfs, ירושלים / القدس); HaNevi'im/Sapir Blvd (gtfs, טבריה)
- cause: `latin_address_index_missing` — street addresses in Latin script return no address candidate at all (the address index answers Hebrew)
- shape of the miss: `correct_answer_outranked`
- corpus note: apostrophe + transliteration

**Verdict (human):** _______________________

### P063 — `Sokolov 30 Ramat Gan`  (en, address)

- expected: **Sokolov RG** at 32.0836, 34.811 (tol 800 m)
- returned: **Sokolov/Ephraim Katzir** (STOP, gtfs, id `mot10day_22292`) at 32.165931, 34.901685 — **12520 m** away
- next candidates: Sokolov Railway Station (gtfs, הוד השרון); Sokolov/HaRav Kotler (gtfs, בני ברק); Weizmann Blvd/Sokolov (gtfs, נתניה)
- cause: `latin_address_index_missing` — street addresses in Latin script return no address candidate at all (the address index answers Hebrew)
- shape of the miss: `same_locality_wrong_feature`

**Verdict (human):** _______________________

### P064 — `Rager Boulevard Beersheba`  (en, address)

- expected: **Rager Blvd** at 31.253, 34.795 (tol 900 m)
- returned: **Afeka/KKL Boulevard** (STOP, gtfs, id `mot10day_12810`) at 32.120097, 34.807805 — **96424 m** away
- next candidates: Ben Gurion Boulevard (gtfs, קרית מוצקין); Hen Boulevard/Burla (gtfs, קרית ביאליק); Bar Lev Boulevard/Zachs (gtfs, ירושלים / القدس)
- cause: `latin_address_index_missing` — street addresses in Latin script return no address candidate at all (the address index answers Hebrew)
- shape of the miss: `different_locality`

**Verdict (human):** _______________________

### P065 — `הרצל 50 חיפה`  (he, address)

- expected: **Herzl Haifa** at 32.8156, 34.9942 (tol 800 m)
- returned: **הרצל 50** (ADDRESS, other, id ``) at 32.807527, 35.000791 — **1089 m** away
- next candidates: הרצל/יואל (gtfs, חיפה); הרצל/הלל יפה (gtfs, חיפה); הרצל ב (gtfs, קריית טבעון)
- cause: `corpus_point_approximate_engine_answer_plausible` — the engine's answer is plausible and the hand-entered corpus point is the less certain of the two — a human verdict, not an engine failure
- shape of the miss: `correct_answer_outranked`

**Verdict (human):** _______________________

### P074 — `Old City Jerusalem`  (en, neighborhood)

- expected: **Old City** at 31.7767, 35.23 (tol 1200 m)
- returned: **Weizmann/Jerusalem City Hall** (STOP, gtfs, id `mot10day_26729`) at 32.823534, 35.081862 — **117232 m** away
- next candidates: The Old City (gtfs, עכו); Old City G (gtfs, المغار); Jerusalem City Hall (osm, ירושלים / القدس)
- cause: `generic_word_outranks_distinctive_word` — a generic word in the query (Station / Mall / Medical Center / City / תחנת רכבת) outranks the distinctive word beside it
- shape of the miss: `correct_answer_outranked`

**Verdict (human):** _______________________

### P081 — `Netania`  (en, misspelling)

- expected: **Netanya** at 32.3097, 34.8619 (tol 2000 m)
- returned: **Netania** (PLACE, osm, id `node/[1683129849]`) at 32.328618, 34.856625 — **2161 m** away
- next candidates: Netanya (gtfs, נתניה); Netanya Stadium (gtfs, נתניה); HaNassi/Yoni Netanyahu (gtfs, הרצליה)
- cause: `corpus_point_approximate_engine_answer_plausible` — the engine's answer is plausible and the hand-entered corpus point is the less certain of the two — a human verdict, not an engine failure
- shape of the miss: `correct_answer_outranked`

**Verdict (human):** _______________________

### P083 — `Savidor Merkaz`  (en, misspelling)

- expected: **TA Savidor** at 32.0836, 34.7981 (tol 400 m)
- returned: **Merkaz Horev/Pica** (STOP, gtfs, id `mot10day_25990`) at 32.784166, 34.986637 — **79884 m** away
- next candidates: Merkaz HaBama (gtfs, גני תקווה); Al Qasar/Al Merkaz (gtfs, ירושלים / القدس); Dorot/Merkaz HaKibbutz (gtfs, מועצה אזורית שער הנגב)
- cause: `transliterated_hebrew_word_absent_from_latin_index` — a transliterated Hebrew word (Merkaz) is absent from the feed's Latin names, which use the translation (Center)
- shape of the miss: `different_locality`
- corpus note: mixed transliteration

**Verdict (human):** _______________________

### P086 — `Petah Tikva`  (en, translit)

- expected: **Petah Tikva** at 32.087, 34.887 (tol 3000 m)
- returned: **Petah Tikva A** (STOP, gtfs, id `mot10day_3054`) at 31.793709, 35.203449 — **44218 m** away
- next candidates: Petah Tikva/Etsel (gtfs, נתניה); Rashi/Petah Tikva (gtfs, אשדוד); Petah Tikva (osm, מועצה אזורית דרום השרון)
- cause: `street_named_after_target_outranks_it` — a bus stop on a street named after the target outranks the target itself (KDP-010's trap, beyond railway stations)
- shape of the miss: `different_locality`
- corpus note: variant 1 of 3

**Verdict (human):** _______________________

### P087 — `Petach Tikwa`  (en, translit)

- expected: **Petah Tikva** at 32.087, 34.887 (tol 3000 m)
- returned: **Petach Tikwa** (PLACE, osm, id `way/[242464393]`) at 32.081814, 34.920334 — **3193 m** away
- next candidates: Petach Tiqwa/Geva (gtfs, נתניה); Petach Tikva (osm, פתח תקווה); Petah Tikva A (gtfs, ירושלים / القدس)
- cause: `osm_duplicate_named_feature_outranks_the_city` — two OSM features carry the city's name and the higher-ranked one is kilometres away, in a different municipality
- shape of the miss: `correct_answer_outranked`
- corpus note: variant 2 of 3

**Verdict (human):** _______________________

### P088 — `Petah Tiqwa`  (en, translit)

- expected: **Petah Tikva** at 32.087, 34.887 (tol 3000 m)
- returned: **Petah Tiqwa** (PLACE, osm, id `way/[242464393]`) at 32.081814, 34.920334 — **3193 m** away
- next candidates: Petach Tiqwa/Geva (gtfs, נתניה); Petah Tikwa (osm, פתח תקווה); Petah Tikva A (gtfs, ירושלים / القدس)
- cause: `osm_duplicate_named_feature_outranks_the_city` — two OSM features carry the city's name and the higher-ranked one is kilometres away, in a different municipality
- shape of the miss: `correct_answer_outranked`
- corpus note: variant 3 of 3

**Verdict (human):** _______________________

### P089 — `Rishon LeTsiyon`  (en, translit)

- expected: **Rishon** at 31.964, 34.804 (tol 3000 m)
- returned: **Rishon LeTsiyon Beach** (STOP, gtfs, id `mot10day_23859`) at 31.996452, 34.733902 — **7532 m** away
- next candidates: Rishon LeTsiyon (osm, ראשון לציון); HaMem Gimel/Rishon LeTsiyon (gtfs, ירושלים / القدس); Rishon LeTsiyon/Rehovot (gtfs, פתח תקווה)
- cause: `satellite_stop_preferred_over_the_poi` — a satellite stop of the POI outranks the POI itself
- shape of the miss: `correct_answer_outranked`
- corpus note: ts vs tz

**Verdict (human):** _______________________

### P093 — `Akko`  (en, translit)

- expected: **Akko** at 32.928, 35.082 (tol 3000 m)
- returned: **Akko Road/HaGefen** (STOP, gtfs, id `mot10day_26497`) at 32.829962, 35.080975 — **10902 m** away
- next candidates: HaTel/Akko Road (gtfs, קרית ביאליק); Akko Road/Road 79 (gtfs, קרית מוצקין); Akko Mall/Ben Ami (gtfs, עכו)
- cause: `street_named_after_target_outranks_it` — a bus stop on a street named after the target outranks the target itself (KDP-010's trap, beyond railway stations)
- shape of the miss: `correct_answer_outranked`

**Verdict (human):** _______________________

### P095 — `Central Station`  (en, near_dependent)

- expected: **TA CBS** at 32.057, 34.78 (tol 1500 m)
- returned: **Central Station** (STOP, gtfs, id `mot10day_4510`) at 31.788492, 35.202603 — **49822 m** away
- next candidates: Central Station (gtfs, אשדוד); Central Station/Yafo (gtfs, ירושלים / القدس); Central Station (gtfs, נצרת)
- cause: `near_bias_not_applied_at_default_placebias` — the `near` bias point has no effect at MOTIS's default placeBias
- shape of the miss: `different_locality`
- corpus note: near=Tel Aviv

**Verdict (human):** _______________________

### P097 — `Herzl`  (en, near_dependent)

- expected: **Herzl TA area** at 32.08, 34.77 (tol 3000 m)
- returned: **HaRo'e/Herzl** (STOP, gtfs, id `mot10day_14426`) at 32.083775, 34.815945 — **4349 m** away
- next candidates: Herzl/Wolfson (gtfs, תל־אביב–יפו); Krinitsi/Herzl (gtfs, רמת גן); Herzl/Mintz (gtfs, נתניה)
- cause: `near_bias_applied_but_wrong_feature` — the `near` bias point was applied but landed on a different same-named feature inside the biased region
- shape of the miss: `correct_answer_outranked`
- corpus note: near=Tel Aviv

**Verdict (human):** _______________________

### P099 — `HaTachana`  (en, near_dependent)

- expected: **HaTachana TA** at 32.061, 34.762 (tol 2000 m)
- returned: **Hatachana** (PLACE, osm, id `node/[5109820219]`) at 33.277532, 35.57773 — **155333 m** away
- next candidates: HaTachana Parking (osm, תל־אביב–יפו); Hatachana Haisraelith (osm, תל־אביב–יפו); HaTachana (osm, תל־אביב–יפו)
- cause: `near_bias_not_applied_at_default_placebias` — the `near` bias point has no effect at MOTIS's default placeBias
- shape of the miss: `correct_answer_outranked`
- corpus note: near=Tel Aviv; common stop name nationwide

**Verdict (human):** _______________________

