# H3 route-review sheet — through the API (POST /v1/journeys)

> **Scheduled only; realtime not enabled.** Times are MOT timetable times. No delay, prediction or alert is shown.

**You are the reviewer.** Everything machine-made below is context. Fill only the `Usable? (Y/N)` and `Notes` cells yourself, comparing with Google Maps, Moovit or BetterRail at the stated date and time. The generator never writes a verdict. Release gate: at least **9 of the 10 required journeys** judged usable.

## Generation

- Generation id: `2d8ec2746bb500abacd0f383316d23616fcf1dc4b3e20104b14c2cb139aad445` (mode `real`, freshness `current`)
- Data built: 2026-10-31T12:18:07.213453Z
- Coverage window (half-open, as reported by the API): 2026-10-31T00:00:00+02:00 .. 2026-11-30T00:00:00+02:00
- Window used for dates: 2026-10-31 00:00 .. 2026-11-30 00:00 Asia/Jerusalem; earliest request instant 2026-10-31 00:00
- Capabilities reported: realtime `not_enabled`, alerts `not_enabled`
- Generated 2026-10-31T12:56:25Z (2026-10-31 14:56 Israel) against `http://127.0.0.1:8500`
- Corpus `poc/corpora/journeys.json` sha256 `5fc013a5e1c52f16…`; case IDs are the PoC IDs. Coordinates are the corpus's approximate hand-entered points; the API plans from them.
- Request options: lang `he`, results 3, walking limits API defaults, arrive-by variants off
- Raw requests and responses: `acceptance-oct31a-20261031-01-h3-review-raw.json`

## Required ten — your tally

| # | Case | Requested | Usable? (Y/N) |
|---|---|---|---|
| 1 | J01 | Mon 2026-11-02 08:00 (UTC+02:00) | |
| 2 | J04 | Wed 2026-11-04 18:30 (UTC+02:00) | |
| 3 | J11 | Mon 2026-11-02 08:00 (UTC+02:00) | |
| 4 | J12 | Mon 2026-11-02 08:00 (UTC+02:00) | |
| 5 | J15 | Mon 2026-11-02 08:00 (UTC+02:00) | |
| 6 | J16 | Mon 2026-11-02 08:00 (UTC+02:00) | |
| 7 | J19 | Mon 2026-11-02 08:00 (UTC+02:00) | |
| 8 | J21 | Tue 2026-11-03 23:40 (UTC+02:00) | |
| 9 | J22 | Wed 2026-11-04 02:30 (UTC+02:00) | |
| 10 | J23 | Wed 2026-11-04 02:30 (UTC+02:00) | |

Total usable: ____ / 10

## Date selection

| Case | Rule | Requested (Asia/Jerusalem) | Calendar flags |
|---|---|---|---|
| J01 | weekday_morning | depart Mon 2026-11-02 08:00 (UTC+02:00) | ordinary day |
| J02 | weekday_morning | depart Mon 2026-11-02 08:00 (UTC+02:00) | ordinary day |
| J03 | weekday_midday | depart Tue 2026-11-03 13:00 (UTC+02:00) | ordinary day |
| J04 | weekday_evening | depart Wed 2026-11-04 18:30 (UTC+02:00) | ordinary day |
| J05 | weekday_midday | depart Tue 2026-11-03 13:00 (UTC+02:00) | ordinary day |
| J06 | weekday_morning | depart Mon 2026-11-02 08:00 (UTC+02:00) | ordinary day |
| J07 | weekday_evening | depart Wed 2026-11-04 18:30 (UTC+02:00) | ordinary day |
| J08 | weekday_morning | depart Mon 2026-11-02 08:00 (UTC+02:00) | ordinary day |
| J09 | weekday_evening | depart Wed 2026-11-04 18:30 (UTC+02:00) | ordinary day |
| J10 | weekday_midday | depart Tue 2026-11-03 13:00 (UTC+02:00) | ordinary day |
| J11 | weekday_morning | depart Mon 2026-11-02 08:00 (UTC+02:00) | ordinary day |
| J12 | weekday_morning | depart Mon 2026-11-02 08:00 (UTC+02:00) | ordinary day |
| J13 | weekday_midday | depart Tue 2026-11-03 13:00 (UTC+02:00) | ordinary day |
| J14 | weekday_morning | depart Mon 2026-11-02 08:00 (UTC+02:00) | ordinary day |
| J15 | weekday_morning | depart Mon 2026-11-02 08:00 (UTC+02:00) | ordinary day |
| J16 | weekday_morning | depart Mon 2026-11-02 08:00 (UTC+02:00) | ordinary day |
| J17 | weekday_morning | depart Mon 2026-11-02 08:00 (UTC+02:00) | ordinary day |
| J18 | weekday_morning | depart Mon 2026-11-02 08:00 (UTC+02:00) | ordinary day |
| J19 | weekday_morning | depart Mon 2026-11-02 08:00 (UTC+02:00) | ordinary day |
| J20 | weekday_midday | depart Tue 2026-11-03 13:00 (UTC+02:00) | ordinary day |
| J21 | late_night | depart Tue 2026-11-03 23:40 (UTC+02:00) | ordinary day |
| J22 | after_midnight | depart Wed 2026-11-04 02:30 (UTC+02:00) | ordinary day |
| J23 | after_midnight | depart Wed 2026-11-04 02:30 (UTC+02:00) | ordinary day |
| J24 | weekday_midday | depart Tue 2026-11-03 13:00 (UTC+02:00) | ordinary day |
| J25 | shabbat | depart Sat 2026-10-31 12:00 (UTC+02:00) | Shabbat |
| J11-FRI | friday_afternoon | depart Fri 2026-11-06 15:30 (UTC+02:00) | Friday (erev Shabbat) |
| J12-FRI | friday_afternoon | depart Fri 2026-11-06 15:30 (UTC+02:00) | Friday (erev Shabbat) |
| J11-SAT | shabbat | depart Sat 2026-10-31 12:00 (UTC+02:00) | Shabbat |
| J05-SAT | shabbat | depart Sat 2026-10-31 12:00 (UTC+02:00) | Shabbat |
| J01-HOL | holiday_morning | OMITTED: no Israeli holiday date (non-Shabbat) from the holiday table in the usable range 2026-10-31 00:00 .. 2026-11-30 00:00 (Asia/Jerusalem) |  |
| J12-HOL | holiday_midday | OMITTED: no Israeli holiday date (non-Shabbat) from the holiday table in the usable range 2026-10-31 00:00 .. 2026-11-30 00:00 (Asia/Jerusalem) |  |
| J01-DST | dst_day_peak | OMITTED: no DST fall-back day in the usable range 2026-10-31 00:00 .. 2026-11-30 00:00 (Asia/Jerusalem) |  |
| J22-DST1 | dst_repeat_first | OMITTED: no repeated-hour instant in the usable range 2026-10-31 00:00 .. 2026-11-30 00:00 (Asia/Jerusalem) |  |
| J22-DST2 | dst_repeat_second | OMITTED: no repeated-hour instant in the usable range 2026-10-31 00:00 .. 2026-11-30 00:00 (Asia/Jerusalem) |  |

**Not covered by this sheet:** J01-HOL, J12-HOL, J01-DST, J22-DST1, J22-DST2

Holiday dates come from a built-in 2026 table and any `--holiday` overrides; verify them against the official calendar. Cases marked Shabbat, Friday, holiday or DST are deliberately unusual: no or reduced service can be correct there.

---

## J01 — Dizengoff Center (דיזנגוף סנטר) → Ramat Gan Bursa (רמת גן בורסה)

**Required journey #1** — PRD §7 #1 Tel Aviv → Ramat Gan · category `tel-aviv-urban-bus` · calendar rule `weekday_morning`

