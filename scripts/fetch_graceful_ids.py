"""One-off: fetch Graceful piece infobox IDs from OSRS wiki (requires User-Agent)."""
import json
import re
import urllib.parse
import urllib.request

UA = "recequip-wiki-scraper/1.0"
SUFFIXES = [
    None,
    "Agility Arena",
    "Adventurer",
    "Varlamore",
    "Trailblazer",
    "Hosidius",
    "Shayzien",
    "Arceuus",
    "Lovakengj",
    "Hallowed",
    "Piscarilius",
    "Kourend",
]
SLOTS = ["hood", "cape", "top", "legs", "gloves", "boots"]


def title_for(slot: str, suffix: str | None) -> str:
    if suffix is None:
        return f"Graceful {slot}"
    return f"Graceful {slot} ({suffix})"


def infobox_ids(wikitext: str) -> list[int]:
    idx = wikitext.find("{{Infobox Item")
    chunk = wikitext[idx : idx + 30000] if idx >= 0 else wikitext[:30000]
    return sorted({int(m.group(1)) for m in re.finditer(r"\|id\d*\s*=\s*(\d+)", chunk)})


def fetch(title: str) -> list[int]:
    url = (
        "https://oldschool.runescape.wiki/api.php?action=parse&prop=wikitext&format=json&page="
        + urllib.parse.quote(title.replace(" ", "_"))
    )
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=30) as r:
        d = json.loads(r.read().decode())
    return infobox_ids(d["parse"]["wikitext"]["*"])


def main() -> None:
    by_slot: dict[str, set[int]] = {s: set() for s in SLOTS}
    for slot in SLOTS:
        for suf in SUFFIXES:
            t = title_for(slot, suf)
            try:
                ids = fetch(t)
                by_slot[slot].update(ids)
                print(t, ids)
            except Exception as e:
                print(t, "ERROR", e)
    print("--- UNION PER SLOT ---")
    for slot in SLOTS:
        print(slot, sorted(by_slot[slot]))


if __name__ == "__main__":
    main()
