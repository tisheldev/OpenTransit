# Licence audit

**DRAFT — not legal advice, pending review**

Reviewed 1 October 2026 against local branch baseline `eea0532baedad5900282d73b7ebdd0f3b77f048f`.
Scope: [Python lock](../services/api/uv.lock), [Compose](../compose.yaml),
[API Dockerfile](../services/api/Dockerfile), [AWS drafts](../deploy/aws/README.md) and
scheduled datasets. No packages, image layers or feeds were downloaded; no Docker ran.
This is a source/metadata inventory, not clearance of binary redistribution.

Lock SHA-256: `f4ada587110e6aec5801bf0829e005546961b58a04cfd19f03801e1058c1dc6d`.

## Python packages

All **25 external packages plus the local project** in `uv.lock` are listed below,
including development-only dependencies. Links identify version-specific PyPI metadata
retrieved on the review date (SPDX expression where supplied, otherwise licence field/
classifier). Colourama's generic BSD classifier was resolved from its
[tagged licence](https://github.com/tartley/colorama/blob/0.4.6/LICENSE.txt).
This did not inspect wheel licence files, vendored Rust code or build-isolation inputs.

| Package | Locked version | Reported licence / review note |
| --- | --- | --- |
| [annotated-doc](https://pypi.org/pypi/annotated-doc/0.0.5/json) | 0.0.5 | MIT |
| [annotated-types](https://pypi.org/pypi/annotated-types/0.8.0/json) | 0.8.0 | MIT |
| [anyio](https://pypi.org/pypi/anyio/4.15.1/json) | 4.15.1 | MIT |
| [certifi](https://pypi.org/pypi/certifi/2026.7.22/json) | 2026.7.22 | **MPL-2.0**; file-level copyleft/source obligations on distribution |
| [click](https://pypi.org/pypi/click/8.5.0/json) | 8.5.0 | BSD-3-Clause |
| [colorama](https://pypi.org/pypi/colorama/0.4.6/json) | 0.4.6 | BSD-3-Clause; conditional Windows dependency |
| [fastapi](https://pypi.org/pypi/fastapi/0.142.1/json) | 0.142.1 | MIT |
| [h11](https://pypi.org/pypi/h11/0.16.0/json) | 0.16.0 | MIT |
| [httpcore](https://pypi.org/pypi/httpcore/1.0.9/json) | 1.0.9 | BSD-3-Clause |
| [httpx](https://pypi.org/pypi/httpx/0.28.1/json) | 0.28.1 | BSD-3-Clause |
| [idna](https://pypi.org/pypi/idna/3.20/json) | 3.20 | BSD-3-Clause |
| [iniconfig](https://pypi.org/pypi/iniconfig/2.3.0/json) | 2.3.0 | MIT; dev |
| [opentelemetry-api](https://pypi.org/pypi/opentelemetry-api/1.45.0/json) | 1.45.0 | Apache-2.0 |
| opentransit-api | 0.1.0 | **Undecided**; no root code licence or project licence field at this baseline |
| [packaging](https://pypi.org/pypi/packaging/26.3/json) | 26.3 | Apache-2.0 OR BSD-2-Clause; dev |
| [pluggy](https://pypi.org/pypi/pluggy/1.6.0/json) | 1.6.0 | MIT; dev |
| [pydantic](https://pypi.org/pypi/pydantic/2.13.5/json) | 2.13.5 | MIT |
| [pydantic-core](https://pypi.org/pypi/pydantic-core/2.46.5/json) | 2.46.5 | MIT; bundled Rust dependencies need artifact notices |
| [pygments](https://pypi.org/pypi/pygments/2.21.0/json) | 2.21.0 | BSD-2-Clause; dev |
| [pytest](https://pypi.org/pypi/pytest/9.1.1/json) | 9.1.1 | MIT; dev |
| [ruff](https://pypi.org/pypi/ruff/0.16.9/json) | 0.16.9 | MIT; dev; bundled Rust dependencies need artifact notices |
| [starlette](https://pypi.org/pypi/starlette/1.7.0/json) | 1.7.0 | BSD-3-Clause |
| [typing-extensions](https://pypi.org/pypi/typing-extensions/4.16.0/json) | 4.16.0 | PSF-2.0 |
| [typing-inspection](https://pypi.org/pypi/typing-inspection/0.4.4/json) | 0.4.4 | MIT |
| [tzdata](https://pypi.org/pypi/tzdata/2026.4/json) | 2026.4 | Apache-2.0 wrapper; IANA data licensing separate |
| [uvicorn](https://pypi.org/pypi/uvicorn/0.54.0/json) | 0.54.0 | BSD-3-Clause |

MIT/BSD/PSF notices must accompany redistributed components; Apache-2.0 also requires
licence/NOTICE preservation where applicable and notices for modified files. Choosing
MIT for OpenTransit would not replace these terms. [Mozilla's MPL FAQ](https://www.mozilla.org/en-US/MPL/2.0/FAQ/)
explains that MPL can coexist with differently licensed surrounding code; preserve
certifi notices and covered-file source availability, especially for modified bundles.

`hatchling>=1.28,<2` in [pyproject.toml](../services/api/pyproject.toml) is a build
requirement absent from this lock. Its resolved version and build dependencies need
an artifact/build inventory before claiming a complete image audit. The API build
uses `uv sync --no-dev`; a lock entry does not mean it ships in production.

## Container and packaged software inventory

Digest prefixes below identify full pins in the linked Dockerfiles/Compose; all AWS
variants reuse these components. Custom ECR API/data/Photon digests are placeholders,
so their resulting images have not been licensed/scanned as complete artifacts.

| Component and use | Pin at baseline | Licence evidence / remaining scope |
| --- | --- | --- |
| MOTIS, Compose and AWS engine | v2.11.2; `sha256:6055f51eec43…` | [MIT](https://github.com/motis-project/motis/blob/v2.11.2/LICENSE) for MOTIS; image OS/bundled dependencies still need inventory |
| Python, API and data-init bases | `3.14.6-slim-bookworm`; `sha256:4c92ffcde4dd…` | CPython PSF-2.0 and historical component notices; Debian packages have individual licences, including copyleft. [Official image notice](https://hub.docker.com/_/python) warns that the image is not under one licence |
| uv binary copied into API image | `0.11.26`; `sha256:3d868e555f8f…` | [MIT](https://github.com/astral-sh/uv/blob/0.11.26/LICENSE-MIT) OR [Apache-2.0](https://github.com/astral-sh/uv/blob/0.11.26/LICENSE-APACHE); bundled crates require notice inventory; uv remains in final API image |
| Temurin, Photon JRE base | `21.0.12.1_1-jre`; `sha256:628467024d42…` | OpenJDK GPL-2.0 with Classpath Exception, plus third-party/base OS terms; retain source/notices. [Official image licence section](https://hub.docker.com/_/eclipse-temurin) |
| Photon JAR in custom image | 1.3.0; SHA-256 `a89707c0045e…` | [Apache-2.0](https://github.com/komoot/photon/blob/1.3.0/LICENSE); shaded Java/OpenSearch/Lucene/JTS dependencies carry separate terms |
| Custom API/verifier and data-init | `{{API_DIGEST}}`, `{{DATA_DIGEST}}` | OpenTransit code licence pending; API uses locked runtime deps above. Init includes code + Python + dataset payload; private ECR is not a dataset licence |
| Custom Photon / local `ot-t5-*` tags | `{{PHOTON_DIGEST}}`, local unbuilt aliases | Combination of Temurin, Photon, bundled libraries and dataset index; same obligations as constituents |
| `alpine` helper in AWS runbook | unpinned example, not a serving container | Mixed Alpine package licences; pin and inspect if used/distributed. It is not evidence that a particular helper image was audited |

Dockerfile frontend `docker/dockerfile:1` is a build tool, not a serving image; include
its resolved digest/components in a later build SBOM. No running Postgres/PostGIS,
nginx or S3 container is selected by these Compose/AWS files.

Photon's [1.3.0 build dependencies](https://github.com/komoot/photon/blob/1.3.0/build.gradle)
include JTS; its [upstream licence statement](https://github.com/locationtech/jts/blob/master/LICENSES.md)
offers EPL-2.0 OR EDL-1.0 (BSD style), with third-party notices. Resolve the actual
shaded JAR's licence choices/notices; the top-level Apache licence alone is insufficient.
Generate digest-specific SBOMs and collect OS copyright files, Java/Rust notices and
required corresponding-source offers during authorized image preparation. This audit
cannot establish those contents from Dockerfile names alone.

## Datasets and derived artifacts

| Dataset | Licence / evidence | Release constraint |
| --- | --- | --- |
| MOT 60-day GTFS | Exact terms unrecorded in [access record](data-usage-and-access.md) | **Blocking terms review:** public API display, raw redistribution, retention/fixtures and required attribution wording need evidence |
| MOT TripIdToDate | Separate dated mapping; no accepted terms recorded | Preserve full identities/service dates; do not infer permissions from GTFS access or the SIRI form |
| OSM Israel/Palestine extract via Geofabrik | [ODbL 1.0](https://opendatacommons.org/licenses/odbl/1-0/); [OSM notice](https://www.openstreetmap.org/copyright); [Geofabrik](https://www.geofabrik.de/data/download.html) | **© OpenStreetMap contributors** in visible results/docs/API metadata; comply with download etiquette |
| Derived MOTIS graph, SQLite/address catalog and Photon index | Inherit source obligations; classification of mixed/derived database vs produced work needs review | ODbL public-use/share-alike/access obligations may apply even while images remain private. Do not publish raw/derived artifacts without review of both OSM and MOT terms |
| IANA timezone data bundled by tzdata | [IANA database](https://www.iana.org/time-zones): public-domain core data; package wrapper Apache-2.0 | Keep packaged notices; inspect exact bundle for historical exceptions |
| Local playground OSM tiles | OSM data attribution plus separate [tile usage policy](https://operations.osmfoundation.org/policies/tiles/) | No bulk tile load scenario; upstream browser requests have their own privacy implications |

SIRI, alerts and other realtime datasets are deferred; no licence/access approval is
inferred for them. Synthetic fixtures must stay labelled and must not incorporate
unreviewed upstream excerpts into a public repository.

## Decisions and conflicts to resolve

1. **Choose OpenTransit code licence and repository visibility before M7 CI.** MIT or
   Apache-2.0 are candidates, not accepted decisions. Apache dependencies constrain a
   future GPL-2.0-only combined distribution; review actual linkage/distribution rather
   than treating every separate process as one work. Preserve third-party notices under
   either permissive choice. No root `LICENSE` is added by this audit.
2. **Separate code from data permissions.** ODbL database share-alike cannot be replaced
   by a permissive code licence; MOT's unknown terms may conflict with required ODbL
   sharing for combined derived artifacts. Obtain a classification/terms decision before
   public database/graph/image distribution and resolve public-use obligations too.
3. **Clear component redistribution obligations.** certifi MPL, OpenJDK GPL/Classpath
   Exception, base OS copyleft and shaded/vendor libraries need notices/source compliance;
   they are review flags, not a finding that OpenTransit code must become GPL/MPL.
4. **Approve source terms and publication wording.** Obtain exact MOT terms and review
   ODbL attribution, share-alike and data availability. Complete the artifact SBOM/notice
   audit before distributing images. [Policy drafts](policies/attribution.md) and
   [operations](operations.md) do not constitute legal approval or release acceptance.
