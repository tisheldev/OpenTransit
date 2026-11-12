"""Merging stop and geocoder candidates by how well each one answers the query."""

from opentransit.place_ranking import merge_candidates


def stop(stop_id: str, name: str, description: str) -> dict:
    return {
        "kind": "stop",
        "id": f"mot:stop:{stop_id}",
        "displayName": name,
        "locality": description,
        "coordinates": {"latitude": 32.16, "longitude": 34.84},
        "locationRef": {"kind": "stop", "stopId": f"mot:stop:{stop_id}"},
    }


def street(ref: str, name: str, locality: str | None, at=(32.16, 34.84)) -> dict:
    return {
        "kind": "address",
        "displayName": name,
        "street": name,
        "houseNumber": None,
        "locality": locality,
        "addressLevel": "street",
        "coordinates": {"latitude": at[0], "longitude": at[1]},
        "locationRef": {"kind": "place", "placeRef": ref},
    }


def house(ref: str, street_name: str, number: str, locality: str, at=(32.16, 34.84)) -> dict:
    return {
        "kind": "address",
        "displayName": f"{street_name} {number}, {locality}",
        "street": street_name,
        "houseNumber": number,
        "locality": locality,
        "addressLevel": "house_number",
        "coordinates": {"latitude": at[0], "longitude": at[1]},
        "locationRef": {"kind": "place", "placeRef": ref},
    }


def poi(ref: str, name: str, locality: str | None) -> dict:
    return {
        "kind": "poi",
        "displayName": name,
        "locality": locality,
        "coordinates": {"latitude": 32.16, "longitude": 34.84},
        "locationRef": {"kind": "place", "placeRef": ref},
    }


def names(items: list[dict]) -> list[str]:
    return [item["displayName"] for item in items]


def test_address_query_puts_the_street_in_the_named_city_before_loose_stop_matches():
    # The reported case (12 November): no house number 13 is mapped on this street, the
    # stop search fell back to stops that share only "13" and the city.
    stops = [
        stop("1", "ארלוזורוב/בן יהודה", "רחוב: ארלוזורוב 13 עיר: הרצליה רציף:  קומה: "),
        stop("2", "היכל אומנויות הבמה/ז'בוטינסקי", "רחוב: ז'בוטינסקי 13 עיר: הרצליה רציף: "),
        stop("3", "הפועל/ציפורה זייד", "רחוב: הפועל 13 עיר: חיפה רציף:  קומה: "),
    ]
    geocoders = [
        street("a", "הפועל", "הרצליה"),
        street("b", "הפועל", "הרצליה", at=(32.161, 34.841)),
        house("c", "הפועל", "13", "בת ים"),
        house("d", "הפועל הצעיר", "13", "רחובות"),
    ]
    merged = merge_candidates("הפועל 13 הרצליה", stops, geocoders, 10, stop_fallback={})
    assert merged[0]["locationRef"]["placeRef"] == "a"
    # The second segment of the same street in the same city is not listed again.
    assert [item["locationRef"].get("placeRef") for item in merged].count("b") == 0
    # Stops that share only the number and the city come after everything that names the street.
    assert names(merged)[-2:] == ["ארלוזורוב/בן יהודה", "היכל אומנויות הבמה/ז'בוטינסקי"]
    assert names(merged).index("הפועל 13, בת ים") < names(merged).index("ארלוזורוב/בן יהודה")


def test_exact_house_leads_an_address_query_and_the_stop_at_that_address_follows():
    stops = [stop("1", "דיזנגוף סנטר/דיזנגוף", "רחוב: דיזנגוף 50 עיר: תל אביב יפו רציף: ")]
    geocoders = [
        house("en", "דיזנגוף", "50", "Tel Aviv-Yafo"),
        house("he", "דיזנגוף", "50", "תל־אביב–יפו"),
        house("he2", "דיזנגוף", "50", "תל־אביב–יפו", at=(32.1601, 34.8401)),
        poi("cafe", "קפה דיזנגוף", "תל־אביב–יפו"),
    ]
    merged = merge_candidates("דיזנגוף 50 תל אביב", stops, geocoders, 10)
    assert [item["locationRef"].get("placeRef", "stop") for item in merged] == [
        "he",
        "stop",
        "cafe",
    ]


