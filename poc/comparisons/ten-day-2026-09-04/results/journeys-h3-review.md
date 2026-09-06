# POC-2 — journey review sheet for checkpoint H3

**This sheet is the checkpoint, not a report of one.** Everything below was
produced by machine checks that verify *structure* — that legs join up, that
times run forwards, that stop ids exist in the feed, that durations are not
absurd. None of it judges whether a route is one a person would actually take.
PRD §7 puts that bar at **9 of the 10 required journeys producing reasonable,**
**usable routes**, judged by comparison against Moovit, Google Maps and
BetterRail. That judgement is yours.

Fill in the `Verdict:` line under each case. `reasonable` / `not reasonable` /
`unsure`, plus a note if it helps.

---

## What you are looking at

- **Feed:** `Gtfs_10_days.zip`, sha256 `08c168da3e6c201c…`
- **Service window:** 2026-09-05 (Sat) .. 2026-09-14 (Mon) (KDP-001 — the feed does *not* cover 4 Sep,
  so every departure time below was resolved onto a date inside the window)
- **Engine:** MOTIS v2.11.2, endpoint `/api/v6/plan`
- **Graph built:** 40 s, peak 3738.6 MB, 910.8 MB on disk
- **Served from:** a container capped at **8 GB** (system-design §320's production box)
- **At rest:** 937.8 MB, 11.4% of the cap, flat across 25 samples
- **Under load:** 20632 requests, all HTTP 200, p95 256.6 ms, peak 1129.5 MB = 13.8% of the cap, no OOM

Times are **Israeli local time (IDT, UTC+3)**. Stop names are exactly as the
MOT feed spells them, in Hebrew, because that is what you will be matching
against in Moovit.

### Two query profiles were run

- **default** — MOTIS as shipped. This is the primary result. It allows 15
  minutes of walking to the first stop and from the last.
- **generous-walk** — the same 25 cases with that walking budget raised to 30
  minutes. Where the two disagree it is noted in the case, because "no route"
  caused by a walking budget is a very different finding from "no route"
  caused by the data.

**Machine totals (default profile): 25/25 answered, 21 structurally consistent with the case's expectations.**
**Same under generous-walk: 22/25.**

---

## J01 — Dizengoff Center → Ramat Gan Bursa

*PRD §7 #1 Tel Aviv → Ramat Gan* · category `tel-aviv-urban-bus`

**Departing:** 2026-09-07T08:00:00+03:00 (rule `weekday_morning`)

> **What to check:** Would a Tel Aviv resident actually take this? Compare against Moovit.

**The corpus expected:** outcome `route`, `modes_any_of` = ['bus', 'light_rail'], `max_transfers` = 2, `min_duration_min` = 10, `max_duration_min` = 55

**RESULT: 5 itinerary/itineraries returned.** The first one — the one a
user would be shown — is:

```
    Departs Mon 07 Sep 08:06 (6 min after the requested time)
    Arrives Mon 07 Sep 08:24 -- 18 min, 0 transfer(s)

    08:06-08:11  walk 294 m                    START -> דיזנגוף סנטר/המלך ג'ורג'
    08:11-08:20  bus 82                        דיזנגוף סנטר/המלך ג'ורג' -> ת.רק"ל אבא הלל/דרך ז'בוטינסקי
               operator דן, towards פתח תקווה_בית רבקה
    08:20-08:24  walk 240 m                    ת.רק"ל אבא הלל/דרך ז'בוטינסקי -> END
```

<details><summary>Alternatives MOTIS also returned (4 more)</summary>

**Alternative 1**

```
    Departs Mon 07 Sep 08:14 (14 min after the requested time)
    Arrives Mon 07 Sep 08:33 -- 19 min, 0 transfer(s)

    08:14-08:17  walk 135 m                    START -> דיזנגוף סנטר/דיזנגוף
    08:17-08:29  bus 238                       דיזנגוף סנטר/דיזנגוף -> ת.רק"ל אבא הלל
               operator דן, towards פתח תקווה_הדר גנים
    08:29-08:33  walk 250 m                    ת.רק"ל אבא הלל -> END
```

**Alternative 2**

```
    Departs Mon 07 Sep 08:17 (17 min after the requested time)
    Arrives Mon 07 Sep 08:35 -- 18 min, 0 transfer(s)

    08:17-08:22  walk 294 m                    START -> דיזנגוף סנטר/המלך ג'ורג'
    08:22-08:31  bus 82                        דיזנגוף סנטר/המלך ג'ורג' -> ת.רק"ל אבא הלל/דרך ז'בוטינסקי
               operator דן, towards פתח תקווה_בית רבקה
    08:31-08:35  walk 240 m                    ת.רק"ל אבא הלל/דרך ז'בוטינסקי -> END
```

**Alternative 3**

```
    Departs Mon 07 Sep 08:18 (18 min after the requested time)
    Arrives Mon 07 Sep 08:42 -- 24 min, 0 transfer(s)

    08:18-08:32  walk 837 m                    START -> לונדון מיניסטור/שד' שאול המלך
    08:32-08:38  bus 142                       לונדון מיניסטור/שד' שאול המלך -> ת.רק"ל אבא הלל
               operator דן, towards תל אביב יפו_קריית עתידים
    08:38-08:42  walk 250 m                    ת.רק"ל אבא הלל -> END
```

</details>

<sub>Machine checks (structure only — not a quality judgement): structural check (any itinerary): **pass**</sub>

**Verdict:** 

---

## J02 — Tel Aviv University → Sourasky Medical Center (Ichilov)

category `tel-aviv-urban-bus`

**Departing:** 2026-09-07T08:00:00+03:00 (rule `weekday_morning`)

> **What to check:** Peak-hour campus-to-hospital trip. Is the walk at either end reasonable?

**The corpus expected:** outcome `route`, `modes_any_of` = ['bus', 'light_rail', 'rail'], `max_transfers` = 2, `min_duration_min` = 12, `max_duration_min` = 60

**RESULT: 5 itinerary/itineraries returned.** The first one — the one a
user would be shown — is:

```
    Departs Mon 07 Sep 08:00 (at the requested time)
    Arrives Mon 07 Sep 08:26 -- 26 min, 1 transfer(s)

    08:00-08:06  walk 389 m                    START -> האוניברסיטה/חיים לבנון
    08:06-08:13  bus 24                        האוניברסיטה/חיים לבנון -> דרך נמיר/יהודה המכבי
               operator מטרופולין, towards תל אביב יפו_מסוף כרמלית
    08:13-08:15  walk 0 m                      דרך נמיר/יהודה המכבי -> דרך נמיר/יהודה המכבי
    08:15-08:21  bus 89                        דרך נמיר/יהודה המכבי -> ביה"ח איכילוב/ויצמן
               operator דן, towards חולון_פארק פרס
    08:21-08:26  walk 275 m                    ביה"ח איכילוב/ויצמן -> END
```

<details><summary>Alternatives MOTIS also returned (4 more)</summary>

**Alternative 1**

```
    Departs Mon 07 Sep 08:05 (5 min after the requested time)
    Arrives Mon 07 Sep 08:30 -- 25 min, 1 transfer(s)

    08:05-08:13  walk 495 m                    START -> אינשטיין/אהרון בארט
    08:13-08:23  bus 40                        אינשטיין/אהרון בארט -> דרך נמיר/שדרות שאול המלך
               operator דן, towards בת ים_מרכז הספורט
    08:23-08:25  walk 147 m                    דרך נמיר/שדרות שאול המלך -> שדרות שאול המלך/הנרייטה סולד
    08:25-08:26  bus 7                         שדרות שאול המלך/הנרייטה סולד -> בית המשפט/ויצמן
               operator דן, towards תל אביב יפו_רכבת האוניברסיטה
    08:26-08:30  walk 239 m                    בית המשפט/ויצמן -> END
```

**Alternative 2**

```
    Departs Mon 07 Sep 08:08 (8 min after the requested time)
    Arrives Mon 07 Sep 08:35 -- 27 min, 2 transfer(s)

    08:08-08:14  walk 389 m                    START -> האוניברסיטה/חיים לבנון
    08:14-08:19  bus 126                       האוניברסיטה/חיים לבנון -> סמינר הקיבוצים/דרך נמיר
               operator מטרופולין, towards בת ים_מרכז הספורט
    08:20-08:22  walk 0 m                      סמינר הקיבוצים/דרך נמיר -> סמינר הקיבוצים/דרך נמיר
    08:22-08:28  bus 249                       סמינר הקיבוצים/דרך נמיר -> בית הדר דפנה/שד' שאול המלך
               operator מטרופולין, towards תל אביב יפו_מסוף כרמלית
    08:28-08:30  walk 0 m                      בית הדר דפנה/שד' שאול המלך -> בית הדר דפנה/שד' שאול המלך
    08:30-08:31  bus 18                        בית הדר דפנה/שד' שאול המלך -> בית המשפט/ויצמן
               operator דן, towards בת ים_בית עלמין
    08:31-08:35  walk 239 m                    בית המשפט/ויצמן -> END
```

**Alternative 3**

```
    Departs Mon 07 Sep 08:10 (10 min after the requested time)
    Arrives Mon 07 Sep 08:36 -- 26 min, 0 transfer(s)

    08:10-08:18  walk 495 m                    START -> אינשטיין/אהרון בארט
    08:18-08:31  bus 7                         אינשטיין/אהרון בארט -> ביה"ח איכילוב/ויצמן
               operator דן, towards חולון_מ.רפואי וולפסון
    08:31-08:36  walk 275 m                    ביה"ח איכילוב/ויצמן -> END
```

</details>

<sub>Machine checks (structure only — not a quality judgement): structural check (any itinerary): **pass**</sub>

**Verdict:** 

---

## J03 — Jaffa Clock Tower → Tel Aviv Savidor Center

category `tel-aviv-urban-bus`

**Departing:** 2026-09-08T13:00:00+03:00 (rule `weekday_midday`)

> **What to check:** Jaffa to the main station. Does it use the red line where sensible?

**The corpus expected:** outcome `route`, `modes_any_of` = ['bus', 'light_rail'], `max_transfers` = 2, `min_duration_min` = 15, `max_duration_min` = 65

**RESULT: 6 itinerary/itineraries returned.** The first one — the one a
user would be shown — is:

```
    Departs Tue 08 Sep 13:04 (4 min after the requested time)
    Arrives Tue 08 Sep 13:35 -- 31 min, 0 transfer(s)

    13:04-13:09  walk 356 m                    START -> יפת/לואי פסטר
    13:09-13:29  bus 44                        יפת/לואי פסטר -> ת. רכבת תל אביב - סבידור/דרך נמיר
               operator דן, towards תל אביב יפו_קריית עתידים
    13:29-13:35  walk 431 m                    ת. רכבת תל אביב - סבידור/דרך נמיר -> END
```

<details><summary>Alternatives MOTIS also returned (5 more)</summary>

**Alternative 1**

```
    Departs Tue 08 Sep 13:05 (5 min after the requested time)
    Arrives Tue 08 Sep 13:39 -- 34 min, 2 transfer(s)

    13:05-13:11  walk 397 m                    START -> יפת/לואי פסטר
    13:11-13:18  bus 18                        יפת/לואי פסטר -> ת.רק"ל מחרוזת/סהרון
               operator דן, towards בת ים_בית עלמין
    13:18-13:20  walk 137 m                    ת.רק"ל מחרוזת/סהרון -> שד' ירושלים/מחרוזת
    13:20-13:22  bus 6                         שד' ירושלים/מחרוזת -> ת. רכבת וולפסון
               operator דן, towards תל אביב יפו_מסוף הלוחמים
    13:22-13:24  walk 249 m                    ת. רכבת וולפסון -> חולון וולפסון
    13:24-13:38  regional rail (no line number in feed) חולון וולפסון -> תל אביב מרכז
               operator רכבת ישראל, towards 318
    13:38-13:39  walk 27 m                     תל אביב מרכז -> END
```

**Alternative 2**

```
    Departs Tue 08 Sep 13:06 (6 min after the requested time)
    Arrives Tue 08 Sep 13:41 -- 35 min, 1 transfer(s)

    13:06-13:15  walk 639 m                    START -> כיכר השעון/מרזוק ועזר
    13:15-13:24  bus 54                        כיכר השעון/מרזוק ועזר -> ת.רכבת ההגנה
               operator דן, towards קריית עתידים
    13:24-13:26  walk 98 m                     ת.רכבת ההגנה -> ת. רכבת ההגנה/החרש
    13:26-13:35  bus 71                        ת. רכבת ההגנה/החרש -> ת. רכבת תל אביב - סבידור/דרך נמיר
               operator סופרבוס, towards תל אביב יפו_מכללת לוינסקי
    13:35-13:41  walk 431 m                    ת. רכבת תל אביב - סבידור/דרך נמיר -> END
```

**Alternative 3**

```
    Departs Tue 08 Sep 13:07 (7 min after the requested time)
    Arrives Tue 08 Sep 13:42 -- 35 min, 0 transfer(s)

    13:07-13:20  walk 879 m                    START -> שלמה
    13:20-13:34  tram 1                        שלמה -> ארלוזורוב
               operator תבל, towards פתח תקווה_ת. מרכזית פתח תקווה
    13:34-13:42  walk 498 m                    ארלוזורוב -> END
```

</details>

<sub>Machine checks (structure only — not a quality judgement): structural check (any itinerary): **pass**</sub>

**Verdict:** 

---

## J04 — Dizengoff Center → Petah Tikva Kiryat Arye

*PRD §7 #2 Tel Aviv → Petah Tikva* · category `tel-aviv-urban-bus`

**Departing:** 2026-09-09T18:30:00+03:00 (rule `weekday_evening`)

> **What to check:** Evening peak. Does it prefer rail or bus, and is that the right call?

**The corpus expected:** outcome `route`, `modes_any_of` = ['bus', 'rail', 'light_rail'], `max_transfers` = 2, `min_duration_min` = 20, `max_duration_min` = 90

**RESULT: 5 itinerary/itineraries returned.** The first one — the one a
user would be shown — is:

```
    Departs Wed 09 Sep 18:31 (at the requested time)
    Arrives Wed 09 Sep 19:06 -- 35 min, 1 transfer(s)

    18:31-18:34  walk 135 m                    START -> דיזנגוף סנטר/דיזנגוף
    18:34-18:41  bus 63                        דיזנגוף סנטר/דיזנגוף -> ת.רק"ל יהודית/דרך מנחם בגין
               operator דן, towards רמת גן_אלוף שדה
    18:41-18:43  walk 93 m                     ת.רק"ל יהודית/דרך מנחם בגין -> יהודית
    18:43-18:58  tram 1                        יהודית -> שנקר
               operator תבל, towards פתח תקווה_ת. מרכזית פתח תקווה
    18:58-19:06  walk 477 m                    שנקר -> END
```

<details><summary>Alternatives MOTIS also returned (4 more)</summary>

**Alternative 1**

```
    Departs Wed 09 Sep 18:36 (6 min after the requested time)
    Arrives Wed 09 Sep 19:11 -- 35 min, 0 transfer(s)

    18:36-18:41  walk 294 m                    START -> דיזנגוף סנטר/המלך ג'ורג'
    18:41-19:03  bus 82                        דיזנגוף סנטר/המלך ג'ורג' -> ת.רק"ל שנקר/דרך ז'בוטינסקי
               operator דן, towards פתח תקווה_בית רבקה
    19:03-19:11  walk 459 m                    ת.רק"ל שנקר/דרך ז'בוטינסקי -> END
```

**Alternative 2**

```
    Departs Wed 09 Sep 18:42 (12 min after the requested time)
    Arrives Wed 09 Sep 19:17 -- 35 min, 1 transfer(s)

    18:42-18:45  walk 135 m                    START -> דיזנגוף סנטר/דיזנגוף
    18:45-18:52  bus 63                        דיזנגוף סנטר/דיזנגוף -> ת.רק"ל יהודית/דרך מנחם בגין
               operator דן, towards רמת גן_אלוף שדה
    18:52-18:54  walk 93 m                     ת.רק"ל יהודית/דרך מנחם בגין -> יהודית
    18:54-19:09  tram 1                        יהודית -> שנקר
               operator תבל, towards פתח תקווה_ת. מרכזית פתח תקווה
    19:09-19:17  walk 477 m                    שנקר -> END
```

**Alternative 3**

```
    Departs Wed 09 Sep 18:46 (16 min after the requested time)
    Arrives Wed 09 Sep 19:21 -- 35 min, 0 transfer(s)

    18:46-18:51  walk 294 m                    START -> דיזנגוף סנטר/המלך ג'ורג'
    18:51-19:13  bus 82                        דיזנגוף סנטר/המלך ג'ורג' -> ת.רק"ל שנקר/דרך ז'בוטינסקי
               operator דן, towards פתח תקווה_בית רבקה
    19:13-19:21  walk 459 m                    ת.רק"ל שנקר/דרך ז'בוטינסקי -> END
```

</details>

<sub>Machine checks (structure only — not a quality judgement): structural check (any itinerary): **pass**</sub>

**Verdict:** 

---

## J05 — Mahane Yehuda Market → Mount Herzl

category `jerusalem-urban-light-rail`

**Departing:** 2026-09-08T13:00:00+03:00 (rule `weekday_midday`)

> **What to check:** This is the light rail's spine. If it routes by bus instead, something is wrong.

**The corpus expected:** outcome `route`, `modes_any_of` = ['light_rail', 'bus'], `max_transfers` = 1, `min_duration_min` = 8, `max_duration_min` = 45

**RESULT: 6 itinerary/itineraries returned.** The first one — the one a
user would be shown — is:

```
    Departs Tue 08 Sep 13:02 (at the requested time)
    Arrives Tue 08 Sep 13:27 -- 25 min, 0 transfer(s)

    13:02-13:04  walk 145 m                    START -> מחנה יהודה
    13:04-13:18  tram 1                        מחנה יהודה -> הר הרצל
               operator כפיר, towards הדסה עין כרם
    13:18-13:27  walk 561 m                    הר הרצל -> END
```

<details><summary>Alternatives MOTIS also returned (5 more)</summary>

**Alternative 1**

```
    Departs Tue 08 Sep 13:07 (7 min after the requested time)
    Arrives Tue 08 Sep 13:32 -- 25 min, 0 transfer(s)

    13:07-13:09  walk 145 m                    START -> מחנה יהודה
    13:09-13:23  tram 1                        מחנה יהודה -> הר הרצל
               operator כפיר, towards הדסה עין כרם
    13:23-13:32  walk 561 m                    הר הרצל -> END
```

**Alternative 2**

```
    Departs Tue 08 Sep 13:12 (12 min after the requested time)
    Arrives Tue 08 Sep 13:37 -- 25 min, 0 transfer(s)

    13:12-13:14  walk 145 m                    START -> מחנה יהודה
    13:14-13:28  tram 1                        מחנה יהודה -> הר הרצל
               operator כפיר, towards הדסה עין כרם
    13:28-13:37  walk 561 m                    הר הרצל -> END
```

**Alternative 3**

```
    Departs Tue 08 Sep 13:17 (17 min after the requested time)
    Arrives Tue 08 Sep 13:42 -- 25 min, 0 transfer(s)

    13:17-13:19  walk 145 m                    START -> מחנה יהודה
    13:19-13:33  tram 1                        מחנה יהודה -> הר הרצל
               operator כפיר, towards הדסה עין כרם
    13:33-13:42  walk 561 m                    הר הרצל -> END
```

</details>

<sub>Machine checks (structure only — not a quality judgement): structural check (any itinerary): **pass**</sub>

**Verdict:** 

---

## J06 — Jerusalem Central Bus Station → Hebrew University Mount Scopus

category `jerusalem-urban-light-rail`

**Departing:** 2026-09-07T08:00:00+03:00 (rule `weekday_morning`)

> **What to check:** Cross-city to Mount Scopus. Check the transfer point is a real interchange.

**The corpus expected:** outcome `route`, `modes_any_of` = ['light_rail', 'bus'], `max_transfers` = 2, `min_duration_min` = 15, `max_duration_min` = 70

**RESULT: 6 itinerary/itineraries returned.** The first one — the one a
user would be shown — is:

```
    Departs Mon 07 Sep 08:01 (at the requested time)
    Arrives Mon 07 Sep 08:28 -- 27 min, 1 transfer(s)

    08:01-08:02  walk 57 m                     START -> ת. מרכזית ירושלים/יפו
    08:02-08:07  bus 18                        ת. מרכזית ירושלים/יפו -> ככר הדוידקה/הנביאים
               operator אגד, towards מלחה
    08:07-08:09  walk 0 m                      ככר הדוידקה/הנביאים -> ככר הדוידקה/הנביאים
    08:12-08:23  bus 19א                       ככר הדוידקה/הנביאים -> האוניברסיטה העברית הר הצופים/מרטין בובר
               operator אגד, towards מסוף הר הצופים
    08:23-08:28  walk 290 m                    האוניברסיטה העברית הר הצופים/מרטין בובר -> END
```

<details><summary>Alternatives MOTIS also returned (5 more)</summary>

**Alternative 1**

```
    Departs Mon 07 Sep 08:07 (7 min after the requested time)
    Arrives Mon 07 Sep 08:30 -- 23 min, 0 transfer(s)

    08:07-08:12  walk 332 m                    START -> שרי ישראל/יפו
    08:12-08:25  bus 568                       שרי ישראל/יפו -> האוניברסיטה העברית הר הצופים/מרטין בובר
               operator אקסטרה ירושלים, towards מסוף הר הצופים
    08:25-08:30  walk 290 m                    האוניברסיטה העברית הר הצופים/מרטין בובר -> END
```

**Alternative 2**

```
    Departs Mon 07 Sep 08:08 (8 min after the requested time)
    Arrives Mon 07 Sep 08:32 -- 24 min, 1 transfer(s)

    08:08-08:09  walk 57 m                     START -> ת. מרכזית ירושלים/יפו
    08:09-08:16  bus 74                        ת. מרכזית ירושלים/יפו -> הנביאים/הרב קוק
               operator סופרבוס, towards חומת שמואל
    08:16-08:18  walk 0 m                      הנביאים/הרב קוק -> הנביאים/הרב קוק
    08:18-08:27  bus 19                        הנביאים/הרב קוק -> האוניברסיטה העברית הר הצופים/מרטין בובר
               operator אגד, towards מסוף הר הצופים
    08:27-08:32  walk 290 m                    האוניברסיטה העברית הר הצופים/מרטין בובר -> END
```

**Alternative 3**

```
    Departs Mon 07 Sep 08:10 (10 min after the requested time)
    Arrives Mon 07 Sep 08:36 -- 26 min, 1 transfer(s)

    08:10-08:12  walk 99 m                     START -> התחנה המרכזית
    08:12-08:18  tram 1                        התחנה המרכזית -> הדווידקה
               operator כפיר, towards נווה יעקב צפ'
    08:18-08:20  walk 133 m                    הדווידקה -> ככר הדוידקה/הנביאים
    08:20-08:31  bus 19                        ככר הדוידקה/הנביאים -> האוניברסיטה העברית הר הצופים/מרטין בובר
               operator אגד, towards מסוף הר הצופים
    08:31-08:36  walk 290 m                    האוניברסיטה העברית הר הצופים/מרטין בובר -> END
```

</details>

<sub>Machine checks (structure only — not a quality judgement): structural check (any itinerary): **pass**</sub>

**Verdict:** 

---

## J07 — Yitzhak Navon Station → Malha Mall

category `jerusalem-urban-light-rail`

**Departing:** 2026-09-09T18:30:00+03:00 (rule `weekday_evening`)

> **What to check:** Does it consider the Malha rail branch, and is that sensible at this hour?

**The corpus expected:** outcome `route`, `modes_any_of` = ['light_rail', 'bus', 'rail'], `max_transfers` = 2, `min_duration_min` = 15, `max_duration_min` = 70

**RESULT: 7 itinerary/itineraries returned.** The first one — the one a
user would be shown — is:

```
    Departs Wed 09 Sep 18:33 (3 min after the requested time)
    Arrives Wed 09 Sep 18:56 -- 23 min, 0 transfer(s)

    18:33-18:37  walk 227 m                    START -> שדרות שז"ר/בנייני האומה
    18:37-18:46  bus 531                       שדרות שז"ר/בנייני האומה -> אצטדיון טדי/א"ס ביתר
               operator סופרבוס, towards גילה
    18:46-18:56  walk 305 m                    אצטדיון טדי/א"ס ביתר -> END
```

<details><summary>Alternatives MOTIS also returned (6 more)</summary>

**Alternative 1**

```
    Departs Wed 09 Sep 18:33 (3 min after the requested time)
    Arrives Wed 09 Sep 18:55 -- 22 min, 1 transfer(s)

    18:33-18:37  walk 227 m                    START -> שדרות שז"ר/בנייני האומה
    18:37-18:46  bus 531                       שדרות שז"ר/בנייני האומה -> אצטדיון טדי/א"ס ביתר
               operator סופרבוס, towards גילה
    18:46-18:48  walk 0 m                      אצטדיון טדי/א"ס ביתר -> אצטדיון טדי/א"ס ביתר
    18:48-18:49  bus 18                        אצטדיון טדי/א"ס ביתר -> קניון מלחה/א"ס מכבי
               operator אגד, towards מלחה
    18:49-18:55  walk 140 m                    קניון מלחה/א"ס מכבי -> END
```

**Alternative 2**

```
    Departs Wed 09 Sep 18:34 (4 min after the requested time)
    Arrives Wed 09 Sep 18:57 -- 23 min, 0 transfer(s)

    18:34-18:38  walk 227 m                    START -> שדרות שז"ר/בנייני האומה
    18:38-18:47  bus 504                       שדרות שז"ר/בנייני האומה -> אצטדיון טדי/א"ס ביתר
               operator סופרבוס, towards חומת שמואל
    18:47-18:57  walk 305 m                    אצטדיון טדי/א"ס ביתר -> END
```

**Alternative 3**

```
    Departs Wed 09 Sep 18:40 (10 min after the requested time)
    Arrives Wed 09 Sep 18:58 -- 18 min, 0 transfer(s)

    18:40-18:44  walk 227 m                    START -> שדרות שז"ר/בנייני האומה
    18:44-18:52  bus 31                        שדרות שז"ר/בנייני האומה -> קניון מלחה/א"ס הפועל   האייל
               operator סופרבוס, towards גילה
    18:52-18:58  walk 422 m                    קניון מלחה/א"ס הפועל   האייל -> END
```

</details>

<sub>Machine checks (structure only — not a quality judgement): structural check (any itinerary): **pass**</sub>

**Verdict:** 

---

## J08 — Haifa Center HaShmona → Technion

category `haifa-urban`

**Departing:** 2026-09-07T08:00:00+03:00 (rule `weekday_morning`)

> **What to check:** Haifa is vertical. Check the walking legs are not absurd gradients.

**The corpus expected:** outcome `route`, `modes_any_of` = ['bus', 'cable_car', 'funicular'], `max_transfers` = 2, `min_duration_min` = 15, `max_duration_min` = 75

**RESULT: 5 itinerary/itineraries returned.** The first one — the one a
user would be shown — is:

```
    Departs Mon 07 Sep 08:03 (3 min after the requested time)
    Arrives Mon 07 Sep 08:42 -- 39 min, 2 transfer(s)

    08:03-08:12  walk 553 m                    START -> עיר תחתית
    08:12-08:12  funicular 1                   עיר תחתית -> הנביאים
               operator כרמלית, towards מרכז הכרמל
    08:14-08:16  walk 70 m                     הנביאים -> תחנת כרמלית/הנביאים
    08:16-08:32  bus 148                       תחנת כרמלית/הנביאים -> חנקין/קומוי
               operator אגד, towards חיפה_אוניברסיטה
    08:32-08:34  walk 175 m                    חנקין/קומוי -> קומוי/חנקין
    08:35-08:37  bus 77                        קומוי/חנקין -> טכניון/מעונות העמים
               operator אגד, towards יגור_מסוף יגור
    08:37-08:42  walk 275 m                    טכניון/מעונות העמים -> END
```

<details><summary>Alternatives MOTIS also returned (4 more)</summary>

**Alternative 1**

```
    Departs Mon 07 Sep 08:05 (5 min after the requested time)
    Arrives Mon 07 Sep 08:45 -- 40 min, 0 transfer(s)

    08:05-08:16  walk 719 m                    START -> תחנת רכבת חיפה מרכז השמונה
    08:16-08:40  bus 17                        תחנת רכבת חיפה מרכז השמונה -> טכניון/מעונות העמים
               operator אגד, towards טכניון
    08:40-08:45  walk 275 m                    טכניון/מעונות העמים -> END
```

**Alternative 2**

```
    Departs Mon 07 Sep 08:14 (14 min after the requested time)
    Arrives Mon 07 Sep 08:58 -- 44 min, 0 transfer(s)

    08:14-08:29  walk 927 m                    START -> חסן שוקרי/הנביאים
    08:29-08:53  bus 19                        חסן שוקרי/הנביאים -> טכניון/מעונות העמים
               operator אגד, towards טכניון
    08:53-08:58  walk 275 m                    טכניון/מעונות העמים -> END
```

**Alternative 3**

```
    Departs Mon 07 Sep 08:15 (15 min after the requested time)
    Arrives Mon 07 Sep 08:50 -- 35 min, 1 transfer(s)

    08:15-08:24  walk 553 m                    START -> עיר תחתית
    08:24-08:25  funicular 1                   עיר תחתית -> ביה"ח בני ציון
               operator כרמלית, towards מרכז הכרמל
    08:25-08:27  walk 105 m                    ביה"ח בני ציון -> תחנת כרמלית/גולומב
    08:28-08:45  bus 76                        תחנת כרמלית/גולומב -> טכניון/מעונות העמים
               operator אגד, towards יגור_מסוף יגור
    08:45-08:50  walk 275 m                    טכניון/מעונות העמים -> END
```

</details>

<sub>Machine checks (structure only — not a quality judgement): structural check (any itinerary): **pass**</sub>

**Verdict:** 

---

## J09 — Haifa University → Bat Galim Central Station

category `haifa-urban`

**Departing:** 2026-09-09T18:30:00+03:00 (rule `weekday_evening`)

> **What to check:** Long descent across the Carmel. Compare to Moovit for line choice.

**The corpus expected:** outcome `route`, `modes_any_of` = ['bus', 'rail'], `max_transfers` = 2, `min_duration_min` = 20, `max_duration_min` = 85

**RESULT: no route returned.**

With the walking budget raised to 30 minutes each end, this case *does*
route. The itinerary it produces is shown below — it is from the
**generous-walk** profile, not the default one.

```
    Departs Wed 09 Sep 18:30 (at the requested time)
    Arrives Wed 09 Sep 19:31 -- 61 min, 0 transfer(s)

    18:30-18:36  walk 399 m                    START -> אוניברסיטה/מגדל אשכול
    18:36-19:15  bus 148                       אוניברסיטה/מגדל אשכול -> עין הים
               operator אגד, towards טירת כרמל_מרכז לבריאות הנפש
    19:15-19:31  walk 1039 m                   עין הים -> END
```

<sub>Machine checks (structure only — not a quality judgement): structural check (any itinerary): **fail** · no itineraries returned but the case expects outcome=route</sub>

**Verdict:** 

---

## J10 — Grand Kanyon Haifa → Rambam Medical Center

category `haifa-urban`

**Departing:** 2026-09-08T13:00:00+03:00 (rule `weekday_midday`)

> **What to check:** Mall to hospital. Does the Metronit BRT get used?

**The corpus expected:** outcome `route`, `modes_any_of` = ['bus', 'rail', 'funicular'], `max_transfers` = 2, `min_duration_min` = 12, `max_duration_min` = 70

**RESULT: 8 itinerary/itineraries returned.** The first one — the one a
user would be shown — is:

```
    Departs Tue 08 Sep 13:00 (at the requested time)
    Arrives Tue 08 Sep 13:44 -- 44 min, 0 transfer(s)

    13:00-13:11  walk 665 m                    START -> מוריה/ספקטור
    13:11-13:34  bus 136                       מוריה/ספקטור -> ת. רכבת בת גלים
               operator אגד, towards חיפה_רכבת בת גלים
    13:34-13:44  walk 609 m                    ת. רכבת בת גלים -> END
```

<details><summary>Alternatives MOTIS also returned (7 more)</summary>

**Alternative 1**

```
    Departs Tue 08 Sep 13:01 (at the requested time)
    Arrives Tue 08 Sep 13:47 -- 46 min, 1 transfer(s)

    13:01-13:12  walk 665 m                    START -> מוריה/ספקטור
    13:12-13:29  bus 58                        מוריה/ספקטור -> דרך סטלה מאריס
               operator סופרבוס, towards חיפה_רכבת מרכז השמונה
    13:29-13:31  walk 317 m                    דרך סטלה מאריס -> הברון הירש/אלנבי
    13:33-13:39  bus 40                        הברון הירש/אלנבי -> העליה השניה/עפרון
               operator אגד, towards תחנת הרכבל
    13:39-13:47  walk 456 m                    העליה השניה/עפרון -> END
```

**Alternative 2**

```
    Departs Tue 08 Sep 13:03 (3 min after the requested time)
    Arrives Tue 08 Sep 13:50 -- 47 min, 0 transfer(s)

    13:03-13:14  walk 665 m                    START -> מוריה/ספקטור
    13:14-13:39  bus 31                        מוריה/ספקטור -> חיל הים/העלייה השנייה
               operator אגד, towards רכבת בת גלים
    13:39-13:50  walk 638 m                    חיל הים/העלייה השנייה -> END
```

**Alternative 3**

```
    Departs Tue 08 Sep 13:06 (6 min after the requested time)
    Arrives Tue 08 Sep 13:52 -- 46 min, 0 transfer(s)

    13:06-13:17  walk 665 m                    START -> מוריה/ספקטור
    13:17-13:42  bus 37                        מוריה/ספקטור -> ת. רכבת בת גלים
               operator אגד, towards רכבת בת גלים
    13:42-13:52  walk 609 m                    ת. רכבת בת גלים -> END
```

</details>

<sub>Machine checks (structure only — not a quality judgement): structural check (any itinerary): **pass**</sub>

**Verdict:** 

---

## J11 — Tel Aviv Savidor Center → Haifa Center HaShmona

*PRD §7 #3 Tel Aviv → Haifa* · category `intercity-rail`

**Departing:** 2026-09-07T08:00:00+03:00 (rule `weekday_morning`)

> **What to check:** The flagship rail corridor. Cross-check timings against BetterRail.

**The corpus expected:** outcome `route`, `modes_any_of` = ['rail'], `max_transfers` = 1, `min_duration_min` = 45, `max_duration_min` = 130

**RESULT: 6 itinerary/itineraries returned.** The first one — the one a
user would be shown — is:

```
    Departs Mon 07 Sep 08:16 (16 min after the requested time)
    Arrives Mon 07 Sep 09:38 -- 82 min, 1 transfer(s)

    08:16-08:17  walk 27 m                     START -> תל אביב מרכז
    08:17-09:23  regional rail (no line number in feed) תל אביב מרכז -> חיפה מרכז
               operator רכבת ישראל, towards 24
    09:23-09:27  walk distance not reported    חיפה מרכז -> תחנת רכבת חיפה מרכז השמונה
    09:28-09:29  bus 2                         תחנת רכבת חיפה מרכז השמונה -> כרמלית
               operator סופרבוס, towards קרית אתא_יוספטל
    09:29-09:38  walk 564 m                    כרמלית -> END
```

<details><summary>Alternatives MOTIS also returned (5 more)</summary>

**Alternative 1**

```
    Departs Mon 07 Sep 08:27 (27 min after the requested time)
    Arrives Mon 07 Sep 09:52 -- 85 min, 1 transfer(s)

    08:27-08:28  walk 27 m                     START -> תל אביב מרכז
    08:28-09:31  regional rail (no line number in feed) תל אביב מרכז -> בת גלים
               operator רכבת ישראל, towards 156
    09:31-09:33  walk 152 m                    בת גלים -> ת. רכבת בת גלים
    09:34-09:41  bus 36                        ת. רכבת בת גלים -> תחנת רכבת חיפה מרכז השמונה
               operator אגד, towards אוניברסיטה
    09:41-09:52  walk 719 m                    תחנת רכבת חיפה מרכז השמונה -> END
```

**Alternative 2**

```
    Departs Mon 07 Sep 08:46 (46 min after the requested time)
    Arrives Mon 07 Sep 10:08 -- 82 min, 1 transfer(s)

    08:46-08:47  walk 27 m                     START -> תל אביב מרכז
    08:47-09:48  regional rail (no line number in feed) תל אביב מרכז -> בת גלים
               operator רכבת ישראל, towards 404
    09:48-09:50  walk 152 m                    בת גלים -> ת. רכבת בת גלים
    09:50-09:57  bus 18                        ת. רכבת בת גלים -> תחנת רכבת חיפה מרכז השמונה
               operator אגד, towards נווה שאנן
    09:57-10:08  walk 719 m                    תחנת רכבת חיפה מרכז השמונה -> END
```

**Alternative 3**

```
    Departs Mon 07 Sep 08:57 (57 min after the requested time)
    Arrives Mon 07 Sep 10:16 -- 79 min, 1 transfer(s)

    08:57-08:58  walk 27 m                     START -> תל אביב מרכז
    08:58-10:00  regional rail (no line number in feed) תל אביב מרכז -> חיפה מרכז
               operator רכבת ישראל, towards 106
    10:00-10:04  walk distance not reported    חיפה מרכז -> תחנת רכבת חיפה מרכז השמונה
    10:06-10:07  bus 1                         תחנת רכבת חיפה מרכז השמונה -> כרמלית
               operator סופרבוס, towards קרית מוצקין_מרכזית הקריות
    10:07-10:16  walk 564 m                    כרמלית -> END
```

</details>

<sub>Machine checks (structure only — not a quality judgement): structural check (any itinerary): **pass**</sub>

**Verdict:** 

---

## J12 — Tel Aviv Savidor Center → Yitzhak Navon Station

*PRD §7 #4 Tel Aviv → Jerusalem* · category `intercity-rail`

**Departing:** 2026-09-07T08:00:00+03:00 (rule `weekday_morning`)

> **What to check:** Fast line. If it routes by bus, the rail calendar is probably misread.

**The corpus expected:** outcome `route`, `modes_any_of` = ['rail'], `max_transfers` = 1, `min_duration_min` = 30, `max_duration_min` = 110

**RESULT: 5 itinerary/itineraries returned.** The first one — the one a
user would be shown — is:

```
    Departs Mon 07 Sep 08:06 (6 min after the requested time)
    Arrives Mon 07 Sep 08:55 -- 49 min, 0 transfer(s)

    08:06-08:07  walk 27 m                     START -> תל אביב מרכז
    08:07-08:52  regional rail (no line number in feed) תל אביב מרכז -> ירושלים/יצחק נבון
               operator רכבת ישראל, towards 723
    08:52-08:55  walk 184 m                    ירושלים/יצחק נבון -> END
```

<details><summary>Alternatives MOTIS also returned (4 more)</summary>

**Alternative 1**

```
    Departs Mon 07 Sep 08:08 (8 min after the requested time)
    Arrives Mon 07 Sep 08:55 -- 47 min, 1 transfer(s)

    08:08-08:09  walk 27 m                     START -> תל אביב מרכז
    08:09-08:15  regional rail (no line number in feed) תל אביב מרכז -> תל אביב ההגנה
               operator רכבת ישראל, towards 621
    08:15-08:17  walk 0 m                      תל אביב ההגנה -> תל אביב ההגנה
    08:17-08:52  regional rail (no line number in feed) תל אביב ההגנה -> ירושלים/יצחק נבון
               operator רכבת ישראל, towards 723
    08:52-08:55  walk 184 m                    ירושלים/יצחק נבון -> END
```

**Alternative 2**

```
    Departs Mon 07 Sep 08:14 (14 min after the requested time)
    Arrives Mon 07 Sep 09:15 -- 61 min, 0 transfer(s)

    08:14-08:20  walk 403 m                    START -> ת.רכבת תל אביב - סבידור/רציפים B
    08:20-09:10  bus 480                       ת.רכבת תל אביב - סבידור/רציפים B -> ת. מרכזית ירושלים/הורדה
               operator אגד, towards ירושלים_תחנה מרכזית
    09:10-09:15  walk 306 m                    ת. מרכזית ירושלים/הורדה -> END
```

**Alternative 3**

```
    Departs Mon 07 Sep 08:36 (36 min after the requested time)
    Arrives Mon 07 Sep 09:25 -- 49 min, 0 transfer(s)

    08:36-08:37  walk 27 m                     START -> תל אביב מרכז
    08:37-09:22  regional rail (no line number in feed) תל אביב מרכז -> ירושלים/יצחק נבון
               operator רכבת ישראל, towards 725
    09:22-09:25  walk 184 m                    ירושלים/יצחק נבון -> END
```

</details>

<sub>Machine checks (structure only — not a quality judgement): structural check (any itinerary): **pass**</sub>

**Verdict:** 

---

## J13 — Tel Aviv HaShalom → Beersheba Central

category `intercity-rail`

**Departing:** 2026-09-08T13:00:00+03:00 (rule `weekday_midday`)

> **What to check:** Long-distance south. Is the itinerary the direct train or a silly chain?

**The corpus expected:** outcome `route`, `modes_any_of` = ['rail'], `max_transfers` = 1, `min_duration_min` = 60, `max_duration_min` = 180

**RESULT: 6 itinerary/itineraries returned.** The first one — the one a
user would be shown — is:

```
    Departs Tue 08 Sep 13:13 (13 min after the requested time)
    Arrives Tue 08 Sep 14:51 -- 98 min, 0 transfer(s)

    13:13-13:17  walk 270 m                    START -> השלום
    13:17-14:50  regional rail (no line number in feed) השלום -> באר שבע מרכז
               operator רכבת ישראל, towards 33
    14:50-14:51  walk 44 m                     באר שבע מרכז -> END
```

<details><summary>Alternatives MOTIS also returned (5 more)</summary>

**Alternative 1**

```
    Departs Tue 08 Sep 13:38 (38 min after the requested time)
    Arrives Tue 08 Sep 15:20 -- 102 min, 0 transfer(s)

    13:38-13:42  walk 270 m                    START -> השלום
    13:42-15:19  regional rail (no line number in feed) השלום -> באר שבע מרכז
               operator רכבת ישראל, towards 643
    15:19-15:20  walk 44 m                     באר שבע מרכז -> END
```

**Alternative 2**

```
    Departs Tue 08 Sep 13:41 (41 min after the requested time)
    Arrives Tue 08 Sep 15:35 -- 114 min, 2 transfer(s)

    13:41-13:47  walk 299 m                    START -> יגאל אלון/דרך השלום
    13:47-13:57  bus 46                        יגאל אלון/דרך השלום -> ת.רכבת ההגנה
               operator דן, towards בת ים_בית עלמין
    13:58-14:00  walk 371 m                    ת.רכבת ההגנה -> מסוף ההגנה/איסוף
    14:00-14:02  bus 114                       מסוף ההגנה/איסוף -> גשר קיבוץ גלויות
               operator דן, towards מסוף רכבת ההגנה
    14:02-14:04  walk 96 m                     גשר קיבוץ גלויות -> דרך קיבוץ גלויות/כביש 1
    14:04-15:25  bus 370                       דרך קיבוץ גלויות/כביש 1 -> ת.מרכזית באר שבע/הורדה
               operator מטרופולין, towards באר שבע_תחנה מרכזית
    15:25-15:35  walk 657 m                    ת.מרכזית באר שבע/הורדה -> END
```

**Alternative 3**

```
    Departs Tue 08 Sep 13:41 (41 min after the requested time)
    Arrives Tue 08 Sep 15:33 -- 112 min, 3 transfer(s)

    13:41-13:47  walk 299 m                    START -> יגאל אלון/דרך השלום
    13:47-13:57  bus 46                        יגאל אלון/דרך השלום -> ת.רכבת ההגנה
               operator דן, towards בת ים_בית עלמין
    13:58-14:00  walk 371 m                    ת.רכבת ההגנה -> מסוף ההגנה/איסוף
    14:00-14:02  bus 114                       מסוף ההגנה/איסוף -> גשר קיבוץ גלויות
               operator דן, towards מסוף רכבת ההגנה
    14:02-14:04  walk 96 m                     גשר קיבוץ גלויות -> דרך קיבוץ גלויות/כביש 1
    14:04-15:16  bus 370                       דרך קיבוץ גלויות/כביש 1 -> מרכז רפואי סורוקה/אוניברסיטת בן גוריון
               operator מטרופולין, towards באר שבע_תחנה מרכזית
    15:16-15:18  walk 0 m                      מרכז רפואי סורוקה/אוניברסיטת בן גוריון -> מרכז רפואי סורוקה/אוניברסיטת בן גוריון
    15:19-15:26  bus 8                         מרכז רפואי סורוקה/אוניברסיטת בן גוריון -> ת.מרכזית/עירוניים לדרום
               operator דן באר שבע, towards מסוף י"א
    15:26-15:33  walk 490 m                    ת.מרכזית/עירוניים לדרום -> END
```

</details>

<sub>Machine checks (structure only — not a quality judgement): structural check (any itinerary): **pass**</sub>

**Verdict:** 

---

## J14 — Nahariya → Ashdod Ad Halom

category `intercity-rail`

**Departing:** 2026-09-07T08:00:00+03:00 (rule `weekday_morning`)

> **What to check:** End-to-end coastal line. Tests the longest single-mode journey in the country.

**The corpus expected:** outcome `route`, `modes_any_of` = ['rail'], `max_transfers` = 2, `min_duration_min` = 120, `max_duration_min` = 260

**RESULT: 5 itinerary/itineraries returned.** The first one — the one a
user would be shown — is:

```
    Departs Mon 07 Sep 08:02 (at the requested time)
    Arrives Mon 07 Sep 10:53 -- 171 min, 1 transfer(s)

    08:02-08:15  walk 760 m                    START -> נהריה
    08:15-10:04  regional rail (no line number in feed) נהריה -> השלום
               operator רכבת ישראל, towards 157
    10:04-10:08  walk 315 m                    השלום -> קניון עזריאלי/כביש 20
    10:09-10:50  bus 280                       קניון עזריאלי/כביש 20 -> ירושלים
               operator אלקטרה אפיקים, towards אשדוד_תחנה מרכזית
    10:50-10:53  walk 154 m                    ירושלים -> END
```

<details><summary>Alternatives MOTIS also returned (4 more)</summary>

**Alternative 1**

```
    Departs Mon 07 Sep 08:03 (3 min after the requested time)
    Arrives Mon 07 Sep 10:53 -- 170 min, 2 transfer(s)

    08:03-08:10  walk 410 m                    START -> שדרות הגעתון/עזריאל ריציק
    08:10-08:10  bus 16                        שדרות הגעתון/עזריאל ריציק -> תחנה מרכזית נהריה/שדרות הגעתון
               operator נתיב אקספרס, towards רגבה_מרכז מסחרי
    08:11-08:15  walk distance not reported    תחנה מרכזית נהריה/שדרות הגעתון -> נהריה
    08:15-10:04  regional rail (no line number in feed) נהריה -> השלום
               operator רכבת ישראל, towards 157
    10:04-10:08  walk 315 m                    השלום -> קניון עזריאלי/כביש 20
    10:09-10:50  bus 280                       קניון עזריאלי/כביש 20 -> ירושלים
               operator אלקטרה אפיקים, towards אשדוד_תחנה מרכזית
    10:50-10:53  walk 154 m                    ירושלים -> END
```

**Alternative 2**

```
    Departs Mon 07 Sep 08:15 (15 min after the requested time)
    Arrives Mon 07 Sep 11:23 -- 188 min, 2 transfer(s)

    08:15-08:28  walk 760 m                    START -> נהריה
    08:28-10:15  regional rail (no line number in feed) נהריה -> השלום
               operator רכבת ישראל, towards 27
    10:26-10:28  walk 329 m                    השלום -> ת. רכבת השלום
    10:28-10:29  bus 274                       ת. רכבת השלום -> קניון עזריאלי/דרך מנחם בגין
               operator אגד, towards תל אביב יפו_אוניברסיטת ת"א
    10:29-10:31  walk 324 m                    קניון עזריאלי/דרך מנחם בגין -> קניון עזריאלי/דרך מנחם בגין
    10:33-11:20  bus 281                       קניון עזריאלי/דרך מנחם בגין -> ירושלים
               operator אלקטרה אפיקים, towards אשדוד_רובע ט"ו
    11:20-11:23  walk 154 m                    ירושלים -> END
```

**Alternative 3**

```
    Departs Mon 07 Sep 08:35 (35 min after the requested time)
    Arrives Mon 07 Sep 11:48 -- 193 min, 1 transfer(s)

    08:35-08:48  walk 760 m                    START -> נהריה
    08:48-10:34  regional rail (no line number in feed) נהריה -> השלום
               operator רכבת ישראל, towards 109
    10:34-10:38  walk 315 m                    השלום -> קניון עזריאלי/כביש 20
    11:04-11:45  bus 280                       קניון עזריאלי/כביש 20 -> ירושלים
               operator אלקטרה אפיקים, towards אשדוד_תחנה מרכזית
    11:45-11:48  walk 154 m                    ירושלים -> END
```

</details>

<sub>Machine checks (structure only — not a quality judgement): structural check (any itinerary): **pass**</sub>

**Verdict:** 

---

## J15 — Weizmann Institute, Rehovot → Haifa Center HaShmona

*PRD §7 #5 bus → train* · category `bus-to-rail`

**Departing:** 2026-09-07T08:00:00+03:00 (rule `weekday_morning`)

> **What to check:** Must contain a bus leg then a rail leg. Verify the interchange is real.

**The corpus expected:** outcome `route`, `modes_all_of` = ['bus', 'rail'], `max_transfers` = 3, `min_duration_min` = 75, `max_duration_min` = 220

**RESULT: 5 itinerary/itineraries returned.** The first one — the one a
user would be shown — is:

```
    Departs Mon 07 Sep 08:00 (at the requested time)
    Arrives Mon 07 Sep 10:16 -- 136 min, 3 transfer(s)

    08:00-08:11  walk 591 m                    START -> מכון ויצמן
    08:11-08:45  bus 277                       מכון ויצמן -> ת.רק"ל יהודית/דרך מנחם בגין
               operator אגד, towards תל אביב יפו_מסוף רדינג
    08:45-08:47  walk 0 m                      ת.רק"ל יהודית/דרך מנחם בגין -> ת.רק"ל יהודית/דרך מנחם בגין
    08:47-08:50  bus 23                        ת.רק"ל יהודית/דרך מנחם בגין -> ת. רכבת השלום
               operator דן, towards גבעתיים_כורזין
    08:51-08:53  walk 226 m                    ת. רכבת השלום -> השלום
    08:53-10:00  regional rail (no line number in feed) השלום -> חיפה מרכז
               operator רכבת ישראל, towards 106
    10:00-10:04  walk distance not reported    חיפה מרכז -> תחנת רכבת חיפה מרכז השמונה
    10:06-10:07  bus 1                         תחנת רכבת חיפה מרכז השמונה -> כרמלית
               operator סופרבוס, towards קרית מוצקין_מרכזית הקריות
    10:07-10:16  walk 564 m                    כרמלית -> END
```

<details><summary>Alternatives MOTIS also returned (4 more)</summary>

**Alternative 1**

```
    Departs Mon 07 Sep 08:21 (21 min after the requested time)
    Arrives Mon 07 Sep 10:40 -- 139 min, 2 transfer(s)

    08:21-08:34  walk 876 m                    START -> רחובות
    08:34-08:43  regional rail (no line number in feed) רחובות -> לוד
               operator רכבת ישראל, towards 956
    08:51-08:53  walk 0 m                      לוד -> לוד
    08:53-10:19  regional rail (no line number in feed) לוד -> בת גלים
               operator רכבת ישראל, towards 26
    10:19-10:21  walk 152 m                    בת גלים -> ת. רכבת בת גלים
    10:22-10:29  bus 18                        ת. רכבת בת גלים -> תחנת רכבת חיפה מרכז השמונה
               operator אגד, towards נווה שאנן
    10:29-10:40  walk 719 m                    תחנת רכבת חיפה מרכז השמונה -> END
```

**Alternative 2**

```
    Departs Mon 07 Sep 08:21 (21 min after the requested time)
    Arrives Mon 07 Sep 10:38 -- 137 min, 3 transfer(s)

    08:21-08:34  walk 876 m                    START -> רחובות
    08:34-08:43  regional rail (no line number in feed) רחובות -> לוד
               operator רכבת ישראל, towards 956
    08:51-08:53  walk 0 m                      לוד -> לוד
    08:53-10:19  regional rail (no line number in feed) לוד -> בת גלים
               operator רכבת ישראל, towards 26
    10:20-10:22  walk 152 m                    בת גלים -> ת. רכבת בת גלים
    10:22-10:27  bus 28                        ת. רכבת בת גלים -> המגינים/בן גוריון
               operator אגד, towards גרנד קניון
    10:27-10:29  walk 0 m                      המגינים/בן גוריון -> המגינים/בן גוריון
    10:29-10:31  bus 24                        המגינים/בן גוריון -> המגינים/ככר ההגנה
               operator אגד, towards אוניברסיטה
    10:31-10:38  walk 438 m                    המגינים/ככר ההגנה -> END
```

**Alternative 3**

```
    Departs Mon 07 Sep 08:25 (25 min after the requested time)
    Arrives Mon 07 Sep 10:50 -- 145 min, 2 transfer(s)

    08:25-08:36  walk 591 m                    START -> מכון ויצמן
    08:36-09:18  bus 274                       מכון ויצמן -> ת. רכבת השלום
               operator אגד, towards תל אביב יפו_אוניברסיטת ת"א
    09:21-09:23  walk 329 m                    ת. רכבת השלום -> השלום
    09:23-10:35  regional rail (no line number in feed) השלום -> חיפה מרכז
               operator רכבת ישראל, towards 158
    10:35-10:39  walk distance not reported    חיפה מרכז -> תחנת רכבת חיפה מרכז השמונה
    10:40-10:41  bus 2                         תחנת רכבת חיפה מרכז השמונה -> כרמלית
               operator סופרבוס, towards קרית אתא_יוספטל
    10:41-10:50  walk 564 m                    כרמלית -> END
```

</details>

<sub>Machine checks (structure only — not a quality judgement): structural check (any itinerary): **pass**</sub>

**Verdict:** 

---

## J16 — Tel Aviv Savidor Center → Technion

*PRD §7 #6 train → bus* · category `rail-to-bus`

**Departing:** 2026-09-07T08:00:00+03:00 (rule `weekday_morning`)

> **What to check:** The PRD §39 demo journey in reverse shape. Rail then bus up the Carmel.

**The corpus expected:** outcome `route`, `modes_all_of` = ['rail', 'bus'], `max_transfers` = 3, `min_duration_min` = 70, `max_duration_min` = 200

**RESULT: 5 itinerary/itineraries returned.** The first one — the one a
user would be shown — is:

```
    Departs Mon 07 Sep 08:27 (27 min after the requested time)
    Arrives Mon 07 Sep 09:52 -- 85 min, 1 transfer(s)

    08:27-08:28  walk 27 m                     START -> תל אביב מרכז
    08:28-09:24  regional rail (no line number in feed) תל אביב מרכז -> חוף הכרמל
               operator רכבת ישראל, towards 156
    09:24-09:26  walk 189 m                    חוף הכרמל -> ת. רכבת חוף הכרמל
    09:33-09:47  bus 1                         ת. רכבת חוף הכרמל -> טכניון/מעונות העמים
               operator אגד, towards טכניון
    09:47-09:52  walk 275 m                    טכניון/מעונות העמים -> END
```

<details><summary>Alternatives MOTIS also returned (4 more)</summary>

**Alternative 1**

```
    Departs Mon 07 Sep 08:46 (46 min after the requested time)
    Arrives Mon 07 Sep 10:30 -- 104 min, 2 transfer(s)

    08:46-08:47  walk 27 m                     START -> תל אביב מרכז
    08:47-09:48  regional rail (no line number in feed) תל אביב מרכז -> בת גלים
               operator רכבת ישראל, towards 404
    09:50-09:52  walk 152 m                    בת גלים -> ת. רכבת בת גלים
    09:52-10:05  bus 28                        ת. רכבת בת גלים -> ארלוזורוב/בלפור
               operator אגד, towards גרנד קניון
    10:05-10:07  walk 56 m                     ארלוזורוב/בלפור -> ארלוזורוב/בלפור
    10:10-10:25  bus 76                        ארלוזורוב/בלפור -> טכניון/מעונות העמים
               operator אגד, towards יגור_מסוף יגור
    10:25-10:30  walk 275 m                    טכניון/מעונות העמים -> END
```

**Alternative 2**

```
    Departs Mon 07 Sep 08:57 (57 min after the requested time)
    Arrives Mon 07 Sep 10:35 -- 98 min, 1 transfer(s)

    08:57-08:58  walk 27 m                     START -> תל אביב מרכז
    08:58-10:00  regional rail (no line number in feed) תל אביב מרכז -> חיפה מרכז
               operator רכבת ישראל, towards 106
    10:00-10:04  walk distance not reported    חיפה מרכז -> תחנת רכבת חיפה מרכז השמונה
    10:06-10:30  bus 17                        תחנת רכבת חיפה מרכז השמונה -> טכניון/מעונות העמים
               operator אגד, towards טכניון
    10:30-10:35  walk 275 m                    טכניון/מעונות העמים -> END
```

**Alternative 3**

```
    Departs Mon 07 Sep 09:27 (87 min after the requested time)
    Arrives Mon 07 Sep 10:52 -- 85 min, 1 transfer(s)

    09:27-09:28  walk 27 m                     START -> תל אביב מרכז
    09:28-10:24  regional rail (no line number in feed) תל אביב מרכז -> חוף הכרמל
               operator רכבת ישראל, towards 158
    10:24-10:26  walk 189 m                    חוף הכרמל -> ת. רכבת חוף הכרמל
    10:33-10:47  bus 1                         ת. רכבת חוף הכרמל -> טכניון/מעונות העמים
               operator אגד, towards טכניון
    10:47-10:52  walk 275 m                    טכניון/מעונות העמים -> END
```

</details>

<sub>Machine checks (structure only — not a quality judgement): structural check (any itinerary): **pass**</sub>

**Verdict:** 

---

## J17 — Modi'in Center → Ben Gurion Airport T3

category `bus-to-rail`

**Departing:** 2026-09-07T08:00:00+03:00 (rule `weekday_morning`)

> **What to check:** Airport access. A wrong answer here is very visible to a real user.

**The corpus expected:** outcome `route`, `modes_any_of` = ['rail', 'bus'], `max_transfers` = 2, `min_duration_min` = 15, `max_duration_min` = 90

**RESULT: no route returned.**

Probes run against this case (see `poc/routing/no-route-diagnosis.json`):

| variation | result |
| --- | --- |
| J17 as-corpus — defaults (as the corpus run) | no route |
| J17 as-corpus — searchWindow 2 h | no route |
| J17 as-corpus — searchWindow 6 h | no route |
| J17 as-corpus — walk up to 30 min each end | no route |
| J17 as-corpus — searchWindow 6 h + 30 min walk | no route |
| J17 to the real T3 interchange — defaults (as the corpus run) | 7 itineraries, 96 min, 1 transfers |
| J17 to the real T3 interchange — searchWindow 2 h | 24 itineraries, 96 min, 1 transfers |
| J17 to the real T3 interchange — searchWindow 6 h | 56 itineraries, 96 min, 1 transfers |
| J17 to the real T3 interchange — walk up to 30 min each end | 8 itineraries, 96 min, 1 transfers |
| J17 to the real T3 interchange — searchWindow 6 h + 30 min walk | 52 itineraries, 96 min, 1 transfers |

<sub>Machine checks (structure only — not a quality judgement): structural check (any itinerary): **fail** · no itineraries returned but the case expects outcome=route</sub>

**Verdict:** 

---

## J18 — Beersheba North University → Bar-Ilan University

category `rail-to-bus`

**Departing:** 2026-09-07T08:00:00+03:00 (rule `weekday_morning`)

> **What to check:** Campus to campus, two operators, at least one interchange.

**The corpus expected:** outcome `route`, `modes_all_of` = ['rail', 'bus'], `max_transfers` = 3, `min_duration_min` = 75, `max_duration_min` = 230

**RESULT: 6 itinerary/itineraries returned.** The first one — the one a
user would be shown — is:

```
    Departs Mon 07 Sep 08:00 (at the requested time)
    Arrives Mon 07 Sep 10:04 -- 124 min, 3 transfer(s)

    08:00-08:04  walk 215 m                    START -> מרפאות חוץ סורוקה/אוניברסיטת בן גוריון
    08:04-08:05  bus 5                         מרפאות חוץ סורוקה/אוניברסיטת בן גוריון -> מרכז רפואי סורוקה/אוניברסיטת בן גוריון
               operator דן באר שבע, towards מסוף חצרים
    08:05-08:07  walk 290 m                    מרכז רפואי סורוקה/אוניברסיטת בן גוריון -> מרכז רפואי סורוקה/אוניברסיטת בן גוריון
    08:07-09:16  bus 370                       מרכז רפואי סורוקה/אוניברסיטת בן גוריון -> מחלף לה גווארדייה
               operator מטרופולין, towards תל אביב יפו_תחנה מרכזית
    09:24-09:26  walk 126 m                    מחלף לה גווארדייה -> מחלף לה גווארדייה
    09:26-09:44  bus 31                        מחלף לה גווארדייה -> הירדן/ אלוף שדה
               operator דן, towards בני ברק_בית עלמין
    09:44-09:46  walk 149 m                    הירדן/ אלוף שדה -> הירדן/אלוף שדה
    09:47-09:56  bus 32                        הירדן/אלוף שדה -> מרכז וואהל/מקס ואנה ווב
               operator דן, towards גבעת שמואל_הרב שלמה גורן
    09:56-10:04  walk 452 m                    מרכז וואהל/מקס ואנה ווב -> END
```

<details><summary>Alternatives MOTIS also returned (5 more)</summary>

**Alternative 1**

```
    Departs Mon 07 Sep 08:00 (at the requested time)
    Arrives Mon 07 Sep 09:56 -- 116 min, 4 transfer(s)

    08:00-08:04  walk 215 m                    START -> מרפאות חוץ סורוקה/אוניברסיטת בן גוריון
    08:04-08:05  bus 5                         מרפאות חוץ סורוקה/אוניברסיטת בן גוריון -> מרכז רפואי סורוקה/אוניברסיטת בן גוריון
               operator דן באר שבע, towards מסוף חצרים
    08:05-08:07  walk 290 m                    מרכז רפואי סורוקה/אוניברסיטת בן גוריון -> מרכז רפואי סורוקה/אוניברסיטת בן גוריון
    08:07-09:16  bus 370                       מרכז רפואי סורוקה/אוניברסיטת בן גוריון -> מחלף לה גווארדייה
               operator מטרופולין, towards תל אביב יפו_תחנה מרכזית
    09:17-09:19  walk 126 m                    מחלף לה גווארדייה -> מחלף לה גווארדייה
    09:19-09:25  bus 2                         מחלף לה גווארדייה -> שכונת הארגזים/לח"י
               operator דן, towards הארגזים
    09:27-09:29  walk 0 m                      שכונת הארגזים/לח"י -> שכונת הארגזים/לח"י
    09:29-09:39  bus 41                        שכונת הארגזים/לח"י -> עמק האלה/דרך שיבא
               operator דן, towards פתח תקווה_מסוף משה ארנס
    09:39-09:41  walk 0 m                      עמק האלה/דרך שיבא -> עמק האלה/דרך שיבא
    09:41-09:48  bus 48                        עמק האלה/דרך שיבא -> מרכז וואהל/מקס ואנה ווב
               operator מטרופולין, towards פתח תקווה_מ.רפואי שניידר
    09:48-09:56  walk 452 m                    מרכז וואהל/מקס ואנה ווב -> END
```

**Alternative 2**

```
    Departs Mon 07 Sep 08:17 (17 min after the requested time)
    Arrives Mon 07 Sep 10:11 -- 114 min, 1 transfer(s)

    08:17-08:27  walk 608 m                    START -> מרכז רפואי סורוקה/אוניברסיטת בן גוריון
    08:27-09:47  bus 669                       מרכז רפואי סורוקה/אוניברסיטת בן גוריון -> מחלף מסובים
               operator מטרופולין, towards רעננה_מסוף אוטובוסים
    09:47-09:49  walk 0 m                      מחלף מסובים -> מחלף מסובים
    09:57-10:03  bus 145                       מחלף מסובים -> מרכז וואהל/מקס ואנה ווב
               operator סופרבוס, towards פתח תקווה_רכבת קרית אריה
    10:03-10:11  walk 452 m                    מרכז וואהל/מקס ואנה ווב -> END
```

**Alternative 3**

```
    Departs Mon 07 Sep 08:20 (20 min after the requested time)
    Arrives Mon 07 Sep 10:11 -- 111 min, 2 transfer(s)

    08:20-08:24  walk 215 m                    START -> מרפאות חוץ סורוקה/אוניברסיטת בן גוריון
    08:24-08:25  bus 4                         מרפאות חוץ סורוקה/אוניברסיטת בן גוריון -> מרכז רפואי סורוקה/אוניברסיטת בן גוריון
               operator דן באר שבע, towards אצטדיון טרנר
    08:25-08:27  walk 290 m                    מרכז רפואי סורוקה/אוניברסיטת בן גוריון -> מרכז רפואי סורוקה/אוניברסיטת בן גוריון
    08:27-09:47  bus 669                       מרכז רפואי סורוקה/אוניברסיטת בן גוריון -> מחלף מסובים
               operator מטרופולין, towards רעננה_מסוף אוטובוסים
    09:47-09:49  walk 0 m                      מחלף מסובים -> מחלף מסובים
    09:57-10:03  bus 145                       מחלף מסובים -> מרכז וואהל/מקס ואנה ווב
               operator סופרבוס, towards פתח תקווה_רכבת קרית אריה
    10:03-10:11  walk 452 m                    מרכז וואהל/מקס ואנה ווב -> END
```

</details>

<sub>Machine checks (structure only — not a quality judgement): structural check (any itinerary): **pass** · structural check (the itinerary shown): **fail** · itinerary 0 (the one a user sees) does not satisfy the case; itinerary 4 does. This is a ranking question -- flag for H3. · first itinerary missed: modes ['bus'] missing modes_all_of entries ['rail']</sub>

**Verdict:** 

---

## J19 — Herzliya Station → Beilinson Hospital, Petah Tikva

*PRD §7 #7 at least one transfer* · category `with-transfer`

**Departing:** 2026-09-07T08:00:00+03:00 (rule `weekday_morning`)

> **What to check:** Must transfer. Is the transfer window realistic, not a 2-minute cross-platform miracle?

**The corpus expected:** outcome `route`, `min_transfers` = 1, `max_transfers` = 3, `min_duration_min` = 20, `max_duration_min` = 100

**RESULT: 5 itinerary/itineraries returned.** The first one — the one a
user would be shown — is:

```
    Departs Mon 07 Sep 08:03 (3 min after the requested time)
    Arrives Mon 07 Sep 09:14 -- 71 min, 1 transfer(s)

    08:03-08:07  walk 184 m                    START -> גלגלי הפלדה/יוחנן הסנדלר
    08:07-08:36  bus 91                        גלגלי הפלדה/יוחנן הסנדלר -> דרך בר לב/דרך משה דיין
               operator מטרופולין, towards תל אביב יפו_מסוף הטייסים
    08:36-08:38  walk 0 m                      דרך בר לב/דרך משה דיין -> דרך בר לב/דרך משה דיין
    08:39-09:07  bus 41                        דרך בר לב/דרך משה דיין -> בריכת נווה עוז/דרך יצחק רבין
               operator דן, towards פתח תקווה_מסוף משה ארנס
    09:07-09:14  walk 438 m                    בריכת נווה עוז/דרך יצחק רבין -> END
```

<details><summary>Alternatives MOTIS also returned (4 more)</summary>

**Alternative 1**

```
    Departs Mon 07 Sep 08:03 (3 min after the requested time)
    Arrives Mon 07 Sep 08:57 -- 54 min, 2 transfer(s)

    08:03-08:07  walk 184 m                    START -> גלגלי הפלדה/יוחנן הסנדלר
    08:07-08:24  bus 91                        גלגלי הפלדה/יוחנן הסנדלר -> ת.רק"ל שאול המלך/דרך מנחם בגין
               operator מטרופולין, towards תל אביב יפו_מסוף הטייסים
    08:27-08:29  walk 126 m                    ת.רק"ל שאול המלך/דרך מנחם בגין -> שאול המלך
    08:29-08:45  tram 1                        שאול המלך -> שחם
               operator תבל, towards פתח תקווה_ת. מרכזית פתח תקווה
    08:45-08:47  walk 124 m                    שחם -> ת.רק"ל שחם/דרך יצחק רבין
    08:48-08:50  bus 75                        ת.רק"ל שחם/דרך יצחק רבין -> דרך יצחק רבין/דגניה
               operator מטרופולין, towards גני תקווה_מרכז גני תקווה
    08:50-08:57  walk 444 m                    דרך יצחק רבין/דגניה -> END
```

**Alternative 2**

```
    Departs Mon 07 Sep 08:06 (6 min after the requested time)
    Arrives Mon 07 Sep 09:01 -- 55 min, 3 transfer(s)

    08:06-08:10  walk 184 m                    START -> גלגלי הפלדה/יוחנן הסנדלר
    08:10-08:14  bus 90                        גלגלי הפלדה/יוחנן הסנדלר -> סינמה סיטי/כביש 2
               operator מטרופולין, towards תל אביב יפו_מסוף כרמלית
    08:16-08:18  walk 0 m                      סינמה סיטי/כביש 2 -> סינמה סיטי/כביש 2
    08:18-08:31  bus 347                       סינמה סיטי/כביש 2 -> ת.רק"ל שאול המלך/דרך מנחם בגין
               operator מטרופולין, towards תל אביב יפו_תחנה מרכזית
    08:32-08:34  walk 126 m                    ת.רק"ל שאול המלך/דרך מנחם בגין -> שאול המלך
    08:34-08:50  tram 1                        שאול המלך -> שחם
               operator תבל, towards פתח תקווה_ת. מרכזית פתח תקווה
    08:50-08:52  walk 124 m                    שחם -> ת.רק"ל שחם/דרך יצחק רבין
    08:53-08:54  bus 143                       ת.רק"ל שחם/דרך יצחק רבין -> דרך יצחק רבין/דגניה
               operator סופרבוס, towards חולון_מוזיאון אגד
    08:54-09:01  walk 444 m                    דרך יצחק רבין/דגניה -> END
```

**Alternative 3**

```
    Departs Mon 07 Sep 08:08 (8 min after the requested time)
    Arrives Mon 07 Sep 09:08 -- 60 min, 2 transfer(s)

    08:08-08:16  walk 521 m                    START -> צומת הרצליה
    08:16-08:35  bus 606                       צומת הרצליה -> ת.רק"ל יהודית/דרך מנחם בגין
               operator מטרופולין, towards תל אביב יפו_תחנה מרכזית
    08:36-08:38  walk 141 m                    ת.רק"ל יהודית/דרך מנחם בגין -> יהודית
    08:38-08:56  tram 1                        יהודית -> שחם
               operator תבל, towards פתח תקווה_ת. מרכזית פתח תקווה
    08:56-08:58  walk 124 m                    שחם -> ת.רק"ל שחם/דרך יצחק רבין
    08:59-09:01  bus 41                        ת.רק"ל שחם/דרך יצחק רבין -> דרך יצחק רבין/דגניה
               operator דן, towards תל אביב יפו_מסוף הלוחמים
    09:01-09:08  walk 444 m                    דרך יצחק רבין/דגניה -> END
```

</details>

<sub>Machine checks (structure only — not a quality judgement): structural check (any itinerary): **pass**</sub>

**Verdict:** 

---

## J20 — Netanya Station → Mahane Yehuda Market

category `with-transfer`

**Departing:** 2026-09-08T13:00:00+03:00 (rule `weekday_midday`)

> **What to check:** Coastal rail then Jerusalem light rail. Checks cross-operator chaining.

**The corpus expected:** outcome `route`, `min_transfers` = 1, `max_transfers` = 3, `min_duration_min` = 60, `max_duration_min` = 200

**RESULT: 7 itinerary/itineraries returned.** The first one — the one a
user would be shown — is:

```
    Departs Tue 08 Sep 13:03 (3 min after the requested time)
    Arrives Tue 08 Sep 15:13 -- 130 min, 2 transfer(s)

    13:03-13:18  walk 889 m                    START -> בית ספר טשרניחובסקי/בן צבי
    13:18-13:51  bus 611                       בית ספר טשרניחובסקי/בן צבי -> ת. רכבת תל אביב - סבידור/דרך נמיר
               operator מטרופולין, towards תל אביב יפו_תחנה מרכזית
    14:00-14:05  walk 297 m                    ת. רכבת תל אביב - סבידור/דרך נמיר -> ת.רכבת תל אביב - סבידור/רציפים B
    14:05-14:56  bus 490                       ת.רכבת תל אביב - סבידור/רציפים B -> הרצוג/ניות
               operator אגד, towards ירושלים_אזור תעשיה תלפיות
    14:56-14:58  walk 244 m                    הרצוג/ניות -> הרצוג/רסקו
    14:58-15:03  bus 509                       הרצוג/רסקו -> שדרות יצחק בן צבי/בצלאל
               operator סופרבוס, towards הר חוצבים
    15:03-15:13  walk 633 m                    שדרות יצחק בן צבי/בצלאל -> END
```

<details><summary>Alternatives MOTIS also returned (6 more)</summary>

**Alternative 1**

```
    Departs Tue 08 Sep 13:03 (3 min after the requested time)
    Arrives Tue 08 Sep 15:03 -- 120 min, 3 transfer(s)

    13:03-13:18  walk 889 m                    START -> בית ספר טשרניחובסקי/בן צבי
    13:18-13:37  bus 611                       בית ספר טשרניחובסקי/בן צבי -> מחלף הסירה לדרום
               operator מטרופולין, towards תל אביב יפו_תחנה מרכזית
    13:37-13:39  walk 0 m                      מחלף הסירה לדרום -> מחלף הסירה לדרום
    13:39-13:56  bus 91                        מחלף הסירה לדרום -> ת. רכבת השלום
               operator מטרופולין, towards תל אביב יפו_מסוף הטייסים
    14:09-14:11  walk 226 m                    ת. רכבת השלום -> השלום
    14:11-14:52  regional rail (no line number in feed) השלום -> ירושלים/יצחק נבון
               operator רכבת ישראל, towards 747
    14:52-14:54  walk 166 m                    ירושלים/יצחק נבון -> ת. מרכזית ירושלים/יפו
    14:55-14:59  bus 75                        ת. מרכזית ירושלים/יפו -> שוק מחנה יהודה/אגריפס
               operator סופרבוס, towards חומת שמואל
    14:59-15:03  walk 230 m                    שוק מחנה יהודה/אגריפס -> END
```

**Alternative 2**

```
    Departs Tue 08 Sep 13:04 (4 min after the requested time)
    Arrives Tue 08 Sep 15:13 -- 129 min, 3 transfer(s)

    13:04-13:11  walk 371 m                    START -> האר"י/הרב חרל"פ
    13:11-13:14  bus 72                        האר"י/הרב חרל"פ -> שד. בן צבי/היהלומן אברהם
               operator אקסטרה, towards תחנת הרכבת
    13:14-13:16  walk 137 m                    שד. בן צבי/היהלומן אברהם -> בן צבי/הגר"א
    13:16-13:51  bus 611                       בן צבי/הגר"א -> ת. רכבת תל אביב - סבידור/דרך נמיר
               operator מטרופולין, towards תל אביב יפו_תחנה מרכזית
    14:00-14:05  walk 297 m                    ת. רכבת תל אביב - סבידור/דרך נמיר -> ת.רכבת תל אביב - סבידור/רציפים B
    14:05-14:56  bus 490                       ת.רכבת תל אביב - סבידור/רציפים B -> הרצוג/ניות
               operator אגד, towards ירושלים_אזור תעשיה תלפיות
    14:56-14:58  walk 244 m                    הרצוג/ניות -> הרצוג/רסקו
    14:58-15:03  bus 509                       הרצוג/רסקו -> שדרות יצחק בן צבי/בצלאל
               operator סופרבוס, towards הר חוצבים
    15:03-15:13  walk 633 m                    שדרות יצחק בן צבי/בצלאל -> END
```

**Alternative 3**

```
    Departs Tue 08 Sep 13:04 (4 min after the requested time)
    Arrives Tue 08 Sep 15:03 -- 119 min, 4 transfer(s)

    13:04-13:11  walk 371 m                    START -> האר"י/הרב חרל"פ
    13:11-13:14  bus 72                        האר"י/הרב חרל"פ -> שד. בן צבי/היהלומן אברהם
               operator אקסטרה, towards תחנת הרכבת
    13:14-13:16  walk 137 m                    שד. בן צבי/היהלומן אברהם -> בן צבי/הגר"א
    13:16-13:37  bus 611                       בן צבי/הגר"א -> מחלף הסירה לדרום
               operator מטרופולין, towards תל אביב יפו_תחנה מרכזית
    13:37-13:39  walk 0 m                      מחלף הסירה לדרום -> מחלף הסירה לדרום
    13:39-13:56  bus 91                        מחלף הסירה לדרום -> ת. רכבת השלום
               operator מטרופולין, towards תל אביב יפו_מסוף הטייסים
    14:09-14:11  walk 226 m                    ת. רכבת השלום -> השלום
    14:11-14:52  regional rail (no line number in feed) השלום -> ירושלים/יצחק נבון
               operator רכבת ישראל, towards 747
    14:52-14:54  walk 166 m                    ירושלים/יצחק נבון -> ת. מרכזית ירושלים/יפו
    14:55-14:59  bus 75                        ת. מרכזית ירושלים/יפו -> שוק מחנה יהודה/אגריפס
               operator סופרבוס, towards חומת שמואל
    14:59-15:03  walk 230 m                    שוק מחנה יהודה/אגריפס -> END
```

</details>

<sub>Machine checks (structure only — not a quality judgement): structural check (any itinerary): **pass**</sub>

**Verdict:** 

---

## J21 — Tel Aviv Savidor Center → Ben Gurion Airport T3

*PRD §7 #8 late night* · category `late-night`

**Departing:** 2026-09-08T23:40:00+03:00 (rule `late_night`)

> **What to check:** Airport rail runs deep into the night. Does the engine know that?

**The corpus expected:** outcome `route`, `modes_any_of` = ['rail', 'bus'], `max_transfers` = 2, `min_duration_min` = 10, `max_duration_min` = 120

**RESULT: no route returned.**

Probes run against this case (see `poc/routing/no-route-diagnosis.json`):

| variation | result |
| --- | --- |
| J21 as-corpus — defaults (as the corpus run) | no route |
| J21 as-corpus — searchWindow 2 h | no route |
| J21 as-corpus — searchWindow 6 h | no route |
| J21 as-corpus — walk up to 30 min each end | no route |
| J21 as-corpus — searchWindow 6 h + 30 min walk | no route |
| J21 to the real T3 interchange — defaults (as the corpus run) | 5 itineraries, 45 min, 0 transfers |
| J21 to the real T3 interchange — searchWindow 2 h | 5 itineraries, 45 min, 0 transfers |
| J21 to the real T3 interchange — searchWindow 6 h | 17 itineraries, 45 min, 0 transfers |
| J21 to the real T3 interchange — walk up to 30 min each end | 5 itineraries, 65 min, 1 transfers |
| J21 to the real T3 interchange — searchWindow 6 h + 30 min walk | 18 itineraries, 65 min, 1 transfers |

<sub>Machine checks (structure only — not a quality judgement): structural check (any itinerary): **fail** · no itineraries returned but the case expects outcome=route</sub>

**Verdict:** 

---

## J22 — Dizengoff Center → Ramat Gan Bursa

*PRD §7 #9 crossing a service-day boundary* · category `service-day-boundary`

**Departing:** 2026-09-09T02:30:00+03:00 (rule `after_midnight`)

> **What to check:** THE GTFS trap: trips after midnight belong to the previous service day with times like 25:30:00. Either a valid night route or a clean no-route is acceptable. A crash, an empty result with no explanation, or a route departing 20 hours later is a FAIL.

**The corpus expected:** outcome `either`, `min_duration_min` = 5, `max_duration_min` = 180

**RESULT: 5 itinerary/itineraries returned.** The first one — the one a
user would be shown — is:

```
    Departs Wed 09 Sep 02:39 (9 min after the requested time)
    Arrives Wed 09 Sep 04:19 -- 100 min, 1 transfer(s)

    02:39-02:42  walk 135 m                    START -> דיזנגוף סנטר/דיזנגוף
    02:42-03:23  bus 445                       דיזנגוף סנטר/דיזנגוף -> נתב"ג טרמינל 3/קומת תח"צ
               operator מטרופולין, towards נמל תעופה בן גוריון_טרמינל 3
    03:23-03:25  walk 616 m                    נתב"ג טרמינל 3/קומת תח"צ -> נתב"ג
    03:53-04:07  regional rail (no line number in feed) נתב"ג -> תל אביב מרכז
               operator רכבת ישראל, towards 9706
    04:07-04:19  walk 767 m                    תל אביב מרכז -> END
```

<details><summary>Alternatives MOTIS also returned (4 more)</summary>

**Alternative 1**

```
    Departs Wed 09 Sep 04:57 (147 min after the requested time)
    Arrives Wed 09 Sep 05:38 -- 41 min, 1 transfer(s)

    04:57-05:00  walk 135 m                    START -> דיזנגוף סנטר/דיזנגוף
    05:00-05:10  bus 172                       דיזנגוף סנטר/דיזנגוף -> שוקן/דרך שלמה
               operator דן, towards חולון_מסוף אזור תעשייה
    05:10-05:12  walk 118 m                    שוקן/דרך שלמה -> דרך שלמה/שוקן
    05:18-05:34  bus 42                        דרך שלמה/שוקן -> ת.רק"ל אבא הלל
               operator דן, towards תל אביב יפו_קריית עתידים
    05:34-05:38  walk 250 m                    ת.רק"ל אבא הלל -> END
```

**Alternative 2**

```
    Departs Wed 09 Sep 04:57 (147 min after the requested time)
    Arrives Wed 09 Sep 05:23 -- 26 min, 2 transfer(s)

    04:57-05:00  walk 135 m                    START -> דיזנגוף סנטר/דיזנגוף
    05:00-05:03  bus 172                       דיזנגוף סנטר/דיזנגוף -> שד' רוטשילד/שיינקין
               operator דן, towards חולון_מסוף אזור תעשייה
    05:05-05:07  walk 112 m                    שד' רוטשילד/שיינקין -> שד' רוטשילד/שיינקין
    05:07-05:11  bus 23                        שד' רוטשילד/שיינקין -> ת.רק"ל יהודית/דרך מנחם בגין
               operator דן, towards גבעתיים_כורזין
    05:11-05:13  walk 0 m                      ת.רק"ל יהודית/דרך מנחם בגין -> ת.רק"ל יהודית/דרך מנחם בגין
    05:13-05:19  bus 50                        ת.רק"ל יהודית/דרך מנחם בגין -> ת.רק"ל אבא הלל/דרך ז'בוטינסקי
               operator דן, towards פתח תקווה_רכבת סגולה
    05:19-05:23  walk 240 m                    ת.רק"ל אבא הלל/דרך ז'בוטינסקי -> END
```

**Alternative 3**

```
    Departs Wed 09 Sep 05:14 (164 min after the requested time)
    Arrives Wed 09 Sep 05:40 -- 26 min, 0 transfer(s)

    05:14-05:17  walk 136 m                    START -> דיזנגוף סנטר/טשרניחובסקי
    05:17-05:36  bus 66                        דיזנגוף סנטר/טשרניחובסקי -> ת.רק"ל אבא הלל/דרך ז'בוטינסקי
               operator דן, towards פתח תקווה_מסוף משה ארנס
    05:36-05:40  walk 240 m                    ת.רק"ל אבא הלל/דרך ז'בוטינסקי -> END
```

</details>

<sub>Machine checks (structure only — not a quality judgement): structural check (any itinerary): **pass**</sub>

**Verdict:** 

---

## J23 — Mitzpe Ramon → Metula

*PRD §7 #10 no reasonable transit route* · category `no-reasonable-route`

**Departing:** 2026-09-09T02:30:00+03:00 (rule `after_midnight`)

> **What to check:** Desert to the Lebanese border at 02:30. A returned itinerary here means the engine is inventing service. A clear 'no route' is the PASS.

**The corpus expected:** outcome `no-route`

**RESULT: 5 itinerary/itineraries returned.** The first one — the one a
user would be shown — is:

```
    Departs Wed 09 Sep 04:57 (147 min after the requested time)
    Arrives Wed 09 Sep 11:46 -- 409 min, 4 transfer(s)

    04:57-05:03  walk 336 m                    START -> מרכז מסחרי/מצפה רמון
    05:03-06:22  bus 64                        מרכז מסחרי/מצפה רמון -> ת.מרכזית באר שבע/הורדה
               operator מטרופולין, towards באר שבע_תחנה מרכזית
    06:28-06:30  walk 163 m                    ת.מרכזית באר שבע/הורדה -> ת.מרכזית באר שבע/רציפים בינעירוני
    06:30-07:50  bus 370                       ת.מרכזית באר שבע/רציפים בינעירוני -> ת.מרכזית תל אביב קומה 6/הורדה
               operator מטרופולין, towards תל אביב יפו_תחנה מרכזית
    07:58-08:00  walk distance not reported    ת.מרכזית תל אביב קומה 6/הורדה -> ת.מרכזית תל אביב קומה 7/רציפים
    08:00-10:39  bus 845                       ת.מרכזית תל אביב קומה 7/רציפים -> תל חי/90
               operator אגד, towards קרית שמונה_תחנה מרכזית
    10:39-10:41  walk 0 m                      תל חי/90 -> תל חי/90
    10:41-10:49  bus 12                        תל חי/90 -> ת. מרכזית ק"ש/רציפים
               operator אגד, towards קרית שמונה_א"ת צפוני
    10:49-10:51  walk 0 m                      ת. מרכזית ק"ש/רציפים -> ת. מרכזית ק"ש/רציפים
    11:30-11:44  bus 20                        ת. מרכזית ק"ש/רציפים -> מרכז ספורט קנדה
               operator אגד, towards תחנה מרכזית
    11:44-11:46  walk 69 m                     מרכז ספורט קנדה -> END
```

<details><summary>Alternatives MOTIS also returned (4 more)</summary>

**Alternative 1**

```
    Departs Wed 09 Sep 06:05 (215 min after the requested time)
    Arrives Wed 09 Sep 13:06 -- 421 min, 3 transfer(s)

    06:05-06:12  walk 390 m                    START -> עין זיק/עין עקב
    06:12-08:43  bus 660                       עין זיק/עין עקב -> ת.מרכזית תל אביב קומה 6/הורדה
               operator מטרופולין, towards תל אביב יפו_תחנה מרכזית
    09:08-09:10  walk distance not reported    ת.מרכזית תל אביב קומה 6/הורדה -> ת.מרכזית תל אביב קומה 7/רציפים
    09:10-11:53  bus 845                       ת.מרכזית תל אביב קומה 7/רציפים -> ת. מרכזית ק"ש/הורדה
               operator אגד, towards קרית שמונה_תחנה מרכזית
    11:53-11:55  walk 0 m                      ת. מרכזית ק"ש/הורדה -> ת. מרכזית ק"ש/הורדה
    11:55-11:55  bus 11                        ת. מרכזית ק"ש/הורדה -> ת. מרכזית ק"ש/רציפים
               operator אגד, towards מפעלים אזוריים הגליל העליון_מ.מסחרי ביג
    11:55-11:57  walk 0 m                      ת. מרכזית ק"ש/רציפים -> ת. מרכזית ק"ש/רציפים
    12:50-13:04  bus 20                        ת. מרכזית ק"ש/רציפים -> מרכז ספורט קנדה
               operator אגד, towards תחנה מרכזית
    13:04-13:06  walk 69 m                     מרכז ספורט קנדה -> END
```

**Alternative 2**

```
    Departs Wed 09 Sep 06:55 (265 min after the requested time)
    Arrives Wed 09 Sep 13:06 -- 371 min, 5 transfer(s)

    06:55-07:01  walk 336 m                    START -> מרכז מסחרי/מצפה רמון
    07:01-08:04  bus 65                        מרכז מסחרי/מצפה רמון -> צומת אוהלים (הנוקדים)
               operator מטרופולין, towards באר שבע_תחנה מרכזית
    08:20-08:22  walk 304 m                    צומת אוהלים (הנוקדים) -> צומת אוהלים (הנוקדים)
    08:22-09:34  bus 458                       צומת אוהלים (הנוקדים) -> מחלף חמד
               operator מטרופולין, towards ירושלים_מרכז תחבורתי הארזים
    09:45-09:47  walk 371 m                    מחלף חמד -> מחלף חמד
    09:47-10:53  bus 960                       מחלף חמד -> מחלף אליקים לצפון
               operator אגד, towards חיפה_מרכזית המפרץ
    11:06-11:08  walk 0 m                      מחלף אליקים לצפון -> מחלף אליקים לצפון
    11:08-12:33  bus 845                       מחלף אליקים לצפון -> ת. מרכזית ק"ש/הורדה
               operator אגד, towards קרית שמונה_תחנה מרכזית
    12:43-12:45  walk 0 m                      ת. מרכזית ק"ש/הורדה -> ת. מרכזית ק"ש/הורדה
    12:45-12:45  bus 11                        ת. מרכזית ק"ש/הורדה -> ת. מרכזית ק"ש/רציפים
               operator אגד, towards מפעלים אזוריים הגליל העליון_מ.מסחרי ביג
    12:45-12:47  walk 0 m                      ת. מרכזית ק"ש/רציפים -> ת. מרכזית ק"ש/רציפים
    12:50-13:04  bus 20                        ת. מרכזית ק"ש/רציפים -> מרכז ספורט קנדה
               operator אגד, towards תחנה מרכזית
    13:04-13:06  walk 69 m                     מרכז ספורט קנדה -> END
```

**Alternative 3**

```
    Departs Wed 09 Sep 08:00 (330 min after the requested time)
    Arrives Wed 09 Sep 14:31 -- 391 min, 4 transfer(s)

    08:00-08:06  walk 336 m                    START -> מרכז מסחרי/מצפה רמון
    08:06-09:18  bus 65                        מרכז מסחרי/מצפה רמון -> ת.מרכזית באר שבע/הורדה
               operator מטרופולין, towards באר שבע_תחנה מרכזית
    09:28-09:30  walk 163 m                    ת.מרכזית באר שבע/הורדה -> ת.מרכזית באר שבע/רציפים בינעירוני
    09:30-10:50  bus 370                       ת.מרכזית באר שבע/רציפים בינעירוני -> ת.מרכזית תל אביב קומה 6/הורדה
               operator מטרופולין, towards תל אביב יפו_תחנה מרכזית
    11:08-11:10  walk distance not reported    ת.מרכזית תל אביב קומה 6/הורדה -> ת.מרכזית תל אביב קומה 7/רציפים
    11:10-13:49  bus 845                       ת.מרכזית תל אביב קומה 7/רציפים -> תל חי/90
               operator אגד, towards קרית שמונה_תחנה מרכזית
    13:59-14:01  walk 0 m                      תל חי/90 -> תל חי/90
    14:01-14:09  bus 12                        תל חי/90 -> ת. מרכזית ק"ש/רציפים
               operator אגד, towards קרית שמונה_א"ת צפוני
    14:09-14:11  walk 0 m                      ת. מרכזית ק"ש/רציפים -> ת. מרכזית ק"ש/רציפים
    14:15-14:29  bus 20                        ת. מרכזית ק"ש/רציפים -> מרכז ספורט קנדה
               operator אגד, towards תחנה מרכזית
    14:29-14:31  walk 69 m                     מרכז ספורט קנדה -> END
```

</details>

<sub>Machine checks (structure only — not a quality judgement): structural check (any itinerary): **fail** · 5 itinerary/itineraries returned but the case requires no route -- the engine may be inventing service</sub>

**Verdict:** 

---

## J24 — Masada Junction → Beersheba Central

category `long-walk-accessibility`

**Departing:** 2026-09-08T13:00:00+03:00 (rule `weekday_midday`)

> **What to check:** Sparse desert service with long access walks. Check the walking legs are physically plausible — not a 6 km hike along a highway shoulder.

**The corpus expected:** outcome `either`, `min_duration_min` = 40, `max_duration_min` = 300, `max_walk_m` = 3000

**RESULT: no route returned.**

<sub>Machine checks (structure only — not a quality judgement): structural check (any itinerary): **pass** · no itineraries returned, which the case allows</sub>

**Verdict:** 

---

## J25 — Dizengoff Center → Yitzhak Navon Station

category `shabbat-holiday`

**Departing:** 2026-09-05T12:00:00+03:00 (rule `shabbat`)

> **What to check:** THE Israeli calendar case: national rail and most buses do not run on Shabbat, while some operators and city lines do. A confident full itinerary on Saturday noon is almost certainly wrong. Verify whatever it returns against the actual calendar.txt entries.

**The corpus expected:** outcome `either`

**RESULT: 5 itinerary/itineraries returned.** The first one — the one a
user would be shown — is:

```
    Departs Sat 05 Sep 18:50 (410 min after the requested time)
    Arrives Sat 05 Sep 20:10 -- 80 min, 1 transfer(s)

    18:50-18:53  walk 136 m                    START -> דיזנגוף סנטר/טשרניחובסקי
    18:53-19:04  bus 18                        דיזנגוף סנטר/טשרניחובסקי -> ת. רכבת תל אביב - סבידור/הורדה
               operator דן, towards תל אביב יפו_רכבת מרכז
    19:04-19:06  walk 184 m                    ת. רכבת תל אביב - סבידור/הורדה -> ת.רכבת תל אביב - סבידור/רציפים B
    19:15-20:05  bus 480                       ת.רכבת תל אביב - סבידור/רציפים B -> ת. מרכזית ירושלים/הורדה
               operator אגד, towards ירושלים_תחנה מרכזית
    20:05-20:10  walk 306 m                    ת. מרכזית ירושלים/הורדה -> END
```

<details><summary>Alternatives MOTIS also returned (4 more)</summary>

**Alternative 1**

```
    Departs Sat 05 Sep 19:10 (430 min after the requested time)
    Arrives Sat 05 Sep 20:25 -- 75 min, 1 transfer(s)

    19:10-19:13  walk 136 m                    START -> דיזנגוף סנטר/טשרניחובסקי
    19:13-19:24  bus 18                        דיזנגוף סנטר/טשרניחובסקי -> ת. רכבת תל אביב - סבידור/הורדה
               operator דן, towards תל אביב יפו_רכבת מרכז
    19:24-19:26  walk 184 m                    ת. רכבת תל אביב - סבידור/הורדה -> ת.רכבת תל אביב - סבידור/רציפים B
    19:30-20:20  bus 480                       ת.רכבת תל אביב - סבידור/רציפים B -> ת. מרכזית ירושלים/הורדה
               operator אגד, towards ירושלים_תחנה מרכזית
    20:20-20:25  walk 306 m                    ת. מרכזית ירושלים/הורדה -> END
```

**Alternative 2**

```
    Departs Sat 05 Sep 19:27 (447 min after the requested time)
    Arrives Sat 05 Sep 20:40 -- 73 min, 1 transfer(s)

    19:27-19:30  walk 136 m                    START -> דיזנגוף סנטר/טשרניחובסקי
    19:30-19:43  bus 61                        דיזנגוף סנטר/טשרניחובסקי -> ת. רכבת תל אביב סבידור/על פרשת דרכים
               operator דן, towards רמת גן_מסוף עמידר
    19:43-19:45  walk 206 m                    ת. רכבת תל אביב סבידור/על פרשת דרכים -> ת.רכבת תל אביב - סבידור/רציפים B
    19:45-20:35  bus 480                       ת.רכבת תל אביב - סבידור/רציפים B -> ת. מרכזית ירושלים/הורדה
               operator אגד, towards ירושלים_תחנה מרכזית
    20:35-20:40  walk 306 m                    ת. מרכזית ירושלים/הורדה -> END
```

**Alternative 3**

```
    Departs Sat 05 Sep 19:42 (462 min after the requested time)
    Arrives Sat 05 Sep 20:55 -- 73 min, 1 transfer(s)

    19:42-19:45  walk 136 m                    START -> דיזנגוף סנטר/טשרניחובסקי
    19:45-19:58  bus 61                        דיזנגוף סנטר/טשרניחובסקי -> ת. רכבת תל אביב סבידור/על פרשת דרכים
               operator דן, towards רמת גן_מסוף עמידר
    19:58-20:00  walk 206 m                    ת. רכבת תל אביב סבידור/על פרשת דרכים -> ת.רכבת תל אביב - סבידור/רציפים B
    20:00-20:50  bus 480                       ת.רכבת תל אביב - סבידור/רציפים B -> ת. מרכזית ירושלים/הורדה
               operator אגד, towards ירושלים_תחנה מרכזית
    20:50-20:55  walk 306 m                    ת. מרכזית ירושלים/הורדה -> END
```

</details>

<sub>Machine checks (structure only — not a quality judgement): structural check (any itinerary): **pass**</sub>

**Verdict:** 

---

## When you are done

Count the verdicts on the ten PRD §7 journeys — the cases tagged with a
`PRD §7` reference above. Nine or more `reasonable` meets the PRD bar and
POC-2 can move from PARTIAL to PASS. Fewer than nine is the FAIL/STOP
condition in PRD §7, which says to investigate another engine before
continuing — and ADR 0004 says that switch is your decision, not an agent's.

Update `poc/results/poc-2.json` with the outcome and re-run
`python poc/poc_status.py --write`.

