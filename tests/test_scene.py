import json
from pathlib import Path
import unittest
from circuit_model import device_kind,parse_value
from native_scene import shape

class SceneContracts(unittest.TestCase):
    def test_type_uses_terminals_not_just_master_name(self):
        self.assertEqual(device_kind({'cell':'p50_ckt','terms':dict(G='a',S='b',D='c',B='d')}),'pmos')
        self.assertEqual(device_kind({'cell':'npnhbeta1_mis_ckt','terms':dict(B='a',C='b',E='c',SUB='d')}),'npn')
        self.assertEqual(device_kind({'cell':'rpposab','terms':dict(PLUS='a',MINUS='b'),'params':{'r':'20K'}}),'resistor')
        self.assertEqual(device_kind({'cell':'nonsense_nmos_named_block','terms':{'IN':'x','OUT':'y'}}),'unknown')

    def test_pdk_engineering_value_capital_k(self):
        self.assertAlmostEqual(parse_value('29.8384K'),29838.4)

    def test_geometry_parser_preserves_radian_arc_angles(self):
        row=['arc','device','drawing',None,[['-1','-1'],['1','1']],None,None,None,None,None,None,None,[['-2','-2'],['2','2']],'0.7751934','2.356194']
        s=shape(row)
        self.assertAlmostEqual(s['startAngle'],.7751934)
        self.assertEqual(s['ellipseBBox'],[[-2.,-2.],[2.,2.]])

    def test_live_native_symbols_and_wires_exist(self):
        root=Path(__file__).resolve().parents[1]/'runtime'/'circuits'
        probes=[]
        for p in root.glob('*.json'):
            data=json.loads(p.read_text(encoding='utf-8'))
            if data.get('lib')=='BJT_test' and data.get('scene'): probes.append(data)
        if not probes: self.skipTest('No live PDK readback fixture')
        for data in probes:
            with self.subTest(cell=data['cell']):
                self.assertFalse(data['scene']['diagnostics']['missingMasters'])
                self.assertGreater(len(data['scene']['shapes']),0)
                self.assertTrue(any(s.get('points') for s in data['scene']['shapes']))
                self.assertTrue(any(i['master'] and i['master']['shapes'] for i in data['scene']['instances']))

    def test_history_rejects_paths_and_other_snapshot_results(self):
        from bridge_service import simulation_history
        with self.assertRaises(ValueError): simulation_history('../last-circuit')
        history=simulation_history('63b853f5e5f06b5c4b3e')
        for run in history['runs']:
            self.assertEqual(run['snapshotId'],'63b853f5e5f06b5c4b3e')

if __name__=='__main__': unittest.main()
