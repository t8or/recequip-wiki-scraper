# Same-tier variant matching validation

Validated on 2026-10-07 against scraper production checkpoint
`89f23186faeba8e31a067580b8d1f99732f2fcae` and published Plugin Hub commit
`e7c64ece0a83c49f98b25cdc57c34f7ee3f641cb`. Both repositories use `master`.

## Final behavior

The Wiki defines recommendation choices and their order. Each named recommendation
accepts only explicitly reviewed variants of the same functional tier. Attractor,
accumulator, assembler and quiver remain independent. Ornamented and max-cape
variants can match their corresponding recommendation; automatic upgrades and
downgrades are not added. Warm cape additions require separate warmth evidence.
Oathplate imbued Slayer helmets remain accepted for combat and warm headwear.

The output contract is unchanged: item names map to arrays of integer IDs. Original
Wiki IDs remain first, so the existing plugin retains each missing item's icon.
No plugin update, display metadata, or plugin-side ranking is required.

## Deterministic comparison

The unchanged scraper's 1,171 distinct Wiki responses were recorded once. Both
baseline and candidate raw outputs were byte-identical; subsequent comparisons
reused the recording and made no additional Wiki requests.

| Check | Result |
|---|---|
| Activities / loadouts | 84 / 284, unchanged |
| Recommendation entries checked | 12,353 |
| Activity, style, slot, tier and item-name structure | Unchanged |
| Original Wiki IDs and their ordering | Preserved |
| Entries changed versus freshly scraped baseline | 738 |
| Added ID occurrences versus freshly scraped baseline | 7,239 |
| Removed previous expansion occurrences | 1,047 |
| Second expansion | Byte-identical across 90 JSON files |
| Python regression tests | 9 passed |
| Published plugin compatibility tests | 5 passed |

Raw pre-expansion JSON SHA-256:
`78398891f47f3925bb56e481b06b6a8973342c1a992cd86d91290ec7c76e5165`.
Validated generated `all.min.json` SHA-256:
`e574ed8c1f4596f61cf9b04c5b45b379619f73cb3d68d973f556617512c7d46b`.
The fresh baseline also incorporates ordinary Wiki drift from the prior checked-in
feed; that drift was recorded separately from the matching changes.

The five compatibility tests used the exact published plugin's production source
(all 41 source/resource files unchanged), RuneLite API 1.13.1, and in-memory bank
widgets. They covered full-feed parsing, separate cape choices and withdrawals,
ornamented helmets, warm cape eligibility, and rejection of cross-tier substitutions.
The user also successfully tested the candidate feed in-game with a local plugin
build containing additional optional display fixes. The unchanged published plugin
was tested automatically, not separately in-game.

## Maintenance and limits

Run `python -m unittest discover -s tests -v` and `python apply_variants.py`.
Both update workflows run the regression suite. Removing mappings requires a fresh
raw scrape before expansion; already-expanded data cannot identify old additions.
The discovery helper downloads one catalog and reports candidates without modifying
accepted mappings or querying individual Wiki pages.

Source-parser anomalies, including some mixed-state item pages and cape IDs in an
Arrows table, remain separate issues. This release preserves those original IDs and
constrains further expansion; it does not claim to repair all source parsing.
The published plugin selects the first eligible matching item in bank order within
each recommendation. Accepted ID array order does not prioritize owned matches by
stats or poison strength. For example, a normal Dragon dagger can be selected ahead
of an owned Dragon dagger(p++) when both IDs are accepted. This existing behavior
was verified in `BankTab.createPartialSection` at the published plugin checkpoint
above; compatibility tests do not establish strongest-owned-item selection.

The published plugin also retains its existing duplicate-icon and missing-alternative
behavior. Optional plugin fixes are outside this scraper release.

Detailed recorded responses, comparison reports and plugin test artifacts are in the
local validation workspace and are not required to run the production scraper.
