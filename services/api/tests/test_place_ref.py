import json

import pytest

from opentransit.core.place_ref import (
    PLACE_REF_PREFIX,
    candidate_identity_hash,
    decode_place_ref,
    encode_place_ref,
)


def test_place_reference_round_trips_exact_candidate_and_generation():
    identity = {
        "label": "Dizengoff Street",
        "street": "Dizengoff Street",
        "houseNumber": None,
        "locality": "Tel-Aviv",
        "coordinates": [32.08, 34.78],
    }
    identity_hash = candidate_identity_hash("address", identity)
    token = encode_place_ref("generation-a", "address", identity_hash, 32.08, 34.78)
    decoded = decode_place_ref(token, "generation-a")
    assert token.startswith(PLACE_REF_PREFIX)
    assert decoded.kind == "address"
    assert decoded.latitude == 32.08
    assert decoded.longitude == 34.78
    assert decoded.candidate_identity_hash == identity_hash
    with pytest.raises(ValueError):
        decode_place_ref(token, "generation-b")


@pytest.mark.parametrize(
    "value",
    [
        "mot:place:v2:bad",
        "mot:place:v1:%%%",
        "mot:place:v1:eyJraW5kIjoicGxhY2UifQ",
    ],
)
def test_place_reference_rejects_malformed_values(value):
    with pytest.raises(ValueError):
        decode_place_ref(value, "generation-a")


def test_place_reference_rejects_noncanonical_fields_and_coordinates():
    payload = {
        "candidateIdentityHash": "0" * 64,
        "coordinates": [32.0, 34.0],
        "generationId": "generation-a",
        "kind": "place",
        "extra": True,
    }
    import base64

    token = PLACE_REF_PREFIX + base64.urlsafe_b64encode(
        json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
    ).decode().rstrip("=")
    with pytest.raises(ValueError):
        decode_place_ref(token, "generation-a")
    with pytest.raises(ValueError):
        encode_place_ref("generation-a", "place", "0" * 64, 35, 34)
