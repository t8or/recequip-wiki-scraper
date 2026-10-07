# Variant discovery and matching validation

Validated locally on 2026-10-07. Neither repository was pushed or published.

## Deterministic checkpoints

- Scraper default branch is `master`, captured at `89f23186faeba8e31a067580b8d1f99732f2fcae`.
- Plugin default branch is `master`, captured at `e7c64ece0a83c49f98b25cdc57c34f7ee3f641cb`.
- Fresh unchanged-scraper output is committed separately as `e811436b4faeebd9217a2367913599b8ff2a87f3`.
- Runtime: Python 3.12.15, mwparserfromhell 0.6.6; Temurin JDK 17.0.20.1+1,
  Gradle 7.4, RuneLite client 1.13.1. Candidate Java tests used offline dependencies
  resolved by the successful baseline build.
- Raw pre-expansion JSON SHA-256: `78398891f47f3925bb56e481b06b6a8973342c1a992cd86d91290ec7c76e5165`.

The baseline ran the unchanged scraper and unchanged expansion step from the recorded
commit. Its 1,171 distinct real Wiki responses were captured once; repeated requests
reused them. The candidate ran its scraper and changed expansion step using only those
captured responses. A replay miss fails rather than silently fetching newer data.
Both raw scraper outputs were byte-identical. Candidate network requests: **0**.

Fresh baseline output differs from the default branch's checked-in data in 52 activities.
That separate baseline-data commit avoids attributing this drift to the new implementation.
The candidate comparisons below use the fresh baseline, not stale checked-in output.

## Results

| Check | Result |
|---|---|
| Activities / loadouts | 84 / 284, unchanged |
| Recommendation entries compared | 12,353 |
| Activity, style, slot, tier, and item-name structure | Unchanged |
| Original Wiki IDs removed | 0 |
| Recommendation entries changed | 803 |
| Added ID occurrences | 8,762 |
| Removed previous expansion ID occurrences | 628 |
| Changes only to ID ordering | 214 |
| Aggregate, minified, and per-activity outputs | Consistent |
| Second application of candidate expansion | Byte-identical across 90 JSON files |
| Python tests | 8 passed |
| Plugin baseline compile/test | Passed |
| Candidate bank placement / JSON contract tests | 5 passed |
| Runnable plugin JAR | Built successfully |
| Manual discovery, live catalog and offline catalog | Both succeeded; neither changed mappings |

The independent comparison checks every candidate ID list against accepted mappings,
slot constraints, and preference policy. It checks actual JSON structure and original
IDs, not just file counts. The Python suite additionally exercises overlapping rules,
incomplete chains, directed upgrades, invalid input, repeat runs, mixed source families,
slot mistakes, and advisory catalog discovery. Java tests exercise the actual bank
placement path with in-memory RuneLite widgets: highest owned preference independent
of bank order, rejection of weaker unaccepted IDs, correct duplicate icons/quantities,
and missing alternatives after an owned alternative. A fifth test reads actual generated
cape recommendations through the plugin Gson deserializer, rejects accumulator/attractor
IDs for an assembler, and selects an owned Dizana’s max cape ahead of an assembler.

## Reviewed behavior

- 45 imbued Slayer helmet IDs: the original three imbue-source IDs plus 42 verified
  cosmetic IDs. Non-imbued helmets are not accepted for an imbued recommendation.
- Corresponding imbued god max capes stay within their god-cape families.
- Explicit ranged direction: attractor → accumulator → assembler → quiver. No reverse
  assembler-to-accumulator/attractor relationship. Charged/blessed quivers precede
  uncharged quivers. Ordinary Max cape is not pooled with all max-cape variants.
- Reviewed one-way preferences replace previous bidirectional lower-tier acceptance
  for Elite Void, poisoned daggers, and other existing configured upgrades.
- Equipment-slot constraints prevent cape expansions in an existing malformed Arrows
  recommendation. Unrelated mixed-family source lists are not globally ranked or
  expanded to higher-preference items.
- Discovery remains a manual report: one catalog download, no Wiki calls, no writes
  to accepted mappings. Existing workflows and plugin JSON format are retained.

Removed baseline expansion IDs by recommendation label:

```json
{
  "Arrows": [
    27359,
    27374,
    27376
  ],
  "Ava's assembler": [
    27359
  ],
  "Crystal pickaxe": [
    23863,
    25112
  ],
  "Elite void robe": [
    8840,
    20469,
    24179,
    26465,
    27001
  ],
  "Elite void top": [
    8839,
    20465,
    24177,
    26463,
    27000
  ],
  "Void knight robe": [
    20471
  ],
  "Void knight top": [
    20467
  ]
}
```

These removals are previous expansions, not IDs scraped directly from the Wiki. They
include weaker standard Void IDs under Elite recommendations, non-equipable repair
states, restricted-game pickaxes, and expansions rejected by slot/comparability checks.

## Evidence and repeatability

The local workspace sibling directory `../validation/2026-10-07-89f2318/` contains:

- `checkpoint.json`, immutable baseline checkout, and candidate validation checkout;
- `run_scrape.py`, `wiki-responses/`, and both raw JSON snapshots;
- `compare_outputs.py`, `comparison.json` (per-recommendation additions/removals),
  and `comparison-summary.json`;
- baseline/candidate request counts and scrape logs;
- Python, baseline/candidate Java, and packaging logs;
- `output-sha256.json` and `candidate-second-pass.log`;
- offline and live manual discovery reports.

To repeat comparison without contacting the Wiki, use Python 3.12 with
mwparserfromhell 0.6.6 to run `run_scrape.py candidate` and `compare_outputs.py` from
that evidence directory. The evidence is local and is not part of this repository's
published source. The normal regression command is:

```sh
python -m unittest discover -s tests -v
```

## Limits

This is a deterministic scraper comparison and automated bank-placement validation,
not a logged-in in-game test. The local JAR still uses the published GitHub feed; the
new generated recommendations must be published separately before that feed changes.
No issues were commented on or closed.

The mapping prevents the reviewed downgrade relationships; it cannot establish every
item's contextual value automatically. Quiver ammunition recovery depends on account
unlocks. Original Wiki parser IDs are retained, including legacy mixed-family/repair
state results. The existing Arrows source anomaly is guarded against further expansion,
not repaired at its source. These limits should be checked in the in-game review and
any later work on item-page parsing.
