"""Create a new, isolated teaching schematic; refuse to replace existing data."""
import json
from dataclasses import asdict
from pathlib import Path
from bridge_service import client, skill, load_circuit, save_json, LOCK, remote_library_path
from circuit_model import LIBRARY, CELL, DEVICES
from virtuoso_bridge.virtuoso.ops import q
from virtuoso_bridge.virtuoso.schematic.ops import schematic_create_inst_by_master_name, schematic_label_instance_term, schematic_create_pin, schematic_create_net_stub
from virtuoso_bridge.virtuoso.symbol.reader import read_symbol_ports

def setup():
    c=client()
    with LOCK:
        if skill(f'ddGetObj({q(LIBRARY)} {q(CELL)} "schematic") != nil')=="t":
            data=load_circuit(LIBRARY,CELL)
            if not data["verified"]: raise RuntimeError("同名原理图已存在但拓扑不同，已保留原文件")
            report=c.schematic.check_and_save(LIBRARY,CELL)
            save_json("schematic-check.json",asdict(report))
            print("Existing teaching schematic verified.")
            return data
        if skill(f'ddGetObj({q(LIBRARY)}) != nil')!="t":
            c.library.create(LIBRARY,remote_library_path(LIBRARY))
        evidence={}
        for cell in ["nmos4","pmos4","idc","cap"]:
            evidence[cell]=read_symbol_ports(c,"analogLib",cell)
        save_json("symbol-evidence.json",evidence)
        with c.schematic.create(LIBRARY,CELL,timeout=90) as sch:
            for d in DEVICES:
                x,y=d["xy"]
                sch.add(schematic_create_inst_by_master_name(d["lib"],d["cell"],"symbol",d["name"],x,y,"R0"))
                for key,value in d["params"].items():
                    sch.add(f'let((i) i=car(setof(x cv~>instances x~>name=={q(d["name"])})) dbReplaceProp(i {q(key)} "string" {q(value)}))')
                for term,net in d["terms"].items():
                    sch.add(schematic_label_instance_term(d["name"],term,net,cosmetic="clean",bind_label_to_wire=True))
            for name,x,y,direction in [("INP",1,5,"input"),("INN",1,7,"input"),("OUT",23,6,"output"),("VDD",23,10,"inputOutput"),("VSS",23,0,"inputOutput")]:
                sch.add(schematic_create_pin(name,x,y,"R0",direction=direction))
                sch.add(schematic_create_net_stub(name,x,y,direction="right",length=.5))
        data=load_circuit(LIBRARY,CELL)
        if not data["verified"]:
            raise RuntimeError("已创建原理图，但连接回读与预期不同。停止，保留证据供检查。")
        report=c.schematic.check_and_save(LIBRARY,CELL)
        save_json("schematic-check.json",asdict(report))
        print(json.dumps(dict(lib=LIBRARY,cell=CELL,devices=len(data["instances"]),verified=data["verified"],check=report.status),ensure_ascii=False))
        return data

if __name__=="__main__": setup()
