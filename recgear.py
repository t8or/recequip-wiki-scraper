import api
import util
import os, sys
import re
import csv
import json
import mwparserfromhell as mw
from collections import defaultdict

itemCache = {}

def get_item_page_code(itemName):
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

def get_ids_of_item(itemCode, itemName):
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

def handle_special_cases(itemName):
    if itemName.replace('_', ' ').startswith('Cape of Accomplishment'):
        capePages = api.query_category('Capes of Accomplishment')
        ids = []
        for capeName, capePage in capePages.items():
            if capeName.endswith('cape'):
                capeCode = mw.parse(capePage, skip_style_tags=True)
                ids.extend(get_ids_of_item(capeCode, capeName))
        return ids
    elif itemName == "Explorer's ring":
        ids = []
        for i in range(1, 5):
            itemCode = get_item_page_code(itemName + f" {i}")
            ids.extend(get_ids_of_item(itemCode, itemName))
        return ids

def get_gear_from_slot(template, slot):
    gear = []
    for i in range(1, 6):
        if template.has(f"{slot}{i}"):
            # print(f"{slot}{i}")
            item = template.get(f"{slot}{i}").value
            tmps = item.filter_templates()
            # print(tmps)
            itemsWithIDs = defaultdict(list)
            for tmp in tmps:
                if tmp.name.matches('plink'):
                    name = tmp.params[0].value.strip()
                    if name in itemCache:
                        itemsWithIDs[name] = itemCache[name]
                        continue

                    specialCase = handle_special_cases(name)
                    if specialCase:
                        itemCache[name] = itemsWithIDs[name] = specialCase
                        continue

                    itemCode = get_item_page_code(name)
                    itemCache[name] = itemsWithIDs[name] = get_ids_of_item(itemCode, name)

                    if len(itemsWithIDs[name]) == 0:
                        ft = itemCode.filter_templates(matches=lambda t: t.name.matches('plink') or t.name.matches('CostLine'))
                        for tmp in ft:
                            subName = tmp.params[0].value.strip()
                            itemCode = get_item_page_code(subName)
                            itemsWithIDs[name].extend(get_ids_of_item(itemCode, subName))

                    # if still no ids found, raise exception
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
    tabs = defaultdict(dict)

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
            tabs[styleName][slot] = get_gear_from_slot(template, slot)
    return tabs

def run():
    itemCacheFile = 'item_ids.cache.json'
    if os.path.isfile(itemCacheFile):
        with open(itemCacheFile, 'r') as fi:
            global itemCache
            itemCache = json.load(fi)
    os.makedirs('recs', exist_ok=True)
    # titles = [
    #     'TzHaar_Fight_Cave/Strategies',
    #     'Barrows/Strategies',
    #     'Scurrius/Strategies',
    #     'Giant_Mole/Strategies',
    #     'Deranged_archaeologist/Strategies',
    #     'Dagannoth_Kings/Strategies',
    #     'Sarachnis/Strategies'
    # ]
    with open('data_to_import.csv', 'r') as csvfile:
        data = csv.reader(csvfile)
        next(data)
        titles = [row[1].replace('https://oldschool.runescape.wiki/w/', '') for row in data if row[1]]
        res = api.get_wiki_api({
            "action": "query",
            "prop": "revisions",
            "rvprop": "content",
            "rvslots": "main",
            # "pageids": pageID
            "titles": '|'.join(titles)
        }, "rvcontinue")
        for pageBatch in res:
            allActivityGearRecs = {}
            for pageID, page in pageBatch['query']['pages'].items():
                print(pageID, page['title'])
                pageContent = page["revisions"][0]['slots']['main']["*"]
                # print(res[0].keys())
                # print(res[0]["query"]["pages"][str(pageID)]["revisions"][0]['slots']['main']['*'])
                allGearRecs = get_page_tabs(pageContent)
                titleParts = page['title'].split('/')
                allActivityGearRecs[titleParts[0]] = allGearRecs

                fileName = '-'.join(titleParts)
                util.write_json(f'recs/{fileName}.json', f'recs/{fileName}.min.json', allGearRecs)
        util.write_json(f'recs/all.json', f'recs/all.min.json', allActivityGearRecs)
    util.write_json(None, itemCacheFile, itemCache)

