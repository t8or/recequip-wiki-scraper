#!/usr/bin/env python3
"""Build bulk variant_ids.json entries; merge with existing Elidinis/Ava's/Rune pouch rows."""
from __future__ import annotations

import json
import re
import sys
import urllib.parse
import urllib.request
from pathlib import Path

UA = "recequip-wiki-scraper/1.0"
ROOT = Path(__file__).resolve().parents[1]
VARIANT_PATH = ROOT / "variant_ids.json"


def wiki_ids(title: str) -> list[int]:
    url = (
        "https://oldschool.runescape.wiki/api.php?action=parse&prop=wikitext&format=json&page="
        + urllib.parse.quote(title.replace(" ", "_"))
    )
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=45) as r:
        d = json.loads(r.read().decode())
    if "error" in d:
        raise RuntimeError(d["error"].get("info", str(d["error"])))
    t = d["parse"]["wikitext"]["*"]
    idx = t.find("{{Infobox Item")
    chunk = t[idx : idx + 35000] if idx >= 0 else t[:35000]
    return sorted({int(m.group(1)) for m in re.finditer(r"\|id\d*\s*=\s*(\d+)", chunk)})


def peer_entries(name: str, family: list[int], note: str) -> list[dict]:
    s = sorted(set(family))
    out = []
    for bid in s:
        extra = [x for x in s if x != bid]
        out.append({"base_id": bid, "name": name, "note": note, "extra_ids": extra})
    return out