def test_house_number_must_match_exactly_not_by_prefix():
    stops = [stop("1", "מרכז תאו/וינגייט", "רחוב: וינגייט 200 עיר: הרצליה רציף: ")]
    geocoders = [street("a", "סוקולוב", "הרצליה")]
    merged = merge_candidates("סוקולוב 20 הרצליה", stops, geocoders, 10, stop_fallback={})
    assert names(merged) == ["סוקולוב", "מרכז תאו/וינגייט"]


def test_name_query_keeps_stops_first_and_drops_unrelated_streets_behind_matches():
    stops = [
        stop("1", "אוניברסיטת ת''א/מוזיאון הטבע", "רחוב: קלאוזנר עיר: תל אביב יפו"),
        stop("2", "מסוף אוניברסיטת ת''א", "רחוב:   עיר: תל אביב יפו"),
    ]
    geocoders = [
        street("s1", "תל אביב", "دالية الكرمل"),
        street("s2", "כביש ירושלים תל אביב", "תל־אביב–יפו"),
        poi("p1", "אוניברסיטת תל אביב", "תל־אביב–יפו"),
    ]
    merged = merge_candidates("אוניברסיטת תל אביב", stops, geocoders, 10)
    assert [item["locationRef"].get("placeRef", "stop") for item in merged] == [
        "stop",
        "p1",
        "stop",
        "s1",
        "s2",
    ]


def test_trusted_stop_matches_are_not_rescored_from_their_displayed_text():
    # The stop search matched an English label; the Hebrew display text shares no word.
    stops = [stop("1", "דיזנגוף סנטר", "רחוב: דיזנגוף עיר: תל אביב יפו")]
    geocoders = [poi("p1", "Dizengoff Center", "Tel Aviv"), poi("p2", "Center Cafe", "Haifa")]
    merged = merge_candidates("Dizengoff Center", stops, geocoders, 10)
    assert names(merged) == ["דיזנגוף סנטר", "Dizengoff Center", "Center Cafe"]


def test_candidates_in_another_script_keep_their_backend_order_between_good_and_bad():
    geocoders = [
        poi("bad", "Herzl Museum", "Jerusalem"),
        poi("unknown", "מוזיאון העיצוב", "חולון"),
        poi("good", "Design Museum", "Holon"),
    ]
    merged = merge_candidates("design museum", [], geocoders, 10)
    assert [item["locationRef"]["placeRef"] for item in merged] == ["good", "unknown", "bad"]


def test_spelling_variants_and_single_typos_still_count_as_matches():
    geocoders = [
        house("far", "הרצל", "5", "רמת גן"),
        house("right", "הרצל", "5", "פתח תקווה"),
        street("typo", "דיזנגוף", "תל אביב"),
    ]
    assert (
        merge_candidates("הרצל 5 פתח תקוה", [], geocoders, 10)[0]["locationRef"]["placeRef"]
        == "right"
    )
    assert merge_candidates("דיזינגוף", [], geocoders, 10)[0]["locationRef"]["placeRef"] == "typo"


def test_equal_candidates_alternate_with_stops_first_and_respect_the_limit():
    stops = [stop(str(n), f"קניון עזריאלי {n}", "עיר: תל אביב יפו") for n in range(4)]
    geocoders = [poi(f"p{n}", f"מרכז עזריאלי {n}", "תל־אביב–יפו") for n in range(4)]
    merged = merge_candidates("עזריאלי", stops, geocoders, 5)
    assert [item["kind"] for item in merged] == ["stop", "poi", "stop", "poi", "stop"]


def test_same_stop_or_place_is_listed_once_and_inputs_are_not_modified():
    stops = [stop("1", "עזריאלי", "עיר: תל אביב יפו"), stop("1", "עזריאלי", "עיר: תל אביב יפו")]
    geocoders = [poi("p", "עזריאלי", None), poi("p", "עזריאלי", None)]
    before = [dict(item) for item in stops + geocoders]
    merged = merge_candidates("עזריאלי", stops, geocoders, 10)
    assert len(merged) == 2
    assert stops + geocoders == before


