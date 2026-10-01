import copy
import hashlib
import json
from dataclasses import replace
from pathlib import Path

import httpx
import pytest

from tools.evaluate_search import (
    EARTH_M,
    VENUE_EARTH_M,
    SearchCase,
    _canonical_expected_stop_ref,
    add_provenance,
    api_types_for,
    correct_saved_exact_stop_scores,
    correlate_process_timings,
    finalize_process_timings,
    haversine_m,
    load_cases,
    main,
    request_params,
    review_markdown,
    run_and_write_evaluation,
    run_evaluation,
    score_response,
    summarize,
    summarize_saved_osm_address_near_groups,
    write_exclusive,
)

ROOT = Path(__file__).resolve().parents[3]
PLACES = ROOT / "poc/corpora/places.json"
VENUES = ROOT / "poc/corpora/places-venues.json"
SUPPLEMENT = ROOT / "services/api/tests/fixtures/m4-api-search-language-variants-20260930.json"


def case(*, types=("poi",), near=None):
    return SearchCase(
        id="T001",
        source_case_id="T001",
        variant="primary",
        query="Central Station",
        language="en",
        language_assignment="explicit",
        query_script="latin",
        category="near_dependent",
        api_types=types,
        expected_place="target",
        latitude=32.0,
        longitude=35.0,
        tolerance_m=1000.0,
        near=near,
        corpus="test",
    )


def _payload(items, *, matched=("poi",), unavailable=(), generation_id=None):
    payload = {
        "data": items,
        "matchedTypes": list(matched),
        "unavailableTypes": list(unavailable),
        "partial": bool(unavailable),
    }
    if generation_id is not None:
        payload["meta"] = {"generationId": generation_id}
    return payload


def test_frozen_corpus_variants_preserve_languages_categories_targets_and_near():
    cases, hashes, supplemental = load_cases(PLACES, VENUES, SUPPLEMENT)
    assert len(cases) == (
        148
        + len(supplemental["venueVariants"])
        + len(supplemental["acceptedGtfsStopVariants"])
        + len(supplemental.get("acceptedOsmAddressVariants", []))
    )
    assert len(hashes) == 3
    assert len(supplemental["venueVariants"]) == 26
    assert len(supplemental["acceptedGtfsStopVariants"]) == 2
    aliases = [item for item in cases if item.corpus == "venues-language-variants"]
    assert sum(item.language == "en" for item in aliases) == 20
    assert sum(item.language == "he" for item in aliases) == 6
    by_id = {item.id: item for item in cases}
    assert by_id["P095"].near == (32.08, 34.78)
    assert by_id["P095"].api_types == ("stop", "station", "poi", "address")
    assert by_id["P051"].api_types == ("address",)
    assert by_id["P001"].api_types == ("stop", "station")
    assert by_id["P001"].earth_radius_m == EARTH_M
    assert by_id["V001"].earth_radius_m == VENUE_EARTH_M
    assert by_id["V001:alt_query_en"].earth_radius_m == VENUE_EARTH_M
    assert by_id["V001"].language == "he"
    assert by_id["V001"].language_assignment == "native Hebrew query"
    assert by_id["V006"].language == "he"
    assert by_id["V006"].language_assignment.startswith("API default he")
    assert by_id["V001:alt_query_en"].language == "en"
    assert by_id["V007:alt_query_he"].language == "he"
    assert by_id["GTFS-TRANS-13583-en"].api_types == ("stop",)
    assert by_id["GTFS-TRANS-13583-en"].expected_stop_id == "13583"
    assert by_id["GTFS-TRANS-13583-en"].tolerance_m is None
    assert supplemental["acceptedGtfsProvenance"]["feedSha256"] == (
        "8629a73c3f6ff024a78e9b8c83602c09180e13e597b82b98a4377a78f3dd2fd9"
    )
    address_variants = supplemental.get("acceptedOsmAddressVariants", [])
    address_cases = [item for item in cases if item.corpus == "accepted-osm-addresses"]
    assert len(address_cases) == len(address_variants)
    assert all(item.api_types == ("address",) for item in address_cases)
    if address_variants:
        provenance = supplemental["acceptedOsmAddressProvenance"]
        assert provenance["pbfSha256"]
        assert sum(item.language == "en" for item in address_cases) == 6
        assert sum(item.language == "he" for item in address_cases) == 1
        assert all("explicit" in item.language_assignment for item in address_cases)
        assert all(
            item.source_reference["pbfSha256"] == provenance["pbfSha256"] for item in address_cases
        )
    places = json.loads(PLACES.read_text(encoding="utf-8"))
    by_source = {item["id"]: item for item in places["cases"]}
    for left_id, right_id in supplemental["addressLanguagePairsAlreadyPresent"]:
        left, right = by_source[left_id], by_source[right_id]
        assert {left["lang"], right["lang"]} == {"he", "en"}
        assert left["expect"]["lat"] == right["expect"]["lat"]
        assert left["expect"]["lon"] == right["expect"]["lon"]


