import contextlib
import copy
import importlib.util
import io
import json
import re
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import apply_variants as variants

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('discovery', ROOT / 'scripts/build_bulk_variant_ids.py')
discovery = importlib.util.module_from_spec(spec)
spec.loader.exec_module(discovery)


class ExpansionTests(unittest.TestCase):
    def run_files(self, directory, entries, data=None):
        root = Path(directory)
        recs = root / 'recs'
        recs.mkdir(exist_ok=True)
        (root / 'variant_ids.json').write_text(json.dumps(entries))
        if data is not None:
            (recs / 'all.json').write_text(json.dumps(data))
            (recs / 'all.min.json').write_text(json.dumps(data))
            for activity in data:
                (recs / (activity['name'] + '.json')).write_text(json.dumps(activity['styles']))
        with patch.multiple(variants, VARIANT_IDS_PATH=str(root/'variant_ids.json'),
                            ALL_JSON_PATH=str(recs/'all.json'), ALL_MIN_JSON_PATH=str(recs/'all.min.json'),
                            RECS_DIR=str(recs)), contextlib.redirect_stdout(io.StringIO()):
            variants.main()
        return {f.name: f.read_bytes() for f in recs.glob('*.json')}

    def test_file_workflow_accumulates_overlapping_rules_and_is_idempotent(self):
        entries = [{'base_id': 1, 'extra_ids': [3]}, {'base_id': 2, 'extra_ids': [4]}]
        data = [{'name': 'Example', 'styles': [{'name': 'Melee', 'head': [{'Helmet': [1, 2]}]}]}]
        with tempfile.TemporaryDirectory() as root:
            once = self.run_files(root, entries, data)
            twice = self.run_files(root, entries)
        self.assertEqual(once, twice)
        output = json.loads(once['all.json'])
        self.assertEqual([1, 2, 3, 4], output[0]['styles'][0]['head'][0]['Helmet'])
        self.assertEqual(output, json.loads(once['all.min.json']))
        self.assertEqual(output[0]['styles'], json.loads(once['Example.json']))

    def test_variants_preserve_wiki_choices_order_and_icons(self):
        entries = [{'base_id': 1, 'extra_ids': [4], 'tier': 0},
                   {'base_id': 2, 'extra_ids': [5], 'tier': 10},
                   {'base_id': 3, 'extra_ids': [6], 'tier': 20},
                   {'base_id': 4, 'extra_ids': [], 'tier': 0},
                   {'base_id': 5, 'extra_ids': [], 'tier': 10},
                   {'base_id': 6, 'extra_ids': [], 'tier': 20}]
        data = [{'name': 'Example', 'styles': [{'name': 'Ranged',
                  'cape': [{'Best': [3]}, {'Middle': [2]}, {'Entry': [1]}]}]}]
        with tempfile.TemporaryDirectory() as root:
            once = self.run_files(root, entries, data)
            self.assertEqual(once, self.run_files(root, entries))
        style = json.loads(once['all.json'])[0]['styles'][0]
        self.assertEqual([{'Best': [3, 6]}, {'Middle': [2, 5]}, {'Entry': [1, 4]}], style['cape'])
        self.assertNotIn('display_ids', style)

    def test_bad_mapping_fails_before_recommendation_writes(self):
        cases = [
            [{'base_id': 1, 'extra_ids': []}, {'base_id': 1, 'extra_ids': []}],
            [{'base_id': True, 'extra_ids': []}],
            [{'base_id': 1, 'extra_ids': [False]}],
            [{'base_id': 1, 'extra_ids': [], 'tier': -1}],
            [{'base_id': 1, 'extra_ids': [], 'warm': 'yes'}],
            [{'base_id': 1, 'extra_ids': [2], 'tier': 10}],
            [{'base_id': 1, 'extra_ids': [2]}, {'base_id': 2, 'extra_ids': [], 'tier': 10}],
            [{'base_id': 1, 'extra_ids': [2]}, {'base_id': 2, 'extra_ids': [3]}],
        ]
        data = [{'name': 'Example', 'styles': []}]
        for entries in cases:
            with self.subTest(entries=entries), tempfile.TemporaryDirectory() as root:
                with contextlib.redirect_stderr(io.StringIO()), self.assertRaises(SystemExit):
                    self.run_files(root, entries, data)
                self.assertEqual(data, json.loads((Path(root)/'recs/all.json').read_text()))

    def test_real_mapping_has_no_ranged_or_void_downgrades(self):
        lookup, slots, warm_ids = variants.load_variant_ids(str(ROOT/'variant_ids.json'))
        for source, forbidden in [(22109, [10498, 10499, 13337]),
                                  (21898, [10498, 10499]),
                                  (28955, [10498, 10499, 22109, 28947]),
                                  (13072, [8839, 24177, 26463, 27000]),
                                  (5698, [1215, 1231, 5680])]:
            self.assertTrue(set(forbidden).isdisjoint(lookup[source]))
        self.assertEqual([], lookup[10498])
        self.assertEqual([13337], lookup[10499])
        self.assertIn(27374, lookup[22109])
        self.assertNotIn(28955, lookup[22109])
        self.assertNotIn(13072, lookup[8839])
        self.assertIn(19641, lookup[11865])
        self.assertIn(33449, lookup[11865])
        self.assertNotIn(11864, lookup[11865])
        self.assertNotIn(13280, lookup[22109])
        self.assertIn(21776, lookup[21791])
        self.assertNotIn(21780, lookup[21791])

    def test_slot_and_mixed_family_guards(self):
        lookup, slots, warm_ids = variants.load_variant_ids(str(ROOT/'variant_ids.json'))
        styles = [{'ammo': [{'Arrows': [22109, 892]}],
                   'cape': [{'Mixed capes': [10499, 999999]}, {"Assembler": [22109, 21914, 24222]}]}]
        variants.apply_variants_to_styles(styles, lookup, 'Example', slots, warm_ids)
        self.assertEqual([22109, 892], styles[0]['ammo'][0]['Arrows'])
        self.assertNotIn(28955, styles[0]['cape'][0]['Mixed capes'])
        self.assertNotIn(28955, styles[0]['cape'][1]['Assembler'])
        self.assertIn(27374, styles[0]['cape'][1]['Assembler'])
        self.assertEqual([22109,21914,24222], styles[0]['cape'][1]['Assembler'][:3])

    def test_warmth_does_not_inherit_combat_substitutions(self):
        lookup, slots, warm_ids = variants.load_variant_ids(str(ROOT/'variant_ids.json'))
        # Max versions are warm, but that property does not transfer to their
        # regular combat equivalents. Source identity matters even for one ID.
        for name in ['Warm clothing#Cape slot', 'Warm_clothing#Cape_slot', 'Warm clothing']:
            original = [13337, 21784, 21898, 6570]
            styles = [{'cape': [{name: original.copy()}, {"Ava's attractor": [10498]}]}]
            variants.apply_variants_to_styles(styles, lookup, 'Wintertodt', slots, warm_ids)
            self.assertTrue(set(original).issubset(styles[0]['cape'][0][name]))
            self.assertTrue({10499,22109,27374,21791,21793,21795}.isdisjoint(styles[0]['cape'][0][name]))
            self.assertTrue({27363,27365}.issubset(styles[0]['cape'][0][name]))
            self.assertEqual([10498], styles[0]['cape'][1]["Ava's attractor"])
        single = [{'cape': [{'Warm clothing#Cape slot': [13337]}]}]
        variants.apply_variants_to_styles(single, lookup, 'Wintertodt', slots, warm_ids)
        self.assertNotIn(10499, single[0]['cape'][0]['Warm clothing#Cape slot'])
        head = [{'head': [{'Warm clothing#Head slot': [11865, 20708]}]}]
        variants.apply_variants_to_styles(head, lookup, 'Wintertodt', slots, warm_ids)
        self.assertTrue({33439, 33441, 33443}.issubset(head[0]['head'][0]['Warm clothing#Head slot']))

    def test_full_dataset_preserves_structure_and_stabilizes(self):
        lookup, slots, warm_ids = variants.load_variant_ids(str(ROOT/'variant_ids.json'))
        data = json.loads((ROOT/'recs/all.json').read_text())
        original = copy.deepcopy(data)
        for activity in data:
            variants.apply_variants_to_styles(activity['styles'], lookup, activity['name'], slots, warm_ids)
        once = copy.deepcopy(data)
        for activity in data:
            variants.apply_variants_to_styles(activity['styles'], lookup, activity['name'], slots, warm_ids)
        self.assertEqual(once, data)
        for before, after in zip(original, data):
            self.assertEqual(before.keys(), after.keys())
            self.assertEqual(before['name'], after['name'])
            for bstyle, astyle in zip(before['styles'], after['styles']):
                self.assertEqual(bstyle.keys(), astyle.keys())
                self.assertEqual(bstyle['name'], astyle['name'])
                for slot in variants.SLOT_KEYS:
                    self.assertEqual(len(bstyle[slot]), len(astyle[slot]))
                    for btier, atier in zip(bstyle[slot], astyle[slot]):
                        self.assertEqual(list(btier), list(atier))
                        for name, ids in btier.items():
                            self.assertTrue(set(ids).issubset(atier[name]))