**Requested:** Depart at Mon 2026-11-02 08:00 (UTC+02:00)  
Request field: `departAt=2026-11-02T08:00:00+02:00`
**Calendar flags:** ordinary day
**Compare:** [Google Maps transit](https://www.google.com/maps/dir/?api=1&origin=32.0757,34.7748&destination=32.0838,34.8044&travelmode=transit) · [Moovit (unofficial deep link; may not prefill)](https://moovitapp.com/?fll=32.0757_34.7748&tll=32.0838_34.8044&from=Dizengoff%20Center&to=Ramat%20Gan%20Bursa) · Set the time yourself to **Depart at 08:00, Mon 2026-11-02** (Google's documented URL has no time parameter).
**Corpus expectation (context, not a verdict):** outcome `route`, max_duration_min = 55, max_transfers = 2, min_duration_min = 10, modes_any_of = ['bus', 'light_rail']

> What to check: Would a Tel Aviv resident actually take this? Compare against Moovit.

**API RESULT: 3 journey option(s) returned** (scheduled times).
Machine note: matches the corpus expectation `route`. This is not a judgement of quality.
Request id `ed6cba0515cd4e1f8ffe6bf7d8200ddc`.

**Option 1:** departs Mon 2026-11-02 08:06, arrives Mon 2026-11-02 08:25; total 19 min, 0 transfer(s), walking 10 min / 535 m

1. Walk 5 min, 294 m: START 08:06 -> דיזנגוף סנטר/המלך ג'ורג' 08:11
2. **bus 82** (דן) toward פתח תקווה_בית רבקה: board דיזנגוף סנטר/המלך ג'ורג' [code 20785] 08:11 -> alight ת.רק''ל אבא הלל/דרך ז'בוטינסקי [code 21644] 08:20 (service date 2026-11-02, trip `503015_011126`)
3. Walk 5 min, 241 m: ת.רק''ל אבא הלל/דרך ז'בוטינסקי 08:20 -> END 08:25

Transfers (alight to next boarding, including any walk): none

**Option 2:** departs Mon 2026-11-02 08:14, arrives Mon 2026-11-02 08:33; total 19 min, 0 transfer(s), walking 7 min / 384 m

1. Walk 3 min, 135 m: START 08:14 -> דיזנגוף סנטר/דיזנגוף 08:17
2. **bus 238** (דן) toward פתח תקווה_הדר גנים: board דיזנגוף סנטר/דיזנגוף [code 25565] 08:17 -> alight ת.רק''ל אבא הלל [code 26248] 08:29 (service date 2026-11-02, trip `46017616_011126`)
3. Walk 4 min, 249 m: ת.רק''ל אבא הלל 08:29 -> END 08:33

Transfers (alight to next boarding, including any walk): none

**Option 3:** departs Mon 2026-11-02 08:15, arrives Mon 2026-11-02 08:35; total 20 min, 1 transfer(s), walking 11 min / 543 m

1. Walk 5 min, 294 m: START 08:15 -> דיזנגוף סנטר/המלך ג'ורג' 08:20
2. **bus 14** (דן) toward תל אביב יפו_בבלי: board דיזנגוף סנטר/המלך ג'ורג' [code 20785] 08:20 -> alight לונדון מיניסטור/שד' שאול המלך [code 21100] 08:22 (service date 2026-11-02, trip `468334_011126`)
3. Walk 2 min, 0 m: לונדון מיניסטור/שד' שאול המלך 08:22 -> לונדון מיניסטור/שד' שאול המלך 08:24
4. **bus 142** (דן) toward תל אביב יפו_קריית עתידים: board לונדון מיניסטור/שד' שאול המלך [code 21100] 08:25 -> alight ת.רק''ל אבא הלל [code 26248] 08:31 (service date 2026-11-02, trip `14081118_011126`)
5. Walk 4 min, 249 m: ת.רק''ל אבא הלל 08:31 -> END 08:35

Transfers (alight to next boarding, including any walk): לונדון מיניסטור/שד' שאול המלך -> לונדון מיניסטור/שד' שאול המלך: 3 min

| Usable? (Y/N) | Notes | Compared against / when checked |
|---|---|---|
|  |  |  |

---

## J02 — Tel Aviv University (אוניברסיטת תל אביב) → Sourasky Medical Center (Ichilov) (בית חולים איכילוב)

category `tel-aviv-urban-bus` · calendar rule `weekday_morning`

**Requested:** Depart at Mon 2026-11-02 08:00 (UTC+02:00)  
Request field: `departAt=2026-11-02T08:00:00+02:00`
**Calendar flags:** ordinary day
**Compare:** [Google Maps transit](https://www.google.com/maps/dir/?api=1&origin=32.1133,34.8044&destination=32.08,34.79&travelmode=transit) · [Moovit (unofficial deep link; may not prefill)](https://moovitapp.com/?fll=32.1133_34.8044&tll=32.08_34.79&from=Tel%20Aviv%20University&to=Sourasky%20Medical%20Center%20%28Ichilov%29) · Set the time yourself to **Depart at 08:00, Mon 2026-11-02** (Google's documented URL has no time parameter).
**Corpus expectation (context, not a verdict):** outcome `route`, max_duration_min = 60, max_transfers = 2, min_duration_min = 12, modes_any_of = ['bus', 'light_rail', 'rail']

> What to check: Peak-hour campus-to-hospital trip. Is the walk at either end reasonable?

**API RESULT: 3 journey option(s) returned** (scheduled times).
Machine note: matches the corpus expectation `route`. This is not a judgement of quality.
Request id `9841f3d5eb0147b694367ea6dbbdf24d`.

**Option 1:** departs Mon 2026-11-02 08:00, arrives Mon 2026-11-02 08:26; total 26 min, 1 transfer(s), walking 13 min / 664 m

1. Walk 6 min, 389 m: START 08:00 -> האוניברסיטה/חיים לבנון 08:06
2. **bus 24** (מטרופולין) toward תל אביב יפו_מסוף כרמלית: board האוניברסיטה/חיים לבנון [code 21388] 08:06 -> alight דרך נמיר/יהודה המכבי [code 21188] 08:13 (service date 2026-11-02, trip `45060631_011126`)
3. Walk 2 min, 0 m: דרך נמיר/יהודה המכבי 08:13 -> דרך נמיר/יהודה המכבי 08:15
4. **bus 89** (דן) toward חולון_פארק פרס: board דרך נמיר/יהודה המכבי [code 21188] 08:15 -> alight ביה''ח איכילוב/ויצמן [code 21173] 08:21 (service date 2026-11-02, trip `13998568_011126`)
5. Walk 5 min, 275 m: ביה''ח איכילוב/ויצמן 08:21 -> END 08:26

Transfers (alight to next boarding, including any walk): דרך נמיר/יהודה המכבי -> דרך נמיר/יהודה המכבי: 2 min

**Option 2:** departs Mon 2026-11-02 08:01, arrives Mon 2026-11-02 08:30; total 29 min, 1 transfer(s), walking 13 min / 682 m

1. Walk 6 min, 407 m: START 08:01 -> האוניברסיטה/איינשטיין 08:07
2. **bus 25** (דן) toward חולון_מוזיאון אגד: board האוניברסיטה/איינשטיין [code 26635] 08:07 -> alight יהודה המכבי/דרך נמיר [code 25943] 08:15 (service date 2026-11-02, trip `3009879_011126`)
3. Walk 2 min, 0 m: יהודה המכבי/דרך נמיר 08:15 -> יהודה המכבי/דרך נמיר 08:17
4. **bus 14** (דן) toward מסוף הלוחמים: board יהודה המכבי/דרך נמיר [code 25943] 08:20 -> alight ביה''ח איכילוב/ויצמן [code 21173] 08:25 (service date 2026-11-02, trip `585552934_011126`)
5. Walk 5 min, 275 m: ביה''ח איכילוב/ויצמן 08:25 -> END 08:30

Transfers (alight to next boarding, including any walk): יהודה המכבי/דרך נמיר -> יהודה המכבי/דרך נמיר: 5 min

**Option 3:** departs Mon 2026-11-02 08:07, arrives Mon 2026-11-02 08:31; total 24 min, 0 transfer(s), walking 11 min / 682 m

1. Walk 6 min, 407 m: START 08:07 -> האוניברסיטה/איינשטיין 08:13
2. **bus 7** (דן) toward חולון_מ.רפואי וולפסון: board האוניברסיטה/איינשטיין [code 26635] 08:13 -> alight ביה''ח איכילוב/ויצמן [code 21173] 08:26 (service date 2026-11-02, trip `2593441_011126`)
3. Walk 5 min, 275 m: ביה''ח איכילוב/ויצמן 08:26 -> END 08:31

Transfers (alight to next boarding, including any walk): none

| Usable? (Y/N) | Notes | Compared against / when checked |
|---|---|---|
|  |  |  |

---

## J03 — Jaffa Clock Tower (מגדל השעון יפו) → Tel Aviv Savidor Center (תל אביב סבידור מרכז)

category `tel-aviv-urban-bus` · calendar rule `weekday_midday`

**Requested:** Depart at Tue 2026-11-03 13:00 (UTC+02:00)  
Request field: `departAt=2026-11-03T13:00:00+02:00`
**Calendar flags:** ordinary day
**Compare:** [Google Maps transit](https://www.google.com/maps/dir/?api=1&origin=32.0542,34.7522&destination=32.0836,34.7981&travelmode=transit) · [Moovit (unofficial deep link; may not prefill)](https://moovitapp.com/?fll=32.0542_34.7522&tll=32.0836_34.7981&from=Jaffa%20Clock%20Tower&to=Tel%20Aviv%20Savidor%20Center) · Set the time yourself to **Depart at 13:00, Tue 2026-11-03** (Google's documented URL has no time parameter).
**Corpus expectation (context, not a verdict):** outcome `route`, max_duration_min = 65, max_transfers = 2, min_duration_min = 15, modes_any_of = ['bus', 'light_rail']

> What to check: Jaffa to the main station. Does it use the red line where sensible?

**API RESULT: 3 journey option(s) returned** (scheduled times).
Machine note: matches the corpus expectation `route`. This is not a judgement of quality.
Request id `23e1801e7a624ed0b24d036daf537c52`.

**Option 1:** departs Tue 2026-11-03 13:04, arrives Tue 2026-11-03 13:35; total 31 min, 0 transfer(s), walking 11 min / 787 m

1. Walk 5 min, 356 m: START 13:04 -> יפת/לואי פסטר 13:09
2. **bus 44** (דן) toward תל אביב יפו_קריית עתידים: board יפת/לואי פסטר [code 20448] 13:09 -> alight ת. רכבת תל אביב - סבידור/דרך נמיר [code 24068] 13:29 (service date 2026-11-03, trip `45068558_011126`)
3. Walk 6 min, 431 m: ת. רכבת תל אביב - סבידור/דרך נמיר 13:29 -> END 13:35

Transfers (alight to next boarding, including any walk): none

**Option 2:** departs Tue 2026-11-03 13:06, arrives Tue 2026-11-03 13:39; total 33 min, 1 transfer(s), walking 14 min / 822 m

1. Walk 9 min, 639 m: START 13:06 -> כיכר השעון/מרזוק ועזר 13:15
2. **bus 54** (דן) toward קריית עתידים: board כיכר השעון/מרזוק ועזר [code 25303] 13:15 -> alight ת.רכבת ההגנה [code 25637] 13:24 (service date 2026-11-03, trip `45563005_011126`)
3. Walk 4 min, 156 m: ת.רכבת ההגנה 13:24 -> תל אביב ההגנה 13:28
4. **rail ** (רכבת ישראל) toward 318: board תל אביב ההגנה [code 17104] 13:30 -> alight תל אביב מרכז [code 17038] 13:38 (service date 2026-11-03, trip `1_526293`)
5. Walk 1 min, 27 m: תל אביב מרכז 13:38 -> END 13:39

Transfers (alight to next boarding, including any walk): ת.רכבת ההגנה -> תל אביב ההגנה: 6 min

**Option 3:** departs Tue 2026-11-03 13:07, arrives Tue 2026-11-03 13:42; total 35 min, 0 transfer(s), walking 21 min / 1366 m

1. Walk 13 min, 879 m: START 13:07 -> שלמה 13:20
2. **light_rail 1** (תבל) toward פתח תקווה_ת. מרכזית פתח תקווה: board שלמה [code 20546] 13:20 -> alight ארלוזורוב [code 20711] 13:34 (service date 2026-11-03, trip `585355926_301026`)
3. Walk 8 min, 487 m: ארלוזורוב 13:34 -> END 13:42

Transfers (alight to next boarding, including any walk): none

| Usable? (Y/N) | Notes | Compared against / when checked |
|---|---|---|
|  |  |  |

---

## J04 — Dizengoff Center (דיזנגוף סנטר) → Petah Tikva Kiryat Arye (פתח תקווה קרית אריה)

**Required journey #2** — PRD §7 #2 Tel Aviv → Petah Tikva · category `tel-aviv-urban-bus` · calendar rule `weekday_evening`

**Requested:** Depart at Wed 2026-11-04 18:30 (UTC+02:00)  
Request field: `departAt=2026-11-04T18:30:00+02:00`
**Calendar flags:** ordinary day
**Compare:** [Google Maps transit](https://www.google.com/maps/dir/?api=1&origin=32.0757,34.7748&destination=32.0956,34.8556&travelmode=transit) · [Moovit (unofficial deep link; may not prefill)](https://moovitapp.com/?fll=32.0757_34.7748&tll=32.0956_34.8556&from=Dizengoff%20Center&to=Petah%20Tikva%20Kiryat%20Arye) · Set the time yourself to **Depart at 18:30, Wed 2026-11-04** (Google's documented URL has no time parameter).
**Corpus expectation (context, not a verdict):** outcome `route`, max_duration_min = 90, max_transfers = 2, min_duration_min = 20, modes_any_of = ['bus', 'rail', 'light_rail']

> What to check: Evening peak. Does it prefer rail or bus, and is that the right call?

**API RESULT: 3 journey option(s) returned** (scheduled times).
Machine note: matches the corpus expectation `route`. This is not a judgement of quality.
Request id `c1d1659375aa4cd9b734ce15bf299a9b`.

**Option 1:** departs Wed 2026-11-04 18:31, arrives Wed 2026-11-04 19:06; total 35 min, 1 transfer(s), walking 13 min / 705 m

1. Walk 3 min, 135 m: START 18:31 -> דיזנגוף סנטר/דיזנגוף 18:34
2. **bus 63** (דן) toward רמת גן_אלוף שדה: board דיזנגוף סנטר/דיזנגוף [code 25565] 18:34 -> alight ת.רק''ל יהודית/דרך מנחם בגין [code 20727] 18:41 (service date 2026-11-04, trip `669285_011126`)
3. Walk 2 min, 93 m: ת.רק''ל יהודית/דרך מנחם בגין 18:41 -> יהודית 18:43
4. **light_rail 1** (תבל) toward פתח תקווה_ת. מרכזית פתח תקווה: board יהודית [code 20707] 18:43 -> alight שנקר [code 36309] 18:58 (service date 2026-11-04, trip `585268659_301026`)
5. Walk 8 min, 477 m: שנקר 18:58 -> END 19:06

Transfers (alight to next boarding, including any walk): ת.רק''ל יהודית/דרך מנחם בגין -> יהודית: 2 min

**Option 2:** departs Wed 2026-11-04 18:36, arrives Wed 2026-11-04 19:11; total 35 min, 0 transfer(s), walking 13 min / 753 m

1. Walk 5 min, 294 m: START 18:36 -> דיזנגוף סנטר/המלך ג'ורג' 18:41
2. **bus 82** (דן) toward פתח תקווה_בית רבקה: board דיזנגוף סנטר/המלך ג'ורג' [code 20785] 18:41 -> alight ת.רק''ל שנקר/דרך ז'בוטינסקי [code 32270] 19:03 (service date 2026-11-04, trip `15186667_011126`)
3. Walk 8 min, 459 m: ת.רק''ל שנקר/דרך ז'בוטינסקי 19:03 -> END 19:11

Transfers (alight to next boarding, including any walk): none

**Option 3:** departs Wed 2026-11-04 18:42, arrives Wed 2026-11-04 19:17; total 35 min, 1 transfer(s), walking 13 min / 705 m

1. Walk 3 min, 135 m: START 18:42 -> דיזנגוף סנטר/דיזנגוף 18:45
2. **bus 63** (דן) toward רמת גן_אלוף שדה: board דיזנגוף סנטר/דיזנגוף [code 25565] 18:45 -> alight ת.רק''ל יהודית/דרך מנחם בגין [code 20727] 18:52 (service date 2026-11-04, trip `13985828_011126`)
3. Walk 2 min, 93 m: ת.רק''ל יהודית/דרך מנחם בגין 18:52 -> יהודית 18:54
4. **light_rail 1** (תבל) toward פתח תקווה_ת. מרכזית פתח תקווה: board יהודית [code 20707] 18:54 -> alight שנקר [code 36309] 19:09 (service date 2026-11-04, trip `585373632_301026`)
5. Walk 8 min, 477 m: שנקר 19:09 -> END 19:17

Transfers (alight to next boarding, including any walk): ת.רק''ל יהודית/דרך מנחם בגין -> יהודית: 2 min

| Usable? (Y/N) | Notes | Compared against / when checked |
|---|---|---|
|  |  |  |

---

## J05 — Mahane Yehuda Market (שוק מחנה יהודה) → Mount Herzl (הר הרצל)

category `jerusalem-urban-light-rail` · calendar rule `weekday_midday`

**Requested:** Depart at Tue 2026-11-03 13:00 (UTC+02:00)  
Request field: `departAt=2026-11-03T13:00:00+02:00`
**Calendar flags:** ordinary day
**Compare:** [Google Maps transit](https://www.google.com/maps/dir/?api=1&origin=31.7853,35.2124&destination=31.7736,35.1806&travelmode=transit) · [Moovit (unofficial deep link; may not prefill)](https://moovitapp.com/?fll=31.7853_35.2124&tll=31.7736_35.1806&from=Mahane%20Yehuda%20Market&to=Mount%20Herzl) · Set the time yourself to **Depart at 13:00, Tue 2026-11-03** (Google's documented URL has no time parameter).
**Corpus expectation (context, not a verdict):** outcome `route`, max_duration_min = 45, max_transfers = 1, min_duration_min = 8, modes_any_of = ['light_rail', 'bus']

> What to check: This is the light rail's spine. If it routes by bus instead, something is wrong.

**API RESULT: 3 journey option(s) returned** (scheduled times).
Machine note: matches the corpus expectation `route`. This is not a judgement of quality.
Request id `5110ff77396941f98961268ae9871449`.

**Option 1:** departs Tue 2026-11-03 13:02, arrives Tue 2026-11-03 13:27; total 25 min, 0 transfer(s), walking 11 min / 706 m

1. Walk 2 min, 145 m: START 13:02 -> מחנה יהודה 13:04
2. **light_rail 1** (כפיר) toward הדסה עין כרם: board מחנה יהודה [code 6172] 13:04 -> alight הר הרצל [code 6185] 13:18 (service date 2026-11-03, trip `12467281_301026`)
3. Walk 9 min, 561 m: הר הרצל 13:18 -> END 13:27

Transfers (alight to next boarding, including any walk): none

**Option 2:** departs Tue 2026-11-03 13:07, arrives Tue 2026-11-03 13:32; total 25 min, 0 transfer(s), walking 11 min / 706 m

1. Walk 2 min, 145 m: START 13:07 -> מחנה יהודה 13:09
2. **light_rail 1** (כפיר) toward הדסה עין כרם: board מחנה יהודה [code 6172] 13:09 -> alight הר הרצל [code 6185] 13:23 (service date 2026-11-03, trip `21129521_301026`)
3. Walk 9 min, 561 m: הר הרצל 13:23 -> END 13:32

Transfers (alight to next boarding, including any walk): none

**Option 3:** departs Tue 2026-11-03 13:12, arrives Tue 2026-11-03 13:37; total 25 min, 0 transfer(s), walking 11 min / 706 m

1. Walk 2 min, 145 m: START 13:12 -> מחנה יהודה 13:14
2. **light_rail 1** (כפיר) toward הדסה עין כרם: board מחנה יהודה [code 6172] 13:14 -> alight הר הרצל [code 6185] 13:28 (service date 2026-11-03, trip `8292667_301026`)
3. Walk 9 min, 561 m: הר הרצל 13:28 -> END 13:37

Transfers (alight to next boarding, including any walk): none

| Usable? (Y/N) | Notes | Compared against / when checked |
|---|---|---|
|  |  |  |

---

## J06 — Jerusalem Central Bus Station (תחנה מרכזית ירושלים) → Hebrew University Mount Scopus (האוניברסיטה העברית הר הצופים)

category `jerusalem-urban-light-rail` · calendar rule `weekday_morning`

**Requested:** Depart at Mon 2026-11-02 08:00 (UTC+02:00)  
Request field: `departAt=2026-11-02T08:00:00+02:00`
**Calendar flags:** ordinary day
**Compare:** [Google Maps transit](https://www.google.com/maps/dir/?api=1&origin=31.7887,35.203&destination=31.7936,35.2444&travelmode=transit) · [Moovit (unofficial deep link; may not prefill)](https://moovitapp.com/?fll=31.7887_35.203&tll=31.7936_35.2444&from=Jerusalem%20Central%20Bus%20Station&to=Hebrew%20University%20Mount%20Scopus) · Set the time yourself to **Depart at 08:00, Mon 2026-11-02** (Google's documented URL has no time parameter).
**Corpus expectation (context, not a verdict):** outcome `route`, max_duration_min = 70, max_transfers = 2, min_duration_min = 15, modes_any_of = ['light_rail', 'bus']

> What to check: Cross-city to Mount Scopus. Check the transfer point is a real interchange.

**API RESULT: 3 journey option(s) returned** (scheduled times).
Machine note: matches the corpus expectation `route`. This is not a judgement of quality.
Request id `dcaeb73fa5dc46928f3e4e4a1353facf`.

**Option 1:** departs Mon 2026-11-02 08:01, arrives Mon 2026-11-02 08:28; total 27 min, 1 transfer(s), walking 8 min / 347 m

1. Walk 1 min, 57 m: START 08:01 -> ת. מרכזית ירושלים/יפו 08:02
2. **bus 18** (אגד) toward מלחה: board ת. מרכזית ירושלים/יפו [code 4156] 08:02 -> alight ככר הדוידקה/הנביאים [code 1601] 08:07 (service date 2026-11-02, trip `8412260_301026`)
3. Walk 2 min, 0 m: ככר הדוידקה/הנביאים 08:07 -> ככר הדוידקה/הנביאים 08:09
4. **bus 19א** (אגד) toward מסוף הר הצופים: board ככר הדוידקה/הנביאים [code 1601] 08:12 -> alight האוניברסיטה העברית הר הצופים/מרטין בובר [code 1371] 08:23 (service date 2026-11-02, trip `8821728_301026`)
5. Walk 5 min, 290 m: האוניברסיטה העברית הר הצופים/מרטין בובר 08:23 -> END 08:28

Transfers (alight to next boarding, including any walk): ככר הדוידקה/הנביאים -> ככר הדוידקה/הנביאים: 5 min

**Option 2:** departs Mon 2026-11-02 08:07, arrives Mon 2026-11-02 08:30; total 23 min, 0 transfer(s), walking 10 min / 623 m

1. Walk 5 min, 333 m: START 08:07 -> שרי ישראל/יפו 08:12
2. **bus 568** (אקסטרה ירושלים) toward מסוף הר הצופים: board שרי ישראל/יפו [code 78] 08:12 -> alight האוניברסיטה העברית הר הצופים/מרטין בובר [code 1371] 08:25 (service date 2026-11-02, trip `585640504_301026`)
3. Walk 5 min, 290 m: האוניברסיטה העברית הר הצופים/מרטין בובר 08:25 -> END 08:30

Transfers (alight to next boarding, including any walk): none

**Option 3:** departs Mon 2026-11-02 08:08, arrives Mon 2026-11-02 08:32; total 24 min, 1 transfer(s), walking 8 min / 347 m

1. Walk 1 min, 57 m: START 08:08 -> ת. מרכזית ירושלים/יפו 08:09
2. **bus 74** (סופרבוס) toward חומת שמואל: board ת. מרכזית ירושלים/יפו [code 4156] 08:09 -> alight הנביאים/הרב קוק [code 3379] 08:16 (service date 2026-11-02, trip `584794982_011126`)
3. Walk 2 min, 0 m: הנביאים/הרב קוק 08:16 -> הנביאים/הרב קוק 08:18
4. **bus 19** (אגד) toward מסוף הר הצופים: board הנביאים/הרב קוק [code 3379] 08:18 -> alight האוניברסיטה העברית הר הצופים/מרטין בובר [code 1371] 08:27 (service date 2026-11-02, trip `585944010_301026`)
5. Walk 5 min, 290 m: האוניברסיטה העברית הר הצופים/מרטין בובר 08:27 -> END 08:32

Transfers (alight to next boarding, including any walk): הנביאים/הרב קוק -> הנביאים/הרב קוק: 2 min

| Usable? (Y/N) | Notes | Compared against / when checked |
|---|---|---|
|  |  |  |

---

## J07 — Yitzhak Navon Station (תחנת יצחק נבון) → Malha Mall (קניון מלחא)

category `jerusalem-urban-light-rail` · calendar rule `weekday_evening`

**Requested:** Depart at Wed 2026-11-04 18:30 (UTC+02:00)  
Request field: `departAt=2026-11-04T18:30:00+02:00`
**Calendar flags:** ordinary day
**Compare:** [Google Maps transit](https://www.google.com/maps/dir/?api=1&origin=31.7888,35.2027&destination=31.7513,35.1875&travelmode=transit) · [Moovit (unofficial deep link; may not prefill)](https://moovitapp.com/?fll=31.7888_35.2027&tll=31.7513_35.1875&from=Yitzhak%20Navon%20Station&to=Malha%20Mall) · Set the time yourself to **Depart at 18:30, Wed 2026-11-04** (Google's documented URL has no time parameter).
**Corpus expectation (context, not a verdict):** outcome `route`, max_duration_min = 70, max_transfers = 2, min_duration_min = 15, modes_any_of = ['light_rail', 'bus', 'rail']

> What to check: Does it consider the Malha rail branch, and is that sensible at this hour?

**API RESULT: 3 journey option(s) returned** (scheduled times).
Machine note: matches the corpus expectation `route`. This is not a judgement of quality.
Request id `34bc741a83fd464abeaba715b90c2b8b`.

**Option 1:** departs Wed 2026-11-04 18:31, arrives Wed 2026-11-04 18:49; total 18 min, 0 transfer(s), walking 10 min / 649 m

1. Walk 4 min, 227 m: START 18:31 -> שדרות שז''ר/בנייני האומה 18:35
2. **bus 31** (סופרבוס) toward גילה: board שדרות שז''ר/בנייני האומה [code 463] 18:35 -> alight קניון מלחה/א''ס הפועל   האייל [code 2913] 18:43 (service date 2026-11-04, trip `584872013_011126`)
3. Walk 6 min, 422 m: קניון מלחה/א''ס הפועל   האייל 18:43 -> END 18:49

Transfers (alight to next boarding, including any walk): none

**Option 2:** departs Wed 2026-11-04 18:34, arrives Wed 2026-11-04 18:57; total 23 min, 0 transfer(s), walking 14 min / 532 m

1. Walk 4 min, 227 m: START 18:34 -> שדרות שז''ר/בנייני האומה 18:38
2. **bus 504** (סופרבוס) toward חומת שמואל: board שדרות שז''ר/בנייני האומה [code 463] 18:38 -> alight אצטדיון טדי/א''ס ביתר [code 222] 18:47 (service date 2026-11-04, trip `584865032_301026`)
3. Walk 10 min, 305 m: אצטדיון טדי/א''ס ביתר 18:47 -> END 18:57

Transfers (alight to next boarding, including any walk): none

**Option 3:** departs Wed 2026-11-04 18:36, arrives Wed 2026-11-04 19:00; total 24 min, 0 transfer(s), walking 10 min / 367 m

1. Walk 4 min, 227 m: START 18:36 -> שדרות שז''ר/בנייני האומה 18:40
2. **bus 509** (סופרבוס) toward מלחה: board שדרות שז''ר/בנייני האומה [code 463] 18:40 -> alight קניון מלחה/א''ס מכבי [code 4171] 18:54 (service date 2026-11-04, trip `585413242_301026`)
3. Walk 6 min, 140 m: קניון מלחה/א''ס מכבי 18:54 -> END 19:00

Transfers (alight to next boarding, including any walk): none

| Usable? (Y/N) | Notes | Compared against / when checked |
|---|---|---|
|  |  |  |

---

## J08 — Haifa Center HaShmona (חיפה מרכז השמונה) → Technion (הטכניון)

category `haifa-urban` · calendar rule `weekday_morning`

**Requested:** Depart at Mon 2026-11-02 08:00 (UTC+02:00)  
Request field: `departAt=2026-11-02T08:00:00+02:00`
**Calendar flags:** ordinary day
**Compare:** [Google Maps transit](https://www.google.com/maps/dir/?api=1&origin=32.8206,34.9985&destination=32.7767,35.0217&travelmode=transit) · [Moovit (unofficial deep link; may not prefill)](https://moovitapp.com/?fll=32.8206_34.9985&tll=32.7767_35.0217&from=Haifa%20Center%20HaShmona&to=Technion) · Set the time yourself to **Depart at 08:00, Mon 2026-11-02** (Google's documented URL has no time parameter).
**Corpus expectation (context, not a verdict):** outcome `route`, max_duration_min = 75, max_transfers = 2, min_duration_min = 15, modes_any_of = ['bus', 'cable_car', 'funicular']

> What to check: Haifa is vertical. Check the walking legs are not absurd gradients.

**API RESULT: 3 journey option(s) returned** (scheduled times).
Machine note: matches the corpus expectation `route`. This is not a judgement of quality.
Request id `9fb84684b94d41728948c6c4f99d5681`.

**Option 1:** departs Mon 2026-11-02 08:00, arrives Mon 2026-11-02 08:40; total 40 min, 0 transfer(s), walking 16 min / 994 m

1. Walk 11 min, 719 m: START 08:00 -> תחנת רכבת חיפה מרכז השמונה 08:11
2. **bus 17** (אגד) toward טכניון: board תחנת רכבת חיפה מרכז השמונה [code 41540] 08:11 -> alight טכניון/מעונות העמים [code 41200] 08:35 (service date 2026-11-02, trip `5355401_301026`)
3. Walk 5 min, 275 m: טכניון/מעונות העמים 08:35 -> END 08:40

Transfers (alight to next boarding, including any walk): none

**Option 2:** departs Mon 2026-11-02 08:01, arrives Mon 2026-11-02 08:40; total 39 min, 1 transfer(s), walking 14 min / 713 m

1. Walk 7 min, 438 m: START 08:01 -> המגינים/ככר ההגנה 08:08
2. **bus 3** (אגד) toward מרכזית חוף הכרמל: board המגינים/ככר ההגנה [code 42723] 08:08 -> alight פלים/קיבוץ גלויות [code 43108] 08:10 (service date 2026-11-02, trip `10378671_301026`)
3. Walk 2 min, 0 m: פלים/קיבוץ גלויות 08:10 -> פלים/קיבוץ גלויות 08:12
4. **bus 17** (אגד) toward טכניון: board פלים/קיבוץ גלויות [code 43108] 08:14 -> alight טכניון/מעונות העמים [code 41200] 08:35 (service date 2026-11-02, trip `5355401_301026`)
5. Walk 5 min, 275 m: טכניון/מעונות העמים 08:35 -> END 08:40

Transfers (alight to next boarding, including any walk): פלים/קיבוץ גלויות -> פלים/קיבוץ גלויות: 4 min

**Option 3:** departs Mon 2026-11-02 08:08, arrives Mon 2026-11-02 08:50; total 42 min, 1 transfer(s), walking 14 min / 820 m

1. Walk 7 min, 438 m: START 08:08 -> המגינים/ככר ההגנה 08:15
2. **bus 16** (אגד) toward מרכזית המפרץ: board המגינים/ככר ההגנה [code 42723] 08:15 -> alight חנקין/קומוי [code 41886] 08:38 (service date 2026-11-02, trip `7083211_301026`)
3. Walk 2 min, 107 m: חנקין/קומוי 08:38 -> קומוי/חנקין 08:40
4. **bus 76** (אגד) toward יגור_מסוף יגור: board קומוי/חנקין [code 41202] 08:43 -> alight טכניון/מעונות העמים [code 41200] 08:45 (service date 2026-11-02, trip `585688536_301026`)
5. Walk 5 min, 275 m: טכניון/מעונות העמים 08:45 -> END 08:50

Transfers (alight to next boarding, including any walk): חנקין/קומוי -> קומוי/חנקין: 5 min

| Usable? (Y/N) | Notes | Compared against / when checked |
|---|---|---|
|  |  |  |

---

## J09 — Haifa University (אוניברסיטת חיפה) → Bat Galim Central Station (חיפה בת גלים)

category `haifa-urban` · calendar rule `weekday_evening`

**Requested:** Depart at Wed 2026-11-04 18:30 (UTC+02:00)  
Request field: `departAt=2026-11-04T18:30:00+02:00`
**Calendar flags:** ordinary day
**Compare:** [Google Maps transit](https://www.google.com/maps/dir/?api=1&origin=32.7614,35.0207&destination=32.8283,34.9539&travelmode=transit) · [Moovit (unofficial deep link; may not prefill)](https://moovitapp.com/?fll=32.7614_35.0207&tll=32.8283_34.9539&from=Haifa%20University&to=Bat%20Galim%20Central%20Station) · Set the time yourself to **Depart at 18:30, Wed 2026-11-04** (Google's documented URL has no time parameter).
**Corpus expectation (context, not a verdict):** outcome `route`, max_duration_min = 85, max_transfers = 2, min_duration_min = 20, modes_any_of = ['bus', 'rail']

> What to check: Long descent across the Carmel. Compare to Moovit for line choice.

**API RESULT: NO ROUTE** — a valid search inside coverage returned no journey. The API does not state a cause (no service, walking limit and data gaps look alike).
Machine note: DIFFERS FROM the corpus expectation `route`. This is not a judgement of quality.
Request id `8f3ef0dc7d1f4cf9952b0e3f9f692672`.

| Usable? (Y/N) | Notes | Compared against / when checked |
|---|---|---|
|  |  |  |

---

## J10 — Grand Kanyon Haifa (גראנד קניון חיפה) → Rambam Medical Center (בית חולים רמבם)

category `haifa-urban` · calendar rule `weekday_midday`

**Requested:** Depart at Tue 2026-11-03 13:00 (UTC+02:00)  
Request field: `departAt=2026-11-03T13:00:00+02:00`
**Calendar flags:** ordinary day
**Compare:** [Google Maps transit](https://www.google.com/maps/dir/?api=1&origin=32.7943,34.9891&destination=32.8347,34.9857&travelmode=transit) · [Moovit (unofficial deep link; may not prefill)](https://moovitapp.com/?fll=32.7943_34.9891&tll=32.8347_34.9857&from=Grand%20Kanyon%20Haifa&to=Rambam%20Medical%20Center) · Set the time yourself to **Depart at 13:00, Tue 2026-11-03** (Google's documented URL has no time parameter).
**Corpus expectation (context, not a verdict):** outcome `route`, max_duration_min = 70, max_transfers = 2, min_duration_min = 12, modes_any_of = ['bus', 'rail', 'funicular']

> What to check: Mall to hospital. Does the Metronit BRT get used?

**API RESULT: 3 journey option(s) returned** (scheduled times).
Machine note: matches the corpus expectation `route`. This is not a judgement of quality.
Request id `46d85fe6dce447b39eb2ccf6851e575b`.

**Option 1:** departs Tue 2026-11-03 13:01, arrives Tue 2026-11-03 13:47; total 46 min, 1 transfer(s), walking 21 min / 1438 m

1. Walk 11 min, 665 m: START 13:01 -> מוריה/ספקטור 13:12
2. **bus 58** (סופרבוס) toward חיפה_רכבת מרכז השמונה: board מוריה/ספקטור [code 40990] 13:12 -> alight דרך סטלה מאריס [code 40666] 13:29 (service date 2026-11-03, trip `584902463_301026`)
3. Walk 2 min, 317 m: דרך סטלה מאריס 13:29 -> הברון הירש/אלנבי 13:31
4. **bus 40** (אגד) toward תחנת הרכבל: board הברון הירש/אלנבי [code 41112] 13:33 -> alight העליה השניה/עפרון [code 41159] 13:39 (service date 2026-11-03, trip `1312483_301026`)
5. Walk 8 min, 456 m: העליה השניה/עפרון 13:39 -> END 13:47

Transfers (alight to next boarding, including any walk): דרך סטלה מאריס -> הברון הירש/אלנבי: 4 min

**Option 2:** departs Tue 2026-11-03 13:06, arrives Tue 2026-11-03 13:52; total 46 min, 0 transfer(s), walking 21 min / 1274 m

1. Walk 11 min, 665 m: START 13:06 -> מוריה/ספקטור 13:17
2. **bus 37** (אגד) toward רכבת בת גלים: board מוריה/ספקטור [code 40990] 13:17 -> alight ת. רכבת בת גלים [code 47181] 13:42 (service date 2026-11-03, trip `1311194_301026`)
3. Walk 10 min, 609 m: ת. רכבת בת גלים 13:42 -> END 13:52

Transfers (alight to next boarding, including any walk): none

**Option 3:** departs Tue 2026-11-03 13:08, arrives Tue 2026-11-03 13:53; total 45 min, 0 transfer(s), walking 22 min / 1303 m

1. Walk 11 min, 665 m: START 13:08 -> מוריה/ספקטור 13:19
2. **bus 37א** (אגד) toward חיפה_רכבת בת גלים: board מוריה/ספקטור [code 40990] 13:19 -> alight חיל הים/העלייה השנייה [code 42746] 13:42 (service date 2026-11-03, trip `25569346_301026`)
3. Walk 11 min, 638 m: חיל הים/העלייה השנייה 13:42 -> END 13:53

Transfers (alight to next boarding, including any walk): none

| Usable? (Y/N) | Notes | Compared against / when checked |
|---|---|---|
|  |  |  |

---

## J11 — Tel Aviv Savidor Center (תל אביב סבידור מרכז) → Haifa Center HaShmona (חיפה מרכז השמונה)

**Required journey #3** — PRD §7 #3 Tel Aviv → Haifa · category `intercity-rail` · calendar rule `weekday_morning`

**Requested:** Depart at Mon 2026-11-02 08:00 (UTC+02:00)  
Request field: `departAt=2026-11-02T08:00:00+02:00`
**Calendar flags:** ordinary day
**Compare:** [Google Maps transit](https://www.google.com/maps/dir/?api=1&origin=32.0836,34.7981&destination=32.8206,34.9985&travelmode=transit) · [Moovit (unofficial deep link; may not prefill)](https://moovitapp.com/?fll=32.0836_34.7981&tll=32.8206_34.9985&from=Tel%20Aviv%20Savidor%20Center&to=Haifa%20Center%20HaShmona) · Set the time yourself to **Depart at 08:00, Mon 2026-11-02** (Google's documented URL has no time parameter).
**Corpus expectation (context, not a verdict):** outcome `route`, max_duration_min = 130, max_transfers = 1, min_duration_min = 45, modes_any_of = ['rail']

> What to check: The flagship rail corridor. Cross-check timings against BetterRail.

API warnings: TRANSFER_STREET_PATH_UNAVAILABLE

**API RESULT: 3 journey option(s) returned** (scheduled times).
Machine note: matches the corpus expectation `route`. This is not a judgement of quality.
Request id `88beebe1cfcf469380ab154da41c5aa7`.

**Option 1:** departs Mon 2026-11-02 08:14, arrives Mon 2026-11-02 09:38; total 84 min, 1 transfer(s), walking 14 min / unknown distance

1. Walk 1 min, 27 m: START 08:14 -> תל אביב מרכז 08:15
2. **rail ** (רכבת ישראל) toward 24: board תל אביב מרכז [code 17038] 08:15 -> alight חיפה מרכז [code 17016] 09:23 (service date 2026-11-02, trip `1_521346`)
3. Walk 4 min (timetable transfer; street path unavailable): חיפה מרכז 09:23 -> תחנת רכבת חיפה מרכז השמונה 09:27
4. **bus 2** (סופרבוס) toward קרית אתא_יוספטל: board תחנת רכבת חיפה מרכז השמונה [code 47574] 09:28 -> alight כרמלית [code 47576] 09:29 (service date 2026-11-02, trip `15019535_301026`)
5. Walk 9 min, 564 m: כרמלית 09:29 -> END 09:38

Transfers (alight to next boarding, including any walk): חיפה מרכז -> תחנת רכבת חיפה מרכז השמונה: 5 min

**Option 2:** departs Mon 2026-11-02 08:25, arrives Mon 2026-11-02 09:52; total 87 min, 1 transfer(s), walking 14 min / 898 m

1. Walk 1 min, 27 m: START 08:25 -> תל אביב מרכז 08:26
2. **rail ** (רכבת ישראל) toward 156: board תל אביב מרכז [code 17038] 08:26 -> alight בת גלים [code 17018] 09:31 (service date 2026-11-02, trip `1_521247`)
3. Walk 2 min, 152 m: בת גלים 09:31 -> ת. רכבת בת גלים 09:33
4. **bus 36** (אגד) toward אוניברסיטה: board ת. רכבת בת גלים [code 47181] 09:34 -> alight תחנת רכבת חיפה מרכז השמונה [code 41540] 09:41 (service date 2026-11-02, trip `11572583_301026`)
5. Walk 11 min, 719 m: תחנת רכבת חיפה מרכז השמונה 09:41 -> END 09:52

Transfers (alight to next boarding, including any walk): בת גלים -> ת. רכבת בת גלים: 3 min

**Option 3:** departs Mon 2026-11-02 08:44, arrives Mon 2026-11-02 10:08; total 84 min, 1 transfer(s), walking 14 min / 898 m

1. Walk 1 min, 27 m: START 08:44 -> תל אביב מרכז 08:45
2. **rail ** (רכבת ישראל) toward 404: board תל אביב מרכז [code 17038] 08:45 -> alight בת גלים [code 17018] 09:48 (service date 2026-11-02, trip `1_521139`)
3. Walk 2 min, 152 m: בת גלים 09:48 -> ת. רכבת בת גלים 09:50
4. **bus 18** (אגד) toward נווה שאנן: board ת. רכבת בת גלים [code 47181] 09:50 -> alight תחנת רכבת חיפה מרכז השמונה [code 41540] 09:57 (service date 2026-11-02, trip `25308365_301026`)
5. Walk 11 min, 719 m: תחנת רכבת חיפה מרכז השמונה 09:57 -> END 10:08

Transfers (alight to next boarding, including any walk): בת גלים -> ת. רכבת בת גלים: 2 min

| Usable? (Y/N) | Notes | Compared against / when checked |
|---|---|---|
|  |  |  |

---

## J12 — Tel Aviv Savidor Center (תל אביב סבידור מרכז) → Yitzhak Navon Station (תחנת יצחק נבון)

**Required journey #4** — PRD §7 #4 Tel Aviv → Jerusalem · category `intercity-rail` · calendar rule `weekday_morning`

**Requested:** Depart at Mon 2026-11-02 08:00 (UTC+02:00)  
Request field: `departAt=2026-11-02T08:00:00+02:00`
**Calendar flags:** ordinary day
**Compare:** [Google Maps transit](https://www.google.com/maps/dir/?api=1&origin=32.0836,34.7981&destination=31.7888,35.2027&travelmode=transit) · [Moovit (unofficial deep link; may not prefill)](https://moovitapp.com/?fll=32.0836_34.7981&tll=31.7888_35.2027&from=Tel%20Aviv%20Savidor%20Center&to=Yitzhak%20Navon%20Station) · Set the time yourself to **Depart at 08:00, Mon 2026-11-02** (Google's documented URL has no time parameter).
**Corpus expectation (context, not a verdict):** outcome `route`, max_duration_min = 110, max_transfers = 1, min_duration_min = 30, modes_any_of = ['rail']

> What to check: Fast line. If it routes by bus, the rail calendar is probably misread.

**API RESULT: 3 journey option(s) returned** (scheduled times).
Machine note: matches the corpus expectation `route`. This is not a judgement of quality.
Request id `c19193f0f117441ca9757631241d66f8`.

**Option 1:** departs Mon 2026-11-02 08:04, arrives Mon 2026-11-02 08:55; total 51 min, 0 transfer(s), walking 4 min / 207 m

1. Walk 1 min, 27 m: START 08:04 -> תל אביב מרכז 08:05
2. **rail ** (רכבת ישראל) toward 723: board תל אביב מרכז [code 17038] 08:05 -> alight ירושלים/יצחק נבון [code 17118] 08:52 (service date 2026-11-02, trip `1_520957`)
3. Walk 3 min, 180 m: ירושלים/יצחק נבון 08:52 -> END 08:55

Transfers (alight to next boarding, including any walk): none

**Option 2:** departs Mon 2026-11-02 08:14, arrives Mon 2026-11-02 09:09; total 55 min, 0 transfer(s), walking 11 min / 710 m

1. Walk 6 min, 403 m: START 08:14 -> ת.רכבת תל אביב - סבידור/רציפים B 08:20
2. **bus 480** (אגד) toward ירושלים_תחנה מרכזית: board ת.רכבת תל אביב - סבידור/רציפים B [code 20740] 08:20 -> alight ת. מרכזית ירושלים/הורדה [code 6109] 09:04 (service date 2026-11-02, trip `2549890_301026`)
3. Walk 5 min, 307 m: ת. מרכזית ירושלים/הורדה 09:04 -> END 09:09

Transfers (alight to next boarding, including any walk): none

**Option 3:** departs Mon 2026-11-02 08:34, arrives Mon 2026-11-02 09:25; total 51 min, 0 transfer(s), walking 4 min / 207 m

1. Walk 1 min, 27 m: START 08:34 -> תל אביב מרכז 08:35
2. **rail ** (רכבת ישראל) toward 725: board תל אביב מרכז [code 17038] 08:35 -> alight ירושלים/יצחק נבון [code 17118] 09:22 (service date 2026-11-02, trip `1_521008`)
3. Walk 3 min, 180 m: ירושלים/יצחק נבון 09:22 -> END 09:25

Transfers (alight to next boarding, including any walk): none

| Usable? (Y/N) | Notes | Compared against / when checked |
|---|---|---|
|  |  |  |

---

## J13 — Tel Aviv HaShalom (תל אביב השלום) → Beersheba Central (באר שבע מרכז)

category `intercity-rail` · calendar rule `weekday_midday`

**Requested:** Depart at Tue 2026-11-03 13:00 (UTC+02:00)  
Request field: `departAt=2026-11-03T13:00:00+02:00`
**Calendar flags:** ordinary day
**Compare:** [Google Maps transit](https://www.google.com/maps/dir/?api=1&origin=32.0731,34.7925&destination=31.243,34.7983&travelmode=transit) · [Moovit (unofficial deep link; may not prefill)](https://moovitapp.com/?fll=32.0731_34.7925&tll=31.243_34.7983&from=Tel%20Aviv%20HaShalom&to=Beersheba%20Central) · Set the time yourself to **Depart at 13:00, Tue 2026-11-03** (Google's documented URL has no time parameter).
**Corpus expectation (context, not a verdict):** outcome `route`, max_duration_min = 180, max_transfers = 1, min_duration_min = 60, modes_any_of = ['rail']

> What to check: Long-distance south. Is the itinerary the direct train or a silly chain?

**API RESULT: 3 journey option(s) returned** (scheduled times).
Machine note: matches the corpus expectation `route`. This is not a judgement of quality.
Request id `1c029451c7544de4a69e3a3a6d891e92`.

**Option 1:** departs Tue 2026-11-03 13:11, arrives Tue 2026-11-03 14:51; total 100 min, 0 transfer(s), walking 5 min / 314 m

1. Walk 4 min, 270 m: START 13:11 -> השלום 13:15
2. **rail ** (רכבת ישראל) toward 33: board השלום [code 17046] 13:15 -> alight באר שבע מרכז [code 17084] 14:50 (service date 2026-11-03, trip `1_521236`)
3. Walk 1 min, 44 m: באר שבע מרכז 14:50 -> END 14:51

Transfers (alight to next boarding, including any walk): none

**Option 2:** departs Tue 2026-11-03 13:37, arrives Tue 2026-11-03 15:20; total 103 min, 0 transfer(s), walking 5 min / 314 m

1. Walk 4 min, 270 m: START 13:37 -> השלום 13:41
2. **rail ** (רכבת ישראל) toward 643: board השלום [code 17046] 13:41 -> alight באר שבע מרכז [code 17084] 15:19 (service date 2026-11-03, trip `1_525336`)
3. Walk 1 min, 44 m: באר שבע מרכז 15:19 -> END 15:20

Transfers (alight to next boarding, including any walk): none

**Option 3:** departs Tue 2026-11-03 13:46, arrives Tue 2026-11-03 15:35; total 109 min, 2 transfer(s), walking 20 min / 1430 m

1. Walk 4 min, 270 m: START 13:46 -> השלום 13:50
2. **rail ** (רכבת ישראל) toward 517: board השלום [code 17046] 13:50 -> alight תל אביב ההגנה [code 17104] 13:55 (service date 2026-11-03, trip `1_521060`)
3. Walk 4 min, 407 m: תל אביב ההגנה 13:56 -> מסוף ההגנה/איסוף 14:00
4. **bus 114** (דן) toward מסוף רכבת ההגנה: board מסוף ההגנה/איסוף [code 20860] 14:00 -> alight גשר קיבוץ גלויות [code 25287] 14:02 (service date 2026-11-03, trip `585060824_011126`)
5. Walk 2 min, 96 m: גשר קיבוץ גלויות 14:02 -> דרך קיבוץ גלויות/כביש 1 14:04
6. **bus 370** (מטרופולין) toward באר שבע_תחנה מרכזית: board דרך קיבוץ גלויות/כביש 1 [code 25069] 14:04 -> alight ת.מרכזית באר שבע/הורדה [code 15657] 15:25 (service date 2026-11-03, trip `2821988_301026`)
7. Walk 10 min, 657 m: ת.מרכזית באר שבע/הורדה 15:25 -> END 15:35

Transfers (alight to next boarding, including any walk): תל אביב ההגנה -> מסוף ההגנה/איסוף: 5 min; גשר קיבוץ גלויות -> דרך קיבוץ גלויות/כביש 1: 2 min

| Usable? (Y/N) | Notes | Compared against / when checked |
|---|---|---|
|  |  |  |

---

## J14 — Nahariya (נהריה) → Ashdod Ad Halom (אשדוד עד הלום)

category `intercity-rail` · calendar rule `weekday_morning`

**Requested:** Depart at Mon 2026-11-02 08:00 (UTC+02:00)  
Request field: `departAt=2026-11-02T08:00:00+02:00`
**Calendar flags:** ordinary day
**Compare:** [Google Maps transit](https://www.google.com/maps/dir/?api=1&origin=33.0079,35.0938&destination=31.794,34.641&travelmode=transit) · [Moovit (unofficial deep link; may not prefill)](https://moovitapp.com/?fll=33.0079_35.0938&tll=31.794_34.641&from=Nahariya&to=Ashdod%20Ad%20Halom) · Set the time yourself to **Depart at 08:00, Mon 2026-11-02** (Google's documented URL has no time parameter).
**Corpus expectation (context, not a verdict):** outcome `route`, max_duration_min = 260, max_transfers = 2, min_duration_min = 120, modes_any_of = ['rail']

> What to check: End-to-end coastal line. Tests the longest single-mode journey in the country.

API warnings: TRANSFER_STREET_PATH_UNAVAILABLE

**API RESULT: 3 journey option(s) returned** (scheduled times).
Machine note: matches the corpus expectation `route`. This is not a judgement of quality.
Request id `497f5c99185d4e9b9d2df21123c2a2b3`.

**Option 1:** departs Mon 2026-11-02 08:02, arrives Mon 2026-11-02 10:53; total 171 min, 1 transfer(s), walking 20 min / 1229 m

1. Walk 13 min, 760 m: START 08:02 -> נהריה 08:15
2. **rail ** (רכבת ישראל) toward 157: board נהריה [code 17014] 08:15 -> alight השלום [code 17046] 10:04 (service date 2026-11-02, trip `1_521246`)
3. Walk 4 min, 315 m: השלום 10:04 -> קניון עזריאלי/כביש 20 10:08
4. **bus 280** (אלקטרה אפיקים) toward אשדוד_תחנה מרכזית: board קניון עזריאלי/כביש 20 [code 21378] 10:09 -> alight ירושלים [code 12019] 10:50 (service date 2026-11-02, trip `28979431_301026`)
5. Walk 3 min, 154 m: ירושלים 10:50 -> END 10:53

Transfers (alight to next boarding, including any walk): השלום -> קניון עזריאלי/כביש 20: 5 min

**Option 2:** departs Mon 2026-11-02 08:03, arrives Mon 2026-11-02 10:53; total 170 min, 2 transfer(s), walking 18 min / unknown distance

1. Walk 7 min, 410 m: START 08:03 -> שדרות הגעתון/עזריאל ריציק 08:10
2. **bus 16** (נתיב אקספרס) toward רגבה_מרכז מסחרי: board שדרות הגעתון/עזריאל ריציק [code 56555] 08:10 -> alight תחנה מרכזית נהריה/שדרות הגעתון [code 56437] 08:10 (service date 2026-11-02, trip `586233801_301026`)
3. Walk 4 min (timetable transfer; street path unavailable): תחנה מרכזית נהריה/שדרות הגעתון 08:11 -> נהריה 08:15
4. **rail ** (רכבת ישראל) toward 157: board נהריה [code 17014] 08:15 -> alight השלום [code 17046] 10:04 (service date 2026-11-02, trip `1_521246`)
5. Walk 4 min, 315 m: השלום 10:04 -> קניון עזריאלי/כביש 20 10:08
6. **bus 280** (אלקטרה אפיקים) toward אשדוד_תחנה מרכזית: board קניון עזריאלי/כביש 20 [code 21378] 10:09 -> alight ירושלים [code 12019] 10:50 (service date 2026-11-02, trip `28979431_301026`)
7. Walk 3 min, 154 m: ירושלים 10:50 -> END 10:53

Transfers (alight to next boarding, including any walk): תחנה מרכזית נהריה/שדרות הגעתון -> נהריה: 5 min; השלום -> קניון עזריאלי/כביש 20: 5 min

**Option 3:** departs Mon 2026-11-02 08:15, arrives Mon 2026-11-02 11:23; total 188 min, 1 transfer(s), walking 24 min / 1324 m

1. Walk 13 min, 760 m: START 08:15 -> נהריה 08:28
2. **rail ** (רכבת ישראל) toward 27: board נהריה [code 17014] 08:28 -> alight תל אביב ההגנה [code 17104] 10:20 (service date 2026-11-02, trip `1_521333`)
3. Walk 8 min, 410 m: תל אביב ההגנה 10:20 -> ת. רכבת ההגנה/החרש 10:28
4. **bus 281** (אלקטרה אפיקים) toward אשדוד_רובע ט"ו: board ת. רכבת ההגנה/החרש [code 20353] 10:40 -> alight ירושלים [code 12019] 11:20 (service date 2026-11-02, trip `42262647_301026`)
5. Walk 3 min, 154 m: ירושלים 11:20 -> END 11:23

Transfers (alight to next boarding, including any walk): תל אביב ההגנה -> ת. רכבת ההגנה/החרש: 20 min

| Usable? (Y/N) | Notes | Compared against / when checked |
|---|---|---|
|  |  |  |

---

## J15 — Weizmann Institute, Rehovot (מכון ויצמן למדע) → Haifa Center HaShmona (חיפה מרכז השמונה)

**Required journey #5** — PRD §7 #5 bus → train · category `bus-to-rail` · calendar rule `weekday_morning`

**Requested:** Depart at Mon 2026-11-02 08:00 (UTC+02:00)  
Request field: `departAt=2026-11-02T08:00:00+02:00`
**Calendar flags:** ordinary day
**Compare:** [Google Maps transit](https://www.google.com/maps/dir/?api=1&origin=31.907,34.8102&destination=32.8206,34.9985&travelmode=transit) · [Moovit (unofficial deep link; may not prefill)](https://moovitapp.com/?fll=31.907_34.8102&tll=32.8206_34.9985&from=Weizmann%20Institute%2C%20Rehovot&to=Haifa%20Center%20HaShmona) · Set the time yourself to **Depart at 08:00, Mon 2026-11-02** (Google's documented URL has no time parameter).
**Corpus expectation (context, not a verdict):** outcome `route`, max_duration_min = 220, max_transfers = 3, min_duration_min = 75, modes_all_of = ['bus', 'rail']

> What to check: Must contain a bus leg then a rail leg. Verify the interchange is real.

API warnings: TRANSFER_STREET_PATH_UNAVAILABLE

**API RESULT: 3 journey option(s) returned** (scheduled times).
Machine note: matches the corpus expectation `route`. This is not a judgement of quality.
Request id `ae848a4823ee4098b29fdcb152bf4b6e`.

**Option 1:** departs Mon 2026-11-02 08:00, arrives Mon 2026-11-02 10:16; total 136 min, 2 transfer(s), walking 30 min / unknown distance

1. Walk 11 min, 591 m: START 08:00 -> מכון ויצמן 08:11
2. **bus 277** (אגד) toward תל אביב יפו_מסוף רדינג: board מכון ויצמן [code 34230] 08:11 -> alight ת. רכבת ההגנה/החרש [code 25636] 08:39 (service date 2026-11-02, trip `584860123_301026`)
3. Walk 6 min, 242 m: ת. רכבת ההגנה/החרש 08:40 -> תל אביב ההגנה 08:46
4. **rail ** (רכבת ישראל) toward 106: board תל אביב ההגנה [code 17104] 08:46 -> alight חיפה מרכז [code 17016] 10:00 (service date 2026-11-02, trip `1_521012`)
5. Walk 4 min (timetable transfer; street path unavailable): חיפה מרכז 10:00 -> תחנת רכבת חיפה מרכז השמונה 10:04
6. **bus 1** (סופרבוס) toward קרית מוצקין_מרכזית הקריות: board תחנת רכבת חיפה מרכז השמונה [code 47574] 10:06 -> alight כרמלית [code 47576] 10:07 (service date 2026-11-02, trip `12078242_301026`)
7. Walk 9 min, 564 m: כרמלית 10:07 -> END 10:16

Transfers (alight to next boarding, including any walk): ת. רכבת ההגנה/החרש -> תל אביב ההגנה: 7 min; חיפה מרכז -> תחנת רכבת חיפה מרכז השמונה: 6 min

**Option 2:** departs Mon 2026-11-02 08:21, arrives Mon 2026-11-02 10:40; total 139 min, 2 transfer(s), walking 28 min / unknown distance

1. Walk 13 min, 876 m: START 08:21 -> רחובות 08:34
2. **rail ** (רכבת ישראל) toward 956: board רחובות [code 17064] 08:34 -> alight לוד [code 17058] 08:43 (service date 2026-11-02, trip `1_520832`)
3. Walk 2 min, 0 m: לוד 08:49 -> לוד 08:51
4. **rail ** (רכבת ישראל) toward 26: board לוד [code 17058] 08:51 -> alight חיפה מרכז [code 17016] 10:23 (service date 2026-11-02, trip `1_520681`)
5. Walk 4 min (timetable transfer; street path unavailable): חיפה מרכז 10:23 -> תחנת רכבת חיפה מרכז השמונה 10:27
6. **bus 1** (סופרבוס) toward קרית מוצקין_מרכזית הקריות: board תחנת רכבת חיפה מרכז השמונה [code 47574] 10:30 -> alight כרמלית [code 47576] 10:31 (service date 2026-11-02, trip `40076506_301026`)
7. Walk 9 min, 564 m: כרמלית 10:31 -> END 10:40

Transfers (alight to next boarding, including any walk): לוד -> לוד: 8 min; חיפה מרכז -> תחנת רכבת חיפה מרכז השמונה: 7 min

**Option 3:** departs Mon 2026-11-02 08:25, arrives Mon 2026-11-02 10:50; total 145 min, 2 transfer(s), walking 26 min / unknown distance

1. Walk 11 min, 591 m: START 08:25 -> מכון ויצמן 08:36
2. **bus 274** (אגד) toward תל אביב יפו_אוניברסיטת ת"א: board מכון ויצמן [code 34230] 08:36 -> alight ת. רכבת השלום [code 21022] 09:18 (service date 2026-11-02, trip `34234277_301026`)
3. Walk 2 min, 329 m: ת. רכבת השלום 09:19 -> השלום 09:21
4. **rail ** (רכבת ישראל) toward 158: board השלום [code 17046] 09:21 -> alight חיפה מרכז [code 17016] 10:35 (service date 2026-11-02, trip `1_521245`)
5. Walk 4 min (timetable transfer; street path unavailable): חיפה מרכז 10:35 -> תחנת רכבת חיפה מרכז השמונה 10:39
6. **bus 2** (סופרבוס) toward קרית אתא_יוספטל: board תחנת רכבת חיפה מרכז השמונה [code 47574] 10:40 -> alight כרמלית [code 47576] 10:41 (service date 2026-11-02, trip `15019544_301026`)
7. Walk 9 min, 564 m: כרמלית 10:41 -> END 10:50

Transfers (alight to next boarding, including any walk): ת. רכבת השלום -> השלום: 3 min; חיפה מרכז -> תחנת רכבת חיפה מרכז השמונה: 5 min

| Usable? (Y/N) | Notes | Compared against / when checked |
|---|---|---|
|  |  |  |

---

## J16 — Tel Aviv Savidor Center (תל אביב סבידור מרכז) → Technion (הטכניון)

**Required journey #6** — PRD §7 #6 train → bus · category `rail-to-bus` · calendar rule `weekday_morning`

**Requested:** Depart at Mon 2026-11-02 08:00 (UTC+02:00)  
Request field: `departAt=2026-11-02T08:00:00+02:00`
**Calendar flags:** ordinary day
**Compare:** [Google Maps transit](https://www.google.com/maps/dir/?api=1&origin=32.0836,34.7981&destination=32.7767,35.0217&travelmode=transit) · [Moovit (unofficial deep link; may not prefill)](https://moovitapp.com/?fll=32.0836_34.7981&tll=32.7767_35.0217&from=Tel%20Aviv%20Savidor%20Center&to=Technion) · Set the time yourself to **Depart at 08:00, Mon 2026-11-02** (Google's documented URL has no time parameter).
**Corpus expectation (context, not a verdict):** outcome `route`, max_duration_min = 200, max_transfers = 3, min_duration_min = 70, modes_all_of = ['rail', 'bus']

> What to check: The PRD §39 demo journey in reverse shape. Rail then bus up the Carmel.

API warnings: TRANSFER_STREET_PATH_UNAVAILABLE

**API RESULT: 3 journey option(s) returned** (scheduled times).
Machine note: matches the corpus expectation `route`. This is not a judgement of quality.
Request id `da6355f87f9543c8908a967ab070b5dd`.

**Option 1:** departs Mon 2026-11-02 08:25, arrives Mon 2026-11-02 09:52; total 87 min, 1 transfer(s), walking 8 min / 491 m

1. Walk 1 min, 27 m: START 08:25 -> תל אביב מרכז 08:26
2. **rail ** (רכבת ישראל) toward 156: board תל אביב מרכז [code 17038] 08:26 -> alight חוף הכרמל [code 17020] 09:24 (service date 2026-11-02, trip `1_521247`)
3. Walk 2 min, 189 m: חוף הכרמל 09:24 -> ת. רכבת חוף הכרמל 09:26
4. **bus 1** (אגד) toward טכניון: board ת. רכבת חוף הכרמל [code 46216] 09:33 -> alight טכניון/מעונות העמים [code 41200] 09:47 (service date 2026-11-02, trip `585633629_301026`)
5. Walk 5 min, 275 m: טכניון/מעונות העמים 09:47 -> END 09:52

Transfers (alight to next boarding, including any walk): חוף הכרמל -> ת. רכבת חוף הכרמל: 9 min

**Option 2:** departs Mon 2026-11-02 08:44, arrives Mon 2026-11-02 10:25; total 101 min, 1 transfer(s), walking 10 min / unknown distance

1. Walk 1 min, 27 m: START 08:44 -> תל אביב מרכז 08:45
2. **rail ** (רכבת ישראל) toward 404: board תל אביב מרכז [code 17038] 08:45 -> alight חיפה מרכז [code 17016] 09:52 (service date 2026-11-02, trip `1_521139`)
3. Walk 4 min (timetable transfer; street path unavailable): חיפה מרכז 09:52 -> תחנת רכבת חיפה מרכז השמונה 09:56
4. **bus 17** (אגד) toward טכניון: board תחנת רכבת חיפה מרכז השמונה [code 41540] 09:56 -> alight טכניון/מעונות העמים [code 41200] 10:20 (service date 2026-11-02, trip `12414978_301026`)
5. Walk 5 min, 275 m: טכניון/מעונות העמים 10:20 -> END 10:25

Transfers (alight to next boarding, including any walk): חיפה מרכז -> תחנת רכבת חיפה מרכז השמונה: 4 min

**Option 3:** departs Mon 2026-11-02 08:45, arrives Mon 2026-11-02 10:37; total 112 min, 3 transfer(s), walking 17 min / 1033 m

1. Walk 6 min, 431 m: START 08:45 -> ת. רכבת תל אביב - סבידור/דרך נמיר 08:51
2. **bus 825** (אגד) toward עפולה_תחנה מרכזית: board ת. רכבת תל אביב - סבידור/דרך נמיר [code 24068] 08:51 -> alight צומת אולגה [code 41694] 09:28 (service date 2026-11-02, trip `25275467_301026`)
3. Walk 2 min, 0 m: צומת אולגה 09:29 -> צומת אולגה 09:31
4. **bus 947** (אגד) toward חיפה_מרכזית חוף הכרמל: board צומת אולגה [code 41694] 09:31 -> alight ת. מרכזית חוף הכרמל/הורדה [code 42657] 10:05 (service date 2026-11-02, trip `584671969_301026`)
5. Walk 2 min, 99 m: ת. מרכזית חוף הכרמל/הורדה 10:09 -> ת. מרכזית חוף הכרמל/רציפים עירוני 10:11
6. **bus 4** (סופרבוס) toward קרית מוצקין_מרכזית הקריות: board ת. מרכזית חוף הכרמל/רציפים עירוני [code 42659] 10:11 -> alight גרנד קניון/שמחה גולן [code 47392] 10:19 (service date 2026-11-02, trip `585235871_301026`)
7. Walk 2 min, 228 m: גרנד קניון/שמחה גולן 10:19 -> גרנד קניון/שמחה גולן 10:21
8. **bus 144** (אגד) toward חיפה_אוניברסיטה: board גרנד קניון/שמחה גולן [code 42571] 10:25 -> alight טכניון/מעונות העמים [code 41200] 10:32 (service date 2026-11-02, trip `19150807_301026`)
9. Walk 5 min, 275 m: טכניון/מעונות העמים 10:32 -> END 10:37

Transfers (alight to next boarding, including any walk): צומת אולגה -> צומת אולגה: 3 min; ת. מרכזית חוף הכרמל/הורדה -> ת. מרכזית חוף הכרמל/רציפים עירוני: 6 min; גרנד קניון/שמחה גולן -> גרנד קניון/שמחה גולן: 6 min

| Usable? (Y/N) | Notes | Compared against / when checked |
|---|---|---|
|  |  |  |

---

## J17 — Modi'in Center (מודיעין מרכז) → Ben Gurion Airport T3 (נתב"ג טרמינל 3)

category `bus-to-rail` · calendar rule `weekday_morning`

**Requested:** Depart at Mon 2026-11-02 08:00 (UTC+02:00)  
Request field: `departAt=2026-11-02T08:00:00+02:00`
**Calendar flags:** ordinary day
**Compare:** [Google Maps transit](https://www.google.com/maps/dir/?api=1&origin=31.9017,35.0074&destination=32.0004,34.8705&travelmode=transit) · [Moovit (unofficial deep link; may not prefill)](https://moovitapp.com/?fll=31.9017_35.0074&tll=32.0004_34.8705&from=Modi%27in%20Center&to=Ben%20Gurion%20Airport%20T3) · Set the time yourself to **Depart at 08:00, Mon 2026-11-02** (Google's documented URL has no time parameter).
**Corpus expectation (context, not a verdict):** outcome `route`, max_duration_min = 90, max_transfers = 2, min_duration_min = 15, modes_any_of = ['rail', 'bus']

> What to check: Airport access. A wrong answer here is very visible to a real user.

API warnings: TRANSFER_STREET_PATH_UNAVAILABLE

**API RESULT: 3 journey option(s) returned** (scheduled times).
Machine note: matches the corpus expectation `route`. This is not a judgement of quality.
Request id `b49e339474c84064a5638256b597ed88`.

**Option 1:** departs Mon 2026-11-02 08:06, arrives Mon 2026-11-02 08:36; total 30 min, 1 transfer(s), walking 10 min / unknown distance

1. Walk 7 min, 402 m: START 08:06 -> עמק איילון/תלתן 08:13
2. **bus 58** (קווים) toward בייק פארק: board עמק איילון/תלתן [code 34155] 08:13 -> alight ת. רכבת מודיעין מרכז [code 33093] 08:14 (service date 2026-11-02, trip `28361843_301026`)
3. Walk 2 min (timetable transfer; street path unavailable): ת. רכבת מודיעין מרכז 08:14 -> מודיעין מרכז 08:16
4. **rail ** (רכבת ישראל) toward 106: board מודיעין מרכז [code 17002] 08:18 -> alight נתב''ג [code 17090] 08:35 (service date 2026-11-02, trip `1_521012`)
5. Walk 1 min, 4 m: נתב''ג 08:35 -> END 08:36

Transfers (alight to next boarding, including any walk): ת. רכבת מודיעין מרכז -> מודיעין מרכז: 4 min

**Option 2:** departs Mon 2026-11-02 08:37, arrives Mon 2026-11-02 09:06; total 29 min, 1 transfer(s), walking 7 min / unknown distance

1. Walk 4 min, 189 m: START 08:37 -> קניון עזריאלי מודיעין 08:41
2. **bus 54** (קווים) toward מ.מסחרי לב רעות: board קניון עזריאלי מודיעין [code 35177] 08:41 -> alight ת. רכבת מודיעין מרכז [code 33093] 08:41 (service date 2026-11-02, trip `36207168_301026`)
3. Walk 2 min (timetable transfer; street path unavailable): ת. רכבת מודיעין מרכז 08:41 -> מודיעין מרכז 08:43
4. **rail ** (רכבת ישראל) toward 158: board מודיעין מרכז [code 17002] 08:48 -> alight נתב''ג [code 17090] 09:05 (service date 2026-11-02, trip `1_521245`)
5. Walk 1 min, 4 m: נתב''ג 09:05 -> END 09:06

Transfers (alight to next boarding, including any walk): ת. רכבת מודיעין מרכז -> מודיעין מרכז: 7 min

**Option 3:** departs Mon 2026-11-02 09:07, arrives Mon 2026-11-02 09:36; total 29 min, 1 transfer(s), walking 7 min / unknown distance

1. Walk 4 min, 189 m: START 09:07 -> קניון עזריאלי מודיעין 09:11
2. **bus 54** (קווים) toward רעות: board קניון עזריאלי מודיעין [code 35177] 09:11 -> alight ת. רכבת מודיעין מרכז [code 33093] 09:11 (service date 2026-11-02, trip `36206990_301026`)
3. Walk 2 min (timetable transfer; street path unavailable): ת. רכבת מודיעין מרכז 09:11 -> מודיעין מרכז 09:13
4. **rail ** (רכבת ישראל) toward 108: board מודיעין מרכז [code 17002] 09:18 -> alight נתב''ג [code 17090] 09:35 (service date 2026-11-02, trip `1_521080`)
5. Walk 1 min, 4 m: נתב''ג 09:35 -> END 09:36

Transfers (alight to next boarding, including any walk): ת. רכבת מודיעין מרכז -> מודיעין מרכז: 7 min

| Usable? (Y/N) | Notes | Compared against / when checked |
|---|---|---|
|  |  |  |

---

## J18 — Beersheba North University (באר שבע צפון אוניברסיטה) → Bar-Ilan University (אוניברסיטת בר אילן)

category `rail-to-bus` · calendar rule `weekday_morning`

**Requested:** Depart at Mon 2026-11-02 08:00 (UTC+02:00)  
Request field: `departAt=2026-11-02T08:00:00+02:00`
**Calendar flags:** ordinary day
**Compare:** [Google Maps transit](https://www.google.com/maps/dir/?api=1&origin=31.262,34.8016&destination=32.07,34.8433&travelmode=transit) · [Moovit (unofficial deep link; may not prefill)](https://moovitapp.com/?fll=31.262_34.8016&tll=32.07_34.8433&from=Beersheba%20North%20University&to=Bar-Ilan%20University) · Set the time yourself to **Depart at 08:00, Mon 2026-11-02** (Google's documented URL has no time parameter).
**Corpus expectation (context, not a verdict):** outcome `route`, max_duration_min = 230, max_transfers = 3, min_duration_min = 75, modes_all_of = ['rail', 'bus']

> What to check: Campus to campus, two operators, at least one interchange.

**API RESULT: 3 journey option(s) returned** (scheduled times).
Machine note: matches the corpus expectation `route`. This is not a judgement of quality.
Request id `44371964eb4841eb9e90e9baf3d5badf`.

**Option 1:** departs Mon 2026-11-02 08:00, arrives Mon 2026-11-02 10:04; total 124 min, 3 transfer(s), walking 18 min / 1233 m

1. Walk 4 min, 215 m: START 08:00 -> מרפאות חוץ סורוקה/אוניברסיטת בן גוריון 08:04
2. **bus 5** (דן באר שבע) toward מסוף חצרים: board מרפאות חוץ סורוקה/אוניברסיטת בן גוריון [code 13949] 08:04 -> alight מרכז רפואי סורוקה/אוניברסיטת בן גוריון [code 15332] 08:05 (service date 2026-11-02, trip `585112451_301026`)
3. Walk 2 min, 290 m: מרכז רפואי סורוקה/אוניברסיטת בן גוריון 08:05 -> מרכז רפואי סורוקה/אוניברסיטת בן גוריון 08:07
4. **bus 370** (מטרופולין) toward תל אביב יפו_תחנה מרכזית: board מרכז רפואי סורוקה/אוניברסיטת בן גוריון [code 15333] 08:07 -> alight מחלף לה גווארדייה [code 21274] 09:16 (service date 2026-11-02, trip `2221042_301026`)
5. Walk 2 min, 126 m: מחלף לה גווארדייה 09:19 -> מחלף לה גווארדייה 09:21
6. **bus 31** (דן) toward בני ברק_בית עלמין: board מחלף לה גווארדייה [code 22934] 09:21 -> alight הירדן/ אלוף שדה [code 21319] 09:39 (service date 2026-11-02, trip `4071661_011126`)
7. Walk 2 min, 150 m: הירדן/ אלוף שדה 09:39 -> הירדן/אלוף שדה 09:41
8. **bus 32** (דן) toward גבעת שמואל_הרב שלמה גורן: board הירדן/אלוף שדה [code 21569] 09:47 -> alight מרכז וואהל/מקס ואנה ווב [code 32907] 09:56 (service date 2026-11-02, trip `36034216_011126`)
9. Walk 8 min, 452 m: מרכז וואהל/מקס ואנה ווב 09:56 -> END 10:04

Transfers (alight to next boarding, including any walk): מרכז רפואי סורוקה/אוניברסיטת בן גוריון -> מרכז רפואי סורוקה/אוניברסיטת בן גוריון: 2 min; מחלף לה גווארדייה -> מחלף לה גווארדייה: 5 min; הירדן/ אלוף שדה -> הירדן/אלוף שדה: 8 min

**Option 2:** departs Mon 2026-11-02 08:00, arrives Mon 2026-11-02 09:56; total 116 min, 4 transfer(s), walking 20 min / 1083 m

1. Walk 4 min, 215 m: START 08:00 -> מרפאות חוץ סורוקה/אוניברסיטת בן גוריון 08:04
2. **bus 5** (דן באר שבע) toward מסוף חצרים: board מרפאות חוץ סורוקה/אוניברסיטת בן גוריון [code 13949] 08:04 -> alight מרכז רפואי סורוקה/אוניברסיטת בן גוריון [code 15332] 08:05 (service date 2026-11-02, trip `585112451_301026`)
3. Walk 2 min, 290 m: מרכז רפואי סורוקה/אוניברסיטת בן גוריון 08:05 -> מרכז רפואי סורוקה/אוניברסיטת בן גוריון 08:07
4. **bus 370** (מטרופולין) toward תל אביב יפו_תחנה מרכזית: board מרכז רפואי סורוקה/אוניברסיטת בן גוריון [code 15333] 08:07 -> alight מחלף לה גווארדייה [code 21274] 09:16 (service date 2026-11-02, trip `2221042_301026`)
5. Walk 2 min, 126 m: מחלף לה גווארדייה 09:17 -> מחלף לה גווארדייה 09:19
6. **bus 2** (דן) toward הארגזים: board מחלף לה גווארדייה [code 22934] 09:19 -> alight שכונת הארגזים/לח''י [code 25669] 09:25 (service date 2026-11-02, trip `44236243_011126`)
7. Walk 2 min, 0 m: שכונת הארגזים/לח''י 09:27 -> שכונת הארגזים/לח''י 09:29
8. **bus 41** (דן) toward פתח תקווה_מסוף משה ארנס: board שכונת הארגזים/לח''י [code 25669] 09:29 -> alight עמק האלה/דרך שיבא [code 31010] 09:39 (service date 2026-11-02, trip `38113270_011126`)
9. Walk 2 min, 0 m: עמק האלה/דרך שיבא 09:39 -> עמק האלה/דרך שיבא 09:41
10. **bus 48** (מטרופולין) toward פתח תקווה_מ.רפואי שניידר: board עמק האלה/דרך שיבא [code 31010] 09:41 -> alight מרכז וואהל/מקס ואנה ווב [code 32907] 09:48 (service date 2026-11-02, trip `586222499_301026`)
11. Walk 8 min, 452 m: מרכז וואהל/מקס ואנה ווב 09:48 -> END 09:56

Transfers (alight to next boarding, including any walk): מרכז רפואי סורוקה/אוניברסיטת בן גוריון -> מרכז רפואי סורוקה/אוניברסיטת בן גוריון: 2 min; מחלף לה גווארדייה -> מחלף לה גווארדייה: 3 min; שכונת הארגזים/לח''י -> שכונת הארגזים/לח''י: 4 min; עמק האלה/דרך שיבא -> עמק האלה/דרך שיבא: 2 min

**Option 3:** departs Mon 2026-11-02 08:17, arrives Mon 2026-11-02 10:11; total 114 min, 1 transfer(s), walking 20 min / 1060 m

1. Walk 10 min, 608 m: START 08:17 -> מרכז רפואי סורוקה/אוניברסיטת בן גוריון 08:27
2. **bus 669** (מטרופולין) toward רעננה_מסוף אוטובוסים: board מרכז רפואי סורוקה/אוניברסיטת בן גוריון [code 15333] 08:27 -> alight מחלף מסובים [code 33432] 09:47 (service date 2026-11-02, trip `41490656_301026`)
3. Walk 2 min, 0 m: מחלף מסובים 09:47 -> מחלף מסובים 09:49
4. **bus 145** (סופרבוס) toward פתח תקווה_רכבת קרית אריה: board מחלף מסובים [code 33432] 09:57 -> alight מרכז וואהל/מקס ואנה ווב [code 32907] 10:03 (service date 2026-11-02, trip `585990270_301026`)
5. Walk 8 min, 452 m: מרכז וואהל/מקס ואנה ווב 10:03 -> END 10:11

Transfers (alight to next boarding, including any walk): מחלף מסובים -> מחלף מסובים: 10 min

| Usable? (Y/N) | Notes | Compared against / when checked |
|---|---|---|
|  |  |  |

---

## J19 — Herzliya Station (תחנת רכבת הרצליה) → Beilinson Hospital, Petah Tikva (בית חולים בילינסון)

**Required journey #7** — PRD §7 #7 at least one transfer · category `with-transfer` · calendar rule `weekday_morning`

**Requested:** Depart at Mon 2026-11-02 08:00 (UTC+02:00)  
Request field: `departAt=2026-11-02T08:00:00+02:00`
**Calendar flags:** ordinary day
**Compare:** [Google Maps transit](https://www.google.com/maps/dir/?api=1&origin=32.1656,34.8095&destination=32.087,34.858&travelmode=transit) · [Moovit (unofficial deep link; may not prefill)](https://moovitapp.com/?fll=32.1656_34.8095&tll=32.087_34.858&from=Herzliya%20Station&to=Beilinson%20Hospital%2C%20Petah%20Tikva) · Set the time yourself to **Depart at 08:00, Mon 2026-11-02** (Google's documented URL has no time parameter).
**Corpus expectation (context, not a verdict):** outcome `route`, max_duration_min = 100, max_transfers = 3, min_duration_min = 20, min_transfers = 1

> What to check: Must transfer. Is the transfer window realistic, not a 2-minute cross-platform miracle?

**API RESULT: 3 journey option(s) returned** (scheduled times).
Machine note: matches the corpus expectation `route`. This is not a judgement of quality.
Request id `4440e16767ca4f67a0d63cba0b401fc8`.

**Option 1:** departs Mon 2026-11-02 08:03, arrives Mon 2026-11-02 09:14; total 71 min, 1 transfer(s), walking 13 min / 622 m

1. Walk 4 min, 184 m: START 08:03 -> גלגלי הפלדה/יוחנן הסנדלר 08:07
2. **bus 91** (מטרופולין) toward תל אביב יפו_מסוף הטייסים: board גלגלי הפלדה/יוחנן הסנדלר [code 26761] 08:07 -> alight דרך בר לב/דרך משה דיין [code 21538] 08:36 (service date 2026-11-02, trip `25080591_011126`)
3. Walk 2 min, 0 m: דרך בר לב/דרך משה דיין 08:36 -> דרך בר לב/דרך משה דיין 08:38
4. **bus 41** (דן) toward פתח תקווה_מסוף משה ארנס: board דרך בר לב/דרך משה דיין [code 21538] 08:39 -> alight בריכת נווה עוז/דרך יצחק רבין [code 38468] 09:07 (service date 2026-11-02, trip `8039658_011126`)
5. Walk 7 min, 438 m: בריכת נווה עוז/דרך יצחק רבין 09:07 -> END 09:14

Transfers (alight to next boarding, including any walk): דרך בר לב/דרך משה דיין -> דרך בר לב/דרך משה דיין: 3 min

**Option 2:** departs Mon 2026-11-02 08:03, arrives Mon 2026-11-02 08:57; total 54 min, 2 transfer(s), walking 15 min / 878 m

1. Walk 4 min, 184 m: START 08:03 -> גלגלי הפלדה/יוחנן הסנדלר 08:07
2. **bus 91** (מטרופולין) toward תל אביב יפו_מסוף הטייסים: board גלגלי הפלדה/יוחנן הסנדלר [code 26761] 08:07 -> alight ת.רק''ל שאול המלך/דרך מנחם בגין [code 20837] 08:24 (service date 2026-11-02, trip `25080591_011126`)
3. Walk 2 min, 126 m: ת.רק''ל שאול המלך/דרך מנחם בגין 08:27 -> שאול המלך 08:29
4. **light_rail 1** (תבל) toward פתח תקווה_ת. מרכזית פתח תקווה: board שאול המלך [code 20709] 08:29 -> alight שחם [code 36313] 08:45 (service date 2026-11-02, trip `585428502_301026`)
5. Walk 2 min, 124 m: שחם 08:45 -> ת.רק''ל שחם/דרך יצחק רבין 08:47
6. **bus 75** (מטרופולין) toward גני תקווה_מרכז גני תקווה: board ת.רק''ל שחם/דרך יצחק רבין [code 36570] 08:48 -> alight דרך יצחק רבין/דגניה [code 35485] 08:50 (service date 2026-11-02, trip `586235023_011126`)
7. Walk 7 min, 444 m: דרך יצחק רבין/דגניה 08:50 -> END 08:57

Transfers (alight to next boarding, including any walk): ת.רק''ל שאול המלך/דרך מנחם בגין -> שאול המלך: 5 min; שחם -> ת.רק''ל שחם/דרך יצחק רבין: 3 min

**Option 3:** departs Mon 2026-11-02 08:06, arrives Mon 2026-11-02 09:01; total 55 min, 3 transfer(s), walking 17 min / 878 m

1. Walk 4 min, 184 m: START 08:06 -> גלגלי הפלדה/יוחנן הסנדלר 08:10
2. **bus 90** (מטרופולין) toward תל אביב יפו_מסוף כרמלית: board גלגלי הפלדה/יוחנן הסנדלר [code 26761] 08:10 -> alight סינמה סיטי/כביש 2 [code 26966] 08:14 (service date 2026-11-02, trip `19637410_011126`)
3. Walk 2 min, 0 m: סינמה סיטי/כביש 2 08:16 -> סינמה סיטי/כביש 2 08:18
4. **bus 347** (מטרופולין) toward תל אביב יפו_תחנה מרכזית: board סינמה סיטי/כביש 2 [code 26966] 08:18 -> alight ת.רק''ל שאול המלך/דרך מנחם בגין [code 20837] 08:31 (service date 2026-11-02, trip `42548405_301026`)
5. Walk 2 min, 126 m: ת.רק''ל שאול המלך/דרך מנחם בגין 08:32 -> שאול המלך 08:34
6. **light_rail 1** (תבל) toward פתח תקווה_ת. מרכזית פתח תקווה: board שאול המלך [code 20709] 08:34 -> alight שחם [code 36313] 08:50 (service date 2026-11-02, trip `585373596_301026`)
7. Walk 2 min, 124 m: שחם 08:50 -> ת.רק''ל שחם/דרך יצחק רבין 08:52
8. **bus 143** (סופרבוס) toward חולון_מוזיאון אגד: board ת.רק''ל שחם/דרך יצחק רבין [code 36570] 08:53 -> alight דרך יצחק רבין/דגניה [code 35485] 08:54 (service date 2026-11-02, trip `586111406_301026`)
9. Walk 7 min, 444 m: דרך יצחק רבין/דגניה 08:54 -> END 09:01

Transfers (alight to next boarding, including any walk): סינמה סיטי/כביש 2 -> סינמה סיטי/כביש 2: 4 min; ת.רק''ל שאול המלך/דרך מנחם בגין -> שאול המלך: 3 min; שחם -> ת.רק''ל שחם/דרך יצחק רבין: 3 min

| Usable? (Y/N) | Notes | Compared against / when checked |
|---|---|---|
|  |  |  |

---

## J20 — Netanya Station (תחנת רכבת נתניה) → Mahane Yehuda Market (שוק מחנה יהודה)

category `with-transfer` · calendar rule `weekday_midday`

**Requested:** Depart at Tue 2026-11-03 13:00 (UTC+02:00)  
Request field: `departAt=2026-11-03T13:00:00+02:00`
**Calendar flags:** ordinary day
**Compare:** [Google Maps transit](https://www.google.com/maps/dir/?api=1&origin=32.3097,34.8619&destination=31.7853,35.2124&travelmode=transit) · [Moovit (unofficial deep link; may not prefill)](https://moovitapp.com/?fll=32.3097_34.8619&tll=31.7853_35.2124&from=Netanya%20Station&to=Mahane%20Yehuda%20Market) · Set the time yourself to **Depart at 13:00, Tue 2026-11-03** (Google's documented URL has no time parameter).
**Corpus expectation (context, not a verdict):** outcome `route`, max_duration_min = 200, max_transfers = 3, min_duration_min = 60, min_transfers = 1

> What to check: Coastal rail then Jerusalem light rail. Checks cross-operator chaining.

**API RESULT: 3 journey option(s) returned** (scheduled times).
Machine note: matches the corpus expectation `route`. This is not a judgement of quality.
Request id `84c096ec8c57462d8a06169b143f6ab8`.

**Option 1:** departs Tue 2026-11-03 13:03, arrives Tue 2026-11-03 15:11; total 128 min, 2 transfer(s), walking 31 min / 2041 m

1. Walk 15 min, 889 m: START 13:03 -> בית ספר טשרניחובסקי/בן צבי 13:18
2. **bus 611** (מטרופולין) toward תל אביב יפו_תחנה מרכזית: board בית ספר טשרניחובסקי/בן צבי [code 39204] 13:18 -> alight ת. רכבת תל אביב - סבידור/דרך נמיר [code 20349] 13:51 (service date 2026-11-03, trip `42518425_301026`)
3. Walk 5 min, 297 m: ת. רכבת תל אביב - סבידור/דרך נמיר 14:00 -> ת.רכבת תל אביב - סבידור/רציפים B 14:05
4. **bus 490** (אגד) toward ירושלים_אזור תעשיה תלפיות: board ת.רכבת תל אביב - סבידור/רציפים B [code 20740] 14:05 -> alight הרצוג/ניות [code 978] 14:49 (service date 2026-11-03, trip `584961616_301026`)
5. Walk 2 min, 244 m: הרצוג/ניות 14:49 -> הרצוג/רסקו 14:51
6. **bus 92** (סופרבוס) toward גילה: board הרצוג/רסקו [code 949] 14:53 -> alight עליאש [code 9862] 15:02 (service date 2026-11-03, trip `584900831_011126`)
7. Walk 9 min, 611 m: עליאש 15:02 -> END 15:11

Transfers (alight to next boarding, including any walk): ת. רכבת תל אביב - סבידור/דרך נמיר -> ת.רכבת תל אביב - סבידור/רציפים B: 14 min; הרצוג/ניות -> הרצוג/רסקו: 4 min

**Option 2:** departs Tue 2026-11-03 13:03, arrives Tue 2026-11-03 15:02; total 119 min, 3 transfer(s), walking 25 min / 1507 m

1. Walk 15 min, 889 m: START 13:03 -> בית ספר טשרניחובסקי/בן צבי 13:18
2. **bus 611** (מטרופולין) toward תל אביב יפו_תחנה מרכזית: board בית ספר טשרניחובסקי/בן צבי [code 39204] 13:18 -> alight מחלף הסירה לדרום [code 20142] 13:37 (service date 2026-11-03, trip `42518425_301026`)
3. Walk 2 min, 0 m: מחלף הסירה לדרום 13:37 -> מחלף הסירה לדרום 13:39
4. **bus 91** (מטרופולין) toward תל אביב יפו_מסוף הטייסים: board מחלף הסירה לדרום [code 20142] 13:39 -> alight ת. רכבת השלום [code 21023] 13:56 (service date 2026-11-03, trip `19065382_011126`)
5. Walk 2 min, 226 m: ת. רכבת השלום 14:07 -> השלום 14:09
6. **rail ** (רכבת ישראל) toward 747: board השלום [code 17046] 14:09 -> alight ירושלים/יצחק נבון [code 17118] 14:52 (service date 2026-11-03, trip `1_520931`)
7. Walk 2 min, 162 m: ירושלים/יצחק נבון 14:52 -> ת. מרכזית ירושלים/יפו 14:54
8. **bus 74** (סופרבוס) toward חומת שמואל: board ת. מרכזית ירושלים/יפו [code 4156] 14:54 -> alight שוק מחנה יהודה/אגריפס [code 3523] 14:58 (service date 2026-11-03, trip `584795009_011126`)
9. Walk 4 min, 230 m: שוק מחנה יהודה/אגריפס 14:58 -> END 15:02

Transfers (alight to next boarding, including any walk): מחלף הסירה לדרום -> מחלף הסירה לדרום: 2 min; ת. רכבת השלום -> השלום: 13 min; ירושלים/יצחק נבון -> ת. מרכזית ירושלים/יפו: 2 min

**Option 3:** departs Tue 2026-11-03 13:04, arrives Tue 2026-11-03 15:11; total 127 min, 3 transfer(s), walking 25 min / 1660 m

1. Walk 7 min, 371 m: START 13:04 -> האר''י/הרב חרל''פ 13:11
2. **bus 72** (אקסטרה) toward תחנת הרכבת: board האר''י/הרב חרל''פ [code 39238] 13:11 -> alight שד. בן צבי/היהלומן אברהם [code 39216] 13:14 (service date 2026-11-03, trip `585092382_011126`)
3. Walk 2 min, 137 m: שד. בן צבי/היהלומן אברהם 13:14 -> בן צבי/הגר''א 13:16
4. **bus 611** (מטרופולין) toward תל אביב יפו_תחנה מרכזית: board בן צבי/הגר''א [code 39215] 13:16 -> alight ת. רכבת תל אביב - סבידור/דרך נמיר [code 20349] 13:51 (service date 2026-11-03, trip `42518425_301026`)
5. Walk 5 min, 297 m: ת. רכבת תל אביב - סבידור/דרך נמיר 14:00 -> ת.רכבת תל אביב - סבידור/רציפים B 14:05
6. **bus 490** (אגד) toward ירושלים_אזור תעשיה תלפיות: board ת.רכבת תל אביב - סבידור/רציפים B [code 20740] 14:05 -> alight הרצוג/ניות [code 978] 14:49 (service date 2026-11-03, trip `584961616_301026`)
7. Walk 2 min, 244 m: הרצוג/ניות 14:49 -> הרצוג/רסקו 14:51
8. **bus 92** (סופרבוס) toward גילה: board הרצוג/רסקו [code 949] 14:53 -> alight עליאש [code 9862] 15:02 (service date 2026-11-03, trip `584900831_011126`)
9. Walk 9 min, 611 m: עליאש 15:02 -> END 15:11

Transfers (alight to next boarding, including any walk): שד. בן צבי/היהלומן אברהם -> בן צבי/הגר''א: 2 min; ת. רכבת תל אביב - סבידור/דרך נמיר -> ת.רכבת תל אביב - סבידור/רציפים B: 14 min; הרצוג/ניות -> הרצוג/רסקו: 4 min

| Usable? (Y/N) | Notes | Compared against / when checked |
|---|---|---|
|  |  |  |

---

## J21 — Tel Aviv Savidor Center (תל אביב סבידור מרכז) → Ben Gurion Airport T3 (נתב"ג טרמינל 3)

**Required journey #8** — PRD §7 #8 late night · category `late-night` · calendar rule `late_night`

**Requested:** Depart at Tue 2026-11-03 23:40 (UTC+02:00)  
Request field: `departAt=2026-11-03T23:40:00+02:00`
**Calendar flags:** ordinary day
**Compare:** [Google Maps transit](https://www.google.com/maps/dir/?api=1&origin=32.0836,34.7981&destination=32.0004,34.8705&travelmode=transit) · [Moovit (unofficial deep link; may not prefill)](https://moovitapp.com/?fll=32.0836_34.7981&tll=32.0004_34.8705&from=Tel%20Aviv%20Savidor%20Center&to=Ben%20Gurion%20Airport%20T3) · Set the time yourself to **Depart at 23:40, Tue 2026-11-03** (Google's documented URL has no time parameter).
**Corpus expectation (context, not a verdict):** outcome `route`, max_duration_min = 120, max_transfers = 2, min_duration_min = 10, modes_any_of = ['rail', 'bus']

> What to check: Airport rail runs deep into the night. Does the engine know that?

**API RESULT: 3 journey option(s) returned** (scheduled times).
Machine note: matches the corpus expectation `route`. This is not a judgement of quality.
Request id `1d84cfbcb7ed4725b8817362bb32b590`.

**Option 1:** departs Tue 2026-11-03 23:40, arrives Wed 2026-11-04 00:04; total 24 min, 0 transfer(s), walking 2 min / 31 m

1. Walk 1 min, 27 m: START 23:40 -> תל אביב מרכז 23:41
2. **rail ** (רכבת ישראל) toward 785: board תל אביב מרכז [code 17038] 23:41 -> alight נתב''ג [code 17090] 00:03 (service date 2026-11-03, trip `1_520882`)
3. Walk 1 min, 4 m: נתב''ג 00:03 -> END 00:04

Transfers (alight to next boarding, including any walk): none

**Option 2:** departs Wed 2026-11-04 00:36, arrives Wed 2026-11-04 00:56; total 20 min, 0 transfer(s), walking 2 min / 31 m

1. Walk 1 min, 27 m: START 00:36 -> תל אביב מרכז 00:37
2. **rail ** (רכבת ישראל) toward 137: board תל אביב מרכז [code 17038] 00:37 -> alight נתב''ג [code 17090] 00:55 (service date 2026-11-03, trip `1_520897`)
3. Walk 1 min, 4 m: נתב''ג 00:55 -> END 00:56

Transfers (alight to next boarding, including any walk): none

**Option 3:** departs Wed 2026-11-04 00:46, arrives Wed 2026-11-04 01:02; total 16 min, 0 transfer(s), walking 2 min / 31 m

1. Walk 1 min, 27 m: START 00:46 -> תל אביב מרכז 00:47
2. **rail ** (רכבת ישראל) toward 9701: board תל אביב מרכז [code 17038] 00:47 -> alight נתב''ג [code 17090] 01:01 (service date 2026-11-04, trip `1_526105`)
3. Walk 1 min, 4 m: נתב''ג 01:01 -> END 01:02

Transfers (alight to next boarding, including any walk): none

| Usable? (Y/N) | Notes | Compared against / when checked |
|---|---|---|
|  |  |  |

---

## J22 — Dizengoff Center (דיזנגוף סנטר) → Ramat Gan Bursa (רמת גן בורסה)

**Required journey #9** — PRD §7 #9 crossing a service-day boundary · category `service-day-boundary` · calendar rule `after_midnight`

**Requested:** Depart at Wed 2026-11-04 02:30 (UTC+02:00)  
Request field: `departAt=2026-11-04T02:30:00+02:00`
**Calendar flags:** ordinary day
**Compare:** [Google Maps transit](https://www.google.com/maps/dir/?api=1&origin=32.0757,34.7748&destination=32.0838,34.8044&travelmode=transit) · [Moovit (unofficial deep link; may not prefill)](https://moovitapp.com/?fll=32.0757_34.7748&tll=32.0838_34.8044&from=Dizengoff%20Center&to=Ramat%20Gan%20Bursa) · Set the time yourself to **Depart at 02:30, Wed 2026-11-04** (Google's documented URL has no time parameter).
**Corpus expectation (context, not a verdict):** outcome `either`, max_duration_min = 180, min_duration_min = 5

> What to check: THE GTFS trap: trips after midnight belong to the previous service day with times like 25:30:00. Either a valid night route or a clean no-route is acceptable. A crash, an empty result with no explanation, or a route departing 20 hours later is a FAIL.

**API RESULT: 3 journey option(s) returned** (scheduled times).
Request id `142c755d62ee468eacfbaedce8ef7500`.

**Option 1:** departs Wed 2026-11-04 02:39, arrives Wed 2026-11-04 04:19; total 100 min, 1 transfer(s), walking 17 min / 1517 m

1. Walk 3 min, 135 m: START 02:39 -> דיזנגוף סנטר/דיזנגוף 02:42
2. **bus 445** (מטרופולין) toward נמל תעופה בן גוריון_טרמינל 3: board דיזנגוף סנטר/דיזנגוף [code 25565] 02:42 -> alight נתב''ג טרמינל 3/קומת תח''צ [code 35275] 03:22 (service date 2026-11-04, trip `53738960_301026`)
3. Walk 2 min, 616 m: נתב''ג טרמינל 3/קומת תח''צ 03:22 -> נתב''ג 03:24
4. **rail ** (רכבת ישראל) toward 9706: board נתב''ג [code 17090] 03:53 -> alight תל אביב מרכז [code 17038] 04:07 (service date 2026-11-04, trip `1_523448`)
5. Walk 12 min, 766 m: תל אביב מרכז 04:07 -> END 04:19

Transfers (alight to next boarding, including any walk): נתב''ג טרמינל 3/קומת תח''צ -> נתב''ג: 31 min

**Option 2:** departs Wed 2026-11-04 04:57, arrives Wed 2026-11-04 05:38; total 41 min, 1 transfer(s), walking 9 min / 502 m

1. Walk 3 min, 135 m: START 04:57 -> דיזנגוף סנטר/דיזנגוף 05:00
2. **bus 172** (דן) toward חולון_מסוף אזור תעשייה: board דיזנגוף סנטר/דיזנגוף [code 25565] 05:00 -> alight שוקן/דרך שלמה [code 20388] 05:10 (service date 2026-11-04, trip `584954845_011126`)
3. Walk 2 min, 118 m: שוקן/דרך שלמה 05:10 -> דרך שלמה/שוקן 05:12
4. **bus 42** (דן) toward תל אביב יפו_קריית עתידים: board דרך שלמה/שוקן [code 20097] 05:18 -> alight ת.רק''ל אבא הלל [code 26248] 05:34 (service date 2026-11-04, trip `46019340_011126`)
5. Walk 4 min, 249 m: ת.רק''ל אבא הלל 05:34 -> END 05:38

Transfers (alight to next boarding, including any walk): שוקן/דרך שלמה -> דרך שלמה/שוקן: 8 min

**Option 3:** departs Wed 2026-11-04 04:57, arrives Wed 2026-11-04 05:24; total 27 min, 2 transfer(s), walking 12 min / 488 m

1. Walk 3 min, 135 m: START 04:57 -> דיזנגוף סנטר/דיזנגוף 05:00
2. **bus 172** (דן) toward חולון_מסוף אזור תעשייה: board דיזנגוף סנטר/דיזנגוף [code 25565] 05:00 -> alight שד' רוטשילד/שיינקין [code 25587] 05:03 (service date 2026-11-04, trip `584954845_011126`)
3. Walk 2 min, 112 m: שד' רוטשילד/שיינקין 05:05 -> שד' רוטשילד/שיינקין 05:07
4. **bus 23** (דן) toward גבעתיים_כורזין: board שד' רוטשילד/שיינקין [code 21732] 05:07 -> alight ת.רק''ל יהודית/דרך מנחם בגין [code 20727] 05:11 (service date 2026-11-04, trip `585553022_011126`)
5. Walk 2 min, 0 m: ת.רק''ל יהודית/דרך מנחם בגין 05:11 -> ת.רק''ל יהודית/דרך מנחם בגין 05:13
6. **bus 50** (דן) toward פתח תקווה_רכבת סגולה: board ת.רק''ל יהודית/דרך מנחם בגין [code 20727] 05:13 -> alight ת.רק''ל אבא הלל/דרך ז'בוטינסקי [code 21644] 05:19 (service date 2026-11-04, trip `585465470_011126`)
7. Walk 5 min, 241 m: ת.רק''ל אבא הלל/דרך ז'בוטינסקי 05:19 -> END 05:24

Transfers (alight to next boarding, including any walk): שד' רוטשילד/שיינקין -> שד' רוטשילד/שיינקין: 4 min; ת.רק''ל יהודית/דרך מנחם בגין -> ת.רק''ל יהודית/דרך מנחם בגין: 2 min

| Usable? (Y/N) | Notes | Compared against / when checked |
|---|---|---|
|  |  |  |

---

## J23 — Har Karkom, central Negev (הר כרכום) → Metula (מטולה)

**Required journey #10** — PRD §7 #10 no reasonable transit route · category `no-reasonable-route` · calendar rule `after_midnight`

**Requested:** Depart at Wed 2026-11-04 02:30 (UTC+02:00)  
Request field: `departAt=2026-11-04T02:30:00+02:00`
**Calendar flags:** ordinary day
**Compare:** [Google Maps transit](https://www.google.com/maps/dir/?api=1&origin=30.28,34.74&destination=33.2778,35.5786&travelmode=transit) · [Moovit (unofficial deep link; may not prefill)](https://moovitapp.com/?fll=30.28_34.74&tll=33.2778_35.5786&from=Har%20Karkom%2C%20central%20Negev&to=Metula) · Set the time yourself to **Depart at 02:30, Wed 2026-11-04** (Google's documented URL has no time parameter).
**Corpus expectation (context, not a verdict):** outcome `no-route`

> What to check: Origin is 23.5 km from the nearest stop in the feed — measured, not assumed. No walking budget reaches transit, so 'no route' is the only correct answer. An itinerary here means the engine is inventing access.

**API RESULT: NO ROUTE** — a valid search inside coverage returned no journey. The API does not state a cause (no service, walking limit and data gaps look alike).
Machine note: matches the corpus expectation `no-route`. This is not a judgement of quality.
Request id `9974c21241f04935813dc84ac1b58a37`.

| Usable? (Y/N) | Notes | Compared against / when checked |
|---|---|---|
|  |  |  |

---

## J24 — Masada Junction (צומת מצדה) → Beersheba Central (באר שבע מרכז)

category `long-walk-accessibility` · calendar rule `weekday_midday`

**Requested:** Depart at Tue 2026-11-03 13:00 (UTC+02:00)  
Request field: `departAt=2026-11-03T13:00:00+02:00`
**Calendar flags:** ordinary day
**Compare:** [Google Maps transit](https://www.google.com/maps/dir/?api=1&origin=31.3156,35.3539&destination=31.243,34.7983&travelmode=transit) · [Moovit (unofficial deep link; may not prefill)](https://moovitapp.com/?fll=31.3156_35.3539&tll=31.243_34.7983&from=Masada%20Junction&to=Beersheba%20Central) · Set the time yourself to **Depart at 13:00, Tue 2026-11-03** (Google's documented URL has no time parameter).
**Corpus expectation (context, not a verdict):** outcome `either`, max_duration_min = 300, max_walk_m = 3000, min_duration_min = 40

> What to check: Sparse desert service with long access walks. Check the walking legs are physically plausible — not a 6 km hike along a highway shoulder.

**API RESULT: NO ROUTE** — a valid search inside coverage returned no journey. The API does not state a cause (no service, walking limit and data gaps look alike).
Request id `90e0c1df69bc4c8fbe672467dc132dcb`.

| Usable? (Y/N) | Notes | Compared against / when checked |
|---|---|---|
|  |  |  |

---

## J25 — Dizengoff Center (דיזנגוף סנטר) → Yitzhak Navon Station (תחנת יצחק נבון)

category `shabbat-holiday` · calendar rule `shabbat`

**Requested:** Depart at Sat 2026-10-31 12:00 (UTC+02:00)  
Request field: `departAt=2026-10-31T12:00:00+02:00`
**Calendar flags:** Shabbat
**Compare:** [Google Maps transit](https://www.google.com/maps/dir/?api=1&origin=32.0757,34.7748&destination=31.7888,35.2027&travelmode=transit) · [Moovit (unofficial deep link; may not prefill)](https://moovitapp.com/?fll=32.0757_34.7748&tll=31.7888_35.2027&from=Dizengoff%20Center&to=Yitzhak%20Navon%20Station) · Set the time yourself to **Depart at 12:00, Sat 2026-10-31** (Google's documented URL has no time parameter).
**Corpus expectation (context, not a verdict):** outcome `either`

> What to check: THE Israeli calendar case: national rail and most buses do not run on Shabbat, while some operators and city lines do. A confident full itinerary on Saturday noon is almost certainly wrong. Verify whatever it returns against the actual calendar.txt entries.

**API RESULT: 3 journey option(s) returned** (scheduled times).
Request id `97826d265def4bd38e1d14686ae1e081`.

**Option 1:** departs Sat 2026-10-31 17:51, arrives Sat 2026-10-31 19:04; total 73 min, 1 transfer(s), walking 12 min / 807 m

1. Walk 5 min, 294 m: START 17:51 -> דיזנגוף סנטר/המלך ג'ורג' 17:56
2. **bus 82** (דן) toward פתח תקווה_בית רבקה: board דיזנגוף סנטר/המלך ג'ורג' [code 20785] 17:56 -> alight ת. רכבת תל אביב סבידור/על פרשת דרכים [code 21140] 18:02 (service date 2026-10-31, trip `585014331_301026`)
3. Walk 2 min, 206 m: ת. רכבת תל אביב סבידור/על פרשת דרכים 18:02 -> ת.רכבת תל אביב - סבידור/רציפים B 18:04
4. **bus 480** (אגד) toward ירושלים_תחנה מרכזית: board ת.רכבת תל אביב - סבידור/רציפים B [code 20740] 18:15 -> alight ת. מרכזית ירושלים/הורדה [code 6109] 18:59 (service date 2026-10-31, trip `3996048_301026`)
5. Walk 5 min, 307 m: ת. מרכזית ירושלים/הורדה 18:59 -> END 19:04

Transfers (alight to next boarding, including any walk): ת. רכבת תל אביב סבידור/על פרשת דרכים -> ת.רכבת תל אביב - סבידור/רציפים B: 13 min

**Option 2:** departs Sat 2026-10-31 18:11, arrives Sat 2026-10-31 19:19; total 68 min, 1 transfer(s), walking 12 min / 807 m

1. Walk 5 min, 294 m: START 18:11 -> דיזנגוף סנטר/המלך ג'ורג' 18:16
2. **bus 82** (דן) toward פתח תקווה_בית רבקה: board דיזנגוף סנטר/המלך ג'ורג' [code 20785] 18:16 -> alight ת. רכבת תל אביב סבידור/על פרשת דרכים [code 21140] 18:22 (service date 2026-10-31, trip `586276679_301026`)
3. Walk 2 min, 206 m: ת. רכבת תל אביב סבידור/על פרשת דרכים 18:22 -> ת.רכבת תל אביב - סבידור/רציפים B 18:24
4. **bus 480** (אגד) toward ירושלים_תחנה מרכזית: board ת.רכבת תל אביב - סבידור/רציפים B [code 20740] 18:30 -> alight ת. מרכזית ירושלים/הורדה [code 6109] 19:14 (service date 2026-10-31, trip `2095990_301026`)
5. Walk 5 min, 307 m: ת. מרכזית ירושלים/הורדה 19:14 -> END 19:19

Transfers (alight to next boarding, including any walk): ת. רכבת תל אביב סבידור/על פרשת דרכים -> ת.רכבת תל אביב - סבידור/רציפים B: 8 min

**Option 3:** departs Sat 2026-10-31 18:28, arrives Sat 2026-10-31 19:34; total 66 min, 1 transfer(s), walking 12 min / 737 m

1. Walk 5 min, 294 m: START 18:28 -> דיזנגוף סנטר/המלך ג'ורג' 18:33
2. **bus 72** (דן) toward תל אביב יפו_רכבת האוניברסיטה: board דיזנגוף סנטר/המלך ג'ורג' [code 20785] 18:33 -> alight ת. רכבת תל אביב - סבידור/דרך נמיר [code 24068] 18:39 (service date 2026-10-31, trip `585368831_301026`)
3. Walk 2 min, 136 m: ת. רכבת תל אביב - סבידור/דרך נמיר 18:39 -> ת.רכבת תל אביב - סבידור/רציפים B 18:41
4. **bus 480** (אגד) toward ירושלים_תחנה מרכזית: board ת.רכבת תל אביב - סבידור/רציפים B [code 20740] 18:45 -> alight ת. מרכזית ירושלים/הורדה [code 6109] 19:29 (service date 2026-10-31, trip `3996050_301026`)
5. Walk 5 min, 307 m: ת. מרכזית ירושלים/הורדה 19:29 -> END 19:34

Transfers (alight to next boarding, including any walk): ת. רכבת תל אביב - סבידור/דרך נמיר -> ת.רכבת תל אביב - סבידור/רציפים B: 6 min

| Usable? (Y/N) | Notes | Compared against / when checked |
|---|---|---|
|  |  |  |

---

## J11-FRI — Tel Aviv Savidor Center (תל אביב סבידור מרכז) → Haifa Center HaShmona (חיפה מרכז השמונה)

category `intercity-rail` · calendar rule `friday_afternoon`

Calendar variant of J11: Friday afternoon: expect reduced or no rail service.

**Requested:** Depart at Fri 2026-11-06 15:30 (UTC+02:00)  
Request field: `departAt=2026-11-06T15:30:00+02:00`
**Calendar flags:** Friday (erev Shabbat)
**Compare:** [Google Maps transit](https://www.google.com/maps/dir/?api=1&origin=32.0836,34.7981&destination=32.8206,34.9985&travelmode=transit) · [Moovit (unofficial deep link; may not prefill)](https://moovitapp.com/?fll=32.0836_34.7981&tll=32.8206_34.9985&from=Tel%20Aviv%20Savidor%20Center&to=Haifa%20Center%20HaShmona) · Set the time yourself to **Depart at 15:30, Fri 2026-11-06** (Google's documented URL has no time parameter).
**Corpus expectation (context, not a verdict):** outcome `route`, max_duration_min = 130, max_transfers = 1, min_duration_min = 45, modes_any_of = ['rail']

> What to check: The flagship rail corridor. Cross-check timings against BetterRail.

**API RESULT: 3 journey option(s) returned** (scheduled times).
Machine note: matches the corpus expectation `route`. This is not a judgement of quality.
Request id `13523c1436d24a53af3c15f9d02011b5`.

**Option 1:** departs Fri 2026-11-06 15:34, arrives Fri 2026-11-06 17:24; total 110 min, 1 transfer(s), walking 17 min / 1112 m

1. Walk 6 min, 431 m: START 15:34 -> ת. רכבת תל אביב - סבידור/דרך נמיר 15:40
2. **bus 909** (אגד) toward נהריה_תחנה מרכזית: board ת. רכבת תל אביב - סבידור/דרך נמיר [code 24068] 15:40 -> alight ת. מרכזית המפרץ/הורדה [code 43008] 16:54 (service date 2026-11-06, trip `59116972_301026`)
3. Walk 2 min, 112 m: ת. מרכזית המפרץ/הורדה 16:54 -> ת. מרכזית המפרץ/מטרונית לחיפה 16:56
4. **bus 1** (סופרבוס) toward חיפה_מרכזית חוף הכרמל: board ת. מרכזית המפרץ/מטרונית לחיפה [code 47488] 17:01 -> alight כרמלית [code 47203] 17:15 (service date 2026-11-06, trip `40077321_301026`)
5. Walk 9 min, 569 m: כרמלית 17:15 -> END 17:24

Transfers (alight to next boarding, including any walk): ת. מרכזית המפרץ/הורדה -> ת. מרכזית המפרץ/מטרונית לחיפה: 7 min

**Option 2:** departs Fri 2026-11-06 15:39, arrives Fri 2026-11-06 17:29; total 110 min, 1 transfer(s), walking 17 min / 1168 m

1. Walk 6 min, 431 m: START 15:39 -> ת. רכבת תל אביב - סבידור/דרך נמיר 15:45
2. **bus 900** (אגד) toward חיפה_מרכזית חוף הכרמל: board ת. רכבת תל אביב - סבידור/דרך נמיר [code 24068] 15:45 -> alight מת''מ [code 42656] 16:54 (service date 2026-11-06, trip `585657610_301026`)
3. Walk 2 min, 173 m: מת''מ 16:54 -> מת''מ 16:56
4. **bus 1** (סופרבוס) toward קרית מוצקין_מרכזית הקריות: board מת''מ [code 42229] 17:04 -> alight כרמלית [code 47576] 17:20 (service date 2026-11-06, trip `11253037_301026`)
5. Walk 9 min, 564 m: כרמלית 17:20 -> END 17:29

Transfers (alight to next boarding, including any walk): מת''מ -> מת''מ: 10 min

**Option 3:** departs Fri 2026-11-06 15:49, arrives Fri 2026-11-06 17:44; total 115 min, 1 transfer(s), walking 17 min / 1168 m

1. Walk 6 min, 431 m: START 15:49 -> ת. רכבת תל אביב - סבידור/דרך נמיר 15:55
2. **bus 900** (אגד) toward חיפה_מרכזית חוף הכרמל: board ת. רכבת תל אביב - סבידור/דרך נמיר [code 24068] 15:55 -> alight מת''מ [code 42656] 17:04 (service date 2026-11-06, trip `585657611_301026`)
3. Walk 2 min, 173 m: מת''מ 17:04 -> מת''מ 17:06
4. **bus 1** (סופרבוס) toward קרית מוצקין_מרכזית הקריות: board מת''מ [code 42229] 17:19 -> alight כרמלית [code 47576] 17:35 (service date 2026-11-06, trip `15202896_301026`)
5. Walk 9 min, 564 m: כרמלית 17:35 -> END 17:44

Transfers (alight to next boarding, including any walk): מת''מ -> מת''מ: 15 min

| Usable? (Y/N) | Notes | Compared against / when checked |
|---|---|---|
|  |  |  |

---

## J12-FRI — Tel Aviv Savidor Center (תל אביב סבידור מרכז) → Yitzhak Navon Station (תחנת יצחק נבון)

category `intercity-rail` · calendar rule `friday_afternoon`

Calendar variant of J12: Friday afternoon: expect reduced or no rail service.

**Requested:** Depart at Fri 2026-11-06 15:30 (UTC+02:00)  
Request field: `departAt=2026-11-06T15:30:00+02:00`
**Calendar flags:** Friday (erev Shabbat)
**Compare:** [Google Maps transit](https://www.google.com/maps/dir/?api=1&origin=32.0836,34.7981&destination=31.7888,35.2027&travelmode=transit) · [Moovit (unofficial deep link; may not prefill)](https://moovitapp.com/?fll=32.0836_34.7981&tll=31.7888_35.2027&from=Tel%20Aviv%20Savidor%20Center&to=Yitzhak%20Navon%20Station) · Set the time yourself to **Depart at 15:30, Fri 2026-11-06** (Google's documented URL has no time parameter).
**Corpus expectation (context, not a verdict):** outcome `route`, max_duration_min = 110, max_transfers = 1, min_duration_min = 30, modes_any_of = ['rail']

> What to check: Fast line. If it routes by bus, the rail calendar is probably misread.

**API RESULT: 3 journey option(s) returned** (scheduled times).
Machine note: matches the corpus expectation `route`. This is not a judgement of quality.
Request id `0c5d3de08ffc46e6ae5013d7c3ca388e`.

**Option 1:** departs Fri 2026-11-06 15:30, arrives Fri 2026-11-06 16:25; total 55 min, 0 transfer(s), walking 11 min / 710 m

1. Walk 6 min, 403 m: START 15:30 -> ת.רכבת תל אביב - סבידור/רציפים B 15:36
2. **bus 480** (אגד) toward ירושלים_תחנה מרכזית: board ת.רכבת תל אביב - סבידור/רציפים B [code 20740] 15:36 -> alight ת. מרכזית ירושלים/הורדה [code 6109] 16:20 (service date 2026-11-06, trip `2117248_301026`)
3. Walk 5 min, 307 m: ת. מרכזית ירושלים/הורדה 16:20 -> END 16:25

Transfers (alight to next boarding, including any walk): none

**Option 2:** departs Fri 2026-11-06 15:42, arrives Fri 2026-11-06 16:37; total 55 min, 0 transfer(s), walking 11 min / 710 m

1. Walk 6 min, 403 m: START 15:42 -> ת.רכבת תל אביב - סבידור/רציפים B 15:48
2. **bus 480** (אגד) toward ירושלים_תחנה מרכזית: board ת.רכבת תל אביב - סבידור/רציפים B [code 20740] 15:48 -> alight ת. מרכזית ירושלים/הורדה [code 6109] 16:32 (service date 2026-11-06, trip `2117249_301026`)
3. Walk 5 min, 307 m: ת. מרכזית ירושלים/הורדה 16:32 -> END 16:37

Transfers (alight to next boarding, including any walk): none

**Option 3:** departs Fri 2026-11-06 15:54, arrives Fri 2026-11-06 16:49; total 55 min, 0 transfer(s), walking 11 min / 710 m

1. Walk 6 min, 403 m: START 15:54 -> ת.רכבת תל אביב - סבידור/רציפים B 16:00
2. **bus 480** (אגד) toward ירושלים_תחנה מרכזית: board ת.רכבת תל אביב - סבידור/רציפים B [code 20740] 16:00 -> alight ת. מרכזית ירושלים/הורדה [code 6109] 16:44 (service date 2026-11-06, trip `1401293_301026`)
3. Walk 5 min, 307 m: ת. מרכזית ירושלים/הורדה 16:44 -> END 16:49

Transfers (alight to next boarding, including any walk): none

| Usable? (Y/N) | Notes | Compared against / when checked |
|---|---|---|
|  |  |  |

---

## J11-SAT — Tel Aviv Savidor Center (תל אביב סבידור מרכז) → Haifa Center HaShmona (חיפה מרכז השמונה)

category `intercity-rail` · calendar rule `shabbat`

Calendar variant of J11: Saturday noon: expect no national rail.

**Requested:** Depart at Sat 2026-10-31 12:00 (UTC+02:00)  
Request field: `departAt=2026-10-31T12:00:00+02:00`
**Calendar flags:** Shabbat
**Compare:** [Google Maps transit](https://www.google.com/maps/dir/?api=1&origin=32.0836,34.7981&destination=32.8206,34.9985&travelmode=transit) · [Moovit (unofficial deep link; may not prefill)](https://moovitapp.com/?fll=32.0836_34.7981&tll=32.8206_34.9985&from=Tel%20Aviv%20Savidor%20Center&to=Haifa%20Center%20HaShmona) · Set the time yourself to **Depart at 12:00, Sat 2026-10-31** (Google's documented URL has no time parameter).
**Corpus expectation (context, not a verdict):** outcome `route`, max_duration_min = 130, max_transfers = 1, min_duration_min = 45, modes_any_of = ['rail']

> What to check: The flagship rail corridor. Cross-check timings against BetterRail.

**API RESULT: 3 journey option(s) returned** (scheduled times).
Machine note: matches the corpus expectation `route`. This is not a judgement of quality.
Request id `8dfbb5a03e22485e995d38671aa28c85`.

**Option 1:** departs Sat 2026-10-31 15:35, arrives Sat 2026-10-31 18:30; total 175 min, 2 transfer(s), walking 19 min / 1362 m

1. Walk 6 min, 431 m: START 15:35 -> ת. רכבת תל אביב - סבידור/דרך נמיר 15:41
2. **bus 825** (אגד) toward עפולה_תחנה מרכזית: board ת. רכבת תל אביב - סבידור/דרך נמיר [code 24068] 15:41 -> alight ת.מרכזית עפולה/הורדה [code 52152] 17:11 (service date 2026-10-31, trip `25275651_301026`)
3. Walk 2 min, 250 m: ת.מרכזית עפולה/הורדה 17:13 -> ת.מרכזית עפולה/רציפים 17:15
4. **bus 301** (סופרבוס) toward חיפה_מרכזית המפרץ: board ת.מרכזית עפולה/רציפים [code 52174] 17:15 -> alight ת. מרכזית המפרץ/הורדה [code 43008] 17:56 (service date 2026-10-31, trip `14464441_301026`)
5. Walk 2 min, 112 m: ת. מרכזית המפרץ/הורדה 17:56 -> ת. מרכזית המפרץ/מטרונית לחיפה 17:58
6. **bus 1** (סופרבוס) toward חיפה_מרכזית חוף הכרמל: board ת. מרכזית המפרץ/מטרונית לחיפה [code 47488] 18:07 -> alight כרמלית [code 47203] 18:21 (service date 2026-10-31, trip `15018301_301026`)
7. Walk 9 min, 569 m: כרמלית 18:21 -> END 18:30

Transfers (alight to next boarding, including any walk): ת.מרכזית עפולה/הורדה -> ת.מרכזית עפולה/רציפים: 4 min; ת. מרכזית המפרץ/הורדה -> ת. מרכזית המפרץ/מטרונית לחיפה: 11 min

**Option 2:** departs Sat 2026-10-31 16:34, arrives Sat 2026-10-31 18:47; total 133 min, 1 transfer(s), walking 17 min / 1253 m

1. Walk 6 min, 431 m: START 16:34 -> ת. רכבת תל אביב - סבידור/דרך נמיר 16:40
2. **bus 836** (אגד) toward טבריה_תחנה מרכזית: board ת. רכבת תל אביב - סבידור/דרך נמיר [code 24068] 16:40 -> alight צומת השומרים [code 51536] 17:55 (service date 2026-10-31, trip `25276278_301026`)
3. Walk 2 min, 229 m: צומת השומרים 17:55 -> צומת השומרים 17:57
4. **bus 332** (נסיעות ותיירות) toward חיפה_רכבת מרכז השמונה: board צומת השומרים [code 43024] 18:13 -> alight קריית הממשלה/העצמאות [code 43096] 18:38 (service date 2026-10-31, trip `45520101_301026`)
5. Walk 9 min, 593 m: קריית הממשלה/העצמאות 18:38 -> END 18:47

Transfers (alight to next boarding, including any walk): צומת השומרים -> צומת השומרים: 18 min

**Option 3:** departs Sat 2026-10-31 16:45, arrives Sat 2026-10-31 18:45; total 120 min, 2 transfer(s), walking 17 min / 1042 m

1. Walk 6 min, 431 m: START 16:45 -> ת. רכבת תל אביב - סבידור/דרך נמיר 16:51
2. **bus 825** (אגד) toward עפולה_תחנה מרכזית: board ת. רכבת תל אביב - סבידור/דרך נמיר [code 24068] 16:51 -> alight צומת אולגה [code 41694] 17:28 (service date 2026-10-31, trip `25275451_301026`)
3. Walk 2 min, 0 m: צומת אולגה 17:42 -> צומת אולגה 17:44
4. **bus 947** (אגד) toward חיפה_מרכזית חוף הכרמל: board צומת אולגה [code 41694] 17:44 -> alight מת''מ [code 42656] 18:17 (service date 2026-10-31, trip `584672084_301026`)
5. Walk 2 min, 173 m: מת''מ 18:17 -> מת''מ 18:19
6. **bus 245** (אגד) toward חיפה_שוק תלפיות: board מת''מ [code 42229] 18:22 -> alight המגינים/ככר ההגנה [code 42723] 18:38 (service date 2026-10-31, trip `585108128_301026`)
7. Walk 7 min, 438 m: המגינים/ככר ההגנה 18:38 -> END 18:45

Transfers (alight to next boarding, including any walk): צומת אולגה -> צומת אולגה: 16 min; מת''מ -> מת''מ: 5 min

| Usable? (Y/N) | Notes | Compared against / when checked |
|---|---|---|
|  |  |  |

---

## J05-SAT — Mahane Yehuda Market (שוק מחנה יהודה) → Mount Herzl (הר הרצל)

category `jerusalem-urban-light-rail` · calendar rule `shabbat`

Calendar variant of J05: Saturday noon: Jerusalem urban case.

**Requested:** Depart at Sat 2026-10-31 12:00 (UTC+02:00)  
Request field: `departAt=2026-10-31T12:00:00+02:00`
**Calendar flags:** Shabbat
**Compare:** [Google Maps transit](https://www.google.com/maps/dir/?api=1&origin=31.7853,35.2124&destination=31.7736,35.1806&travelmode=transit) · [Moovit (unofficial deep link; may not prefill)](https://moovitapp.com/?fll=31.7853_35.2124&tll=31.7736_35.1806&from=Mahane%20Yehuda%20Market&to=Mount%20Herzl) · Set the time yourself to **Depart at 12:00, Sat 2026-10-31** (Google's documented URL has no time parameter).
**Corpus expectation (context, not a verdict):** outcome `route`, max_duration_min = 45, max_transfers = 1, min_duration_min = 8, modes_any_of = ['light_rail', 'bus']

> What to check: This is the light rail's spine. If it routes by bus instead, something is wrong.

**API RESULT: 3 journey option(s) returned** (scheduled times).
Machine note: matches the corpus expectation `route`. This is not a judgement of quality.
Request id `7966b3f847f84af8bae369b68eef3253`.

**Option 1:** departs Sat 2026-10-31 17:52, arrives Sat 2026-10-31 18:28; total 36 min, 1 transfer(s), walking 20 min / 1216 m

1. Walk 10 min, 642 m: START 17:52 -> הטורים 18:02
2. **light_rail 3** (כפיר) toward מנחת (מלחה): board הטורים [code 6174] 18:02 -> alight גבעת רם [code 2743] 18:07 (service date 2026-10-31, trip `586277246_301026`)
3. Walk 4 min, 167 m: גבעת רם 18:07 -> וולפסון/קפלן 18:11
4. **bus 35** (אגד) toward מלחה: board וולפסון/קפלן [code 4208] 18:12 -> alight שדרות הרצל/הר הרצל [code 547] 18:22 (service date 2026-10-31, trip `585632827_301026`)
5. Walk 6 min, 407 m: שדרות הרצל/הר הרצל 18:22 -> END 18:28

Transfers (alight to next boarding, including any walk): גבעת רם -> וולפסון/קפלן: 5 min

**Option 2:** departs Sat 2026-10-31 18:02, arrives Sat 2026-10-31 18:29; total 27 min, 0 transfer(s), walking 17 min / 1117 m

1. Walk 7 min, 431 m: START 18:02 -> יפו/שערי צדק 18:09
2. **bus 27** (אגד) toward הדסה עין כרם: board יפו/שערי צדק [code 1468] 18:09 -> alight יפה נוף/מגדים [code 1679] 18:19 (service date 2026-10-31, trip `585984839_301026`)
3. Walk 10 min, 686 m: יפה נוף/מגדים 18:19 -> END 18:29

Transfers (alight to next boarding, including any walk): none

**Option 3:** departs Sat 2026-10-31 18:08, arrives Sat 2026-10-31 18:33; total 25 min, 0 transfer(s), walking 11 min / 706 m

1. Walk 2 min, 145 m: START 18:08 -> מחנה יהודה 18:10
2. **light_rail 1** (כפיר) toward הדסה עין כרם: board מחנה יהודה [code 6172] 18:10 -> alight הר הרצל [code 6185] 18:24 (service date 2026-10-31, trip `586277225_301026`)
3. Walk 9 min, 561 m: הר הרצל 18:24 -> END 18:33

Transfers (alight to next boarding, including any walk): none

| Usable? (Y/N) | Notes | Compared against / when checked |
|---|---|---|
|  |  |  |

---

## J01-HOL — Dizengoff Center (דיזנגוף סנטר) → Ramat Gan Bursa (רמת גן בורסה)

category `tel-aviv-urban-bus` · calendar rule `holiday_morning`

Calendar variant of J01: Israeli holiday timetable, morning.

**NOT GENERATED:** no Israeli holiday date (non-Shabbat) from the holiday table in the usable range 2026-10-31 00:00 .. 2026-11-30 00:00 (Asia/Jerusalem).

No request was sent. This calendar situation is not covered by this sheet.

---

## J12-HOL — Tel Aviv Savidor Center (תל אביב סבידור מרכז) → Yitzhak Navon Station (תחנת יצחק נבון)

category `intercity-rail` · calendar rule `holiday_midday`

Calendar variant of J12: Israeli holiday timetable, midday intercity.

**NOT GENERATED:** no Israeli holiday date (non-Shabbat) from the holiday table in the usable range 2026-10-31 00:00 .. 2026-11-30 00:00 (Asia/Jerusalem).

No request was sent. This calendar situation is not covered by this sheet.

---

## J01-DST — Dizengoff Center (דיזנגוף סנטר) → Ramat Gan Bursa (רמת גן בורסה)

category `tel-aviv-urban-bus` · calendar rule `dst_day_peak`

Calendar variant of J01: Peak on the DST fall-back day.

**NOT GENERATED:** no DST fall-back day in the usable range 2026-10-31 00:00 .. 2026-11-30 00:00 (Asia/Jerusalem).

No request was sent. This calendar situation is not covered by this sheet.

---

## J22-DST1 — Dizengoff Center (דיזנגוף סנטר) → Ramat Gan Bursa (רמת גן בורסה)

category `service-day-boundary` · calendar rule `dst_repeat_first`

Calendar variant of J22: Repeated hour, first occurrence (earlier offset).

**NOT GENERATED:** no repeated-hour instant in the usable range 2026-10-31 00:00 .. 2026-11-30 00:00 (Asia/Jerusalem).

No request was sent. This calendar situation is not covered by this sheet.

---

## J22-DST2 — Dizengoff Center (דיזנגוף סנטר) → Ramat Gan Bursa (רמת גן בורסה)

category `service-day-boundary` · calendar rule `dst_repeat_second`

Calendar variant of J22: Repeated hour, second occurrence (later offset).

**NOT GENERATED:** no repeated-hour instant in the usable range 2026-10-31 00:00 .. 2026-11-30 00:00 (Asia/Jerusalem).

No request was sent. This calendar situation is not covered by this sheet.

---
