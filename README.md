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
