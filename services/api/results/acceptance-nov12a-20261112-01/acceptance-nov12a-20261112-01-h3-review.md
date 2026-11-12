# H3 route-review sheet — through the API (POST /v1/journeys)

> **Scheduled only; realtime not enabled.** Times are MOT timetable times. No delay, prediction or alert is shown.

**You are the reviewer.** Everything machine-made below is context. Fill only the `Usable? (Y/N)` and `Notes` cells yourself, comparing with Google Maps, Moovit or BetterRail at the stated date and time. The generator never writes a verdict. Release gate: at least **9 of the 10 required journeys** judged usable.

## Generation

- Generation id: `fbab648bdbeace9e69e9c089bdeeffd86d32a516d34b8198a7f5a38f5923fb75` (mode `real`, freshness `current`)
- Data built: 2026-11-12T10:02:42.444172Z
- Coverage window (half-open, as reported by the API): 2026-11-11T00:00:00+02:00 .. 2026-12-11T00:00:00+02:00
- Window used for dates: 2026-11-11 00:00 .. 2026-12-11 00:00 Asia/Jerusalem; earliest request instant 2026-11-11 00:00
- Capabilities reported: realtime `not_enabled`, alerts `not_enabled`
- Generated 2026-11-12T12:19:03Z (2026-11-12 14:19 Israel) against `http://127.0.0.1:8540`
- Corpus `poc/corpora/journeys.json` sha256 `5fc013a5e1c52f16…`; case IDs are the PoC IDs. Coordinates are the corpus's approximate hand-entered points; the API plans from them.
- Request options: lang `he`, results 3, walking limits API defaults, arrive-by variants off
- Raw requests and responses: `acceptance-nov12a-20261112-01-h3-review-raw.json`

## Required ten — your tally

| # | Case | Requested | Usable? (Y/N) |
|---|---|---|---|
| 1 | J01 | Mon 2026-11-16 08:00 (UTC+02:00) | |
| 2 | J04 | Wed 2026-11-11 18:30 (UTC+02:00) | |
| 3 | J11 | Mon 2026-11-16 08:00 (UTC+02:00) | |
| 4 | J12 | Mon 2026-11-16 08:00 (UTC+02:00) | |
| 5 | J15 | Mon 2026-11-16 08:00 (UTC+02:00) | |
| 6 | J16 | Mon 2026-11-16 08:00 (UTC+02:00) | |
| 7 | J19 | Mon 2026-11-16 08:00 (UTC+02:00) | |
| 8 | J21 | Tue 2026-11-17 23:40 (UTC+02:00) | |
| 9 | J22 | Wed 2026-11-11 02:30 (UTC+02:00) | |
| 10 | J23 | Wed 2026-11-11 02:30 (UTC+02:00) | |

Total usable: ____ / 10

## Date selection

| Case | Rule | Requested (Asia/Jerusalem) | Calendar flags |
|---|---|---|---|
| J01 | weekday_morning | depart Mon 2026-11-16 08:00 (UTC+02:00) | ordinary day |
| J02 | weekday_morning | depart Mon 2026-11-16 08:00 (UTC+02:00) | ordinary day |
| J03 | weekday_midday | depart Tue 2026-11-17 13:00 (UTC+02:00) | ordinary day |
| J04 | weekday_evening | depart Wed 2026-11-11 18:30 (UTC+02:00) | ordinary day |
| J05 | weekday_midday | depart Tue 2026-11-17 13:00 (UTC+02:00) | ordinary day |
| J06 | weekday_morning | depart Mon 2026-11-16 08:00 (UTC+02:00) | ordinary day |
| J07 | weekday_evening | depart Wed 2026-11-11 18:30 (UTC+02:00) | ordinary day |
| J08 | weekday_morning | depart Mon 2026-11-16 08:00 (UTC+02:00) | ordinary day |
| J09 | weekday_evening | depart Wed 2026-11-11 18:30 (UTC+02:00) | ordinary day |
| J10 | weekday_midday | depart Tue 2026-11-17 13:00 (UTC+02:00) | ordinary day |
| J11 | weekday_morning | depart Mon 2026-11-16 08:00 (UTC+02:00) | ordinary day |
| J12 | weekday_morning | depart Mon 2026-11-16 08:00 (UTC+02:00) | ordinary day |
| J13 | weekday_midday | depart Tue 2026-11-17 13:00 (UTC+02:00) | ordinary day |
| J14 | weekday_morning | depart Mon 2026-11-16 08:00 (UTC+02:00) | ordinary day |
| J15 | weekday_morning | depart Mon 2026-11-16 08:00 (UTC+02:00) | ordinary day |
| J16 | weekday_morning | depart Mon 2026-11-16 08:00 (UTC+02:00) | ordinary day |
| J17 | weekday_morning | depart Mon 2026-11-16 08:00 (UTC+02:00) | ordinary day |
| J18 | weekday_morning | depart Mon 2026-11-16 08:00 (UTC+02:00) | ordinary day |
| J19 | weekday_morning | depart Mon 2026-11-16 08:00 (UTC+02:00) | ordinary day |
| J20 | weekday_midday | depart Tue 2026-11-17 13:00 (UTC+02:00) | ordinary day |
| J21 | late_night | depart Tue 2026-11-17 23:40 (UTC+02:00) | ordinary day |
| J22 | after_midnight | depart Wed 2026-11-11 02:30 (UTC+02:00) | ordinary day |
| J23 | after_midnight | depart Wed 2026-11-11 02:30 (UTC+02:00) | ordinary day |
| J24 | weekday_midday | depart Tue 2026-11-17 13:00 (UTC+02:00) | ordinary day |
| J25 | shabbat | depart Sat 2026-11-14 12:00 (UTC+02:00) | Shabbat |
| J11-FRI | friday_afternoon | depart Fri 2026-11-13 15:30 (UTC+02:00) | Friday (erev Shabbat) |
| J12-FRI | friday_afternoon | depart Fri 2026-11-13 15:30 (UTC+02:00) | Friday (erev Shabbat) |
| J11-SAT | shabbat | depart Sat 2026-11-14 12:00 (UTC+02:00) | Shabbat |
| J05-SAT | shabbat | depart Sat 2026-11-14 12:00 (UTC+02:00) | Shabbat |
| J01-HOL | holiday_morning | OMITTED: no Israeli holiday date (non-Shabbat) from the holiday table in the usable range 2026-11-11 00:00 .. 2026-12-11 00:00 (Asia/Jerusalem) |  |
| J12-HOL | holiday_midday | OMITTED: no Israeli holiday date (non-Shabbat) from the holiday table in the usable range 2026-11-11 00:00 .. 2026-12-11 00:00 (Asia/Jerusalem) |  |
| J01-DST | dst_day_peak | OMITTED: no DST fall-back day in the usable range 2026-11-11 00:00 .. 2026-12-11 00:00 (Asia/Jerusalem) |  |
| J22-DST1 | dst_repeat_first | OMITTED: no repeated-hour instant in the usable range 2026-11-11 00:00 .. 2026-12-11 00:00 (Asia/Jerusalem) |  |
| J22-DST2 | dst_repeat_second | OMITTED: no repeated-hour instant in the usable range 2026-11-11 00:00 .. 2026-12-11 00:00 (Asia/Jerusalem) |  |

**Not covered by this sheet:** J01-HOL, J12-HOL, J01-DST, J22-DST1, J22-DST2

Holiday dates come from a built-in 2026 table and any `--holiday` overrides; verify them against the official calendar. Cases marked Shabbat, Friday, holiday or DST are deliberately unusual: no or reduced service can be correct there.

---

## J01 — Dizengoff Center (דיזנגוף סנטר) → Ramat Gan Bursa (רמת גן בורסה)

**Required journey #1** — PRD §7 #1 Tel Aviv → Ramat Gan · category `tel-aviv-urban-bus` · calendar rule `weekday_morning`