@pytest.mark.parametrize(
    ("category", "expected"),
    [
        ("station", ("stop", "station")),
        ("poi_landmark", ("poi",)),
        ("neighborhood", ("poi",)),
        ("address", ("address",)),
        ("misspelling", ("stop", "station", "poi", "address")),
        ("translit", ("stop", "station", "poi", "address")),
        ("near_dependent", ("stop", "station", "poi", "address")),
    ],
)
def test_category_selector_mapping(category, expected):
    assert api_types_for(category) == expected


def test_query_params_use_original_near_and_fixed_limit():
    selected = case(types=("stop", "station"), near=(32.123456789, 34.876543219))
    assert request_params(selected) == [
        ("q", "Central Station"),
        ("lang", "en"),
        ("type", "stop"),
        ("type", "station"),
        ("limit", "10"),
        ("near", "32.123456789,34.876543219"),
    ]


def test_top1_and_top5_are_scored_separately_without_distance_rounding():
    selected = case()
    items = [
        {
            "kind": "poi",
            "displayName": "wrong first",
            "coordinates": {"latitude": 32.02, "longitude": 35.0},
            "locationRef": {"kind": "place", "placeRef": "ref-1"},
        },
        {
            "kind": "poi",
            "displayName": "target",
            "coordinates": {"latitude": 32.0, "longitude": 35.0},
            "precision": "numbered_label",
            "languageUsed": "en",
            "locationRef": {"kind": "place", "placeRef": "ref-2"},
        },
    ]
    scored = score_response(selected, 200, _payload(items))
    assert scored["outcome"] == "success"
    assert scored["top1Hit"] is False
    assert scored["top5Hit"] is True and scored["top5HitRank"] == 2
    assert scored["candidates"][1]["locationRef"]["placeRef"] == "ref-2"
    assert scored["candidates"][1]["precision"] == "numbered_label"


def test_top5_does_not_promote_a_raw_rank_six_hit():
    selected = case()
    duplicates = [
        {
            "kind": "poi",
            "displayName": f"wrong {index}",
            "coordinates": {"latitude": 32.02 + index * 0.001, "longitude": 35.0},
            "locationRef": {"kind": "place", "placeRef": f"wrong-{index}"},
        }
        for index in range(4)
    ]
    items = [
        *duplicates,
        duplicates[0],
        {
            "kind": "poi",
            "displayName": "target",
            "coordinates": {"latitude": 32.0, "longitude": 35.0},
            "locationRef": {"kind": "place", "placeRef": "target"},
        },
    ]
    scored = score_response(selected, 200, _payload(items))
    assert scored["top1Hit"] is False
    assert scored["top5Hit"] is False
    assert scored["top5HitRank"] is None
    assert scored["candidates"][4]["duplicateOfDistinctRank"] == 1
    assert scored["candidates"][5]["distinctRank"] == 5
    assert scored["candidates"][5]["rank"] == 6


def test_top5_reports_raw_and_distinct_rank_for_a_hit_in_first_five():
    selected = case()
    duplicate = {
        "kind": "poi",
        "displayName": "wrong",
        "coordinates": {"latitude": 32.02, "longitude": 35.0},
        "locationRef": {"kind": "place", "placeRef": "wrong"},
    }
    target = {
        "kind": "poi",
        "displayName": "target",
        "coordinates": {"latitude": 32.0, "longitude": 35.0},
        "locationRef": {"kind": "place", "placeRef": "target"},
    }
    scored = score_response(selected, 200, _payload([duplicate, duplicate, duplicate, target]))
    assert scored["top5Hit"] is True
    assert scored["top5HitRank"] == 4
    assert scored["top5DistinctRank"] == 2


def test_tolerance_boundary_uses_full_precision_distance():
    selected = case()
    point = {"kind": "poi", "coordinates": {"latitude": 32.01, "longitude": 35.0}}
    distance = haversine_m(32.01, 35.0, selected.latitude, selected.longitude)
    exact = score_response(replace(selected, tolerance_m=distance), 200, _payload([point]))
    below = score_response(replace(selected, tolerance_m=distance - 1e-8), 200, _payload([point]))
    assert exact["top1DistanceMeters"] == distance
    assert exact["top1Hit"] is True
    assert below["top1Hit"] is False


