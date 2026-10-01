# H3 route-review sheet — through the API (POST /v1/journeys)

> **Scheduled only; realtime not enabled.** Times are MOT timetable times. No delay, prediction or alert is shown.

**You are the reviewer.** Everything machine-made below is context. Fill only the `Usable? (Y/N)` and `Notes` cells yourself, comparing with Google Maps, Moovit or BetterRail at the stated date and time. The generator never writes a verdict. Release gate: at least **9 of the 10 required journeys** judged usable.

## Generation

- Generation id: `5eb4e43d9456b96a68ee44ffb7a58fe9137ed16bf40a670cf513c34564e44249` (mode `real`, freshness `current`)
- Data built: 2026-10-01T12:41:32.586765Z
- Coverage window (half-open, as reported by the API): 2026-10-01T00:00:00+03:00 .. 2026-11-01T00:00:00+02:00
- Window used for dates: 2026-10-01 00:00 .. 2026-11-01 00:00 Asia/Jerusalem; earliest request instant 2026-10-01 00:00
- Capabilities reported: realtime `not_enabled`, alerts `not_enabled`
- Generated 2026-10-01T14:58:19Z (2026-10-01 17:58 Israel) against `http://127.0.0.1:8500`
- Corpus `poc/corpora/journeys.json` sha256 `5fc013a5e1c52f16…`; case IDs are the PoC IDs. Coordinates are the corpus's approximate hand-entered points; the API plans from them.
- Request options: lang `he`, results 3, walking limits API defaults, arrive-by variants off
- Raw requests and responses: `acceptance-oct1b-20261001-02-h3-review-raw.json`

## Required ten — your tally

| # | Case | Requested | Usable? (Y/N) |
|---|---|---|---|
| 1 | J01 | Mon 2026-10-05 08:00 (UTC+03:00) | |
| 2 | J04 | Wed 2026-10-07 18:30 (UTC+03:00) | |
| 3 | J11 | Mon 2026-10-05 08:00 (UTC+03:00) | |
| 4 | J12 | Mon 2026-10-05 08:00 (UTC+03:00) | |
| 5 | J15 | Mon 2026-10-05 08:00 (UTC+03:00) | |
| 6 | J16 | Mon 2026-10-05 08:00 (UTC+03:00) | |
| 7 | J19 | Mon 2026-10-05 08:00 (UTC+03:00) | |
| 8 | J21 | Tue 2026-10-06 23:40 (UTC+03:00) | |
| 9 | J22 | Wed 2026-10-07 02:30 (UTC+03:00) | |
| 10 | J23 | Wed 2026-10-07 02:30 (UTC+03:00) | |

Total usable: ____ / 10

## Date selection

| Case | Rule | Requested (Asia/Jerusalem) | Calendar flags |
|---|---|---|---|
| J01 | weekday_morning | depart Mon 2026-10-05 08:00 (UTC+03:00) | ordinary day |
| J02 | weekday_morning | depart Mon 2026-10-05 08:00 (UTC+03:00) | ordinary day |
| J03 | weekday_midday | depart Tue 2026-10-06 13:00 (UTC+03:00) | ordinary day |
| J04 | weekday_evening | depart Wed 2026-10-07 18:30 (UTC+03:00) | ordinary day |
| J05 | weekday_midday | depart Tue 2026-10-06 13:00 (UTC+03:00) | ordinary day |
| J06 | weekday_morning | depart Mon 2026-10-05 08:00 (UTC+03:00) | ordinary day |
| J07 | weekday_evening | depart Wed 2026-10-07 18:30 (UTC+03:00) | ordinary day |
| J08 | weekday_morning | depart Mon 2026-10-05 08:00 (UTC+03:00) | ordinary day |
| J09 | weekday_evening | depart Wed 2026-10-07 18:30 (UTC+03:00) | ordinary day |
| J10 | weekday_midday | depart Tue 2026-10-06 13:00 (UTC+03:00) | ordinary day |
| J11 | weekday_morning | depart Mon 2026-10-05 08:00 (UTC+03:00) | ordinary day |
| J12 | weekday_morning | depart Mon 2026-10-05 08:00 (UTC+03:00) | ordinary day |
| J13 | weekday_midday | depart Tue 2026-10-06 13:00 (UTC+03:00) | ordinary day |
| J14 | weekday_morning | depart Mon 2026-10-05 08:00 (UTC+03:00) | ordinary day |
| J15 | weekday_morning | depart Mon 2026-10-05 08:00 (UTC+03:00) | ordinary day |
| J16 | weekday_morning | depart Mon 2026-10-05 08:00 (UTC+03:00) | ordinary day |
| J17 | weekday_morning | depart Mon 2026-10-05 08:00 (UTC+03:00) | ordinary day |
| J18 | weekday_morning | depart Mon 2026-10-05 08:00 (UTC+03:00) | ordinary day |
| J19 | weekday_morning | depart Mon 2026-10-05 08:00 (UTC+03:00) | ordinary day |
| J20 | weekday_midday | depart Tue 2026-10-06 13:00 (UTC+03:00) | ordinary day |
| J21 | late_night | depart Tue 2026-10-06 23:40 (UTC+03:00) | ordinary day |
| J22 | after_midnight | depart Wed 2026-10-07 02:30 (UTC+03:00) | ordinary day |
| J23 | after_midnight | depart Wed 2026-10-07 02:30 (UTC+03:00) | ordinary day |
| J24 | weekday_midday | depart Tue 2026-10-06 13:00 (UTC+03:00) | ordinary day |
| J25 | shabbat | depart Sat 2026-10-10 12:00 (UTC+03:00) | Shabbat |
| J11-FRI | friday_afternoon | depart Fri 2026-10-09 15:30 (UTC+03:00) | Friday (erev Shabbat) |
| J12-FRI | friday_afternoon | depart Fri 2026-10-09 15:30 (UTC+03:00) | Friday (erev Shabbat) |
| J11-SAT | shabbat | depart Sat 2026-10-10 12:00 (UTC+03:00) | Shabbat |
| J05-SAT | shabbat | depart Sat 2026-10-10 12:00 (UTC+03:00) | Shabbat |
| J01-HOL | holiday_morning | depart Thu 2026-10-01 08:00 (UTC+03:00) | Holiday calendar: Chol HaMoed Sukkot (chol_hamoed) |
| J12-HOL | holiday_midday | depart Thu 2026-10-01 13:00 (UTC+03:00) | Holiday calendar: Chol HaMoed Sukkot (chol_hamoed) |
| J01-DST | dst_day_peak | depart Sun 2026-10-25 08:00 (UTC+02:00) | DST fall-back day: clocks go back 02:00 to 01:00 |
| J22-DST1 | dst_repeat_first | depart Sun 2026-10-25 01:30 (UTC+03:00) | DST fall-back day: clocks go back 02:00 to 01:00 |
| J22-DST2 | dst_repeat_second | depart Sun 2026-10-25 01:30 (UTC+02:00) | DST fall-back day: clocks go back 02:00 to 01:00 |

Holiday dates come from a built-in 2026 table and any `--holiday` overrides; verify them against the official calendar. Cases marked Shabbat, Friday, holiday or DST are deliberately unusual: no or reduced service can be correct there.

---

## J01 — Dizengoff Center (דיזנגוף סנטר) → Ramat Gan Bursa (רמת גן בורסה)

**Required journey #1** — PRD §7 #1 Tel Aviv → Ramat Gan · category `tel-aviv-urban-bus` · calendar rule `weekday_morning`

