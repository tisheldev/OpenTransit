"""M7 per-client rate limiting: token buckets, client identity and the HTTP contract.

Synthetic requests only; no engine, generation or network is used.
"""

import pytest
from fastapi.testclient import TestClient

from opentransit.api.app import create_app
from opentransit.api.rate_limit import (
    EXEMPT_PATHS,
    BucketPolicy,
    RateLimiter,
    classify,
    client_identity,
    parse_trusted_proxies,
)
from opentransit.config import Settings


class FakeClock:
    def __init__(self, now: float = 1000.0) -> None:
        self.now = now

    def __call__(self) -> float:
        return self.now


def limiter(clock, **overrides) -> RateLimiter:
    policies = {
        "standard": BucketPolicy(per_minute=60, burst=3),
        "expensive": BucketPolicy(per_minute=6, burst=2),
    }
    return RateLimiter(policies, clock=clock, **overrides)


# --- token buckets -------------------------------------------------------------------


def test_burst_then_reject_with_retry_after_then_refill():
    clock = FakeClock()
    limits = limiter(clock)
    assert [limits.check("expensive", "a").allowed for _ in range(2)] == [True, True]
    denied = limits.check("expensive", "a")
    assert not denied.allowed
    assert denied.retry_after == 10  # 6/minute: one token every 10 seconds
    clock.now += 9.5
    assert not limits.check("expensive", "a").allowed
    clock.now += 0.5
    assert limits.check("expensive", "a").allowed
    assert not limits.check("expensive", "a").allowed


def test_retry_after_is_a_whole_number_of_seconds_and_at_least_one():
    clock = FakeClock()
    limits = RateLimiter({"standard": BucketPolicy(per_minute=6000, burst=1)}, clock=clock)
    assert limits.check("standard", "a").allowed
    denied = limits.check("standard", "a")
    assert denied.retry_after == 1


def test_denied_requests_do_not_consume_tokens():
    clock = FakeClock()
    limits = limiter(clock)
    for _ in range(2):
        limits.check("expensive", "a")
    for _ in range(50):
        assert not limits.check("expensive", "a").allowed
    clock.now += 10
    assert limits.check("expensive", "a").allowed


def test_classes_and_clients_are_independent():
    clock = FakeClock()
    limits = limiter(clock)
    for _ in range(2):
        assert limits.check("expensive", "a").allowed
    assert not limits.check("expensive", "a").allowed
    assert limits.check("standard", "a").allowed
    assert limits.check("expensive", "b").allowed


def test_idle_entries_expire_and_raw_identities_are_not_stored():
    clock = FakeClock()
    limits = limiter(clock)
    limits.check("standard", "203.0.113.9")
    limits.check("expensive", "203.0.113.9")
    assert len(limits) == 2
    assert "203.0.113.9" not in repr(limits._buckets)  # keyed digests only
    clock.now += 21  # both buckets are full again after burst / rate seconds
    limits.check("standard", "198.51.100.1")
    assert len(limits) == 1


def test_client_table_is_bounded_least_recently_used_first():
    clock = FakeClock()
    limits = limiter(clock, max_clients=3)
    for name in ("a", "b", "c"):
        limits.check("expensive", name)
    limits.check("expensive", "a")  # refresh a
    limits.check("expensive", "d")  # evicts b
    assert len(limits) == 3
    assert not limits.check("expensive", "a").allowed  # a kept its spent bucket
    assert limits.check("expensive", "b").allowed  # b was evicted, starts full


def test_policy_bounds_are_validated():
    with pytest.raises(ValueError):
        BucketPolicy(per_minute=0, burst=1)
    with pytest.raises(ValueError):
        BucketPolicy(per_minute=10, burst=0)
    with pytest.raises(ValueError):
        RateLimiter({"standard": BucketPolicy(60, 10)}, clock=FakeClock(), max_clients=0)


# --- classification ------------------------------------------------------------------


@pytest.mark.parametrize(
    ("method", "path", "expected"),
    [
        ("GET", "/healthz", None),
        ("GET", "/readyz", None),
        ("HEAD", "/readyz", None),
        ("POST", "/v1/journeys", "expensive"),
        ("POST", "/v1/journeys/", "expensive"),
        ("GET", "/v1/places", "expensive"),
        ("GET", "/v1/status", "standard"),
        ("GET", "/v1/stops/mot:stop:1/departures", "standard"),
        ("GET", "/v1/trips/abc", "standard"),
        ("GET", "/openapi.json", "standard"),
        ("GET", "/does-not-exist", "standard"),
    ],
)
def test_classify(method, path, expected):
    assert classify(method, path) == expected


def test_exempt_paths_are_only_health_and_readiness():
    assert EXEMPT_PATHS == frozenset({"/healthz", "/readyz"})