def test_venue_results_use_the_historical_6371000m_radius():
    point = {"kind": "poi", "coordinates": {"latitude": 32.01, "longitude": 35.0}}
    venue_distance = haversine_m(32.01, 35.0, 32.0, 35.0, VENUE_EARTH_M)
    places_distance = haversine_m(32.01, 35.0, 32.0, 35.0, EARTH_M)
    tolerance = (venue_distance + places_distance) / 2
    venue_case = replace(case(), tolerance_m=tolerance, earth_radius_m=VENUE_EARTH_M)
    places_case = replace(case(), tolerance_m=tolerance, earth_radius_m=EARTH_M)
    venue_score = score_response(venue_case, 200, _payload([point]))
    places_score = score_response(places_case, 200, _payload([point]))
    assert venue_score["top1DistanceMeters"] == venue_distance
    assert venue_score["top1Hit"] is True
    assert places_score["top1DistanceMeters"] == places_distance
    assert places_score["top1Hit"] is False


def test_candidates_must_belong_to_a_requested_and_matched_category():
    selected = case(types=("poi", "address"))
    wrong_requested_kind = score_response(
        selected,
        200,
        _payload(
            [{"kind": "stop", "coordinates": {"latitude": 32.0, "longitude": 35.0}}],
            matched=("poi", "address"),
        ),
    )
    assert wrong_requested_kind["outcome"] == "invalid_response"
    assert wrong_requested_kind["top1Hit"] is False
    assert wrong_requested_kind["scoreEligible"] is False

    unavailable_candidate = score_response(
        case(),
        200,
        _payload(
            [{"kind": "poi", "coordinates": {"latitude": 32.0, "longitude": 35.0}}],
            matched=(),
            unavailable=("poi",),
        ),
    )
    assert unavailable_candidate["outcome"] == "invalid_response"
    assert unavailable_candidate["top1Hit"] is False
    assert unavailable_candidate["scoreEligible"] is False


def test_service_success_requires_current_generation_and_all_requested_categories():
    selected = case(types=("poi", "address"))
    complete = score_response(
        selected,
        200,
        _payload([], matched=("poi", "address"), generation_id="current"),
        expected_generation_id="current",
    )
    assert complete["responseValid"] is True
    assert complete["generationCurrent"] is True
    assert complete["categoriesComplete"] is True
    assert complete["serviceSuccess"] is True

    partial = score_response(
        selected,
        200,
        _payload(
            [],
            matched=("poi",),
            unavailable=("address",),
            generation_id="current",
        ),
        expected_generation_id="current",
    )
    assert partial["responseValid"] is True
    assert partial["generationCurrent"] is True
    assert partial["categoriesComplete"] is False
    assert partial["serviceSuccess"] is False

    stale = score_response(
        selected,
        200,
        _payload([], matched=("poi", "address"), generation_id="old"),
        expected_generation_id="current",
    )
    assert stale["outcome"] == "generation_mismatch"
    assert stale["responseValid"] is True
    assert stale["generationCurrent"] is False
    assert stale["categoriesComplete"] is True
    assert stale["serviceSuccess"] is False


def test_translated_stop_uses_exact_source_identity_without_invented_tolerance():
    selected = next(
        item
        for item in load_cases(PLACES, VENUES, SUPPLEMENT)[0]
        if item.id == "GTFS-TRANS-13583-en"
    )
    result = score_response(
        selected,
        200,
        _payload(
            [
                {
                    "kind": "stop",
                    "locationRef": {"kind": "stop", "stopId": "mot:stop:13583"},
                }
            ],
            matched=("stop",),
        ),
    )
    assert selected.expected_stop_id == "13583"  # frozen corpus value is unchanged
    assert result["scoreRule"] == "exact_stop_reference"
    assert result["top1Hit"] and result["top5Hit"]
    # A different stop with the same label is not the expected identity.
    other = score_response(
        selected,
        200,
        _payload(
            [{"kind": "stop", "locationRef": {"kind": "stop", "stopId": "mot:stop:13561"}}],
            matched=("stop",),
        ),
    )
    assert not other["top1Hit"] and not other["top5Hit"]


def test_valid_empty_partial_unavailable_and_malformed_are_distinct():
    selected = case(types=("stop", "station", "poi", "address"))
    empty = score_response(
        selected, 200, _payload([], matched=("stop", "station", "poi", "address"))
    )
    assert empty["outcome"] == "valid_empty" and empty["scoreEligible"]
    partial = score_response(
        selected, 200, _payload([], matched=("stop", "station"), unavailable=("poi", "address"))
    )
    assert partial["outcome"] == "partial"
    unavailable = score_response(
        selected, 200, _payload([], matched=(), unavailable=selected.api_types)
    )
    assert unavailable["outcome"] == "unavailable"
    http_error = score_response(selected, 503, {"code": "CATEGORY_UNAVAILABLE"})
    assert http_error["outcome"] == "http_error"
    malformed = score_response(selected, 200, {"data": [], "matchedTypes": ["stop"]})
    assert malformed["outcome"] == "invalid_response"
    stale = score_response(
        selected,
        200,
        _payload([], matched=selected.api_types, generation_id="old"),
        expected_generation_id="current",
    )
    assert stale["outcome"] == "generation_mismatch"
    assert stale["responseValid"] is True


