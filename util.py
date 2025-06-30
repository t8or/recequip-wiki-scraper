"""Utility functions for parsing and processing Old School RuneScape wiki data."""

import json
import re
from typing import Dict, List, Optional, Tuple, Iterator, Any, Callable, cast
from mwparserfromhell.nodes.template import Parameter
from mwparserfromhell.wikicode import Wikicode
from mwparserfromhell.nodes import Template

VERSION_EXTRACTOR = re.compile(r"(.*?)([0-9]+)?$")



def each_version(templateName: str, code: Wikicode, includeBase: bool = False,
    mergableKeys: List[str] | None = None) -> Iterator[Tuple[int, Dict[str, Any]]]:
    """
    each_version is a generator that yields each version of an infobox
    with variants, such as {{Infobox Item}} on [[Ring of charos]]
    """
    if mergableKeys is None:
        mergableKeys = ["version", "image", "caption"]
    infoboxes = filter_templates_by_name(templateName, code)
    if len(infoboxes) < 1:
        return
    for infobox in infoboxes:
        base: Dict[str, Wikicode] = {}
        versions: Dict[int, Dict[str, Wikicode]] = {}
        for param in cast(List[Parameter], infobox.params):
            matcher = VERSION_EXTRACTOR.match(str(param.name).strip())
            if matcher is None:
                raise AssertionError()
            primary = matcher.group(1)
            dic = base
            if matcher.group(2) is not None:
                version = int(matcher.group(2))
                if version not in versions:
                    versions[version] = {}
                dic = versions[version]
            dic[primary] = param.value
        if len(versions) == 0:
            yield (-1, base)
        else:
            allMergable = True
            for versionID, versionDict in versions.items():
                for key in versionDict:
                    if not key in mergableKeys:
                        allMergable = False
            if allMergable:
                yield (-1, base)
            else:
                if includeBase:
                    yield (-1, base)
                for versionID, versionDict in versions.items():
                    yield (versionID, {**base, **versionDict})


def write_json(name: str | None, minName: str | None, data: dict[str, Any] | list[Any]):
    """Write data to a JSON file"""
    if name is not None:
        with open(name, "w+", encoding="utf-8") as fi:
            json.dump(data, fi, indent=2)
    if minName is not None:
        with open(minName, "w+", encoding="utf-8") as fi:
            json.dump(data, fi, separators=(",", ":"))

def get_ids_for_page(source: str, version: Dict[str, str]) -> list[int] | None:
    """mostly a copy of get_doc_for_id_string but just returning a list"""
    if not "id" in version:
        print(f"page {source} is missing an id")
        return None

    ids = [int(id) for id in map(lambda id: id.strip(), str(version["id"]).split(",")) if id != "" and id.isdigit()]

    if len(ids) == 0:
        print(f"page {source} is has an empty id")
        return None

    return ids

def get_doc_for_id_string(source: str, version: Dict[str, str], docs: Dict[str, Dict[str, Any]],
    allowDuplicates: bool = False) -> Optional[Dict[str, Any]]:
    """Get a document for a given id string"""
    if not "id" in version:
        print(f"page {source} is missing an id")
        return None

    ids = [id for id in map(lambda id: id.strip(), str(version["id"]).split(",")) if id != "" and id.isdigit()]

    if len(ids) == 0:
        print(f"page {source} is has an empty id")
        return None

    doc: Dict[str, Any] = {}
    doc["__source__"] = source
    invalid = False
    for id in ids:
        if not allowDuplicates and id in docs:
            print(f"page {source} is has the same id as {docs[id]['__source__']}")
            invalid = True
        docs[id] = doc

    if invalid:
        return None
    return doc


def copy(name: str | Tuple[str, str],
    doc: Dict[str, Any],
    version: Dict[str, Any],
    convert: Callable[[Any], Any] = lambda x: x) -> bool:
    """Copy a value from one version to another"""
    srcName = name if isinstance(name, str) else name[0]
    dstName = name if isinstance(name, str) else name[1]
    if not srcName in version:
        return False
    strval = str(version[srcName]).strip()
    if strval == "":
        return False
    newval = convert(strval)
    if not newval:
        return False
    doc[dstName] = newval
    return True


def has_template(name: str, code: Wikicode) -> bool:
    """Check if a template exists in the code"""
    return len(filter_templates_by_name(name, code)) != 0

def filter_templates_by_name(name: str, code: Wikicode) -> List[Template]:
    """Filter templates by name"""
    return code.filter_templates(matches=lambda t: t.name.matches(name)) # type: ignore
