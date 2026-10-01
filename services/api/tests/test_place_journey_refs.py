import httpx

from opentransit.core.place_ref import encode_place_ref


def _place_ref(generation_id="synthetic-test"):
    return encode_place_ref(
        generation_id,
        "place",
        "a" * 64,
        latitude=32.2,
        longitude=34.9,
    )


def test_journey_resolves_place_ref_to_coordinate_without_second_geocode(
    client_factory, query, engine_route
):
    requests = []

    def engine(request):
        requests.append(request)
        return httpx.Response(200, json=engine_route)

    query["from"] = {"kind": "place", "placeRef": _place_ref()}
    with client_factory(engine) as client:
        response = client.post("/v1/journeys", json=query)
    assert response.status_code == 200
    plan = next(request for request in requests if request.url.path == "/api/v6/plan")
    assert plan.url.params["fromPlace"] == "32.2,34.9"
    assert not any(request.url.path == "/api/v1/geocode" for request in requests)


def test_journey_rejects_malformed_or_stale_place_ref_before_engine_call(client_factory, query):
    for token in ("not-a-place-ref", _place_ref("another-generation")):
        calls = []

        def engine(request, requests=calls):
            requests.append(request)
            return httpx.Response(200, json={"itineraries": [], "direct": []})

        body = dict(query)
        body["from"] = {"kind": "place", "placeRef": token}
        with client_factory(engine) as client:
            response = client.post("/v1/journeys", json=body)
        assert response.status_code == 422
        assert response.json()["code"] == "INVALID_PLACE_REF"
        assert not any(request.url.path == "/api/v6/plan" for request in calls)