def test_log_correlation_rejects_missing_duplicate_and_status_mismatch():
    records = [
        {"requestId": "a" * 32, "httpStatus": 200},
        {"requestId": "b" * 32, "httpStatus": 200},
        {"requestId": "c" * 32, "httpStatus": 503},
        {"requestId": None, "httpStatus": 200},
    ]
    logs = "\n".join(
        [
            f"request_id={'a' * 32} route=/v1/places status=200 duration_ms=12.5",
            f"request_id={'b' * 32} route=/v1/places status=200 duration_ms=11.0",
            f"request_id={'b' * 32} route=/v1/places status=200 duration_ms=11.1",
            f"request_id={'c' * 32} route=/v1/places status=200 duration_ms=9.0",
        ]
    )
    summary = correlate_process_timings(records, logs)
    assert summary == {
        "verified": False,
        "requestCount": 4,
        "matchedCount": 1,
        "unmatchedCount": 3,
    }
    assert records[0]["processDurationMs"] == 12.5
    assert records[1]["logCorrelationStatus"] == "ambiguous_duplicate_log_entries"
    assert records[2]["logCorrelationStatus"] == "log_status_mismatch"
    assert records[3]["logCorrelationStatus"] == "missing_request_id"


def test_duplicate_response_request_ids_are_ambiguous_even_with_one_log_line():
    request_id = "d" * 32
    records = [
        {"requestId": request_id, "httpStatus": 200},
        {"requestId": request_id, "httpStatus": 200},
    ]
    log = f"request_id={request_id} route=/v1/places status=200 duration_ms=10.0"
    summary = correlate_process_timings(records, log)
    assert summary["matchedCount"] == 0
    assert all(item["processDurationMs"] is None for item in records)
    assert all(
        item["logCorrelationStatus"] == "ambiguous_duplicate_response_ids" for item in records
    )


def test_runner_fixed_denominator_seeded_repeats_and_unavailable_are_not_retried():
    selected_cases = [case(), case()]
    calls = []

    def send(params):
        calls.append(params)
        request = httpx.Request("GET", "http://api.test/v1/places")
        return httpx.Response(
            503,
            json={"code": "CATEGORY_UNAVAILABLE"},
            request=request,
            headers={"X-Request-ID": f"{len(calls):032x}"},
        )

    result = run_evaluation(
        selected_cases, send, log_text=None, seed=15, captured_at="2026-09-30T00:00:00Z"
    )
    assert len(calls) == 8
    assert result["parameters"]["requestCount"] == 8
    assert result["summary"]["overall"]["denominator"] == 2
    assert result["summary"]["overall"]["top1"] == 0
    assert result["summary"]["firstPassOutcomes"] == {"http_error": 2}
    assert result["timing"]["correlation"]["verified"] is False
    assert result["timing"]["warm"]["byCategory"]["near_dependent"]["apiProcess"] == {
        "p50Ms": None,
        "p95Ms": None,
        "maxMs": None,
    }
    assert result["parameters"]["retryCount"] == 0
    assert result["parameters"]["warmOrder"] == [1, 0]
    assert result["timing"]["firstPass"]["apiProcess"] == {
        "p50Ms": None,
        "p95Ms": None,
        "maxMs": None,
    }
    assert result["summary"]["byCorpus"]["test"]["total"] == 2


def test_fast_503_timings_are_descriptive_but_not_latency_acceptance():
    requests = []

    def send(_params):
        request_id = f"{len(requests) + 1:032x}"
        response = httpx.Response(
            503,
            json={"code": "CATEGORY_UNAVAILABLE"},
            request=httpx.Request("GET", "http://api.test/v1/places"),
            headers={"X-Request-ID": request_id},
        )
        requests.append((request_id, response.status_code))
        return response

    raw = run_evaluation([case()], send, log_text=None, expected_generation_id="current")
    log_text = "\n".join(
        f"request_id={request_id} route=/v1/places status={status} duration_ms=1.0"
        for request_id, status in requests
    )
    finalized = finalize_process_timings(
        raw,
        log_text,
        log_sha256="log-hash",
        source_result_sha256="raw-hash",
    )

    latency = finalized["timing"]["allRequests"]
    assert latency["allRequestApiProcess"]["p95Ms"] == 1.0
    assert latency["allRequestApiProcess"]["sampleCount"] == 4
    assert latency["successfulServiceCount"] == 0
    assert latency["successfulServiceApiProcess"]["p95Ms"] is None
    assert latency["latencyAcceptanceEligible"] is False
    assert "unsuccessful_http_response" in latency["latencyAcceptanceBlockers"]


