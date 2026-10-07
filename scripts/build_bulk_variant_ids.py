#!/usr/bin/env python3
"""Report possible variants without changing accepted mappings or recommendations.

Example: python scripts/build_bulk_variant_ids.py --search 'slayer helmet|max cape|quiver'
One catalog download per invocation; no Wiki requests. Names are discovery hints,
not proof of equipment equivalence. Review the report before editing variant_ids.json.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CATALOG_URL = 'https://chisel.weirdgloop.org/moid/data_files/itemsmin.js'


def read_catalog(text: str) -> list[dict]:
    # MOID publishes a JSON array assigned to `items`. Never execute downloaded JS.
    text = text.strip()
    if text.startswith('items='):
        text = text[len('items='):].strip()
    if text.endswith(';'):
        text = text[:-1]
    items = json.loads(text)
    if not isinstance(items, list) or not items:
        raise ValueError('Item catalog must be a non-empty JSON array')
    seen = set()
    for item in items:
        if (not isinstance(item, dict) or type(item.get('id')) is not int
                or not isinstance(item.get('name'), str) or item['id'] in seen):
            raise ValueError('Invalid or duplicate item in catalog')
        seen.add(item['id'])
    return items


def discover(items: list[dict], entries: list[dict], search: re.Pattern) -> list[dict]:
    """Surface matching IDs absent from each matching accepted recommendation.

    An ID can be known elsewhere and still be missing from the relevant mapping.
    Each row lists uncovered base IDs for inspection, never automatic acceptance.
    """
    matching = [e for e in entries if search.search(e.get('name', ''))]
    results = []
    for item in items:
        name = item['name']
        config = item.get('configName', '')
        if (name.lower() == 'null' or config.startswith(('placeholder_', 'cert_'))
                or not search.search(name)):
            continue
        uncovered = [e['base_id'] for e in matching
                     if item['id'] not in [e['base_id'], *e['extra_ids']]]
        known = any(item['id'] in [e['base_id'], *e['extra_ids']] for e in entries)
        if known and not uncovered:
            continue
        actions = item.get('invOps', [])
        if isinstance(actions, dict):
            actions = list(actions.values())
        results.append({
            'id': item['id'], 'name': name, 'config_name': config,
            'equipable': any(a in ('Wear', 'Wield', 'Equip') for a in actions),
            'missing_from_base_ids': uncovered,
            'review': 'Verify equal or stronger functionality; names do not establish a match.',
            'lookup': f"https://chisel.weirdgloop.org/moid/item_id.html#{item['id']}",
        })
    return sorted(results, key=lambda row: (row['name'].casefold(), row['id']))


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--search', required=True, help='Case-insensitive item-name regex')
    parser.add_argument('--catalog', type=Path, help='Use a previously downloaded catalog offline')
    args = parser.parse_args()
    try:
        search = re.compile(args.search, re.IGNORECASE)
        if args.catalog:
            text = args.catalog.read_text(encoding='utf-8')
        else:
            request = urllib.request.Request(CATALOG_URL, headers={
                'User-Agent': 'RecommendedEquipment variant discovery/1.0',
            })
            with urllib.request.urlopen(request, timeout=45) as response:
                text = response.read().decode('utf-8')
        items = read_catalog(text)
        entries = json.loads((ROOT / 'variant_ids.json').read_text(encoding='utf-8'))
        report = discover(items, entries, search)
    except (OSError, ValueError, re.error, KeyError, TypeError) as exc:
        raise SystemExit(f'Discovery failed; accepted mappings unchanged: {exc}') from exc
    print(json.dumps({'source': str(args.catalog or CATALOG_URL),
                      'search': args.search, 'candidates': report}, indent=2))
    print(f'{len(report)} candidates require review. No mappings changed.', file=sys.stderr)


if __name__ == '__main__':
    main()
