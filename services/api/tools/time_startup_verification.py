"""Time the API startup verification path (unmanaged lifespan sequence) against a generation.

Usage: python tools/time_startup_verification.py <src-dir> <before|after> <generation-dir>

"before" replays the pre-API-STARTUP sequence (no shared digests); "after" shares one
ArtifactDigests between the address check and RuntimeSnapshot.load, as the lifespan now does.
Point <src-dir> at an extracted source tree of the code under test (git archive).
Read-only: opens artifacts for reading only; Photon/MOTIS are stubbed (no network, no Docker).
"""

import json
import sys
import time
from collections import Counter
from pathlib import Path

src, variant, generation = sys.argv[1], sys.argv[2], Path(sys.argv[3])
sys.path.insert(0, src)

import httpx  # noqa: E402

import opentransit.runtime as runtime_module  # noqa: E402
from opentransit.address_catalog import AddressCatalog  # noqa: E402
from opentransit.core import artifacts as artifacts_module  # noqa: E402
from opentransit.motis import MotisClient  # noqa: E402
from opentransit.runtime import AddressProviderBinding, RuntimeSnapshot  # noqa: E402

assert Path(artifacts_module.__file__).resolve().is_relative_to(Path(src).resolve())

reads = Counter()
original_open = Path.open


def spy(self, mode="r", *args, **kwargs):
    if "r" in mode and "b" in mode:
        reads[Path(self).resolve()] += 1
    if any(flag in mode for flag in "wax+"):
        raise RuntimeError(f"refusing to open {self} for writing")
    return original_open(self, mode, *args, **kwargs)


Path.open = spy

reference_seconds = []
OriginalStore = runtime_module.ReferenceStore


class TimedStore(OriginalStore):
    def __init__(self, *args, **kwargs):
        started = time.perf_counter()
        super().__init__(*args, **kwargs)
        reference_seconds.append(time.perf_counter() - started)


runtime_module.ReferenceStore = TimedStore


class PhotonClient:
    base_url = "http://127.0.0.1:2322"

    async def aclose(self):
        pass


manifest_path = generation / "manifest.json"
manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
started = time.perf_counter()
if variant == "after":
    digests = artifacts_module.ArtifactDigests()
    metadata = artifacts_module.verify_address_composite(generation, manifest, digests)
    extra = {"digests": digests}
else:
    metadata = artifacts_module.verify_address_composite(generation, manifest)
    extra = {}
catalog = AddressCatalog(generation / "address-catalog.sqlite", metadata["sourceDumpSha256"])
address_seconds = time.perf_counter() - started
binding = AddressProviderBinding(
    PhotonClient(),
    "http://127.0.0.1:2322",
    metadata["addressArtifactIdentity"],
    metadata["indexUuid"],
    catalog,
)
load_started = time.perf_counter()
snapshot = RuntimeSnapshot.load(
    manifest_path,
    MotisClient(httpx.AsyncClient(base_url="http://127.0.0.1:58081")),
    address_provider=binding,
    **extra,
)
load_seconds = time.perf_counter() - load_started
total = time.perf_counter() - started
catalog.close()

sizes = {path: path.stat().st_size for path in reads}
artifact_reads = {
    path.relative_to(generation.resolve()).as_posix(): count
    for path, count in reads.items()
    if path.is_relative_to(generation.resolve())
}
print(
    json.dumps(
        {
            "variant": variant,
            "generationId": snapshot.generation.id,
            "totalSeconds": round(total, 1),
            "addressVerificationSeconds": round(address_seconds, 1),
            "runtimeSnapshotLoadSeconds": round(load_seconds, 1),
            "referenceStoreOpenSeconds": round(sum(reference_seconds), 1),
            "fileHashSecondsApprox": round(total - sum(reference_seconds), 1),
            "binaryReadBytes": sum(sizes[path] * count for path, count in reads.items()),
            "readsPerArtifact": {
                name: artifact_reads.get(name, 0)
                for name in (
                    "reference.sqlite",
                    "address-catalog.sqlite",
                    "photon-import-attestation.json",
                    "schedule-component-manifest.json",
                    "config.yml",
                )
            },
            "graphFileReadsMax": max(
                (count for name, count in artifact_reads.items() if name.startswith("motis/")),
                default=0,
            ),
        }
    )
)