def test_partial_or_stale_searches_cannot_make_all_request_latency_eligible():
    requested = case(types=("poi", "address"))
    requests = []
    call_count = 0

    def send(_params):
        nonlocal call_count
        call_count += 1
        request_id = f"{call_count:032x}"
        if call_count == 2:
            payload = _payload(
                [],
                matched=("poi",),
                unavailable=("address",),
                generation_id="current",
            )
        elif call_count == 3:
            payload = _payload([], matched=("poi", "address"), generation_id="old")
        else:
            payload = _payload([], matched=("poi", "address"), generation_id="current")
        response = httpx.Response(
            200,
            json=payload,
            request=httpx.Request("GET", "http://api.test/v1/places"),
            headers={"X-Request-ID": request_id},
        )
        requests.append((request_id, response.status_code))
        return response

    raw = run_evaluation([requested], send, log_text=None, expected_generation_id="current")
    log_text = "\n".join(
        f"request_id={request_id} route=/v1/places status={status} duration_ms=8.0"
        for request_id, status in requests
    )
    finalized = finalize_process_timings(
        raw,
        log_text,
        log_sha256="log-hash",
        source_result_sha256="raw-hash",
    )

    first_pass = finalized["timing"]["firstPass"]["latencyAcceptance"]
    all_requests = finalized["timing"]["allRequests"]
    assert first_pass["latencyAcceptanceEligible"] is True
    assert first_pass["successfulServiceCount"] == 1
    assert all_requests["validResponseCount"] == 4
    assert all_requests["currentGenerationCount"] == 3
    assert all_requests["fullRequestedCategoriesCount"] == 3
    assert all_requests["successfulServiceCount"] == 2
    assert all_requests["latencyAcceptanceEligible"] is False
    assert "stale_or_unverified_generation" in all_requests["latencyAcceptanceBlockers"]
    assert "incomplete_category_execution" in all_requests["latencyAcceptanceBlockers"]


def test_offline_timing_finalizer_creates_a_derived_copy_without_changing_raw_result():
    selected_cases = [case()]
    calls = []

    def send(params):
        calls.append(params)
        request_id = f"{len(calls):032x}"
        return httpx.Response(
            200,
            json=_payload([], generation_id="current"),
            request=httpx.Request("GET", "http://api.test/v1/places"),
            headers={"X-Request-ID": request_id},
        )

    raw = run_evaluation(
        selected_cases,
        send,
        log_text=None,
        captured_at="2026-09-30T00:00:00Z",
        expected_generation_id="current",
    )
    raw_first_pass = raw["records"][0]["firstPass"]["processDurationMs"]
    log_text = "\n".join(
        f"request_id={index:032x} route=/v1/places status=200 duration_ms=12.5"
        for index in range(1, len(calls) + 1)
    )
    finalized = finalize_process_timings(
        raw,
        log_text,
        log_sha256="log-hash",
        source_result_sha256="raw-hash",
    )
    assert raw_first_pass is None
    assert raw["records"][0]["firstPass"]["processDurationMs"] is None
    assert raw["timing"]["allRequests"]["successfulServiceCount"] == 4
    assert raw["timing"]["allRequests"]["latencyAcceptanceEligible"] is False
    assert raw["timing"]["allRequests"]["successfulServiceApiProcess"]["p95Ms"] is None
    assert finalized["timing"]["correlation"]["verified"] is True
    assert finalized["timing"]["firstPass"]["apiProcess"]["p95Ms"] == 12.5
    assert finalized["timing"]["allRequests"]["latencyAcceptanceEligible"] is True
    assert finalized["provenance"]["containerLogSha256"] == "log-hash"
    assert finalized["timingFinalization"]["sourceResultSha256"] == "raw-hash"