class DiscoveryTests(unittest.TestCase):
    def test_known_elsewhere_still_reported_as_uncovered(self):
        items = [{'id': 1, 'name': 'Slayer helmet (i)', 'invOps': ['Wear']},
                 {'id': 2, 'name': 'Black slayer helmet (i)', 'invOps': ['Wear']},
                 {'id': 3, 'name': 'Black slayer helmet (i)', 'configName': 'placeholder_helm'},
                 {'id': 4, 'name': 'Black slayer helmet (i)', 'configName': 'cert_helm'}]
        entries = [{'base_id': 1, 'name': 'Slayer helmet (i)', 'extra_ids': []},
                   {'base_id': 2, 'name': 'Black slayer helmet (i)', 'extra_ids': []}]
        before = copy.deepcopy(entries)
        result = discovery.discover(items, entries, re.compile('slayer helmet', re.I))
        self.assertEqual([1, 2], sorted(r['id'] for r in result))
        self.assertEqual([1], next(r for r in result if r['id'] == 2)['missing_from_base_ids'])
        self.assertEqual(before, entries)

    def test_catalog_is_parsed_without_executing_javascript(self):
        self.assertEqual([{'id': 1, 'name': 'Helmet'}],
                         discovery.read_catalog('items=[{"id":1,"name":"Helmet"}];'))
        for text in ['items=[];alert(1)', '{}', '[]',
                     '[{"id":1,"name":"X"},{"id":1,"name":"Y"}]']:
            with self.subTest(text=text), self.assertRaises(ValueError):
                discovery.read_catalog(text)


if __name__ == '__main__':
    unittest.main()