# --- client identity -----------------------------------------------------------------


ALB = parse_trusted_proxies("10.0.0.0/16")


def test_forwarded_for_is_ignored_unless_proxies_are_trusted():
    assert client_identity("203.0.113.7", "198.51.100.1", ()) == "203.0.113.7"
    assert client_identity("10.0.1.5", "198.51.100.1", ()) == "10.0.1.5"


def test_forwarded_for_from_an_untrusted_peer_is_ignored():
    assert client_identity("203.0.113.7", "198.51.100.1", ALB) == "203.0.113.7"


def test_trusted_peer_uses_rightmost_untrusted_forwarded_address():
    # A client-supplied (spoofed) leftmost entry must not select the bucket.
    header = "1.2.3.4, 198.51.100.20"
    assert client_identity("10.0.1.5", header, ALB) == "198.51.100.20"
    assert client_identity("10.0.1.5", "198.51.100.20, 10.0.2.9", ALB) == "198.51.100.20"


def test_trusted_peer_without_usable_forwarded_address_falls_back_safely():
    assert client_identity("10.0.1.5", None, ALB) == "10.0.1.5"
    assert client_identity("10.0.1.5", "", ALB) == "10.0.1.5"
    assert client_identity("10.0.1.5", "not-an-ip", ALB) == "10.0.1.5"
    assert client_identity("10.0.1.5", "198.51.100.3, junk", ALB) == "10.0.1.5"
    assert client_identity("10.0.1.5", "10.0.3.3, 10.0.4.4", ALB) == "10.0.3.3"


def test_ipv6_clients_share_a_slash_64_bucket():
    first = client_identity("2001:db8:1:2:aaaa::1", None, ())
    second = client_identity("2001:db8:1:2:bbbb::2", None, ())
    other = client_identity("2001:db8:1:3::1", None, ())
    assert first == second == "2001:db8:1:2::/64"
    assert other != first
    assert client_identity("::ffff:203.0.113.8", None, ()) == "203.0.113.8"


def test_non_ip_peer_names_are_kept_as_opaque_identities():
    assert client_identity("testclient", None, ()) == "testclient"
    assert client_identity(None, None, ()) == "unknown"


def test_trusted_proxies_parse_and_reject_invalid_values():
    assert parse_trusted_proxies("") == ()
    assert len(parse_trusted_proxies(" 10.0.0.0/16 , 172.31.0.0/16 ")) == 2
    with pytest.raises(ValueError):
        parse_trusted_proxies("10.0.0.0/33")
    with pytest.raises(ValueError):
        parse_trusted_proxies("0.0.0.0/0")


# --- settings ------------------------------------------------------------------------


def test_settings_defaults_enable_conservative_limits(tmp_path):
    settings = Settings(tmp_path / "manifest.json")
    assert settings.rate_limit_enabled is True
    assert (settings.rate_limit_standard_per_minute, settings.rate_limit_standard_burst) == (
        60,
        20,
    )
    assert (settings.rate_limit_expensive_per_minute, settings.rate_limit_expensive_burst) == (
        30,
        15,
    )
    assert settings.trusted_proxies == ()


def test_settings_from_env(monkeypatch):
    monkeypatch.setenv("OPENTRANSIT_RATE_LIMIT_ENABLED", "0")
    monkeypatch.setenv("OPENTRANSIT_RATE_LIMIT_STANDARD_PER_MINUTE", "120")
    monkeypatch.setenv("OPENTRANSIT_RATE_LIMIT_STANDARD_BURST", "40")
    monkeypatch.setenv("OPENTRANSIT_RATE_LIMIT_EXPENSIVE_PER_MINUTE", "12")
    monkeypatch.setenv("OPENTRANSIT_RATE_LIMIT_EXPENSIVE_BURST", "6")
    monkeypatch.setenv("OPENTRANSIT_RATE_LIMIT_MAX_CLIENTS", "5000")
    monkeypatch.setenv("OPENTRANSIT_TRUSTED_PROXIES", "10.0.0.0/16")
    settings = Settings.from_env()
    assert settings.rate_limit_enabled is False
    assert settings.rate_limit_standard_per_minute == 120
    assert settings.rate_limit_standard_burst == 40
    assert settings.rate_limit_expensive_per_minute == 12
    assert settings.rate_limit_expensive_burst == 6
    assert settings.rate_limit_max_clients == 5000
    assert settings.trusted_proxies == ("10.0.0.0/16",)


