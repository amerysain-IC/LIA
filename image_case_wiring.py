"""Continuous, source-inspired routes for the 52-device image test case.

Routes are actual conductive schematic wires. Different-net crossings have no
junction; endpoints and collinear overlaps are audited before touching Cadence.
Coordinates are in source-image pixels and are converted by build_image_case.
"""
from __future__ import annotations
from collections import defaultdict
import json
from pathlib import Path
from build_image_case import D, CASE

SYMBOLS=json.loads((CASE/'symbol-evidence.json').read_text(encoding='utf-8'))
DEVICES={d['name']:d for d in D}
TERMINALS={}
for d in D:
    for t in SYMBOLS[d['cell']]['terms']:
        if t['name'] not in d['terms']:continue
        box=t['bbox'];x=(box[0][0]+box[1][0])/2;y=(box[0][1]+box[1][1])/2
        if d['orient']=='MY':x=-x
        elif d['orient']=='R90':x,y=-y,x
        TERMINALS[d['name']+'.'+t['name']]=(d['terms'][t['name']],(round(d['xy'][0]+x*80,6),round(d['xy'][1]-y*80,6)))

ROUTES=defaultdict(list)
def p(name):return TERMINALS[name][1]
def add(net,*points):
    pts=[p(v) if isinstance(v,str) else tuple(v) for v in points]
    for v in points:
        if isinstance(v,str):assert TERMINALS[v][0]==net,(net,v,TERMINALS[v])
    pts=[v for i,v in enumerate(pts) if i==0 or v!=pts[i-1]]
    assert len(pts)>1
    assert all(a[0]==b[0] or a[1]==b[1] for a,b in zip(pts,pts[1:])),(net,pts)
    ROUTES[net].append(pts)

add('Vin',(55,40),(1317,40))
for n in range(1,7):
    x,y=p('R'+str(n)+'.PLUS');add('Vin',(x,40),(x,y))
add('Vin',(118,40),'J1.D')
add('Vin',(741,40),(741,409),'Q13.C')
add('Vin',(1143,40),(1143,293),'Q19.C')
add('Vin',(1244,40),(1244,380),'Q20.C')
add('Vin',(1317,40),'Z2.MINUS')

add('Vout',(58,750),(1270,750))
add('Vout',(58,750),(58,421),'J1.G')
add('Vout','Z1.PLUS',(124,750))
add('Vout','Q7.E',(383,750))
add('Vout','Q8.C',(454,526),(454,750))
add('Vout','Q11.E',(666,626),(666,750))
add('Vout','Q12.C',(698,480),(698,750))
add('Vout','Q14.C',(820,509),(820,750))
for name in ['R9.MINUS','R10.MINUS','R13.MINUS','R14.MINUS','R18.MINUS','R19.MINUS','C1.MINUS']:
    x,y=p(name);add('Vout',name,(x,750))
# Q22.B and Q23.B lie directly on the Vout rail.

add('E1','R1.MINUS',(238,140),(258,140),'Q1.E')
add('E2','R2.MINUS',(383,152),'Q2.E')
add('E3','R3.MINUS',(533,152),'Q3.E')
add('E4','R4.MINUS',(820,152),'Q4.E')
add('E17','R5.MINUS',(966,152),'Q17.E')
add('E18','R6.MINUS',(1077,152),'Q18.E')
add('E5','Q5.E',(238,591),'R9.PLUS')
add('E6','Q6.E',(294,591),'R10.PLUS')
add('E9','Q9.E',(533,526),'R13.PLUS')
add('E21','Q21.E',(1077,546),'R18.PLUS')
add('E23','Q23.E',(1007,765),'R20.PLUS')
add('N20','Z2.PLUS','Z3.MINUS')
add('N21','Z3.PLUS','R23.PLUS')

add('N1','J1.S',(124,436),(124,635),'Z1.MINUS')
add('N1',(124,576),'R8.PLUS')

add('N2','R7.MINUS',(238,561),'Q5.C')
add('N2',(238,278),(278,278),'Q1.B','Q2.B','Q3.B')

add('N3','Q1.C',(238,182),'R7.PLUS')
add('N3',(238,199),(645,199),(645,167),'Q4.B')

add('N4','Q2.C',(383,182),'R11.PLUS')
add('N4',(383,412),(339,412),(339,620),(205,620),(205,576),'R8.MINUS')
add('N4',(339,620),(350,620),(350,576),'Q7.B')
add('N4','Q5.B',(288,576),(288,620))
add('N4','Q6.B',(344,576),(344,620))

add('N5','Q3.C',(533,182),'R12.PLUS')
add('N5',(533,394),(454,394),(454,496),'Q8.E')
add('N5',(533,402),(600,402),(600,450),'Q10.E')

add('N6','Q4.C',(820,182),(820,479),'Q14.E')
add('N6','Q13.B',(820,424))

add('N7','Q17.C',(966,182),(966,218),(1020,218),(1020,167),'Q17.B')
add('N7','Q18.B',(1020,167))
add('N7','Q6.C',(294,561),(294,252),(1020,252),(1020,218))

add('N8','R11.MINUS',(383,511),'Q8.B','Q9.B')
add('N8','Q7.C',(383,511))

add('N9','R12.MINUS',(533,465),'Q10.B')
add('N9','Q9.C',(533,496),(533,465))

