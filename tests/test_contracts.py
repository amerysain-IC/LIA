import copy
import json
from pathlib import Path
import unittest
from circuit_model import DEVICES, LIBRARY, CELL, topology_hash, enrich, apply_changes, make_netlist, parse_value, device_kind

def fixture():
    devices=copy.deepcopy(DEVICES)
    for d in devices:
        d['param_evidence']={'stored':dict(d['params'])}
    return enrich(dict(instances=devices,pins={},nets={},notes=[]),LIBRARY,CELL)

class CircuitContractTests(unittest.TestCase):
    def test_jfet_and_zener_are_not_misreported_as_mos_or_unknown(self):
        self.assertEqual(device_kind(dict(cell='njfet',terms=dict(D='in',G='out',S='bias'),params={})), 'njfet')
        self.assertEqual(device_kind(dict(cell='pjfet',terms=dict(D='in',G='out',S='bias'),params={})), 'pjfet')
        self.assertEqual(device_kind(dict(cell='zener',terms=dict(PLUS='out',MINUS='ref'),params={})), 'zener')

    def test_engineering_units_are_numbers_not_programs(self):
        self.assertAlmostEqual(parse_value('2p'),2e-12)
        self.assertAlmostEqual(parse_value('20µ'),20e-6)
        self.assertAlmostEqual(parse_value('20u'),20e-6)
        for text in ['__import__("os")','1u; system("x")','NaN','inf','-2u','0','2 * 3','1e999','1u\nmodel fake mos1']:
            with self.subTest(text=text),self.assertRaises(ValueError): parse_value(text)

    def test_parameter_edits_never_mutate_source_or_topology(self):
        original=fixture(); pristine=copy.deepcopy(original)
        changed=apply_changes(original,{'CC':{'c':'4p'},'M1':{'w':'30u'}})
        self.assertEqual(original,pristine)
        self.assertEqual(topology_hash(changed['instances']),original['topologyHash'])
        self.assertIn('c=4e-12',make_netlist(changed))
        self.assertIn('w=3e-05',make_netlist(changed))

    def test_rejects_topology_model_and_unknown_device_updates(self):
        data=fixture()
        for changes in [{'M1':{'G':'OUT'}},{'M1':{'model':'another'}},{'NEW_DEVICE':{'w':'1u'}},{'CC':{'c':'0'}},{'CC':{'c':'1000'}}]:
            with self.subTest(changes=changes),self.assertRaises(ValueError): apply_changes(data,changes)

    def test_netlist_uses_verified_terminal_order_and_keeps_internal_topology(self):
        data=fixture()
        ac=make_netlist(data,'ac'); tran=make_netlist(data,'tran')
        self.assertIn('M2 (N1 INP TAIL VSS) edu_n',ac)
        self.assertIn('M1 (NX INN TAIL VSS) edu_n',ac)
        self.assertEqual(ac.split('subckt amplifier')[1].split('ends amplifier')[0],tran.split('subckt amplifier')[1].split('ends amplifier')[0])
        self.assertIn('XAMP (inp out out vdd 0) amplifier',tran)

    def test_changed_terminal_is_detected_and_simulation_refused(self):
        data=fixture(); data['instances'][0]['terms']['G']='OUT'
        data['topologyHash']=topology_hash(data['instances'])
        with self.assertRaises(ValueError): make_netlist(data)

    def test_other_libraries_never_implicitly_use_teaching_models(self):
        data=fixture(); data['teaching']=False
        with self.assertRaises(ValueError): make_netlist(data)

    def test_external_model_change_disables_teaching_simulation(self):
        data=fixture()
        data['instances'][0]['param_evidence']['stored']['model']='unverified_model'
        data=enrich(data,LIBRARY,CELL)
        self.assertFalse(data['verified'])
        with self.assertRaises(ValueError): make_netlist(data)

    def test_actual_saved_readback_has_symmetric_network_evidence(self):
        p=Path(__file__).resolve().parents[1]/'runtime'/'last-circuit.json'
        if not p.exists(): self.skipTest('No live readback artifact')
        data=json.loads(p.read_text(encoding='utf-8'))
        if data.get('teaching'):
            self.assertTrue(data['verified'])
            self.assertEqual(len(data['instances']),11)
        else:
            self.assertGreater(len(data['instances']),0)
        for d in data['instances']:
            for terminal,net in d['terms'].items():
                self.assertIn(d['name']+'.'+terminal,data['nets'][net]['connections'])

if __name__=='__main__': unittest.main()
