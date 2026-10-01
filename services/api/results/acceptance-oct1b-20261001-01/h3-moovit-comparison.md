# H3 route review — our API vs Moovit

Generation `5eb4e43d…` (acceptance build oct1b, Oct 1–31 coverage), API source `c14476a`. Our journeys are **scheduled only**. Moovit results were read on 2026-10-01 from moovitapp.com at the **same coordinates and departure time** (Moovit may include its own live adjustments). Raw API responses: [h3-review-raw](acceptance-oct1b-20261001-01-h3-review-raw.json); full leg-by-leg sheet: [h3-review](acceptance-oct1b-20261001-01-h3-review.md).

**You fill in `Usable?` (Y / N / unsure) and `Notes`.** H3 passes when at least 9 of the 10 required journeys (★) are usable. The `Δ best arrival` column is a mechanical hint only: our earliest arrival minus Moovit's earliest arrival (positive = we arrive later).

| Case | From → To | When | Our best options (dep→arr, transfers, lines) | Moovit best options | Δ best arrival | Usable? | Notes |
|---|---|---|---|---|---|---|---|
| ★ J01 | Dizengoff Center → Ramat Gan Bursa | 10-05 08:00 | 08:06→08:24 (0×, 82); 08:14→08:33 (0×, 238); 08:17→08:35 (0×, 82) | 82 08:11→08:22; 66 08:02→08:24; 238 08:17→08:33 | +2 min | | |
| J02 | Tel Aviv University → Sourasky Medical Center (Ichilov) | 10-05 08:00 | 08:00→08:26 (1×, 24/89); 08:05→08:30 (1×, 40/7); 08:08→08:35 (2×, 10/249/18) | 7 08:06→08:22 (direct); 171 08:12→08:31; 40/274→7 08:13→08:30 | +4 min | | |
| J03 | Jaffa Clock Tower → Tel Aviv Savidor Center | 10-06 13:00 | 13:04→13:35 (0×, 44); 13:06→13:39 (1×, 54/rail); 13:07→13:42 (0×, 1) | 18 13:07→13:31; LRT 13:13→13:34; 44 13:09→13:32 | +4 min | | |
| ★ J04 | Dizengoff Center → Petah Tikva Kiryat Arye | 10-07 18:30 | 18:31→19:06 (1×, 63/1); 18:36→19:11 (0×, 82); 18:42→19:17 (1×, 63/1) | LRT red line 18:43→19:00; 82 18:41→19:08; 172 18:33→19:08 | +6 min | | |
| J05 | Mahane Yehuda Market → Mount Herzl | 10-06 13:00 | 13:02→13:27 (0×, 1); 13:07→13:32 (0×, 1); 13:12→13:37 (0×, 1) | LRT 13:08→13:32; 39/814 13:13→13:33; 27/27א 13:24→13:43 | -5 min | | |
| J06 | Jerusalem Central Bus Station → Hebrew University Mount Scopus | 10-05 08:00 | 08:01→08:28 (1×, 18/19א); 08:07→08:30 (0×, 568); 08:08→08:32 (1×, 74/19) | 74/18 → 19/19א/17 08:02→08:22; 568/68 08:11→08:29; 19א/19/17 08:04→08:31 | +6 min | | |
| J07 | Yitzhak Navon Station → Malha Mall | 10-07 18:30 | 18:33→18:56 (0×, 531); 18:33→18:55 (1×, 531/18); 18:34→18:57 (0×, 504) | 531/504/509 18:37→18:50; 31 18:44→18:55; 18 18:32→19:10 | +5 min | | |
| J08 | Haifa Center HaShmona → Technion | 10-05 08:00 | 08:00→08:40 (0×, 17); 08:01→08:40 (1×, 3/17); 08:08→08:50 (1×, 16/76) | 17/217 08:11→08:39; 444→142 08:07→08:40; 67→1 08:18→08:51 | +1 min | | |
| J09 | Haifa University → Bat Galim Central Station | 10-07 18:30 | **no route** | 148/24 → 9 18:36→19:24; 37א/24/37 → 1 → 9 18:38→19:34; 148/37א/37 → 110 → 9 18:38→19:38 | **we: no route; Moovit has routes** | | |
| J10 | Grand Kanyon Haifa → Rambam Medical Center | 10-06 13:00 | 13:01→13:47 (1×, 58/40); 13:06→13:52 (0×, 37); 13:08→13:53 (0×, 37א) | 51א 13:18→13:56 | -9 min | | |
| ★ J11 | Tel Aviv Savidor Center → Haifa Center HaShmona | 10-05 08:00 | 08:25→09:52 (1×, rail/36); 08:44→10:08 (1×, rail/18) | train → bus 5 08:17→09:29; train → bus 5 08:28→09:41; 910 → 1 08:15→09:51 | +23 min | | |
| ★ J12 | Tel Aviv Savidor Center → Yitzhak Navon Station | 10-05 08:00 | 08:04→08:55 (0×, rail); 08:14→09:09 (0×, 480); 08:34→09:25 (0×, rail) | train 08:07→09:04; 480 08:20→09:08; train → 555 08:31→09:47 | -9 min | | |
| J13 | Tel Aviv HaShalom → Beersheba Central | 10-06 13:00 | 13:11→14:51 (0×, rail); 13:37→15:20 (0×, rail); 13:46→15:35 (2×, rail/114/370) | train 13:15→14:50; train 13:11→14:57; 280→348 13:04→14:58 | +1 min | | |
| J14 | Nahariya → Ashdod Ad Halom | 10-05 08:00 | 08:02→10:53 (1×, rail/280); 08:15→11:23 (1×, rail/281); 08:15→11:21 (3×, rail/89/312/10) | train → 280 08:15→10:52; train → 629 → 13 08:15→11:08 | +1 min | | |
| ★ J15 | Weizmann Institute, Rehovot → Haifa Center HaShmona | 10-05 08:00 | **no route** | 277 → train → 5 08:12→10:06; train → 26 → 5 08:34→10:29; train → 26 → 5 08:24→10:29 | **we: no route; Moovit has routes** | | |
| ★ J16 | Tel Aviv Savidor Center → Technion | 10-05 08:00 | 08:25→09:52 (1×, rail/1); 08:45→10:37 (3×, 825/947/4/144) | train → 217/17 08:17→10:01 | -9 min | | |
| J17 | Modi'in Center → Ben Gurion Airport T3 | 10-05 08:00 | **no route** | train 08:18→08:36 (Modi'in Center → airport); 111 → 425 08:10→08:49; train → train 08:06→09:00 | **we: no route; Moovit has routes** | | |
| J18 | Beersheba North University → Bar-Ilan University | 10-05 08:00 | 08:00→10:04 (3×, 5/370/31/32); 08:00→09:56 (4×, 5/370/2/41/48); 08:17→10:11 (1×, 669/145) | bus → train → bus 08:27→10:09; bus → train → bus 08:27→10:12; train → bus 08:34→10:19 | -13 min | | |
| ★ J19 | Herzliya Station → Beilinson Hospital, Petah Tikva | 10-05 08:00 | 08:03→09:14 (1×, 91/41); 08:03→08:57 (2×, 91/1/75); 08:06→09:01 (3×, 90/347/1/143) | 606/600/… → 48/22/47/30 08:06→08:52; 91 → 11 08:07→09:01; 91 → 41 08:07→09:13 | +5 min | | |
| J20 | Netanya Station → Mahane Yehuda Market | 10-06 13:00 | 13:03→15:13 (2×, 611/490/39א); 13:03→15:03 (3×, 611/91/rail/75); 13:04→15:13 (3×, 72/611/490/39א) | 610 → 950 13:14→15:36; 71א → 253 → 749 13:35→15:48; 407 → 75 14:21→15:50 | -33 min | | |
| ★ J21 | Tel Aviv Savidor Center → Ben Gurion Airport T3 | 10-06 23:40 | 23:40→00:04 (0×, rail); 00:36→00:56 (0×, rail); 00:46→01:02 (0×, rail) | train 23:43→00:04; 469 00:20→00:52 | +0 min | | |
| ★ J22 | Dizengoff Center → Ramat Gan Bursa | 10-07 02:30 | 02:39→04:19 (1×, 445/rail); 04:57→05:38 (1×, 172/42); 04:57→05:23 (2×, 172/23/50) | 445 → train → 8 02:42→04:20; 66 05:17→05:39 | -1 min | | |
| ★ J23 | Har Karkom, central Negev → Metula | 10-07 02:30 | **no route** | no route (Moovit: 'try changing the departure time') | both no route | | |
| J24 | Masada Junction → Beersheba Central | 10-06 13:00 | **no route** | 421 → 388 13:30→15:16; 421 → 20/388/121 13:30→15:22; 384 15:40→17:24 | **we: no route; Moovit has routes** | | |
| J25 | Dizengoff Center → Yitzhak Navon Station | 10-10 12:00 | 18:50→20:04 (1×, 18/480); 19:10→20:19 (1×, 18/480); 19:27→20:34 (1×, 61/480) | not comparable: Moovit only plans ~7 days ahead (it silently switched to leave-now); recheck from 2026-10-03 | — | | |
| J11-FRI | Tel Aviv Savidor Center → Haifa Center HaShmona | 10-09 15:30 | 15:34→17:15 (1×, 909/2); 15:44→17:27 (1×, 909/2); 15:54→17:39 (1×, 909/2) | not comparable: Moovit only plans ~7 days ahead (it silently switched to leave-now); recheck from 2026-10-02 | — | | |
| J12-FRI | Tel Aviv Savidor Center → Yitzhak Navon Station | 10-09 15:30 | 15:30→16:25 (0×, 480); 15:42→16:37 (0×, 480); 15:54→16:49 (0×, 480) | not comparable: Moovit only plans ~7 days ahead (it silently switched to leave-now); recheck from 2026-10-02 | — | | |
| J11-SAT | Tel Aviv Savidor Center → Haifa Center HaShmona | 10-10 12:00 | 15:35→18:30 (2×, 825/301/1); 16:34→18:47 (1×, 836/332); 16:45→18:45 (2×, 825/947/245) | not comparable: Moovit only plans ~7 days ahead (it silently switched to leave-now); recheck from 2026-10-03 | — | | |
| J05-SAT | Mahane Yehuda Market → Mount Herzl | 10-10 12:00 | 19:38→20:03 (0×, 1); 19:47→20:12 (0×, 1); 19:56→20:21 (0×, 1) | not comparable: Moovit only plans ~7 days ahead (it silently switched to leave-now); recheck from 2026-10-03 | — | | |
| J01-HOL | Dizengoff Center → Ramat Gan Bursa | 10-01 08:00 | 08:00→08:19 (1×, 14/142); 08:02→08:21 (0×, 238); 08:06→08:24 (0×, 82) | 238 08:05→08:21; 82 08:11→08:22; 66 08:05→08:27 | -2 min | | |
| J12-HOL | Tel Aviv Savidor Center → Yitzhak Navon Station | 10-01 13:00 | 13:04→13:55 (0×, rail); 13:14→14:09 (0×, 480); 13:34→14:25 (0×, rail) | train 13:07→14:04; 480 13:20→14:08 | -9 min | | |
| J01-DST | Dizengoff Center → Ramat Gan Bursa | 10-25 08:00 | 08:06→08:24 (0×, 82); 08:14→08:33 (0×, 238); 08:17→08:35 (0×, 82) | not comparable: Moovit only plans ~7 days ahead (it silently switched to leave-now); recheck from 2026-10-18 | — | | |
| J22-DST1 | Dizengoff Center → Ramat Gan Bursa | 10-25 01:30 | 01:30→01:59 (0×, 18); 01:30→01:52 (1×, 18/142); 01:37→01:01 (0×, 61) | not comparable: Moovit only plans ~7 days ahead (it silently switched to leave-now); recheck from 2026-10-18 | — | | |
| J22-DST2 | Dizengoff Center → Ramat Gan Bursa | 10-25 01:30 | 01:42→02:20 (0×, 425); 01:53→02:30 (1×, 425/1); 02:12→02:50 (0×, 425) | not comparable: Moovit only plans ~7 days ahead (it silently switched to leave-now); recheck from 2026-10-18 | — | | |

## Mechanical flags (not verdicts)

- **J09**: no_route but Moovit has routes
- **J11**: we arrive 23 min later
- **J15**: no_route but Moovit has routes
- **J17**: no_route but Moovit has routes
- **J24**: no_route but Moovit has routes

Friday/Shabbat (9–10 Oct) and DST (25 Oct) variants could not be compared yet because Moovit plans about one week ahead; they can be rechecked from the dates shown. J25 (Shabbat noon, Tel Aviv → Jerusalem): our first departure is 18:50, after Shabbat ends — check that this matches your expectation.