def test_finalize_cli_reads_saved_result_and_writes_a_new_exclusive_artifact(tmp_path, monkeypatch):
    selected = case()
    request_ids = [f"{index:032x}" for index in range(1, 5)]
    request_index = 0

    def send(_params):
        nonlocal request_index
        request_id = request_ids[request_index]
        request_index += 1
        return httpx.Response(
            200,
            json=_payload([]),
            request=httpx.Request("GET", "http://api.test/v1/places"),
            headers={"X-Request-ID": request_id},
        )

    saved = run_evaluation(
        [selected],
        send,
        log_text=None,
        captured_at="2026-09-30T00:00:00Z",
    )
    source = tmp_path / "raw.json"
    log = tmp_path / "api.log"
    output = tmp_path / "final.json"
    source.write_text(json.dumps(saved), encoding="utf-8")
    log.write_text(
        "".join(
            f"request_id={request_id} route=/v1/places status=200 duration_ms=8.5\n"
            for request_id in request_ids
        ),
        encoding="utf-8",
    )
    monkeypatch.setattr(
        "sys.argv",
        [
            "evaluate_search.py",
            "--finalize-input",
            str(source),
            "--container-log-file",
            str(log),
            "--output",
            str(output),
        ],
    )

    assert main() == 0
    derived = json.loads(output.read_text(encoding="utf-8"))
    assert derived["timing"]["correlation"]["verified"] is True
    assert derived["timing"]["firstPass"]["apiProcess"]["p95Ms"] == 8.5
    assert saved["timing"]["correlation"]["verified"] is False
    with pytest.raises(SystemExit):
        main()


def test_exclusive_writer_refuses_to_replace_prior_evidence(tmp_path):
    output = tmp_path / "evidence.json"
    write_exclusive(output, "prior")
    with pytest.raises(FileExistsError):
        write_exclusive(output, "replacement")
    assert output.read_text(encoding="utf-8") == "prior"


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        ("13583", "mot:stop:13583"),
        ("mot:stop:13583", "mot:stop:13583"),
        ("00123", "mot:stop:00123"),
    ],
)
def test_canonical_expected_stop_ref_preserves_source_digits(value, expected):
    assert _canonical_expected_stop_ref(value) == expected


def test_canonical_expected_stop_ref_keeps_leading_zero_ids_distinct():
    assert _canonical_expected_stop_ref("00123") != _canonical_expected_stop_ref("123")


def _saved_stop_record(case_id, source_id, candidate_refs):
    candidates = [
        {
            "rank": index,
            "distinctRank": index,
            "kind": "stop",
            "locationRef": {"kind": "stop", "stopId": ref},
            "coordinates": {"latitude": 32.0, "longitude": 35.0},
            "distanceMeters": 0.0,
        }
        for index, ref in enumerate(candidate_refs, 1)
    ]
    scored = {
        "top1Hit": False,
        "top5Hit": False,
        "top5HitRank": None,
        "top5DistinctRank": None,
        "scoreRule": "exact_stop_reference",
        "outcome": "success",
        "candidates": candidates,
        "clientRoundTripMs": 12.0,
        "processDurationMs": 4.0,
    }
    return {
        "case": {
            "id": case_id,
            "variant": "query",
            "query": "frozen query",
            "language": "en",
            "queryScript": "latin",
            "category": "translated_stop",
            "apiTypes": ["stop"],
            "expected": {
                "place": "Expected stop",
                "latitude": 32.0,
                "longitude": 35.0,
                "toleranceMeters": None,
                "expectedStopId": source_id,
            },
            "near": None,
            "corpus": "accepted-gtfs-stops",
            "sourceReference": {"sourceStopId": source_id},
        },
        "firstPass": scored,
        "warmRepeats": [copy.deepcopy(scored)],
    }


def test_offline_exact_stop_correction_uses_saved_candidates_and_preserves_other_scores():
    places = {
        "case": {"id": "P001", "category": "station", "language": "he", "corpus": "places-100"},
        "firstPass": {"top1Hit": True, "top5Hit": True, "outcome": "success"},
        "warmRepeats": [],
    }
    first_gtfs = _saved_stop_record(
        "GTFS-TRANS-13583-en", "13583", ["mot:stop:13561", "mot:stop:13583"]
    )
    second_gtfs = _saved_stop_record("GTFS-TRANS-42658-en", "42658", ["mot:stop:42658"])
    saved = {
        "summary": summarize([places, first_gtfs, second_gtfs]),
        "records": [places, first_gtfs, second_gtfs],
        "timing": {"firstPass": {"apiProcess": {"p95Ms": 8.5}}},
    }
    original = copy.deepcopy(saved)
    corrected = correct_saved_exact_stop_scores(saved, source_result_sha256="saved-hash")
    corrected_by_id = {row["case"]["id"]: row for row in corrected["records"]}
    first = corrected_by_id["GTFS-TRANS-13583-en"]
    second = corrected_by_id["GTFS-TRANS-42658-en"]

    assert first["firstPass"]["top1Hit"] is False
    assert first["firstPass"]["top5Hit"] is True
    assert first["firstPass"]["top5HitRank"] == 2
    assert first["warmRepeats"][0]["top5Hit"] is True
    assert second["firstPass"]["top1Hit"] is True
    assert second["firstPass"]["top5Hit"] is True
    assert first["case"]["expected"]["expectedStopId"] == "13583"
    assert first["case"]["sourceReference"]["sourceStopId"] == "13583"
    assert first["firstPass"]["candidates"] == original["records"][1]["firstPass"]["candidates"]
    assert first["firstPass"]["clientRoundTripMs"] == 12.0
    assert corrected["timing"] == original["timing"]
    assert (
        corrected["summary"]["byCorpus"]["places-100"]
        == original["summary"]["byCorpus"]["places-100"]
    )
    assert corrected["exactStopScoringCorrection"]["sourceResultSha256"] == "saved-hash"
    assert corrected["exactStopScoringCorrection"]["originalSummary"] == original["summary"]
    assert saved == original