**Requested:** Depart at Mon 2026-10-05 08:00 (UTC+03:00)  
Request field: `departAt=2026-10-05T08:00:00+03:00`
**Calendar flags:** ordinary day
**Compare:** [Google Maps transit](https://www.google.com/maps/dir/?api=1&origin=32.0757,34.7748&destination=32.0838,34.8044&travelmode=transit) · [Moovit (unofficial deep link; may not prefill)](https://moovitapp.com/?fll=32.0757_34.7748&tll=32.0838_34.8044&from=Dizengoff%20Center&to=Ramat%20Gan%20Bursa) · Set the time yourself to **Depart at 08:00, Mon 2026-10-05** (Google's documented URL has no time parameter).
**Corpus expectation (context, not a verdict):** outcome `route`, max_duration_min = 55, max_transfers = 2, min_duration_min = 10, modes_any_of = ['bus', 'light_rail']

> What to check: Would a Tel Aviv resident actually take this? Compare against Moovit.

**API RESULT: 3 journey option(s) returned** (scheduled times).
Machine note: matches the corpus expectation `route`. This is not a judgement of quality.
Request id `d6eb4c64b13e465aa3c85c22dd3d0002`.

**Option 1:** departs Mon 2026-10-05 08:06, arrives Mon 2026-10-05 08:24; total 18 min, 0 transfer(s), walking 9 min / 534 m

1. Walk 5 min, 294 m: START 08:06 -> דיזנגוף סנטר/המלך ג'ורג' 08:11
2. **bus 82** (דן) toward פתח תקווה_בית רבקה: board דיזנגוף סנטר/המלך ג'ורג' [code 20785] 08:11 -> alight ת.רק''ל אבא הלל/דרך ז'בוטינסקי [code 21644] 08:20 (service date 2026-10-05, trip `503091_051026`)
3. Walk 4 min, 240 m: ת.רק''ל אבא הלל/דרך ז'בוטינסקי 08:20 -> END 08:24

Transfers (alight to next boarding, including any walk): none

**Option 2:** departs Mon 2026-10-05 08:14, arrives Mon 2026-10-05 08:33; total 19 min, 0 transfer(s), walking 7 min / 384 m

1. Walk 3 min, 135 m: START 08:14 -> דיזנגוף סנטר/דיזנגוף 08:17
2. **bus 238** (דן) toward פתח תקווה_הדר גנים: board דיזנגוף סנטר/דיזנגוף [code 25565] 08:17 -> alight ת.רק''ל אבא הלל [code 26248] 08:29 (service date 2026-10-05, trip `46017670_051026`)
3. Walk 4 min, 249 m: ת.רק''ל אבא הלל 08:29 -> END 08:33

Transfers (alight to next boarding, including any walk): none

**Option 3:** departs Mon 2026-10-05 08:17, arrives Mon 2026-10-05 08:35; total 18 min, 0 transfer(s), walking 9 min / 534 m

1. Walk 5 min, 294 m: START 08:17 -> דיזנגוף סנטר/המלך ג'ורג' 08:22
2. **bus 82** (דן) toward פתח תקווה_בית רבקה: board דיזנגוף סנטר/המלך ג'ורג' [code 20785] 08:22 -> alight ת.רק''ל אבא הלל/דרך ז'בוטינסקי [code 21644] 08:31 (service date 2026-10-05, trip `631360_051026`)
3. Walk 4 min, 240 m: ת.רק''ל אבא הלל/דרך ז'בוטינסקי 08:31 -> END 08:35

Transfers (alight to next boarding, including any walk): none

| Usable? (Y/N) | Notes | Compared against / when checked |
|---|---|---|
|  |  |  |

---

## J02 — Tel Aviv University (אוניברסיטת תל אביב) → Sourasky Medical Center (Ichilov) (בית חולים איכילוב)

category `tel-aviv-urban-bus` · calendar rule `weekday_morning`

**Requested:** Depart at Mon 2026-10-05 08:00 (UTC+03:00)  
Request field: `departAt=2026-10-05T08:00:00+03:00`
**Calendar flags:** ordinary day
**Compare:** [Google Maps transit](https://www.google.com/maps/dir/?api=1&origin=32.1133,34.8044&destination=32.08,34.79&travelmode=transit) · [Moovit (unofficial deep link; may not prefill)](https://moovitapp.com/?fll=32.1133_34.8044&tll=32.08_34.79&from=Tel%20Aviv%20University&to=Sourasky%20Medical%20Center%20%28Ichilov%29) · Set the time yourself to **Depart at 08:00, Mon 2026-10-05** (Google's documented URL has no time parameter).
**Corpus expectation (context, not a verdict):** outcome `route`, max_duration_min = 60, max_transfers = 2, min_duration_min = 12, modes_any_of = ['bus', 'light_rail', 'rail']

> What to check: Peak-hour campus-to-hospital trip. Is the walk at either end reasonable?

**API RESULT: 3 journey option(s) returned** (scheduled times).
Machine note: matches the corpus expectation `route`. This is not a judgement of quality.
Request id `72db0c99972e4506a980ea6ee097f5e0`.

**Option 1:** departs Mon 2026-10-05 08:00, arrives Mon 2026-10-05 08:26; total 26 min, 1 transfer(s), walking 13 min / 664 m

1. Walk 6 min, 389 m: START 08:00 -> האוניברסיטה/חיים לבנון 08:06
2. **bus 24** (מטרופולין) toward תל אביב יפו_מסוף כרמלית: board האוניברסיטה/חיים לבנון [code 21388] 08:06 -> alight דרך נמיר/יהודה המכבי [code 21188] 08:13 (service date 2026-10-05, trip `45060631_041026`)
3. Walk 2 min, 0 m: דרך נמיר/יהודה המכבי 08:13 -> דרך נמיר/יהודה המכבי 08:15
4. **bus 89** (דן) toward חולון_פארק פרס: board דרך נמיר/יהודה המכבי [code 21188] 08:15 -> alight ביה''ח איכילוב/ויצמן [code 21173] 08:21 (service date 2026-10-05, trip `13998604_051026`)
5. Walk 5 min, 275 m: ביה''ח איכילוב/ויצמן 08:21 -> END 08:26

Transfers (alight to next boarding, including any walk): דרך נמיר/יהודה המכבי -> דרך נמיר/יהודה המכבי: 2 min

**Option 2:** departs Mon 2026-10-05 08:05, arrives Mon 2026-10-05 08:30; total 25 min, 1 transfer(s), walking 14 min / 881 m

1. Walk 8 min, 495 m: START 08:05 -> אינשטיין/אהרון בארט 08:13
2. **bus 40** (דן) toward בת ים_מרכז הספורט: board אינשטיין/אהרון בארט [code 26635] 08:13 -> alight דרך נמיר/שדרות שאול המלך [code 20876] 08:23 (service date 2026-10-05, trip `616982_051026`)
3. Walk 2 min, 147 m: דרך נמיר/שדרות שאול המלך 08:23 -> שדרות שאול המלך/הנרייטה סולד 08:25
4. **bus 7** (דן) toward תל אביב יפו_רכבת האוניברסיטה: board שדרות שאול המלך/הנרייטה סולד [code 2320] 08:25 -> alight בית המשפט/ויצמן [code 21238] 08:26 (service date 2026-10-05, trip `4514429_051026`)
5. Walk 4 min, 239 m: בית המשפט/ויצמן 08:26 -> END 08:30

Transfers (alight to next boarding, including any walk): דרך נמיר/שדרות שאול המלך -> שדרות שאול המלך/הנרייטה סולד: 2 min

**Option 3:** departs Mon 2026-10-05 08:08, arrives Mon 2026-10-05 08:35; total 27 min, 2 transfer(s), walking 14 min / 618 m

1. Walk 6 min, 379 m: START 08:08 -> האוניברסיטה/חיים לבנון 08:14
2. **bus 10** (דן) toward חולון_מוזיאון אגד: board האוניברסיטה/חיים לבנון [code 21513] 08:14 -> alight סמינר הקיבוצים/דרך נמיר [code 25071] 08:19 (service date 2026-10-05, trip `45563633_051026`)
3. Walk 2 min, 0 m: סמינר הקיבוצים/דרך נמיר 08:20 -> סמינר הקיבוצים/דרך נמיר 08:22
4. **bus 249** (מטרופולין) toward תל אביב יפו_מסוף כרמלית: board סמינר הקיבוצים/דרך נמיר [code 25071] 08:22 -> alight בית הדר דפנה/שד' שאול המלך [code 25732] 08:28 (service date 2026-10-05, trip `585511882_041026`)
5. Walk 2 min, 0 m: בית הדר דפנה/שד' שאול המלך 08:28 -> בית הדר דפנה/שד' שאול המלך 08:30
6. **bus 18** (דן) toward בת ים_בית עלמין: board בית הדר דפנה/שד' שאול המלך [code 25732] 08:30 -> alight בית המשפט/ויצמן [code 21238] 08:31 (service date 2026-10-05, trip `8370319_051026`)
7. Walk 4 min, 239 m: בית המשפט/ויצמן 08:31 -> END 08:35

Transfers (alight to next boarding, including any walk): סמינר הקיבוצים/דרך נמיר -> סמינר הקיבוצים/דרך נמיר: 3 min; בית הדר דפנה/שד' שאול המלך -> בית הדר דפנה/שד' שאול המלך: 2 min

| Usable? (Y/N) | Notes | Compared against / when checked |
|---|---|---|
|  |  |  |

---

## J03 — Jaffa Clock Tower (מגדל השעון יפו) → Tel Aviv Savidor Center (תל אביב סבידור מרכז)

category `tel-aviv-urban-bus` · calendar rule `weekday_midday`

**Requested:** Depart at Tue 2026-10-06 13:00 (UTC+03:00)  
Request field: `departAt=2026-10-06T13:00:00+03:00`
**Calendar flags:** ordinary day
**Compare:** [Google Maps transit](https://www.google.com/maps/dir/?api=1&origin=32.0542,34.7522&destination=32.0836,34.7981&travelmode=transit) · [Moovit (unofficial deep link; may not prefill)](https://moovitapp.com/?fll=32.0542_34.7522&tll=32.0836_34.7981&from=Jaffa%20Clock%20Tower&to=Tel%20Aviv%20Savidor%20Center) · Set the time yourself to **Depart at 13:00, Tue 2026-10-06** (Google's documented URL has no time parameter).
**Corpus expectation (context, not a verdict):** outcome `route`, max_duration_min = 65, max_transfers = 2, min_duration_min = 15, modes_any_of = ['bus', 'light_rail']

> What to check: Jaffa to the main station. Does it use the red line where sensible?

**API RESULT: 3 journey option(s) returned** (scheduled times).
Machine note: matches the corpus expectation `route`. This is not a judgement of quality.
Request id `4fd4030465d3499995cd4e40f2fae135`.

**Option 1:** departs Tue 2026-10-06 13:04, arrives Tue 2026-10-06 13:35; total 31 min, 0 transfer(s), walking 11 min / 787 m

1. Walk 5 min, 356 m: START 13:04 -> יפת/לואי פסטר 13:09
2. **bus 44** (דן) toward תל אביב יפו_קריית עתידים: board יפת/לואי פסטר [code 20448] 13:09 -> alight ת. רכבת תל אביב - סבידור/דרך נמיר [code 24068] 13:29 (service date 2026-10-06, trip `44004405_051026`)
3. Walk 6 min, 431 m: ת. רכבת תל אביב - סבידור/דרך נמיר 13:29 -> END 13:35

Transfers (alight to next boarding, including any walk): none

**Option 2:** departs Tue 2026-10-06 13:06, arrives Tue 2026-10-06 13:39; total 33 min, 1 transfer(s), walking 14 min / 822 m

1. Walk 9 min, 639 m: START 13:06 -> כיכר השעון/מרזוק ועזר 13:15
2. **bus 54** (דן) toward קריית עתידים: board כיכר השעון/מרזוק ועזר [code 25303] 13:15 -> alight ת.רכבת ההגנה [code 25637] 13:24 (service date 2026-10-06, trip `8378487_051026`)
3. Walk 4 min, 156 m: ת.רכבת ההגנה 13:24 -> תל אביב ההגנה 13:28
4. **rail ** (רכבת ישראל) toward 318: board תל אביב ההגנה [code 17104] 13:30 -> alight תל אביב מרכז [code 17038] 13:38 (service date 2026-10-06, trip `1_520711`)
5. Walk 1 min, 27 m: תל אביב מרכז 13:38 -> END 13:39

Transfers (alight to next boarding, including any walk): ת.רכבת ההגנה -> תל אביב ההגנה: 6 min

**Option 3:** departs Tue 2026-10-06 13:07, arrives Tue 2026-10-06 13:42; total 35 min, 0 transfer(s), walking 21 min / 1366 m

1. Walk 13 min, 879 m: START 13:07 -> שלמה 13:20
2. **light_rail 1** (תבל) toward פתח תקווה_ת. מרכזית פתח תקווה: board שלמה [code 20546] 13:20 -> alight ארלוזורוב [code 20711] 13:34 (service date 2026-10-06, trip `585355926_021026`)
3. Walk 8 min, 487 m: ארלוזורוב 13:34 -> END 13:42

Transfers (alight to next boarding, including any walk): none

| Usable? (Y/N) | Notes | Compared against / when checked |
|---|---|---|
|  |  |  |

---

## J04 — Dizengoff Center (דיזנגוף סנטר) → Petah Tikva Kiryat Arye (פתח תקווה קרית אריה)

**Required journey #2** — PRD §7 #2 Tel Aviv → Petah Tikva · category `tel-aviv-urban-bus` · calendar rule `weekday_evening`

**Requested:** Depart at Wed 2026-10-07 18:30 (UTC+03:00)  
Request field: `departAt=2026-10-07T18:30:00+03:00`
**Calendar flags:** ordinary day
**Compare:** [Google Maps transit](https://www.google.com/maps/dir/?api=1&origin=32.0757,34.7748&destination=32.0956,34.8556&travelmode=transit) · [Moovit (unofficial deep link; may not prefill)](https://moovitapp.com/?fll=32.0757_34.7748&tll=32.0956_34.8556&from=Dizengoff%20Center&to=Petah%20Tikva%20Kiryat%20Arye) · Set the time yourself to **Depart at 18:30, Wed 2026-10-07** (Google's documented URL has no time parameter).
**Corpus expectation (context, not a verdict):** outcome `route`, max_duration_min = 90, max_transfers = 2, min_duration_min = 20, modes_any_of = ['bus', 'rail', 'light_rail']

> What to check: Evening peak. Does it prefer rail or bus, and is that the right call?

**API RESULT: 3 journey option(s) returned** (scheduled times).
Machine note: matches the corpus expectation `route`. This is not a judgement of quality.
Request id `08b2ba79d9ae4f5bbc01de32536b2fd0`.

**Option 1:** departs Wed 2026-10-07 18:31, arrives Wed 2026-10-07 19:06; total 35 min, 1 transfer(s), walking 13 min / 705 m

1. Walk 3 min, 135 m: START 18:31 -> דיזנגוף סנטר/דיזנגוף 18:34
2. **bus 63** (דן) toward רמת גן_אלוף שדה: board דיזנגוף סנטר/דיזנגוף [code 25565] 18:34 -> alight ת.רק''ל יהודית/דרך מנחם בגין [code 20727] 18:41 (service date 2026-10-07, trip `668878_051026`)
3. Walk 2 min, 93 m: ת.רק''ל יהודית/דרך מנחם בגין 18:41 -> יהודית 18:43
4. **light_rail 1** (תבל) toward פתח תקווה_ת. מרכזית פתח תקווה: board יהודית [code 20707] 18:43 -> alight שנקר [code 36309] 18:58 (service date 2026-10-07, trip `585268659_021026`)
5. Walk 8 min, 477 m: שנקר 18:58 -> END 19:06

Transfers (alight to next boarding, including any walk): ת.רק''ל יהודית/דרך מנחם בגין -> יהודית: 2 min

**Option 2:** departs Wed 2026-10-07 18:36, arrives Wed 2026-10-07 19:11; total 35 min, 0 transfer(s), walking 13 min / 753 m

1. Walk 5 min, 294 m: START 18:36 -> דיזנגוף סנטר/המלך ג'ורג' 18:41
2. **bus 82** (דן) toward פתח תקווה_בית רבקה: board דיזנגוף סנטר/המלך ג'ורג' [code 20785] 18:41 -> alight ת.רק''ל שנקר/דרך ז'בוטינסקי [code 32270] 19:03 (service date 2026-10-07, trip `15186667_051026`)
3. Walk 8 min, 459 m: ת.רק''ל שנקר/דרך ז'בוטינסקי 19:03 -> END 19:11

Transfers (alight to next boarding, including any walk): none

**Option 3:** departs Wed 2026-10-07 18:42, arrives Wed 2026-10-07 19:17; total 35 min, 1 transfer(s), walking 13 min / 705 m

1. Walk 3 min, 135 m: START 18:42 -> דיזנגוף סנטר/דיזנגוף 18:45
2. **bus 63** (דן) toward רמת גן_אלוף שדה: board דיזנגוף סנטר/דיזנגוף [code 25565] 18:45 -> alight ת.רק''ל יהודית/דרך מנחם בגין [code 20727] 18:52 (service date 2026-10-07, trip `13985921_051026`)
3. Walk 2 min, 93 m: ת.רק''ל יהודית/דרך מנחם בגין 18:52 -> יהודית 18:54
4. **light_rail 1** (תבל) toward פתח תקווה_ת. מרכזית פתח תקווה: board יהודית [code 20707] 18:54 -> alight שנקר [code 36309] 19:09 (service date 2026-10-07, trip `585373632_021026`)
5. Walk 8 min, 477 m: שנקר 19:09 -> END 19:17

Transfers (alight to next boarding, including any walk): ת.רק''ל יהודית/דרך מנחם בגין -> יהודית: 2 min

| Usable? (Y/N) | Notes | Compared against / when checked |
|---|---|---|
|  |  |  |

---

## J05 — Mahane Yehuda Market (שוק מחנה יהודה) → Mount Herzl (הר הרצל)

category `jerusalem-urban-light-rail` · calendar rule `weekday_midday`

**Requested:** Depart at Tue 2026-10-06 13:00 (UTC+03:00)  
Request field: `departAt=2026-10-06T13:00:00+03:00`
**Calendar flags:** ordinary day
**Compare:** [Google Maps transit](https://www.google.com/maps/dir/?api=1&origin=31.7853,35.2124&destination=31.7736,35.1806&travelmode=transit) · [Moovit (unofficial deep link; may not prefill)](https://moovitapp.com/?fll=31.7853_35.2124&tll=31.7736_35.1806&from=Mahane%20Yehuda%20Market&to=Mount%20Herzl) · Set the time yourself to **Depart at 13:00, Tue 2026-10-06** (Google's documented URL has no time parameter).
**Corpus expectation (context, not a verdict):** outcome `route`, max_duration_min = 45, max_transfers = 1, min_duration_min = 8, modes_any_of = ['light_rail', 'bus']

> What to check: This is the light rail's spine. If it routes by bus instead, something is wrong.

**API RESULT: 3 journey option(s) returned** (scheduled times).
Machine note: matches the corpus expectation `route`. This is not a judgement of quality.
Request id `89b6e0ed1227452bbf19b53fcb6cb7c4`.

**Option 1:** departs Tue 2026-10-06 13:02, arrives Tue 2026-10-06 13:27; total 25 min, 0 transfer(s), walking 11 min / 706 m

1. Walk 2 min, 145 m: START 13:02 -> מחנה יהודה 13:04
2. **light_rail 1** (כפיר) toward הדסה עין כרם: board מחנה יהודה [code 6172] 13:04 -> alight הר הרצל [code 6185] 13:18 (service date 2026-10-06, trip `12467281_021026`)
3. Walk 9 min, 561 m: הר הרצל 13:18 -> END 13:27

Transfers (alight to next boarding, including any walk): none

**Option 2:** departs Tue 2026-10-06 13:07, arrives Tue 2026-10-06 13:32; total 25 min, 0 transfer(s), walking 11 min / 706 m

1. Walk 2 min, 145 m: START 13:07 -> מחנה יהודה 13:09
2. **light_rail 1** (כפיר) toward הדסה עין כרם: board מחנה יהודה [code 6172] 13:09 -> alight הר הרצל [code 6185] 13:23 (service date 2026-10-06, trip `21129521_021026`)
3. Walk 9 min, 561 m: הר הרצל 13:23 -> END 13:32

Transfers (alight to next boarding, including any walk): none

**Option 3:** departs Tue 2026-10-06 13:12, arrives Tue 2026-10-06 13:37; total 25 min, 0 transfer(s), walking 11 min / 706 m

1. Walk 2 min, 145 m: START 13:12 -> מחנה יהודה 13:14
2. **light_rail 1** (כפיר) toward הדסה עין כרם: board מחנה יהודה [code 6172] 13:14 -> alight הר הרצל [code 6185] 13:28 (service date 2026-10-06, trip `8292667_021026`)
3. Walk 9 min, 561 m: הר הרצל 13:28 -> END 13:37

Transfers (alight to next boarding, including any walk): none

| Usable? (Y/N) | Notes | Compared against / when checked |
|---|---|---|
|  |  |  |

---

## J06 — Jerusalem Central Bus Station (תחנה מרכזית ירושלים) → Hebrew University Mount Scopus (האוניברסיטה העברית הר הצופים)

category `jerusalem-urban-light-rail` · calendar rule `weekday_morning`

**Requested:** Depart at Mon 2026-10-05 08:00 (UTC+03:00)  
Request field: `departAt=2026-10-05T08:00:00+03:00`
**Calendar flags:** ordinary day
**Compare:** [Google Maps transit](https://www.google.com/maps/dir/?api=1&origin=31.7887,35.203&destination=31.7936,35.2444&travelmode=transit) · [Moovit (unofficial deep link; may not prefill)](https://moovitapp.com/?fll=31.7887_35.203&tll=31.7936_35.2444&from=Jerusalem%20Central%20Bus%20Station&to=Hebrew%20University%20Mount%20Scopus) · Set the time yourself to **Depart at 08:00, Mon 2026-10-05** (Google's documented URL has no time parameter).
**Corpus expectation (context, not a verdict):** outcome `route`, max_duration_min = 70, max_transfers = 2, min_duration_min = 15, modes_any_of = ['light_rail', 'bus']

> What to check: Cross-city to Mount Scopus. Check the transfer point is a real interchange.

**API RESULT: 3 journey option(s) returned** (scheduled times).
Machine note: matches the corpus expectation `route`. This is not a judgement of quality.
Request id `8379b72c611f48f6855f39591fa19588`.

**Option 1:** departs Mon 2026-10-05 08:01, arrives Mon 2026-10-05 08:28; total 27 min, 1 transfer(s), walking 8 min / 347 m

1. Walk 1 min, 57 m: START 08:01 -> ת. מרכזית ירושלים/יפו 08:02
2. **bus 18** (אגד) toward מלחה: board ת. מרכזית ירושלים/יפו [code 4156] 08:02 -> alight ככר הדוידקה/הנביאים [code 1601] 08:07 (service date 2026-10-05, trip `8412260_051026`)
3. Walk 2 min, 0 m: ככר הדוידקה/הנביאים 08:07 -> ככר הדוידקה/הנביאים 08:09
4. **bus 19א** (אגד) toward מסוף הר הצופים: board ככר הדוידקה/הנביאים [code 1601] 08:12 -> alight האוניברסיטה העברית הר הצופים/מרטין בובר [code 1371] 08:23 (service date 2026-10-05, trip `8821728_051026`)
5. Walk 5 min, 290 m: האוניברסיטה העברית הר הצופים/מרטין בובר 08:23 -> END 08:28

Transfers (alight to next boarding, including any walk): ככר הדוידקה/הנביאים -> ככר הדוידקה/הנביאים: 5 min

**Option 2:** departs Mon 2026-10-05 08:07, arrives Mon 2026-10-05 08:30; total 23 min, 0 transfer(s), walking 10 min / 622 m

1. Walk 5 min, 332 m: START 08:07 -> שרי ישראל/יפו 08:12
2. **bus 568** (אקסטרה ירושלים) toward מסוף הר הצופים: board שרי ישראל/יפו [code 78] 08:12 -> alight האוניברסיטה העברית הר הצופים/מרטין בובר [code 1371] 08:25 (service date 2026-10-05, trip `585640525_051026`)
3. Walk 5 min, 290 m: האוניברסיטה העברית הר הצופים/מרטין בובר 08:25 -> END 08:30

Transfers (alight to next boarding, including any walk): none

**Option 3:** departs Mon 2026-10-05 08:08, arrives Mon 2026-10-05 08:32; total 24 min, 1 transfer(s), walking 8 min / 347 m

1. Walk 1 min, 57 m: START 08:08 -> ת. מרכזית ירושלים/יפו 08:09
2. **bus 74** (סופרבוס) toward חומת שמואל: board ת. מרכזית ירושלים/יפו [code 4156] 08:09 -> alight הנביאים/הרב קוק [code 3379] 08:16 (service date 2026-10-05, trip `584794982_031026`)
3. Walk 2 min, 0 m: הנביאים/הרב קוק 08:16 -> הנביאים/הרב קוק 08:18
4. **bus 19** (אגד) toward מסוף הר הצופים: board הנביאים/הרב קוק [code 3379] 08:18 -> alight האוניברסיטה העברית הר הצופים/מרטין בובר [code 1371] 08:27 (service date 2026-10-05, trip `585944010_051026`)
5. Walk 5 min, 290 m: האוניברסיטה העברית הר הצופים/מרטין בובר 08:27 -> END 08:32

Transfers (alight to next boarding, including any walk): הנביאים/הרב קוק -> הנביאים/הרב קוק: 2 min

| Usable? (Y/N) | Notes | Compared against / when checked |
|---|---|---|
|  |  |  |

---

## J07 — Yitzhak Navon Station (תחנת יצחק נבון) → Malha Mall (קניון מלחא)

category `jerusalem-urban-light-rail` · calendar rule `weekday_evening`

**Requested:** Depart at Wed 2026-10-07 18:30 (UTC+03:00)  
Request field: `departAt=2026-10-07T18:30:00+03:00`
**Calendar flags:** ordinary day
**Compare:** [Google Maps transit](https://www.google.com/maps/dir/?api=1&origin=31.7888,35.2027&destination=31.7513,35.1875&travelmode=transit) · [Moovit (unofficial deep link; may not prefill)](https://moovitapp.com/?fll=31.7888_35.2027&tll=31.7513_35.1875&from=Yitzhak%20Navon%20Station&to=Malha%20Mall) · Set the time yourself to **Depart at 18:30, Wed 2026-10-07** (Google's documented URL has no time parameter).
**Corpus expectation (context, not a verdict):** outcome `route`, max_duration_min = 70, max_transfers = 2, min_duration_min = 15, modes_any_of = ['light_rail', 'bus', 'rail']

> What to check: Does it consider the Malha rail branch, and is that sensible at this hour?

**API RESULT: 3 journey option(s) returned** (scheduled times).
Machine note: matches the corpus expectation `route`. This is not a judgement of quality.
Request id `47eb30563cf7417ca6fa2278687abaf1`.

**Option 1:** departs Wed 2026-10-07 18:33, arrives Wed 2026-10-07 18:56; total 23 min, 0 transfer(s), walking 14 min / 532 m

1. Walk 4 min, 227 m: START 18:33 -> שדרות שז''ר/בנייני האומה 18:37
2. **bus 531** (סופרבוס) toward גילה: board שדרות שז''ר/בנייני האומה [code 463] 18:37 -> alight אצטדיון טדי/א''ס ביתר [code 222] 18:46 (service date 2026-10-07, trip `584871058_031026`)
3. Walk 10 min, 305 m: אצטדיון טדי/א''ס ביתר 18:46 -> END 18:56

Transfers (alight to next boarding, including any walk): none

**Option 2:** departs Wed 2026-10-07 18:33, arrives Wed 2026-10-07 18:55; total 22 min, 1 transfer(s), walking 12 min / 367 m

1. Walk 4 min, 227 m: START 18:33 -> שדרות שז''ר/בנייני האומה 18:37
2. **bus 531** (סופרבוס) toward גילה: board שדרות שז''ר/בנייני האומה [code 463] 18:37 -> alight אצטדיון טדי/א''ס ביתר [code 222] 18:46 (service date 2026-10-07, trip `584871058_031026`)
3. Walk 2 min, 0 m: אצטדיון טדי/א''ס ביתר 18:46 -> אצטדיון טדי/א''ס ביתר 18:48
4. **bus 18** (אגד) toward מלחה: board אצטדיון טדי/א''ס ביתר [code 222] 18:48 -> alight קניון מלחה/א''ס מכבי [code 4171] 18:49 (service date 2026-10-07, trip `12879280_051026`)
5. Walk 6 min, 140 m: קניון מלחה/א''ס מכבי 18:49 -> END 18:55

Transfers (alight to next boarding, including any walk): אצטדיון טדי/א''ס ביתר -> אצטדיון טדי/א''ס ביתר: 2 min

**Option 3:** departs Wed 2026-10-07 18:34, arrives Wed 2026-10-07 18:57; total 23 min, 0 transfer(s), walking 14 min / 532 m

1. Walk 4 min, 227 m: START 18:34 -> שדרות שז''ר/בנייני האומה 18:38
2. **bus 504** (סופרבוס) toward חומת שמואל: board שדרות שז''ר/בנייני האומה [code 463] 18:38 -> alight אצטדיון טדי/א''ס ביתר [code 222] 18:47 (service date 2026-10-07, trip `584865032_031026`)
3. Walk 10 min, 305 m: אצטדיון טדי/א''ס ביתר 18:47 -> END 18:57

Transfers (alight to next boarding, including any walk): none

| Usable? (Y/N) | Notes | Compared against / when checked |
|---|---|---|
|  |  |  |

---

## J08 — Haifa Center HaShmona (חיפה מרכז השמונה) → Technion (הטכניון)

category `haifa-urban` · calendar rule `weekday_morning`

**Requested:** Depart at Mon 2026-10-05 08:00 (UTC+03:00)  
Request field: `departAt=2026-10-05T08:00:00+03:00`
**Calendar flags:** ordinary day
**Compare:** [Google Maps transit](https://www.google.com/maps/dir/?api=1&origin=32.8206,34.9985&destination=32.7767,35.0217&travelmode=transit) · [Moovit (unofficial deep link; may not prefill)](https://moovitapp.com/?fll=32.8206_34.9985&tll=32.7767_35.0217&from=Haifa%20Center%20HaShmona&to=Technion) · Set the time yourself to **Depart at 08:00, Mon 2026-10-05** (Google's documented URL has no time parameter).
**Corpus expectation (context, not a verdict):** outcome `route`, max_duration_min = 75, max_transfers = 2, min_duration_min = 15, modes_any_of = ['bus', 'cable_car', 'funicular']

> What to check: Haifa is vertical. Check the walking legs are not absurd gradients.

**API RESULT: 3 journey option(s) returned** (scheduled times).
Machine note: matches the corpus expectation `route`. This is not a judgement of quality.
Request id `93aab26d213e409e9a1b4631fd68757a`.

**Option 1:** departs Mon 2026-10-05 08:00, arrives Mon 2026-10-05 08:40; total 40 min, 0 transfer(s), walking 16 min / 994 m

1. Walk 11 min, 719 m: START 08:00 -> תחנת רכבת חיפה מרכז השמונה 08:11
2. **bus 17** (אגד) toward טכניון: board תחנת רכבת חיפה מרכז השמונה [code 41540] 08:11 -> alight טכניון/מעונות העמים [code 41200] 08:35 (service date 2026-10-05, trip `5355401_041026`)
3. Walk 5 min, 275 m: טכניון/מעונות העמים 08:35 -> END 08:40

Transfers (alight to next boarding, including any walk): none

**Option 2:** departs Mon 2026-10-05 08:01, arrives Mon 2026-10-05 08:40; total 39 min, 1 transfer(s), walking 14 min / 713 m

1. Walk 7 min, 438 m: START 08:01 -> המגינים/ככר ההגנה 08:08
2. **bus 3** (אגד) toward מרכזית חוף הכרמל: board המגינים/ככר ההגנה [code 42723] 08:08 -> alight פלים/קיבוץ גלויות [code 43108] 08:10 (service date 2026-10-05, trip `10378671_041026`)
3. Walk 2 min, 0 m: פלים/קיבוץ גלויות 08:10 -> פלים/קיבוץ גלויות 08:12
4. **bus 17** (אגד) toward טכניון: board פלים/קיבוץ גלויות [code 43108] 08:14 -> alight טכניון/מעונות העמים [code 41200] 08:35 (service date 2026-10-05, trip `5355401_041026`)
5. Walk 5 min, 275 m: טכניון/מעונות העמים 08:35 -> END 08:40

Transfers (alight to next boarding, including any walk): פלים/קיבוץ גלויות -> פלים/קיבוץ גלויות: 4 min

**Option 3:** departs Mon 2026-10-05 08:08, arrives Mon 2026-10-05 08:50; total 42 min, 1 transfer(s), walking 14 min / 820 m

1. Walk 7 min, 438 m: START 08:08 -> המגינים/ככר ההגנה 08:15
2. **bus 16** (אגד) toward מרכזית המפרץ: board המגינים/ככר ההגנה [code 42723] 08:15 -> alight חנקין/קומוי [code 41886] 08:38 (service date 2026-10-05, trip `7083211_021026`)
3. Walk 2 min, 107 m: חנקין/קומוי 08:38 -> קומוי/חנקין 08:40
4. **bus 76** (אגד) toward יגור_מסוף יגור: board קומוי/חנקין [code 41202] 08:43 -> alight טכניון/מעונות העמים [code 41200] 08:45 (service date 2026-10-05, trip `585688536_031026`)
5. Walk 5 min, 275 m: טכניון/מעונות העמים 08:45 -> END 08:50

Transfers (alight to next boarding, including any walk): חנקין/קומוי -> קומוי/חנקין: 5 min

| Usable? (Y/N) | Notes | Compared against / when checked |
|---|---|---|
|  |  |  |

---

## J09 — Haifa University (אוניברסיטת חיפה) → Bat Galim Central Station (חיפה בת גלים)

category `haifa-urban` · calendar rule `weekday_evening`

**Requested:** Depart at Wed 2026-10-07 18:30 (UTC+03:00)  
Request field: `departAt=2026-10-07T18:30:00+03:00`
**Calendar flags:** ordinary day
**Compare:** [Google Maps transit](https://www.google.com/maps/dir/?api=1&origin=32.7614,35.0207&destination=32.8283,34.9539&travelmode=transit) · [Moovit (unofficial deep link; may not prefill)](https://moovitapp.com/?fll=32.7614_35.0207&tll=32.8283_34.9539&from=Haifa%20University&to=Bat%20Galim%20Central%20Station) · Set the time yourself to **Depart at 18:30, Wed 2026-10-07** (Google's documented URL has no time parameter).
**Corpus expectation (context, not a verdict):** outcome `route`, max_duration_min = 85, max_transfers = 2, min_duration_min = 20, modes_any_of = ['bus', 'rail']

> What to check: Long descent across the Carmel. Compare to Moovit for line choice.

**API RESULT: NO ROUTE** — a valid search inside coverage returned no journey. The API does not state a cause (no service, walking limit and data gaps look alike).
Machine note: DIFFERS FROM the corpus expectation `route`. This is not a judgement of quality.
Request id `87ef8765bdad4be698d8e770141b3393`.

| Usable? (Y/N) | Notes | Compared against / when checked |
|---|---|---|
|  |  |  |

---

## J10 — Grand Kanyon Haifa (גראנד קניון חיפה) → Rambam Medical Center (בית חולים רמבם)

category `haifa-urban` · calendar rule `weekday_midday`

**Requested:** Depart at Tue 2026-10-06 13:00 (UTC+03:00)  
Request field: `departAt=2026-10-06T13:00:00+03:00`
**Calendar flags:** ordinary day
**Compare:** [Google Maps transit](https://www.google.com/maps/dir/?api=1&origin=32.7943,34.9891&destination=32.8347,34.9857&travelmode=transit) · [Moovit (unofficial deep link; may not prefill)](https://moovitapp.com/?fll=32.7943_34.9891&tll=32.8347_34.9857&from=Grand%20Kanyon%20Haifa&to=Rambam%20Medical%20Center) · Set the time yourself to **Depart at 13:00, Tue 2026-10-06** (Google's documented URL has no time parameter).
**Corpus expectation (context, not a verdict):** outcome `route`, max_duration_min = 70, max_transfers = 2, min_duration_min = 12, modes_any_of = ['bus', 'rail', 'funicular']

> What to check: Mall to hospital. Does the Metronit BRT get used?

**API RESULT: 3 journey option(s) returned** (scheduled times).
Machine note: matches the corpus expectation `route`. This is not a judgement of quality.
Request id `692febb28d964ffebf944d20b6db2b26`.

**Option 1:** departs Tue 2026-10-06 13:01, arrives Tue 2026-10-06 13:47; total 46 min, 1 transfer(s), walking 21 min / 1438 m

1. Walk 11 min, 665 m: START 13:01 -> מוריה/ספקטור 13:12
2. **bus 58** (סופרבוס) toward חיפה_רכבת מרכז השמונה: board מוריה/ספקטור [code 40990] 13:12 -> alight דרך סטלה מאריס [code 40666] 13:29 (service date 2026-10-06, trip `584902463_011026`)
3. Walk 2 min, 317 m: דרך סטלה מאריס 13:29 -> הברון הירש/אלנבי 13:31
4. **bus 40** (אגד) toward תחנת הרכבל: board הברון הירש/אלנבי [code 41112] 13:33 -> alight העליה השניה/עפרון [code 41159] 13:39 (service date 2026-10-06, trip `1312483_021026`)
5. Walk 8 min, 456 m: העליה השניה/עפרון 13:39 -> END 13:47

Transfers (alight to next boarding, including any walk): דרך סטלה מאריס -> הברון הירש/אלנבי: 4 min

**Option 2:** departs Tue 2026-10-06 13:06, arrives Tue 2026-10-06 13:52; total 46 min, 0 transfer(s), walking 21 min / 1274 m

1. Walk 11 min, 665 m: START 13:06 -> מוריה/ספקטור 13:17
2. **bus 37** (אגד) toward רכבת בת גלים: board מוריה/ספקטור [code 40990] 13:17 -> alight ת. רכבת בת גלים [code 47181] 13:42 (service date 2026-10-06, trip `1311194_041026`)
3. Walk 10 min, 609 m: ת. רכבת בת גלים 13:42 -> END 13:52

Transfers (alight to next boarding, including any walk): none

**Option 3:** departs Tue 2026-10-06 13:08, arrives Tue 2026-10-06 13:53; total 45 min, 0 transfer(s), walking 22 min / 1303 m

1. Walk 11 min, 665 m: START 13:08 -> מוריה/ספקטור 13:19
2. **bus 37א** (אגד) toward חיפה_רכבת בת גלים: board מוריה/ספקטור [code 40990] 13:19 -> alight חיל הים/העלייה השנייה [code 42746] 13:42 (service date 2026-10-06, trip `25569346_041026`)
3. Walk 11 min, 638 m: חיל הים/העלייה השנייה 13:42 -> END 13:53

Transfers (alight to next boarding, including any walk): none

| Usable? (Y/N) | Notes | Compared against / when checked |
|---|---|---|
|  |  |  |

---

## J11 — Tel Aviv Savidor Center (תל אביב סבידור מרכז) → Haifa Center HaShmona (חיפה מרכז השמונה)

**Required journey #3** — PRD §7 #3 Tel Aviv → Haifa · category `intercity-rail` · calendar rule `weekday_morning`

**Requested:** Depart at Mon 2026-10-05 08:00 (UTC+03:00)  
Request field: `departAt=2026-10-05T08:00:00+03:00`
**Calendar flags:** ordinary day
**Compare:** [Google Maps transit](https://www.google.com/maps/dir/?api=1&origin=32.0836,34.7981&destination=32.8206,34.9985&travelmode=transit) · [Moovit (unofficial deep link; may not prefill)](https://moovitapp.com/?fll=32.0836_34.7981&tll=32.8206_34.9985&from=Tel%20Aviv%20Savidor%20Center&to=Haifa%20Center%20HaShmona) · Set the time yourself to **Depart at 08:00, Mon 2026-10-05** (Google's documented URL has no time parameter).
**Corpus expectation (context, not a verdict):** outcome `route`, max_duration_min = 130, max_transfers = 1, min_duration_min = 45, modes_any_of = ['rail']

> What to check: The flagship rail corridor. Cross-check timings against BetterRail.

API warnings: TRANSFER_STREET_PATH_UNAVAILABLE

**API RESULT: 3 journey option(s) returned** (scheduled times).
Machine note: matches the corpus expectation `route`. This is not a judgement of quality.
Request id `e23cad7800404551918acabf2c3bc041`.

**Option 1:** departs Mon 2026-10-05 08:14, arrives Mon 2026-10-05 09:38; total 84 min, 1 transfer(s), walking 14 min / unknown distance

1. Walk 1 min, 27 m: START 08:14 -> תל אביב מרכז 08:15
2. **rail ** (רכבת ישראל) toward 24: board תל אביב מרכז [code 17038] 08:15 -> alight חיפה מרכז [code 17016] 09:23 (service date 2026-10-05, trip `1_521346`)
3. Walk 4 min (timetable transfer; street path unavailable): חיפה מרכז 09:23 -> תחנת רכבת חיפה מרכז השמונה 09:27
4. **bus 2** (סופרבוס) toward קרית אתא_יוספטל: board תחנת רכבת חיפה מרכז השמונה [code 47574] 09:28 -> alight כרמלית [code 47576] 09:29 (service date 2026-10-05, trip `15019535_011026`)
5. Walk 9 min, 564 m: כרמלית 09:29 -> END 09:38

Transfers (alight to next boarding, including any walk): חיפה מרכז -> תחנת רכבת חיפה מרכז השמונה: 5 min

**Option 2:** departs Mon 2026-10-05 08:25, arrives Mon 2026-10-05 09:52; total 87 min, 1 transfer(s), walking 14 min / 898 m

1. Walk 1 min, 27 m: START 08:25 -> תל אביב מרכז 08:26
2. **rail ** (רכבת ישראל) toward 156: board תל אביב מרכז [code 17038] 08:26 -> alight בת גלים [code 17018] 09:31 (service date 2026-10-05, trip `1_521247`)
3. Walk 2 min, 152 m: בת גלים 09:31 -> ת. רכבת בת גלים 09:33
4. **bus 36** (אגד) toward אוניברסיטה: board ת. רכבת בת גלים [code 47181] 09:34 -> alight תחנת רכבת חיפה מרכז השמונה [code 41540] 09:41 (service date 2026-10-05, trip `11572583_021026`)
5. Walk 11 min, 719 m: תחנת רכבת חיפה מרכז השמונה 09:41 -> END 09:52

Transfers (alight to next boarding, including any walk): בת גלים -> ת. רכבת בת גלים: 3 min

**Option 3:** departs Mon 2026-10-05 08:44, arrives Mon 2026-10-05 10:08; total 84 min, 1 transfer(s), walking 14 min / 898 m

1. Walk 1 min, 27 m: START 08:44 -> תל אביב מרכז 08:45
2. **rail ** (רכבת ישראל) toward 404: board תל אביב מרכז [code 17038] 08:45 -> alight בת גלים [code 17018] 09:48 (service date 2026-10-05, trip `1_521139`)
3. Walk 2 min, 152 m: בת גלים 09:48 -> ת. רכבת בת גלים 09:50
4. **bus 18** (אגד) toward נווה שאנן: board ת. רכבת בת גלים [code 47181] 09:50 -> alight תחנת רכבת חיפה מרכז השמונה [code 41540] 09:57 (service date 2026-10-05, trip `25308365_041026`)
5. Walk 11 min, 719 m: תחנת רכבת חיפה מרכז השמונה 09:57 -> END 10:08

Transfers (alight to next boarding, including any walk): בת גלים -> ת. רכבת בת גלים: 2 min

| Usable? (Y/N) | Notes | Compared against / when checked |
|---|---|---|
|  |  |  |

---

## J12 — Tel Aviv Savidor Center (תל אביב סבידור מרכז) → Yitzhak Navon Station (תחנת יצחק נבון)

**Required journey #4** — PRD §7 #4 Tel Aviv → Jerusalem · category `intercity-rail` · calendar rule `weekday_morning`

**Requested:** Depart at Mon 2026-10-05 08:00 (UTC+03:00)  
Request field: `departAt=2026-10-05T08:00:00+03:00`
**Calendar flags:** ordinary day
**Compare:** [Google Maps transit](https://www.google.com/maps/dir/?api=1&origin=32.0836,34.7981&destination=31.7888,35.2027&travelmode=transit) · [Moovit (unofficial deep link; may not prefill)](https://moovitapp.com/?fll=32.0836_34.7981&tll=31.7888_35.2027&from=Tel%20Aviv%20Savidor%20Center&to=Yitzhak%20Navon%20Station) · Set the time yourself to **Depart at 08:00, Mon 2026-10-05** (Google's documented URL has no time parameter).
**Corpus expectation (context, not a verdict):** outcome `route`, max_duration_min = 110, max_transfers = 1, min_duration_min = 30, modes_any_of = ['rail']

> What to check: Fast line. If it routes by bus, the rail calendar is probably misread.

**API RESULT: 3 journey option(s) returned** (scheduled times).
Machine note: matches the corpus expectation `route`. This is not a judgement of quality.
Request id `d1b622cf64c34a35961f7e2301941bd9`.

**Option 1:** departs Mon 2026-10-05 08:04, arrives Mon 2026-10-05 08:55; total 51 min, 0 transfer(s), walking 4 min / 207 m

1. Walk 1 min, 27 m: START 08:04 -> תל אביב מרכז 08:05
2. **rail ** (רכבת ישראל) toward 723: board תל אביב מרכז [code 17038] 08:05 -> alight ירושלים/יצחק נבון [code 17118] 08:52 (service date 2026-10-05, trip `1_520957`)
3. Walk 3 min, 180 m: ירושלים/יצחק נבון 08:52 -> END 08:55

Transfers (alight to next boarding, including any walk): none

**Option 2:** departs Mon 2026-10-05 08:14, arrives Mon 2026-10-05 09:09; total 55 min, 0 transfer(s), walking 11 min / 710 m

1. Walk 6 min, 403 m: START 08:14 -> ת.רכבת תל אביב - סבידור/רציפים B 08:20
2. **bus 480** (אגד) toward ירושלים_תחנה מרכזית: board ת.רכבת תל אביב - סבידור/רציפים B [code 20740] 08:20 -> alight ת. מרכזית ירושלים/הורדה [code 6109] 09:04 (service date 2026-10-05, trip `2549890_041026`)
3. Walk 5 min, 307 m: ת. מרכזית ירושלים/הורדה 09:04 -> END 09:09

Transfers (alight to next boarding, including any walk): none

**Option 3:** departs Mon 2026-10-05 08:34, arrives Mon 2026-10-05 09:25; total 51 min, 0 transfer(s), walking 4 min / 207 m

1. Walk 1 min, 27 m: START 08:34 -> תל אביב מרכז 08:35
2. **rail ** (רכבת ישראל) toward 725: board תל אביב מרכז [code 17038] 08:35 -> alight ירושלים/יצחק נבון [code 17118] 09:22 (service date 2026-10-05, trip `1_521008`)
3. Walk 3 min, 180 m: ירושלים/יצחק נבון 09:22 -> END 09:25

Transfers (alight to next boarding, including any walk): none

| Usable? (Y/N) | Notes | Compared against / when checked |
|---|---|---|
|  |  |  |

---

## J13 — Tel Aviv HaShalom (תל אביב השלום) → Beersheba Central (באר שבע מרכז)

category `intercity-rail` · calendar rule `weekday_midday`

**Requested:** Depart at Tue 2026-10-06 13:00 (UTC+03:00)  
Request field: `departAt=2026-10-06T13:00:00+03:00`
**Calendar flags:** ordinary day
**Compare:** [Google Maps transit](https://www.google.com/maps/dir/?api=1&origin=32.0731,34.7925&destination=31.243,34.7983&travelmode=transit) · [Moovit (unofficial deep link; may not prefill)](https://moovitapp.com/?fll=32.0731_34.7925&tll=31.243_34.7983&from=Tel%20Aviv%20HaShalom&to=Beersheba%20Central) · Set the time yourself to **Depart at 13:00, Tue 2026-10-06** (Google's documented URL has no time parameter).
**Corpus expectation (context, not a verdict):** outcome `route`, max_duration_min = 180, max_transfers = 1, min_duration_min = 60, modes_any_of = ['rail']

> What to check: Long-distance south. Is the itinerary the direct train or a silly chain?

**API RESULT: 3 journey option(s) returned** (scheduled times).
Machine note: matches the corpus expectation `route`. This is not a judgement of quality.
Request id `567eabc17c6d44f0ae2e034a5e3c697c`.

**Option 1:** departs Tue 2026-10-06 13:11, arrives Tue 2026-10-06 14:51; total 100 min, 0 transfer(s), walking 5 min / 314 m

1. Walk 4 min, 270 m: START 13:11 -> השלום 13:15
2. **rail ** (רכבת ישראל) toward 33: board השלום [code 17046] 13:15 -> alight באר שבע מרכז [code 17084] 14:50 (service date 2026-10-06, trip `1_521236`)
3. Walk 1 min, 44 m: באר שבע מרכז 14:50 -> END 14:51

Transfers (alight to next boarding, including any walk): none

**Option 2:** departs Tue 2026-10-06 13:37, arrives Tue 2026-10-06 15:20; total 103 min, 0 transfer(s), walking 5 min / 314 m

1. Walk 4 min, 270 m: START 13:37 -> השלום 13:41
2. **rail ** (רכבת ישראל) toward 643: board השלום [code 17046] 13:41 -> alight באר שבע מרכז [code 17084] 15:19 (service date 2026-10-06, trip `1_521011`)
3. Walk 1 min, 44 m: באר שבע מרכז 15:19 -> END 15:20

Transfers (alight to next boarding, including any walk): none

**Option 3:** departs Tue 2026-10-06 13:46, arrives Tue 2026-10-06 15:35; total 109 min, 2 transfer(s), walking 20 min / 1430 m

1. Walk 4 min, 270 m: START 13:46 -> השלום 13:50
2. **rail ** (רכבת ישראל) toward 517: board השלום [code 17046] 13:50 -> alight תל אביב ההגנה [code 17104] 13:55 (service date 2026-10-06, trip `1_521060`)
3. Walk 4 min, 407 m: תל אביב ההגנה 13:56 -> מסוף ההגנה/איסוף 14:00
4. **bus 114** (דן) toward מסוף רכבת ההגנה: board מסוף ההגנה/איסוף [code 20860] 14:00 -> alight גשר קיבוץ גלויות [code 25287] 14:02 (service date 2026-10-06, trip `585060902_051026`)
5. Walk 2 min, 96 m: גשר קיבוץ גלויות 14:02 -> דרך קיבוץ גלויות/כביש 1 14:04
6. **bus 370** (מטרופולין) toward באר שבע_תחנה מרכזית: board דרך קיבוץ גלויות/כביש 1 [code 25069] 14:04 -> alight ת.מרכזית באר שבע/הורדה [code 15657] 15:25 (service date 2026-10-06, trip `2821988_011026`)
7. Walk 10 min, 657 m: ת.מרכזית באר שבע/הורדה 15:25 -> END 15:35

Transfers (alight to next boarding, including any walk): תל אביב ההגנה -> מסוף ההגנה/איסוף: 5 min; גשר קיבוץ גלויות -> דרך קיבוץ גלויות/כביש 1: 2 min

| Usable? (Y/N) | Notes | Compared against / when checked |
|---|---|---|
|  |  |  |

---

## J14 — Nahariya (נהריה) → Ashdod Ad Halom (אשדוד עד הלום)

category `intercity-rail` · calendar rule `weekday_morning`

**Requested:** Depart at Mon 2026-10-05 08:00 (UTC+03:00)  
Request field: `departAt=2026-10-05T08:00:00+03:00`
**Calendar flags:** ordinary day
**Compare:** [Google Maps transit](https://www.google.com/maps/dir/?api=1&origin=33.0079,35.0938&destination=31.794,34.641&travelmode=transit) · [Moovit (unofficial deep link; may not prefill)](https://moovitapp.com/?fll=33.0079_35.0938&tll=31.794_34.641&from=Nahariya&to=Ashdod%20Ad%20Halom) · Set the time yourself to **Depart at 08:00, Mon 2026-10-05** (Google's documented URL has no time parameter).
**Corpus expectation (context, not a verdict):** outcome `route`, max_duration_min = 260, max_transfers = 2, min_duration_min = 120, modes_any_of = ['rail']

> What to check: End-to-end coastal line. Tests the longest single-mode journey in the country.

API warnings: TRANSFER_STREET_PATH_UNAVAILABLE

**API RESULT: 3 journey option(s) returned** (scheduled times).
Machine note: matches the corpus expectation `route`. This is not a judgement of quality.
Request id `adcac816b69242bba8e17305e155209d`.

**Option 1:** departs Mon 2026-10-05 08:02, arrives Mon 2026-10-05 10:53; total 171 min, 1 transfer(s), walking 20 min / 1229 m

1. Walk 13 min, 760 m: START 08:02 -> נהריה 08:15
2. **rail ** (רכבת ישראל) toward 157: board נהריה [code 17014] 08:15 -> alight השלום [code 17046] 10:04 (service date 2026-10-05, trip `1_521246`)
3. Walk 4 min, 315 m: השלום 10:04 -> קניון עזריאלי/כביש 20 10:08
4. **bus 280** (אלקטרה אפיקים) toward אשדוד_תחנה מרכזית: board קניון עזריאלי/כביש 20 [code 21378] 10:09 -> alight ירושלים [code 12019] 10:50 (service date 2026-10-05, trip `28979431_041026`)
5. Walk 3 min, 154 m: ירושלים 10:50 -> END 10:53

Transfers (alight to next boarding, including any walk): השלום -> קניון עזריאלי/כביש 20: 5 min

**Option 2:** departs Mon 2026-10-05 08:03, arrives Mon 2026-10-05 10:53; total 170 min, 2 transfer(s), walking 18 min / unknown distance

1. Walk 7 min, 410 m: START 08:03 -> שדרות הגעתון/עזריאל ריציק 08:10
2. **bus 16** (נתיב אקספרס) toward רגבה_מרכז מסחרי: board שדרות הגעתון/עזריאל ריציק [code 56555] 08:10 -> alight תחנה מרכזית נהריה/שדרות הגעתון [code 56437] 08:10 (service date 2026-10-05, trip `586233801_011026`)
3. Walk 4 min (timetable transfer; street path unavailable): תחנה מרכזית נהריה/שדרות הגעתון 08:11 -> נהריה 08:15
4. **rail ** (רכבת ישראל) toward 157: board נהריה [code 17014] 08:15 -> alight השלום [code 17046] 10:04 (service date 2026-10-05, trip `1_521246`)
5. Walk 4 min, 315 m: השלום 10:04 -> קניון עזריאלי/כביש 20 10:08
6. **bus 280** (אלקטרה אפיקים) toward אשדוד_תחנה מרכזית: board קניון עזריאלי/כביש 20 [code 21378] 10:09 -> alight ירושלים [code 12019] 10:50 (service date 2026-10-05, trip `28979431_041026`)
7. Walk 3 min, 154 m: ירושלים 10:50 -> END 10:53

Transfers (alight to next boarding, including any walk): תחנה מרכזית נהריה/שדרות הגעתון -> נהריה: 5 min; השלום -> קניון עזריאלי/כביש 20: 5 min

**Option 3:** departs Mon 2026-10-05 08:15, arrives Mon 2026-10-05 11:23; total 188 min, 1 transfer(s), walking 24 min / 1324 m

1. Walk 13 min, 760 m: START 08:15 -> נהריה 08:28
2. **rail ** (רכבת ישראל) toward 27: board נהריה [code 17014] 08:28 -> alight תל אביב ההגנה [code 17104] 10:20 (service date 2026-10-05, trip `1_521333`)
3. Walk 8 min, 410 m: תל אביב ההגנה 10:20 -> ת. רכבת ההגנה/החרש 10:28
4. **bus 281** (אלקטרה אפיקים) toward אשדוד_רובע ט"ו: board ת. רכבת ההגנה/החרש [code 20353] 10:40 -> alight ירושלים [code 12019] 11:20 (service date 2026-10-05, trip `42262647_041026`)
5. Walk 3 min, 154 m: ירושלים 11:20 -> END 11:23

Transfers (alight to next boarding, including any walk): תל אביב ההגנה -> ת. רכבת ההגנה/החרש: 20 min

| Usable? (Y/N) | Notes | Compared against / when checked |
|---|---|---|
|  |  |  |

---

## J15 — Weizmann Institute, Rehovot (מכון ויצמן למדע) → Haifa Center HaShmona (חיפה מרכז השמונה)

**Required journey #5** — PRD §7 #5 bus → train · category `bus-to-rail` · calendar rule `weekday_morning`

**Requested:** Depart at Mon 2026-10-05 08:00 (UTC+03:00)  
Request field: `departAt=2026-10-05T08:00:00+03:00`
**Calendar flags:** ordinary day
**Compare:** [Google Maps transit](https://www.google.com/maps/dir/?api=1&origin=31.907,34.8102&destination=32.8206,34.9985&travelmode=transit) · [Moovit (unofficial deep link; may not prefill)](https://moovitapp.com/?fll=31.907_34.8102&tll=32.8206_34.9985&from=Weizmann%20Institute%2C%20Rehovot&to=Haifa%20Center%20HaShmona) · Set the time yourself to **Depart at 08:00, Mon 2026-10-05** (Google's documented URL has no time parameter).
**Corpus expectation (context, not a verdict):** outcome `route`, max_duration_min = 220, max_transfers = 3, min_duration_min = 75, modes_all_of = ['bus', 'rail']

> What to check: Must contain a bus leg then a rail leg. Verify the interchange is real.

API warnings: TRANSFER_STREET_PATH_UNAVAILABLE

**API RESULT: 3 journey option(s) returned** (scheduled times).
Machine note: matches the corpus expectation `route`. This is not a judgement of quality.
Request id `9f2c0237dfe54460995c791c0c964b34`.

**Option 1:** departs Mon 2026-10-05 08:00, arrives Mon 2026-10-05 10:16; total 136 min, 2 transfer(s), walking 30 min / unknown distance

1. Walk 11 min, 591 m: START 08:00 -> מכון ויצמן 08:11
2. **bus 277** (אגד) toward תל אביב יפו_מסוף רדינג: board מכון ויצמן [code 34230] 08:11 -> alight ת. רכבת ההגנה/החרש [code 25636] 08:39 (service date 2026-10-05, trip `584860123_021026`)
3. Walk 6 min, 242 m: ת. רכבת ההגנה/החרש 08:40 -> תל אביב ההגנה 08:46
4. **rail ** (רכבת ישראל) toward 106: board תל אביב ההגנה [code 17104] 08:46 -> alight חיפה מרכז [code 17016] 10:00 (service date 2026-10-05, trip `1_521012`)
5. Walk 4 min (timetable transfer; street path unavailable): חיפה מרכז 10:00 -> תחנת רכבת חיפה מרכז השמונה 10:04
6. **bus 1** (סופרבוס) toward קרית מוצקין_מרכזית הקריות: board תחנת רכבת חיפה מרכז השמונה [code 47574] 10:06 -> alight כרמלית [code 47576] 10:07 (service date 2026-10-05, trip `12078242_011026`)
7. Walk 9 min, 564 m: כרמלית 10:07 -> END 10:16

Transfers (alight to next boarding, including any walk): ת. רכבת ההגנה/החרש -> תל אביב ההגנה: 7 min; חיפה מרכז -> תחנת רכבת חיפה מרכז השמונה: 6 min

**Option 2:** departs Mon 2026-10-05 08:21, arrives Mon 2026-10-05 10:40; total 139 min, 2 transfer(s), walking 28 min / unknown distance

1. Walk 13 min, 876 m: START 08:21 -> רחובות 08:34
2. **rail ** (רכבת ישראל) toward 956: board רחובות [code 17064] 08:34 -> alight לוד [code 17058] 08:43 (service date 2026-10-05, trip `1_520832`)
3. Walk 2 min, 0 m: לוד 08:49 -> לוד 08:51
4. **rail ** (רכבת ישראל) toward 26: board לוד [code 17058] 08:51 -> alight חיפה מרכז [code 17016] 10:23 (service date 2026-10-05, trip `1_520681`)
5. Walk 4 min (timetable transfer; street path unavailable): חיפה מרכז 10:23 -> תחנת רכבת חיפה מרכז השמונה 10:27
6. **bus 1** (סופרבוס) toward קרית מוצקין_מרכזית הקריות: board תחנת רכבת חיפה מרכז השמונה [code 47574] 10:30 -> alight כרמלית [code 47576] 10:31 (service date 2026-10-05, trip `40076506_011026`)
7. Walk 9 min, 564 m: כרמלית 10:31 -> END 10:40

Transfers (alight to next boarding, including any walk): לוד -> לוד: 8 min; חיפה מרכז -> תחנת רכבת חיפה מרכז השמונה: 7 min

**Option 3:** departs Mon 2026-10-05 08:25, arrives Mon 2026-10-05 10:50; total 145 min, 2 transfer(s), walking 26 min / unknown distance

1. Walk 11 min, 591 m: START 08:25 -> מכון ויצמן 08:36
2. **bus 274** (אגד) toward תל אביב יפו_אוניברסיטת ת"א: board מכון ויצמן [code 34230] 08:36 -> alight ת. רכבת השלום [code 21022] 09:18 (service date 2026-10-05, trip `34234277_031026`)
3. Walk 2 min, 329 m: ת. רכבת השלום 09:19 -> השלום 09:21
4. **rail ** (רכבת ישראל) toward 158: board השלום [code 17046] 09:21 -> alight חיפה מרכז [code 17016] 10:35 (service date 2026-10-05, trip `1_521245`)
5. Walk 4 min (timetable transfer; street path unavailable): חיפה מרכז 10:35 -> תחנת רכבת חיפה מרכז השמונה 10:39
6. **bus 2** (סופרבוס) toward קרית אתא_יוספטל: board תחנת רכבת חיפה מרכז השמונה [code 47574] 10:40 -> alight כרמלית [code 47576] 10:41 (service date 2026-10-05, trip `15019544_011026`)
7. Walk 9 min, 564 m: כרמלית 10:41 -> END 10:50

Transfers (alight to next boarding, including any walk): ת. רכבת השלום -> השלום: 3 min; חיפה מרכז -> תחנת רכבת חיפה מרכז השמונה: 5 min

| Usable? (Y/N) | Notes | Compared against / when checked |
|---|---|---|
|  |  |  |

---

## J16 — Tel Aviv Savidor Center (תל אביב סבידור מרכז) → Technion (הטכניון)

**Required journey #6** — PRD §7 #6 train → bus · category `rail-to-bus` · calendar rule `weekday_morning`

**Requested:** Depart at Mon 2026-10-05 08:00 (UTC+03:00)  
Request field: `departAt=2026-10-05T08:00:00+03:00`
**Calendar flags:** ordinary day
**Compare:** [Google Maps transit](https://www.google.com/maps/dir/?api=1&origin=32.0836,34.7981&destination=32.7767,35.0217&travelmode=transit) · [Moovit (unofficial deep link; may not prefill)](https://moovitapp.com/?fll=32.0836_34.7981&tll=32.7767_35.0217&from=Tel%20Aviv%20Savidor%20Center&to=Technion) · Set the time yourself to **Depart at 08:00, Mon 2026-10-05** (Google's documented URL has no time parameter).
**Corpus expectation (context, not a verdict):** outcome `route`, max_duration_min = 200, max_transfers = 3, min_duration_min = 70, modes_all_of = ['rail', 'bus']

> What to check: The PRD §39 demo journey in reverse shape. Rail then bus up the Carmel.

API warnings: TRANSFER_STREET_PATH_UNAVAILABLE

**API RESULT: 3 journey option(s) returned** (scheduled times).
Machine note: matches the corpus expectation `route`. This is not a judgement of quality.
Request id `3df6b43772e94c189d747cc99e61ce30`.

**Option 1:** departs Mon 2026-10-05 08:25, arrives Mon 2026-10-05 09:52; total 87 min, 1 transfer(s), walking 8 min / 491 m

1. Walk 1 min, 27 m: START 08:25 -> תל אביב מרכז 08:26
2. **rail ** (רכבת ישראל) toward 156: board תל אביב מרכז [code 17038] 08:26 -> alight חוף הכרמל [code 17020] 09:24 (service date 2026-10-05, trip `1_521247`)
3. Walk 2 min, 189 m: חוף הכרמל 09:24 -> ת. רכבת חוף הכרמל 09:26
4. **bus 1** (אגד) toward טכניון: board ת. רכבת חוף הכרמל [code 46216] 09:33 -> alight טכניון/מעונות העמים [code 41200] 09:47 (service date 2026-10-05, trip `585633629_051026`)
5. Walk 5 min, 275 m: טכניון/מעונות העמים 09:47 -> END 09:52

Transfers (alight to next boarding, including any walk): חוף הכרמל -> ת. רכבת חוף הכרמל: 9 min

**Option 2:** departs Mon 2026-10-05 08:44, arrives Mon 2026-10-05 10:25; total 101 min, 1 transfer(s), walking 10 min / unknown distance

1. Walk 1 min, 27 m: START 08:44 -> תל אביב מרכז 08:45
2. **rail ** (רכבת ישראל) toward 404: board תל אביב מרכז [code 17038] 08:45 -> alight חיפה מרכז [code 17016] 09:52 (service date 2026-10-05, trip `1_521139`)
3. Walk 4 min (timetable transfer; street path unavailable): חיפה מרכז 09:52 -> תחנת רכבת חיפה מרכז השמונה 09:56
4. **bus 17** (אגד) toward טכניון: board תחנת רכבת חיפה מרכז השמונה [code 41540] 09:56 -> alight טכניון/מעונות העמים [code 41200] 10:20 (service date 2026-10-05, trip `12414978_041026`)
5. Walk 5 min, 275 m: טכניון/מעונות העמים 10:20 -> END 10:25

Transfers (alight to next boarding, including any walk): חיפה מרכז -> תחנת רכבת חיפה מרכז השמונה: 4 min

**Option 3:** departs Mon 2026-10-05 08:45, arrives Mon 2026-10-05 10:37; total 112 min, 3 transfer(s), walking 17 min / 1033 m

1. Walk 6 min, 431 m: START 08:45 -> ת. רכבת תל אביב - סבידור/דרך נמיר 08:51
2. **bus 825** (אגד) toward עפולה_תחנה מרכזית: board ת. רכבת תל אביב - סבידור/דרך נמיר [code 24068] 08:51 -> alight צומת אולגה [code 41694] 09:28 (service date 2026-10-05, trip `25275467_021026`)
3. Walk 2 min, 0 m: צומת אולגה 09:29 -> צומת אולגה 09:31
4. **bus 947** (אגד) toward חיפה_מרכזית חוף הכרמל: board צומת אולגה [code 41694] 09:31 -> alight ת. מרכזית חוף הכרמל/הורדה [code 42657] 10:05 (service date 2026-10-05, trip `584671969_041026`)
5. Walk 2 min, 99 m: ת. מרכזית חוף הכרמל/הורדה 10:09 -> ת. מרכזית חוף הכרמל/רציפים עירוני 10:11
6. **bus 4** (סופרבוס) toward קרית מוצקין_מרכזית הקריות: board ת. מרכזית חוף הכרמל/רציפים עירוני [code 42659] 10:11 -> alight גרנד קניון/שמחה גולן [code 47392] 10:19 (service date 2026-10-05, trip `585235871_011026`)
7. Walk 2 min, 228 m: גרנד קניון/שמחה גולן 10:19 -> גרנד קניון/שמחה גולן 10:21
8. **bus 144** (אגד) toward חיפה_אוניברסיטה: board גרנד קניון/שמחה גולן [code 42571] 10:25 -> alight טכניון/מעונות העמים [code 41200] 10:32 (service date 2026-10-05, trip `19150807_021026`)
9. Walk 5 min, 275 m: טכניון/מעונות העמים 10:32 -> END 10:37

Transfers (alight to next boarding, including any walk): צומת אולגה -> צומת אולגה: 3 min; ת. מרכזית חוף הכרמל/הורדה -> ת. מרכזית חוף הכרמל/רציפים עירוני: 6 min; גרנד קניון/שמחה גולן -> גרנד קניון/שמחה גולן: 6 min

| Usable? (Y/N) | Notes | Compared against / when checked |
|---|---|---|
|  |  |  |

---

## J17 — Modi'in Center (מודיעין מרכז) → Ben Gurion Airport T3 (נתב"ג טרמינל 3)

category `bus-to-rail` · calendar rule `weekday_morning`

**Requested:** Depart at Mon 2026-10-05 08:00 (UTC+03:00)  
Request field: `departAt=2026-10-05T08:00:00+03:00`
**Calendar flags:** ordinary day
**Compare:** [Google Maps transit](https://www.google.com/maps/dir/?api=1&origin=31.9017,35.0074&destination=32.0004,34.8705&travelmode=transit) · [Moovit (unofficial deep link; may not prefill)](https://moovitapp.com/?fll=31.9017_35.0074&tll=32.0004_34.8705&from=Modi%27in%20Center&to=Ben%20Gurion%20Airport%20T3) · Set the time yourself to **Depart at 08:00, Mon 2026-10-05** (Google's documented URL has no time parameter).
**Corpus expectation (context, not a verdict):** outcome `route`, max_duration_min = 90, max_transfers = 2, min_duration_min = 15, modes_any_of = ['rail', 'bus']

> What to check: Airport access. A wrong answer here is very visible to a real user.

API warnings: TRANSFER_STREET_PATH_UNAVAILABLE

**API RESULT: 3 journey option(s) returned** (scheduled times).
Machine note: matches the corpus expectation `route`. This is not a judgement of quality.
Request id `95c7e81b1fe3402eb23222e90a29dc01`.

**Option 1:** departs Mon 2026-10-05 08:06, arrives Mon 2026-10-05 08:36; total 30 min, 1 transfer(s), walking 10 min / unknown distance

1. Walk 7 min, 402 m: START 08:06 -> עמק איילון/תלתן 08:13
2. **bus 58** (קווים) toward בייק פארק: board עמק איילון/תלתן [code 34155] 08:13 -> alight ת. רכבת מודיעין מרכז [code 33093] 08:14 (service date 2026-10-05, trip `28361843_051026`)
3. Walk 2 min (timetable transfer; street path unavailable): ת. רכבת מודיעין מרכז 08:14 -> מודיעין מרכז 08:16
4. **rail ** (רכבת ישראל) toward 106: board מודיעין מרכז [code 17002] 08:18 -> alight נתב''ג [code 17090] 08:35 (service date 2026-10-05, trip `1_521012`)
5. Walk 1 min, 4 m: נתב''ג 08:35 -> END 08:36

Transfers (alight to next boarding, including any walk): ת. רכבת מודיעין מרכז -> מודיעין מרכז: 4 min

**Option 2:** departs Mon 2026-10-05 08:37, arrives Mon 2026-10-05 09:06; total 29 min, 1 transfer(s), walking 7 min / unknown distance

1. Walk 4 min, 189 m: START 08:37 -> קניון עזריאלי מודיעין 08:41
2. **bus 54** (קווים) toward מ.מסחרי לב רעות: board קניון עזריאלי מודיעין [code 35177] 08:41 -> alight ת. רכבת מודיעין מרכז [code 33093] 08:41 (service date 2026-10-05, trip `36207168_021026`)
3. Walk 2 min (timetable transfer; street path unavailable): ת. רכבת מודיעין מרכז 08:41 -> מודיעין מרכז 08:43
4. **rail ** (רכבת ישראל) toward 158: board מודיעין מרכז [code 17002] 08:48 -> alight נתב''ג [code 17090] 09:05 (service date 2026-10-05, trip `1_521245`)
5. Walk 1 min, 4 m: נתב''ג 09:05 -> END 09:06

Transfers (alight to next boarding, including any walk): ת. רכבת מודיעין מרכז -> מודיעין מרכז: 7 min

**Option 3:** departs Mon 2026-10-05 09:07, arrives Mon 2026-10-05 09:36; total 29 min, 1 transfer(s), walking 7 min / unknown distance

1. Walk 4 min, 189 m: START 09:07 -> קניון עזריאלי מודיעין 09:11
2. **bus 54** (קווים) toward רעות: board קניון עזריאלי מודיעין [code 35177] 09:11 -> alight ת. רכבת מודיעין מרכז [code 33093] 09:11 (service date 2026-10-05, trip `36206990_021026`)
3. Walk 2 min (timetable transfer; street path unavailable): ת. רכבת מודיעין מרכז 09:11 -> מודיעין מרכז 09:13
4. **rail ** (רכבת ישראל) toward 108: board מודיעין מרכז [code 17002] 09:18 -> alight נתב''ג [code 17090] 09:35 (service date 2026-10-05, trip `1_521080`)
5. Walk 1 min, 4 m: נתב''ג 09:35 -> END 09:36

Transfers (alight to next boarding, including any walk): ת. רכבת מודיעין מרכז -> מודיעין מרכז: 7 min

| Usable? (Y/N) | Notes | Compared against / when checked |
|---|---|---|
|  |  |  |

---

## J18 — Beersheba North University (באר שבע צפון אוניברסיטה) → Bar-Ilan University (אוניברסיטת בר אילן)

category `rail-to-bus` · calendar rule `weekday_morning`

**Requested:** Depart at Mon 2026-10-05 08:00 (UTC+03:00)  
Request field: `departAt=2026-10-05T08:00:00+03:00`
**Calendar flags:** ordinary day
**Compare:** [Google Maps transit](https://www.google.com/maps/dir/?api=1&origin=31.262,34.8016&destination=32.07,34.8433&travelmode=transit) · [Moovit (unofficial deep link; may not prefill)](https://moovitapp.com/?fll=31.262_34.8016&tll=32.07_34.8433&from=Beersheba%20North%20University&to=Bar-Ilan%20University) · Set the time yourself to **Depart at 08:00, Mon 2026-10-05** (Google's documented URL has no time parameter).
**Corpus expectation (context, not a verdict):** outcome `route`, max_duration_min = 230, max_transfers = 3, min_duration_min = 75, modes_all_of = ['rail', 'bus']

> What to check: Campus to campus, two operators, at least one interchange.

**API RESULT: 3 journey option(s) returned** (scheduled times).
Machine note: matches the corpus expectation `route`. This is not a judgement of quality.
Request id `03d65264a60b44cc970579b0714f736a`.

**Option 1:** departs Mon 2026-10-05 08:00, arrives Mon 2026-10-05 10:04; total 124 min, 3 transfer(s), walking 18 min / 1233 m

1. Walk 4 min, 215 m: START 08:00 -> מרפאות חוץ סורוקה/אוניברסיטת בן גוריון 08:04
2. **bus 5** (דן באר שבע) toward מסוף חצרים: board מרפאות חוץ סורוקה/אוניברסיטת בן גוריון [code 13949] 08:04 -> alight מרכז רפואי סורוקה/אוניברסיטת בן גוריון [code 15332] 08:05 (service date 2026-10-05, trip `585112451_041026`)
3. Walk 2 min, 290 m: מרכז רפואי סורוקה/אוניברסיטת בן גוריון 08:05 -> מרכז רפואי סורוקה/אוניברסיטת בן גוריון 08:07
4. **bus 370** (מטרופולין) toward תל אביב יפו_תחנה מרכזית: board מרכז רפואי סורוקה/אוניברסיטת בן גוריון [code 15333] 08:07 -> alight מחלף לה גווארדייה [code 21274] 09:16 (service date 2026-10-05, trip `2221042_011026`)
5. Walk 2 min, 126 m: מחלף לה גווארדייה 09:24 -> מחלף לה גווארדייה 09:26
6. **bus 31** (דן) toward בני ברק_בית עלמין: board מחלף לה גווארדייה [code 22934] 09:26 -> alight הירדן/ אלוף שדה [code 21319] 09:44 (service date 2026-10-05, trip `4949043_051026`)
7. Walk 2 min, 150 m: הירדן/ אלוף שדה 09:44 -> הירדן/אלוף שדה 09:46
8. **bus 32** (דן) toward גבעת שמואל_הרב שלמה גורן: board הירדן/אלוף שדה [code 21569] 09:47 -> alight מרכז וואהל/מקס ואנה ווב [code 32907] 09:56 (service date 2026-10-05, trip `36034267_051026`)
9. Walk 8 min, 452 m: מרכז וואהל/מקס ואנה ווב 09:56 -> END 10:04

Transfers (alight to next boarding, including any walk): מרכז רפואי סורוקה/אוניברסיטת בן גוריון -> מרכז רפואי סורוקה/אוניברסיטת בן גוריון: 2 min; מחלף לה גווארדייה -> מחלף לה גווארדייה: 10 min; הירדן/ אלוף שדה -> הירדן/אלוף שדה: 3 min

**Option 2:** departs Mon 2026-10-05 08:00, arrives Mon 2026-10-05 09:56; total 116 min, 4 transfer(s), walking 20 min / 1083 m

1. Walk 4 min, 215 m: START 08:00 -> מרפאות חוץ סורוקה/אוניברסיטת בן גוריון 08:04
2. **bus 5** (דן באר שבע) toward מסוף חצרים: board מרפאות חוץ סורוקה/אוניברסיטת בן גוריון [code 13949] 08:04 -> alight מרכז רפואי סורוקה/אוניברסיטת בן גוריון [code 15332] 08:05 (service date 2026-10-05, trip `585112451_041026`)
3. Walk 2 min, 290 m: מרכז רפואי סורוקה/אוניברסיטת בן גוריון 08:05 -> מרכז רפואי סורוקה/אוניברסיטת בן גוריון 08:07
4. **bus 370** (מטרופולין) toward תל אביב יפו_תחנה מרכזית: board מרכז רפואי סורוקה/אוניברסיטת בן גוריון [code 15333] 08:07 -> alight מחלף לה גווארדייה [code 21274] 09:16 (service date 2026-10-05, trip `2221042_011026`)
5. Walk 2 min, 126 m: מחלף לה גווארדייה 09:17 -> מחלף לה גווארדייה 09:19
6. **bus 2** (דן) toward הארגזים: board מחלף לה גווארדייה [code 22934] 09:19 -> alight שכונת הארגזים/לח''י [code 25669] 09:25 (service date 2026-10-05, trip `44236314_051026`)
7. Walk 2 min, 0 m: שכונת הארגזים/לח''י 09:27 -> שכונת הארגזים/לח''י 09:29
8. **bus 41** (דן) toward פתח תקווה_מסוף משה ארנס: board שכונת הארגזים/לח''י [code 25669] 09:29 -> alight עמק האלה/דרך שיבא [code 31010] 09:39 (service date 2026-10-05, trip `37982808_051026`)
9. Walk 2 min, 0 m: עמק האלה/דרך שיבא 09:39 -> עמק האלה/דרך שיבא 09:41
10. **bus 48** (מטרופולין) toward פתח תקווה_מ.רפואי שניידר: board עמק האלה/דרך שיבא [code 31010] 09:41 -> alight מרכז וואהל/מקס ואנה ווב [code 32907] 09:48 (service date 2026-10-05, trip `586222499_031026`)
11. Walk 8 min, 452 m: מרכז וואהל/מקס ואנה ווב 09:48 -> END 09:56

Transfers (alight to next boarding, including any walk): מרכז רפואי סורוקה/אוניברסיטת בן גוריון -> מרכז רפואי סורוקה/אוניברסיטת בן גוריון: 2 min; מחלף לה גווארדייה -> מחלף לה גווארדייה: 3 min; שכונת הארגזים/לח''י -> שכונת הארגזים/לח''י: 4 min; עמק האלה/דרך שיבא -> עמק האלה/דרך שיבא: 2 min

**Option 3:** departs Mon 2026-10-05 08:17, arrives Mon 2026-10-05 10:11; total 114 min, 1 transfer(s), walking 20 min / 1060 m

1. Walk 10 min, 608 m: START 08:17 -> מרכז רפואי סורוקה/אוניברסיטת בן גוריון 08:27
2. **bus 669** (מטרופולין) toward רעננה_מסוף אוטובוסים: board מרכז רפואי סורוקה/אוניברסיטת בן גוריון [code 15333] 08:27 -> alight מחלף מסובים [code 33432] 09:47 (service date 2026-10-05, trip `41490656_051026`)
3. Walk 2 min, 0 m: מחלף מסובים 09:47 -> מחלף מסובים 09:49
4. **bus 145** (סופרבוס) toward פתח תקווה_רכבת קרית אריה: board מחלף מסובים [code 33432] 09:57 -> alight מרכז וואהל/מקס ואנה ווב [code 32907] 10:03 (service date 2026-10-05, trip `585990270_041026`)
5. Walk 8 min, 452 m: מרכז וואהל/מקס ואנה ווב 10:03 -> END 10:11

Transfers (alight to next boarding, including any walk): מחלף מסובים -> מחלף מסובים: 10 min

| Usable? (Y/N) | Notes | Compared against / when checked |
|---|---|---|
|  |  |  |

---

## J19 — Herzliya Station (תחנת רכבת הרצליה) → Beilinson Hospital, Petah Tikva (בית חולים בילינסון)

**Required journey #7** — PRD §7 #7 at least one transfer · category `with-transfer` · calendar rule `weekday_morning`

**Requested:** Depart at Mon 2026-10-05 08:00 (UTC+03:00)  
Request field: `departAt=2026-10-05T08:00:00+03:00`
**Calendar flags:** ordinary day
**Compare:** [Google Maps transit](https://www.google.com/maps/dir/?api=1&origin=32.1656,34.8095&destination=32.087,34.858&travelmode=transit) · [Moovit (unofficial deep link; may not prefill)](https://moovitapp.com/?fll=32.1656_34.8095&tll=32.087_34.858&from=Herzliya%20Station&to=Beilinson%20Hospital%2C%20Petah%20Tikva) · Set the time yourself to **Depart at 08:00, Mon 2026-10-05** (Google's documented URL has no time parameter).
**Corpus expectation (context, not a verdict):** outcome `route`, max_duration_min = 100, max_transfers = 3, min_duration_min = 20, min_transfers = 1

> What to check: Must transfer. Is the transfer window realistic, not a 2-minute cross-platform miracle?

**API RESULT: 3 journey option(s) returned** (scheduled times).
Machine note: matches the corpus expectation `route`. This is not a judgement of quality.
Request id `4dd1230aed614951affdcf07980e2785`.

**Option 1:** departs Mon 2026-10-05 08:03, arrives Mon 2026-10-05 09:14; total 71 min, 1 transfer(s), walking 13 min / 622 m

1. Walk 4 min, 184 m: START 08:03 -> גלגלי הפלדה/יוחנן הסנדלר 08:07
2. **bus 91** (מטרופולין) toward תל אביב יפו_מסוף הטייסים: board גלגלי הפלדה/יוחנן הסנדלר [code 26761] 08:07 -> alight דרך בר לב/דרך משה דיין [code 21538] 08:36 (service date 2026-10-05, trip `25080591_041026`)
3. Walk 2 min, 0 m: דרך בר לב/דרך משה דיין 08:36 -> דרך בר לב/דרך משה דיין 08:38
4. **bus 41** (דן) toward פתח תקווה_מסוף משה ארנס: board דרך בר לב/דרך משה דיין [code 21538] 08:39 -> alight בריכת נווה עוז/דרך יצחק רבין [code 38468] 09:07 (service date 2026-10-05, trip `8073634_051026`)
5. Walk 7 min, 438 m: בריכת נווה עוז/דרך יצחק רבין 09:07 -> END 09:14

Transfers (alight to next boarding, including any walk): דרך בר לב/דרך משה דיין -> דרך בר לב/דרך משה דיין: 3 min

**Option 2:** departs Mon 2026-10-05 08:03, arrives Mon 2026-10-05 08:57; total 54 min, 2 transfer(s), walking 15 min / 878 m

1. Walk 4 min, 184 m: START 08:03 -> גלגלי הפלדה/יוחנן הסנדלר 08:07
2. **bus 91** (מטרופולין) toward תל אביב יפו_מסוף הטייסים: board גלגלי הפלדה/יוחנן הסנדלר [code 26761] 08:07 -> alight ת.רק''ל שאול המלך/דרך מנחם בגין [code 20837] 08:24 (service date 2026-10-05, trip `25080591_041026`)
3. Walk 2 min, 126 m: ת.רק''ל שאול המלך/דרך מנחם בגין 08:27 -> שאול המלך 08:29
4. **light_rail 1** (תבל) toward פתח תקווה_ת. מרכזית פתח תקווה: board שאול המלך [code 20709] 08:29 -> alight שחם [code 36313] 08:45 (service date 2026-10-05, trip `585428502_021026`)
5. Walk 2 min, 124 m: שחם 08:45 -> ת.רק''ל שחם/דרך יצחק רבין 08:47
6. **bus 75** (מטרופולין) toward גני תקווה_מרכז גני תקווה: board ת.רק''ל שחם/דרך יצחק רבין [code 36570] 08:48 -> alight דרך יצחק רבין/דגניה [code 35485] 08:50 (service date 2026-10-05, trip `586235023_041026`)
7. Walk 7 min, 444 m: דרך יצחק רבין/דגניה 08:50 -> END 08:57

Transfers (alight to next boarding, including any walk): ת.רק''ל שאול המלך/דרך מנחם בגין -> שאול המלך: 5 min; שחם -> ת.רק''ל שחם/דרך יצחק רבין: 3 min

**Option 3:** departs Mon 2026-10-05 08:06, arrives Mon 2026-10-05 09:01; total 55 min, 3 transfer(s), walking 17 min / 878 m

1. Walk 4 min, 184 m: START 08:06 -> גלגלי הפלדה/יוחנן הסנדלר 08:10
2. **bus 90** (מטרופולין) toward תל אביב יפו_מסוף כרמלית: board גלגלי הפלדה/יוחנן הסנדלר [code 26761] 08:10 -> alight סינמה סיטי/כביש 2 [code 26966] 08:14 (service date 2026-10-05, trip `19637410_041026`)
3. Walk 2 min, 0 m: סינמה סיטי/כביש 2 08:16 -> סינמה סיטי/כביש 2 08:18
4. **bus 347** (מטרופולין) toward תל אביב יפו_תחנה מרכזית: board סינמה סיטי/כביש 2 [code 26966] 08:18 -> alight ת.רק''ל שאול המלך/דרך מנחם בגין [code 20837] 08:31 (service date 2026-10-05, trip `42548405_031026`)
5. Walk 2 min, 126 m: ת.רק''ל שאול המלך/דרך מנחם בגין 08:32 -> שאול המלך 08:34
6. **light_rail 1** (תבל) toward פתח תקווה_ת. מרכזית פתח תקווה: board שאול המלך [code 20709] 08:34 -> alight שחם [code 36313] 08:50 (service date 2026-10-05, trip `585373596_021026`)
7. Walk 2 min, 124 m: שחם 08:50 -> ת.רק''ל שחם/דרך יצחק רבין 08:52
8. **bus 143** (סופרבוס) toward חולון_מוזיאון אגד: board ת.רק''ל שחם/דרך יצחק רבין [code 36570] 08:53 -> alight דרך יצחק רבין/דגניה [code 35485] 08:54 (service date 2026-10-05, trip `586111406_011026`)
9. Walk 7 min, 444 m: דרך יצחק רבין/דגניה 08:54 -> END 09:01

Transfers (alight to next boarding, including any walk): סינמה סיטי/כביש 2 -> סינמה סיטי/כביש 2: 4 min; ת.רק''ל שאול המלך/דרך מנחם בגין -> שאול המלך: 3 min; שחם -> ת.רק''ל שחם/דרך יצחק רבין: 3 min

| Usable? (Y/N) | Notes | Compared against / when checked |
|---|---|---|
|  |  |  |

---

## J20 — Netanya Station (תחנת רכבת נתניה) → Mahane Yehuda Market (שוק מחנה יהודה)

category `with-transfer` · calendar rule `weekday_midday`

**Requested:** Depart at Tue 2026-10-06 13:00 (UTC+03:00)  
Request field: `departAt=2026-10-06T13:00:00+03:00`
**Calendar flags:** ordinary day
**Compare:** [Google Maps transit](https://www.google.com/maps/dir/?api=1&origin=32.3097,34.8619&destination=31.7853,35.2124&travelmode=transit) · [Moovit (unofficial deep link; may not prefill)](https://moovitapp.com/?fll=32.3097_34.8619&tll=31.7853_35.2124&from=Netanya%20Station&to=Mahane%20Yehuda%20Market) · Set the time yourself to **Depart at 13:00, Tue 2026-10-06** (Google's documented URL has no time parameter).
**Corpus expectation (context, not a verdict):** outcome `route`, max_duration_min = 200, max_transfers = 3, min_duration_min = 60, min_transfers = 1

> What to check: Coastal rail then Jerusalem light rail. Checks cross-operator chaining.

**API RESULT: 3 journey option(s) returned** (scheduled times).
Machine note: matches the corpus expectation `route`. This is not a judgement of quality.
Request id `22a9a11dc9a84befaac3b1197710f7fb`.

**Option 1:** departs Tue 2026-10-06 13:03, arrives Tue 2026-10-06 15:13; total 130 min, 2 transfer(s), walking 33 min / 1868 m

1. Walk 15 min, 889 m: START 13:03 -> בית ספר טשרניחובסקי/בן צבי 13:18
2. **bus 611** (מטרופולין) toward תל אביב יפו_תחנה מרכזית: board בית ספר טשרניחובסקי/בן צבי [code 39204] 13:18 -> alight ת. רכבת תל אביב - סבידור/דרך נמיר [code 20349] 13:51 (service date 2026-10-06, trip `42518425_021026`)
3. Walk 5 min, 297 m: ת. רכבת תל אביב - סבידור/דרך נמיר 14:00 -> ת.רכבת תל אביב - סבידור/רציפים B 14:05
4. **bus 490** (אגד) toward ירושלים_אזור תעשיה תלפיות: board ת.רכבת תל אביב - סבידור/רציפים B [code 20740] 14:05 -> alight צומת גבעת מרדכי/בייט [code 9895] 14:48 (service date 2026-10-06, trip `584961616_041026`)
5. Walk 2 min, 0 m: צומת גבעת מרדכי/בייט 14:48 -> צומת גבעת מרדכי/בייט 14:50
6. **bus 39א** (אגד) toward מרכז תחבורתי הארזים: board צומת גבעת מרדכי/בייט [code 9895] 14:54 -> alight מלכי ישראל/תחכמוני [code 1917] 15:02 (service date 2026-10-06, trip `585330389_051026`)
7. Walk 11 min, 682 m: מלכי ישראל/תחכמוני 15:02 -> END 15:13

Transfers (alight to next boarding, including any walk): ת. רכבת תל אביב - סבידור/דרך נמיר -> ת.רכבת תל אביב - סבידור/רציפים B: 14 min; צומת גבעת מרדכי/בייט -> צומת גבעת מרדכי/בייט: 6 min

**Option 2:** departs Tue 2026-10-06 13:03, arrives Tue 2026-10-06 15:03; total 120 min, 3 transfer(s), walking 25 min / 1507 m

1. Walk 15 min, 889 m: START 13:03 -> בית ספר טשרניחובסקי/בן צבי 13:18
2. **bus 611** (מטרופולין) toward תל אביב יפו_תחנה מרכזית: board בית ספר טשרניחובסקי/בן צבי [code 39204] 13:18 -> alight מחלף הסירה לדרום [code 20142] 13:37 (service date 2026-10-06, trip `42518425_021026`)
3. Walk 2 min, 0 m: מחלף הסירה לדרום 13:37 -> מחלף הסירה לדרום 13:39
4. **bus 91** (מטרופולין) toward תל אביב יפו_מסוף הטייסים: board מחלף הסירה לדרום [code 20142] 13:39 -> alight ת. רכבת השלום [code 21023] 13:56 (service date 2026-10-06, trip `19065382_041026`)
5. Walk 2 min, 226 m: ת. רכבת השלום 14:07 -> השלום 14:09
6. **rail ** (רכבת ישראל) toward 747: board השלום [code 17046] 14:09 -> alight ירושלים/יצחק נבון [code 17118] 14:52 (service date 2026-10-06, trip `1_520931`)
7. Walk 2 min, 162 m: ירושלים/יצחק נבון 14:52 -> ת. מרכזית ירושלים/יפו 14:54
8. **bus 75** (סופרבוס) toward חומת שמואל: board ת. מרכזית ירושלים/יפו [code 4156] 14:55 -> alight שוק מחנה יהודה/אגריפס [code 3523] 14:59 (service date 2026-10-06, trip `584640799_031026`)
9. Walk 4 min, 230 m: שוק מחנה יהודה/אגריפס 14:59 -> END 15:03

Transfers (alight to next boarding, including any walk): מחלף הסירה לדרום -> מחלף הסירה לדרום: 2 min; ת. רכבת השלום -> השלום: 13 min; ירושלים/יצחק נבון -> ת. מרכזית ירושלים/יפו: 3 min

**Option 3:** departs Tue 2026-10-06 13:04, arrives Tue 2026-10-06 15:13; total 129 min, 3 transfer(s), walking 27 min / 1487 m

1. Walk 7 min, 371 m: START 13:04 -> האר''י/הרב חרל''פ 13:11
2. **bus 72** (אקסטרה) toward תחנת הרכבת: board האר''י/הרב חרל''פ [code 39238] 13:11 -> alight שד. בן צבי/היהלומן אברהם [code 39216] 13:14 (service date 2026-10-06, trip `585092382_041026`)
3. Walk 2 min, 137 m: שד. בן צבי/היהלומן אברהם 13:14 -> בן צבי/הגר''א 13:16
4. **bus 611** (מטרופולין) toward תל אביב יפו_תחנה מרכזית: board בן צבי/הגר''א [code 39215] 13:16 -> alight ת. רכבת תל אביב - סבידור/דרך נמיר [code 20349] 13:51 (service date 2026-10-06, trip `42518425_021026`)
5. Walk 5 min, 297 m: ת. רכבת תל אביב - סבידור/דרך נמיר 14:00 -> ת.רכבת תל אביב - סבידור/רציפים B 14:05
6. **bus 490** (אגד) toward ירושלים_אזור תעשיה תלפיות: board ת.רכבת תל אביב - סבידור/רציפים B [code 20740] 14:05 -> alight צומת גבעת מרדכי/בייט [code 9895] 14:48 (service date 2026-10-06, trip `584961616_041026`)
7. Walk 2 min, 0 m: צומת גבעת מרדכי/בייט 14:48 -> צומת גבעת מרדכי/בייט 14:50
8. **bus 39א** (אגד) toward מרכז תחבורתי הארזים: board צומת גבעת מרדכי/בייט [code 9895] 14:54 -> alight מלכי ישראל/תחכמוני [code 1917] 15:02 (service date 2026-10-06, trip `585330389_051026`)
9. Walk 11 min, 682 m: מלכי ישראל/תחכמוני 15:02 -> END 15:13

Transfers (alight to next boarding, including any walk): שד. בן צבי/היהלומן אברהם -> בן צבי/הגר''א: 2 min; ת. רכבת תל אביב - סבידור/דרך נמיר -> ת.רכבת תל אביב - סבידור/רציפים B: 14 min; צומת גבעת מרדכי/בייט -> צומת גבעת מרדכי/בייט: 6 min

| Usable? (Y/N) | Notes | Compared against / when checked |
|---|---|---|
|  |  |  |

---

## J21 — Tel Aviv Savidor Center (תל אביב סבידור מרכז) → Ben Gurion Airport T3 (נתב"ג טרמינל 3)

**Required journey #8** — PRD §7 #8 late night · category `late-night` · calendar rule `late_night`

**Requested:** Depart at Tue 2026-10-06 23:40 (UTC+03:00)  
Request field: `departAt=2026-10-06T23:40:00+03:00`
**Calendar flags:** ordinary day
**Compare:** [Google Maps transit](https://www.google.com/maps/dir/?api=1&origin=32.0836,34.7981&destination=32.0004,34.8705&travelmode=transit) · [Moovit (unofficial deep link; may not prefill)](https://moovitapp.com/?fll=32.0836_34.7981&tll=32.0004_34.8705&from=Tel%20Aviv%20Savidor%20Center&to=Ben%20Gurion%20Airport%20T3) · Set the time yourself to **Depart at 23:40, Tue 2026-10-06** (Google's documented URL has no time parameter).
**Corpus expectation (context, not a verdict):** outcome `route`, max_duration_min = 120, max_transfers = 2, min_duration_min = 10, modes_any_of = ['rail', 'bus']

> What to check: Airport rail runs deep into the night. Does the engine know that?

**API RESULT: 3 journey option(s) returned** (scheduled times).
Machine note: matches the corpus expectation `route`. This is not a judgement of quality.
Request id `467c74c5229d446db17a13a042744948`.

**Option 1:** departs Tue 2026-10-06 23:40, arrives Wed 2026-10-07 00:04; total 24 min, 0 transfer(s), walking 2 min / 31 m

1. Walk 1 min, 27 m: START 23:40 -> תל אביב מרכז 23:41
2. **rail ** (רכבת ישראל) toward 785: board תל אביב מרכז [code 17038] 23:41 -> alight נתב''ג [code 17090] 00:03 (service date 2026-10-06, trip `1_520882`)
3. Walk 1 min, 4 m: נתב''ג 00:03 -> END 00:04

Transfers (alight to next boarding, including any walk): none

**Option 2:** departs Wed 2026-10-07 00:36, arrives Wed 2026-10-07 00:56; total 20 min, 0 transfer(s), walking 2 min / 31 m

1. Walk 1 min, 27 m: START 00:36 -> תל אביב מרכז 00:37
2. **rail ** (רכבת ישראל) toward 137: board תל אביב מרכז [code 17038] 00:37 -> alight נתב''ג [code 17090] 00:55 (service date 2026-10-06, trip `1_520897`)
3. Walk 1 min, 4 m: נתב''ג 00:55 -> END 00:56

Transfers (alight to next boarding, including any walk): none

**Option 3:** departs Wed 2026-10-07 00:46, arrives Wed 2026-10-07 01:02; total 16 min, 0 transfer(s), walking 2 min / 31 m

1. Walk 1 min, 27 m: START 00:46 -> תל אביב מרכז 00:47
2. **rail ** (רכבת ישראל) toward 9701: board תל אביב מרכז [code 17038] 00:47 -> alight נתב''ג [code 17090] 01:01 (service date 2026-10-07, trip `1_523443`)
3. Walk 1 min, 4 m: נתב''ג 01:01 -> END 01:02

Transfers (alight to next boarding, including any walk): none

| Usable? (Y/N) | Notes | Compared against / when checked |
|---|---|---|
|  |  |  |

---

## J22 — Dizengoff Center (דיזנגוף סנטר) → Ramat Gan Bursa (רמת גן בורסה)

**Required journey #9** — PRD §7 #9 crossing a service-day boundary · category `service-day-boundary` · calendar rule `after_midnight`

**Requested:** Depart at Wed 2026-10-07 02:30 (UTC+03:00)  
Request field: `departAt=2026-10-07T02:30:00+03:00`
**Calendar flags:** ordinary day
**Compare:** [Google Maps transit](https://www.google.com/maps/dir/?api=1&origin=32.0757,34.7748&destination=32.0838,34.8044&travelmode=transit) · [Moovit (unofficial deep link; may not prefill)](https://moovitapp.com/?fll=32.0757_34.7748&tll=32.0838_34.8044&from=Dizengoff%20Center&to=Ramat%20Gan%20Bursa) · Set the time yourself to **Depart at 02:30, Wed 2026-10-07** (Google's documented URL has no time parameter).
**Corpus expectation (context, not a verdict):** outcome `either`, max_duration_min = 180, min_duration_min = 5

> What to check: THE GTFS trap: trips after midnight belong to the previous service day with times like 25:30:00. Either a valid night route or a clean no-route is acceptable. A crash, an empty result with no explanation, or a route departing 20 hours later is a FAIL.

**API RESULT: 3 journey option(s) returned** (scheduled times).
Request id `6aff029458134c7f88d781a8e44badde`.

**Option 1:** departs Wed 2026-10-07 02:39, arrives Wed 2026-10-07 04:19; total 100 min, 1 transfer(s), walking 17 min / 1517 m

1. Walk 3 min, 135 m: START 02:39 -> דיזנגוף סנטר/דיזנגוף 02:42
2. **bus 445** (מטרופולין) toward נמל תעופה בן גוריון_טרמינל 3: board דיזנגוף סנטר/דיזנגוף [code 25565] 02:42 -> alight נתב''ג טרמינל 3/קומת תח''צ [code 35275] 03:23 (service date 2026-10-07, trip `53738960_041026`)
3. Walk 2 min, 616 m: נתב''ג טרמינל 3/קומת תח''צ 03:23 -> נתב''ג 03:25
4. **rail ** (רכבת ישראל) toward 9706: board נתב''ג [code 17090] 03:53 -> alight תל אביב מרכז [code 17038] 04:07 (service date 2026-10-07, trip `1_523448`)
5. Walk 12 min, 766 m: תל אביב מרכז 04:07 -> END 04:19

Transfers (alight to next boarding, including any walk): נתב''ג טרמינל 3/קומת תח''צ -> נתב''ג: 30 min

**Option 2:** departs Wed 2026-10-07 04:57, arrives Wed 2026-10-07 05:38; total 41 min, 1 transfer(s), walking 9 min / 502 m

1. Walk 3 min, 135 m: START 04:57 -> דיזנגוף סנטר/דיזנגוף 05:00
2. **bus 172** (דן) toward חולון_מסוף אזור תעשייה: board דיזנגוף סנטר/דיזנגוף [code 25565] 05:00 -> alight שוקן/דרך שלמה [code 20388] 05:10 (service date 2026-10-07, trip `584954854_051026`)
3. Walk 2 min, 118 m: שוקן/דרך שלמה 05:10 -> דרך שלמה/שוקן 05:12
4. **bus 42** (דן) toward תל אביב יפו_קריית עתידים: board דרך שלמה/שוקן [code 20097] 05:18 -> alight ת.רק''ל אבא הלל [code 26248] 05:34 (service date 2026-10-07, trip `46019436_051026`)
5. Walk 4 min, 249 m: ת.רק''ל אבא הלל 05:34 -> END 05:38

Transfers (alight to next boarding, including any walk): שוקן/דרך שלמה -> דרך שלמה/שוקן: 8 min

**Option 3:** departs Wed 2026-10-07 04:57, arrives Wed 2026-10-07 05:23; total 26 min, 2 transfer(s), walking 11 min / 487 m

1. Walk 3 min, 135 m: START 04:57 -> דיזנגוף סנטר/דיזנגוף 05:00
2. **bus 172** (דן) toward חולון_מסוף אזור תעשייה: board דיזנגוף סנטר/דיזנגוף [code 25565] 05:00 -> alight שד' רוטשילד/שיינקין [code 25587] 05:03 (service date 2026-10-07, trip `584954854_051026`)
3. Walk 2 min, 112 m: שד' רוטשילד/שיינקין 05:05 -> שד' רוטשילד/שיינקין 05:07
4. **bus 23** (דן) toward גבעתיים_כורזין: board שד' רוטשילד/שיינקין [code 21732] 05:07 -> alight ת.רק''ל יהודית/דרך מנחם בגין [code 20727] 05:11 (service date 2026-10-07, trip `585553063_051026`)
5. Walk 2 min, 0 m: ת.רק''ל יהודית/דרך מנחם בגין 05:11 -> ת.רק''ל יהודית/דרך מנחם בגין 05:13
6. **bus 50** (דן) toward פתח תקווה_רכבת סגולה: board ת.רק''ל יהודית/דרך מנחם בגין [code 20727] 05:13 -> alight ת.רק''ל אבא הלל/דרך ז'בוטינסקי [code 21644] 05:19 (service date 2026-10-07, trip `585465512_051026`)
7. Walk 4 min, 240 m: ת.רק''ל אבא הלל/דרך ז'בוטינסקי 05:19 -> END 05:23

Transfers (alight to next boarding, including any walk): שד' רוטשילד/שיינקין -> שד' רוטשילד/שיינקין: 4 min; ת.רק''ל יהודית/דרך מנחם בגין -> ת.רק''ל יהודית/דרך מנחם בגין: 2 min

| Usable? (Y/N) | Notes | Compared against / when checked |
|---|---|---|
|  |  |  |

---

## J23 — Har Karkom, central Negev (הר כרכום) → Metula (מטולה)

**Required journey #10** — PRD §7 #10 no reasonable transit route · category `no-reasonable-route` · calendar rule `after_midnight`

**Requested:** Depart at Wed 2026-10-07 02:30 (UTC+03:00)  
Request field: `departAt=2026-10-07T02:30:00+03:00`
**Calendar flags:** ordinary day
**Compare:** [Google Maps transit](https://www.google.com/maps/dir/?api=1&origin=30.28,34.74&destination=33.2778,35.5786&travelmode=transit) · [Moovit (unofficial deep link; may not prefill)](https://moovitapp.com/?fll=30.28_34.74&tll=33.2778_35.5786&from=Har%20Karkom%2C%20central%20Negev&to=Metula) · Set the time yourself to **Depart at 02:30, Wed 2026-10-07** (Google's documented URL has no time parameter).
**Corpus expectation (context, not a verdict):** outcome `no-route`

> What to check: Origin is 23.5 km from the nearest stop in the feed — measured, not assumed. No walking budget reaches transit, so 'no route' is the only correct answer. An itinerary here means the engine is inventing access.

**API RESULT: NO ROUTE** — a valid search inside coverage returned no journey. The API does not state a cause (no service, walking limit and data gaps look alike).
Machine note: matches the corpus expectation `no-route`. This is not a judgement of quality.
Request id `070c86e1c25649a8802bd7d6e54a5d2e`.

| Usable? (Y/N) | Notes | Compared against / when checked |
|---|---|---|
|  |  |  |

---

## J24 — Masada Junction (צומת מצדה) → Beersheba Central (באר שבע מרכז)

category `long-walk-accessibility` · calendar rule `weekday_midday`

**Requested:** Depart at Tue 2026-10-06 13:00 (UTC+03:00)  
Request field: `departAt=2026-10-06T13:00:00+03:00`
**Calendar flags:** ordinary day
**Compare:** [Google Maps transit](https://www.google.com/maps/dir/?api=1&origin=31.3156,35.3539&destination=31.243,34.7983&travelmode=transit) · [Moovit (unofficial deep link; may not prefill)](https://moovitapp.com/?fll=31.3156_35.3539&tll=31.243_34.7983&from=Masada%20Junction&to=Beersheba%20Central) · Set the time yourself to **Depart at 13:00, Tue 2026-10-06** (Google's documented URL has no time parameter).
**Corpus expectation (context, not a verdict):** outcome `either`, max_duration_min = 300, max_walk_m = 3000, min_duration_min = 40

> What to check: Sparse desert service with long access walks. Check the walking legs are physically plausible — not a 6 km hike along a highway shoulder.

**API RESULT: NO ROUTE** — a valid search inside coverage returned no journey. The API does not state a cause (no service, walking limit and data gaps look alike).
Request id `548c05689a804b0da08590d5e2831fd5`.

| Usable? (Y/N) | Notes | Compared against / when checked |
|---|---|---|
|  |  |  |

---

## J25 — Dizengoff Center (דיזנגוף סנטר) → Yitzhak Navon Station (תחנת יצחק נבון)

category `shabbat-holiday` · calendar rule `shabbat`

**Requested:** Depart at Sat 2026-10-10 12:00 (UTC+03:00)  
Request field: `departAt=2026-10-10T12:00:00+03:00`
**Calendar flags:** Shabbat
**Compare:** [Google Maps transit](https://www.google.com/maps/dir/?api=1&origin=32.0757,34.7748&destination=31.7888,35.2027&travelmode=transit) · [Moovit (unofficial deep link; may not prefill)](https://moovitapp.com/?fll=32.0757_34.7748&tll=31.7888_35.2027&from=Dizengoff%20Center&to=Yitzhak%20Navon%20Station) · Set the time yourself to **Depart at 12:00, Sat 2026-10-10** (Google's documented URL has no time parameter).
**Corpus expectation (context, not a verdict):** outcome `either`

> What to check: THE Israeli calendar case: national rail and most buses do not run on Shabbat, while some operators and city lines do. A confident full itinerary on Saturday noon is almost certainly wrong. Verify whatever it returns against the actual calendar.txt entries.

**API RESULT: 3 journey option(s) returned** (scheduled times).
Request id `45cdbdb8b2e7477fa987abcbaef5d6ce`.

**Option 1:** departs Sat 2026-10-10 18:50, arrives Sat 2026-10-10 20:04; total 74 min, 1 transfer(s), walking 10 min / 627 m

1. Walk 3 min, 136 m: START 18:50 -> דיזנגוף סנטר/טשרניחובסקי 18:53
2. **bus 18** (דן) toward תל אביב יפו_רכבת מרכז: board דיזנגוף סנטר/טשרניחובסקי [code 25564] 18:53 -> alight ת. רכבת תל אביב - סבידור/הורדה [code 27997] 19:04 (service date 2026-10-10, trip `649376_081026`)
3. Walk 2 min, 184 m: ת. רכבת תל אביב - סבידור/הורדה 19:04 -> ת.רכבת תל אביב - סבידור/רציפים B 19:06
4. **bus 480** (אגד) toward ירושלים_תחנה מרכזית: board ת.רכבת תל אביב - סבידור/רציפים B [code 20740] 19:15 -> alight ת. מרכזית ירושלים/הורדה [code 6109] 19:59 (service date 2026-10-10, trip `8815703_041026`)
5. Walk 5 min, 307 m: ת. מרכזית ירושלים/הורדה 19:59 -> END 20:04

Transfers (alight to next boarding, including any walk): ת. רכבת תל אביב - סבידור/הורדה -> ת.רכבת תל אביב - סבידור/רציפים B: 11 min

**Option 2:** departs Sat 2026-10-10 19:10, arrives Sat 2026-10-10 20:19; total 69 min, 1 transfer(s), walking 10 min / 627 m

1. Walk 3 min, 136 m: START 19:10 -> דיזנגוף סנטר/טשרניחובסקי 19:13
2. **bus 18** (דן) toward תל אביב יפו_רכבת מרכז: board דיזנגוף סנטר/טשרניחובסקי [code 25564] 19:13 -> alight ת. רכבת תל אביב - סבידור/הורדה [code 27997] 19:24 (service date 2026-10-10, trip `7909362_081026`)
3. Walk 2 min, 184 m: ת. רכבת תל אביב - סבידור/הורדה 19:24 -> ת.רכבת תל אביב - סבידור/רציפים B 19:26
4. **bus 480** (אגד) toward ירושלים_תחנה מרכזית: board ת.רכבת תל אביב - סבידור/רציפים B [code 20740] 19:30 -> alight ת. מרכזית ירושלים/הורדה [code 6109] 20:14 (service date 2026-10-10, trip `4925744_041026`)
5. Walk 5 min, 307 m: ת. מרכזית ירושלים/הורדה 20:14 -> END 20:19

Transfers (alight to next boarding, including any walk): ת. רכבת תל אביב - סבידור/הורדה -> ת.רכבת תל אביב - סבידור/רציפים B: 6 min

**Option 3:** departs Sat 2026-10-10 19:27, arrives Sat 2026-10-10 20:34; total 67 min, 1 transfer(s), walking 10 min / 649 m

1. Walk 3 min, 136 m: START 19:27 -> דיזנגוף סנטר/טשרניחובסקי 19:30
2. **bus 61** (דן) toward רמת גן_מסוף עמידר: board דיזנגוף סנטר/טשרניחובסקי [code 25564] 19:30 -> alight ת. רכבת תל אביב סבידור/על פרשת דרכים [code 21140] 19:42 (service date 2026-10-10, trip `585014470_081026`)
3. Walk 2 min, 206 m: ת. רכבת תל אביב סבידור/על פרשת דרכים 19:42 -> ת.רכבת תל אביב - סבידור/רציפים B 19:44
4. **bus 480** (אגד) toward ירושלים_תחנה מרכזית: board ת.רכבת תל אביב - סבידור/רציפים B [code 20740] 19:45 -> alight ת. מרכזית ירושלים/הורדה [code 6109] 20:29 (service date 2026-10-10, trip `2100737_041026`)
5. Walk 5 min, 307 m: ת. מרכזית ירושלים/הורדה 20:29 -> END 20:34

Transfers (alight to next boarding, including any walk): ת. רכבת תל אביב סבידור/על פרשת דרכים -> ת.רכבת תל אביב - סבידור/רציפים B: 3 min

| Usable? (Y/N) | Notes | Compared against / when checked |
|---|---|---|
|  |  |  |

---

## J11-FRI — Tel Aviv Savidor Center (תל אביב סבידור מרכז) → Haifa Center HaShmona (חיפה מרכז השמונה)

category `intercity-rail` · calendar rule `friday_afternoon`

Calendar variant of J11: Friday afternoon: expect reduced or no rail service.

**Requested:** Depart at Fri 2026-10-09 15:30 (UTC+03:00)  
Request field: `departAt=2026-10-09T15:30:00+03:00`
**Calendar flags:** Friday (erev Shabbat)
**Compare:** [Google Maps transit](https://www.google.com/maps/dir/?api=1&origin=32.0836,34.7981&destination=32.8206,34.9985&travelmode=transit) · [Moovit (unofficial deep link; may not prefill)](https://moovitapp.com/?fll=32.0836_34.7981&tll=32.8206_34.9985&from=Tel%20Aviv%20Savidor%20Center&to=Haifa%20Center%20HaShmona) · Set the time yourself to **Depart at 15:30, Fri 2026-10-09** (Google's documented URL has no time parameter).
**Corpus expectation (context, not a verdict):** outcome `route`, max_duration_min = 130, max_transfers = 1, min_duration_min = 45, modes_any_of = ['rail']

> What to check: The flagship rail corridor. Cross-check timings against BetterRail.

**API RESULT: 3 journey option(s) returned** (scheduled times).
Machine note: matches the corpus expectation `route`. This is not a judgement of quality.
Request id `a7b25932bc7d46ffb0d3802f1ee51a2b`.

**Option 1:** departs Fri 2026-10-09 15:34, arrives Fri 2026-10-09 17:15; total 101 min, 1 transfer(s), walking 17 min / 1112 m

1. Walk 6 min, 431 m: START 15:34 -> ת. רכבת תל אביב - סבידור/דרך נמיר 15:40
2. **bus 909** (אגד) toward נהריה_תחנה מרכזית: board ת. רכבת תל אביב - סבידור/דרך נמיר [code 24068] 15:40 -> alight ת. מרכזית המפרץ/הורדה [code 43008] 16:54 (service date 2026-10-09, trip `59116972_041026`)
3. Walk 2 min, 112 m: ת. מרכזית המפרץ/הורדה 16:54 -> ת. מרכזית המפרץ/מטרונית לחיפה 16:56
4. **bus 2** (סופרבוס) toward חיפה_רכבת בת גלים: board ת. מרכזית המפרץ/מטרונית לחיפה [code 47488] 16:56 -> alight כרמלית [code 47203] 17:06 (service date 2026-10-09, trip `15020355_011026`)
5. Walk 9 min, 569 m: כרמלית 17:06 -> END 17:15

Transfers (alight to next boarding, including any walk): ת. מרכזית המפרץ/הורדה -> ת. מרכזית המפרץ/מטרונית לחיפה: 2 min

**Option 2:** departs Fri 2026-10-09 15:44, arrives Fri 2026-10-09 17:27; total 103 min, 1 transfer(s), walking 17 min / 1112 m

1. Walk 6 min, 431 m: START 15:44 -> ת. רכבת תל אביב - סבידור/דרך נמיר 15:50
2. **bus 909** (אגד) toward נהריה_תחנה מרכזית: board ת. רכבת תל אביב - סבידור/דרך נמיר [code 24068] 15:50 -> alight ת. מרכזית המפרץ/הורדה [code 43008] 17:04 (service date 2026-10-09, trip `585137869_041026`)
3. Walk 2 min, 112 m: ת. מרכזית המפרץ/הורדה 17:04 -> ת. מרכזית המפרץ/מטרונית לחיפה 17:06
4. **bus 2** (סופרבוס) toward חיפה_רכבת בת גלים: board ת. מרכזית המפרץ/מטרונית לחיפה [code 47488] 17:08 -> alight כרמלית [code 47203] 17:18 (service date 2026-10-09, trip `16128781_011026`)
5. Walk 9 min, 569 m: כרמלית 17:18 -> END 17:27

Transfers (alight to next boarding, including any walk): ת. מרכזית המפרץ/הורדה -> ת. מרכזית המפרץ/מטרונית לחיפה: 4 min

**Option 3:** departs Fri 2026-10-09 15:54, arrives Fri 2026-10-09 17:39; total 105 min, 1 transfer(s), walking 17 min / 1112 m

1. Walk 6 min, 431 m: START 15:54 -> ת. רכבת תל אביב - סבידור/דרך נמיר 16:00
2. **bus 909** (אגד) toward נהריה_תחנה מרכזית: board ת. רכבת תל אביב - סבידור/דרך נמיר [code 24068] 16:00 -> alight ת. מרכזית המפרץ/הורדה [code 43008] 17:14 (service date 2026-10-09, trip `585657624_041026`)
3. Walk 2 min, 112 m: ת. מרכזית המפרץ/הורדה 17:14 -> ת. מרכזית המפרץ/מטרונית לחיפה 17:16
4. **bus 2** (סופרבוס) toward חיפה_רכבת בת גלים: board ת. מרכזית המפרץ/מטרונית לחיפה [code 47488] 17:20 -> alight כרמלית [code 47203] 17:30 (service date 2026-10-09, trip `15020358_011026`)
5. Walk 9 min, 569 m: כרמלית 17:30 -> END 17:39

Transfers (alight to next boarding, including any walk): ת. מרכזית המפרץ/הורדה -> ת. מרכזית המפרץ/מטרונית לחיפה: 6 min

| Usable? (Y/N) | Notes | Compared against / when checked |
|---|---|---|
|  |  |  |

---

## J12-FRI — Tel Aviv Savidor Center (תל אביב סבידור מרכז) → Yitzhak Navon Station (תחנת יצחק נבון)

category `intercity-rail` · calendar rule `friday_afternoon`

Calendar variant of J12: Friday afternoon: expect reduced or no rail service.

**Requested:** Depart at Fri 2026-10-09 15:30 (UTC+03:00)  
Request field: `departAt=2026-10-09T15:30:00+03:00`
**Calendar flags:** Friday (erev Shabbat)
**Compare:** [Google Maps transit](https://www.google.com/maps/dir/?api=1&origin=32.0836,34.7981&destination=31.7888,35.2027&travelmode=transit) · [Moovit (unofficial deep link; may not prefill)](https://moovitapp.com/?fll=32.0836_34.7981&tll=31.7888_35.2027&from=Tel%20Aviv%20Savidor%20Center&to=Yitzhak%20Navon%20Station) · Set the time yourself to **Depart at 15:30, Fri 2026-10-09** (Google's documented URL has no time parameter).
**Corpus expectation (context, not a verdict):** outcome `route`, max_duration_min = 110, max_transfers = 1, min_duration_min = 30, modes_any_of = ['rail']

> What to check: Fast line. If it routes by bus, the rail calendar is probably misread.

**API RESULT: 3 journey option(s) returned** (scheduled times).
Machine note: matches the corpus expectation `route`. This is not a judgement of quality.
Request id `185d068a13d44108bc25f989a8ad49fe`.

**Option 1:** departs Fri 2026-10-09 15:30, arrives Fri 2026-10-09 16:25; total 55 min, 0 transfer(s), walking 11 min / 710 m

1. Walk 6 min, 403 m: START 15:30 -> ת.רכבת תל אביב - סבידור/רציפים B 15:36
2. **bus 480** (אגד) toward ירושלים_תחנה מרכזית: board ת.רכבת תל אביב - סבידור/רציפים B [code 20740] 15:36 -> alight ת. מרכזית ירושלים/הורדה [code 6109] 16:20 (service date 2026-10-09, trip `2117248_041026`)
3. Walk 5 min, 307 m: ת. מרכזית ירושלים/הורדה 16:20 -> END 16:25

Transfers (alight to next boarding, including any walk): none

**Option 2:** departs Fri 2026-10-09 15:42, arrives Fri 2026-10-09 16:37; total 55 min, 0 transfer(s), walking 11 min / 710 m

1. Walk 6 min, 403 m: START 15:42 -> ת.רכבת תל אביב - סבידור/רציפים B 15:48
2. **bus 480** (אגד) toward ירושלים_תחנה מרכזית: board ת.רכבת תל אביב - סבידור/רציפים B [code 20740] 15:48 -> alight ת. מרכזית ירושלים/הורדה [code 6109] 16:32 (service date 2026-10-09, trip `2117249_041026`)
3. Walk 5 min, 307 m: ת. מרכזית ירושלים/הורדה 16:32 -> END 16:37

Transfers (alight to next boarding, including any walk): none

**Option 3:** departs Fri 2026-10-09 15:54, arrives Fri 2026-10-09 16:49; total 55 min, 0 transfer(s), walking 11 min / 710 m

1. Walk 6 min, 403 m: START 15:54 -> ת.רכבת תל אביב - סבידור/רציפים B 16:00
2. **bus 480** (אגד) toward ירושלים_תחנה מרכזית: board ת.רכבת תל אביב - סבידור/רציפים B [code 20740] 16:00 -> alight ת. מרכזית ירושלים/הורדה [code 6109] 16:44 (service date 2026-10-09, trip `1401293_041026`)
3. Walk 5 min, 307 m: ת. מרכזית ירושלים/הורדה 16:44 -> END 16:49

Transfers (alight to next boarding, including any walk): none

| Usable? (Y/N) | Notes | Compared against / when checked |
|---|---|---|
|  |  |  |

---

## J11-SAT — Tel Aviv Savidor Center (תל אביב סבידור מרכז) → Haifa Center HaShmona (חיפה מרכז השמונה)

category `intercity-rail` · calendar rule `shabbat`

Calendar variant of J11: Saturday noon: expect no national rail.

**Requested:** Depart at Sat 2026-10-10 12:00 (UTC+03:00)  
Request field: `departAt=2026-10-10T12:00:00+03:00`
**Calendar flags:** Shabbat
**Compare:** [Google Maps transit](https://www.google.com/maps/dir/?api=1&origin=32.0836,34.7981&destination=32.8206,34.9985&travelmode=transit) · [Moovit (unofficial deep link; may not prefill)](https://moovitapp.com/?fll=32.0836_34.7981&tll=32.8206_34.9985&from=Tel%20Aviv%20Savidor%20Center&to=Haifa%20Center%20HaShmona) · Set the time yourself to **Depart at 12:00, Sat 2026-10-10** (Google's documented URL has no time parameter).
**Corpus expectation (context, not a verdict):** outcome `route`, max_duration_min = 130, max_transfers = 1, min_duration_min = 45, modes_any_of = ['rail']

> What to check: The flagship rail corridor. Cross-check timings against BetterRail.

**API RESULT: 3 journey option(s) returned** (scheduled times).
Machine note: matches the corpus expectation `route`. This is not a judgement of quality.
Request id `517869149b44452880d067f661069bd1`.

**Option 1:** departs Sat 2026-10-10 15:35, arrives Sat 2026-10-10 18:30; total 175 min, 2 transfer(s), walking 19 min / 1362 m

1. Walk 6 min, 431 m: START 15:35 -> ת. רכבת תל אביב - סבידור/דרך נמיר 15:41
2. **bus 825** (אגד) toward עפולה_תחנה מרכזית: board ת. רכבת תל אביב - סבידור/דרך נמיר [code 24068] 15:41 -> alight ת.מרכזית עפולה/הורדה [code 52152] 17:10 (service date 2026-10-10, trip `25275651_021026`)
3. Walk 2 min, 250 m: ת.מרכזית עפולה/הורדה 17:13 -> ת.מרכזית עפולה/רציפים 17:15
4. **bus 301** (סופרבוס) toward חיפה_מרכזית המפרץ: board ת.מרכזית עפולה/רציפים [code 52174] 17:15 -> alight ת. מרכזית המפרץ/הורדה [code 43008] 17:56 (service date 2026-10-10, trip `14464441_021026`)
5. Walk 2 min, 112 m: ת. מרכזית המפרץ/הורדה 17:56 -> ת. מרכזית המפרץ/מטרונית לחיפה 17:58
6. **bus 1** (סופרבוס) toward חיפה_מרכזית חוף הכרמל: board ת. מרכזית המפרץ/מטרונית לחיפה [code 47488] 18:07 -> alight כרמלית [code 47203] 18:21 (service date 2026-10-10, trip `15018301_011026`)
7. Walk 9 min, 569 m: כרמלית 18:21 -> END 18:30

Transfers (alight to next boarding, including any walk): ת.מרכזית עפולה/הורדה -> ת.מרכזית עפולה/רציפים: 5 min; ת. מרכזית המפרץ/הורדה -> ת. מרכזית המפרץ/מטרונית לחיפה: 11 min

**Option 2:** departs Sat 2026-10-10 16:34, arrives Sat 2026-10-10 18:47; total 133 min, 1 transfer(s), walking 17 min / 1253 m

1. Walk 6 min, 431 m: START 16:34 -> ת. רכבת תל אביב - סבידור/דרך נמיר 16:40
2. **bus 836** (אגד) toward טבריה_תחנה מרכזית: board ת. רכבת תל אביב - סבידור/דרך נמיר [code 24068] 16:40 -> alight צומת השומרים [code 51536] 17:55 (service date 2026-10-10, trip `25276278_041026`)
3. Walk 2 min, 229 m: צומת השומרים 17:55 -> צומת השומרים 17:57
4. **bus 332** (נסיעות ותיירות) toward חיפה_רכבת מרכז השמונה: board צומת השומרים [code 43024] 18:13 -> alight קריית הממשלה/העצמאות [code 43096] 18:38 (service date 2026-10-10, trip `45520101_031026`)
5. Walk 9 min, 593 m: קריית הממשלה/העצמאות 18:38 -> END 18:47

Transfers (alight to next boarding, including any walk): צומת השומרים -> צומת השומרים: 18 min

**Option 3:** departs Sat 2026-10-10 16:45, arrives Sat 2026-10-10 18:45; total 120 min, 2 transfer(s), walking 17 min / 1042 m

1. Walk 6 min, 431 m: START 16:45 -> ת. רכבת תל אביב - סבידור/דרך נמיר 16:51
2. **bus 825** (אגד) toward עפולה_תחנה מרכזית: board ת. רכבת תל אביב - סבידור/דרך נמיר [code 24068] 16:51 -> alight צומת אולגה [code 41694] 17:28 (service date 2026-10-10, trip `25275451_021026`)
3. Walk 2 min, 0 m: צומת אולגה 17:42 -> צומת אולגה 17:44
4. **bus 947** (אגד) toward חיפה_מרכזית חוף הכרמל: board צומת אולגה [code 41694] 17:44 -> alight מת''מ [code 42656] 18:17 (service date 2026-10-10, trip `584672084_041026`)
5. Walk 2 min, 173 m: מת''מ 18:17 -> מת''מ 18:19
6. **bus 245** (אגד) toward חיפה_שוק תלפיות: board מת''מ [code 42229] 18:22 -> alight המגינים/ככר ההגנה [code 42723] 18:38 (service date 2026-10-10, trip `585108128_031026`)
7. Walk 7 min, 438 m: המגינים/ככר ההגנה 18:38 -> END 18:45

Transfers (alight to next boarding, including any walk): צומת אולגה -> צומת אולגה: 16 min; מת''מ -> מת''מ: 5 min

| Usable? (Y/N) | Notes | Compared against / when checked |
|---|---|---|
|  |  |  |

---

## J05-SAT — Mahane Yehuda Market (שוק מחנה יהודה) → Mount Herzl (הר הרצל)

category `jerusalem-urban-light-rail` · calendar rule `shabbat`

Calendar variant of J05: Saturday noon: Jerusalem urban case.

**Requested:** Depart at Sat 2026-10-10 12:00 (UTC+03:00)  
Request field: `departAt=2026-10-10T12:00:00+03:00`
**Calendar flags:** Shabbat
**Compare:** [Google Maps transit](https://www.google.com/maps/dir/?api=1&origin=31.7853,35.2124&destination=31.7736,35.1806&travelmode=transit) · [Moovit (unofficial deep link; may not prefill)](https://moovitapp.com/?fll=31.7853_35.2124&tll=31.7736_35.1806&from=Mahane%20Yehuda%20Market&to=Mount%20Herzl) · Set the time yourself to **Depart at 12:00, Sat 2026-10-10** (Google's documented URL has no time parameter).
**Corpus expectation (context, not a verdict):** outcome `route`, max_duration_min = 45, max_transfers = 1, min_duration_min = 8, modes_any_of = ['light_rail', 'bus']

> What to check: This is the light rail's spine. If it routes by bus instead, something is wrong.

**API RESULT: 3 journey option(s) returned** (scheduled times).
Machine note: matches the corpus expectation `route`. This is not a judgement of quality.
Request id `12fd9c515c2f43249ded1f0a700481f3`.

**Option 1:** departs Sat 2026-10-10 19:38, arrives Sat 2026-10-10 20:03; total 25 min, 0 transfer(s), walking 11 min / 706 m

1. Walk 2 min, 145 m: START 19:38 -> מחנה יהודה 19:40
2. **light_rail 1** (כפיר) toward הדסה עין כרם: board מחנה יהודה [code 6172] 19:40 -> alight הר הרצל [code 6185] 19:54 (service date 2026-10-10, trip `586038333_021026`)
3. Walk 9 min, 561 m: הר הרצל 19:54 -> END 20:03

Transfers (alight to next boarding, including any walk): none

**Option 2:** departs Sat 2026-10-10 19:47, arrives Sat 2026-10-10 20:12; total 25 min, 0 transfer(s), walking 11 min / 706 m

1. Walk 2 min, 145 m: START 19:47 -> מחנה יהודה 19:49
2. **light_rail 1** (כפיר) toward הדסה עין כרם: board מחנה יהודה [code 6172] 19:49 -> alight הר הרצל [code 6185] 20:03 (service date 2026-10-10, trip `586269288_021026`)
3. Walk 9 min, 561 m: הר הרצל 20:03 -> END 20:12

Transfers (alight to next boarding, including any walk): none

**Option 3:** departs Sat 2026-10-10 19:56, arrives Sat 2026-10-10 20:21; total 25 min, 0 transfer(s), walking 11 min / 706 m

1. Walk 2 min, 145 m: START 19:56 -> מחנה יהודה 19:58
2. **light_rail 1** (כפיר) toward הדסה עין כרם: board מחנה יהודה [code 6172] 19:58 -> alight הר הרצל [code 6185] 20:12 (service date 2026-10-10, trip `586262221_021026`)
3. Walk 9 min, 561 m: הר הרצל 20:12 -> END 20:21

Transfers (alight to next boarding, including any walk): none

| Usable? (Y/N) | Notes | Compared against / when checked |
|---|---|---|
|  |  |  |

---

## J01-HOL — Dizengoff Center (דיזנגוף סנטר) → Ramat Gan Bursa (רמת גן בורסה)

category `tel-aviv-urban-bus` · calendar rule `holiday_morning`

Calendar variant of J01: Israeli holiday timetable, morning.

**Requested:** Depart at Thu 2026-10-01 08:00 (UTC+03:00)  
Request field: `departAt=2026-10-01T08:00:00+03:00`
**Calendar flags:** Holiday calendar: Chol HaMoed Sukkot (chol_hamoed)
**Compare:** [Google Maps transit](https://www.google.com/maps/dir/?api=1&origin=32.0757,34.7748&destination=32.0838,34.8044&travelmode=transit) · [Moovit (unofficial deep link; may not prefill)](https://moovitapp.com/?fll=32.0757_34.7748&tll=32.0838_34.8044&from=Dizengoff%20Center&to=Ramat%20Gan%20Bursa) · Set the time yourself to **Depart at 08:00, Thu 2026-10-01** (Google's documented URL has no time parameter).
**Corpus expectation (context, not a verdict):** outcome `route`, max_duration_min = 55, max_transfers = 2, min_duration_min = 10, modes_any_of = ['bus', 'light_rail']

> What to check: Would a Tel Aviv resident actually take this? Compare against Moovit.

**API RESULT: 3 journey option(s) returned** (scheduled times).
Machine note: matches the corpus expectation `route`. This is not a judgement of quality.
Request id `9c8ffe45f42c42adb14b3b52a9d9b9ae`.

**Option 1:** departs Thu 2026-10-01 08:00, arrives Thu 2026-10-01 08:19; total 19 min, 1 transfer(s), walking 11 min / 543 m

1. Walk 5 min, 294 m: START 08:00 -> דיזנגוף סנטר/המלך ג'ורג' 08:05
2. **bus 14** (דן) toward תל אביב יפו_בבלי: board דיזנגוף סנטר/המלך ג'ורג' [code 20785] 08:05 -> alight לונדון מיניסטור/שד' שאול המלך [code 21100] 08:07 (service date 2026-10-01, trip `37731542_011026`)
3. Walk 2 min, 0 m: לונדון מיניסטור/שד' שאול המלך 08:07 -> לונדון מיניסטור/שד' שאול המלך 08:09
4. **bus 142** (דן) toward תל אביב יפו_קריית עתידים: board לונדון מיניסטור/שד' שאול המלך [code 21100] 08:09 -> alight ת.רק''ל אבא הלל [code 26248] 08:15 (service date 2026-10-01, trip `4083282_011026`)
5. Walk 4 min, 249 m: ת.רק''ל אבא הלל 08:15 -> END 08:19

Transfers (alight to next boarding, including any walk): לונדון מיניסטור/שד' שאול המלך -> לונדון מיניסטור/שד' שאול המלך: 2 min

**Option 2:** departs Thu 2026-10-01 08:02, arrives Thu 2026-10-01 08:21; total 19 min, 0 transfer(s), walking 7 min / 384 m

1. Walk 3 min, 135 m: START 08:02 -> דיזנגוף סנטר/דיזנגוף 08:05
2. **bus 238** (דן) toward פתח תקווה_הדר גנים: board דיזנגוף סנטר/דיזנגוף [code 25565] 08:05 -> alight ת.רק''ל אבא הלל [code 26248] 08:17 (service date 2026-10-01, trip `585292502_011026`)
3. Walk 4 min, 249 m: ת.רק''ל אבא הלל 08:17 -> END 08:21

Transfers (alight to next boarding, including any walk): none

**Option 3:** departs Thu 2026-10-01 08:06, arrives Thu 2026-10-01 08:24; total 18 min, 0 transfer(s), walking 9 min / 534 m

1. Walk 5 min, 294 m: START 08:06 -> דיזנגוף סנטר/המלך ג'ורג' 08:11
2. **bus 82** (דן) toward פתח תקווה_בית רבקה: board דיזנגוף סנטר/המלך ג'ורג' [code 20785] 08:11 -> alight ת.רק''ל אבא הלל/דרך ז'בוטינסקי [code 21644] 08:20 (service date 2026-10-01, trip `503015_011026`)
3. Walk 4 min, 240 m: ת.רק''ל אבא הלל/דרך ז'בוטינסקי 08:20 -> END 08:24

Transfers (alight to next boarding, including any walk): none

| Usable? (Y/N) | Notes | Compared against / when checked |
|---|---|---|
|  |  |  |

---

## J12-HOL — Tel Aviv Savidor Center (תל אביב סבידור מרכז) → Yitzhak Navon Station (תחנת יצחק נבון)

category `intercity-rail` · calendar rule `holiday_midday`

Calendar variant of J12: Israeli holiday timetable, midday intercity.

**Requested:** Depart at Thu 2026-10-01 13:00 (UTC+03:00)  
Request field: `departAt=2026-10-01T13:00:00+03:00`
**Calendar flags:** Holiday calendar: Chol HaMoed Sukkot (chol_hamoed)
**Compare:** [Google Maps transit](https://www.google.com/maps/dir/?api=1&origin=32.0836,34.7981&destination=31.7888,35.2027&travelmode=transit) · [Moovit (unofficial deep link; may not prefill)](https://moovitapp.com/?fll=32.0836_34.7981&tll=31.7888_35.2027&from=Tel%20Aviv%20Savidor%20Center&to=Yitzhak%20Navon%20Station) · Set the time yourself to **Depart at 13:00, Thu 2026-10-01** (Google's documented URL has no time parameter).
**Corpus expectation (context, not a verdict):** outcome `route`, max_duration_min = 110, max_transfers = 1, min_duration_min = 30, modes_any_of = ['rail']

> What to check: Fast line. If it routes by bus, the rail calendar is probably misread.

**API RESULT: 3 journey option(s) returned** (scheduled times).
Machine note: matches the corpus expectation `route`. This is not a judgement of quality.
Request id `c493fe1903e9416fb2ec0e9a043f1dce`.

**Option 1:** departs Thu 2026-10-01 13:04, arrives Thu 2026-10-01 13:55; total 51 min, 0 transfer(s), walking 4 min / 207 m

1. Walk 1 min, 27 m: START 13:04 -> תל אביב מרכז 13:05
2. **rail ** (רכבת ישראל) toward 743: board תל אביב מרכז [code 17038] 13:05 -> alight ירושלים/יצחק נבון [code 17118] 13:52 (service date 2026-10-01, trip `1_520881`)
3. Walk 3 min, 180 m: ירושלים/יצחק נבון 13:52 -> END 13:55

Transfers (alight to next boarding, including any walk): none

**Option 2:** departs Thu 2026-10-01 13:14, arrives Thu 2026-10-01 14:09; total 55 min, 0 transfer(s), walking 11 min / 710 m

1. Walk 6 min, 403 m: START 13:14 -> ת.רכבת תל אביב - סבידור/רציפים B 13:20
2. **bus 480** (אגד) toward ירושלים_תחנה מרכזית: board ת.רכבת תל אביב - סבידור/רציפים B [code 20740] 13:20 -> alight ת. מרכזית ירושלים/הורדה [code 6109] 14:04 (service date 2026-10-01, trip `3995594_011026`)
3. Walk 5 min, 307 m: ת. מרכזית ירושלים/הורדה 14:04 -> END 14:09

Transfers (alight to next boarding, including any walk): none

**Option 3:** departs Thu 2026-10-01 13:34, arrives Thu 2026-10-01 14:25; total 51 min, 0 transfer(s), walking 4 min / 207 m

1. Walk 1 min, 27 m: START 13:34 -> תל אביב מרכז 13:35
2. **rail ** (רכבת ישראל) toward 745: board תל אביב מרכז [code 17038] 13:35 -> alight ירושלים/יצחק נבון [code 17118] 14:22 (service date 2026-10-01, trip `1_520944`)
3. Walk 3 min, 180 m: ירושלים/יצחק נבון 14:22 -> END 14:25

Transfers (alight to next boarding, including any walk): none

| Usable? (Y/N) | Notes | Compared against / when checked |
|---|---|---|
|  |  |  |

---

## J01-DST — Dizengoff Center (דיזנגוף סנטר) → Ramat Gan Bursa (רמת גן בורסה)

category `tel-aviv-urban-bus` · calendar rule `dst_day_peak`

Calendar variant of J01: Peak on the DST fall-back day.

**Requested:** Depart at Sun 2026-10-25 08:00 (UTC+02:00)  
Request field: `departAt=2026-10-25T08:00:00+02:00`
**Calendar flags:** DST fall-back day: clocks go back 02:00 to 01:00
**Compare:** [Google Maps transit](https://www.google.com/maps/dir/?api=1&origin=32.0757,34.7748&destination=32.0838,34.8044&travelmode=transit) · [Moovit (unofficial deep link; may not prefill)](https://moovitapp.com/?fll=32.0757_34.7748&tll=32.0838_34.8044&from=Dizengoff%20Center&to=Ramat%20Gan%20Bursa) · Set the time yourself to **Depart at 08:00, Sun 2026-10-25** (Google's documented URL has no time parameter).
**Corpus expectation (context, not a verdict):** outcome `route`, max_duration_min = 55, max_transfers = 2, min_duration_min = 10, modes_any_of = ['bus', 'light_rail']

> What to check: Would a Tel Aviv resident actually take this? Compare against Moovit.

**API RESULT: 3 journey option(s) returned** (scheduled times).
Machine note: matches the corpus expectation `route`. This is not a judgement of quality.
Request id `585f23e7c59143caa589dbf8a0c9116a`.

**Option 1:** departs Sun 2026-10-25 08:06(+02:00), arrives Sun 2026-10-25 08:24(+02:00); total 18 min, 0 transfer(s), walking 9 min / 534 m

1. Walk 5 min, 294 m: START 08:06(+02:00) -> דיזנגוף סנטר/המלך ג'ורג' 08:11(+02:00)
2. **bus 82** (דן) toward פתח תקווה_בית רבקה: board דיזנגוף סנטר/המלך ג'ורג' [code 20785] 08:11(+02:00) -> alight ת.רק''ל אבא הלל/דרך ז'בוטינסקי [code 21644] 08:20(+02:00) (service date 2026-10-25, trip `503015_081026`)
3. Walk 4 min, 240 m: ת.רק''ל אבא הלל/דרך ז'בוטינסקי 08:20(+02:00) -> END 08:24(+02:00)

Transfers (alight to next boarding, including any walk): none

**Option 2:** departs Sun 2026-10-25 08:14(+02:00), arrives Sun 2026-10-25 08:33(+02:00); total 19 min, 0 transfer(s), walking 7 min / 384 m

1. Walk 3 min, 135 m: START 08:14(+02:00) -> דיזנגוף סנטר/דיזנגוף 08:17(+02:00)
2. **bus 238** (דן) toward פתח תקווה_הדר גנים: board דיזנגוף סנטר/דיזנגוף [code 25565] 08:17(+02:00) -> alight ת.רק''ל אבא הלל [code 26248] 08:29(+02:00) (service date 2026-10-25, trip `46017616_081026`)
3. Walk 4 min, 249 m: ת.רק''ל אבא הלל 08:29(+02:00) -> END 08:33(+02:00)

Transfers (alight to next boarding, including any walk): none

**Option 3:** departs Sun 2026-10-25 08:17(+02:00), arrives Sun 2026-10-25 08:35(+02:00); total 18 min, 0 transfer(s), walking 9 min / 534 m

1. Walk 5 min, 294 m: START 08:17(+02:00) -> דיזנגוף סנטר/המלך ג'ורג' 08:22(+02:00)
2. **bus 82** (דן) toward פתח תקווה_בית רבקה: board דיזנגוף סנטר/המלך ג'ורג' [code 20785] 08:22(+02:00) -> alight ת.רק''ל אבא הלל/דרך ז'בוטינסקי [code 21644] 08:31(+02:00) (service date 2026-10-25, trip `631281_081026`)
3. Walk 4 min, 240 m: ת.רק''ל אבא הלל/דרך ז'בוטינסקי 08:31(+02:00) -> END 08:35(+02:00)

Transfers (alight to next boarding, including any walk): none

| Usable? (Y/N) | Notes | Compared against / when checked |
|---|---|---|
|  |  |  |

---

## J22-DST1 — Dizengoff Center (דיזנגוף סנטר) → Ramat Gan Bursa (רמת גן בורסה)

category `service-day-boundary` · calendar rule `dst_repeat_first`

Calendar variant of J22: Repeated hour, first occurrence (earlier offset).

**Requested:** Depart at Sun 2026-10-25 01:30 (UTC+03:00)  
Request field: `departAt=2026-10-25T01:30:00+03:00`
**Calendar flags:** DST fall-back day: clocks go back 02:00 to 01:00
**Compare:** [Google Maps transit](https://www.google.com/maps/dir/?api=1&origin=32.0757,34.7748&destination=32.0838,34.8044&travelmode=transit) · [Moovit (unofficial deep link; may not prefill)](https://moovitapp.com/?fll=32.0757_34.7748&tll=32.0838_34.8044&from=Dizengoff%20Center&to=Ramat%20Gan%20Bursa) · Set the time yourself to **Depart at 01:30, Sun 2026-10-25** (Google's documented URL has no time parameter).
**Corpus expectation (context, not a verdict):** outcome `either`, max_duration_min = 180, min_duration_min = 5

> What to check: THE GTFS trap: trips after midnight belong to the previous service day with times like 25:30:00. Either a valid night route or a clean no-route is acceptable. A crash, an empty result with no explanation, or a route departing 20 hours later is a FAIL.

**API RESULT: 3 journey option(s) returned** (scheduled times).
Request id `e0a76f3ee5034d188111d6156fcf5212`.

**Option 1:** departs Sun 2026-10-25 01:30(+03:00), arrives Sun 2026-10-25 01:59(+03:00); total 29 min, 0 transfer(s), walking 18 min / 1116 m

1. Walk 3 min, 136 m: START 01:30(+03:00) -> דיזנגוף סנטר/טשרניחובסקי 01:33(+03:00)
2. **bus 18** (דן) toward תל אביב יפו_רכבת מרכז: board דיזנגוף סנטר/טשרניחובסקי [code 25564] 01:33(+03:00) -> alight ת. רכבת תל אביב - סבידור/הורדה [code 27997] 01:44(+03:00) (service date 2026-10-25, trip `473458_081026`)
3. Walk 15 min, 980 m: ת. רכבת תל אביב - סבידור/הורדה 01:44(+03:00) -> END 01:59(+03:00)

Transfers (alight to next boarding, including any walk): none

**Option 2:** departs Sun 2026-10-25 01:30(+03:00), arrives Sun 2026-10-25 01:52(+03:00); total 22 min, 1 transfer(s), walking 9 min / 385 m

1. Walk 3 min, 136 m: START 01:30(+03:00) -> דיזנגוף סנטר/טשרניחובסקי 01:33(+03:00)
2. **bus 18** (דן) toward תל אביב יפו_רכבת מרכז: board דיזנגוף סנטר/טשרניחובסקי [code 25564] 01:33(+03:00) -> alight בית הדר דפנה/שד' שאול המלך [code 21303] 01:41(+03:00) (service date 2026-10-25, trip `473458_081026`)
3. Walk 2 min, 0 m: בית הדר דפנה/שד' שאול המלך 01:41(+03:00) -> בית הדר דפנה/שד' שאול המלך 01:43(+03:00)
4. **bus 142** (דן) toward תל אביב יפו_קריית עתידים: board בית הדר דפנה/שד' שאול המלך [code 21303] 01:44(+03:00) -> alight ת.רק''ל אבא הלל [code 26248] 01:48(+03:00) (service date 2026-10-25, trip `585168278_081026`)
5. Walk 4 min, 249 m: ת.רק''ל אבא הלל 01:48(+03:00) -> END 01:52(+03:00)

Transfers (alight to next boarding, including any walk): בית הדר דפנה/שד' שאול המלך -> בית הדר דפנה/שד' שאול המלך: 3 min

**Option 3:** departs Sun 2026-10-25 01:37(+03:00), arrives Sun 2026-10-25 01:01(+02:00); total 24 min, 0 transfer(s), walking 11 min / 600 m

1. Walk 3 min, 136 m: START 01:37(+03:00) -> דיזנגוף סנטר/טשרניחובסקי 01:40(+03:00)
2. **bus 61** (דן) toward רמת גן_מסוף עמידר: board דיזנגוף סנטר/טשרניחובסקי [code 25564] 01:40(+03:00) -> alight הבורסה/דרך ז'בוטינסקי [code 28665] 01:53(+03:00) (service date 2026-10-25, trip `584712056_081026`)
3. Walk 8 min, 464 m: הבורסה/דרך ז'בוטינסקי 01:53(+03:00) -> END 01:01(+02:00)

Transfers (alight to next boarding, including any walk): none

| Usable? (Y/N) | Notes | Compared against / when checked |
|---|---|---|
|  |  |  |

---

## J22-DST2 — Dizengoff Center (דיזנגוף סנטר) → Ramat Gan Bursa (רמת גן בורסה)

category `service-day-boundary` · calendar rule `dst_repeat_second`

Calendar variant of J22: Repeated hour, second occurrence (later offset).

**Requested:** Depart at Sun 2026-10-25 01:30 (UTC+02:00)  
Request field: `departAt=2026-10-25T01:30:00+02:00`
**Calendar flags:** DST fall-back day: clocks go back 02:00 to 01:00
**Compare:** [Google Maps transit](https://www.google.com/maps/dir/?api=1&origin=32.0757,34.7748&destination=32.0838,34.8044&travelmode=transit) · [Moovit (unofficial deep link; may not prefill)](https://moovitapp.com/?fll=32.0757_34.7748&tll=32.0838_34.8044&from=Dizengoff%20Center&to=Ramat%20Gan%20Bursa) · Set the time yourself to **Depart at 01:30, Sun 2026-10-25** (Google's documented URL has no time parameter).
**Corpus expectation (context, not a verdict):** outcome `either`, max_duration_min = 180, min_duration_min = 5

> What to check: THE GTFS trap: trips after midnight belong to the previous service day with times like 25:30:00. Either a valid night route or a clean no-route is acceptable. A crash, an empty result with no explanation, or a route departing 20 hours later is a FAIL.

**API RESULT: 3 journey option(s) returned** (scheduled times).
Request id `c6ad6899dd0145dd92b03845f81533ba`.

**Option 1:** departs Sun 2026-10-25 01:42(+02:00), arrives Sun 2026-10-25 02:20(+02:00); total 38 min, 0 transfer(s), walking 26 min / 1536 m

1. Walk 14 min, 828 m: START 01:42(+02:00) -> אבן גבירול/השופטים 01:56(+02:00)
2. **bus 425** (אגד) toward תל אביב יפו_קריית עתידים: board אבן גבירול/השופטים [code 25631] 01:56(+02:00) -> alight ביאליק/תובל [code 21197] 02:08(+02:00) (service date 2026-10-25, trip `6707125_021026`)
3. Walk 12 min, 708 m: ביאליק/תובל 02:08(+02:00) -> END 02:20(+02:00)

Transfers (alight to next boarding, including any walk): none

**Option 2:** departs Sun 2026-10-25 01:53(+02:00), arrives Sun 2026-10-25 02:30(+02:00); total 37 min, 1 transfer(s), walking 18 min / 1275 m

1. Walk 12 min, 784 m: START 01:53(+02:00) -> הבימה/שד' בן ציון 02:05(+02:00)
2. **bus 425** (אגד) toward ראשון לציון_נוה חוף: board הבימה/שד' בן ציון [code 25621] 02:05(+02:00) -> alight חברת החשמל/דרך מנחם בגין [code 21376] 02:11(+02:00) (service date 2026-10-25, trip `6707119_021026`)
3. Walk 2 min, 251 m: חברת החשמל/דרך מנחם בגין 02:11(+02:00) -> דרך מנחם בגין/הגליל 02:13(+02:00)
4. **bus 1** (דן) toward פתח תקווה_מסוף משה ארנס: board דרך מנחם בגין/הגליל [code 21502] 02:16(+02:00) -> alight ת.רק''ל אבא הלל/דרך ז'בוטינסקי [code 21644] 02:26(+02:00) (service date 2026-10-25, trip `585413087_081026`)
5. Walk 4 min, 240 m: ת.רק''ל אבא הלל/דרך ז'בוטינסקי 02:26(+02:00) -> END 02:30(+02:00)

Transfers (alight to next boarding, including any walk): חברת החשמל/דרך מנחם בגין -> דרך מנחם בגין/הגליל: 5 min

**Option 3:** departs Sun 2026-10-25 02:12(+02:00), arrives Sun 2026-10-25 02:50(+02:00); total 38 min, 0 transfer(s), walking 26 min / 1536 m

1. Walk 14 min, 828 m: START 02:12(+02:00) -> אבן גבירול/השופטים 02:26(+02:00)
2. **bus 425** (אגד) toward תל אביב יפו_קריית עתידים: board אבן גבירול/השופטים [code 25631] 02:26(+02:00) -> alight ביאליק/תובל [code 21197] 02:38(+02:00) (service date 2026-10-25, trip `6707126_021026`)
3. Walk 12 min, 708 m: ביאליק/תובל 02:38(+02:00) -> END 02:50(+02:00)

Transfers (alight to next boarding, including any walk): none

| Usable? (Y/N) | Notes | Compared against / when checked |
|---|---|---|
|  |  |  |

---
