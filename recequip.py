"""Script to scrape recommended gear from the oldschool runescape wiki"""

import os
import sys
import csv
import json
from collections import defaultdict
from itertools import chain
from typing import Any
import mwparserfromhell as mw
from mwparserfromhell.nodes import Template, Tag, Text
from mwparserfromhell.wikicode import Wikicode
import api
import util

useCache: bool = True
itemCache: dict[str, list[int]] = {}

def get_item_page_code(itemName: str):
    """
    Retrieve and parse the wiki page content for a given item name.
    
    Args:
        itemName (str): The name of the item to look up on the wiki
        
    Returns:
        mwparserfromhell.wikicode.Wikicode: Parsed wiki page content
    """
    itemPage = api.get_wiki_api({
        'action': 'query',
        'prop': 'revisions',
        'rvprop': 'content',
        'rvslots': 'main',
        'titles': itemName,
        'redirects': '1',
    }, 'rvcontinue')
    itemPage = list(itemPage)
    itemPage = itemPage[0]['query']['pages']
    pageID = list(itemPage.keys())[0]
    itemPage = itemPage[pageID]["revisions"][0]['slots']['main']['*']
    return mw.parse(itemPage, skip_style_tags=True)

def get_ids_of_item(itemCode: Wikicode, itemName: str) -> list[int]:
    """
    Extract item IDs from a parsed wiki page containing item information.
    
    Args:
        itemCode (Wikicode): Parsed wiki page content
        itemName (str): Name of the item being processed
        
    Returns:
        list: List of item IDs found for the given item
    """
    if itemName in itemCache:
        return itemCache[itemName]
    versions = util.each_version("Infobox Item", itemCode)
    ids: list[int] = []
    for (vid, version) in versions:
        # if vid == -1:
        #     continue
        idsForVersion = util.get_ids_for_page(itemName + str(vid), version)
        if idsForVersion is None:
            continue
        ids.extend(idsForVersion)
    return ids

def handle_special_cases(itemName: str, template: Template) -> tuple[list[int] | None, str | None]:
    """
    Handle special cases for items that require custom processing logic.
    
    This function handles items like achievement capes, barrows equipment,
    god staves, and other items that don't follow standard wiki patterns.
    
    Args:
        itemName (str): Name of the item to process
        template (Template): Wiki template containing item information
        
    Returns:
        tuple: (list of item IDs, item name) or (None, None) if no special case applies
    """
    if itemName in itemCache:
        return itemCache[itemName], itemName
    ids: list[int] = []
    if itemName.replace('_', ' ').startswith('Cape of Accomplishment'):
        capePages = api.query_category('Capes of Accomplishment')
        for capeName, capePage in capePages.items():
            if capeName.endswith('cape'):
                capeCode = mw.parse(capePage, skip_style_tags=True)
                ids.extend(get_ids_of_item(capeCode, capeName))
        return ids, itemName
    elif itemName in [
        "Ardougne cloak",
        "Desert amulet",
        "Falador shield",
        "Fremennik sea boots",
        "Kandarin headgear",
        "Karamja gloves",
        "Rada's blessing",
        "Explorer's ring",
        "Morytania legs",
        "Varrock armour",
        "Western banner",
        "Wilderness sword"
    ]:
        for i in range(1, 5):
            itemNameVersion = itemName + f" {i}"
            itemCode = get_item_page_code(itemNameVersion)
            ids.extend(get_ids_of_item(itemCode, itemNameVersion))
        return ids, itemName
    elif itemName == 'Barrows helm':
        for i in ["Ahrim's hood", "Dharok's helm", "Guthan's helm", "Karil's coif", "Torag's helm", "Verac's helm"]:
            itemCode = get_item_page_code(i)
            ids.extend(get_ids_of_item(itemCode, itemName))
        return ids, itemName
    elif itemName == 'Barrows body':
        for i in ["Ahrim's robetop", "Dharok's platebody", "Guthan's platebody", "Karil's leathertop", "Torag's platebody", "Verac's brassard"]:
            itemCode = get_item_page_code(i)
            ids.extend(get_ids_of_item(itemCode, itemName))
        return ids, itemName
    elif itemName == 'Barrows legs':
        for i in ["Ahrim's robeskirt", "Dharok's platelegs", "Guthan's chainskirt", "Karil's leatherskirt", "Torag's platelegs", "Verac's plateskirt"]:
            itemCode = get_item_page_code(i)
            ids.extend(get_ids_of_item(itemCode, itemName))
        return ids, itemName
    elif itemName == 'Barrows equipment':
        if template.has('txt'):
            newItemName: str = template.get('txt').value.strip()
            return handle_special_cases(newItemName, template)
        else:
            raise Exception(f'No txt found for {itemName}: {template}')
    elif itemName == 'God staves':
        # TODO: would be nice to handle it below using the Infotable Bonuses template but
        # we need to check the redirect fragment and only get stuff inside
        return get_items_from_page('God spells'), itemName

    # Link pages
    elif itemName in [
        'Damaged book',
        'Halo',
    ]:
        itemCode = get_item_page_code(itemName)
        for link in itemCode.filter_wikilinks():
            ids.extend(get_items_from_page(link.title.strip()))
        return ids, itemName
    elif itemName == 'Blessing':
        for i in ["God blessings", "Rada's blessing"]:
            ids.extend(get_items_from_page(i))
        return ids, itemName
    return None, None

