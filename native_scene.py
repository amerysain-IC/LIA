"""Read source geometry, rather than guessing PDK symbols from their names.

All coordinates remain in Virtuoso database units. Only the viewer maps them
to screen pixels. This reader owns and closes its read-only cellview reference.
"""
from __future__ import annotations
from virtuoso_bridge.virtuoso.ops import q
from virtuoso_bridge.virtuoso.skill_output import parse_sexpr

def scene_skill(lib, cell):
    return r'''
procedure(csTutorShape(s)
  let((typ pts txt)
    typ=s~>objType
    pts=when(member(typ list("line" "path" "polygon")) s~>points)
    txt=when(typ=="label" s~>theLabel)
    list(typ s~>layerName s~>purpose pts s~>bBox
      when(typ=="label" s~>xy) txt
      when(typ=="label" s~>height)
      when(typ=="label" s~>orient)
      when(typ=="label" s~>justify)
      when(typ=="label" s~>labelType)
      when(s~>net s~>net~>name)
      when(typ=="arc" s~>ellipseBBox)
      when(typ=="arc" s~>startAngle)
      when(typ=="arc" s~>stopAngle))))
procedure(csTutorTransform(i)
  list(dbTransformPoint(list(0 0) i~>transform)
       dbTransformPoint(list(1 0) i~>transform)
       dbTransformPoint(list(0 1) i~>transform)))
procedure(csTutorMaster(m depth)
  when(m
    list(m~>bBox mapcar('csTutorShape m~>shapes)
      when(depth>0
        foreach(mapcar child m~>instances
          list(csTutorTransform(child) csTutorMaster(child~>master depth-1)))))))
let((cv answer)
  unwindProtect(
    progn(
      cv=dbOpenCellViewByType(__LIB__ __CELL__ "schematic" "schematic" "r")
      unless(cv error("Cannot read source schematic geometry"))
      answer=list("scene-v1" cv~>bBox mapcar('csTutorShape cv~>shapes)
        foreach(mapcar i cv~>instances
          list(i~>name i~>libName i~>cellName i~>viewName
            csTutorTransform(i) i~>bBox csTutorMaster(i~>master 2))))
      answer)
    when(cv dbClose(cv))))
'''.replace('__LIB__',q(lib)).replace('__CELL__',q(cell))

def numbers(value):
    if isinstance(value,list): return [numbers(v) for v in value]
    if isinstance(value,str):
        try: return float(value)
        except ValueError: pass
    return value

def shape(row):
    fields=['type','layer','purpose','points','bbox','xy','text','height','orient','justify','labelType','net','ellipseBBox','startAngle','stopAngle']
    return {k:numbers(v) if k in ['points','bbox','xy','height','ellipseBBox','startAngle','stopAngle'] else v for k,v in zip(fields,row)}

def master(row):
    if not row: return None
    return dict(bbox=numbers(row[0]),shapes=[shape(s) for s in row[1] or []],children=[dict(transform=numbers(c[0]),master=master(c[1])) for c in row[2] or []])

def parse_scene(output):
    data=parse_sexpr(output)
    if not isinstance(data,list) or len(data)!=4 or data[0]!='scene-v1':
        raise ValueError('Virtuoso geometry response is incomplete')
    result=dict(version=1,bbox=numbers(data[1]),shapes=[shape(s) for s in data[2] or []],instances=[])
    for row in data[3] or []:
        result['instances'].append(dict(name=row[0],lib=row[1],cell=row[2],view=row[3],transform=numbers(row[4]),bbox=numbers(row[5]),master=master(row[6])))
    missing=[i['name'] for i in result['instances'] if not i['master']]
    result['diagnostics']=dict(source='virtuoso-database',missingMasters=missing,unsupportedShapes=sorted({s['type'] for i in result['instances'] if i['master'] for s in i['master']['shapes'] if s['type'] not in ['line','path','polygon','rect','ellipse','arc','label','textDisplay']}))
    return result

def read_scene(client,lib,cell):
    response=client.execute_skill(scene_skill(lib,cell),timeout=60)
    if not response.ok: raise RuntimeError('; '.join(response.errors) or '无法读取原理图几何')
    return parse_scene(response.output)
