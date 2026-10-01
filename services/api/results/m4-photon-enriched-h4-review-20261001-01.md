# Six disputed address locations — source review packet

This packet requests independent review of six locations from one saved enriched Photon trial. **Human fields are blank.** It does not change frozen expectations, radii, scores or the ≥80% address criterion, and it is not final API H4 approval.

The trial returned 22 successful HTTP responses and scored **16/22** geometry top-1/top-5: **9/15 original**, **7/7 new source-node cases**. Five new cases use recorded `near` coordinates; unassisted geometry is **11/17**. Exact source-node identity is 6/7 top-1 and 7/7 top-5. All saved API successes are already Photon successes, so the offline provider union remains 16/22; that is not a merged ranking result.

A source record with the requested number/street/city is evidence of source consistency, not independent geographic truth. None of the original six cases records an expected OSM object ID. Do not copy a provider coordinate into the expected point or choose another street segment using that point.

## Preserved evidence

- [Versioned enriched trial](C:/Users/nhenr/.codex/worktrees/8007/OpenTransit/services/api/results/m4-photon-enriched-trial-20261001-01.json)
- [Exact saved requests and raw responses](C:/Users/nhenr/.codex/worktrees/8007/OpenTransit/.runtime/m4-photon-evaluation-20261001/photon-enriched-addresses-20261001-01.json)
- [Frozen corrected API baseline](C:/Users/nhenr/.codex/worktrees/8007/OpenTransit/services/api/results/m4-api-search-20260930-02-corrected.json)
- [Original source-node address dump](C:/Users/nhenr/.codex/worktrees/8007/OpenTransit/.runtime/m4-photon-spike-20260930/israel-address-nodes-photon-0.1.0.jsonl)
- [Retained source ways and administrative geometry](C:/Users/nhenr/.codex/worktrees/8007/OpenTransit/.runtime/m4-photon-context-20261001/context-v1.jsonl)
- [Enriched dump](C:/Users/nhenr/.codex/worktrees/8007/OpenTransit/.runtime/m4-photon-enrichment-20261001/israel-addresses-enriched-photon-0.1.0.jsonl) and [complete source-contribution sidecar](C:/Users/nhenr/.codex/worktrees/8007/OpenTransit/.runtime/m4-photon-enrichment-20261001/israel-addresses-enriched-photon-0.1.0.provenance.json)
- [Diagnosis and source hashes](C:/Users/nhenr/.codex/worktrees/8007/OpenTransit/services/api/results/m4-photon-enriched-diagnosis-20261001-01.json); [169 street-selection exclusions](C:/Users/nhenr/.codex/worktrees/8007/OpenTransit/services/api/results/m4-enrichment-street-selection-audit-20261001-01.json)

Source PBF SHA-256: `8a34b30f91a63ef9239961ba0e4d660ae22deda2f6da4b85ba4772a6b7c4c74f`. Source JSONL context and old node dump hashes were independently checked in this review. Raw enriched-trial SHA-256: `c586a75d59882ebecd8626a5d782801b3d39b76798efc97301e921cd5c3f9f91`. Full hashes are recorded in the diagnosis.

OSM links below are **identity navigation only**. No online content was fetched or verified; current OSM may differ from the retained PBF. Coordinates are WGS84 and shown as **latitude, longitude**. Distances use the unchanged corpus Earth radius **6,371,008.8 m**.

## Frozen failures

