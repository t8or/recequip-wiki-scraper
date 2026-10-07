"""Standalone script to merge variant IDs into the scraped recommendations.

Usage:
    python apply_variants.py

Reads:
    variant_ids.json  -- manually-maintained base_id → extra_ids mapping
    recs/all.json     -- scraper output

Writes:
    recs/all.json          -- updated (pretty-printed, 2-space indent)
    recs/all.min.json      -- updated (minified)
    recs/<Activity>.json   -- updated per-activity files

The script is idempotent: running it twice produces identical output.
Mappings explicitly list all accepted substitutions; chains are validated, not inferred.
Optional preference values put verified upgrades ahead of weaker accepted IDs.

Design notes:
    - Matching is done on base_id (integer), never on item name strings.
    - Directionality is implicit: only an entry whose base_id appears in an
      item's ID list triggers expansion.  If you do not want an upgraded item
      to expand backwards to its base, simply do not create an entry with the
      upgraded item's ID as base_id.
    - No external dependencies beyond the Python 3 standard library.
"""

import json
import os
import sys

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
VARIANT_IDS_PATH = os.path.join(SCRIPT_DIR, "variant_ids.json")
ALL_JSON_PATH = os.path.join(SCRIPT_DIR, "recs", "all.json")
ALL_MIN_JSON_PATH = os.path.join(SCRIPT_DIR, "recs", "all.min.json")
RECS_DIR = os.path.join(SCRIPT_DIR, "recs")

SLOT_KEYS = [
    "head", "neck", "cape", "body", "legs",
    "weapon", "shield", "ammo", "hands", "feet", "ring", "special",
]


def load_variant_ids(path: str) -> tuple[dict[int, list[int]], dict[int, int], dict[int, str]]:
    """Load and validate variant_ids.json.

    Returns accepted substitutions, item preferences, and equipment slot constraints.
    Raises SystemExit on validation errors.
    """
    try:
        with open(path, encoding="utf-8") as f:
            entries = json.load(f)
    except FileNotFoundError:
        print(f"ERROR: {path} not found.", file=sys.stderr)
        sys.exit(1)
    except json.JSONDecodeError as exc:
        print(f"ERROR: {path} is not valid JSON: {exc}", file=sys.stderr)
        sys.exit(1)

    if not isinstance(entries, list):
        print(f"ERROR: {path} must be a JSON array.", file=sys.stderr)
        sys.exit(1)

    lookup: dict[int, list[int]] = {}
    preferences: dict[int, int] = {}
    slots: dict[int, str] = {}
    for i, entry in enumerate(entries):
        if not isinstance(entry, dict):
            print(f"ERROR: Entry {i} in {path} is not an object.", file=sys.stderr)
            sys.exit(1)
        for required_key in ("base_id", "extra_ids"):
            if required_key not in entry:
                print(
                    f"ERROR: Entry {i} in {path} is missing required key '{required_key}'.",
                    file=sys.stderr,
                )
                sys.exit(1)
        if type(entry["base_id"]) is not int or entry["base_id"] <= 0:
            print(
                f"ERROR: Entry {i} in {path}: 'base_id' must be an integer.",
                file=sys.stderr,
            )
            sys.exit(1)
        if not isinstance(entry["extra_ids"], list) or not all(
            type(x) is int and x > 0 for x in entry["extra_ids"]
        ):
            print(
                f"ERROR: Entry {i} in {path}: 'extra_ids' must be a list of integers.",
                file=sys.stderr,
            )
            sys.exit(1)
        base_id: int = entry["base_id"]
        if base_id in lookup:
            print(
                f"ERROR: Duplicate base_id {base_id} in {path}.",
                file=sys.stderr,
            )
            sys.exit(1)
        preference = entry.get("preference", 0)
        if type(preference) is not int or preference < 0:
            raise SystemExit(f"ERROR: Invalid preference for {base_id} in {path}.")
        if 'slot' in entry:
            if entry['slot'] not in SLOT_KEYS:
                raise SystemExit(f"ERROR: Invalid equipment slot for {base_id}.")
            slots[base_id] = entry['slot']
        preferences[base_id] = preference
        lookup[base_id] = list(dict.fromkeys(entry["extra_ids"]))

    # Accepted relationships must be explicit and complete. This makes replay
    # stable without inventing transitive equipment equivalence at runtime.
    for base_id, extra_ids in lookup.items():
        accepted = {base_id, *extra_ids}
        for item_id in extra_ids:
            if preferences.get(item_id, 0) < preferences[base_id]:
                raise SystemExit(f"ERROR: {base_id} accepts lower-preference item {item_id}.")
            missing = set(lookup.get(item_id, [])) - accepted
            if missing:
                raise SystemExit(
                    f"ERROR: Incomplete substitutions for {base_id}: {sorted(missing)}. "
                    "Review and list accepted IDs explicitly."
                )
    return lookup, preferences, slots