def main() -> None:
    entries: list[dict] = []

    slayer = wiki_ids("Slayer helmet (i)")
    entries.extend(peer_entries("Slayer helmet (i)", slayer, "Recolor variants (all Slayer helmet (i) IDs)"))

    black = wiki_ids("Black mask (i)")
    entries.extend(peer_entries("Black mask (i)", black, "Recolor variants (all Black mask (i) IDs)"))

    suffixes = [
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
    slots = ["hood", "cape", "top", "legs", "gloves", "boots"]
    for slot in slots:
        fam: set[int] = set()
        for suf in suffixes:
            title = f"Graceful {slot}" if suf is None else f"Graceful {slot} ({suf})"
            fam.update(wiki_ids(title))
        entries.extend(
            peer_entries(
                f"Graceful {slot}",
                list(fam),
                "All graceful kit/recolor variants for this slot (wiki infobox IDs)",
            )
        )

    bowfa = wiki_ids("Bow of faerdhinen") + wiki_ids("Bow of faerdhinen (c)")
    entries.extend(peer_entries("Bow of faerdhinen", bowfa, "Inactive/active + corrupted (c)"))

    blade = wiki_ids("Blade of saeldor") + wiki_ids("Blade of saeldor (c)")
    entries.extend(peer_entries("Blade of saeldor", blade, "Inactive/active + corrupted (c)"))

    crystal_helm: list[int] = []
    crystal_body: list[int] = []
    crystal_legs: list[int] = []
    for clan in ["Amlodd", "Cadarn", "Crwys", "Hefin", "Iorwerth", "Ithell", "Trahaearn", "deadman"]:
        crystal_helm.extend(wiki_ids(f"Crystal helm ({clan})"))
        crystal_body.extend(wiki_ids(f"Crystal body ({clan})"))
        crystal_legs.extend(wiki_ids(f"Crystal legs ({clan})"))
    crystal_helm = wiki_ids("Crystal helm") + crystal_helm
    crystal_body = wiki_ids("Crystal body") + crystal_body
    crystal_legs = wiki_ids("Crystal legs") + crystal_legs
    entries.extend(peer_entries("Crystal helm", crystal_helm, "Base + inactive + all elven recolors + deadman"))
    entries.extend(peer_entries("Crystal body", crystal_body, "Base + inactive + all elven recolors + deadman"))
    entries.extend(peer_entries("Crystal legs", crystal_legs, "Base + inactive + all elven recolors + deadman"))

    cuisse = wiki_ids("Proselyte cuisse")[0]
    tasset = wiki_ids("Proselyte tasset")[0]
    entries.append(
        {
            "base_id": cuisse,
            "name": "Proselyte cuisse",
            "note": "Equivalent leg slot: Proselyte tasset (skirt)",
            "extra_ids": [tasset],
        }
    )
    entries.append(
        {
            "base_id": tasset,
            "name": "Proselyte tasset",
            "note": "Equivalent leg slot: Proselyte cuisse (platelegs)",
            "extra_ids": [cuisse],
        }
    )

    claws = wiki_ids("Dragon claws") + wiki_ids("Dragon claws (or)") + wiki_ids("Dragon claws (cr)")
    entries.extend(peer_entries("Dragon claws", claws, "Normal + ornament (or) + Bounty Hunter (cr)"))

    bh_cr = [
        "Dragon dagger",
        "Dragon battleaxe",
        "Dragon boots",
        "Dragon chainbody",
        "Dragon crossbow",
        "Dragon halberd",
        "Dragon mace",
        "Dragon warhammer",
        "Dragon 2h sword",
    ]
    bh_bh = [
        ("Dark bow", "Dark bow (bh)"),
        ("Barrelchest anchor", "Barrelchest anchor (bh)"),
        ("Abyssal dagger", "Abyssal dagger (bh)"),
    ]
    for base in bh_cr:
        cr_title = f"{base} (cr)"
        fam = sorted(set(wiki_ids(base) + wiki_ids(cr_title)))
        entries.extend(peer_entries(base, fam, f"Base + {cr_title} (Bounty Hunter cosmetic)"))
    for base, bh_title in bh_bh:
        fam = sorted(set(wiki_ids(base) + wiki_ids(bh_title)))
        entries.extend(peer_entries(base, fam, f"Base + {bh_title} (Bounty Hunter cosmetic)"))

    # Tools / leagues variants present in recs
    dp = wiki_ids("Dragon pickaxe") + wiki_ids("Dragon pickaxe (or)")
    entries.extend(peer_entries("Dragon pickaxe", dp, "Base + Dragon pickaxe (or) ornament"))

    inf = wiki_ids("Infernal axe") + wiki_ids("Infernal axe (or)")
    entries.extend(peer_entries("Infernal axe", inf, "Base + Infernal axe (or) ornament"))

    cp = wiki_ids("Crystal pickaxe") + wiki_ids("Crystal pickaxe (The Gauntlet)") + wiki_ids("Echo pickaxe")
    entries.extend(
        peer_entries(
            "Crystal pickaxe",
            cp,
            "Standard + Gauntlet + Echo (Leagues / community variants)",
        )
    )

    # Torva + Sanguine torva (blood ornament)
    entries.extend(
        peer_entries(
            "Torva full helm",
            wiki_ids("Torva full helm") + wiki_ids("Sanguine torva full helm"),
            "Torva + Sanguine torva (blood ornament) + all infobox versions",
        )
    )
    entries.extend(
        peer_entries(
            "Torva platebody",
            wiki_ids("Torva platebody") + wiki_ids("Sanguine torva platebody"),
            "Torva + Sanguine torva (blood ornament) + all infobox versions",
        )
    )
    entries.extend(
        peer_entries(
            "Torva platelegs",
            wiki_ids("Torva platelegs") + wiki_ids("Sanguine torva platelegs"),
            "Torva + Sanguine torva (blood ornament) + all infobox versions",
        )
    )

    # Blood moon armour (recolors)
    entries.extend(
        peer_entries(
            "Blood moon helm",
            wiki_ids("Blood moon helm"),
            "Blood moon armour recolors (all wiki infobox versions)",
        )
    )
    entries.extend(
        peer_entries(
            "Blood moon chestplate",
            wiki_ids("Blood moon chestplate"),
            "Blood moon armour recolors (all wiki infobox versions)",
        )
    )
    entries.extend(
        peer_entries(
            "Blood moon tassets",
            wiki_ids("Blood moon tassets"),
            "Blood moon armour recolors (all wiki infobox versions)",
        )
    )

    # Oathplate + Radiant oathplate (white / purifying sigil cosmetic)
    entries.extend(
        peer_entries(
            "Oathplate helm",
            wiki_ids("Oathplate helm") + wiki_ids("Radiant oathplate helm"),
            "Oathplate + Radiant oathplate (white) variant",
        )
    )
    entries.extend(
        peer_entries(
            "Oathplate chest",
            wiki_ids("Oathplate chest") + wiki_ids("Radiant oathplate chest"),
            "Oathplate + Radiant oathplate (white) variant",
        )
    )
    entries.extend(
        peer_entries(
            "Oathplate legs",
            wiki_ids("Oathplate legs") + wiki_ids("Radiant oathplate legs"),
            "Oathplate + Radiant oathplate (white) variant",
        )
    )

    # Abyssal whip: base + LMS volcanic/frozen + Shattered relics (or)
    entries.extend(
        peer_entries(
            "Abyssal whip",
            wiki_ids("Abyssal whip")
            + wiki_ids("Volcanic abyssal whip")
            + wiki_ids("Frozen abyssal whip")
            + wiki_ids("Abyssal whip (or)"),
            "Base + Volcanic/Frozen (LMS Justine) + Abyssal whip (or) Shattered relics kit",
        )
    )
    # Abyssal tentacle: base + Shattered (or) only (no volcanic/frozen tentacle items)
    entries.extend(
        peer_entries(
            "Abyssal tentacle",
            wiki_ids("Abyssal tentacle") + wiki_ids("Abyssal tentacle (or)"),
            "Base + Abyssal tentacle (or) Shattered relics variety ornament kit",
        )
    )

    by_id: dict[int, dict] = {}
    for e in entries:
        by_id[e["base_id"]] = e

    preserved = {22109, 12791, 25985, 27251}
    if VARIANT_PATH.is_file():
        existing = json.loads(VARIANT_PATH.read_text(encoding="utf-8"))
        for e in existing:
            bid = e["base_id"]
            if bid in preserved:
                by_id[bid] = e

    merged = sorted(by_id.values(), key=lambda x: x["base_id"])
    VARIANT_PATH.write_text(json.dumps(merged, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"Wrote {len(merged)} entries to {VARIANT_PATH}", file=sys.stderr)


if __name__ == "__main__":
    main()