def test_different_places_with_one_name_are_all_kept():
    geocoders = [
        poi("b1", "בנק הפועלים", "הרצליה"),
        poi("b2", "בנק הפועלים", "הרצליה"),
        street("s1", "הרצל", "רמת גן", at=(32.08, 34.81)),
        street("s2", "הרצל", "תל אביב", at=(32.06, 34.77)),
        street("s3", "הרצל", None, at=(31.25, 34.79)),
        street("s4", "הרצל", None, at=(32.80, 35.00)),
    ]
    merged = merge_candidates("הרצל", [], geocoders, 10)
    assert {item["locationRef"]["placeRef"] for item in merged} >= {"s1", "s2", "s3", "s4"}
    assert len(merge_candidates("בנק הפועלים", [], geocoders, 10)[:2]) == 2


def test_only_the_word_being_typed_matches_as_a_prefix():
    geocoders = [
        poi("bank", "בנק הפועלים", "הרצליה"),
        street("street", "הפועל", "הרצליה"),
        poi("center", "דיזנגוף סנטר", "תל אביב"),
    ]
    # "הפועל" is a finished word here, so "הפועלים" is a different word.
    merged = merge_candidates("הפועל 13 הרצליה", [], geocoders, 10)
    assert [item["locationRef"]["placeRef"] for item in merged][:2] == ["street", "bank"]
    assert merged[0]["locationRef"]["placeRef"] == "street"
    typing = merge_candidates("דיזנגוף סנ", [], list(reversed(geocoders)), 10)
    assert typing[0]["locationRef"]["placeRef"] == "center"
    finished_city = merge_candidates("הפועל הרצל", [], geocoders, 10)
    assert finished_city[0]["locationRef"]["placeRef"] == "street"


def test_english_street_with_a_hebrew_city_is_not_treated_as_missing_the_city():
    geocoders = [
        house("right", "Ben Yehuda", "20", "תל־אביב–יפו"),
        poi("bar", "Bar Yehuda", "Tel-Aviv"),
        poi("street1", "street 1", "Jerusalem"),
        house("jaffa", "Jaffa", "97", "ירושלים | القدس"),
    ]
    merged = merge_candidates("Ben Yehuda 20 Tel Aviv", [], list(reversed(geocoders)), 10)
    assert [item["locationRef"]["placeRef"] for item in merged][:2] == ["right", "bar"]
    # "Street" names nothing: the house on Jaffa precedes a place merely called "street 1".
    merged = merge_candidates("Jaffa Street 97 Jerusalem", [], geocoders, 10)
    assert merged[0]["locationRef"]["placeRef"] == "jaffa"


def test_fallback_stops_are_judged_by_every_label_the_index_holds():
    # Displayed in Hebrew; the index matched its English alias, with a typo in the query.
    airport = stop("airport", "נתב''ג", "")
    fallback = {"mot:stop:airport": {"name": ["נתבג", "ben gurion airport"], "context": ""}}
    geocoders = [
        poi("p", "Ben Gurion Airport", "Ramla Subdistrict"),
        street("s", "Ben Gurion", "בית שאן"),
    ]
    merged = merge_candidates(
        "Ben Gurion Airoport", [airport], geocoders, 10, stop_fallback=fallback
    )
    assert [item["locationRef"].get("placeRef", "stop") for item in merged] == ["stop", "p", "s"]
    # Transliterations of one name are one word.
    arye = stop("arye", "Kiriyat Arieh", "")
    labels = {"mot:stop:arye": {"name": ["kiriyat arieh", "petah tikva kiryat arye"]}}
    merged = merge_candidates(
        "Petach Tikva Kiryat Arye",
        [arye],
        [poi("k", "Kiryat Arye", "Petah Tikva")],
        10,
        stop_fallback=labels,
    )
    assert merged[0]["id"] == "mot:stop:arye"


def test_exact_house_with_a_city_label_in_another_script_precedes_places_without_the_number():
    geocoders = [
        house("right", "Dizengoff", "100", "תל־אביב–יפו"),
        poi("meir", "Meir Dizengoff", "Tel-Aviv"),
        poi("cafe", "Cafe Dizengoff", "Tel-Aviv"),
    ]
    merged = merge_candidates("Dizengoff 100 Tel Aviv", [], geocoders, 10)
    assert merged[0]["locationRef"]["placeRef"] == "right"