def test_offline_exact_stop_correction_rejects_source_id_mismatch():
    bad = _saved_stop_record("GTFS-TRANS-13583-en", "0013583", ["mot:stop:13583"])
    other = _saved_stop_record("GTFS-TRANS-42658-en", "42658", ["mot:stop:42658"])
    with pytest.raises(ValueError, match="source ID mismatch"):
        correct_saved_exact_stop_scores(
            {"records": [bad, other]}, source_result_sha256="saved-hash"
        )


def test_near_breakdown_uses_only_saved_accepted_osm_address_metadata():
    rows = [
        {
            "case": {"id": "near", "corpus": "accepted-osm-addresses", "near": {"latitude": 1}},
            "firstPass": {"top1Hit": True, "top5Hit": True},
        },
        {
            "case": {"id": "without", "corpus": "accepted-osm-addresses", "near": None},
            "firstPass": {"top1Hit": False, "top5Hit": True},
        },
        {
            "case": {"id": "other", "corpus": "places-100", "near": None},
            "firstPass": {"top1Hit": True, "top5Hit": True},
        },
    ]
    breakdown = summarize_saved_osm_address_near_groups(rows)
    assert breakdown["groups"]["near_supplied"]["caseIds"] == ["near"]
    assert breakdown["groups"]["near_supplied"]["top1"] == 1
    assert breakdown["groups"]["near_not_supplied"]["caseIds"] == ["without"]
    assert "no inference" in breakdown["basis"]


def test_address_level_is_retained_and_review_sheet_shows_it_with_safe_cells():
    address_case = case(types=("address",))
    address_case = replace(address_case, id="ADDR", corpus="accepted-osm-addresses")
    scored = score_response(
        address_case,
        200,
        _payload(
            [
                {
                    "kind": "address",
                    "displayName": "Street | line\ncontinued",
                    "addressLevel": "house",
                    "precision": "numbered_label",
                    "languageUsed": "en",
                    "coordinates": {"latitude": 32.0, "longitude": 35.0},
                }
            ],
            matched=("address",),
        ),
    )
    assert scored["candidates"][0]["addressLevel"] == "house"
    row = {
        "case": {
            "id": "ADDR",
            "variant": "primary",
            "query": "street query",
            "language": "en",
            "queryScript": "latin",
            "category": "address",
            "corpus": "accepted-osm-addresses",
            "expected": {"place": "expected", "latitude": 32, "longitude": 35},
            "near": None,
        },
        "firstPass": scored,
        "warmRepeats": [],
    }
    result = {
        "capturedAt": "2026-10-01T00:00:00Z",
        "summary": {"overall": {"top1": 0, "top5": 0, "denominator": 1}},
        "records": [row],
    }
    review = review_markdown(result)
    assert "Address level" in review
    assert "| house | numbered_label | en |" in review
    assert "Street \\| line continued" in review
    assert "H4 usability | H4 verdict" in review


def test_provenance_includes_generation_inputs_and_sidecar_file_hashes(tmp_path):
    manifest = tmp_path / "manifest.json"
    source_hashes = tmp_path / "source-hashes.json"
    runtime = tmp_path / "runtime.json"
    manifest.write_text(
        json.dumps(
            {
                "generationId": "generation-1",
                "engineDigest": "sha256:engine",
                "inputs": {"feed.zip": {"sha256": "feed-hash"}},
                "artifacts": {"reference": {"sha256": "reference-hash"}},
            }
        ),
        encoding="utf-8",
    )
    source_hashes.write_text('{"app.py":"source-hash"}', encoding="utf-8")
    runtime.write_text('{"generationId":"generation-1"}', encoding="utf-8")
    result = {}
    add_provenance(
        result,
        api_url="http://127.0.0.1:8000/",
        manifest_path=manifest,
        source_hashes_path=source_hashes,
        runtime_evidence_path=runtime,
        container_log_path=None,
        corpus_hashes={"places.json": "corpus-hash"},
        supplemental={},
    )
    provenance = result["provenance"]
    assert provenance["generationInputs"] == {"feed.zip": "feed-hash"}
    assert provenance["apiSourceHashes"] == {"app.py": "source-hash"}
    assert provenance["apiSourceHashFileSha256"]
    assert provenance["runtimeEvidenceSha256"]


