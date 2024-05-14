import api
import util
import os, sys
import re
import csv
import json
import mwparserfromhell as mw
from collections import defaultdict
from itertools import chain
from mwparserfromhell.wikicode import Wikicode, Template, Tag, Text

useCache: bool = True
itemCache = {}

def get_item_page_code(itemName: str):
    itemPage = api.get_wiki_api({
        'action': 'query',
        'prop': 'revisions',
        'rvprop': 'content',
        'rvslots': 'main',
        'titles': itemName,
        'redirects': 1
    }, 'rvcontinue')
    itemPage = list(itemPage)
    itemPage = itemPage[0]['query']['pages']
    pageID = list(itemPage.keys())[0]
    itemPage = itemPage[pageID]["revisions"][0]['slots']['main']['*']
    return mw.parse(itemPage, skip_style_tags=True)

def get_ids_of_item(itemCode: Wikicode, itemName: str):
    if itemName in itemCache:
        return itemCache[itemName]
    versions = util.each_version("Infobox Item", itemCode)
    ids = []
    for (vid, version) in versions:
        # if vid == -1:
        #     continue
        idsForVersion = util.get_ids_for_page(itemName + str(vid), version)
        if idsForVersion is None:
            continue
        ids.extend(idsForVersion)
    return ids

def handle_special_cases(itemName: str, template: Template):
    if itemName.replace('_', ' ').startswith('Cape of Accomplishment'):
        capePages = api.query_category('Capes of Accomplishment')
        ids = []
        for capeName, capePage in capePages.items():
            if capeName.endswith('cape'):
                capeCode = mw.parse(capePage, skip_style_tags=True)
                ids.extend(get_ids_of_item(capeCode, capeName))
        return ids
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
        ids = []
        for i in range(1, 5):
            itemCode = get_item_page_code(itemName + f" {i}")
            ids.extend(get_ids_of_item(itemCode, itemName))
        return ids
    elif itemName == 'Barrows helm':
        ids = []
        for i in ["Ahrim's hood", "Dharok's helm", "Guthan's helm", "Karil's coif", "Torag's helm", "Verac's helm"]:
            itemCode = get_item_page_code(i)
            ids.extend(get_ids_of_item(itemCode, itemName))
        return ids
    elif itemName == 'Barrows body':
        ids = []
        for i in ["Ahrim's robetop", "Dharok's platebody", "Guthan's platebody", "Karil's leathertop", "Torag's platebody", "Verac's brassard"]:
            itemCode = get_item_page_code(i)
            ids.extend(get_ids_of_item(itemCode, itemName))
        return ids
    elif itemName == 'Barrows legs':
        ids = []
        for i in ["Ahrim's robeskirt", "Dharok's platelegs", "Guthan's chainskirt", "Karil's leatherskirt", "Torag's platelegs", "Verac's plateskirt"]:
            itemCode = get_item_page_code(i)
            ids.extend(get_ids_of_item(itemCode, itemName))
        return ids
    elif itemName == 'Barrows equipment':
        if template.has('txt'):
            itemName = template.get('txt').value.strip()
            return handle_special_cases(itemName, template)
        else:
            raise Exception(f'No txt found for {itemName}')
    elif itemName == 'God staves':
        # TODO: would be nice to handle it below using the Infotable Bonuses template but
        # we need to check the redirect fragment and only get stuff inside
        return get_items_from_page('God spells')
    elif itemName == 'Damaged book' or itemName == 'Halo':
        itemCode = get_item_page_code(itemName)
        ids = []
        for link in itemCode.filter_wikilinks():
            ids.extend(get_items_from_page(link.title.strip()))
        return ids

def get_items_from_page(itemName: str):
    itemCode = get_item_page_code(itemName)
    ids = []
    for ft in itemCode.filter_templates():
        # Real item page, break out after getting ids
        if ft.name.matches('Infobox Item'):
            ids.extend(get_ids_of_item(itemCode, itemName))
            break

        # If a page has a bonus table, use it to get ids
        if ft.name.matches('Infotable Bonuses'):
            positionalParams = [p.value.strip() for p in ft.params if not p.showkey]
            for p in positionalParams:
                itemCode = get_item_page_code(p)
                ids.extend(get_ids_of_item(itemCode, p))
            break

        if ft.name.matches('plink') or ft.name.matches('plinkp') or ft.name.matches('plinkt') or ft.name.matches('CostLine'):
            subName = ft.params[0].value.strip()
            itemCode = get_item_page_code(subName)
            ids.extend(get_ids_of_item(itemCode, subName))
            continue

    # remove duplicates from ids without changing order
    return list(dict.fromkeys(ids))

def get_gear_from_slot(template, slot):
    gear = []
    for i in range(1, 6):
        if template.has(f"{slot}{i}"):
            # print(f"{slot}{i}")
            item = template.get(f"{slot}{i}").value

            # Stolen and modified from Wikicode source
            def getter(i, node):
                for ch in Wikicode._get_children(node):
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
            itemsWithIDs = defaultdict(list)
            for tmp in tmps:
                name = tmp.params[0].value.strip()
                if name in itemCache:
                    itemsWithIDs[name] = itemCache[name]
                    continue

                specialCase = handle_special_cases(name, tmp)
                if specialCase:
                    itemCache[name] = itemsWithIDs[name] = specialCase
                    continue

                itemCache[name] = itemsWithIDs[name] = get_items_from_page(name)

                # if no ids found, add it to a file to be manually checked later
                if len(itemsWithIDs[name]) == 0:
                    print(f'No ids found for {name}', file=sys.stderr)
                    del itemCache[name]
                    with open('items_that_need_special_handling.txt', 'r+') as fi:
                        if name in fi.read():
                            continue
                        fi.write(f'{name}\n')
                    # raise Exception(f'No ids found for {name}')
            gear.append(itemsWithIDs)

    return gear

def get_page_tabs(page):
    code = mw.parse(page, skip_style_tags=True)
    tabs = []

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

    for template in code.filter_templates(matches=lambda t: t.name.matches("Recommended equipment")):
        styleName = template.get("style").value.strip() if template.has("style") else "Default"
        style = { 'name': styleName }
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
        #     'Callisto/Strategies',
        #     # 'The Leviathan/Strategies',
        # ]
        res = api.get_wiki_api({
            "action": "query",
            "prop": "revisions",
            "rvprop": "content",
            "rvslots": "main",
            "titles": '|'.join(titles)
        }, "rvcontinue")

        urlMap = { row["title"].split('#')[0]: row for row in strategies }

        allActivityGearRecs = []
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

                util.write_json(f'recs/{name}.json', f'recs/{name}.min.json', allGearRecs)
        util.write_json(f'recs/all.json', f'recs/all.min.json', allActivityGearRecs)
    util.write_json(None, itemCacheFile, itemCache)

