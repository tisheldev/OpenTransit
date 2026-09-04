#!/usr/bin/env python3
"""Generate places.json — the POC-5 geocoding corpus.

Kept as a generator rather than hand-written JSON so the 100 queries stay
readable as data and the schema can be regenerated after Agent A snaps
coordinates to real GTFS stops.

Coordinates are APPROXIMATE and hand-entered. They are targets with a
tolerance, not ground truth. `tol_m` is deliberately generous: POC-5 asks
"did this resolve somewhere usable enough to start routing" (PRD §10),
not "is this the exact stop centroid".
"""

import json
from pathlib import Path

# (id, query, lang, category, expected_place, lat, lon, tol_m, note)
# lang: he | en | mixed
Q = [
    # --- stations and stops (20) -------------------------------------------
    ("P001", "Tel Aviv Savidor Center", "en", "station", "TA Savidor", 32.0836, 34.7981, 400, ""),
    ("P002", "תחנת רכבת תל אביב סבידור מרכז", "he", "station", "TA Savidor", 32.0836, 34.7981, 400, ""),
    ("P003", "HaShalom Station", "en", "station", "TA HaShalom", 32.0731, 34.7925, 400, "PRD §10 names this one explicitly"),
    ("P004", "תחנת השלום", "he", "station", "TA HaShalom", 32.0731, 34.7925, 400, ""),
    ("P005", "Yitzhak Navon", "en", "station", "JLM Navon", 31.7888, 35.2027, 500, ""),
    ("P006", "תחנת יצחק נבון", "he", "station", "JLM Navon", 31.7888, 35.2027, 500, ""),
    ("P007", "Haifa Center HaShmona", "en", "station", "Haifa Center", 32.8206, 34.9985, 500, ""),
    ("P008", "חיפה מרכז השמונה", "he", "station", "Haifa Center", 32.8206, 34.9985, 500, ""),
    ("P009", "Beersheba Central Station", "en", "station", "BS Central", 31.2430, 34.7983, 500, ""),
    ("P010", "באר שבע מרכז", "he", "station", "BS Central", 31.2430, 34.7983, 500, ""),
    ("P011", "Ben Gurion Airport", "en", "station", "TLV Airport", 32.0114, 34.8867, 900, "airport terminal vs station ambiguity"),
    ("P012", "נמל תעופה בן גוריון", "he", "station", "TLV Airport", 32.0114, 34.8867, 900, ""),
    ("P013", "Herzliya Station", "en", "station", "Herzliya", 32.1656, 34.8095, 500, ""),
    ("P014", "Modi'in Center", "en", "station", "Modiin Center", 31.9017, 35.0074, 600, "apostrophe handling"),
    ("P015", "Nahariya", "en", "station", "Nahariya", 33.0079, 35.0938, 700, "northern terminus"),
    ("P016", "Ashdod Ad Halom", "en", "station", "Ashdod", 31.7940, 34.6410, 600, ""),
    ("P017", "Bat Galim", "en", "station", "Bat Galim", 32.8283, 34.9539, 500, ""),
    ("P018", "Jerusalem Central Bus Station", "en", "station", "JLM CBS", 31.7887, 35.2030, 500, ""),
    ("P019", "תחנה מרכזית ירושלים", "he", "station", "JLM CBS", 31.7887, 35.2030, 500, ""),
    ("P020", "Petah Tikva Kiryat Arye", "en", "station", "PT Kiryat Arye", 32.0956, 34.8556, 500, ""),

    # --- universities, hospitals, malls, landmarks (20) --------------------
    ("P021", "Technion", "en", "poi_university", "Technion", 32.7767, 35.0217, 900, "PRD §39 demo destination"),
    ("P022", "הטכניון", "he", "poi_university", "Technion", 32.7767, 35.0217, 900, ""),
    ("P023", "Tel Aviv University", "en", "poi_university", "TAU", 32.1133, 34.8044, 900, ""),
    ("P024", "אוניברסיטת תל אביב", "he", "poi_university", "TAU", 32.1133, 34.8044, 900, ""),
    ("P025", "Hebrew University Mount Scopus", "en", "poi_university", "HUJI Scopus", 31.7936, 35.2444, 900, ""),
    ("P026", "Ben Gurion University", "en", "poi_university", "BGU", 31.2620, 34.8016, 900, ""),
    ("P027", "Bar-Ilan University", "en", "poi_university", "Bar-Ilan", 32.0700, 34.8433, 900, "hyphen handling"),
    ("P028", "Haifa University", "en", "poi_university", "Haifa U", 32.7614, 35.0207, 900, ""),
    ("P029", "Weizmann Institute", "en", "poi_university", "Weizmann", 31.9070, 34.8102, 900, ""),
    ("P030", "Ichilov", "en", "poi_hospital", "Sourasky", 32.0800, 34.7900, 700, "colloquial name, not the official one"),
    ("P031", "איכילוב", "he", "poi_hospital", "Sourasky", 32.0800, 34.7900, 700, ""),
    ("P032", "Beilinson Hospital", "en", "poi_hospital", "Beilinson", 32.0870, 34.8580, 700, ""),
    ("P033", "Rambam Medical Center", "en", "poi_hospital", "Rambam", 32.8347, 34.9857, 700, ""),
    ("P034", "Hadassah Ein Kerem", "en", "poi_hospital", "Hadassah EK", 31.7658, 35.1206, 900, ""),
    ("P035", "Dizengoff Center", "en", "poi_mall", "Dizengoff Ctr", 32.0757, 34.7748, 500, "PRD §39 demo origin"),
    ("P036", "דיזנגוף סנטר", "he", "poi_mall", "Dizengoff Ctr", 32.0757, 34.7748, 500, ""),
    ("P037", "Azrieli Center", "en", "poi_mall", "Azrieli", 32.0742, 34.7925, 500, ""),
    ("P038", "Malha Mall", "en", "poi_mall", "Malha", 31.7513, 35.1875, 700, ""),
    ("P039", "Mahane Yehuda Market", "en", "poi_landmark", "Mahane Yehuda", 31.7853, 35.2124, 500, ""),
    ("P040", "Western Wall", "en", "poi_landmark", "Kotel", 31.7767, 35.2345, 500, ""),

    # --- more landmarks (10) -----------------------------------------------
    ("P041", "הכותל המערבי", "he", "poi_landmark", "Kotel", 31.7767, 35.2345, 500, ""),
    ("P042", "Jaffa Clock Tower", "en", "poi_landmark", "Jaffa Clock", 32.0542, 34.7522, 500, ""),
    ("P043", "מגדל השעון יפו", "he", "poi_landmark", "Jaffa Clock", 32.0542, 34.7522, 500, ""),
    ("P044", "Yad Vashem", "en", "poi_landmark", "Yad Vashem", 31.7742, 35.1753, 700, ""),
    ("P045", "Mount Herzl", "en", "poi_landmark", "Har Herzl", 31.7736, 35.1806, 600, ""),
    ("P046", "Sarona Market", "en", "poi_landmark", "Sarona", 32.0714, 34.7869, 500, ""),
    ("P047", "Habima Theatre", "en", "poi_landmark", "Habima", 32.0724, 34.7803, 500, ""),
    ("P048", "Bloomfield Stadium", "en", "poi_landmark", "Bloomfield", 32.0517, 34.7614, 600, ""),
    ("P049", "Masada", "en", "poi_landmark", "Masada", 31.3156, 35.3539, 2000, "remote; large tolerance"),
    ("P050", "Mitzpe Ramon", "en", "poi_landmark", "Mitzpe Ramon", 30.6100, 34.8017, 2000, "remote desert town"),

    # --- street addresses (15) ---------------------------------------------
    ("P051", "Dizengoff 100 Tel Aviv", "en", "address", "Dizengoff St", 32.0793, 34.7740, 700, ""),
    ("P052", "דיזנגוף 100 תל אביב", "he", "address", "Dizengoff St", 32.0793, 34.7740, 700, ""),
    ("P053", "Rothschild Boulevard 1 Tel Aviv", "en", "address", "Rothschild", 32.0637, 34.7699, 700, ""),
    ("P054", "שדרות רוטשילד 1 תל אביב", "he", "address", "Rothschild", 32.0637, 34.7699, 700, ""),
    ("P055", "Ibn Gabirol 30 Tel Aviv", "en", "address", "Ibn Gabirol", 32.0805, 34.7810, 700, "PRD §39 demo street"),
    ("P056", "Jaffa Street 97 Jerusalem", "en", "address", "Jaffa St JLM", 31.7857, 35.2110, 700, "'Jaffa St' exists in several cities"),
    ("P057", "יפו 97 ירושלים", "he", "address", "Jaffa St JLM", 31.7857, 35.2110, 700, ""),
    ("P058", "King George 15 Jerusalem", "en", "address", "King George", 31.7800, 35.2178, 700, ""),
    ("P059", "Herzl 50 Haifa", "en", "address", "Herzl Haifa", 32.8156, 34.9942, 800, "'Herzl' street in most cities"),
    ("P060", "Ben Yehuda 20 Tel Aviv", "en", "address", "Ben Yehuda TA", 32.0790, 34.7686, 700, "also a Jerusalem street"),
    ("P061", "Allenby 40 Tel Aviv", "en", "address", "Allenby", 32.0654, 34.7702, 700, ""),
    ("P062", "HaNevi'im 20 Jerusalem", "en", "address", "HaNeviim", 31.7828, 35.2200, 700, "apostrophe + transliteration"),
    ("P063", "Sokolov 30 Ramat Gan", "en", "address", "Sokolov RG", 32.0836, 34.8110, 800, ""),
    ("P064", "Rager Boulevard Beersheba", "en", "address", "Rager Blvd", 31.2530, 34.7950, 900, ""),
    ("P065", "הרצל 50 חיפה", "he", "address", "Herzl Haifa", 32.8156, 34.9942, 800, ""),

    # --- neighborhoods (10) -------------------------------------------------
    ("P066", "Florentin", "en", "neighborhood", "Florentin TA", 32.0570, 34.7690, 1200, ""),
    ("P067", "פלורנטין", "he", "neighborhood", "Florentin TA", 32.0570, 34.7690, 1200, ""),
    ("P068", "Neve Tzedek", "en", "neighborhood", "Neve Tzedek", 32.0620, 34.7620, 1000, ""),
    ("P069", "Ramat Aviv", "en", "neighborhood", "Ramat Aviv", 32.1100, 34.7960, 1500, ""),
    ("P070", "Rehavia", "en", "neighborhood", "Rehavia JLM", 31.7750, 35.2110, 1200, ""),
    ("P071", "Nachlaot", "en", "neighborhood", "Nachlaot", 31.7830, 35.2100, 1000, ""),
    ("P072", "Hadar HaCarmel", "en", "neighborhood", "Hadar", 32.8100, 34.9950, 1500, ""),
    ("P073", "Ramot", "en", "neighborhood", "Ramot JLM", 31.8130, 35.1900, 2000, "ambiguous: also Ramot in Haifa area"),
    ("P074", "Old City Jerusalem", "en", "neighborhood", "Old City", 31.7767, 35.2300, 1200, ""),
    ("P075", "העיר העתיקה ירושלים", "he", "neighborhood", "Old City", 31.7767, 35.2300, 1200, ""),

    # --- common misspellings (10) ------------------------------------------
    ("P076", "Dizengof Center", "en", "misspelling", "Dizengoff Ctr", 32.0757, 34.7748, 500, "one f"),
    ("P077", "Technyon", "en", "misspelling", "Technion", 32.7767, 35.0217, 900, ""),
    ("P078", "Jerusalim", "en", "misspelling", "Jerusalem", 31.7857, 35.2110, 3000, ""),
    ("P079", "Beer Sheva", "en", "misspelling", "BS Central", 31.2430, 34.7983, 2000, "space variant"),
    ("P080", "Herzliyya", "en", "misspelling", "Herzliya", 32.1656, 34.8095, 2000, "double y"),
    ("P081", "Netania", "en", "misspelling", "Netanya", 32.3097, 34.8619, 2000, ""),
    ("P082", "Rishon Lezion", "en", "misspelling", "Rishon", 31.9640, 34.8040, 3000, "casing + spacing"),
    ("P083", "Savidor Merkaz", "en", "misspelling", "TA Savidor", 32.0836, 34.7981, 400, "mixed transliteration"),
    ("P084", "Ben Gurion Airoport", "en", "misspelling", "TLV Airport", 32.0114, 34.8867, 900, ""),
    ("P085", "Machne Yehuda", "en", "misspelling", "Mahane Yehuda", 31.7853, 35.2124, 500, ""),

    # --- transliteration variants of the same Hebrew name (9) ---------------
    ("P086", "Petah Tikva", "en", "translit", "Petah Tikva", 32.0870, 34.8870, 3000, "variant 1 of 3"),
    ("P087", "Petach Tikwa", "en", "translit", "Petah Tikva", 32.0870, 34.8870, 3000, "variant 2 of 3"),
    ("P088", "Petah Tiqwa", "en", "translit", "Petah Tikva", 32.0870, 34.8870, 3000, "variant 3 of 3"),
    ("P089", "Rishon LeTsiyon", "en", "translit", "Rishon", 31.9640, 34.8040, 3000, "ts vs tz"),
    ("P090", "Rishon LeZion", "en", "translit", "Rishon", 31.9640, 34.8040, 3000, ""),
    ("P091", "Kfar Saba", "en", "translit", "Kfar Saba", 32.1750, 34.9070, 3000, ""),
    ("P092", "Kefar Sava", "en", "translit", "Kfar Saba", 32.1750, 34.9070, 3000, "b/v and vowel variant"),
    ("P093", "Akko", "en", "translit", "Akko", 32.9280, 35.0820, 3000, ""),
    ("P094", "Acre", "en", "translit", "Akko", 32.9280, 35.0820, 3000, "English exonym, not a transliteration"),

    # --- near-dependent: correct answer depends on the bias point (6) -------
    ("P095", "Central Station", "en", "near_dependent", "TA CBS", 32.0570, 34.7800, 1500, "near=Tel Aviv"),
    ("P096", "Central Station", "en", "near_dependent", "JLM CBS", 31.7887, 35.2030, 1500, "near=Jerusalem — same string, different answer"),
    ("P097", "Herzl", "en", "near_dependent", "Herzl TA area", 32.0800, 34.7700, 3000, "near=Tel Aviv"),
    ("P098", "Herzl", "en", "near_dependent", "Herzl Haifa", 32.8156, 34.9942, 3000, "near=Haifa"),
    ("P099", "HaTachana", "en", "near_dependent", "HaTachana TA", 32.0610, 34.7620, 2000, "near=Tel Aviv; common stop name nationwide"),
    ("P100", "University", "en", "near_dependent", "Haifa U", 32.7614, 35.0207, 3000, "near=Haifa"),
]

