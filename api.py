import os
import json
import urllib.request
import urllib.parse
from typing import *

use_cache: bool = True
user_agent: Dict[str, str] = {"User-Agent": "Runelite Wiki Scraper/1.0 (+abex@runelite.net)"}

def get_wiki_api(args: Dict[str, str], continueKey: str) -> Iterator[Any]:
	args["format"] = "json"
	batches = []
	if 'titles' in args:
		titles = args.get("titles").split('|')
		batches = [titles[i:i+50] for i in range(0, len(titles), 50)]
	elif 'pageids' in args:
		pageids = args.get("pageids").split('|')
		batches = [pageids[i:i+50] for i in range(0, len(pageids), 50)]
	if batches:
		for batch in batches:
			if 'titles' in args:
				args["titles"] = "|".join(batch)
			elif 'pageids' in args:
				args["pageids"] = "|".join(batch)
			for js in get_wiki_api_helper(args, continueKey):
				yield js
	else:
		for js in get_wiki_api_helper(args, continueKey):
			yield js

def get_wiki_api_helper(args: Dict[str, str], continueKey: str) -> Iterator[Any]:
	while True:
		url = "https://oldschool.runescape.wiki/api.php?" + urllib.parse.urlencode(args)
		print("Grabbing " + url)
		with urllib.request.urlopen(urllib.request.Request(url, headers=user_agent)) as raw:
			js = json.load(raw)
		yield js
		if "continue" in js:
			args[continueKey] = js["continue"][continueKey]
		else:
			return

def query_category(category_name: str) -> Dict[str, str]:
	"""
	query_category returns a dict of page title to page wikitext
	you can then use mwparserfromhell to parse the wikitext into
	an ast
	"""
	cache_file_name = category_name + ".cache.json"
	if use_cache and os.path.isfile(cache_file_name):
		with open(cache_file_name, "r") as fi:
			return json.load(fi)

	pageids = []
	for res in get_wiki_api(
		{
		"action": "query",
		"list": "categorymembers",
		"cmlimit": "500",
		"cmtitle": "Category:" + category_name,
		}, "cmcontinue"):

		for page in res["query"]["categorymembers"]:
			pageids.append(str(page["pageid"]))

	pages = {}
	for i in range(0, len(pageids), 50):
		for res in get_wiki_api(
			{
			"action": "query",
			"prop": "revisions",
			"rvprop": "content",
			"pageids": "|".join(pageids[i:i + 50]),
			}, "rvcontinue"):
			for id, page in res["query"]["pages"].items():
				pages[page["title"]] = page["revisions"][0]["*"]

	with open(cache_file_name, "w+") as fi:
		json.dump(pages, fi)

	return pages
