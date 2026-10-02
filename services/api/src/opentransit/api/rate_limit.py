"""Per-client token-bucket rate limiting (M7).

In-process and in-memory: correct for the single API worker in one serving task. Several
workers or tasks would each keep their own buckets, so the effective limit would multiply;
a shared store is needed before scaling out.

Privacy: buckets are keyed by a per-process keyed digest of the client identity, never by
the raw address; entries expire once their bucket would be full again and the table is
bounded (least recently used first). Nothing here is logged or persisted.
"""

import hashlib
import ipaddress
import math
import secrets
import time
from collections import OrderedDict
from collections.abc import Callable, Iterable, Mapping
from dataclasses import dataclass

EXEMPT_PATHS = frozenset({"/healthz", "/readyz"})
# Journey planning and search hit the engine/geocoders; everything else reads local data.
EXPENSIVE_ROUTES = frozenset({("POST", "/v1/journeys"), ("GET", "/v1/places")})
STANDARD = "standard"
EXPENSIVE = "expensive"
_EPSILON = 1e-9

Network = ipaddress.IPv4Network | ipaddress.IPv6Network


@dataclass(frozen=True)
class BucketPolicy:
    per_minute: int
    burst: int

    def __post_init__(self) -> None:
        if not 1 <= self.per_minute <= 60_000 or not 1 <= self.burst <= 10_000:
            raise ValueError("Rate limit must be 1-60000/minute with burst 1-10000")

    @property
    def per_second(self) -> float:
        return self.per_minute / 60.0

    @property
    def idle_expiry_seconds(self) -> float:
        """After this long without requests any bucket is full, so dropping it is lossless."""
        return self.burst / self.per_second


@dataclass(frozen=True)
class Decision:
    allowed: bool
    retry_after: int = 0


class RateLimiter:
    def __init__(
        self,
        policies: Mapping[str, BucketPolicy],
        clock: Callable[[], float] = time.monotonic,
        max_clients: int = 10_000,
    ) -> None:
        if max_clients < 1:
            raise ValueError("max_clients must be positive")
        self._policies = dict(policies)
        self._clock = clock
        self._max = max_clients
        self._key = secrets.token_bytes(16)
        # (class, digest) -> [tokens, updated_at]; ordered least recently used first.
        self._buckets: OrderedDict[tuple[str, bytes], list[float]] = OrderedDict()

    def __len__(self) -> int:
        return len(self._buckets)

    def _digest(self, identity: str) -> bytes:
        return hashlib.blake2b(identity.encode(), key=self._key, digest_size=16).digest()

    def _expire(self, now: float) -> None:
        while self._buckets:
            (bucket_class, _), (_, updated) = next(iter(self._buckets.items()))
            if now - updated < self._policies[bucket_class].idle_expiry_seconds:
                return
            self._buckets.popitem(last=False)

    def check(self, bucket_class: str, identity: str) -> Decision:
        """Take one token for this client and class, or report the wait for the next one."""
        policy = self._policies[bucket_class]
        now = self._clock()
        self._expire(now)
        key = (bucket_class, self._digest(identity))
        bucket = self._buckets.get(key)
        if bucket is None:
            bucket = [float(policy.burst), now]
            self._buckets[key] = bucket
            while len(self._buckets) > self._max:
                self._buckets.popitem(last=False)
        else:
            self._buckets.move_to_end(key)
            bucket[0] = min(float(policy.burst), bucket[0] + (now - bucket[1]) * policy.per_second)
            bucket[1] = now
        if bucket[0] >= 1 - _EPSILON:
            bucket[0] = max(0.0, bucket[0] - 1)
            return Decision(True)
        wait = (1 - bucket[0]) / policy.per_second
        return Decision(False, max(1, math.ceil(wait - _EPSILON)))


def classify(method: str, path: str) -> str | None:
    """Bucket class for a request, or None when it is exempt (health and readiness)."""
    normalized = path.rstrip("/") or "/"
    if normalized in EXEMPT_PATHS:
        return None
    if (method.upper(), normalized) in EXPENSIVE_ROUTES:
        return EXPENSIVE
    return STANDARD


def parse_trusted_proxies(value: str | Iterable[str]) -> tuple[Network, ...]:
    """Parse explicit proxy CIDRs; a catch-all would let any client choose its bucket."""
    items = value.split(",") if isinstance(value, str) else value
    networks = []
    for item in items:
        item = item.strip()
        if not item:
            continue
        network = ipaddress.ip_network(item, strict=False)
        if network.prefixlen == 0:
            raise ValueError("Trusted proxies must not include every address")
        networks.append(network)
    return tuple(networks)


def _address(value: str) -> ipaddress.IPv4Address | ipaddress.IPv6Address | None:
    try:
        address = ipaddress.ip_address(value.strip())
    except ValueError:
        return None
    if isinstance(address, ipaddress.IPv6Address) and address.ipv4_mapped is not None:
        return address.ipv4_mapped
    return address


def _bucket_identity(address: ipaddress.IPv4Address | ipaddress.IPv6Address) -> str:
    if isinstance(address, ipaddress.IPv6Address):
        # One subscriber usually holds a whole /64; per-address buckets are trivially evaded.
        return str(ipaddress.IPv6Network((address, 64), strict=False))
    return str(address)


def client_identity(
    peer: str | None, forwarded_for: str | None, trusted: tuple[Network, ...]
) -> str:
    """Client identity for rate limiting.

    X-Forwarded-For is read only when the direct peer is inside an explicitly trusted proxy
    network (the load balancer). The header is walked from the right, skipping trusted
    hops; the first untrusted address is the client the proxy saw. Entries further left are
    client-supplied and could be spoofed, so they are never used while an untrusted address
    exists to their right. A malformed entry stops the walk at the nearest valid hop.
    """
    if peer is None:
        return "unknown"
    peer_address = _address(peer)
    if peer_address is None:
        return peer  # Non-IP transports (for example the test client) stay opaque.

    def is_trusted(address) -> bool:
        return any(address in network for network in trusted)

    chosen = peer_address
    if trusted and forwarded_for and is_trusted(peer_address):
        for entry in reversed(forwarded_for.split(",")):
            address = _address(entry)
            if address is None:
                break
            chosen = address
            if not is_trusted(address):
                break
    return _bucket_identity(chosen)
