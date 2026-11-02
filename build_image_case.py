"""Recreate the user supplied image in a new, isolated Virtuoso schematic.

Symbol placement follows the image. Every net is drawn as continuous physical
wires, with a single descriptive label per net.
No semiconductor model parameters or emitter area ratios are inferred.
"""
from __future__ import annotations
from collections import Counter
from dataclasses import asdict
import json
from pathlib import Path
import shutil

from bridge_service import client, skill, load_circuit, save_json, sync_libraries, remote_library_path
from circuit_model import topology_hash
from virtuoso_bridge.virtuoso.ops import q
from virtuoso_bridge.virtuoso.schematic.ops import (
    schematic_create_inst_by_master_name as inst, schematic_label_instance_term as label,
    schematic_create_pin as pin, schematic_create_net_stub as stub,
    schematic_create_wire as wire, schematic_create_wire_label as wire_label,
)
from virtuoso_bridge.virtuoso.symbol.reader import read_symbol_ports

ROOT=Path(__file__).resolve().parent
CASE=ROOT/'cases'/'image_001'
LIB='CircuitImageTests'
CELL='image_001'
SOURCE=CASE/'source.png'
D=[]
def add(name,cell,xy,terms,params=None,orient='R0'):
    D.append(dict(name=name,lib='analogLib',cell=cell,xy=xy,orient=orient,terms=terms,params=params or {}))
def bjt(n,p,xy,c,b,e,mirror=False):
    add('Q'+str(n),p,xy,dict(C=c,B=b,E=e),dict(model='UNSPECIFIED_'+p.upper()),'MY' if mirror else 'R0')
def resistor(n,xy,value,a,b,horizontal=False):
    add('R'+str(n),'res',[xy[0]-15 if horizontal else xy[0],xy[1] if horizontal else xy[1]-15],dict(PLUS=a,MINUS=b),dict(r=value),'R90' if horizontal else 'R0')

# N1=startup reference; N2=PNP bias; N3=control of Q4; N4=NPN bias.
bjt(1,'pnp',[278,167],'N3','N2','E1',True)
bjt(2,'pnp',[343,167],'N4','N2','E2')
bjt(3,'pnp',[493,167],'N5','N2','E3')
bjt(4,'pnp',[780,167],'N6','N3','E4')
bjt(5,'npn',[278,576],'N2','N4','E5',True)
bjt(6,'npn',[334,576],'N7','N4','E6',True)
bjt(7,'npn',[363,576],'N8','N4','Vout')
bjt(8,'pnp',[414,511],'Vout','N8','N5')
bjt(9,'npn',[493,511],'N9','N8','E9')
bjt(10,'pnp',[560,465],'N10','N9','N5')
bjt(11,'npn',[625,611],'N11','N10','Vout')
bjt(12,'pnp',[740,465],'Vout','N12','N11',True)
bjt(13,'npn',[782,424],'Vin','N6','N12',True)
bjt(14,'pnp',[860,494],'Vout','N13','N6',True)
bjt(15,'pnp',[940,378],'N13','N14','N11',True)
bjt(16,'pnp',[966,378],'N14','N14','N11')
bjt(17,'pnp',[1006,167],'N7','N7','E17',True)
bjt(18,'pnp',[1039,167],'N11','N7','E18')
bjt(19,'npn',[1104,308],'Vin','N11','N15')
bjt(20,'npn',[1205,395],'Vin','N15','N16')
bjt(21,'npn',[1118,531],'N11','N17','E21',True)
bjt(22,'npn',[992,750],'N13','Vout','N18',True)
bjt(23,'npn',[1046,750],'N14','Vout','E23',True)
add('J1','njfet',[98,421],dict(D='Vin',G='Vout',S='N1'),dict(model='UNSPECIFIED_NJFET'))
for n,xy,v,a,b,h in [
 (1,[238,95],'300','Vin','E1',False),(2,[383,95],'300','Vin','E2',False),
 (3,[533,95],'300','Vin','E3',False),(4,[820,95],'3k','Vin','E4',False),
 (5,[966,95],'300','Vin','E17',False),(6,[1077,95],'70','Vin','E18',False),
 (7,[238,240],'350','N3','N2',False),(8,[180,576],'200k','N1','N4',True),
 (9,[238,655],'180','E5','Vout',False),(10,[294,655],'180','E6','Vout',False),
 (11,[383,465],'130','N4','N8',False),(12,[533,430],'8.67k','N5','N9',False),
 (13,[533,665],'2k','E9','Vout',False),(14,[600,665],'6k','N10','Vout',False),
 (15,[741,535],'5.1k','N12','N16',False),(16,[1143,450],'500','N15','N16',False),
 (17,[1202,531],'400','N17','N16',True),(18,[1077,665],'60','E21','Vout',False),
 (19,[1244,665],'2.5','N16','Vout',False),(20,[1007,808],'2.4k','E23','N18',False),
 (21,[1080,844],'12.8k','N18','N19',True),(22,[1190,844],'50','N19','Adjust',True),
 (23,[1317,270],'18k','N21','N17',False),
]: resistor(n,xy,v,a,b,h)
for n,xy,bv,k,a in [(1,[124,650],'6.3','N1','Vout'),(2,[1317,88],'6.8','Vin','N20'),(3,[1317,160],'6.8','N20','N21')]:
    add('Z'+str(n),'zener',[xy[0],xy[1]-15],dict(MINUS=k,PLUS=a),dict(model='UNSPECIFIED_ZENER_'+bv.replace('.','p'),sourceNominalBreakdown=bv+'V'))
