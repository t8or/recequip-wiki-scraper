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