**Requested:** Depart at Mon 2026-11-16 08:00 (UTC+02:00)  
Request field: `departAt=2026-11-16T08:00:00+02:00`
**Calendar flags:** ordinary day
**Compare:** [Google Maps transit](https://www.google.com/maps/dir/?api=1&origin=32.0757,34.7748&destination=32.0838,34.8044&travelmode=transit) · [Moovit (unofficial deep link; may not prefill)](https://moovitapp.com/?fll=32.0757_34.7748&tll=32.0838_34.8044&from=Dizengoff%20Center&to=Ramat%20Gan%20Bursa) · Set the time yourself to **Depart at 08:00, Mon 2026-11-16** (Google's documented URL has no time parameter).
**Corpus expectation (context, not a verdict):** outcome `route`, max_duration_min = 55, max_transfers = 2, min_duration_min = 10, modes_any_of = ['bus', 'light_rail']

> What to check: Would a Tel Aviv resident actually take this? Compare against Moovit.

**API RESULT: 3 journey option(s) returned** (scheduled times).
Machine note: matches the corpus expectation `route`. This is not a judgement of quality.
Request id `40477512f9024c4e9b28e747a71bcc66`.

**Option 1:** departs Mon 2026-11-16 08:06, arrives Mon 2026-11-16 08:24; total 18 min, 0 transfer(s), walking 9 min / 533 m

1. Walk 5 min, 294 m: START 08:06 -> דיזנגוף סנטר/המלך ג'ורג' 08:11
2. **bus 82** (דן) toward פתח תקווה_בית רבקה: board דיזנגוף סנטר/המלך ג'ורג' [code 20785] 08:11 -> alight ת.רק''ל אבא הלל/דרך ז'בוטינסקי [code 21644] 08:20 (service date 2026-11-16, trip `503015_161126`)
3. Walk 4 min, 239 m: ת.רק''ל אבא הלל/דרך ז'בוטינסקי 08:20 -> END 08:24

Transfers (alight to next boarding, including any walk): none

**Option 2:** departs Mon 2026-11-16 08:14, arrives Mon 2026-11-16 08:33; total 19 min, 0 transfer(s), walking 7 min / 390 m

1. Walk 3 min, 135 m: START 08:14 -> דיזנגוף סנטר/דיזנגוף 08:17
2. **bus 238** (דן) toward פתח תקווה_הדר גנים: board דיזנגוף סנטר/דיזנגוף [code 25565] 08:17 -> alight ת.רק''ל אבא הלל [code 26248] 08:29 (service date 2026-11-16, trip `46017616_161126`)
3. Walk 4 min, 255 m: ת.רק''ל אבא הלל 08:29 -> END 08:33

Transfers (alight to next boarding, including any walk): none

**Option 3:** departs Mon 2026-11-16 08:17, arrives Mon 2026-11-16 08:35; total 18 min, 0 transfer(s), walking 9 min / 533 m

1. Walk 5 min, 294 m: START 08:17 -> דיזנגוף סנטר/המלך ג'ורג' 08:22
2. **bus 82** (דן) toward פתח תקווה_בית רבקה: board דיזנגוף סנטר/המלך ג'ורג' [code 20785] 08:22 -> alight ת.רק''ל אבא הלל/דרך ז'בוטינסקי [code 21644] 08:31 (service date 2026-11-16, trip `631281_161126`)
3. Walk 4 min, 239 m: ת.רק''ל אבא הלל/דרך ז'בוטינסקי 08:31 -> END 08:35

Transfers (alight to next boarding, including any walk): none

| Usable? (Y/N) | Notes | Compared against / when checked |
|---|---|---|
|  |  |  |

---

## J02 — Tel Aviv University (אוניברסיטת תל אביב) → Sourasky Medical Center (Ichilov) (בית חולים איכילוב)

category `tel-aviv-urban-bus` · calendar rule `weekday_morning`

**Requested:** Depart at Mon 2026-11-16 08:00 (UTC+02:00)  
Request field: `departAt=2026-11-16T08:00:00+02:00`
**Calendar flags:** ordinary day
**Compare:** [Google Maps transit](https://www.google.com/maps/dir/?api=1&origin=32.1133,34.8044&destination=32.08,34.79&travelmode=transit) · [Moovit (unofficial deep link; may not prefill)](https://moovitapp.com/?fll=32.1133_34.8044&tll=32.08_34.79&from=Tel%20Aviv%20University&to=Sourasky%20Medical%20Center%20%28Ichilov%29) · Set the time yourself to **Depart at 08:00, Mon 2026-11-16** (Google's documented URL has no time parameter).
**Corpus expectation (context, not a verdict):** outcome `route`, max_duration_min = 60, max_transfers = 2, min_duration_min = 12, modes_any_of = ['bus', 'light_rail', 'rail']

> What to check: Peak-hour campus-to-hospital trip. Is the walk at either end reasonable?

**API RESULT: 3 journey option(s) returned** (scheduled times).
Machine note: matches the corpus expectation `route`. This is not a judgement of quality.
Request id `31dc11d973314ae79d5788f8119a571e`.

**Option 1:** departs Mon 2026-11-16 08:00, arrives Mon 2026-11-16 08:26; total 26 min, 1 transfer(s), walking 12 min / 577 m

1. Walk 6 min, 389 m: START 08:00 -> האוניברסיטה/חיים לבנון 08:06
2. **bus 24** (מטרופולין) toward תל אביב יפו_מסוף כרמלית: board האוניברסיטה/חיים לבנון [code 21388] 08:06 -> alight דרך נמיר/יהודה המכבי [code 21188] 08:13 (service date 2026-11-16, trip `45060631_151126`)
3. Walk 2 min, 0 m: דרך נמיר/יהודה המכבי 08:13 -> דרך נמיר/יהודה המכבי 08:15
4. **bus 89** (דן) toward חולון_פארק פרס: board דרך נמיר/יהודה המכבי [code 21188] 08:15 -> alight ביה''ח איכילוב/ויצמן [code 21206] 08:22 (service date 2026-11-16, trip `13998568_161126`)
5. Walk 4 min, 188 m: ביה''ח איכילוב/ויצמן 08:22 -> END 08:26

Transfers (alight to next boarding, including any walk): דרך נמיר/יהודה המכבי -> דרך נמיר/יהודה המכבי: 2 min

**Option 2:** departs Mon 2026-11-16 08:01, arrives Mon 2026-11-16 08:30; total 29 min, 1 transfer(s), walking 12 min / 595 m

1. Walk 6 min, 407 m: START 08:01 -> האוניברסיטה/איינשטיין 08:07
2. **bus 25** (דן) toward חולון_מוזיאון אגד: board האוניברסיטה/איינשטיין [code 26635] 08:07 -> alight יהודה המכבי/דרך נמיר [code 25943] 08:15 (service date 2026-11-16, trip `3009879_161126`)
3. Walk 2 min, 0 m: יהודה המכבי/דרך נמיר 08:15 -> יהודה המכבי/דרך נמיר 08:17
4. **bus 14** (דן) toward מסוף הלוחמים: board יהודה המכבי/דרך נמיר [code 25943] 08:20 -> alight ביה''ח איכילוב/ויצמן [code 21206] 08:26 (service date 2026-11-16, trip `585552934_161126`)
5. Walk 4 min, 188 m: ביה''ח איכילוב/ויצמן 08:26 -> END 08:30

Transfers (alight to next boarding, including any walk): יהודה המכבי/דרך נמיר -> יהודה המכבי/דרך נמיר: 5 min

**Option 3:** departs Mon 2026-11-16 08:07, arrives Mon 2026-11-16 08:31; total 24 min, 0 transfer(s), walking 10 min / 595 m

1. Walk 6 min, 407 m: START 08:07 -> האוניברסיטה/איינשטיין 08:13
2. **bus 7** (דן) toward חולון_מ.רפואי וולפסון: board האוניברסיטה/איינשטיין [code 26635] 08:13 -> alight ביה''ח איכילוב/ויצמן [code 21206] 08:27 (service date 2026-11-16, trip `2593441_161126`)
3. Walk 4 min, 188 m: ביה''ח איכילוב/ויצמן 08:27 -> END 08:31

Transfers (alight to next boarding, including any walk): none

| Usable? (Y/N) | Notes | Compared against / when checked |
|---|---|---|
|  |  |  |

---

## J03 — Jaffa Clock Tower (מגדל השעון יפו) → Tel Aviv Savidor Center (תל אביב סבידור מרכז)

category `tel-aviv-urban-bus` · calendar rule `weekday_midday`

**Requested:** Depart at Tue 2026-11-17 13:00 (UTC+02:00)  
Request field: `departAt=2026-11-17T13:00:00+02:00`
**Calendar flags:** ordinary day
**Compare:** [Google Maps transit](https://www.google.com/maps/dir/?api=1&origin=32.0542,34.7522&destination=32.0836,34.7981&travelmode=transit) · [Moovit (unofficial deep link; may not prefill)](https://moovitapp.com/?fll=32.0542_34.7522&tll=32.0836_34.7981&from=Jaffa%20Clock%20Tower&to=Tel%20Aviv%20Savidor%20Center) · Set the time yourself to **Depart at 13:00, Tue 2026-11-17** (Google's documented URL has no time parameter).
**Corpus expectation (context, not a verdict):** outcome `route`, max_duration_min = 65, max_transfers = 2, min_duration_min = 15, modes_any_of = ['bus', 'light_rail']

> What to check: Jaffa to the main station. Does it use the red line where sensible?

**API RESULT: 3 journey option(s) returned** (scheduled times).
Machine note: matches the corpus expectation `route`. This is not a judgement of quality.
Request id `4036943a6828418ca37fb89562bdd84e`.

**Option 1:** departs Tue 2026-11-17 13:04, arrives Tue 2026-11-17 13:35; total 31 min, 0 transfer(s), walking 11 min / 787 m

1. Walk 5 min, 356 m: START 13:04 -> יפת/לואי פסטר 13:09
2. **bus 44** (דן) toward תל אביב יפו_קריית עתידים: board יפת/לואי פסטר [code 20448] 13:09 -> alight ת. רכבת תל אביב - סבידור/דרך נמיר [code 24068] 13:29 (service date 2026-11-17, trip `45068558_161126`)
3. Walk 6 min, 431 m: ת. רכבת תל אביב - סבידור/דרך נמיר 13:29 -> END 13:35

Transfers (alight to next boarding, including any walk): none

**Option 2:** departs Tue 2026-11-17 13:06, arrives Tue 2026-11-17 13:39; total 33 min, 1 transfer(s), walking 14 min / 822 m

1. Walk 9 min, 639 m: START 13:06 -> כיכר השעון/מרזוק ועזר 13:15
2. **bus 54** (דן) toward קריית עתידים: board כיכר השעון/מרזוק ועזר [code 25303] 13:15 -> alight ת.רכבת ההגנה [code 25637] 13:24 (service date 2026-11-17, trip `45563005_161126`)
3. Walk 4 min, 156 m: ת.רכבת ההגנה 13:24 -> תל אביב ההגנה 13:28
4. **rail ** (רכבת ישראל) toward 318: board תל אביב ההגנה [code 17104] 13:30 -> alight תל אביב מרכז [code 17038] 13:38 (service date 2026-11-17, trip `1_533057`)
5. Walk 1 min, 27 m: תל אביב מרכז 13:38 -> END 13:39

Transfers (alight to next boarding, including any walk): ת.רכבת ההגנה -> תל אביב ההגנה: 6 min

**Option 3:** departs Tue 2026-11-17 13:07, arrives Tue 2026-11-17 13:42; total 35 min, 0 transfer(s), walking 21 min / 1366 m

1. Walk 13 min, 879 m: START 13:07 -> שלמה 13:20
2. **light_rail 1** (תבל) toward פתח תקווה_ת. מרכזית פתח תקווה: board שלמה [code 20546] 13:20 -> alight ארלוזורוב [code 20711] 13:34 (service date 2026-11-17, trip `585355926_111126`)
3. Walk 8 min, 487 m: ארלוזורוב 13:34 -> END 13:42

Transfers (alight to next boarding, including any walk): none

| Usable? (Y/N) | Notes | Compared against / when checked |
|---|---|---|
|  |  |  |

---

## J04 — Dizengoff Center (דיזנגוף סנטר) → Petah Tikva Kiryat Arye (פתח תקווה קרית אריה)

**Required journey #2** — PRD §7 #2 Tel Aviv → Petah Tikva · category `tel-aviv-urban-bus` · calendar rule `weekday_evening`

**Requested:** Depart at Wed 2026-11-11 18:30 (UTC+02:00)  
Request field: `departAt=2026-11-11T18:30:00+02:00`
**Calendar flags:** ordinary day
**Compare:** [Google Maps transit](https://www.google.com/maps/dir/?api=1&origin=32.0757,34.7748&destination=32.0956,34.8556&travelmode=transit) · [Moovit (unofficial deep link; may not prefill)](https://moovitapp.com/?fll=32.0757_34.7748&tll=32.0956_34.8556&from=Dizengoff%20Center&to=Petah%20Tikva%20Kiryat%20Arye) · Set the time yourself to **Depart at 18:30, Wed 2026-11-11** (Google's documented URL has no time parameter).
**Corpus expectation (context, not a verdict):** outcome `route`, max_duration_min = 90, max_transfers = 2, min_duration_min = 20, modes_any_of = ['bus', 'rail', 'light_rail']

> What to check: Evening peak. Does it prefer rail or bus, and is that the right call?

**API RESULT: 3 journey option(s) returned** (scheduled times).
Machine note: matches the corpus expectation `route`. This is not a judgement of quality.
Request id `e43234d1bbeb4faba3d647747b772f35`.

**Option 1:** departs Wed 2026-11-11 18:31, arrives Wed 2026-11-11 19:06; total 35 min, 1 transfer(s), walking 13 min / 705 m

1. Walk 3 min, 135 m: START 18:31 -> דיזנגוף סנטר/דיזנגוף 18:34
2. **bus 63** (דן) toward רמת גן_אלוף שדה: board דיזנגוף סנטר/דיזנגוף [code 25565] 18:34 -> alight ת.רק''ל יהודית/דרך מנחם בגין [code 20727] 18:41 (service date 2026-11-11, trip `668964_111126`)
3. Walk 2 min, 93 m: ת.רק''ל יהודית/דרך מנחם בגין 18:41 -> יהודית 18:43
4. **light_rail 1** (תבל) toward פתח תקווה_ת. מרכזית פתח תקווה: board יהודית [code 20707] 18:43 -> alight שנקר [code 36309] 18:58 (service date 2026-11-11, trip `585268659_111126`)
5. Walk 8 min, 477 m: שנקר 18:58 -> END 19:06

Transfers (alight to next boarding, including any walk): ת.רק''ל יהודית/דרך מנחם בגין -> יהודית: 2 min

**Option 2:** departs Wed 2026-11-11 18:36, arrives Wed 2026-11-11 19:11; total 35 min, 0 transfer(s), walking 13 min / 753 m

1. Walk 5 min, 294 m: START 18:36 -> דיזנגוף סנטר/המלך ג'ורג' 18:41
2. **bus 82** (דן) toward פתח תקווה_בית רבקה: board דיזנגוף סנטר/המלך ג'ורג' [code 20785] 18:41 -> alight ת.רק''ל שנקר/דרך ז'בוטינסקי [code 32270] 19:03 (service date 2026-11-11, trip `8685495_111126`)
3. Walk 8 min, 459 m: ת.רק''ל שנקר/דרך ז'בוטינסקי 19:03 -> END 19:11

Transfers (alight to next boarding, including any walk): none

**Option 3:** departs Wed 2026-11-11 18:42, arrives Wed 2026-11-11 19:17; total 35 min, 1 transfer(s), walking 13 min / 705 m

1. Walk 3 min, 135 m: START 18:42 -> דיזנגוף סנטר/דיזנגוף 18:45
2. **bus 63** (דן) toward רמת גן_אלוף שדה: board דיזנגוף סנטר/דיזנגוף [code 25565] 18:45 -> alight ת.רק''ל יהודית/דרך מנחם בגין [code 20727] 18:52 (service date 2026-11-11, trip `13986014_111126`)
3. Walk 2 min, 93 m: ת.רק''ל יהודית/דרך מנחם בגין 18:52 -> יהודית 18:54
4. **light_rail 1** (תבל) toward פתח תקווה_ת. מרכזית פתח תקווה: board יהודית [code 20707] 18:54 -> alight שנקר [code 36309] 19:09 (service date 2026-11-11, trip `585373632_111126`)
5. Walk 8 min, 477 m: שנקר 19:09 -> END 19:17

Transfers (alight to next boarding, including any walk): ת.רק''ל יהודית/דרך מנחם בגין -> יהודית: 2 min

| Usable? (Y/N) | Notes | Compared against / when checked |
|---|---|---|
|  |  |  |

---

## J05 — Mahane Yehuda Market (שוק מחנה יהודה) → Mount Herzl (הר הרצל)

category `jerusalem-urban-light-rail` · calendar rule `weekday_midday`

**Requested:** Depart at Tue 2026-11-17 13:00 (UTC+02:00)  
Request field: `departAt=2026-11-17T13:00:00+02:00`
**Calendar flags:** ordinary day
**Compare:** [Google Maps transit](https://www.google.com/maps/dir/?api=1&origin=31.7853,35.2124&destination=31.7736,35.1806&travelmode=transit) · [Moovit (unofficial deep link; may not prefill)](https://moovitapp.com/?fll=31.7853_35.2124&tll=31.7736_35.1806&from=Mahane%20Yehuda%20Market&to=Mount%20Herzl) · Set the time yourself to **Depart at 13:00, Tue 2026-11-17** (Google's documented URL has no time parameter).
**Corpus expectation (context, not a verdict):** outcome `route`, max_duration_min = 45, max_transfers = 1, min_duration_min = 8, modes_any_of = ['light_rail', 'bus']

> What to check: This is the light rail's spine. If it routes by bus instead, something is wrong.

**API RESULT: 3 journey option(s) returned** (scheduled times).
Machine note: matches the corpus expectation `route`. This is not a judgement of quality.
Request id `ead6cc6648734a85be370120aff8da5d`.

**Option 1:** departs Tue 2026-11-17 13:02, arrives Tue 2026-11-17 13:27; total 25 min, 0 transfer(s), walking 11 min / 706 m

1. Walk 2 min, 145 m: START 13:02 -> מחנה יהודה 13:04
2. **light_rail 1** (כפיר) toward הדסה עין כרם: board מחנה יהודה [code 6172] 13:04 -> alight הר הרצל [code 6185] 13:18 (service date 2026-11-17, trip `12467281_111126`)
3. Walk 9 min, 561 m: הר הרצל 13:18 -> END 13:27

Transfers (alight to next boarding, including any walk): none

**Option 2:** departs Tue 2026-11-17 13:08, arrives Tue 2026-11-17 13:33; total 25 min, 0 transfer(s), walking 11 min / 706 m

1. Walk 2 min, 145 m: START 13:08 -> מחנה יהודה 13:10
2. **light_rail 1** (כפיר) toward הדסה עין כרם: board מחנה יהודה [code 6172] 13:10 -> alight הר הרצל [code 6185] 13:24 (service date 2026-11-17, trip `18451290_111126`)
3. Walk 9 min, 561 m: הר הרצל 13:24 -> END 13:33

Transfers (alight to next boarding, including any walk): none

**Option 3:** departs Tue 2026-11-17 13:14, arrives Tue 2026-11-17 13:39; total 25 min, 0 transfer(s), walking 11 min / 706 m

1. Walk 2 min, 145 m: START 13:14 -> מחנה יהודה 13:16
2. **light_rail 1** (כפיר) toward הדסה עין כרם: board מחנה יהודה [code 6172] 13:16 -> alight הר הרצל [code 6185] 13:30 (service date 2026-11-17, trip `38553409_111126`)
3. Walk 9 min, 561 m: הר הרצל 13:30 -> END 13:39

Transfers (alight to next boarding, including any walk): none

| Usable? (Y/N) | Notes | Compared against / when checked |
|---|---|---|
|  |  |  |

---

## J06 — Jerusalem Central Bus Station (תחנה מרכזית ירושלים) → Hebrew University Mount Scopus (האוניברסיטה העברית הר הצופים)

category `jerusalem-urban-light-rail` · calendar rule `weekday_morning`

**Requested:** Depart at Mon 2026-11-16 08:00 (UTC+02:00)  
Request field: `departAt=2026-11-16T08:00:00+02:00`
**Calendar flags:** ordinary day
**Compare:** [Google Maps transit](https://www.google.com/maps/dir/?api=1&origin=31.7887,35.203&destination=31.7936,35.2444&travelmode=transit) · [Moovit (unofficial deep link; may not prefill)](https://moovitapp.com/?fll=31.7887_35.203&tll=31.7936_35.2444&from=Jerusalem%20Central%20Bus%20Station&to=Hebrew%20University%20Mount%20Scopus) · Set the time yourself to **Depart at 08:00, Mon 2026-11-16** (Google's documented URL has no time parameter).
**Corpus expectation (context, not a verdict):** outcome `route`, max_duration_min = 70, max_transfers = 2, min_duration_min = 15, modes_any_of = ['light_rail', 'bus']

> What to check: Cross-city to Mount Scopus. Check the transfer point is a real interchange.

**API RESULT: 3 journey option(s) returned** (scheduled times).
Machine note: matches the corpus expectation `route`. This is not a judgement of quality.
Request id `0aff3584f335440d9fe5636d990acbbc`.

**Option 1:** departs Mon 2026-11-16 08:01, arrives Mon 2026-11-16 08:28; total 27 min, 1 transfer(s), walking 8 min / 347 m

1. Walk 1 min, 57 m: START 08:01 -> ת. מרכזית ירושלים/יפו 08:02
2. **bus 18** (אגד) toward מלחה: board ת. מרכזית ירושלים/יפו [code 4156] 08:02 -> alight ככר הדוידקה/הנביאים [code 1601] 08:07 (service date 2026-11-16, trip `8412260_111126`)
3. Walk 2 min, 0 m: ככר הדוידקה/הנביאים 08:07 -> ככר הדוידקה/הנביאים 08:09
4. **bus 19א** (אגד) toward מסוף הר הצופים: board ככר הדוידקה/הנביאים [code 1601] 08:12 -> alight האוניברסיטה העברית הר הצופים/מרטין בובר [code 1371] 08:23 (service date 2026-11-16, trip `8821728_111126`)
5. Walk 5 min, 290 m: האוניברסיטה העברית הר הצופים/מרטין בובר 08:23 -> END 08:28

Transfers (alight to next boarding, including any walk): ככר הדוידקה/הנביאים -> ככר הדוידקה/הנביאים: 5 min

**Option 2:** departs Mon 2026-11-16 08:07, arrives Mon 2026-11-16 08:30; total 23 min, 0 transfer(s), walking 10 min / 623 m

1. Walk 5 min, 333 m: START 08:07 -> שרי ישראל/יפו 08:12
2. **bus 568** (אקסטרה ירושלים) toward מסוף הר הצופים: board שרי ישראל/יפו [code 78] 08:12 -> alight האוניברסיטה העברית הר הצופים/מרטין בובר [code 1371] 08:25 (service date 2026-11-16, trip `585640504_131126`)
3. Walk 5 min, 290 m: האוניברסיטה העברית הר הצופים/מרטין בובר 08:25 -> END 08:30

Transfers (alight to next boarding, including any walk): none

**Option 3:** departs Mon 2026-11-16 08:08, arrives Mon 2026-11-16 08:32; total 24 min, 1 transfer(s), walking 8 min / 347 m

1. Walk 1 min, 57 m: START 08:08 -> ת. מרכזית ירושלים/יפו 08:09
2. **bus 74** (סופרבוס) toward חומת שמואל: board ת. מרכזית ירושלים/יפו [code 4156] 08:09 -> alight הנביאים/הרב קוק [code 3379] 08:16 (service date 2026-11-16, trip `584794982_151126`)
3. Walk 2 min, 0 m: הנביאים/הרב קוק 08:16 -> הנביאים/הרב קוק 08:18
4. **bus 19** (אגד) toward מסוף הר הצופים: board הנביאים/הרב קוק [code 3379] 08:18 -> alight האוניברסיטה העברית הר הצופים/מרטין בובר [code 1371] 08:27 (service date 2026-11-16, trip `585944010_111126`)
5. Walk 5 min, 290 m: האוניברסיטה העברית הר הצופים/מרטין בובר 08:27 -> END 08:32

Transfers (alight to next boarding, including any walk): הנביאים/הרב קוק -> הנביאים/הרב קוק: 2 min

| Usable? (Y/N) | Notes | Compared against / when checked |
|---|---|---|
|  |  |  |

---

## J07 — Yitzhak Navon Station (תחנת יצחק נבון) → Malha Mall (קניון מלחא)

category `jerusalem-urban-light-rail` · calendar rule `weekday_evening`

**Requested:** Depart at Wed 2026-11-11 18:30 (UTC+02:00)  
Request field: `departAt=2026-11-11T18:30:00+02:00`
**Calendar flags:** ordinary day
**Compare:** [Google Maps transit](https://www.google.com/maps/dir/?api=1&origin=31.7888,35.2027&destination=31.7513,35.1875&travelmode=transit) · [Moovit (unofficial deep link; may not prefill)](https://moovitapp.com/?fll=31.7888_35.2027&tll=31.7513_35.1875&from=Yitzhak%20Navon%20Station&to=Malha%20Mall) · Set the time yourself to **Depart at 18:30, Wed 2026-11-11** (Google's documented URL has no time parameter).
**Corpus expectation (context, not a verdict):** outcome `route`, max_duration_min = 70, max_transfers = 2, min_duration_min = 15, modes_any_of = ['light_rail', 'bus', 'rail']

> What to check: Does it consider the Malha rail branch, and is that sensible at this hour?

**API RESULT: 3 journey option(s) returned** (scheduled times).
Machine note: matches the corpus expectation `route`. This is not a judgement of quality.
Request id `b8bc407ce3074e3e89174c20db393939`.

**Option 1:** departs Wed 2026-11-11 18:31, arrives Wed 2026-11-11 18:49; total 18 min, 0 transfer(s), walking 10 min / 649 m

1. Walk 4 min, 227 m: START 18:31 -> שדרות שז''ר/בנייני האומה 18:35
2. **bus 31** (סופרבוס) toward גילה: board שדרות שז''ר/בנייני האומה [code 463] 18:35 -> alight קניון מלחה/א''ס הפועל   האייל [code 2913] 18:43 (service date 2026-11-11, trip `584872013_111126`)
3. Walk 6 min, 422 m: קניון מלחה/א''ס הפועל   האייל 18:43 -> END 18:49

Transfers (alight to next boarding, including any walk): none

**Option 2:** departs Wed 2026-11-11 18:34, arrives Wed 2026-11-11 18:57; total 23 min, 0 transfer(s), walking 14 min / 532 m

1. Walk 4 min, 227 m: START 18:34 -> שדרות שז''ר/בנייני האומה 18:38
2. **bus 504** (סופרבוס) toward חומת שמואל: board שדרות שז''ר/בנייני האומה [code 463] 18:38 -> alight אצטדיון טדי/א''ס ביתר [code 222] 18:47 (service date 2026-11-11, trip `584865032_111126`)
3. Walk 10 min, 305 m: אצטדיון טדי/א''ס ביתר 18:47 -> END 18:57

Transfers (alight to next boarding, including any walk): none

**Option 3:** departs Wed 2026-11-11 18:36, arrives Wed 2026-11-11 19:00; total 24 min, 0 transfer(s), walking 10 min / 367 m

1. Walk 4 min, 227 m: START 18:36 -> שדרות שז''ר/בנייני האומה 18:40
2. **bus 509** (סופרבוס) toward מלחה: board שדרות שז''ר/בנייני האומה [code 463] 18:40 -> alight קניון מלחה/א''ס מכבי [code 4171] 18:54 (service date 2026-11-11, trip `585413242_111126`)
3. Walk 6 min, 140 m: קניון מלחה/א''ס מכבי 18:54 -> END 19:00

Transfers (alight to next boarding, including any walk): none

| Usable? (Y/N) | Notes | Compared against / when checked |
|---|---|---|
|  |  |  |

---

## J08 — Haifa Center HaShmona (חיפה מרכז השמונה) → Technion (הטכניון)

category `haifa-urban` · calendar rule `weekday_morning`

**Requested:** Depart at Mon 2026-11-16 08:00 (UTC+02:00)  
Request field: `departAt=2026-11-16T08:00:00+02:00`
**Calendar flags:** ordinary day
**Compare:** [Google Maps transit](https://www.google.com/maps/dir/?api=1&origin=32.8206,34.9985&destination=32.7767,35.0217&travelmode=transit) · [Moovit (unofficial deep link; may not prefill)](https://moovitapp.com/?fll=32.8206_34.9985&tll=32.7767_35.0217&from=Haifa%20Center%20HaShmona&to=Technion) · Set the time yourself to **Depart at 08:00, Mon 2026-11-16** (Google's documented URL has no time parameter).
**Corpus expectation (context, not a verdict):** outcome `route`, max_duration_min = 75, max_transfers = 2, min_duration_min = 15, modes_any_of = ['bus', 'cable_car', 'funicular']

> What to check: Haifa is vertical. Check the walking legs are not absurd gradients.

**API RESULT: 3 journey option(s) returned** (scheduled times).
Machine note: matches the corpus expectation `route`. This is not a judgement of quality.
Request id `d3c2374f01a241d293e493c471c1fb99`.

**Option 1:** departs Mon 2026-11-16 08:01, arrives Mon 2026-11-16 08:42; total 41 min, 2 transfer(s), walking 16 min / 926 m

1. Walk 7 min, 438 m: START 08:01 -> המגינים/ככר ההגנה 08:08
2. **bus 3** (אגד) toward מרכזית חוף הכרמל: board המגינים/ככר ההגנה [code 42723] 08:08 -> alight העירייה [code 42866] 08:15 (service date 2026-11-16, trip `10378671_151126`)
3. Walk 2 min, 0 m: העירייה 08:15 -> העירייה 08:17
4. **bus 148** (אגד) toward חיפה_אוניברסיטה: board העירייה [code 42866] 08:17 -> alight חנקין/קומוי [code 41201] 08:32 (service date 2026-11-16, trip `585108217_111126`)
5. Walk 2 min, 175 m: חנקין/קומוי 08:32 -> קומוי/חנקין 08:34
6. **bus 77** (אגד) toward יגור_מסוף יגור: board קומוי/חנקין [code 41202] 08:35 -> alight טכניון/מעונות העמים [code 41200] 08:37 (service date 2026-11-16, trip `16151688_111126`)
7. Walk 5 min, 313 m: טכניון/מעונות העמים 08:37 -> END 08:42

Transfers (alight to next boarding, including any walk): העירייה -> העירייה: 2 min; חנקין/קומוי -> קומוי/חנקין: 3 min

**Option 2:** departs Mon 2026-11-16 08:05, arrives Mon 2026-11-16 08:45; total 40 min, 0 transfer(s), walking 16 min / 1032 m

1. Walk 11 min, 719 m: START 08:05 -> תחנת רכבת חיפה מרכז השמונה 08:16
2. **bus 17** (אגד) toward טכניון: board תחנת רכבת חיפה מרכז השמונה [code 41540] 08:16 -> alight טכניון/מעונות העמים [code 41200] 08:40 (service date 2026-11-16, trip `2842328_151126`)
3. Walk 5 min, 313 m: טכניון/מעונות העמים 08:40 -> END 08:45

Transfers (alight to next boarding, including any walk): none

**Option 3:** departs Mon 2026-11-16 08:08, arrives Mon 2026-11-16 08:50; total 42 min, 1 transfer(s), walking 14 min / 858 m

1. Walk 7 min, 438 m: START 08:08 -> המגינים/ככר ההגנה 08:15
2. **bus 16** (אגד) toward מרכזית המפרץ: board המגינים/ככר ההגנה [code 42723] 08:15 -> alight חנקין/קומוי [code 41886] 08:38 (service date 2026-11-16, trip `7083211_111126`)
3. Walk 2 min, 107 m: חנקין/קומוי 08:38 -> קומוי/חנקין 08:40
4. **bus 76** (אגד) toward יגור_מסוף יגור: board קומוי/חנקין [code 41202] 08:43 -> alight טכניון/מעונות העמים [code 41200] 08:45 (service date 2026-11-16, trip `585688536_111126`)
5. Walk 5 min, 313 m: טכניון/מעונות העמים 08:45 -> END 08:50

Transfers (alight to next boarding, including any walk): חנקין/קומוי -> קומוי/חנקין: 5 min

| Usable? (Y/N) | Notes | Compared against / when checked |
|---|---|---|
|  |  |  |

---

## J09 — Haifa University (אוניברסיטת חיפה) → Bat Galim Central Station (חיפה בת גלים)

category `haifa-urban` · calendar rule `weekday_evening`

**Requested:** Depart at Wed 2026-11-11 18:30 (UTC+02:00)  
Request field: `departAt=2026-11-11T18:30:00+02:00`
**Calendar flags:** ordinary day
**Compare:** [Google Maps transit](https://www.google.com/maps/dir/?api=1&origin=32.7614,35.0207&destination=32.8283,34.9539&travelmode=transit) · [Moovit (unofficial deep link; may not prefill)](https://moovitapp.com/?fll=32.7614_35.0207&tll=32.8283_34.9539&from=Haifa%20University&to=Bat%20Galim%20Central%20Station) · Set the time yourself to **Depart at 18:30, Wed 2026-11-11** (Google's documented URL has no time parameter).
**Corpus expectation (context, not a verdict):** outcome `route`, max_duration_min = 85, max_transfers = 2, min_duration_min = 20, modes_any_of = ['bus', 'rail']

> What to check: Long descent across the Carmel. Compare to Moovit for line choice.

**API RESULT: NO ROUTE** — a valid search inside coverage returned no journey. The API does not state a cause (no service, walking limit and data gaps look alike).
Machine note: DIFFERS FROM the corpus expectation `route`. This is not a judgement of quality.
Request id `c146b156fd544a3cbd4f1bf0ca85a008`.

| Usable? (Y/N) | Notes | Compared against / when checked |
|---|---|---|
|  |  |  |

---

## J10 — Grand Kanyon Haifa (גראנד קניון חיפה) → Rambam Medical Center (בית חולים רמבם)

category `haifa-urban` · calendar rule `weekday_midday`

**Requested:** Depart at Tue 2026-11-17 13:00 (UTC+02:00)  
Request field: `departAt=2026-11-17T13:00:00+02:00`
**Calendar flags:** ordinary day
**Compare:** [Google Maps transit](https://www.google.com/maps/dir/?api=1&origin=32.7943,34.9891&destination=32.8347,34.9857&travelmode=transit) · [Moovit (unofficial deep link; may not prefill)](https://moovitapp.com/?fll=32.7943_34.9891&tll=32.8347_34.9857&from=Grand%20Kanyon%20Haifa&to=Rambam%20Medical%20Center) · Set the time yourself to **Depart at 13:00, Tue 2026-11-17** (Google's documented URL has no time parameter).
**Corpus expectation (context, not a verdict):** outcome `route`, max_duration_min = 70, max_transfers = 2, min_duration_min = 12, modes_any_of = ['bus', 'rail', 'funicular']

> What to check: Mall to hospital. Does the Metronit BRT get used?

**API RESULT: 3 journey option(s) returned** (scheduled times).
Machine note: matches the corpus expectation `route`. This is not a judgement of quality.
Request id `f754646e636643ea8244b127d903c7eb`.

**Option 1:** departs Tue 2026-11-17 13:00, arrives Tue 2026-11-17 13:44; total 44 min, 0 transfer(s), walking 21 min / 1274 m

1. Walk 11 min, 665 m: START 13:00 -> מוריה/ספקטור 13:11
2. **bus 136** (אגד) toward חיפה_רכבת בת גלים: board מוריה/ספקטור [code 40990] 13:11 -> alight ת. רכבת בת גלים [code 47181] 13:34 (service date 2026-11-17, trip `10387657_151126`)
3. Walk 10 min, 609 m: ת. רכבת בת גלים 13:34 -> END 13:44

Transfers (alight to next boarding, including any walk): none

**Option 2:** departs Tue 2026-11-17 13:01, arrives Tue 2026-11-17 13:47; total 46 min, 1 transfer(s), walking 21 min / 1438 m

1. Walk 11 min, 665 m: START 13:01 -> מוריה/ספקטור 13:12
2. **bus 58** (סופרבוס) toward חיפה_רכבת מרכז השמונה: board מוריה/ספקטור [code 40990] 13:12 -> alight דרך סטלה מאריס [code 40666] 13:29 (service date 2026-11-17, trip `584902463_111126`)
3. Walk 2 min, 317 m: דרך סטלה מאריס 13:29 -> הברון הירש/אלנבי 13:31
4. **bus 40** (אגד) toward תחנת הרכבל: board הברון הירש/אלנבי [code 41112] 13:33 -> alight העליה השניה/עפרון [code 41159] 13:39 (service date 2026-11-17, trip `1312483_111126`)
5. Walk 8 min, 456 m: העליה השניה/עפרון 13:39 -> END 13:47

Transfers (alight to next boarding, including any walk): דרך סטלה מאריס -> הברון הירש/אלנבי: 4 min

**Option 3:** departs Tue 2026-11-17 13:03, arrives Tue 2026-11-17 13:50; total 47 min, 0 transfer(s), walking 22 min / 1303 m

1. Walk 11 min, 665 m: START 13:03 -> מוריה/ספקטור 13:14
2. **bus 31** (אגד) toward רכבת בת גלים: board מוריה/ספקטור [code 40990] 13:14 -> alight חיל הים/העלייה השנייה [code 42746] 13:39 (service date 2026-11-17, trip `584813463_151126`)
3. Walk 11 min, 638 m: חיל הים/העלייה השנייה 13:39 -> END 13:50

Transfers (alight to next boarding, including any walk): none

| Usable? (Y/N) | Notes | Compared against / when checked |
|---|---|---|
|  |  |  |

---

## J11 — Tel Aviv Savidor Center (תל אביב סבידור מרכז) → Haifa Center HaShmona (חיפה מרכז השמונה)

**Required journey #3** — PRD §7 #3 Tel Aviv → Haifa · category `intercity-rail` · calendar rule `weekday_morning`

**Requested:** Depart at Mon 2026-11-16 08:00 (UTC+02:00)  
Request field: `departAt=2026-11-16T08:00:00+02:00`
**Calendar flags:** ordinary day
**Compare:** [Google Maps transit](https://www.google.com/maps/dir/?api=1&origin=32.0836,34.7981&destination=32.8206,34.9985&travelmode=transit) · [Moovit (unofficial deep link; may not prefill)](https://moovitapp.com/?fll=32.0836_34.7981&tll=32.8206_34.9985&from=Tel%20Aviv%20Savidor%20Center&to=Haifa%20Center%20HaShmona) · Set the time yourself to **Depart at 08:00, Mon 2026-11-16** (Google's documented URL has no time parameter).
**Corpus expectation (context, not a verdict):** outcome `route`, max_duration_min = 130, max_transfers = 1, min_duration_min = 45, modes_any_of = ['rail']

> What to check: The flagship rail corridor. Cross-check timings against BetterRail.

API warnings: TRANSFER_STREET_PATH_UNAVAILABLE

**API RESULT: 3 journey option(s) returned** (scheduled times).
Machine note: matches the corpus expectation `route`. This is not a judgement of quality.
Request id `28982b7336fe4e14bc42316c9da33cf9`.

**Option 1:** departs Mon 2026-11-16 08:12, arrives Mon 2026-11-16 09:35; total 83 min, 1 transfer(s), walking 10 min / 617 m

1. Walk 1 min, 27 m: START 08:12 -> תל אביב מרכז 08:13
2. **rail ** (רכבת ישראל) toward 24: board תל אביב מרכז [code 17038] 08:13 -> alight בת גלים [code 17018] 09:18 (service date 2026-11-16, trip `1_531713`)
3. Walk 2 min, 152 m: בת גלים 09:18 -> ת. רכבת בת גלים 09:20
4. **bus 236** (אגד) toward אוניברסיטה: board ת. רכבת בת גלים [code 47181] 09:20 -> alight המגינים/ככר ההגנה [code 42723] 09:28 (service date 2026-11-16, trip `584814283_111126`)
5. Walk 7 min, 438 m: המגינים/ככר ההגנה 09:28 -> END 09:35

Transfers (alight to next boarding, including any walk): בת גלים -> ת. רכבת בת גלים: 2 min

**Option 2:** departs Mon 2026-11-16 08:26, arrives Mon 2026-11-16 09:52; total 86 min, 1 transfer(s), walking 14 min / unknown distance

1. Walk 1 min, 27 m: START 08:26 -> תל אביב מרכז 08:27
2. **rail ** (רכבת ישראל) toward 156: board תל אביב מרכז [code 17038] 08:27 -> alight חיפה מרכז [code 17016] 09:38 (service date 2026-11-16, trip `1_531478`)
3. Walk 4 min (timetable transfer; street path unavailable): חיפה מרכז 09:38 -> תחנת רכבת חיפה מרכז השמונה 09:42
4. **bus 1** (סופרבוס) toward קרית מוצקין_מרכזית הקריות: board תחנת רכבת חיפה מרכז השמונה [code 47574] 09:42 -> alight כרמלית [code 47576] 09:43 (service date 2026-11-16, trip `12078238_111126`)
5. Walk 9 min, 564 m: כרמלית 09:43 -> END 09:52

Transfers (alight to next boarding, including any walk): חיפה מרכז -> תחנת רכבת חיפה מרכז השמונה: 4 min

**Option 3:** departs Mon 2026-11-16 08:46, arrives Mon 2026-11-16 10:08; total 82 min, 1 transfer(s), walking 14 min / 898 m

1. Walk 1 min, 27 m: START 08:46 -> תל אביב מרכז 08:47
2. **rail ** (רכבת ישראל) toward 404: board תל אביב מרכז [code 17038] 08:47 -> alight בת גלים [code 17018] 09:47 (service date 2026-11-16, trip `1_531147`)
3. Walk 2 min, 152 m: בת גלים 09:47 -> ת. רכבת בת גלים 09:49
4. **bus 18** (אגד) toward נווה שאנן: board ת. רכבת בת גלים [code 47181] 09:50 -> alight תחנת רכבת חיפה מרכז השמונה [code 41540] 09:57 (service date 2026-11-16, trip `25308365_151126`)
5. Walk 11 min, 719 m: תחנת רכבת חיפה מרכז השמונה 09:57 -> END 10:08

Transfers (alight to next boarding, including any walk): בת גלים -> ת. רכבת בת גלים: 3 min

| Usable? (Y/N) | Notes | Compared against / when checked |
|---|---|---|
|  |  |  |

---

## J12 — Tel Aviv Savidor Center (תל אביב סבידור מרכז) → Yitzhak Navon Station (תחנת יצחק נבון)

**Required journey #4** — PRD §7 #4 Tel Aviv → Jerusalem · category `intercity-rail` · calendar rule `weekday_morning`

**Requested:** Depart at Mon 2026-11-16 08:00 (UTC+02:00)  
Request field: `departAt=2026-11-16T08:00:00+02:00`
**Calendar flags:** ordinary day
**Compare:** [Google Maps transit](https://www.google.com/maps/dir/?api=1&origin=32.0836,34.7981&destination=31.7888,35.2027&travelmode=transit) · [Moovit (unofficial deep link; may not prefill)](https://moovitapp.com/?fll=32.0836_34.7981&tll=31.7888_35.2027&from=Tel%20Aviv%20Savidor%20Center&to=Yitzhak%20Navon%20Station) · Set the time yourself to **Depart at 08:00, Mon 2026-11-16** (Google's documented URL has no time parameter).
**Corpus expectation (context, not a verdict):** outcome `route`, max_duration_min = 110, max_transfers = 1, min_duration_min = 30, modes_any_of = ['rail']

> What to check: Fast line. If it routes by bus, the rail calendar is probably misread.

**API RESULT: 3 journey option(s) returned** (scheduled times).
Machine note: matches the corpus expectation `route`. This is not a judgement of quality.
Request id `8e9a37b8c434461a953555a8d135b083`.

**Option 1:** departs Mon 2026-11-16 08:17, arrives Mon 2026-11-16 09:05; total 48 min, 0 transfer(s), walking 4 min / 207 m

1. Walk 1 min, 27 m: START 08:17 -> תל אביב מרכז 08:18
2. **rail ** (רכבת ישראל) toward 723: board תל אביב מרכז [code 17038] 08:18 -> alight ירושלים/יצחק נבון [code 17118] 09:02 (service date 2026-11-16, trip `1_531687`)
3. Walk 3 min, 180 m: ירושלים/יצחק נבון 09:02 -> END 09:05

Transfers (alight to next boarding, including any walk): none

**Option 2:** departs Mon 2026-11-16 08:47, arrives Mon 2026-11-16 09:22; total 35 min, 0 transfer(s), walking 4 min / 207 m

1. Walk 1 min, 27 m: START 08:47 -> תל אביב מרכז 08:48
2. **rail ** (רכבת ישראל) toward 2759: board תל אביב מרכז [code 17038] 08:48 -> alight ירושלים/יצחק נבון [code 17118] 09:19 (service date 2026-11-16, trip `1_531527`)
3. Walk 3 min, 180 m: ירושלים/יצחק נבון 09:19 -> END 09:22

Transfers (alight to next boarding, including any walk): none

**Option 3:** departs Mon 2026-11-16 08:54, arrives Mon 2026-11-16 09:58; total 64 min, 1 transfer(s), walking 13 min / 1304 m

1. Walk 6 min, 403 m: START 08:54 -> ת.רכבת תל אביב - סבידור/רציפים B 09:00
2. **bus 490** (אגד) toward ירושלים_אזור תעשיה תלפיות: board ת.רכבת תל אביב - סבידור/רציפים B [code 20740] 09:00 -> alight מחלף חמד [code 640] 09:38 (service date 2026-11-16, trip `586145832_111126`)
3. Walk 2 min, 0 m: מחלף חמד 09:38 -> מחלף חמד 09:40
4. **bus 615** (תנופה) toward ירושלים_בנייני האומה: board מחלף חמד [code 640] 09:42 -> alight שדרות שז''ר/בנייני האומה [code 4218] 09:53 (service date 2026-11-16, trip `584795976_131126`)
5. Walk 5 min, 901 m: שדרות שז''ר/בנייני האומה 09:53 -> END 09:58

Transfers (alight to next boarding, including any walk): מחלף חמד -> מחלף חמד: 4 min

| Usable? (Y/N) | Notes | Compared against / when checked |
|---|---|---|
|  |  |  |

---

## J13 — Tel Aviv HaShalom (תל אביב השלום) → Beersheba Central (באר שבע מרכז)

category `intercity-rail` · calendar rule `weekday_midday`

**Requested:** Depart at Tue 2026-11-17 13:00 (UTC+02:00)  
Request field: `departAt=2026-11-17T13:00:00+02:00`
**Calendar flags:** ordinary day
**Compare:** [Google Maps transit](https://www.google.com/maps/dir/?api=1&origin=32.0731,34.7925&destination=31.243,34.7983&travelmode=transit) · [Moovit (unofficial deep link; may not prefill)](https://moovitapp.com/?fll=32.0731_34.7925&tll=31.243_34.7983&from=Tel%20Aviv%20HaShalom&to=Beersheba%20Central) · Set the time yourself to **Depart at 13:00, Tue 2026-11-17** (Google's documented URL has no time parameter).
**Corpus expectation (context, not a verdict):** outcome `route`, max_duration_min = 180, max_transfers = 1, min_duration_min = 60, modes_any_of = ['rail']

> What to check: Long-distance south. Is the itinerary the direct train or a silly chain?

**API RESULT: 3 journey option(s) returned** (scheduled times).
Machine note: matches the corpus expectation `route`. This is not a judgement of quality.
Request id `0b06522350604700a3a0c160b14b314c`.

**Option 1:** departs Tue 2026-11-17 13:13, arrives Tue 2026-11-17 14:54; total 101 min, 0 transfer(s), walking 5 min / 314 m

1. Walk 4 min, 270 m: START 13:13 -> השלום 13:17
2. **rail ** (רכבת ישראל) toward 33: board השלום [code 17046] 13:17 -> alight באר שבע מרכז [code 17084] 14:53 (service date 2026-11-17, trip `1_531747`)
3. Walk 1 min, 44 m: באר שבע מרכז 14:53 -> END 14:54

Transfers (alight to next boarding, including any walk): none

**Option 2:** departs Tue 2026-11-17 13:37, arrives Tue 2026-11-17 15:20; total 103 min, 0 transfer(s), walking 5 min / 314 m

1. Walk 4 min, 270 m: START 13:37 -> השלום 13:41
2. **rail ** (רכבת ישראל) toward 643: board השלום [code 17046] 13:41 -> alight באר שבע מרכז [code 17084] 15:19 (service date 2026-11-17, trip `1_532816`)
3. Walk 1 min, 44 m: באר שבע מרכז 15:19 -> END 15:20

Transfers (alight to next boarding, including any walk): none

**Option 3:** departs Tue 2026-11-17 13:41, arrives Tue 2026-11-17 15:35; total 114 min, 2 transfer(s), walking 20 min / 1406 m

1. Walk 6 min, 299 m: START 13:41 -> יגאל אלון/דרך השלום 13:47
2. **bus 46** (דן) toward בת ים_בית עלמין: board יגאל אלון/דרך השלום [code 21487] 13:47 -> alight ת.רכבת ההגנה [code 25638] 13:57 (service date 2026-11-17, trip `585411959_161126`)
3. Walk 2 min, 357 m: ת.רכבת ההגנה 13:58 -> מסוף ההגנה/איסוף 14:00
4. **bus 114** (דן) toward מסוף רכבת ההגנה: board מסוף ההגנה/איסוף [code 20860] 14:00 -> alight גשר קיבוץ גלויות [code 25287] 14:02 (service date 2026-11-17, trip `585060824_161126`)
5. Walk 2 min, 96 m: גשר קיבוץ גלויות 14:02 -> דרך קיבוץ גלויות/כביש 1 14:04
6. **bus 370** (מטרופולין) toward באר שבע_תחנה מרכזית: board דרך קיבוץ גלויות/כביש 1 [code 25069] 14:04 -> alight ת.מרכזית באר שבע/הורדה [code 15657] 15:25 (service date 2026-11-17, trip `2821988_131126`)
7. Walk 10 min, 654 m: ת.מרכזית באר שבע/הורדה 15:25 -> END 15:35

Transfers (alight to next boarding, including any walk): ת.רכבת ההגנה -> מסוף ההגנה/איסוף: 3 min; גשר קיבוץ גלויות -> דרך קיבוץ גלויות/כביש 1: 2 min

| Usable? (Y/N) | Notes | Compared against / when checked |
|---|---|---|
|  |  |  |

---

## J14 — Nahariya (נהריה) → Ashdod Ad Halom (אשדוד עד הלום)

category `intercity-rail` · calendar rule `weekday_morning`

**Requested:** Depart at Mon 2026-11-16 08:00 (UTC+02:00)  
Request field: `departAt=2026-11-16T08:00:00+02:00`
**Calendar flags:** ordinary day
**Compare:** [Google Maps transit](https://www.google.com/maps/dir/?api=1&origin=33.0079,35.0938&destination=31.794,34.641&travelmode=transit) · [Moovit (unofficial deep link; may not prefill)](https://moovitapp.com/?fll=33.0079_35.0938&tll=31.794_34.641&from=Nahariya&to=Ashdod%20Ad%20Halom) · Set the time yourself to **Depart at 08:00, Mon 2026-11-16** (Google's documented URL has no time parameter).
**Corpus expectation (context, not a verdict):** outcome `route`, max_duration_min = 260, max_transfers = 2, min_duration_min = 120, modes_any_of = ['rail']

> What to check: End-to-end coastal line. Tests the longest single-mode journey in the country.

**API RESULT: 3 journey option(s) returned** (scheduled times).
Machine note: matches the corpus expectation `route`. This is not a judgement of quality.
Request id `cdda1b1d80374b419ea4c452dacd4796`.

**Option 1:** departs Mon 2026-11-16 08:17, arrives Mon 2026-11-16 11:23; total 186 min, 1 transfer(s), walking 24 min / 1324 m

1. Walk 13 min, 760 m: START 08:17 -> נהריה 08:30
2. **rail ** (רכבת ישראל) toward 27: board נהריה [code 17014] 08:30 -> alight תל אביב ההגנה [code 17104] 10:23 (service date 2026-11-16, trip `1_531716`)
3. Walk 8 min, 410 m: תל אביב ההגנה 10:23 -> ת. רכבת ההגנה/החרש 10:31
4. **bus 281** (אלקטרה אפיקים) toward אשדוד_רובע ט"ו: board ת. רכבת ההגנה/החרש [code 20353] 10:40 -> alight ירושלים [code 12019] 11:20 (service date 2026-11-16, trip `42262647_111126`)
5. Walk 3 min, 154 m: ירושלים 11:20 -> END 11:23

Transfers (alight to next boarding, including any walk): תל אביב ההגנה -> ת. רכבת ההגנה/החרש: 17 min

**Option 2:** departs Mon 2026-11-16 08:33, arrives Mon 2026-11-16 11:48; total 195 min, 1 transfer(s), walking 20 min / 1229 m

1. Walk 13 min, 760 m: START 08:33 -> נהריה 08:46
2. **rail ** (רכבת ישראל) toward 109: board נהריה [code 17014] 08:46 -> alight השלום [code 17046] 10:32 (service date 2026-11-16, trip `1_531794`)
3. Walk 4 min, 315 m: השלום 10:32 -> קניון עזריאלי/כביש 20 10:36
4. **bus 280** (אלקטרה אפיקים) toward אשדוד_תחנה מרכזית: board קניון עזריאלי/כביש 20 [code 21378] 11:04 -> alight ירושלים [code 12019] 11:45 (service date 2026-11-16, trip `3275_111126`)
5. Walk 3 min, 154 m: ירושלים 11:45 -> END 11:48

Transfers (alight to next boarding, including any walk): השלום -> קניון עזריאלי/כביש 20: 32 min

**Option 3:** departs Mon 2026-11-16 08:33, arrives Mon 2026-11-16 11:38; total 185 min, 2 transfer(s), walking 24 min / 1284 m

1. Walk 13 min, 760 m: START 08:33 -> נהריה 08:46
2. **rail ** (רכבת ישראל) toward 109: board נהריה [code 17014] 08:46 -> alight תל אביב האוניברסיטה - אקספו [code 17036] 10:22 (service date 2026-11-16, trip `1_531794`)
3. Walk 2 min, 0 m: תל אביב האוניברסיטה - אקספו 10:30 -> תל אביב האוניברסיטה - אקספו 10:32
4. **rail ** (רכבת ישראל) toward 631: board תל אביב האוניברסיטה - אקספו [code 17036] 10:32 -> alight אשדוד עד הלום- מטרופול [code 17070] 11:14 (service date 2026-11-16, trip `1_532830`)
5. Walk 2 min, 111 m: אשדוד עד הלום- מטרופול 11:14 -> ת. רכבת אשדוד עד הלום/איסוף 11:16
6. **bus 1** (אלקטרה אפיקים) toward רכבת עד הלום: board ת. רכבת אשדוד עד הלום/איסוף [code 11038] 11:20 -> alight תחנה מרכזית [code 11866] 11:31 (service date 2026-11-16, trip `584836646_111126`)
7. Walk 7 min, 413 m: תחנה מרכזית 11:31 -> END 11:38

Transfers (alight to next boarding, including any walk): תל אביב האוניברסיטה - אקספו -> תל אביב האוניברסיטה - אקספו: 10 min; אשדוד עד הלום- מטרופול -> ת. רכבת אשדוד עד הלום/איסוף: 6 min

| Usable? (Y/N) | Notes | Compared against / when checked |
|---|---|---|
|  |  |  |

---

## J15 — Weizmann Institute, Rehovot (מכון ויצמן למדע) → Haifa Center HaShmona (חיפה מרכז השמונה)

**Required journey #5** — PRD §7 #5 bus → train · category `bus-to-rail` · calendar rule `weekday_morning`

**Requested:** Depart at Mon 2026-11-16 08:00 (UTC+02:00)  
Request field: `departAt=2026-11-16T08:00:00+02:00`
**Calendar flags:** ordinary day
**Compare:** [Google Maps transit](https://www.google.com/maps/dir/?api=1&origin=31.907,34.8102&destination=32.8206,34.9985&travelmode=transit) · [Moovit (unofficial deep link; may not prefill)](https://moovitapp.com/?fll=31.907_34.8102&tll=32.8206_34.9985&from=Weizmann%20Institute%2C%20Rehovot&to=Haifa%20Center%20HaShmona) · Set the time yourself to **Depart at 08:00, Mon 2026-11-16** (Google's documented URL has no time parameter).
**Corpus expectation (context, not a verdict):** outcome `route`, max_duration_min = 220, max_transfers = 3, min_duration_min = 75, modes_all_of = ['bus', 'rail']

> What to check: Must contain a bus leg then a rail leg. Verify the interchange is real.

API warnings: TRANSFER_STREET_PATH_UNAVAILABLE

**API RESULT: 3 journey option(s) returned** (scheduled times).
Machine note: matches the corpus expectation `route`. This is not a judgement of quality.
Request id `76b43ea02b2c40ad8efe146077900ae5`.

**Option 1:** departs Mon 2026-11-16 08:08, arrives Mon 2026-11-16 10:16; total 128 min, 2 transfer(s), walking 28 min / unknown distance

1. Walk 13 min, 876 m: START 08:08 -> רחובות 08:21
2. **rail ** (רכבת ישראל) toward 956: board רחובות [code 17064] 08:21 -> alight תל אביב ההגנה [code 17104] 08:43 (service date 2026-11-16, trip `1_531587`)
3. Walk 2 min, 0 m: תל אביב ההגנה 08:45 -> תל אביב ההגנה 08:47
4. **rail ** (רכבת ישראל) toward 106: board תל אביב ההגנה [code 17104] 08:47 -> alight חיפה מרכז [code 17016] 10:00 (service date 2026-11-16, trip `1_531791`)
5. Walk 4 min (timetable transfer; street path unavailable): חיפה מרכז 10:00 -> תחנת רכבת חיפה מרכז השמונה 10:04
6. **bus 1** (סופרבוס) toward קרית מוצקין_מרכזית הקריות: board תחנת רכבת חיפה מרכז השמונה [code 47574] 10:06 -> alight כרמלית [code 47576] 10:07 (service date 2026-11-16, trip `12078242_111126`)
7. Walk 9 min, 564 m: כרמלית 10:07 -> END 10:16

Transfers (alight to next boarding, including any walk): תל אביב ההגנה -> תל אביב ההגנה: 4 min; חיפה מרכז -> תחנת רכבת חיפה מרכז השמונה: 6 min

**Option 2:** departs Mon 2026-11-16 08:17, arrives Mon 2026-11-16 10:40; total 143 min, 2 transfer(s), walking 30 min / 1704 m

1. Walk 11 min, 591 m: START 08:17 -> מכון ויצמן 08:28
2. **bus 277** (אגד) toward תל אביב יפו_מסוף רדינג: board מכון ויצמן [code 34230] 08:28 -> alight ת. רכבת ההגנה/החרש [code 25636] 08:56 (service date 2026-11-16, trip `584658548_151126`)
3. Walk 6 min, 242 m: ת. רכבת ההגנה/החרש 08:57 -> תל אביב ההגנה 09:03
4. **rail ** (רכבת ישראל) toward 26: board תל אביב ההגנה [code 17104] 09:03 -> alight בת גלים [code 17018] 10:18 (service date 2026-11-16, trip `1_531715`)
5. Walk 2 min, 152 m: בת גלים 10:18 -> ת. רכבת בת גלים 10:20
6. **bus 18** (אגד) toward נווה שאנן: board ת. רכבת בת גלים [code 47181] 10:22 -> alight תחנת רכבת חיפה מרכז השמונה [code 41540] 10:29 (service date 2026-11-16, trip `25308368_151126`)
7. Walk 11 min, 719 m: תחנת רכבת חיפה מרכז השמונה 10:29 -> END 10:40

Transfers (alight to next boarding, including any walk): ת. רכבת ההגנה/החרש -> תל אביב ההגנה: 7 min; בת גלים -> ת. רכבת בת גלים: 4 min

**Option 3:** departs Mon 2026-11-16 08:17, arrives Mon 2026-11-16 10:38; total 141 min, 3 transfer(s), walking 28 min / 1423 m

1. Walk 11 min, 591 m: START 08:17 -> מכון ויצמן 08:28
2. **bus 277** (אגד) toward תל אביב יפו_מסוף רדינג: board מכון ויצמן [code 34230] 08:28 -> alight ת. רכבת ההגנה/החרש [code 25636] 08:56 (service date 2026-11-16, trip `584658548_151126`)
3. Walk 6 min, 242 m: ת. רכבת ההגנה/החרש 08:57 -> תל אביב ההגנה 09:03
4. **rail ** (רכבת ישראל) toward 26: board תל אביב ההגנה [code 17104] 09:03 -> alight בת גלים [code 17018] 10:18 (service date 2026-11-16, trip `1_531715`)
5. Walk 2 min, 152 m: בת גלים 10:20 -> ת. רכבת בת גלים 10:22
6. **bus 28** (אגד) toward גרנד קניון: board ת. רכבת בת גלים [code 47181] 10:22 -> alight המגינים/בן גוריון [code 41539] 10:27 (service date 2026-11-16, trip `25310325_151126`)
7. Walk 2 min, 0 m: המגינים/בן גוריון 10:27 -> המגינים/בן גוריון 10:29
8. **bus 24** (אגד) toward אוניברסיטה: board המגינים/בן גוריון [code 41539] 10:29 -> alight המגינים/ככר ההגנה [code 42723] 10:31 (service date 2026-11-16, trip `3814696_151126`)
9. Walk 7 min, 438 m: המגינים/ככר ההגנה 10:31 -> END 10:38

Transfers (alight to next boarding, including any walk): ת. רכבת ההגנה/החרש -> תל אביב ההגנה: 7 min; בת גלים -> ת. רכבת בת גלים: 4 min; המגינים/בן גוריון -> המגינים/בן גוריון: 2 min

| Usable? (Y/N) | Notes | Compared against / when checked |
|---|---|---|
|  |  |  |

---

## J16 — Tel Aviv Savidor Center (תל אביב סבידור מרכז) → Technion (הטכניון)

**Required journey #6** — PRD §7 #6 train → bus · category `rail-to-bus` · calendar rule `weekday_morning`

**Requested:** Depart at Mon 2026-11-16 08:00 (UTC+02:00)  
Request field: `departAt=2026-11-16T08:00:00+02:00`
**Calendar flags:** ordinary day
**Compare:** [Google Maps transit](https://www.google.com/maps/dir/?api=1&origin=32.0836,34.7981&destination=32.7767,35.0217&travelmode=transit) · [Moovit (unofficial deep link; may not prefill)](https://moovitapp.com/?fll=32.0836_34.7981&tll=32.7767_35.0217&from=Tel%20Aviv%20Savidor%20Center&to=Technion) · Set the time yourself to **Depart at 08:00, Mon 2026-11-16** (Google's documented URL has no time parameter).
**Corpus expectation (context, not a verdict):** outcome `route`, max_duration_min = 200, max_transfers = 3, min_duration_min = 70, modes_all_of = ['rail', 'bus']

> What to check: The PRD §39 demo journey in reverse shape. Rail then bus up the Carmel.

API warnings: TRANSFER_STREET_PATH_UNAVAILABLE

**API RESULT: 3 journey option(s) returned** (scheduled times).
Machine note: matches the corpus expectation `route`. This is not a judgement of quality.
Request id `c070db617c38481ea8de7c8db4a15ee3`.

**Option 1:** departs Mon 2026-11-16 08:26, arrives Mon 2026-11-16 09:52; total 86 min, 1 transfer(s), walking 8 min / 529 m

1. Walk 1 min, 27 m: START 08:26 -> תל אביב מרכז 08:27
2. **rail ** (רכבת ישראל) toward 156: board תל אביב מרכז [code 17038] 08:27 -> alight חוף הכרמל [code 17020] 09:27 (service date 2026-11-16, trip `1_531478`)
3. Walk 2 min, 189 m: חוף הכרמל 09:27 -> ת. רכבת חוף הכרמל 09:29
4. **bus 1** (אגד) toward טכניון: board ת. רכבת חוף הכרמל [code 46216] 09:33 -> alight טכניון/מעונות העמים [code 41200] 09:47 (service date 2026-11-16, trip `585633629_111126`)
5. Walk 5 min, 313 m: טכניון/מעונות העמים 09:47 -> END 09:52

Transfers (alight to next boarding, including any walk): חוף הכרמל -> ת. רכבת חוף הכרמל: 6 min

**Option 2:** departs Mon 2026-11-16 08:46, arrives Mon 2026-11-16 10:30; total 104 min, 2 transfer(s), walking 10 min / 548 m

1. Walk 1 min, 27 m: START 08:46 -> תל אביב מרכז 08:47
2. **rail ** (רכבת ישראל) toward 404: board תל אביב מרכז [code 17038] 08:47 -> alight בת גלים [code 17018] 09:47 (service date 2026-11-16, trip `1_531147`)
3. Walk 2 min, 152 m: בת גלים 09:50 -> ת. רכבת בת גלים 09:52
4. **bus 28** (אגד) toward גרנד קניון: board ת. רכבת בת גלים [code 47181] 09:52 -> alight ארלוזורוב/בלפור [code 41565] 10:05 (service date 2026-11-16, trip `25310323_151126`)
5. Walk 2 min, 56 m: ארלוזורוב/בלפור 10:05 -> ארלוזורוב/בלפור 10:07
6. **bus 76** (אגד) toward יגור_מסוף יגור: board ארלוזורוב/בלפור [code 41692] 10:10 -> alight טכניון/מעונות העמים [code 41200] 10:25 (service date 2026-11-16, trip `585688541_111126`)
7. Walk 5 min, 313 m: טכניון/מעונות העמים 10:25 -> END 10:30

Transfers (alight to next boarding, including any walk): בת גלים -> ת. רכבת בת גלים: 5 min; ארלוזורוב/בלפור -> ארלוזורוב/בלפור: 5 min

**Option 3:** departs Mon 2026-11-16 08:56, arrives Mon 2026-11-16 10:35; total 99 min, 1 transfer(s), walking 10 min / unknown distance

1. Walk 1 min, 27 m: START 08:56 -> תל אביב מרכז 08:57
2. **rail ** (רכבת ישראל) toward 106: board תל אביב מרכז [code 17038] 08:57 -> alight חיפה מרכז [code 17016] 10:00 (service date 2026-11-16, trip `1_531791`)
3. Walk 4 min (timetable transfer; street path unavailable): חיפה מרכז 10:00 -> תחנת רכבת חיפה מרכז השמונה 10:04
4. **bus 17** (אגד) toward טכניון: board תחנת רכבת חיפה מרכז השמונה [code 41540] 10:06 -> alight טכניון/מעונות העמים [code 41200] 10:30 (service date 2026-11-16, trip `1304487_151126`)
5. Walk 5 min, 313 m: טכניון/מעונות העמים 10:30 -> END 10:35

Transfers (alight to next boarding, including any walk): חיפה מרכז -> תחנת רכבת חיפה מרכז השמונה: 6 min

| Usable? (Y/N) | Notes | Compared against / when checked |
|---|---|---|
|  |  |  |

---

## J17 — Modi'in Center (מודיעין מרכז) → Ben Gurion Airport T3 (נתב"ג טרמינל 3)

category `bus-to-rail` · calendar rule `weekday_morning`

**Requested:** Depart at Mon 2026-11-16 08:00 (UTC+02:00)  
Request field: `departAt=2026-11-16T08:00:00+02:00`
**Calendar flags:** ordinary day
**Compare:** [Google Maps transit](https://www.google.com/maps/dir/?api=1&origin=31.9017,35.0074&destination=32.0004,34.8705&travelmode=transit) · [Moovit (unofficial deep link; may not prefill)](https://moovitapp.com/?fll=31.9017_35.0074&tll=32.0004_34.8705&from=Modi%27in%20Center&to=Ben%20Gurion%20Airport%20T3) · Set the time yourself to **Depart at 08:00, Mon 2026-11-16** (Google's documented URL has no time parameter).
**Corpus expectation (context, not a verdict):** outcome `route`, max_duration_min = 90, max_transfers = 2, min_duration_min = 15, modes_any_of = ['rail', 'bus']

> What to check: Airport access. A wrong answer here is very visible to a real user.

API warnings: TRANSFER_STREET_PATH_UNAVAILABLE

**API RESULT: 3 journey option(s) returned** (scheduled times).
Machine note: matches the corpus expectation `route`. This is not a judgement of quality.
Request id `5a45aaa728d04553a66bf2885c6047fd`.

**Option 1:** departs Mon 2026-11-16 08:06, arrives Mon 2026-11-16 08:37; total 31 min, 1 transfer(s), walking 10 min / unknown distance

1. Walk 7 min, 402 m: START 08:06 -> עמק איילון/תלתן 08:13
2. **bus 58** (קווים) toward בייק פארק: board עמק איילון/תלתן [code 34155] 08:13 -> alight ת. רכבת מודיעין מרכז [code 33093] 08:14 (service date 2026-11-16, trip `28361843_111126`)
3. Walk 2 min (timetable transfer; street path unavailable): ת. רכבת מודיעין מרכז 08:14 -> מודיעין מרכז 08:16
4. **rail ** (רכבת ישראל) toward 106: board מודיעין מרכז [code 17002] 08:19 -> alight נתב''ג [code 17090] 08:36 (service date 2026-11-16, trip `1_531791`)
5. Walk 1 min, 4 m: נתב''ג 08:36 -> END 08:37

Transfers (alight to next boarding, including any walk): ת. רכבת מודיעין מרכז -> מודיעין מרכז: 5 min

**Option 2:** departs Mon 2026-11-16 08:37, arrives Mon 2026-11-16 09:07; total 30 min, 1 transfer(s), walking 7 min / unknown distance

1. Walk 4 min, 189 m: START 08:37 -> קניון עזריאלי מודיעין 08:41
2. **bus 54** (קווים) toward מ.מסחרי לב רעות: board קניון עזריאלי מודיעין [code 35177] 08:41 -> alight ת. רכבת מודיעין מרכז [code 33093] 08:41 (service date 2026-11-16, trip `36207168_111126`)
3. Walk 2 min (timetable transfer; street path unavailable): ת. רכבת מודיעין מרכז 08:41 -> מודיעין מרכז 08:43
4. **rail ** (רכבת ישראל) toward 158: board מודיעין מרכז [code 17002] 08:49 -> alight נתב''ג [code 17090] 09:06 (service date 2026-11-16, trip `1_531408`)
5. Walk 1 min, 4 m: נתב''ג 09:06 -> END 09:07

Transfers (alight to next boarding, including any walk): ת. רכבת מודיעין מרכז -> מודיעין מרכז: 8 min

**Option 3:** departs Mon 2026-11-16 09:07, arrives Mon 2026-11-16 09:37; total 30 min, 1 transfer(s), walking 7 min / unknown distance

1. Walk 4 min, 189 m: START 09:07 -> קניון עזריאלי מודיעין 09:11
2. **bus 54** (קווים) toward רעות: board קניון עזריאלי מודיעין [code 35177] 09:11 -> alight ת. רכבת מודיעין מרכז [code 33093] 09:11 (service date 2026-11-16, trip `36206990_111126`)
3. Walk 2 min (timetable transfer; street path unavailable): ת. רכבת מודיעין מרכז 09:11 -> מודיעין מרכז 09:13
4. **rail ** (רכבת ישראל) toward 108: board מודיעין מרכז [code 17002] 09:19 -> alight נתב''ג [code 17090] 09:36 (service date 2026-11-16, trip `1_531793`)
5. Walk 1 min, 4 m: נתב''ג 09:36 -> END 09:37

Transfers (alight to next boarding, including any walk): ת. רכבת מודיעין מרכז -> מודיעין מרכז: 8 min

| Usable? (Y/N) | Notes | Compared against / when checked |
|---|---|---|
|  |  |  |

---

## J18 — Beersheba North University (באר שבע צפון אוניברסיטה) → Bar-Ilan University (אוניברסיטת בר אילן)

category `rail-to-bus` · calendar rule `weekday_morning`

**Requested:** Depart at Mon 2026-11-16 08:00 (UTC+02:00)  
Request field: `departAt=2026-11-16T08:00:00+02:00`
**Calendar flags:** ordinary day
**Compare:** [Google Maps transit](https://www.google.com/maps/dir/?api=1&origin=31.262,34.8016&destination=32.07,34.8433&travelmode=transit) · [Moovit (unofficial deep link; may not prefill)](https://moovitapp.com/?fll=31.262_34.8016&tll=32.07_34.8433&from=Beersheba%20North%20University&to=Bar-Ilan%20University) · Set the time yourself to **Depart at 08:00, Mon 2026-11-16** (Google's documented URL has no time parameter).
**Corpus expectation (context, not a verdict):** outcome `route`, max_duration_min = 230, max_transfers = 3, min_duration_min = 75, modes_all_of = ['rail', 'bus']

> What to check: Campus to campus, two operators, at least one interchange.

**API RESULT: 3 journey option(s) returned** (scheduled times).
Machine note: matches the corpus expectation `route`. This is not a judgement of quality.
Request id `570f5ee71abf4155b2becda60544b7b6`.

**Option 1:** departs Mon 2026-11-16 08:00, arrives Mon 2026-11-16 10:04; total 124 min, 3 transfer(s), walking 18 min / 1233 m

1. Walk 4 min, 215 m: START 08:00 -> מרפאות חוץ סורוקה/אוניברסיטת בן גוריון 08:04
2. **bus 5** (דן באר שבע) toward מסוף חצרים: board מרפאות חוץ סורוקה/אוניברסיטת בן גוריון [code 13949] 08:04 -> alight מרכז רפואי סורוקה/אוניברסיטת בן גוריון [code 15332] 08:05 (service date 2026-11-16, trip `585112451_111126`)
3. Walk 2 min, 290 m: מרכז רפואי סורוקה/אוניברסיטת בן גוריון 08:05 -> מרכז רפואי סורוקה/אוניברסיטת בן גוריון 08:07
4. **bus 370** (מטרופולין) toward תל אביב יפו_תחנה מרכזית: board מרכז רפואי סורוקה/אוניברסיטת בן גוריון [code 15333] 08:07 -> alight מחלף לה גווארדייה [code 21274] 09:16 (service date 2026-11-16, trip `2221042_131126`)
5. Walk 2 min, 126 m: מחלף לה גווארדייה 09:19 -> מחלף לה גווארדייה 09:21
6. **bus 31** (דן) toward בני ברק_בית עלמין: board מחלף לה גווארדייה [code 22934] 09:21 -> alight הירדן/ אלוף שדה [code 21319] 09:39 (service date 2026-11-16, trip `4071661_161126`)
7. Walk 2 min, 150 m: הירדן/ אלוף שדה 09:39 -> הירדן/אלוף שדה 09:41
8. **bus 32** (דן) toward גבעת שמואל_הרב שלמה גורן: board הירדן/אלוף שדה [code 21569] 09:47 -> alight מרכז וואהל/מקס ואנה ווב [code 32907] 09:56 (service date 2026-11-16, trip `36034216_161126`)
9. Walk 8 min, 452 m: מרכז וואהל/מקס ואנה ווב 09:56 -> END 10:04

Transfers (alight to next boarding, including any walk): מרכז רפואי סורוקה/אוניברסיטת בן גוריון -> מרכז רפואי סורוקה/אוניברסיטת בן גוריון: 2 min; מחלף לה גווארדייה -> מחלף לה גווארדייה: 5 min; הירדן/ אלוף שדה -> הירדן/אלוף שדה: 8 min

**Option 2:** departs Mon 2026-11-16 08:00, arrives Mon 2026-11-16 09:56; total 116 min, 4 transfer(s), walking 20 min / 1083 m

1. Walk 4 min, 215 m: START 08:00 -> מרפאות חוץ סורוקה/אוניברסיטת בן גוריון 08:04
2. **bus 5** (דן באר שבע) toward מסוף חצרים: board מרפאות חוץ סורוקה/אוניברסיטת בן גוריון [code 13949] 08:04 -> alight מרכז רפואי סורוקה/אוניברסיטת בן גוריון [code 15332] 08:05 (service date 2026-11-16, trip `585112451_111126`)
3. Walk 2 min, 290 m: מרכז רפואי סורוקה/אוניברסיטת בן גוריון 08:05 -> מרכז רפואי סורוקה/אוניברסיטת בן גוריון 08:07
4. **bus 370** (מטרופולין) toward תל אביב יפו_תחנה מרכזית: board מרכז רפואי סורוקה/אוניברסיטת בן גוריון [code 15333] 08:07 -> alight מחלף לה גווארדייה [code 21274] 09:16 (service date 2026-11-16, trip `2221042_131126`)
5. Walk 2 min, 126 m: מחלף לה גווארדייה 09:17 -> מחלף לה גווארדייה 09:19
6. **bus 2** (דן) toward הארגזים: board מחלף לה גווארדייה [code 22934] 09:19 -> alight שכונת הארגזים/לח''י [code 25669] 09:25 (service date 2026-11-16, trip `44236243_161126`)
7. Walk 2 min, 0 m: שכונת הארגזים/לח''י 09:27 -> שכונת הארגזים/לח''י 09:29
8. **bus 41** (דן) toward פתח תקווה_מסוף משה ארנס: board שכונת הארגזים/לח''י [code 25669] 09:29 -> alight עמק האלה/דרך שיבא [code 31010] 09:39 (service date 2026-11-16, trip `38113270_161126`)
9. Walk 2 min, 0 m: עמק האלה/דרך שיבא 09:39 -> עמק האלה/דרך שיבא 09:41
10. **bus 48** (מטרופולין) toward פתח תקווה_מ.רפואי שניידר: board עמק האלה/דרך שיבא [code 31010] 09:41 -> alight מרכז וואהל/מקס ואנה ווב [code 32907] 09:48 (service date 2026-11-16, trip `586222499_151126`)
11. Walk 8 min, 452 m: מרכז וואהל/מקס ואנה ווב 09:48 -> END 09:56

Transfers (alight to next boarding, including any walk): מרכז רפואי סורוקה/אוניברסיטת בן גוריון -> מרכז רפואי סורוקה/אוניברסיטת בן גוריון: 2 min; מחלף לה גווארדייה -> מחלף לה גווארדייה: 3 min; שכונת הארגזים/לח''י -> שכונת הארגזים/לח''י: 4 min; עמק האלה/דרך שיבא -> עמק האלה/דרך שיבא: 2 min

**Option 3:** departs Mon 2026-11-16 08:17, arrives Mon 2026-11-16 10:11; total 114 min, 1 transfer(s), walking 20 min / 1060 m

1. Walk 10 min, 608 m: START 08:17 -> מרכז רפואי סורוקה/אוניברסיטת בן גוריון 08:27
2. **bus 669** (מטרופולין) toward רעננה_מסוף אוטובוסים: board מרכז רפואי סורוקה/אוניברסיטת בן גוריון [code 15333] 08:27 -> alight מחלף מסובים [code 33432] 09:47 (service date 2026-11-16, trip `41490656_131126`)
3. Walk 2 min, 0 m: מחלף מסובים 09:47 -> מחלף מסובים 09:49
4. **bus 145** (סופרבוס) toward פתח תקווה_רכבת קרית אריה: board מחלף מסובים [code 33432] 09:57 -> alight מרכז וואהל/מקס ואנה ווב [code 32907] 10:03 (service date 2026-11-16, trip `585990270_111126`)
5. Walk 8 min, 452 m: מרכז וואהל/מקס ואנה ווב 10:03 -> END 10:11

Transfers (alight to next boarding, including any walk): מחלף מסובים -> מחלף מסובים: 10 min

| Usable? (Y/N) | Notes | Compared against / when checked |
|---|---|---|
|  |  |  |

---

## J19 — Herzliya Station (תחנת רכבת הרצליה) → Beilinson Hospital, Petah Tikva (בית חולים בילינסון)

**Required journey #7** — PRD §7 #7 at least one transfer · category `with-transfer` · calendar rule `weekday_morning`

**Requested:** Depart at Mon 2026-11-16 08:00 (UTC+02:00)  
Request field: `departAt=2026-11-16T08:00:00+02:00`
**Calendar flags:** ordinary day
**Compare:** [Google Maps transit](https://www.google.com/maps/dir/?api=1&origin=32.1656,34.8095&destination=32.087,34.858&travelmode=transit) · [Moovit (unofficial deep link; may not prefill)](https://moovitapp.com/?fll=32.1656_34.8095&tll=32.087_34.858&from=Herzliya%20Station&to=Beilinson%20Hospital%2C%20Petah%20Tikva) · Set the time yourself to **Depart at 08:00, Mon 2026-11-16** (Google's documented URL has no time parameter).
**Corpus expectation (context, not a verdict):** outcome `route`, max_duration_min = 100, max_transfers = 3, min_duration_min = 20, min_transfers = 1

> What to check: Must transfer. Is the transfer window realistic, not a 2-minute cross-platform miracle?

**API RESULT: 3 journey option(s) returned** (scheduled times).
Machine note: matches the corpus expectation `route`. This is not a judgement of quality.
Request id `6748711f659b435083cc1073999e5098`.

**Option 1:** departs Mon 2026-11-16 08:03, arrives Mon 2026-11-16 09:14; total 71 min, 1 transfer(s), walking 13 min / 622 m

1. Walk 4 min, 184 m: START 08:03 -> גלגלי הפלדה/יוחנן הסנדלר 08:07
2. **bus 91** (מטרופולין) toward תל אביב יפו_מסוף הטייסים: board גלגלי הפלדה/יוחנן הסנדלר [code 26761] 08:07 -> alight דרך בר לב/דרך משה דיין [code 21538] 08:36 (service date 2026-11-16, trip `25080591_151126`)
3. Walk 2 min, 0 m: דרך בר לב/דרך משה דיין 08:36 -> דרך בר לב/דרך משה דיין 08:38
4. **bus 41** (דן) toward פתח תקווה_מסוף משה ארנס: board דרך בר לב/דרך משה דיין [code 21538] 08:39 -> alight בריכת נווה עוז/דרך יצחק רבין [code 38468] 09:07 (service date 2026-11-16, trip `8039658_161126`)
5. Walk 7 min, 438 m: בריכת נווה עוז/דרך יצחק רבין 09:07 -> END 09:14

Transfers (alight to next boarding, including any walk): דרך בר לב/דרך משה דיין -> דרך בר לב/דרך משה דיין: 3 min

**Option 2:** departs Mon 2026-11-16 08:03, arrives Mon 2026-11-16 08:57; total 54 min, 2 transfer(s), walking 15 min / 878 m

1. Walk 4 min, 184 m: START 08:03 -> גלגלי הפלדה/יוחנן הסנדלר 08:07
2. **bus 91** (מטרופולין) toward תל אביב יפו_מסוף הטייסים: board גלגלי הפלדה/יוחנן הסנדלר [code 26761] 08:07 -> alight ת.רק''ל שאול המלך/דרך מנחם בגין [code 20837] 08:24 (service date 2026-11-16, trip `25080591_151126`)
3. Walk 2 min, 126 m: ת.רק''ל שאול המלך/דרך מנחם בגין 08:27 -> שאול המלך 08:29
4. **light_rail 1** (תבל) toward פתח תקווה_ת. מרכזית פתח תקווה: board שאול המלך [code 20709] 08:29 -> alight שחם [code 36313] 08:45 (service date 2026-11-16, trip `585428502_111126`)
5. Walk 2 min, 124 m: שחם 08:45 -> ת.רק''ל שחם/דרך יצחק רבין 08:47
6. **bus 75** (מטרופולין) toward גני תקווה_מרכז גני תקווה: board ת.רק''ל שחם/דרך יצחק רבין [code 36570] 08:48 -> alight דרך יצחק רבין/דגניה [code 35485] 08:50 (service date 2026-11-16, trip `586235023_151126`)
7. Walk 7 min, 444 m: דרך יצחק רבין/דגניה 08:50 -> END 08:57

Transfers (alight to next boarding, including any walk): ת.רק''ל שאול המלך/דרך מנחם בגין -> שאול המלך: 5 min; שחם -> ת.רק''ל שחם/דרך יצחק רבין: 3 min

**Option 3:** departs Mon 2026-11-16 08:06, arrives Mon 2026-11-16 09:01; total 55 min, 3 transfer(s), walking 17 min / 878 m

1. Walk 4 min, 184 m: START 08:06 -> גלגלי הפלדה/יוחנן הסנדלר 08:10
2. **bus 90** (מטרופולין) toward תל אביב יפו_מסוף כרמלית: board גלגלי הפלדה/יוחנן הסנדלר [code 26761] 08:10 -> alight סינמה סיטי/כביש 2 [code 26966] 08:14 (service date 2026-11-16, trip `19637410_151126`)
3. Walk 2 min, 0 m: סינמה סיטי/כביש 2 08:16 -> סינמה סיטי/כביש 2 08:18
4. **bus 347** (מטרופולין) toward תל אביב יפו_תחנה מרכזית: board סינמה סיטי/כביש 2 [code 26966] 08:18 -> alight ת.רק''ל שאול המלך/דרך מנחם בגין [code 20837] 08:31 (service date 2026-11-16, trip `42548405_111126`)
5. Walk 2 min, 126 m: ת.רק''ל שאול המלך/דרך מנחם בגין 08:32 -> שאול המלך 08:34
6. **light_rail 1** (תבל) toward פתח תקווה_ת. מרכזית פתח תקווה: board שאול המלך [code 20709] 08:34 -> alight שחם [code 36313] 08:50 (service date 2026-11-16, trip `585373596_111126`)
7. Walk 2 min, 124 m: שחם 08:50 -> ת.רק''ל שחם/דרך יצחק רבין 08:52
8. **bus 143** (סופרבוס) toward חולון_מוזיאון אגד: board ת.רק''ל שחם/דרך יצחק רבין [code 36570] 08:53 -> alight דרך יצחק רבין/דגניה [code 35485] 08:54 (service date 2026-11-16, trip `586111406_111126`)
9. Walk 7 min, 444 m: דרך יצחק רבין/דגניה 08:54 -> END 09:01

Transfers (alight to next boarding, including any walk): סינמה סיטי/כביש 2 -> סינמה סיטי/כביש 2: 4 min; ת.רק''ל שאול המלך/דרך מנחם בגין -> שאול המלך: 3 min; שחם -> ת.רק''ל שחם/דרך יצחק רבין: 3 min

| Usable? (Y/N) | Notes | Compared against / when checked |
|---|---|---|
|  |  |  |

---

## J20 — Netanya Station (תחנת רכבת נתניה) → Mahane Yehuda Market (שוק מחנה יהודה)

category `with-transfer` · calendar rule `weekday_midday`

**Requested:** Depart at Tue 2026-11-17 13:00 (UTC+02:00)  
Request field: `departAt=2026-11-17T13:00:00+02:00`
**Calendar flags:** ordinary day
**Compare:** [Google Maps transit](https://www.google.com/maps/dir/?api=1&origin=32.3097,34.8619&destination=31.7853,35.2124&travelmode=transit) · [Moovit (unofficial deep link; may not prefill)](https://moovitapp.com/?fll=32.3097_34.8619&tll=31.7853_35.2124&from=Netanya%20Station&to=Mahane%20Yehuda%20Market) · Set the time yourself to **Depart at 13:00, Tue 2026-11-17** (Google's documented URL has no time parameter).
**Corpus expectation (context, not a verdict):** outcome `route`, max_duration_min = 200, max_transfers = 3, min_duration_min = 60, min_transfers = 1

> What to check: Coastal rail then Jerusalem light rail. Checks cross-operator chaining.

**API RESULT: 3 journey option(s) returned** (scheduled times).
Machine note: matches the corpus expectation `route`. This is not a judgement of quality.
Request id `71c257088f5b468faace93d0cbb7b2dc`.

**Option 1:** departs Tue 2026-11-17 13:03, arrives Tue 2026-11-17 15:08; total 125 min, 3 transfer(s), walking 29 min / 2275 m

1. Walk 15 min, 889 m: START 13:03 -> בית ספר טשרניחובסקי/בן צבי 13:18
2. **bus 611** (מטרופולין) toward תל אביב יפו_תחנה מרכזית: board בית ספר טשרניחובסקי/בן צבי [code 39204] 13:18 -> alight מכללת לוינסקי/דרך נמיר [code 20105] 13:40 (service date 2026-11-17, trip `42518425_111126`)
3. Walk 2 min, 301 m: מכללת לוינסקי/דרך נמיר 13:43 -> מכללת לוינסקי/דרך נמיר 13:45
4. **bus 123** (מטרופולין) toward קלנסווה_מרכז: board מכללת לוינסקי/דרך נמיר [code 20096] 13:45 -> alight מחלף ירקון [code 39686] 13:57 (service date 2026-11-17, trip `584868307_151126`)
5. Walk 4 min, 381 m: מחלף ירקון 13:57 -> מחלף ירקון 14:01
6. **bus 950** (אגד) toward ירושלים_תחנה מרכזית: board מחלף ירקון [code 39684] 14:01 -> alight ת. מרכזית ירושלים/הורדה [code 6109] 14:56 (service date 2026-11-17, trip `3998465_171126`)
7. Walk 4 min, 474 m: ת. מרכזית ירושלים/הורדה 14:56 -> שדרות שז''ר/בנייני האומה 15:00
8. **bus 78** (סופרבוס) toward תלפיות מזרח: board שדרות שז''ר/בנייני האומה [code 463] 15:01 -> alight שוק מחנה יהודה/אגריפס [code 3523] 15:04 (service date 2026-11-17, trip `584769649_151126`)
9. Walk 4 min, 230 m: שוק מחנה יהודה/אגריפס 15:04 -> END 15:08

Transfers (alight to next boarding, including any walk): מכללת לוינסקי/דרך נמיר -> מכללת לוינסקי/דרך נמיר: 5 min; מחלף ירקון -> מחלף ירקון: 4 min; ת. מרכזית ירושלים/הורדה -> שדרות שז''ר/בנייני האומה: 5 min

**Option 2:** departs Tue 2026-11-17 13:04, arrives Tue 2026-11-17 15:08; total 124 min, 4 transfer(s), walking 23 min / 1894 m

1. Walk 7 min, 371 m: START 13:04 -> האר''י/הרב חרל''פ 13:11
2. **bus 72** (אקסטרה) toward תחנת הרכבת: board האר''י/הרב חרל''פ [code 39238] 13:11 -> alight שד. בן צבי/היהלומן אברהם [code 39216] 13:14 (service date 2026-11-17, trip `585092382_111126`)
3. Walk 2 min, 137 m: שד. בן צבי/היהלומן אברהם 13:14 -> בן צבי/הגר''א 13:16
4. **bus 611** (מטרופולין) toward תל אביב יפו_תחנה מרכזית: board בן צבי/הגר''א [code 39215] 13:16 -> alight מכללת לוינסקי/דרך נמיר [code 20105] 13:40 (service date 2026-11-17, trip `42518425_111126`)
5. Walk 2 min, 301 m: מכללת לוינסקי/דרך נמיר 13:43 -> מכללת לוינסקי/דרך נמיר 13:45
6. **bus 123** (מטרופולין) toward קלנסווה_מרכז: board מכללת לוינסקי/דרך נמיר [code 20096] 13:45 -> alight מחלף ירקון [code 39686] 13:57 (service date 2026-11-17, trip `584868307_151126`)
7. Walk 4 min, 381 m: מחלף ירקון 13:57 -> מחלף ירקון 14:01
8. **bus 950** (אגד) toward ירושלים_תחנה מרכזית: board מחלף ירקון [code 39684] 14:01 -> alight ת. מרכזית ירושלים/הורדה [code 6109] 14:56 (service date 2026-11-17, trip `3998465_171126`)
9. Walk 4 min, 474 m: ת. מרכזית ירושלים/הורדה 14:56 -> שדרות שז''ר/בנייני האומה 15:00
10. **bus 78** (סופרבוס) toward תלפיות מזרח: board שדרות שז''ר/בנייני האומה [code 463] 15:01 -> alight שוק מחנה יהודה/אגריפס [code 3523] 15:04 (service date 2026-11-17, trip `584769649_151126`)
11. Walk 4 min, 230 m: שוק מחנה יהודה/אגריפס 15:04 -> END 15:08

Transfers (alight to next boarding, including any walk): שד. בן צבי/היהלומן אברהם -> בן צבי/הגר''א: 2 min; מכללת לוינסקי/דרך נמיר -> מכללת לוינסקי/דרך נמיר: 5 min; מחלף ירקון -> מחלף ירקון: 4 min; ת. מרכזית ירושלים/הורדה -> שדרות שז''ר/בנייני האומה: 5 min

**Option 3:** departs Tue 2026-11-17 13:07, arrives Tue 2026-11-17 15:10; total 123 min, 2 transfer(s), walking 15 min / 1932 m

1. Walk 8 min, 466 m: START 13:07 -> הקליר/האר''י  13:15
2. **bus 71א** (אקסטרה) toward תחנת הרכבת: board הקליר/האר''י  [code 36829] 13:15 -> alight ת. רכבת נתניה [code 39426] 13:32 (service date 2026-11-17, trip `585105791_111126`)
3. Walk 2 min, 103 m: ת. רכבת נתניה 13:50 -> נתניה 13:52
4. **rail ** (רכבת ישראל) toward 747: board נתניה [code 17030] 13:52 -> alight ירושלים/יצחק נבון [code 17118] 15:02 (service date 2026-11-17, trip `1_531510`)
5. Walk 2 min, 1228 m: ירושלים/יצחק נבון 15:02 -> בנייני האומה 15:04
6. **light_rail 3** (כפיר) toward שער שכם: board בנייני האומה [code 2738] 15:04 -> alight מחנה יהודה [code 6173] 15:07 (service date 2026-11-17, trip `586277809_111126`)
7. Walk 3 min, 135 m: מחנה יהודה 15:07 -> END 15:10

Transfers (alight to next boarding, including any walk): ת. רכבת נתניה -> נתניה: 20 min; ירושלים/יצחק נבון -> בנייני האומה: 2 min

| Usable? (Y/N) | Notes | Compared against / when checked |
|---|---|---|
|  |  |  |

---

## J21 — Tel Aviv Savidor Center (תל אביב סבידור מרכז) → Ben Gurion Airport T3 (נתב"ג טרמינל 3)

**Required journey #8** — PRD §7 #8 late night · category `late-night` · calendar rule `late_night`

**Requested:** Depart at Tue 2026-11-17 23:40 (UTC+02:00)  
Request field: `departAt=2026-11-17T23:40:00+02:00`
**Calendar flags:** ordinary day
**Compare:** [Google Maps transit](https://www.google.com/maps/dir/?api=1&origin=32.0836,34.7981&destination=32.0004,34.8705&travelmode=transit) · [Moovit (unofficial deep link; may not prefill)](https://moovitapp.com/?fll=32.0836_34.7981&tll=32.0004_34.8705&from=Tel%20Aviv%20Savidor%20Center&to=Ben%20Gurion%20Airport%20T3) · Set the time yourself to **Depart at 23:40, Tue 2026-11-17** (Google's documented URL has no time parameter).
**Corpus expectation (context, not a verdict):** outcome `route`, max_duration_min = 120, max_transfers = 2, min_duration_min = 10, modes_any_of = ['rail', 'bus']

> What to check: Airport rail runs deep into the night. Does the engine know that?

**API RESULT: 3 journey option(s) returned** (scheduled times).
Machine note: matches the corpus expectation `route`. This is not a judgement of quality.
Request id `194ed9f279a745e5a92d471574289665`.

**Option 1:** departs Tue 2026-11-17 23:45, arrives Wed 2026-11-18 00:05; total 20 min, 0 transfer(s), walking 2 min / 31 m

1. Walk 1 min, 27 m: START 23:45 -> תל אביב מרכז 23:46
2. **rail ** (רכבת ישראל) toward 785: board תל אביב מרכז [code 17038] 23:46 -> alight נתב''ג [code 17090] 00:04 (service date 2026-11-17, trip `1_531546`)
3. Walk 1 min, 4 m: נתב''ג 00:04 -> END 00:05

Transfers (alight to next boarding, including any walk): none

**Option 2:** departs Wed 2026-11-18 00:36, arrives Wed 2026-11-18 00:56; total 20 min, 0 transfer(s), walking 2 min / 31 m

1. Walk 1 min, 27 m: START 00:36 -> תל אביב מרכז 00:37
2. **rail ** (רכבת ישראל) toward 137: board תל אביב מרכז [code 17038] 00:37 -> alight נתב''ג [code 17090] 00:55 (service date 2026-11-17, trip `1_531421`)
3. Walk 1 min, 4 m: נתב''ג 00:55 -> END 00:56

Transfers (alight to next boarding, including any walk): none

**Option 3:** departs Wed 2026-11-18 00:46, arrives Wed 2026-11-18 01:02; total 16 min, 0 transfer(s), walking 2 min / 31 m

1. Walk 1 min, 27 m: START 00:46 -> תל אביב מרכז 00:47
2. **rail ** (רכבת ישראל) toward 9701: board תל אביב מרכז [code 17038] 00:47 -> alight נתב''ג [code 17090] 01:01 (service date 2026-11-18, trip `1_526105`)
3. Walk 1 min, 4 m: נתב''ג 01:01 -> END 01:02

Transfers (alight to next boarding, including any walk): none

| Usable? (Y/N) | Notes | Compared against / when checked |
|---|---|---|
|  |  |  |

---

## J22 — Dizengoff Center (דיזנגוף סנטר) → Ramat Gan Bursa (רמת גן בורסה)

**Required journey #9** — PRD §7 #9 crossing a service-day boundary · category `service-day-boundary` · calendar rule `after_midnight`

**Requested:** Depart at Wed 2026-11-11 02:30 (UTC+02:00)  
Request field: `departAt=2026-11-11T02:30:00+02:00`
**Calendar flags:** ordinary day
**Compare:** [Google Maps transit](https://www.google.com/maps/dir/?api=1&origin=32.0757,34.7748&destination=32.0838,34.8044&travelmode=transit) · [Moovit (unofficial deep link; may not prefill)](https://moovitapp.com/?fll=32.0757_34.7748&tll=32.0838_34.8044&from=Dizengoff%20Center&to=Ramat%20Gan%20Bursa) · Set the time yourself to **Depart at 02:30, Wed 2026-11-11** (Google's documented URL has no time parameter).
**Corpus expectation (context, not a verdict):** outcome `either`, max_duration_min = 180, min_duration_min = 5

> What to check: THE GTFS trap: trips after midnight belong to the previous service day with times like 25:30:00. Either a valid night route or a clean no-route is acceptable. A crash, an empty result with no explanation, or a route departing 20 hours later is a FAIL.

**API RESULT: 3 journey option(s) returned** (scheduled times).
Request id `e760b655296f4ac9912bd93f7c218bd0`.

**Option 1:** departs Wed 2026-11-11 02:39, arrives Wed 2026-11-11 04:18; total 99 min, 1 transfer(s), walking 16 min / 1517 m

1. Walk 3 min, 135 m: START 02:39 -> דיזנגוף סנטר/דיזנגוף 02:42
2. **bus 445** (מטרופולין) toward נמל תעופה בן גוריון_טרמינל 3: board דיזנגוף סנטר/דיזנגוף [code 25565] 02:42 -> alight נתב''ג טרמינל 3/קומת תח''צ [code 35275] 03:22 (service date 2026-11-11, trip `53738960_111126`)
3. Walk 2 min, 616 m: נתב''ג טרמינל 3/קומת תח''צ 03:22 -> נתב''ג 03:24
4. **rail ** (רכבת ישראל) toward 9706: board נתב''ג [code 17090] 03:53 -> alight תל אביב מרכז [code 17038] 04:07 (service date 2026-11-11, trip `1_523448`)
5. Walk 11 min, 766 m: תל אביב מרכז 04:07 -> END 04:18

Transfers (alight to next boarding, including any walk): נתב''ג טרמינל 3/קומת תח''צ -> נתב''ג: 31 min

**Option 2:** departs Wed 2026-11-11 04:57, arrives Wed 2026-11-11 05:38; total 41 min, 1 transfer(s), walking 9 min / 508 m

1. Walk 3 min, 135 m: START 04:57 -> דיזנגוף סנטר/דיזנגוף 05:00
2. **bus 172** (דן) toward חולון_מסוף אזור תעשייה: board דיזנגוף סנטר/דיזנגוף [code 25565] 05:00 -> alight שוקן/דרך שלמה [code 20388] 05:10 (service date 2026-11-11, trip `584954863_111126`)
3. Walk 2 min, 118 m: שוקן/דרך שלמה 05:10 -> דרך שלמה/שוקן 05:12
4. **bus 42** (דן) toward תל אביב יפו_קריית עתידים: board דרך שלמה/שוקן [code 20097] 05:18 -> alight ת.רק''ל אבא הלל [code 26248] 05:34 (service date 2026-11-11, trip `46019532_111126`)
5. Walk 4 min, 255 m: ת.רק''ל אבא הלל 05:34 -> END 05:38

Transfers (alight to next boarding, including any walk): שוקן/דרך שלמה -> דרך שלמה/שוקן: 8 min

**Option 3:** departs Wed 2026-11-11 04:57, arrives Wed 2026-11-11 05:23; total 26 min, 2 transfer(s), walking 11 min / 486 m

1. Walk 3 min, 135 m: START 04:57 -> דיזנגוף סנטר/דיזנגוף 05:00
2. **bus 172** (דן) toward חולון_מסוף אזור תעשייה: board דיזנגוף סנטר/דיזנגוף [code 25565] 05:00 -> alight שד' רוטשילד/שיינקין [code 25587] 05:03 (service date 2026-11-11, trip `584954863_111126`)
3. Walk 2 min, 112 m: שד' רוטשילד/שיינקין 05:05 -> שד' רוטשילד/שיינקין 05:07
4. **bus 23** (דן) toward גבעתיים_כורזין: board שד' רוטשילד/שיינקין [code 21732] 05:07 -> alight ת.רק''ל יהודית/דרך מנחם בגין [code 20727] 05:11 (service date 2026-11-11, trip `585553261_111126`)
5. Walk 2 min, 0 m: ת.רק''ל יהודית/דרך מנחם בגין 05:11 -> ת.רק''ל יהודית/דרך מנחם בגין 05:13
6. **bus 50** (דן) toward פתח תקווה_רכבת סגולה: board ת.רק''ל יהודית/דרך מנחם בגין [code 20727] 05:13 -> alight ת.רק''ל אבא הלל/דרך ז'בוטינסקי [code 21644] 05:19 (service date 2026-11-11, trip `585465555_111126`)
7. Walk 4 min, 239 m: ת.רק''ל אבא הלל/דרך ז'בוטינסקי 05:19 -> END 05:23

Transfers (alight to next boarding, including any walk): שד' רוטשילד/שיינקין -> שד' רוטשילד/שיינקין: 4 min; ת.רק''ל יהודית/דרך מנחם בגין -> ת.רק''ל יהודית/דרך מנחם בגין: 2 min

| Usable? (Y/N) | Notes | Compared against / when checked |
|---|---|---|
|  |  |  |

---

## J23 — Har Karkom, central Negev (הר כרכום) → Metula (מטולה)

**Required journey #10** — PRD §7 #10 no reasonable transit route · category `no-reasonable-route` · calendar rule `after_midnight`

**Requested:** Depart at Wed 2026-11-11 02:30 (UTC+02:00)  
Request field: `departAt=2026-11-11T02:30:00+02:00`
**Calendar flags:** ordinary day
**Compare:** [Google Maps transit](https://www.google.com/maps/dir/?api=1&origin=30.28,34.74&destination=33.2778,35.5786&travelmode=transit) · [Moovit (unofficial deep link; may not prefill)](https://moovitapp.com/?fll=30.28_34.74&tll=33.2778_35.5786&from=Har%20Karkom%2C%20central%20Negev&to=Metula) · Set the time yourself to **Depart at 02:30, Wed 2026-11-11** (Google's documented URL has no time parameter).
**Corpus expectation (context, not a verdict):** outcome `no-route`

> What to check: Origin is 23.5 km from the nearest stop in the feed — measured, not assumed. No walking budget reaches transit, so 'no route' is the only correct answer. An itinerary here means the engine is inventing access.

**API RESULT: NO ROUTE** — a valid search inside coverage returned no journey. The API does not state a cause (no service, walking limit and data gaps look alike).
Machine note: matches the corpus expectation `no-route`. This is not a judgement of quality.
Request id `147371f9defd4ef7a3a0bd593e6c0074`.

| Usable? (Y/N) | Notes | Compared against / when checked |
|---|---|---|
|  |  |  |

---

## J24 — Masada Junction (צומת מצדה) → Beersheba Central (באר שבע מרכז)

category `long-walk-accessibility` · calendar rule `weekday_midday`

**Requested:** Depart at Tue 2026-11-17 13:00 (UTC+02:00)  
Request field: `departAt=2026-11-17T13:00:00+02:00`
**Calendar flags:** ordinary day
**Compare:** [Google Maps transit](https://www.google.com/maps/dir/?api=1&origin=31.3156,35.3539&destination=31.243,34.7983&travelmode=transit) · [Moovit (unofficial deep link; may not prefill)](https://moovitapp.com/?fll=31.3156_35.3539&tll=31.243_34.7983&from=Masada%20Junction&to=Beersheba%20Central) · Set the time yourself to **Depart at 13:00, Tue 2026-11-17** (Google's documented URL has no time parameter).
**Corpus expectation (context, not a verdict):** outcome `either`, max_duration_min = 300, max_walk_m = 3000, min_duration_min = 40

> What to check: Sparse desert service with long access walks. Check the walking legs are physically plausible — not a 6 km hike along a highway shoulder.

**API RESULT: NO ROUTE** — a valid search inside coverage returned no journey. The API does not state a cause (no service, walking limit and data gaps look alike).
Request id `5d73ca22625244bb8a73873e7df247c6`.

| Usable? (Y/N) | Notes | Compared against / when checked |
|---|---|---|
|  |  |  |

---

## J25 — Dizengoff Center (דיזנגוף סנטר) → Yitzhak Navon Station (תחנת יצחק נבון)

category `shabbat-holiday` · calendar rule `shabbat`

**Requested:** Depart at Sat 2026-11-14 12:00 (UTC+02:00)  
Request field: `departAt=2026-11-14T12:00:00+02:00`
**Calendar flags:** Shabbat
**Compare:** [Google Maps transit](https://www.google.com/maps/dir/?api=1&origin=32.0757,34.7748&destination=31.7888,35.2027&travelmode=transit) · [Moovit (unofficial deep link; may not prefill)](https://moovitapp.com/?fll=32.0757_34.7748&tll=31.7888_35.2027&from=Dizengoff%20Center&to=Yitzhak%20Navon%20Station) · Set the time yourself to **Depart at 12:00, Sat 2026-11-14** (Google's documented URL has no time parameter).
**Corpus expectation (context, not a verdict):** outcome `either`

> What to check: THE Israeli calendar case: national rail and most buses do not run on Shabbat, while some operators and city lines do. A confident full itinerary on Saturday noon is almost certainly wrong. Verify whatever it returns against the actual calendar.txt entries.

**API RESULT: 3 journey option(s) returned** (scheduled times).
Request id `c792aa1683e24f2c8bc377890acf40de`.

**Option 1:** departs Sat 2026-11-14 17:51, arrives Sat 2026-11-14 19:04; total 73 min, 1 transfer(s), walking 12 min / 807 m

1. Walk 5 min, 294 m: START 17:51 -> דיזנגוף סנטר/המלך ג'ורג' 17:56
2. **bus 82** (דן) toward פתח תקווה_בית רבקה: board דיזנגוף סנטר/המלך ג'ורג' [code 20785] 17:56 -> alight ת. רכבת תל אביב סבידור/על פרשת דרכים [code 21140] 18:02 (service date 2026-11-14, trip `585014331_131126`)
3. Walk 2 min, 206 m: ת. רכבת תל אביב סבידור/על פרשת דרכים 18:02 -> ת.רכבת תל אביב - סבידור/רציפים B 18:04
4. **bus 480** (אגד) toward ירושלים_תחנה מרכזית: board ת.רכבת תל אביב - סבידור/רציפים B [code 20740] 18:15 -> alight ת. מרכזית ירושלים/הורדה [code 6109] 18:59 (service date 2026-11-14, trip `3996048_111126`)
5. Walk 5 min, 307 m: ת. מרכזית ירושלים/הורדה 18:59 -> END 19:04

Transfers (alight to next boarding, including any walk): ת. רכבת תל אביב סבידור/על פרשת דרכים -> ת.רכבת תל אביב - סבידור/רציפים B: 13 min

**Option 2:** departs Sat 2026-11-14 17:55, arrives Sat 2026-11-14 19:04; total 69 min, 2 transfer(s), walking 14 min / 940 m

1. Walk 5 min, 294 m: START 17:55 -> דיזנגוף סנטר/המלך ג'ורג' 18:00
2. **bus 14** (דן) toward תל אביב יפו_בבלי: board דיזנגוף סנטר/המלך ג'ורג' [code 20785] 18:00 -> alight בית המשפט/ויצמן [code 21238] 18:05 (service date 2026-11-14, trip `586287295_131126`)
3. Walk 2 min, 133 m: בית המשפט/ויצמן 18:08 -> ביה''ח איכילוב/ויצמן 18:10
4. **bus 7** (דן) toward חולון_מ.רפואי וולפסון: board ביה''ח איכילוב/ויצמן [code 21206] 18:10 -> alight ת. רכבת תל אביב סבידור/על פרשת דרכים [code 21140] 18:13 (service date 2026-11-14, trip `586276616_131126`)
5. Walk 2 min, 206 m: ת. רכבת תל אביב סבידור/על פרשת דרכים 18:13 -> ת.רכבת תל אביב - סבידור/רציפים B 18:15
6. **bus 480** (אגד) toward ירושלים_תחנה מרכזית: board ת.רכבת תל אביב - סבידור/רציפים B [code 20740] 18:15 -> alight ת. מרכזית ירושלים/הורדה [code 6109] 18:59 (service date 2026-11-14, trip `3996048_111126`)
7. Walk 5 min, 307 m: ת. מרכזית ירושלים/הורדה 18:59 -> END 19:04

Transfers (alight to next boarding, including any walk): בית המשפט/ויצמן -> ביה''ח איכילוב/ויצמן: 5 min; ת. רכבת תל אביב סבידור/על פרשת דרכים -> ת.רכבת תל אביב - סבידור/רציפים B: 2 min

**Option 3:** departs Sat 2026-11-14 18:11, arrives Sat 2026-11-14 19:19; total 68 min, 1 transfer(s), walking 12 min / 807 m

1. Walk 5 min, 294 m: START 18:11 -> דיזנגוף סנטר/המלך ג'ורג' 18:16
2. **bus 82** (דן) toward פתח תקווה_בית רבקה: board דיזנגוף סנטר/המלך ג'ורג' [code 20785] 18:16 -> alight ת. רכבת תל אביב סבידור/על פרשת דרכים [code 21140] 18:22 (service date 2026-11-14, trip `586276679_131126`)
3. Walk 2 min, 206 m: ת. רכבת תל אביב סבידור/על פרשת דרכים 18:22 -> ת.רכבת תל אביב - סבידור/רציפים B 18:24
4. **bus 480** (אגד) toward ירושלים_תחנה מרכזית: board ת.רכבת תל אביב - סבידור/רציפים B [code 20740] 18:30 -> alight ת. מרכזית ירושלים/הורדה [code 6109] 19:14 (service date 2026-11-14, trip `2095990_111126`)
5. Walk 5 min, 307 m: ת. מרכזית ירושלים/הורדה 19:14 -> END 19:19

Transfers (alight to next boarding, including any walk): ת. רכבת תל אביב סבידור/על פרשת דרכים -> ת.רכבת תל אביב - סבידור/רציפים B: 8 min

| Usable? (Y/N) | Notes | Compared against / when checked |
|---|---|---|
|  |  |  |

---

## J11-FRI — Tel Aviv Savidor Center (תל אביב סבידור מרכז) → Haifa Center HaShmona (חיפה מרכז השמונה)

category `intercity-rail` · calendar rule `friday_afternoon`

Calendar variant of J11: Friday afternoon: expect reduced or no rail service.

**Requested:** Depart at Fri 2026-11-13 15:30 (UTC+02:00)  
Request field: `departAt=2026-11-13T15:30:00+02:00`
**Calendar flags:** Friday (erev Shabbat)
**Compare:** [Google Maps transit](https://www.google.com/maps/dir/?api=1&origin=32.0836,34.7981&destination=32.8206,34.9985&travelmode=transit) · [Moovit (unofficial deep link; may not prefill)](https://moovitapp.com/?fll=32.0836_34.7981&tll=32.8206_34.9985&from=Tel%20Aviv%20Savidor%20Center&to=Haifa%20Center%20HaShmona) · Set the time yourself to **Depart at 15:30, Fri 2026-11-13** (Google's documented URL has no time parameter).
**Corpus expectation (context, not a verdict):** outcome `route`, max_duration_min = 130, max_transfers = 1, min_duration_min = 45, modes_any_of = ['rail']

> What to check: The flagship rail corridor. Cross-check timings against BetterRail.

**API RESULT: 3 journey option(s) returned** (scheduled times).
Machine note: matches the corpus expectation `route`. This is not a judgement of quality.
Request id `87693ebb56b348e0b82abec4fddfdef1`.

**Option 1:** departs Fri 2026-11-13 15:34, arrives Fri 2026-11-13 17:24; total 110 min, 1 transfer(s), walking 17 min / 1112 m

1. Walk 6 min, 431 m: START 15:34 -> ת. רכבת תל אביב - סבידור/דרך נמיר 15:40
2. **bus 909** (אגד) toward נהריה_תחנה מרכזית: board ת. רכבת תל אביב - סבידור/דרך נמיר [code 24068] 15:40 -> alight ת. מרכזית המפרץ/הורדה [code 43008] 16:54 (service date 2026-11-13, trip `59116972_111126`)
3. Walk 2 min, 112 m: ת. מרכזית המפרץ/הורדה 16:54 -> ת. מרכזית המפרץ/מטרונית לחיפה 16:56
4. **bus 1** (סופרבוס) toward חיפה_מרכזית חוף הכרמל: board ת. מרכזית המפרץ/מטרונית לחיפה [code 47488] 17:01 -> alight כרמלית [code 47203] 17:15 (service date 2026-11-13, trip `40077321_111126`)
5. Walk 9 min, 569 m: כרמלית 17:15 -> END 17:24

Transfers (alight to next boarding, including any walk): ת. מרכזית המפרץ/הורדה -> ת. מרכזית המפרץ/מטרונית לחיפה: 7 min

**Option 2:** departs Fri 2026-11-13 15:39, arrives Fri 2026-11-13 17:29; total 110 min, 1 transfer(s), walking 17 min / 1168 m

1. Walk 6 min, 431 m: START 15:39 -> ת. רכבת תל אביב - סבידור/דרך נמיר 15:45
2. **bus 900** (אגד) toward חיפה_מרכזית חוף הכרמל: board ת. רכבת תל אביב - סבידור/דרך נמיר [code 24068] 15:45 -> alight מת''מ [code 42656] 16:54 (service date 2026-11-13, trip `585657610_111126`)
3. Walk 2 min, 173 m: מת''מ 16:54 -> מת''מ 16:56
4. **bus 1** (סופרבוס) toward קרית מוצקין_מרכזית הקריות: board מת''מ [code 42229] 17:04 -> alight כרמלית [code 47576] 17:20 (service date 2026-11-13, trip `11253037_111126`)
5. Walk 9 min, 564 m: כרמלית 17:20 -> END 17:29

Transfers (alight to next boarding, including any walk): מת''מ -> מת''מ: 10 min

**Option 3:** departs Fri 2026-11-13 15:49, arrives Fri 2026-11-13 17:44; total 115 min, 1 transfer(s), walking 17 min / 1168 m

1. Walk 6 min, 431 m: START 15:49 -> ת. רכבת תל אביב - סבידור/דרך נמיר 15:55
2. **bus 900** (אגד) toward חיפה_מרכזית חוף הכרמל: board ת. רכבת תל אביב - סבידור/דרך נמיר [code 24068] 15:55 -> alight מת''מ [code 42656] 17:04 (service date 2026-11-13, trip `585657611_111126`)
3. Walk 2 min, 173 m: מת''מ 17:04 -> מת''מ 17:06
4. **bus 1** (סופרבוס) toward קרית מוצקין_מרכזית הקריות: board מת''מ [code 42229] 17:19 -> alight כרמלית [code 47576] 17:35 (service date 2026-11-13, trip `15202896_111126`)
5. Walk 9 min, 564 m: כרמלית 17:35 -> END 17:44

Transfers (alight to next boarding, including any walk): מת''מ -> מת''מ: 15 min

| Usable? (Y/N) | Notes | Compared against / when checked |
|---|---|---|
|  |  |  |

---

## J12-FRI — Tel Aviv Savidor Center (תל אביב סבידור מרכז) → Yitzhak Navon Station (תחנת יצחק נבון)

category `intercity-rail` · calendar rule `friday_afternoon`

Calendar variant of J12: Friday afternoon: expect reduced or no rail service.

**Requested:** Depart at Fri 2026-11-13 15:30 (UTC+02:00)  
Request field: `departAt=2026-11-13T15:30:00+02:00`
**Calendar flags:** Friday (erev Shabbat)
**Compare:** [Google Maps transit](https://www.google.com/maps/dir/?api=1&origin=32.0836,34.7981&destination=31.7888,35.2027&travelmode=transit) · [Moovit (unofficial deep link; may not prefill)](https://moovitapp.com/?fll=32.0836_34.7981&tll=31.7888_35.2027&from=Tel%20Aviv%20Savidor%20Center&to=Yitzhak%20Navon%20Station) · Set the time yourself to **Depart at 15:30, Fri 2026-11-13** (Google's documented URL has no time parameter).
**Corpus expectation (context, not a verdict):** outcome `route`, max_duration_min = 110, max_transfers = 1, min_duration_min = 30, modes_any_of = ['rail']

> What to check: Fast line. If it routes by bus, the rail calendar is probably misread.

**API RESULT: 3 journey option(s) returned** (scheduled times).
Machine note: matches the corpus expectation `route`. This is not a judgement of quality.
Request id `ea906e5cf47b4be18d13a3cda9a09a30`.

**Option 1:** departs Fri 2026-11-13 15:30, arrives Fri 2026-11-13 16:25; total 55 min, 0 transfer(s), walking 11 min / 710 m

1. Walk 6 min, 403 m: START 15:30 -> ת.רכבת תל אביב - סבידור/רציפים B 15:36
2. **bus 480** (אגד) toward ירושלים_תחנה מרכזית: board ת.רכבת תל אביב - סבידור/רציפים B [code 20740] 15:36 -> alight ת. מרכזית ירושלים/הורדה [code 6109] 16:20 (service date 2026-11-13, trip `2117248_111126`)
3. Walk 5 min, 307 m: ת. מרכזית ירושלים/הורדה 16:20 -> END 16:25

Transfers (alight to next boarding, including any walk): none

**Option 2:** departs Fri 2026-11-13 15:42, arrives Fri 2026-11-13 16:37; total 55 min, 0 transfer(s), walking 11 min / 710 m

1. Walk 6 min, 403 m: START 15:42 -> ת.רכבת תל אביב - סבידור/רציפים B 15:48
2. **bus 480** (אגד) toward ירושלים_תחנה מרכזית: board ת.רכבת תל אביב - סבידור/רציפים B [code 20740] 15:48 -> alight ת. מרכזית ירושלים/הורדה [code 6109] 16:32 (service date 2026-11-13, trip `2117249_111126`)
3. Walk 5 min, 307 m: ת. מרכזית ירושלים/הורדה 16:32 -> END 16:37

Transfers (alight to next boarding, including any walk): none

**Option 3:** departs Fri 2026-11-13 15:54, arrives Fri 2026-11-13 16:49; total 55 min, 0 transfer(s), walking 11 min / 710 m

1. Walk 6 min, 403 m: START 15:54 -> ת.רכבת תל אביב - סבידור/רציפים B 16:00
2. **bus 480** (אגד) toward ירושלים_תחנה מרכזית: board ת.רכבת תל אביב - סבידור/רציפים B [code 20740] 16:00 -> alight ת. מרכזית ירושלים/הורדה [code 6109] 16:44 (service date 2026-11-13, trip `1401293_111126`)
3. Walk 5 min, 307 m: ת. מרכזית ירושלים/הורדה 16:44 -> END 16:49

Transfers (alight to next boarding, including any walk): none

| Usable? (Y/N) | Notes | Compared against / when checked |
|---|---|---|
|  |  |  |

---

## J11-SAT — Tel Aviv Savidor Center (תל אביב סבידור מרכז) → Haifa Center HaShmona (חיפה מרכז השמונה)

category `intercity-rail` · calendar rule `shabbat`

Calendar variant of J11: Saturday noon: expect no national rail.

**Requested:** Depart at Sat 2026-11-14 12:00 (UTC+02:00)  
Request field: `departAt=2026-11-14T12:00:00+02:00`
**Calendar flags:** Shabbat
**Compare:** [Google Maps transit](https://www.google.com/maps/dir/?api=1&origin=32.0836,34.7981&destination=32.8206,34.9985&travelmode=transit) · [Moovit (unofficial deep link; may not prefill)](https://moovitapp.com/?fll=32.0836_34.7981&tll=32.8206_34.9985&from=Tel%20Aviv%20Savidor%20Center&to=Haifa%20Center%20HaShmona) · Set the time yourself to **Depart at 12:00, Sat 2026-11-14** (Google's documented URL has no time parameter).
**Corpus expectation (context, not a verdict):** outcome `route`, max_duration_min = 130, max_transfers = 1, min_duration_min = 45, modes_any_of = ['rail']

> What to check: The flagship rail corridor. Cross-check timings against BetterRail.

**API RESULT: 3 journey option(s) returned** (scheduled times).
Machine note: matches the corpus expectation `route`. This is not a judgement of quality.
Request id `7874cc2c59024e7bb45c9fae4fe3545c`.

**Option 1:** departs Sat 2026-11-14 15:35, arrives Sat 2026-11-14 18:30; total 175 min, 2 transfer(s), walking 19 min / 1362 m

1. Walk 6 min, 431 m: START 15:35 -> ת. רכבת תל אביב - סבידור/דרך נמיר 15:41
2. **bus 825** (אגד) toward עפולה_תחנה מרכזית: board ת. רכבת תל אביב - סבידור/דרך נמיר [code 24068] 15:41 -> alight ת.מרכזית עפולה/הורדה [code 52152] 17:11 (service date 2026-11-14, trip `25275651_111126`)
3. Walk 2 min, 250 m: ת.מרכזית עפולה/הורדה 17:13 -> ת.מרכזית עפולה/רציפים 17:15
4. **bus 301** (סופרבוס) toward חיפה_מרכזית המפרץ: board ת.מרכזית עפולה/רציפים [code 52174] 17:15 -> alight ת. מרכזית המפרץ/הורדה [code 43008] 17:56 (service date 2026-11-14, trip `14464441_111126`)
5. Walk 2 min, 112 m: ת. מרכזית המפרץ/הורדה 17:56 -> ת. מרכזית המפרץ/מטרונית לחיפה 17:58
6. **bus 1** (סופרבוס) toward חיפה_מרכזית חוף הכרמל: board ת. מרכזית המפרץ/מטרונית לחיפה [code 47488] 18:07 -> alight כרמלית [code 47203] 18:21 (service date 2026-11-14, trip `15018301_111126`)
7. Walk 9 min, 569 m: כרמלית 18:21 -> END 18:30

Transfers (alight to next boarding, including any walk): ת.מרכזית עפולה/הורדה -> ת.מרכזית עפולה/רציפים: 4 min; ת. מרכזית המפרץ/הורדה -> ת. מרכזית המפרץ/מטרונית לחיפה: 11 min

**Option 2:** departs Sat 2026-11-14 16:34, arrives Sat 2026-11-14 18:47; total 133 min, 1 transfer(s), walking 17 min / 1253 m

1. Walk 6 min, 431 m: START 16:34 -> ת. רכבת תל אביב - סבידור/דרך נמיר 16:40
2. **bus 836** (אגד) toward טבריה_תחנה מרכזית: board ת. רכבת תל אביב - סבידור/דרך נמיר [code 24068] 16:40 -> alight צומת השומרים [code 51536] 17:55 (service date 2026-11-14, trip `25276278_111126`)
3. Walk 2 min, 229 m: צומת השומרים 17:55 -> צומת השומרים 17:57
4. **bus 332** (נסיעות ותיירות) toward חיפה_רכבת מרכז השמונה: board צומת השומרים [code 43024] 18:13 -> alight קריית הממשלה/העצמאות [code 43096] 18:38 (service date 2026-11-14, trip `45520101_111126`)
5. Walk 9 min, 593 m: קריית הממשלה/העצמאות 18:38 -> END 18:47

Transfers (alight to next boarding, including any walk): צומת השומרים -> צומת השומרים: 18 min

**Option 3:** departs Sat 2026-11-14 16:45, arrives Sat 2026-11-14 18:45; total 120 min, 2 transfer(s), walking 17 min / 1042 m

1. Walk 6 min, 431 m: START 16:45 -> ת. רכבת תל אביב - סבידור/דרך נמיר 16:51
2. **bus 825** (אגד) toward עפולה_תחנה מרכזית: board ת. רכבת תל אביב - סבידור/דרך נמיר [code 24068] 16:51 -> alight צומת אולגה [code 41694] 17:28 (service date 2026-11-14, trip `25275451_111126`)
3. Walk 2 min, 0 m: צומת אולגה 17:42 -> צומת אולגה 17:44
4. **bus 947** (אגד) toward חיפה_מרכזית חוף הכרמל: board צומת אולגה [code 41694] 17:44 -> alight מת''מ [code 42656] 18:17 (service date 2026-11-14, trip `584672084_111126`)
5. Walk 2 min, 173 m: מת''מ 18:17 -> מת''מ 18:19
6. **bus 245** (אגד) toward חיפה_שוק תלפיות: board מת''מ [code 42229] 18:22 -> alight המגינים/ככר ההגנה [code 42723] 18:38 (service date 2026-11-14, trip `585108128_111126`)
7. Walk 7 min, 438 m: המגינים/ככר ההגנה 18:38 -> END 18:45

Transfers (alight to next boarding, including any walk): צומת אולגה -> צומת אולגה: 16 min; מת''מ -> מת''מ: 5 min

| Usable? (Y/N) | Notes | Compared against / when checked |
|---|---|---|
|  |  |  |

---

## J05-SAT — Mahane Yehuda Market (שוק מחנה יהודה) → Mount Herzl (הר הרצל)

category `jerusalem-urban-light-rail` · calendar rule `shabbat`

Calendar variant of J05: Saturday noon: Jerusalem urban case.

**Requested:** Depart at Sat 2026-11-14 12:00 (UTC+02:00)  
Request field: `departAt=2026-11-14T12:00:00+02:00`
**Calendar flags:** Shabbat
**Compare:** [Google Maps transit](https://www.google.com/maps/dir/?api=1&origin=31.7853,35.2124&destination=31.7736,35.1806&travelmode=transit) · [Moovit (unofficial deep link; may not prefill)](https://moovitapp.com/?fll=31.7853_35.2124&tll=31.7736_35.1806&from=Mahane%20Yehuda%20Market&to=Mount%20Herzl) · Set the time yourself to **Depart at 12:00, Sat 2026-11-14** (Google's documented URL has no time parameter).
**Corpus expectation (context, not a verdict):** outcome `route`, max_duration_min = 45, max_transfers = 1, min_duration_min = 8, modes_any_of = ['light_rail', 'bus']

> What to check: This is the light rail's spine. If it routes by bus instead, something is wrong.

**API RESULT: 3 journey option(s) returned** (scheduled times).
Machine note: matches the corpus expectation `route`. This is not a judgement of quality.
Request id `7497be570ce247a583fa2dd995170f53`.

**Option 1:** departs Sat 2026-11-14 17:59, arrives Sat 2026-11-14 18:24; total 25 min, 0 transfer(s), walking 11 min / 706 m

1. Walk 2 min, 145 m: START 17:59 -> מחנה יהודה 18:01
2. **light_rail 1** (כפיר) toward הדסה עין כרם: board מחנה יהודה [code 6172] 18:01 -> alight הר הרצל [code 6185] 18:15 (service date 2026-11-14, trip `586287190_111126`)
3. Walk 9 min, 561 m: הר הרצל 18:15 -> END 18:24

Transfers (alight to next boarding, including any walk): none

**Option 2:** departs Sat 2026-11-14 18:02, arrives Sat 2026-11-14 18:29; total 27 min, 0 transfer(s), walking 17 min / 1117 m

1. Walk 7 min, 431 m: START 18:02 -> יפו/שערי צדק 18:09
2. **bus 27** (אגד) toward הדסה עין כרם: board יפו/שערי צדק [code 1468] 18:09 -> alight יפה נוף/מגדים [code 1679] 18:19 (service date 2026-11-14, trip `585984839_111126`)
3. Walk 10 min, 686 m: יפה נוף/מגדים 18:19 -> END 18:29

Transfers (alight to next boarding, including any walk): none

**Option 3:** departs Sat 2026-11-14 18:08, arrives Sat 2026-11-14 18:33; total 25 min, 0 transfer(s), walking 11 min / 706 m

1. Walk 2 min, 145 m: START 18:08 -> מחנה יהודה 18:10
2. **light_rail 1** (כפיר) toward הדסה עין כרם: board מחנה יהודה [code 6172] 18:10 -> alight הר הרצל [code 6185] 18:24 (service date 2026-11-14, trip `586277225_111126`)
3. Walk 9 min, 561 m: הר הרצל 18:24 -> END 18:33

Transfers (alight to next boarding, including any walk): none

| Usable? (Y/N) | Notes | Compared against / when checked |
|---|---|---|
|  |  |  |

---

## J01-HOL — Dizengoff Center (דיזנגוף סנטר) → Ramat Gan Bursa (רמת גן בורסה)

category `tel-aviv-urban-bus` · calendar rule `holiday_morning`

Calendar variant of J01: Israeli holiday timetable, morning.

**NOT GENERATED:** no Israeli holiday date (non-Shabbat) from the holiday table in the usable range 2026-11-11 00:00 .. 2026-12-11 00:00 (Asia/Jerusalem).

No request was sent. This calendar situation is not covered by this sheet.

---

## J12-HOL — Tel Aviv Savidor Center (תל אביב סבידור מרכז) → Yitzhak Navon Station (תחנת יצחק נבון)

category `intercity-rail` · calendar rule `holiday_midday`

Calendar variant of J12: Israeli holiday timetable, midday intercity.

**NOT GENERATED:** no Israeli holiday date (non-Shabbat) from the holiday table in the usable range 2026-11-11 00:00 .. 2026-12-11 00:00 (Asia/Jerusalem).

No request was sent. This calendar situation is not covered by this sheet.

---

## J01-DST — Dizengoff Center (דיזנגוף סנטר) → Ramat Gan Bursa (רמת גן בורסה)

category `tel-aviv-urban-bus` · calendar rule `dst_day_peak`

Calendar variant of J01: Peak on the DST fall-back day.

**NOT GENERATED:** no DST fall-back day in the usable range 2026-11-11 00:00 .. 2026-12-11 00:00 (Asia/Jerusalem).

No request was sent. This calendar situation is not covered by this sheet.

---

## J22-DST1 — Dizengoff Center (דיזנגוף סנטר) → Ramat Gan Bursa (רמת גן בורסה)

category `service-day-boundary` · calendar rule `dst_repeat_first`

Calendar variant of J22: Repeated hour, first occurrence (earlier offset).

**NOT GENERATED:** no repeated-hour instant in the usable range 2026-11-11 00:00 .. 2026-12-11 00:00 (Asia/Jerusalem).

No request was sent. This calendar situation is not covered by this sheet.

---

## J22-DST2 — Dizengoff Center (דיזנגוף סנטר) → Ramat Gan Bursa (רמת גן בורסה)

category `service-day-boundary` · calendar rule `dst_repeat_second`

Calendar variant of J22: Repeated hour, second occurrence (later offset).

**NOT GENERATED:** no repeated-hour instant in the usable range 2026-11-11 00:00 .. 2026-12-11 00:00 (Asia/Jerusalem).

No request was sent. This calendar situation is not covered by this sheet.

---