add('N10','Q10.C',(600,480),'R14.PLUS')
add('N10',(600,611),'Q11.B')

add('N11',(666,308),'Q19.B')
add('N11','Q11.C',(666,596),(666,308))
add('N11','Q12.E',(698,450),(698,308))
add('N11','Q15.E',(901,363),(901,308))
add('N11','Q16.E',(1007,363),(1007,308))
add('N11','Q18.C',(1077,182),(1077,308))
add('N11',(1085,308),(1085,516),'Q21.C')

add('N12','Q13.E',(741,439),'R15.PLUS')
add('N12',(741,465),'Q12.B')

add('N13','Q15.C',(901,393),(901,470),(952,470),(952,735),'Q22.C')
add('N13',(859,494),(952,494))
add('N13',(859,494),'C1.PLUS')
add('N13',(905,494),'C2.PLUS')
# Q14.B is on the N13 horizontal run.

add('N14','Q15.B',(955,378),'Q16.B')
add('N14',(955,378),(955,444),(1007,444),(1007,735),'Q23.C')
add('N14','Q16.C',(1007,393),(1007,444))

add('N15','Q19.E',(1143,323),(1143,395),'Q20.B')
add('N15',(1143,395),'R16.PLUS')

add('N16','Q20.E',(1244,410),'R19.PLUS')
add('N16','R17.MINUS',(1244,531))
add('N16','R16.MINUS',(1143,582),(1244,582))
add('N16','R15.MINUS',(741,595),(1143,595),(1143,582))

add('N17','Q21.B','R17.PLUS')
add('N17','R23.MINUS',(1317,487),(1160,487),(1160,531))

add('N18','Q22.E',(952,765),(952,844),'R21.PLUS')
add('N18','R20.MINUS',(1007,844))

add('N19','R21.MINUS','R22.PLUS')
add('N19','C2.MINUS',(905,868),(1117,868),(1117,844))
add('Adjust','R22.MINUS',(1300,844))

PORTS={'Vin':(55,40),'Vout':(1270,750),'Adjust':(1300,844)}
def segments():
    return [(net,a,b) for net,paths in ROUTES.items() for path in paths for a,b in zip(path,path[1:])]
def on_segment(p,a,b):
    return min(a[0],b[0])-1e-6<=p[0]<=max(a[0],b[0])+1e-6 and min(a[1],b[1])-1e-6<=p[1]<=max(a[1],b[1])+1e-6 and abs((b[0]-a[0])*(p[1]-a[1])-(b[1]-a[1])*(p[0]-a[0]))<1e-5
def physically_joined(a,b,c,d):
    # A crossing without an endpoint/junction is a crossover, not a contact.
    return any(on_segment(p,c,d) for p in [a,b]) or any(on_segment(p,a,b) for p in [c,d])
def component_count(segs):
    parent=list(range(len(segs)))
    def find(i):
        while parent[i]!=i:parent[i]=parent[parent[i]];i=parent[i]
        return i
    for i,(a,b) in enumerate(segs):
        for j,(c,d) in enumerate(segs[:i]):
            if physically_joined(a,b,c,d):parent[find(i)]=find(j)
    return len({find(i) for i in range(len(segs))})
def audit():
    errors=[];segs=segments()
    for name,(net,pt) in TERMINALS.items():
        if not any(n==net and on_segment(pt,a,b) for n,a,b in segs):errors.append(('unwired',name,net,pt))
        for n,a,b in segs:
            if n!=net and on_segment(pt,a,b):errors.append(('foreign-terminal',name,net,n,pt))
    for n,paths in ROUTES.items():
        for path in paths:
            for pt in path:
                for m,a,b in segs:
                    if m!=n and on_segment(pt,a,b):errors.append(('foreign-junction',n,m,pt))
    for n,pt in PORTS.items():
        if not any(m==n and on_segment(pt,a,b) for m,a,b in segs):errors.append(('unwired-port',n))
    for net in ROUTES:
        count=component_count([(a,b) for n,a,b in segs if n==net])
        if count!=1:errors.append(('disconnected-wire-tree',net,count))
    return list(dict.fromkeys(errors))

def emit_wires(sch):
    from build_image_case import point
    from virtuoso_bridge.virtuoso.ops import q
    from virtuoso_bridge.virtuoso.schematic.ops import schematic_create_wire as wire
    for net,paths in ROUTES.items():
        ordered=sorted(paths,key=lambda p:sum(math.dist(a,b) for a,b in zip(p,p[1:])),reverse=True)
        # Attach the one descriptive net label to a returned wire object. Do not
        # add a free-ended stub merely to carry a label.
        for index,path in enumerate(ordered):
            expr=wire([point(p) for p in path],route_style='draw')
            if index==0:
                sch.add(f'let((ws w pts mid) ws={expr} w=car(ws) unless(w error("route not created")) pts=w~>points mid=list((xCoord(car(pts))+xCoord(cadr(pts)))/2.0 (yCoord(car(pts))+yCoord(cadr(pts)))/2.0) schCreateWireLabel(cv w mid {q(net)} "lowerCenter" "R0" "stick" .04 nil))')
            else:sch.add(expr)


if __name__=='__main__':
    errors=audit();print(json.dumps(dict(nets=len(ROUTES),segments=len(segments()),errors=errors),indent=2))
    raise SystemExit(bool(errors))