def test_missing_provenance_fails_before_requests_or_output_files(tmp_path):
    manifest = tmp_path / "manifest.json"
    manifest.write_text('{"generationId":"generation-1"}', encoding="utf-8")
    missing_hashes = tmp_path / "missing-source-hashes.json"
    output = tmp_path / "result.json"
    review = tmp_path / "review.md"
    sent = 0

    def send(_params):
        nonlocal sent
        sent += 1
        return httpx.Response(503)

    with pytest.raises(FileNotFoundError):
        run_and_write_evaluation(
            cases=[case()],
            send=send,
            seed=20260930,
            expected_generation_id="generation-1",
            api_url="http://api.test",
            manifest_path=manifest,
            source_hashes_path=missing_hashes,
            runtime_evidence_path=None,
            corpus_hashes={"places.json": "frozen-hash"},
            supplemental={},
            output_path=output,
            review_path=review,
        )

    assert sent == 0
    assert not output.exists()
    assert not review.exists()


def test_preflight_provenance_snapshot_survives_source_changes_during_requests(tmp_path):
    manifest = tmp_path / "manifest.json"
    source_hashes = tmp_path / "source-hashes.json"
    runtime = tmp_path / "runtime.json"
    manifest.write_text(
        '{"generationId":"generation-1","inputs":{"feed":{"sha256":"feed-v1"}}}',
        encoding="utf-8",
    )
    source_hashes.write_text('{"app.py":"source-v1"}', encoding="utf-8")
    runtime.write_text('{"generationId":"generation-1"}', encoding="utf-8")
    expected_manifest_hash = hashlib.sha256(manifest.read_bytes()).hexdigest()
    output = tmp_path / "result.json"
    review = tmp_path / "review.md"
    changed = False

    def send(_params):
        nonlocal changed
        if not changed:
            changed = True
            manifest.write_text('{"generationId":"mutated-after-preflight"}', encoding="utf-8")
            source_hashes.unlink()
        return httpx.Response(503)

    run_and_write_evaluation(
        cases=[case()],
        send=send,
        seed=20260930,
        expected_generation_id="generation-1",
        api_url="http://api.test",
        manifest_path=manifest,
        source_hashes_path=source_hashes,
        runtime_evidence_path=runtime,
        corpus_hashes={"places.json": "frozen-hash"},
        supplemental={},
        output_path=output,
        review_path=review,
    )

    saved = json.loads(output.read_text(encoding="utf-8"))
    assert saved["provenance"]["generationId"] == "generation-1"
    assert saved["provenance"]["generationManifestSha256"] == expected_manifest_hash
    assert saved["provenance"]["apiSourceHashes"] == {"app.py": "source-v1"}
    assert saved["provenance"]["apiSourceHashFileSha256"]
    assert review.exists()


def test_review_sheet_leaves_human_verdict_blank():
    selected = case()
    result = run_evaluation(
        [selected],
        lambda _params: httpx.Response(
            503,
            json={},
            request=httpx.Request("GET", "http://api.test/v1/places"),
        ),
        log_text=None,
        captured_at="2026-09-30T00:00:00Z",
    )
    review = review_markdown(result)
    assert "- Human H4 verdict: " in review
    assert "| Query | Expected place |" in review
    assert (
        "| Top result | Kind | Address level | Precision | Result language | Distance m |" in review
    )
    assert "| H4 usability | H4 verdict |" in review
    row = next(line for line in review.splitlines() if line.startswith("| T001 |"))
    assert "| T001 | primary | Central Station | target | en |" in row
    assert "| http_error |" in row and row.endswith("|  |  |")


def test_review_sheet_escapes_dynamic_table_content_and_keeps_mechanical_fields():
    selected = replace(
        case(),
        query="Mall | Center\nNorth",
        expected_place="Target|Place",
    )
    result = run_evaluation(
        [selected],
        lambda _params: httpx.Response(
            200,
            json=_payload(
                [
                    {
                        "kind": "poi",
                        "displayName": "Name|Label\nSecond",
                        "precision": "address|parcel",
                        "languageUsed": "en",
                        "coordinates": {"latitude": 32.0, "longitude": 35.0},
                    }
                ]
            ),
            request=httpx.Request("GET", "http://api.test/v1/places"),
        ),
        log_text=None,
    )
    review = review_markdown(result)
    row = next(line for line in review.splitlines() if line.startswith("| T001 |"))
    assert "Mall \\| Center North" in row
    assert "Target\\|Place" in row
    assert "Name\\|Label Second" in row
    assert "address\\|parcel" in row
    assert row.count("H4") == 0
    assert row.endswith("|  |  |")