@pytest.mark.parametrize(
    ("name", "value"),
    [
        ("OPENTRANSIT_RATE_LIMIT_ENABLED", "yes"),
        ("OPENTRANSIT_RATE_LIMIT_STANDARD_PER_MINUTE", "0"),
        ("OPENTRANSIT_RATE_LIMIT_EXPENSIVE_BURST", "lots"),
        ("OPENTRANSIT_RATE_LIMIT_MAX_CLIENTS", "10"),
        ("OPENTRANSIT_TRUSTED_PROXIES", "everyone"),
    ],
)
def test_invalid_rate_limit_env_fails_startup(monkeypatch, name, value):
    monkeypatch.setenv(name, value)
    with pytest.raises(ValueError):
        Settings.from_env()


# --- HTTP contract -------------------------------------------------------------------


def make_client(tmp_path, peer="203.0.113.5", clock=None, **settings):
    values = {
        "rate_limit_standard_per_minute": 60,
        "rate_limit_standard_burst": 3,
        "rate_limit_expensive_per_minute": 6,
        "rate_limit_expensive_burst": 2,
    }
    values.update(settings)
    app = create_app(
        Settings(tmp_path / "missing-manifest.json", **values),
        rate_limit_clock=clock or FakeClock(),
    )
    return TestClient(app, client=(peer, 40000))


def test_journeys_return_429_problem_with_retry_after(tmp_path, caplog):
    client = make_client(tmp_path)
    body = {"not": "a valid journey"}
    statuses = [client.post("/v1/journeys", json=body).status_code for _ in range(2)]
    assert 429 not in statuses
    response = client.post("/v1/journeys", json=body)
    assert response.status_code == 429
    assert response.headers["retry-after"] == "10"
    assert response.headers["content-type"].startswith("application/problem+json")
    assert response.headers["cache-control"] == "no-store"
    problem = response.json()
    assert problem["code"] == "RATE_LIMITED"
    assert problem["status"] == 429
    assert problem["type"] == "urn:opentransit:problem:rate-limited"
    assert problem["requestId"] == response.headers["x-request-id"]
    assert "203.0.113.5" not in response.text
    assert "203.0.113.5" not in caplog.text
    assert "route=rate_limit:expensive status=429" in caplog.text


def test_search_shares_the_expensive_bucket_and_standard_is_separate(tmp_path):
    client = make_client(tmp_path)
    client.get("/v1/places", params={"q": "ab"})
    client.post("/v1/journeys", json={})
    assert client.get("/v1/places", params={"q": "ab"}).status_code == 429
    assert client.get("/v1/status").status_code != 429


def test_health_and_readiness_are_never_limited(tmp_path):
    client = make_client(tmp_path, rate_limit_standard_burst=1)
    for _ in range(25):
        assert client.get("/healthz").status_code == 200
        assert client.get("/readyz").status_code != 429
    assert client.get("/v1/status").status_code != 429
    assert client.get("/v1/status").status_code == 429


def test_disabled_limiter_never_rejects(tmp_path):
    client = make_client(tmp_path, rate_limit_enabled=False)
    for _ in range(10):
        assert client.post("/v1/journeys", json={}).status_code != 429


def test_rejection_happens_before_the_body_is_read(tmp_path):
    client = make_client(tmp_path)
    for _ in range(2):
        client.post("/v1/journeys", json={})
    response = client.post("/v1/journeys", content=b"x" * 40_000)
    assert response.status_code == 429  # not 413: the over-limit body is never parsed


def test_forwarded_for_selects_the_bucket_only_behind_a_trusted_proxy(tmp_path):
    spoofed = make_client(tmp_path)
    for index in range(3):
        headers = {"X-Forwarded-For": f"198.51.100.{index}"}
        status = spoofed.post("/v1/journeys", json={}, headers=headers).status_code
    assert status == 429  # rotating the header does not create new buckets

    behind_alb = make_client(tmp_path, peer="10.0.1.5", trusted_proxies=("10.0.0.0/16",))
    for index in range(3):
        headers = {"X-Forwarded-For": f"198.51.100.{index}"}
        assert behind_alb.post("/v1/journeys", json={}, headers=headers).status_code != 429
    headers = {"X-Forwarded-For": "198.51.100.0"}
    behind_alb.post("/v1/journeys", json={}, headers=headers)
    assert behind_alb.post("/v1/journeys", json={}, headers=headers).status_code == 429


def test_openapi_documents_429_on_limited_routes_only(tmp_path):
    schema = make_client(tmp_path).get("/openapi.json").json()
    journeys = schema["paths"]["/v1/journeys"]["post"]["responses"]
    assert "429" in journeys
    assert "Retry-After" in journeys["429"]["headers"]
    assert "429" in schema["paths"]["/v1/places"]["get"]["responses"]
    assert "429" in schema["paths"]["/v1/status"]["get"]["responses"]
    assert "429" not in schema["paths"]["/healthz"]["get"]["responses"]
    assert "429" not in schema["paths"]["/readyz"]["get"]["responses"]