add('C1','cap',[859,625],dict(PLUS='N13',MINUS='Vout'),dict(c='10p'))
add('C2','cap',[905,657],dict(PLUS='N13',MINUS='N19'),dict(c='10p'))

def point(p):
    # 80 image pixels per schematic unit; all coordinates are representable.
    return [round(p[0]/80,6),round((900-p[1])/80,6)]

def setup():
    CASE.mkdir(parents=True,exist_ok=True)
    if SOURCE.exists() and not (CASE/'source.png').exists(): shutil.copy2(SOURCE,CASE/'source.png')
    expected={d['name']:d for d in D}
    assert len(expected)==52 and len(D)==52
    manifest=dict(library=LIB,cell=CELL,devices=D,ports=['Vin','Vout','Adjust'],
        source='User supplied schematic image; source.png',
        sourceCrossCheck='https://www.onsemi.com/pdf/datasheet/lm317m-d.pdf, Figure 2 (different sense resistor)',
        assumptions=['BJT/JFET model names and emitter area ratios are unspecified in the source.',
            'R19 is 2.5 ohm per supplied image, not the 1.25 ohm of LM317M Figure 2.',
            'Vout is the floating internal reference rail; it is not ground.',
            'C2 returns to N19 (before the 50 ohm Adjust resistor), not Vout.',
            'R15 (5.1k) returns to N16 (pass emitter, before 2.5 ohm), not Vout.',
            'Every net uses continuous physical wires; crossovers without a junction remain separate.',
            'No semiconductor models, area ratios, external divider, load, or simulation results supplied.'])
    (CASE/'circuit.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2),encoding='utf-8')
    c=client()
    # Check for old/partial targets before using create(), which can replace a view.
    exists=skill(f'ddGetObj({q(LIB)} {q(CELL)} "schematic") != nil')=='t'
    if exists:
        actual=c.schematic.read(LIB,CELL,include_positions=True,include_param_evidence=True,param_filters=None)
        if topology_hash(actual['instances'])!=topology_hash(D):
            raise RuntimeError('Existing target differs; it has been preserved. Inspect it before continuing.')
    else:
        if skill(f'ddGetObj({q(LIB)}) != nil')!='t':
            c.library.create(LIB,remote_library_path(LIB))
        symbols={k:read_symbol_ports(c,'analogLib',k) for k in sorted({d['cell'] for d in D})}
        terminal_locations={name:{'terms':[{'name':t['name'],'bbox':t['bbox']} for t in symbol['terms']]} for name,symbol in symbols.items()}
        (CASE/'symbol-evidence.json').write_text(json.dumps(terminal_locations,indent=2),encoding='utf-8')
        from image_case_wiring import emit_wires, PORTS
        with c.schematic.create(LIB,CELL,timeout=120) as sch:
            for d in D:
                sch.add(inst(d['lib'],d['cell'],'symbol',d['name'],*point(d['xy']),d['orient']))
                for key,value in d['params'].items():
                    sch.add(f'let((i) i=car(setof(x cv~>instances x~>name=={q(d["name"])})) dbReplaceProp(i {q(key)} "string" {q(value)}))')
            for name,xy in PORTS.items():
                sch.add(pin(name,*point(xy),'R0',direction='inputOutput'))
            emit_wires(sch)
            for text,xy in [('IMAGE CASE 001 - FLOATING THREE-TERMINAL CIRCUIT',[55,0]),
                ('SEMICONDUCTOR MODELS AND EMITTER AREA RATIOS UNSPECIFIED',[55,890])]:
                p=point(xy)
                sch.add(f'dbCreateLabel(cv list("annotate" "drawing") list({p[0]} {p[1]}) {q(text)} "lowerLeft" "R0" "stick" .08)')
        actual=c.schematic.read(LIB,CELL,include_positions=True,include_param_evidence=True,param_filters=None,timeout=60)
    # Compare all terminal partitions, not just numbers of devices.
    if topology_hash(actual['instances'])!=topology_hash(D):
        (CASE/'failed-readback.json').write_text(json.dumps(actual,indent=2),encoding='utf-8')
        errors=[]
        for d in actual['instances']:
            if d['name'] not in expected: errors.append(dict(name=d['name'],unexpected=True));continue
            if d['terms']!=expected[d['name']]['terms']:errors.append(dict(name=d['name'],expected=expected[d['name']]['terms'],actual=d['terms']))
        raise RuntimeError('Readback mismatch; target preserved: '+json.dumps(errors))
    for d in actual['instances']:
        for key,value in expected[d['name']]['params'].items():
            stored=d.get('param_evidence',{}).get('stored',{})
            if str(stored.get(key))!=value:raise RuntimeError('Stored parameter mismatch: '+d['name']+'.'+key)
    report=c.schematic.check_and_save(LIB,CELL)
    (CASE/'check-save.json').write_text(json.dumps(asdict(report),indent=2),encoding='utf-8')
    if not report.ok:raise RuntimeError('Check/save did not pass; see check-save.json')
    sync_libraries()
    data=load_circuit(LIB,CELL)
    (CASE/'readback.json').write_text(json.dumps(data,indent=2),encoding='utf-8')
    result=dict(library=LIB,cell=CELL,snapshotId=data['id'],instances=len(data['instances']),
        types=dict(Counter(d['cell'] for d in data['instances'])),topologyMatches=True,
        checkStatus=report.status,scene=bool(data.get('scene')),simulated=False)
    (CASE/'result.json').write_text(json.dumps(result,indent=2),encoding='utf-8')
    print(json.dumps(result,indent=2))
    return data

if __name__=='__main__':setup()
