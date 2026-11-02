"""Regression anchors transcribed from the user supplied regulator image."""
import json
from pathlib import Path
import unittest
from circuit_model import topology_hash
from build_image_case import D
from image_case_wiring import audit, component_count
from rewire_image_case import geometry_check

CASE=Path(__file__).resolve().parents[1]/'cases'/'image_001'

class ImageCaseTests(unittest.TestCase):
    def test_routes_are_one_continuous_tree_per_net_without_foreign_junctions(self):
        self.assertEqual(audit(),[])

    def test_crossing_without_junction_does_not_count_as_connected(self):
        self.assertEqual(component_count([((0,1),(2,1)),((1,0),(1,2))]),2)
        self.assertEqual(component_count([((0,1),(2,1)),((1,0),(1,1)),((1,1),(1,2))]),1)

    def test_actual_geometry_has_35_continuous_physical_nets(self):
        p=CASE/'readback.json'
        if not p.exists():self.skipTest('No live image-case readback')
        report=geometry_check(json.loads(p.read_text(encoding='utf-8'))['scene'])
        self.assertEqual(len(report),35)
        self.assertTrue(all(v['physicalComponents']==1 for v in report.values()))

    def test_equal_net_labels_do_not_hide_missing_visible_wires(self):
        p=CASE/'readback.json'
        if not p.exists():self.skipTest('No live image-case readback')
        scene=json.loads(p.read_text(encoding='utf-8'))['scene']
        scene['shapes']=[s for s in scene['shapes'] if not (s.get('net')=='N17' and s['type'] in ['line','path'])]
        with self.assertRaisesRegex(AssertionError,'No physical wires'):
            geometry_check(scene)

    def test_floating_reference_and_startup_gate(self):
        d={x['name']:x for x in D}
        self.assertEqual(d['J1']['terms'],dict(D='Vin',G='Vout',S='N1'))
        self.assertEqual(d['Z1']['terms'],dict(MINUS='N1',PLUS='Vout'))
        self.assertNotIn('0',{n for x in D for n in x['terms'].values()})

    def test_output_sense_and_compensation_return_nodes(self):
        d={x['name']:x for x in D}
        self.assertEqual(d['R19']['params']['r'],'2.5')
        self.assertEqual(d['Q20']['terms']['E'],d['R19']['terms']['PLUS'])
        self.assertEqual(d['R19']['terms']['MINUS'],'Vout')
        self.assertEqual(d['R15']['terms']['MINUS'],d['Q20']['terms']['E'])
        self.assertEqual(d['C1']['terms'],dict(PLUS='N13',MINUS='Vout'))
        self.assertEqual(d['C2']['terms'],dict(PLUS='N13',MINUS='N19'))
        self.assertEqual(d['R22']['terms'],dict(PLUS='N19',MINUS='Adjust'))

    def test_actual_virtuoso_readback_matches_all_52_devices_and_parameters(self):
        p=CASE/'readback.json'
        if not p.exists():self.skipTest('No live image-case readback')
        actual=json.loads(p.read_text(encoding='utf-8'))
        self.assertEqual(len(actual['instances']),52)
        self.assertEqual(topology_hash(actual['instances']),topology_hash(D))
        self.assertEqual(set(actual['pins']),{'Vin','Vout','Adjust'})
        self.assertFalse(actual['verified'])
        self.assertFalse(actual['scene']['diagnostics']['missingMasters'])
        expected={d['name']:d for d in D}
        for d in actual['instances']:
            for key,value in expected[d['name']]['params'].items():
                self.assertEqual(str(d['param_evidence']['stored'][key]),value)

    def test_real_check_save_has_no_errors_or_warnings(self):
        p=CASE/'check-save.json'
        if not p.exists():self.skipTest('No live image-case check')
        report=json.loads(p.read_text(encoding='utf-8'))
        self.assertEqual(report['status'],'saved')
        self.assertEqual(report['check_error_count'],0)
        self.assertEqual(report['check_warning_count'],0)

    def test_saved_ai_analysis_identifies_regulator_and_covers_every_device(self):
        p=CASE/'analysis.json'
        if not p.exists():self.skipTest('No saved live AI analysis')
        analysis=json.loads(p.read_text(encoding='utf-8'))
        self.assertIn('稳压',analysis['identity']['label'])
        self.assertIn('线性',analysis['identity']['label'])
        self.assertEqual({n for s in analysis['sections'] for n in s['devices']},{d['name'] for d in D})
        self.assertTrue(analysis['identity']['limitations'])

if __name__=='__main__':unittest.main()