def get_alt_items(itemName: str) -> list[str]:
    """
    Get alternative item names for a given item name.
    
    Args:
        itemName (str): Name of the item to get alternative names for
        
    Returns:
        list: List of alternative item names, or itemName if no alternatives found
    """
    if itemName == "Skull sceptre":
        return ["Skull sceptre", "Skull sceptre (i)"]
    return [itemName]

def get_items_from_page(itemName: str):
    """
    Extract item IDs from a wiki page, handling various page structures and templates.
    
    Args:
        itemName (str): Name of the item or page to process (can include section fragments)
        
    Returns:
        list: List of unique item IDs found on the page
    """
    sectionName = None
    if '#' in itemName:
        itemName, sectionName = itemName.split('#')
    itemCode = get_item_page_code(itemName)
    if sectionName is not None:
        itemCode = itemCode.get_sections(matches=sectionName.replace('_', ' '))[0]
    ids: list[int] = []
    for ft in itemCode.filter_templates():
        # Real item page, break out after getting ids
        if ft.name.matches('Infobox Item'):
            ids.extend(get_ids_of_item(itemCode, itemName))
            break

        # If a page has a bonus table, use it to get ids
        if ft.name.matches('Infotable Bonuses'):
            positionalParams = [p.value.strip() for p in ft.params if not p.showkey]
            for p in positionalParams:
                for i in get_alt_items(p):
                    itemCode = get_item_page_code(i)
                    ids.extend(get_ids_of_item(itemCode, i))
            break

        if ft.name.matches('plink') or ft.name.matches('plinkp') or ft.name.matches('plinkt') or ft.name.matches('CostLine'):
            subName = ft.params[0].value.strip()
            for i in get_alt_items(subName):
                itemCode = get_item_page_code(i)
                ids.extend(get_ids_of_item(itemCode, i))
            continue

    # remove duplicates from ids without changing order
    return list(dict.fromkeys(ids))

def get_gear_from_slot(template: Template, slot: str) -> list[dict[str, list[int]]]:
    """
    Extract gear recommendations for a specific equipment slot from a template.
    
    Args:
        template: Wiki template containing gear recommendations
        slot (str): Equipment slot name (e.g., 'head', 'body', 'weapon')
        
    Returns:
        list: List of dictionaries containing gear items with their IDs for the slot
    """
    gear: list[dict[str, list[int]]] = []
    for i in range(1, 6):
        if template.has(f"{slot}{i}"):
            # print(f"{slot}{i}")
            item = template.get(f"{slot}{i}").value

            # Stolen and modified from Wikicode source
            def getter(i, node):
                # pylint: disable=protected-access
                for ch in Wikicode._get_children(node): # type: ignore
                    if isinstance(ch, Tag) and ch.tag == 'ref':
                        break
                    if isinstance(ch, Text):
                        continue
                    yield (i, ch)
            nodes = chain(*(getter(i, n) for i, n in enumerate(item.nodes)))
            tmps = [node for i, node in nodes if isinstance(node, Template) and node.name.matches('plink')]

            # No templates in slot
            if len(tmps) == 0:
                continue
            itemsWithIDs: defaultdict[str, list[int]] = defaultdict(list)
            for tmp in tmps:
                name = tmp.params[0].value.strip()
                specialCase, specialCaseName = handle_special_cases(name, tmp)
                if specialCase:
                    specialCaseName = specialCaseName if specialCaseName else name
                    itemCache[specialCaseName] = itemsWithIDs[specialCaseName] = specialCase
                    continue

                if name in itemCache:
                    itemsWithIDs[name] = itemCache[name]
                    continue

                itemCache[name] = itemsWithIDs[name] = get_items_from_page(name)

                # if no ids found, add it to a file to be manually checked later
                if len(itemsWithIDs[name]) == 0:
                    print(f'No ids found for {name}', file=sys.stderr)
                    del itemCache[name]
                    with open('items_that_need_special_handling.txt', 'r+', encoding='utf-8') as fi:
                        if name in fi.read():
                            continue
                        fi.write(f'{name}\n')
                    # raise Exception(f'No ids found for {name}')
            gear.append(itemsWithIDs)

    return gear