| Case | Query / language | Frozen expected latitude, longitude | Radius | Returned source object | Returned latitude, longitude | Distance | Source precision |
| --- | --- | --- | ---: | --- | --- | ---: | --- |
| P059 | Herzl 50 Haifa / en | 32.8156, 34.9942 | 800 m | [N13196140834](https://www.openstreetmap.org/node/13196140834) | 32.8075269, 35.0007915 | 1088.719 m | address-node point; roof/entrance unverified |
| P061 | Allenby 40 Tel Aviv / en | 32.0654, 34.7702 | 700 m | [N2079179445](https://www.openstreetmap.org/node/2079179445) | 32.072365, 34.768784 | 785.883 m | address-node point; roof/entrance unverified |
| P062 | HaNevi'im 20 Jerusalem / en | 31.7828, 35.22 | 700 m | [N2270796176](https://www.openstreetmap.org/node/2270796176) | 31.7835314, 35.2275288 | 716.263 m | address-node point; roof/entrance unverified |
| P063 | Sokolov 30 Ramat Gan / en | 32.0836, 34.811 | 800 m | [N2323944512](https://www.openstreetmap.org/node/2323944512) | 32.093282, 34.8192454 | 1327.567 m | address-node point; roof/entrance unverified |
| P064 | Rager Boulevard Beersheba / en | 31.253, 34.795 | 900 m | [W5005029](https://www.openstreetmap.org/way/5005029) | 31.24372605841935, 34.79357708190895 | 1040.051 m | street-way midpoint; no house precision |
| P065 | הרצל 50 חיפה / he | 32.8156, 34.9942 | 800 m | [N13196140834](https://www.openstreetmap.org/node/13196140834) | 32.8075269, 35.0007915 | 1088.719 m | address-node point; roof/entrance unverified |

All six remain failures under the frozen geometry rule. Every query, language, expected coordinate, radius, Earth radius and recorded `near` value matches the frozen baseline; none of these six uses `near`. Limit remains 10. The enriched helper explicitly requests both house and street layers; the old provider trial requested houses only.

## P059 — Herzl 50 Haifa

Frozen expected point: **32.8156, 34.9942**, radius **800 m**. Returned [N13196140834](https://www.openstreetmap.org/node/13196140834): **32.8075269, 35.0007915**; distance **1088.719 m**, exceeding the radius by **288.719 m**. HTTP 200; 1 candidate.

Original source address tags, copied from the preserved pre-enrichment node dump:

```json
{
  "addr:city": "חיפה",
  "addr:housenumber": "50",
  "addr:street": "הרצל"
}
```

The original source node coordinate is preserved exactly. Returned house number: **50**; returned street: **Herzl**. Its English/Hebrew street and locality aliases are supported by the following retained contributions, not by the corpus expectation:

Street ways: [W53441117](https://www.openstreetmap.org/way/53441117), [W995957808](https://www.openstreetmap.org/way/995957808), [W995957809](https://www.openstreetmap.org/way/995957809), [W1053096531](https://www.openstreetmap.org/way/1053096531), [W1053256442](https://www.openstreetmap.org/way/1053256442).

Source street name fields:

```json
[
  {
    "name": "הרצל",
    "name:he": "הרצל",
    "name:en": "Herzl"
  }
]
```

Locality contribution: [R1387888](https://www.openstreetmap.org/relation/1387888); sidecar status **unique_containing_locality**, source geometry **MultiPolygon**, `boundary=administrative`, `admin_level=8`. Source names:

```json
{
  "name": "חיפה",
  "name:he": "חיפה",
  "name:en": "Haifa"
}
```

The sidecar reports matched source street aliases and no conflicts for this node. This review verifies the retained identities, labels and coordinate preservation; it does not independently certify the real-world building location or roof/entrance precision.

P059 and P065 are an English/Hebrew pair returning the same source node and coordinate. They require one location adjudication, with both frozen failures retained.

Human review — leave blank until an independent verdict:

- Reviewer / date:
- Independent source or inspection method:
- Requested street/locality labels correct:
- Requested house-number identity correct (if applicable):
- Returned coordinate appropriate for the requested address/street:
- Frozen expected point/radius independently supported:
- Verdict (correct candidate / incorrect candidate / unresolved):
- Any proposed reference revision and independent justification:
- Explicit approval of a revision (if any):

## P061 — Allenby 40 Tel Aviv

Frozen expected point: **32.0654, 34.7702**, radius **700 m**. Returned [N2079179445](https://www.openstreetmap.org/node/2079179445): **32.072365, 34.768784**; distance **785.883 m**, exceeding the radius by **85.883 m**. HTTP 200; 1 candidate.

Original source address tags, copied from the preserved pre-enrichment node dump:

```json
{
  "addr:housenumber": "40",
  "addr:street": "אלנבי"
}
```

The original source node coordinate is preserved exactly. Returned house number: **40**; returned street: **Allenby**. Its English/Hebrew street and locality aliases are supported by the following retained contributions, not by the corpus expectation:

Street ways: [W239173014](https://www.openstreetmap.org/way/239173014), [W762618951](https://www.openstreetmap.org/way/762618951), [W1134725825](https://www.openstreetmap.org/way/1134725825), [W1197653096](https://www.openstreetmap.org/way/1197653096).

Source street name fields:

```json
[
  {
    "name": "אלנבי",
    "name:he": "אלנבי",
    "name:en": "Allenby"
  }
]
```

Locality contribution: [R1382494](https://www.openstreetmap.org/relation/1382494); sidecar status **unique_containing_locality**, source geometry **MultiPolygon**, `boundary=administrative`, `admin_level=8`. Source names:

```json
{
  "name": "תל־אביב–יפו",
  "name:he": "תל־אביב–יפו",
  "name:en": "Tel-Aviv"
}
```

The sidecar reports matched source street aliases and no conflicts for this node. This review verifies the retained identities, labels and coordinate preservation; it does not independently certify the real-world building location or roof/entrance precision.

Human review — leave blank until an independent verdict:

- Reviewer / date:
- Independent source or inspection method:
- Requested street/locality labels correct:
- Requested house-number identity correct (if applicable):
- Returned coordinate appropriate for the requested address/street:
- Frozen expected point/radius independently supported:
- Verdict (correct candidate / incorrect candidate / unresolved):
- Any proposed reference revision and independent justification:
- Explicit approval of a revision (if any):

## P062 — HaNevi'im 20 Jerusalem

Frozen expected point: **31.7828, 35.22**, radius **700 m**. Returned [N2270796176](https://www.openstreetmap.org/node/2270796176): **31.7835314, 35.2275288**; distance **716.263 m**, exceeding the radius by **16.263 m**. HTTP 200; 8 candidates.

Original source address tags, copied from the preserved pre-enrichment node dump:

```json
{
  "addr:housenumber": "20",
  "addr:street": "הנביאים"
}
```

The original source node coordinate is preserved exactly. Returned house number: **20**; returned street: **HaNeviim**. Its English/Hebrew street and locality aliases are supported by the following retained contributions, not by the corpus expectation:

Street ways: [W184893897](https://www.openstreetmap.org/way/184893897), [W184893908](https://www.openstreetmap.org/way/184893908), [W771909608](https://www.openstreetmap.org/way/771909608), [W774633464](https://www.openstreetmap.org/way/774633464), [W774633466](https://www.openstreetmap.org/way/774633466), [W774633471](https://www.openstreetmap.org/way/774633471), [W823928167](https://www.openstreetmap.org/way/823928167), [W998148853](https://www.openstreetmap.org/way/998148853), [W1001532397](https://www.openstreetmap.org/way/1001532397), [W1001532400](https://www.openstreetmap.org/way/1001532400), [W1001532402](https://www.openstreetmap.org/way/1001532402), [W1079809992](https://www.openstreetmap.org/way/1079809992), [W1182516715](https://www.openstreetmap.org/way/1182516715), [W1182516716](https://www.openstreetmap.org/way/1182516716).

Source street name fields:

```json
[
  {
    "name": "הנביאים",
    "name:he": "הנביאים",
    "name:en": "HaNeviim"
  }
]
```

Locality contribution: [R1381350](https://www.openstreetmap.org/relation/1381350); sidecar status **unique_containing_locality**, source geometry **MultiPolygon**, `boundary=administrative`, `admin_level=8`. Source names:

```json
{
  "name": "ירושלים | القدس",
  "name:he": "ירושלים",
  "name:en": "Jerusalem"
}
```

The sidecar reports matched source street aliases and no conflicts for this node. This review verifies the retained identities, labels and coordinate preservation; it does not independently certify the real-world building location or roof/entrance precision.

Rank 2 is a second retained HaNeviim 20 source node, [N5814720752](https://www.openstreetmap.org/node/5814720752), at **31.7835444, 35.2275235**, distance **715.931 m**. Both matching house points remain outside 700 m. Later candidates contain different street names; promoting them because of proximity would not establish the requested address.

Human review — leave blank until an independent verdict:

- Reviewer / date:
- Independent source or inspection method:
- Requested street/locality labels correct:
- Requested house-number identity correct (if applicable):
- Returned coordinate appropriate for the requested address/street:
- Frozen expected point/radius independently supported:
- Verdict (correct candidate / incorrect candidate / unresolved):
- Any proposed reference revision and independent justification:
- Explicit approval of a revision (if any):

## P063 — Sokolov 30 Ramat Gan

Frozen expected point: **32.0836, 34.811**, radius **800 m**. Returned [N2323944512](https://www.openstreetmap.org/node/2323944512): **32.093282, 34.8192454**; distance **1327.567 m**, exceeding the radius by **527.567 m**. HTTP 200; 1 candidate.

Original source address tags, copied from the preserved pre-enrichment node dump:

```json
{
  "addr:housenumber": "30",
  "addr:street": "סוקולוב"
}
```

The original source node coordinate is preserved exactly. Returned house number: **30**; returned street: **Sokolov**. Its English/Hebrew street and locality aliases are supported by the following retained contributions, not by the corpus expectation:

Street ways: [W156722185](https://www.openstreetmap.org/way/156722185), [W157436191](https://www.openstreetmap.org/way/157436191).

Source street name fields:

```json
[
  {
    "name": "סוקולוב",
    "name:he": "סוקולוב",
    "name:en": "Sokolov"
  }
]
```

Locality contribution: [R1382493](https://www.openstreetmap.org/relation/1382493); sidecar status **unique_containing_locality**, source geometry **MultiPolygon**, `boundary=administrative`, `admin_level=8`. Source names:

```json
{
  "name": "רמת גן",
  "name:he": "רמת גן",
  "name:en": "Ramat Gan"
}
```

The sidecar reports matched source street aliases and no conflicts for this node. This review verifies the retained identities, labels and coordinate preservation; it does not independently certify the real-world building location or roof/entrance precision.

Human review — leave blank until an independent verdict:

- Reviewer / date:
- Independent source or inspection method:
- Requested street/locality labels correct:
- Requested house-number identity correct (if applicable):
- Returned coordinate appropriate for the requested address/street:
- Frozen expected point/radius independently supported:
- Verdict (correct candidate / incorrect candidate / unresolved):
- Any proposed reference revision and independent justification:
- Explicit approval of a revision (if any):

## P064 — Rager Boulevard Beersheba

Frozen expected point: **31.253, 34.795**, radius **900 m**. Returned [W5005029](https://www.openstreetmap.org/way/5005029): **31.24372605841935, 34.79357708190895**; distance **1040.051 m**, exceeding the radius by **140.051 m**. HTTP 200; 1 candidate.

Retained source way tags:

```json
{
  "highway": "primary",
  "lanes": "3",
  "maxspeed": "60",
  "name": "שדרות יצחק רגר",
  "name:en": "Yitzhack Rager Avenue",
  "name:he": "שדרות יצחק רגר",
  "oneway": "yes",
  "surface": "asphalt"
}
```

The way has three retained coordinates:

```json
[
  [
    34.7935335,
    31.2436567
  ],
  [
    34.7935661,
    31.2437086
  ],
  [
    34.7936207,
    31.2437954
  ]
]
```

The export uses a geometry-derived midpoint of this individual road segment. The sidecar links it to enclosing locality [R1377264](https://www.openstreetmap.org/relation/1377264); the saved response labels the city **Be’er-Sheva**. The complete locality source tags and polygon are retained in the linked context file.

The retained context contains **46** ways with a primary source name containing “Rager”; all **46** were emitted. The provider returned one segment. Saved responses do not establish why that segment was selected. A single road-segment point cannot establish the location of the entire avenue, and it has no house-number precision. Do not substitute a segment nearest the frozen expected point.

Human review — leave blank until an independent verdict:

- Reviewer / date:
- Independent source or inspection method:
- Requested street/locality labels correct:
- Requested house-number identity correct (if applicable):
- Returned coordinate appropriate for the requested address/street:
- Frozen expected point/radius independently supported:
- Verdict (correct candidate / incorrect candidate / unresolved):
- Any proposed reference revision and independent justification:
- Explicit approval of a revision (if any):

## P065 — הרצל 50 חיפה

Frozen expected point: **32.8156, 34.9942**, radius **800 m**. Returned [N13196140834](https://www.openstreetmap.org/node/13196140834): **32.8075269, 35.0007915**; distance **1088.719 m**, exceeding the radius by **288.719 m**. HTTP 200; 1 candidate.

Original source address tags, copied from the preserved pre-enrichment node dump:

```json
{
  "addr:city": "חיפה",
  "addr:housenumber": "50",
  "addr:street": "הרצל"
}
```

The original source node coordinate is preserved exactly. Returned house number: **50**; returned street: **הרצל**. Its English/Hebrew street and locality aliases are supported by the following retained contributions, not by the corpus expectation:

Street ways: [W53441117](https://www.openstreetmap.org/way/53441117), [W995957808](https://www.openstreetmap.org/way/995957808), [W995957809](https://www.openstreetmap.org/way/995957809), [W1053096531](https://www.openstreetmap.org/way/1053096531), [W1053256442](https://www.openstreetmap.org/way/1053256442).

Source street name fields:

```json
[
  {
    "name": "הרצל",
    "name:he": "הרצל",
    "name:en": "Herzl"
  }
]
```

Locality contribution: [R1387888](https://www.openstreetmap.org/relation/1387888); sidecar status **unique_containing_locality**, source geometry **MultiPolygon**, `boundary=administrative`, `admin_level=8`. Source names:

```json
{
  "name": "חיפה",
  "name:he": "חיפה",
  "name:en": "Haifa"
}
```

The sidecar reports matched source street aliases and no conflicts for this node. This review verifies the retained identities, labels and coordinate preservation; it does not independently certify the real-world building location or roof/entrance precision.

P059 and P065 are an English/Hebrew pair returning the same source node and coordinate. They require one location adjudication, with both frozen failures retained.

Human review — leave blank until an independent verdict:

- Reviewer / date:
- Independent source or inspection method:
- Requested street/locality labels correct:
- Requested house-number identity correct (if applicable):
- Returned coordinate appropriate for the requested address/street:
- Frozen expected point/radius independently supported:
- Verdict (correct candidate / incorrect candidate / unresolved):
- Any proposed reference revision and independent justification:
- Explicit approval of a revision (if any):

## Review boundary

The next observation is an independent geographic-groundtruth verdict for these six cases. Source consistency alone cannot justify an expectation revision. Any future revision requires explicit approval and separately versioned expectations; this packet changes nothing. Provider/API integration, the unchanged ≥80% address requirement, source precision, display-language provenance, API p95, capacity and final API-path H4 approval remain separate requirements.