def merge_ids(existing_ids: list[int], extra_ids: list[int]) -> tuple[list[int], list[int]]:
    """Append extra_ids to existing_ids, deduplicating, preserving order.

    Returns (merged_list, newly_added_ids).
    """
    existing_set = set(existing_ids)
    added: list[int] = []
    merged = list(existing_ids)
    for eid in extra_ids:
        if eid not in existing_set:
            merged.append(eid)
            existing_set.add(eid)
            added.append(eid)
    return merged, added


def apply_variants_to_styles(
    styles: list,
    lookup: dict[int, list[int]],
    activity_name: str,
    preferences: dict[int, int] | None = None,
    slots: dict[int, str] | None = None,
) -> list[tuple[str, str, list[int]]]:
    """Walk style objects and apply variant ID expansions in place.

    Returns a list of (item_name, slot_key, added_ids) tuples for reporting.
    """
    patches: list[tuple[str, str, list[int]]] = []
    preferences = preferences or {}
    slots = slots or {}

    for style in styles:
        for slot_key in SLOT_KEYS:
            tier_list = style.get(slot_key)
            if not isinstance(tier_list, list):
                continue
            for tier_dict in tier_list:
                if not isinstance(tier_dict, dict):
                    continue
                for item_name, item_ids in tier_dict.items():
                    if not isinstance(item_ids, list):
                        continue
                    # Comparable versions share at least one accepted replacement.
                    # Unrelated IDs in a broad Wiki label must not be ranked together.
                    accepted_sets = [{base, *lookup.get(base, [])} for base in item_ids]
                    comparable = (bool(accepted_sets)
                                  and all(slots.get(base, slot_key) == slot_key for base in item_ids)
                                  and bool(set.intersection(*accepted_sets)))
                    merged = list(dict.fromkeys(item_ids))
                    added_ids: list[int] = []
                    for base_id in item_ids:
                        if slots.get(base_id, slot_key) != slot_key:
                            continue
                        accepted = [item_id for item_id in lookup.get(base_id, [])
                                    if comparable or preferences.get(item_id, 0) == preferences.get(base_id, 0)]
                        merged, added = merge_ids(merged, accepted)
                        added_ids.extend(added)
                    # Equal-preference variants keep their existing order.
                    if comparable:
                        merged.sort(key=lambda item_id: -preferences.get(item_id, 0))
                    if merged != item_ids:
                        tier_dict[item_name] = merged
                        patches.append((item_name, slot_key, added_ids))

    return patches


def main() -> None:
    # Load variant_ids.json
    lookup, preferences, slots = load_variant_ids(VARIANT_IDS_PATH)
    if not lookup:
        print("No variant entries found in variant_ids.json. Nothing to do.")
        return

    # Load all.json
    if not os.path.exists(ALL_JSON_PATH):
        print(f"ERROR: {ALL_JSON_PATH} not found. Run the scraper first.", file=sys.stderr)
        sys.exit(1)

    with open(ALL_JSON_PATH, encoding="utf-8") as f:
        all_data = json.load(f)

    if not isinstance(all_data, list):
        print(f"ERROR: {ALL_JSON_PATH} root must be a JSON array.", file=sys.stderr)
        sys.exit(1)

    # Apply variants and collect patch report
    total_patches: list[tuple[str, str, str, list[int]]] = []

    for activity in all_data:
        activity_name = activity.get("name", "<unknown>")
        styles = activity.get("styles", [])
        patches = apply_variants_to_styles(styles, lookup, activity_name, preferences, slots)
        for item_name, slot_key, added_ids in patches:
            total_patches.append((activity_name, item_name, slot_key, added_ids))

    # Write updated all.json (no trailing newline — matches util.write_json)
    with open(ALL_JSON_PATH, "w", encoding="utf-8") as f:
        json.dump(all_data, f, indent=2, ensure_ascii=False)

    # Write updated all.min.json
    with open(ALL_MIN_JSON_PATH, "w", encoding="utf-8") as f:
        json.dump(all_data, f, separators=(",", ":"), ensure_ascii=False)

    # Write updated per-activity files
    for activity in all_data:
        activity_name = activity.get("name", "")
        if not activity_name:
            continue
        styles = activity.get("styles", [])
        activity_path = os.path.join(RECS_DIR, f"{activity_name}.json")
        if os.path.exists(activity_path):
            with open(activity_path, "w", encoding="utf-8") as f:
                json.dump(styles, f, indent=2, ensure_ascii=False)

    # Print summary
    if total_patches:
        print(f"Updated {len(total_patches)} recommendation ID list(s):\n")
        for activity_name, item_name, slot_key, added_ids in total_patches:
            detail = f"added IDs {added_ids}" if added_ids else "updated preference order"
            print(f"  [{activity_name}] {item_name} ({slot_key}): {detail}")
    else:
        print("No variant expansions were needed (all extra IDs already present).")


if __name__ == "__main__":
    main()