def get_page_tabs(page: str) -> list[dict[str, Any]]:
    """
    Extract all gear recommendation styles/tabs from a wiki page.
    
    Args:
        page (str): Raw wiki page content
        
    Returns:
        list: List of dictionaries containing gear recommendations for each style/tab
    """
    code = mw.parse(page, skip_style_tags=True)
    tabs: list[dict[str, Any]] = []

    # Will probably need to do better parsing to be able to utilize tab names. Not all tabs have the rec template.
    # Perhaps when we look at the tabber and find the tab, we can "get the next rec template" unless we find another tab.
    # Seems complicated. Unfortunately, that means that what is displayed in the panel won't 100% match the website tabs.
    # for tag in code.filter_tags():
    #     if tag.tag.nodes[0].value == 'tabber':
    #         stripped = tag.contents.strip_code().replace('\n', '')
    #         tabNames = list(re.match(r'(.*?)=', stripped).groups())
    #         tabNames.extend(re.findall(r'\|-\|(.*?)=', stripped))
    #         print(tabNames)
    #         break

    for template in util.filter_templates_by_name("Recommended equipment", code):
        styleName: str = str(template.get("style").value.strip()) if template.has("style") else "Default"
        style: dict[str, Any] = { 'name': styleName }
        print('Getting recs for', styleName)
        slots = [
            "head",
            "neck",
            "cape",
            "body",
            "legs",
            "weapon",
            "shield",
            "ammo",
            "hands",
            "feet",
            "ring",
            "special",
        ]
        for slot in slots:
            style[slot] = get_gear_from_slot(template, slot)
        tabs.append(style)
    return tabs

def run():
    """
    Main function to scrape recommended gear from the Old School RuneScape wiki.
    
    This function:
    1. Loads cached item IDs if available
    2. Reads strategy data from CSV file
    3. Fetches wiki pages for each strategy
    4. Extracts gear recommendations from each page
    5. Saves results to JSON files
    6. Updates the item cache
    """
    itemCacheFile = 'item_ids.cache.json'
    if useCache and os.path.isfile(itemCacheFile):
        with open(itemCacheFile, 'r') as fi:
            global itemCache
            itemCache = json.load(fi)
    os.makedirs('recs', exist_ok=True)
    with open('data_to_import.csv', 'r') as csvfile:
        data = csv.reader(csvfile)
        next(data)
        strategies = [{
            "name": row[0],
            "url": row[1],
            "title": row[1].replace('https://oldschool.runescape.wiki/w/', ''),
            "category": row[2],
            # "location": row[3],
        } for row in data if row[1]]
        titles = [strategy['title'] for strategy in strategies]
        # titles = [
        #     # 'TzHaar_Fight_Cave/Strategies',
        #     # 'Barrows/Strategies',
        #     # 'Scurrius/Strategies',
        #     # 'Giant_Mole/Strategies',
        #     # 'Deranged_archaeologist/Strategies',
        #     # 'Dagannoth_Kings/Strategies',
        #     # 'Sarachnis/Strategies'
        #     # 'Callisto/Strategies',
        #     # 'The Leviathan/Strategies',
        #     # 'Nex/Strategies',
        #     # 'Amoxliatl/Strategies',
        #     # 'Araxxor/Strategies',
        #     # 'Wintertodt/Strategies',
        #     # 'The Hueycoatl/Strategies',
        #     'Doom_of_Mokhaiotl/Strategies'
        # ]
        res = api.get_wiki_api({
            "action": "query",
            "prop": "revisions",
            "rvprop": "content",
            "rvslots": "main",
            "titles": '|'.join(titles)
        }, "rvcontinue")

        urlMap = { row["title"].split('#')[0]: row for row in strategies }

        allActivityGearRecs: list[dict[str, Any]] = []
        for pageBatch in res:
            for pageID, page in pageBatch['query']['pages'].items():
                print(page['title'], pageID)
                pageContent = page["revisions"][0]['slots']['main']["*"]
                allGearRecs = get_page_tabs(pageContent)
                data = urlMap[page['title'].replace(' ', '_')]
                name = data['name']
                newData = {
                    **data,
                    'styles': allGearRecs
                }
                del newData['title']
                allActivityGearRecs.append(newData)

                util.write_json(f'recs/{name}.json', None, allGearRecs)
                util.write_json(None, itemCacheFile, itemCache)
        util.write_json(f'recs/all.json', f'recs/all.min.json', allActivityGearRecs)
    util.write_json(None, itemCacheFile, itemCache)