NEAR = {
    "P095": (32.0800, 34.7800), "P096": (31.7857, 35.2110),
    "P097": (32.0800, 34.7800), "P098": (32.8156, 34.9942),
    "P099": (32.0800, 34.7800), "P100": (32.7940, 34.9896),
}


def main() -> None:
    cases = []
    for qid, q, lang, cat, place, lat, lon, tol, note in Q:
        case = {
            "id": qid, "query": q, "lang": lang, "category": cat,
            "expect": {"place": place, "lat": lat, "lon": lon, "tol_m": tol},
        }
        if qid in NEAR:
            case["near"] = {"lat": NEAR[qid][0], "lon": NEAR[qid][1]}
        if note:
            case["note"] = note
        cases.append(case)

    counts: dict[str, int] = {}
    for c in cases:
        counts[c["category"]] = counts.get(c["category"], 0) + 1

    doc = {
        "schema_version": 1,
        "generated": "2026-09-04",
        "generator": "poc/corpora/build_places.py",
        "purpose": "POC-5 geocoding corpus. PRD §10 PASS bar is >=20 correct resolutions; this corpus is 100 so the per-category breakdown is meaningful.",
        "provenance": {
            "coordinates": "APPROXIMATE, hand-entered, NOT validated against GTFS or OSM. Targets with a tolerance, not ground truth.",
            "tolerance": "tol_m is generous by design. PRD §10 asks whether a query resolves well enough to start routing, not whether it hits a stop centroid.",
            "near_dependent": "P095-P100 include a `near` bias point. P095/P096 and P097/P098 are the same query string with different correct answers — an engine that ignores `near` cannot pass both.",
        },
        "category_counts": counts,
        "total": len(cases),
        "cases": cases,
    }

    out = Path(__file__).with_name("places.json")
    out.write_text(json.dumps(doc, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"wrote {out} — {len(cases)} cases")
    for k in sorted(counts):
        print(f"  {k:16} {counts[k]:3}")


if __name__ == "__main__":
    main()
