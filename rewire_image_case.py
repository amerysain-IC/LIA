"""Stage and validate visible wires, then update only the owned image testcase.

Run normally to build/verify a new stage. --install also updates image_001,
after copying its current native cellview to a recoverable backup.
"""
from __future__ import annotations
import argparse
from dataclasses import asdict
import json
import math
from pathlib import Path
import time
import uuid

from build_image_case import D, LIB, CELL, CASE, point
from image_case_wiring import ROUTES, PORTS, TERMINALS, audit, on_segment, physically_joined, emit_wires
from bridge_service import client, load_circuit, skill
from native_scene import read_scene
from circuit_model import topology_hash
from virtuoso_bridge.virtuoso.ops import q
from virtuoso_bridge.virtuoso.schematic.ops import schematic_create_inst_by_master_name as inst, schematic_create_pin as pin, schematic_create_wire as wire

REVISION='continuous-wires-v1'
def json_file(name,data):
    (CASE/name).write_text(json.dumps(data,ensure_ascii=False,indent=2),encoding='utf-8')

def verify_electrical(actual):
    assert len(actual['instances'])==len(D)
    assert topology_hash(actual['instances'])==topology_hash(D),'Terminal topology changed'
    assert set(actual['pins'])==set(PORTS)
    expected={d['name']:d for d in D}
    for d in actual['instances']:
        e=expected[d['name']]
        assert d['orient']==e['orient'],d['name']
        assert all(abs(a-b)<1e-6 for a,b in zip(d['xy'],point(e['xy']))),d['name']
        for key,value in e['params'].items():
            assert str(d['param_evidence']['stored'].get(key))==value,(d['name'],key)

def geometry_check(scene):
    # Ignore all net-label equivalence: each net must be one physical wire tree.
    lines={net:[] for net in ROUTES}
    for s in scene['shapes']:
        if s['layer']=='wire' and s['type'] in ['line','path'] and s.get('net') in lines:
            pts=s.get('points') or []
            for a,b in zip(pts,pts[1:]):lines[s['net']].append((tuple(a),tuple(b)))
    def intersects(a,b,c,d):
        return physically_joined(a,b,c,d)
    report={}
    for net,segments in lines.items():
        assert segments,('No physical wires',net)
        parent=list(range(len(segments)))
        def find(a):
            while parent[a]!=a:parent[a]=parent[parent[a]];a=parent[a]
            return a
        for i,(a,b) in enumerate(segments):
            for j,(c,d) in enumerate(segments[:i]):
                if intersects(a,b,c,d):parent[find(i)]=find(j)
        components={find(i) for i in range(len(segments))}
        assert len(components)==1,('Net only joined by names, not visible wires',net,len(components))
        terminals=[(name,point(pt)) for name,(n,pt) in TERMINALS.items() if n==net]
        terminals += [(name,point(pt)) for name,pt in PORTS.items() if name==net]
        for name,pt in terminals:
            assert any(on_segment(pt,a,b) for a,b in segments),('Pin missing physical wire',name,net,pt)
        report[net]=dict(physicalComponents=1,segments=len(segments),terminals=len(terminals))
    return report

def read(c,cell):
    return c.schematic.read(LIB,cell,include_positions=True,include_param_evidence=True,param_filters=None,timeout=60)

def checked(c,cell,prefix):
    report=c.schematic.check_and_save(LIB,cell)
    json_file(prefix+'-check.json',asdict(report))
    assert report.ok and report.check_error_count==0 and report.check_warning_count==0,asdict(report)
    data=read(c,cell);verify_electrical(data)
    scene=read_scene(c,LIB,cell);physical=geometry_check(scene)
    json_file(prefix+'-geometry.json',physical)
    json_file(prefix+'-readback.json',dict(data,scene=scene))
    return data,scene

def main(install=False):
    assert not audit(),audit()
    c=client()
    original=read(c,CELL);verify_electrical(original)
    c.dialogs.enable_guard(timeout=15)
    suffix=time.strftime('%Y%m%d_%H%M%S')+'_'+uuid.uuid4().hex[:4]
    stage='image_001_wires_'+suffix
    with c.schematic.create(LIB,stage,timeout=120) as sch:
        for d in D:
            sch.add(inst(d['lib'],d['cell'],'symbol',d['name'],*point(d['xy']),d['orient']))
            for key,value in d['params'].items():
                sch.add(f'let((i) i=car(setof(x cv~>instances x~>name=={q(d["name"])})) dbReplaceProp(i {q(key)} "string" {q(value)}))')
        for name,xy in PORTS.items():sch.add(pin(name,*point(xy),'R0',direction='inputOutput'))
        emit_wires(sch)
    checked(c,stage,'wired-stage')
    print('Verified continuous wires in stage:',stage,flush=True)
    if not install:return
    # Preserve a native backup, then mutate only wire/drawing lines and their
    # labels in the requested target. Instances, pins and parameters stay intact.
    backup='image_001_labels_backup_'+suffix
    skill(f'let((src dst) src=dbOpenCellViewByType({q(LIB)} {q(CELL)} "schematic" "schematic" "r") dst=dbCopyCellView(src {q(LIB)} {q(backup)} "schematic" nil nil nil) unless(dst error("backup failed")) dbSave(dst) dbClose(dst) dbClose(src) t)')
    verify_electrical(read(c,CELL))
    old_scene=read_scene(c,LIB,CELL)
    json_file('before-continuous-wires.json',dict(original,scene=old_scene))
    with c.schematic.modify(LIB,CELL,timeout=120) as sch:
        sch.add('foreach(s setof(x cv~>shapes x~>layerName=="wire" && member(x~>objType list("line" "path" "label"))) dbDeleteObject(s))')
        emit_wires(sch)
        sch.add(f'dbReplaceProp(cv "imageCaseWiringRevision" "string" {q(REVISION)})')
    data,scene=checked(c,CELL,'wired-final')
    loaded=load_circuit(LIB,CELL)
    json_file('readback.json',loaded)
    json_file('check-save.json',json.loads((CASE/'wired-final-check.json').read_text(encoding='utf-8')))
    result=dict(library=LIB,cell=CELL,snapshotId=loaded['id'],instances=len(data['instances']),
        topologyMatches=True,checkErrors=0,checkWarnings=0,physicalNets=len(ROUTES),
        continuousWires=True,backupCell=backup,stagingCell=stage,simulated=False)
    json_file('wiring-result.json',result)
    print(json.dumps(result,indent=2))

if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--install',action='store_true');args=parser.parse_args();main(args.install)
