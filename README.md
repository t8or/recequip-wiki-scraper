# Recommended Equipment Wiki Scraper

This project runs weekly to scrape the [OSRS Wiki](https://oldschool.runescape.wiki/) for recommended equipment from boss strategies pages defined in [data_to_import.csv](./data_to_import.csv) to be used in the [Recommended Equipment](https://runelite.net/plugin-hub/show/recommended-equipment) RuneLite plugin. This file should be updated to include new boss recommendations.

Since this data pulls directly from the wiki, if there is something missing or wrong in the plugin, updating the wiki should fix it. For example, a lot of Equipment tables are set with styles like Melee, Range, and Magic instead of what their tab is called. So if there are multiple "range" setups they will be hard to distinguish in the plugin. Update the wiki!

## Development

```
pipenv install
pipenv run python main.py
```

This project caches item ids as it finds them so that subsequent fetches, e.g. different equipment styles or bosses that use the same item, don't have to make a request and parse the wiki again. If you wish to run fresh (in case items have new variations or otherwise), run `rm *.cache.json` prior to running.

The [items_that_need_special_handling.txt](./items_that_need_special_handling.txt) file contains items (if any) scraped from boss strategies that were not able to successfully resolve to IDs. Exceptions will need to be added to [recequip.py](./recequip.py) in the `handle_special_cases` function for those items.

## Codebase Structure

### Core Components
- **`main.py`** - Entry point that enables caching and runs the scraper
- **`recequip.py`** - Core scraping logic (302 lines) with item resolution and special case handling
- **`api.py`** - Wiki API wrapper with caching and batch processing capabilities  
- **`util.py`** - Utility functions for parsing MediaWiki templates and handling item versions

### Data Files
- **`data_to_import.csv`** - Boss/activity definitions with URLs of which bosses to scrape(122 entries as of 6/28/25)
- **`recs/`** - Output directory with JSON files containing equipment recommendations
- **`items_that_need_special_handling.txt`** - Log of items requiring manual intervention

### Architecture
**Data Flow:** CSV definitions → Wiki API → MediaWiki parsing → Item ID resolution → JSON output

**Key Features:**
- File-based caching system (`*.cache.json`) for efficiency with enhanced caching in special case handling
- Batch processing (50-item batches) for API rate limiting
- Advanced special case handling for complex items including:
  - Barrows equipment (helms, bodies, legs) with specific item mappings
  - Achievement Diary items (Ardougne cloak, Desert amulet, etc.) with proper version handling
  - Cape of Accomplishment variants
  - Link pages (Damaged book, Halo, Blessing) that reference multiple items
  - God staves and equipment with redirect handling
- Improved version management with accurate versioned item name tracking (e.g., "Ardougne cloak 1" vs base "Ardougne cloak")
- Enhanced item tracking with tuple return format `(item_ids, item_name)` for better data integrity
- Wiki section parsing support for items with fragment identifiers (#section)
- Error recovery with logging for unresolvable items

**Output Format:** Structured JSON with equipment slots containing item names mapped to game IDs:
```json
{
  "name": "Magic",
  "head": [{"Item Name": [item_ids]}],
  "neck": [...],
  "cape": [...]
}
```

## TODO

### Future Improvements
- **Enhanced God Staves Handling**: Improve handling of God staves using the Infotable Bonuses template by checking redirect fragments to only extract relevant items (currently uses workaround via God spells page)
- **Complete Tab Name Parsing**: Implement better parsing for tabber elements to utilize actual tab names from wiki pages instead of relying solely on recommendation template style names, ensuring better alignment between plugin display and website tabs
- **Template Coverage Expansion**: Add support for additional MediaWiki templates beyond current plink variants (plink, plinkp, plinkt, CostLine) to capture more item references

## Maintaining item variants

`variant_ids.json` is the accepted mapping. Normal scrapes join it locally through
`apply_variants.py`; variant discovery never runs as part of the scheduled scrape.
The plugin output remains an array of integer IDs per recommendation.

To look for new variants, run the existing helper with an item-name search:

```sh
python scripts/build_bulk_variant_ids.py --search 'slayer helmet|max cape|quiver'
```

It downloads the Weird Gloop item catalog once, makes no Wiki requests, and prints
candidates without modifying any files. Use `--catalog /path/to/itemsmin.js` to
reuse a downloaded catalog offline. The search is case-insensitive regex. This is
scoped discovery, not an exhaustive equivalence detector: run it for the equipment
you want to maintain. It includes IDs known elsewhere but not accepted by each
matching mapping, and flags whether they are equipable. Such gaps can be intentional.

Review candidates using the linked item-ID lookup and relevant Wiki infoboxes.
A name match, identical model, or RuneLite variant group does **not** establish that
one item can replace another. Check functionality, imbues, charges, restricted-game
versions, and repair state. Accept reviewed variants of the same functional tier;
never add an automatic upgrade or downgrade. Record source evidence in `note`.

Each mapping has `base_id`, `extra_ids`, and optional `name`, `note`, `tier`, `slot`,
and `warm` fields:

- `base_id` identifies a recommended item; `extra_ids` explicitly lists its reviewed
  variants. Names document the mapping; they do not establish equivalence.
- `tier` defaults to zero and is a validation boundary, not a ranking. Every extra
  must have the same tier as its base. Cross-tier edges fail before output is written.
- Accepted relationships must be explicit and complete. Validation rejects duplicate
  base IDs and incomplete chains rather than inferring new relationships.
- `slot` restricts a mapping to its equipment slot. `warm: true` records verified warmth
  for an added cape variant; combat equivalence alone cannot establish warmth.
- Wiki choices, tiers, original IDs and their order remain intact. Expansion appends
  variants without sorting. Each named recommendation stays independently selectable.

Attractor, accumulator, assembler and quiver are separate choices. An assembler's
ornament/max variants can satisfy an assembler recommendation, but cannot satisfy
an accumulator or attractor recommendation. Charged states, imbues and other functional
variants require review rather than a blanket stronger-is-acceptable rule.

Original IDs returned by the Wiki parser remain intact. Some existing broad or
versioned item-page results still mix states; this change removes automatic expansion
across tiers and does not claim to repair those separate source-parsing problems.

After reviewing additions, edit `variant_ids.json`, then run:

```sh
python -m unittest discover -s tests -v
python apply_variants.py
```

Review the generated JSON diff before committing. Both existing update workflows run
the same tests. The helper no longer rewrites the mapping or preserves only a hardcoded
subset of manual entries. There is no second registry, compiler, or persistent discovery
state to synchronize.

**Removing an accepted replacement requires fresh scraper output.** The expanded JSON
does not retain which IDs were originally scraped versus added by earlier mappings.
Applying a narrower mapping to already-expanded output cannot remove old IDs. Run the
normal scraper first (or replay recorded Wiki responses), then apply the narrowed mapping
and review the removals. Do not silently remove IDs that originated in the Wiki itself.

### How the published plugin selects an owned item

**The published plugin selects the first matching item in bank order.** Within a
single recommendation's accepted ID list, it scans eligible bank item widgets and
uses the first match. It does not rank owned matches by stats, poison strength, or
their position in the scraper's ID array. Reordering those IDs therefore does not
make a stronger owned variant take priority.

For example, if a recommendation accepts both a normal Dragon dagger and a
Dragon dagger(p++), the normal dagger can be selected first when both are banked.
An accepted ID list defines which items qualify, not which owned item is preferred.
The Wiki's order of separate recommendations remains a different concern.

This behavior was verified against published plugin commit
`e7c64ece0a83c49f98b25cdc57c34f7ee3f641cb` in
[`BankTab.createPartialSection`](https://github.com/t8or/runelite-recommended-equipment/blob/e7c64ece0a83c49f98b25cdc57c34f7ee3f641cb/src/main/java/com/adamk33n3r/runelite/recommendedequipment/banktab/BankTab.java).
The scraper-only release does not change this selection behavior.

### Missing-item display icons

Expansion preserves the original first Wiki ID and appends reviewed variants. Thus
missing icons retain the Wiki's representative item without new display metadata.
The published plugin can consume this output without an update. No `display_ids`
metadata or plugin-side ranking is required.

`Warm clothing` cape recommendations retain the Wiki's listed IDs and permit
additional variants only when their mapping entry explicitly records `warm: true`.
Warmth is a separate property: max capes can be warm when their ordinary combat
counterparts are not. The verified Masori assembler max-cape variants retain their
warmth; ordinary accumulators, assemblers and god capes do not inherit it.
Headwear expansion remains unchanged, including the imbued Oathplate Slayer helmets.
Regenerate from raw scraper output to remove old expansions; reapplying to an
already-expanded list cannot distinguish original items from previous additions.
