"""Offline replay tool: recomputed stop search, saved geocoder items, production merge."""

import json
from pathlib import Path

import pytest
from test_reference import synthetic_feed

from opentransit.reference import ReferenceStore, build_reference
from tools.evaluate_search import SearchCase
from tools.replay_search import (
    cell_counts,
    diff_cases,
    main,
    replay,
    saved_geocoder_items,
    stop_related,
)

ROOT = Path(__file__).resolve().parents[3]


def _case(
    case_id="C1",
    *,
    types=("stop", "station", "poi"),
    category="misspelling",
    expected=(32.08, 34.78),
):
    return SearchCase(
        id=case_id,
        source_case_id=case_id,
        variant="primary",
        query="Central A",
        language="en",
        language_assignment="explicit",
        query_script="latin",
        category=category,
        api_types=types,
        expected_place="Central",
        latitude=expected[0],
        longitude=expected[1],
        tolerance_m=400.0,
        near=None,
        corpus="places-100",
    )


def _record(case_id="C1", candidates=()):
    return {
        "case": {"id": case_id},
        "firstPass": {
            "top1Hit": False,
            "top5Hit": False,
            "top5HitRank": None,
            "candidates": list(candidates),
        },
    }


def _geocoder_candidate(name, distance_lat=32.0801):
    return {
        "kind": "poi",
        "displayName": name,
        "coordinates": {"latitude": distance_lat, "longitude": 34.7801},
        "addressLevel": None,
        "precision": None,
        "languageUsed": "en",
        "locationRef": {"kind": "place", "placeRef": f"mot:place:v1:{name}"},
    }


@pytest.fixture
def reference(tmp_path):
    feed = synthetic_feed(tmp_path / "feed.zip")
    database = tmp_path / "reference.sqlite"
    build_reference(feed, database, "replay-test")
    return ReferenceStore(database, "replay-test"), database


def test_geocoder_items_come_from_saved_candidates_in_recorded_order():
    record = _record(
        candidates=[
            {"kind": "stop", "displayName": "Stop", "locationRef": {"kind": "stop"}},
            _geocoder_candidate("first"),
            _geocoder_candidate("second"),
        ]
    )
    assert [item["displayName"] for item in saved_geocoder_items(record)] == ["first", "second"]


def test_only_stop_related_cases_are_replayed_and_scored_with_the_production_merge(reference):
    store, _ = reference
    cases = {
        "C1": _case("C1"),
        "POI": _case("POI", types=("poi",), category="venue"),
    }
    saved = {
        "records": [
            _record("C1", [_geocoder_candidate("Park A")]),
            _record("POI", [_geocoder_candidate("Park B")]),
        ]
    }
    assert [stop_related(case) for case in cases.values()] == [True, False]
    outcome = replay(store, saved, cases)
    assert [item["caseId"] for item in outcome["cases"]] == ["C1"]
    item = outcome["cases"][0]
    # The station "Central" (parent of platforms A and B) leads the merge (stop-first),
    # followed by the saved geocoder candidate: replay matches the production merge.
    assert [entry["kind"] for entry in item["replayed"]["top5"]] == ["station", "poi"]
    assert item["replayed"]["top1Hit"] is True
    assert item["recorded"]["top1Hit"] is False
    assert outcome["indexBuildSeconds"] >= 0
    assert len(outcome["timings"]) == 1


def test_cell_counts_and_diff_report_gains_and_losses():
    per_case = [
        {
            "caseId": "A",
            "category": "station",
            "recorded": {"top1Hit": False, "top5Hit": False},
            "replayed": {"top1Hit": True, "top5Hit": True},
        },
        {
            "caseId": "B",
            "category": "station",
            "recorded": {"top1Hit": True, "top5Hit": True},
            "replayed": {"top1Hit": False, "top5Hit": True},
        },
    ]
    assert cell_counts(per_case, "recorded") == {"station": [1, 1, 2]}
    assert cell_counts(per_case, "replayed") == {"station": [1, 2, 2]}
    diff = diff_cases(
        {item["caseId"]: item["recorded"] for item in per_case},
        {item["caseId"]: item["replayed"] for item in per_case},
    )
    assert diff == {
        "top1Gained": ["A"],
        "top1Lost": ["B"],
        "top5Gained": ["A"],
        "top5Lost": [],
    }


def test_cli_writes_a_new_result_with_provenance_and_refuses_to_overwrite(tmp_path, reference):
    _, database = reference
    saved_path = tmp_path / "saved.json"
    saved_path.write_text(
        json.dumps(
            {
                "summary": {"overall": {"top1": 10, "top5": 12, "denominator": 20}},
                "records": [
                    _record("P001", [_geocoder_candidate("Park A")]),
                    _record("P013"),
                ],
            }
        ),
        encoding="utf-8",
    )
    output = tmp_path / "replay.json"
    args = ["--reference", str(database), "--saved-run", str(saved_path), "--output", str(output)]
    assert main(args + ["--label", "first"]) == 0
    result = json.loads(output.read_text(encoding="utf-8"))
    assert result["label"] == "first"
    assert result["caseCount"] == 2
    assert result["provenance"]["referenceContentSha256"]
    assert len(result["provenance"]["savedRunSha256"]) == 64
    assert result["projectedOverall"]["denominator"] == 20
    assert "diffVsRecorded" in result

    second = tmp_path / "replay-2.json"
    assert (
        main(
            [
                "--reference",
                str(database),
                "--saved-run",
                str(saved_path),
                "--output",
                str(second),
                "--compare",
                f"first={output}",
            ]
        )
        == 0
    )
    compared = json.loads(second.read_text(encoding="utf-8"))
    assert compared["compare"][0]["name"] == "first"
    assert compared["compare"][0]["diff"]["top1Lost"] == []
    with pytest.raises(SystemExit):
        main(args)


def test_locality_probe_judges_results_by_polygon_containment(tmp_path):
    from test_localities import PBF_SHA, TAGS_CENTRAL, _polygon, _square, _write_context

    from opentransit.localities import load_locality_context
    from tools.replay_search import locality_probe

    feed = synthetic_feed(tmp_path / "feed.zip")
    plain = tmp_path / "plain.sqlite"
    build_reference(feed, plain, "probe-plain")
    assert locality_probe(ReferenceStore(plain, "probe-plain"))["available"] is False

    context = _write_context(
        tmp_path / "context-v1.jsonl",
        [(7, TAGS_CENTRAL, _polygon(_square(34.775, 32.075, 34.785, 32.0815)))],
    )
    database = tmp_path / "with-localities.sqlite"
    build_reference(
        feed,
        database,
        "probe",
        localities=load_locality_context(context, expected_osm_sha256=PBF_SHA),
    )
    result = locality_probe(
        ReferenceStore(database, "probe"),
        (("Centralia", "en", "osm:relation:7"), ("מרכזיה", "he", "osm:relation:7")),
    )
    assert result["available"] is True
    assert result["totals"]["after"] == {"queries": 2, "top1Inside": 2, "top5AllInside": 2}
    assert result["top1Lost"] == []
    first = result["cases"][0]
    assert first["before"]["top1Inside"] is False  # feed-only search knows no "Centralia"
    assert first["after"]["top"][0]["inside"] is True
    with pytest.raises(ValueError, match="lacks"):
        locality_probe(ReferenceStore(database, "probe"), (("X", "en", "osm:relation:99"),))
