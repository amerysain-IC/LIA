"""Explicit, inspectable circuit contracts for the first teaching experiment."""
from __future__ import annotations
import copy
import hashlib
import json
import math
import re

LIBRARY = "CircuitTutorLab"
CELL = "two_stage_opamp"

def device(name, kind, terms, params, xy, group):
    return dict(name=name, kind=kind, lib="analogLib", cell={"nmos":"nmos4", "pmos":"pmos4", "capacitor":"cap", "isource":"idc"}[kind], terms=terms, params=params, xy=xy, group=group)

DEVICES = [
    device("M1", "nmos", dict(D="NX", G="INN", S="TAIL", B="VSS"), dict(w="20u", l="1u", model="edu_n"), [4, 5], "input"),
    device("M2", "nmos", dict(D="N1", G="INP", S="TAIL", B="VSS"), dict(w="20u", l="1u", model="edu_n"), [9, 5], "input"),
    device("M3", "pmos", dict(D="NX", G="NX", S="VDD", B="VDD"), dict(w="40u", l="1u", model="edu_p"), [4, 9], "mirror"),
    device("M4", "pmos", dict(D="N1", G="NX", S="VDD", B="VDD"), dict(w="40u", l="1u", model="edu_p"), [9, 9], "mirror"),
    device("M5", "nmos", dict(D="TAIL", G="VB", S="VSS", B="VSS"), dict(w="20u", l="1u", model="edu_n"), [6.5, 1.5], "bias"),
    device("M6", "pmos", dict(D="OUT", G="N1", S="VDD", B="VDD"), dict(w="160u", l="1u", model="edu_p"), [16, 9], "output"),
    device("M7", "nmos", dict(D="OUT", G="VB", S="VSS", B="VSS"), dict(w="40u", l="1u", model="edu_n"), [16, 3], "output"),
    device("M8", "nmos", dict(D="VB", G="VB", S="VSS", B="VSS"), dict(w="10u", l="1u", model="edu_n"), [-2, 3], "bias"),
    device("IREF", "isource", dict(PLUS="VDD", MINUS="VB"), dict(idc="20u"), [-2, 8], "bias"),
    device("CC", "capacitor", dict(PLUS="N1", MINUS="OUT"), dict(c="2p"), [12, 6], "compensation"),
    device("CL", "capacitor", dict(PLUS="OUT", MINUS="VSS"), dict(c="3p"), [20, 3], "load"),
]
SECTIONS = [
    dict(id="input", title="输入差分对", subtitle="M1 · M2", devices=["M1","M2"], body="M1 与 M2 把两个输入端的电压差变成支路电流差。两者共享 M5 提供的尾电流；INP 接 M2，INN 接 M1。输入对称时，两支路电流接近相等。", effect="增大输入管 W，固定电流下通常可提高跨导，同时增加寄生电容；增大 L 往往提高输出电阻。实际变化要结合工作点与仿真判断。"),
    dict(id="mirror", title="电流镜有源负载", subtitle="M3 · M4", devices=["M3","M4"], body="M3 漏极与栅极相连，建立 PMOS 镜像偏置；M4 将电流镜像到 N1。它把差分电流变化汇聚为单端电压，并为第一级提供较大的等效负载电阻。", effect="M3、M4 的尺寸比会影响电流镜比例与直流平衡。一起调整可保持近似镜像关系；单独调整会引入偏置变化。"),
    dict(id="output", title="第二级共源放大", subtitle="M6 · M7", devices=["M6","M7"], body="N1 驱动 PMOS M6 的栅极；M7 作为偏置电流下拉负载。N1 下降时，M6 导通增强，OUT 上升。与前级合起来，INP 是非反相输入。", effect="M6、M7 的尺寸和偏置共同决定输出静态点、增益与驱动能力。改变一侧后，应先检查 OUT 是否仍处于电源范围中部及各管饱和情况。"),
    dict(id="compensation", title="米勒补偿", subtitle="CC", devices=["CC"], body="CC 跨接第一级高阻节点 N1 与输出 OUT，利用米勒效应拉低主极点，使极点分离。它也会引入前馈路径，因此稳定性需要通过实际幅相曲线评估。", effect="增大 CC 常使单位增益频率降低，并可能改善相位裕度，但结果取决于非主极点与零点；还可能减慢大信号转换。"),
    dict(id="bias", title="偏置与尾电流", subtitle="IREF · M8 · M5", devices=["IREF","M8","M5"], body="IREF 流过二极管连接的 M8 建立 VB。M5 和 M7 通过 VB 镜像出尾电流与第二级电流；镜像比例由相应 W/L 决定。", effect="提高 IREF 往往增加跨导、带宽和充放电能力，也会增加功耗；应同时检查输入共模范围与输出摆幅。"),
    dict(id="load", title="输出负载", subtitle="CL", devices=["CL"], body="CL 模拟后级输入与连线的等效电容。它位于 OUT 与 VSS 之间，会影响输出极点和阶跃响应。", effect="增大 CL 会提高驱动负担，通常降低非主极点频率。比较相位裕度、过冲和建立速度，观察负载对稳定性的影响。"),
]

def topology_hash(instances):
    topology = sorted((x["name"], x["lib"], x["cell"], sorted(x["terms"].items())) for x in instances)
    return hashlib.sha256(json.dumps(topology, ensure_ascii=False).encode()).hexdigest()

def parse_value(value):
    """Only finite numeric engineering literals. Never evaluate user expressions."""
    if isinstance(value, bool):
        raise ValueError("参数不能是布尔值")
    text = str(value).strip().replace("µ", "u").replace("μ", "u")
    match = re.fullmatch(r"([+-]?(?:\d+(?:\.\d*)?|\.\d+)(?:[eE][+-]?\d+)?)(meg|[TGMkKmunpf]?)", text)
    if not match:
        raise ValueError("参数只支持数字和工程单位，例如 20u、1u、2p")
    scale = {"":1,"T":1e12,"G":1e9,"M":1e6,"meg":1e6,"k":1e3,"K":1e3,"m":1e-3,"u":1e-6,"n":1e-9,"p":1e-12,"f":1e-15}[match[2]]
    number = float(match[1]) * scale
    if not math.isfinite(number) or number <= 0:
        raise ValueError("参数必须是有限正数")
    return number

def editable(instance):
    kind=instance.get("kind", "unknown")
    return {"nmos":["w","l"], "pmos":["w","l"], "capacitor":["c"], "resistor":["r"], "isource":["idc"]}.get(kind, [])

def apply_changes(snapshot, changes):
    if not isinstance(changes, dict) or len(changes)>200:
        raise ValueError("参数修改格式无效")
    result=copy.deepcopy(snapshot)
    devices={d["name"]:d for d in result["instances"]}
    ranges={"w":(0.1e-6,2000e-6),"l":(0.1e-6,100e-6),"c":(1e-15,1e-6),"r":(0.1,1e12),"idc":(1e-9,.01)}
    for name, values in changes.items():
        if name not in devices or not isinstance(values,dict):
            raise ValueError("未找到器件或参数格式无效")
        for key,value in values.items():
            if key not in editable(devices[name]):
                raise ValueError("只允许更改器件数值，不能更改模型、名称或拓扑")
            numeric=parse_value(value)
            lo,hi=ranges[key]
            if not lo<=numeric<=hi:
                raise ValueError(f"{name}.{key} 超出教学实验范围 [{lo:g}, {hi:g}]")
            devices[name]["params"][key]=str(value).strip()
    if topology_hash(result["instances"]) != snapshot["topologyHash"]:
        raise ValueError("拓扑校验失败")
    return result

def device_kind(d):
    """Terminals constrain the type; the PDK cell/model only refines polarity."""
    label=(d.get('cell','')+' '+str(d.get('params',{}).get('model',''))).lower()
    terms={t.upper() for t in d.get('terms',{})}
    if {'D','G','S'}<=terms:
        if 'jfet' in label: return 'pjfet' if 'pjfet' in label else 'njfet' if 'njfet' in label else 'jfet'
        if re.search(r'pmos|pch|pfet|\bp\d',label): return 'pmos'
        if re.search(r'nmos|nch|nfet|\bn\d',label): return 'nmos'
        return 'mos'
    if {'C','B','E'}<=terms: return 'pnp' if 'pnp' in label else 'npn' if 'npn' in label else 'bjt'
    name=d.get('cell','').lower()
    if name in ['gnd','vss','vdd'] and len(terms)==1: return 'ground' if name=='gnd' else 'supply'
    if {'PLUS','MINUS'}<=terms:
        if 'zener' in name: return 'zener'
        if name.startswith(('vdc','vpulse','vsin','vsource','vac')): return 'vsource'
        if name.startswith(('idc','ipulse','isin','isource','iac')): return 'isource'
        if re.search(r'^cap|capacitor|mimcap|momcap',name): return 'capacitor'
        if name.startswith(('res','rpp','rn','rp')) or 'r' in d.get('params',{}): return 'resistor'
        if name.startswith(('dio','pn','np')): return 'diode'
    return 'unknown'

def enrich(raw, lib, cell):
    teaching=lib==LIBRARY and cell==CELL
    expected={d["name"]:d for d in DEVICES}
    for d in raw["instances"]:
        d["kind"]=device_kind(d)
        if teaching and d["name"] in expected:
            d["group"]=expected[d["name"]]["group"]
        else:
            d["group"]="general"
        evidence=d.get("param_evidence",{}).get("stored",{})
        d["params"].update({k:str(v) for k,v in evidence.items() if k in editable(d)+["model"] and v is not None})
        d["editable"]=editable(d)
    raw.update(lib=lib, cell=cell, title="二级 CMOS 运算放大器" if teaching else f"{lib} / {cell}", teaching=teaching, topologyHash=topology_hash(raw["instances"]), source="virtuoso", modelLabel="通用 MOS Level-1 教学模型 · 非 PDK 签核" if teaching else "来自 Virtuoso 原理图 · 模型待确认")
    raw["id"]=hashlib.sha256(json.dumps(raw, sort_keys=True, ensure_ascii=False).encode()).hexdigest()[:20]
    if teaching:
        desired=topology_hash(DEVICES)
        models_match=all(d["params"].get("model")==expected.get(d["name"],{}).get("params",{}).get("model") for d in raw["instances"] if d["kind"] in ["nmos","pmos"])
        unsupported={"m","nf","as","ad","ps","pd","nrd","nrs","sa","sb","sd","delvto","dtemp","trise"}
        unsupported_properties=any(k in unsupported and v not in (None,"", " ") for d in raw["instances"] for k,v in d.get("param_evidence",{}).get("stored",{}).items())
        raw["verified"]=raw["topologyHash"]==desired and models_match and not unsupported_properties and all(d.get("numInst",1)==1 and not d.get("nlAction") for d in raw["instances"])
        raw["sections"]=copy.deepcopy(SECTIONS)
    else:
        raw["verified"]=False
        raw["sections"]=[]
    return raw

def make_netlist(snapshot, mode="ac"):
    if not snapshot.get("teaching") or not snapshot.get("verified") or snapshot["topologyHash"] != topology_hash(DEVICES) or topology_hash(snapshot["instances"]) != topology_hash(DEVICES):
        raise ValueError("自动仿真目前仅支持已校验的二级运放；其他电路需要先配置模型和测试平台")
    lines=["// Circuit Studio — derived from verified Virtuoso connectivity", "simulator lang=spectre", "global 0", "model edu_n mos1 type=n vto=0.45 kp=200u gamma=0.4 phi=0.7 lambda=0.04 tox=7n cgso=0.2n cgdo=0.2n", "model edu_p mos1 type=p vto=-0.45 kp=80u gamma=0.4 phi=0.7 lambda=0.04 tox=7n cgso=0.2n cgdo=0.2n", "subckt amplifier (INP INN OUT VDD VSS)"]
    for d in sorted(snapshot["instances"],key=lambda x:x["name"]):
        p=d["params"]; t=d["terms"]; kind=d["kind"]
        if kind in ["nmos","pmos"]:
            order=["D","G","S","B"]
            text=f"{d['name']} ({' '.join(t[k] for k in order)}) {'edu_p' if kind=='pmos' else 'edu_n'} w={parse_value(p['w']):.12g} l={parse_value(p['l']):.12g}"
        else:
            order=["PLUS","MINUS"]
            primitive,key=("capacitor","c") if kind=="capacitor" else ("isource","idc")
            text=f"{d['name']} ({' '.join(t[k] for k in order)}) {primitive} {'c' if key=='c' else 'dc'}={parse_value(p[key]):.12g}"
        lines.append(text)
    lines += ["ends amplifier", "VDD (vdd 0) vsource dc=1.8", "simulatorOptions options reltol=1e-5 vabstol=1u iabstol=1p temp=27"]
    if mode=="ac":
        lines += ["VINP (inp 0) vsource dc=0.9 mag=0.5", "VINN (inn 0) vsource dc=0.9 mag=0.5 phase=180", "XAMP (inp inn out vdd 0) amplifier", "op dc", "ac ac start=1 stop=1G dec=60", "save out inp inn XAMP.N1 XAMP.VB VDD:p", "saveOptions options save=allpub"]
    else:
        lines += ["VINP (inp 0) vsource type=pulse val0=0.895 val1=0.905 delay=2u rise=20n fall=20n width=8u period=16u", "XAMP (inp out out vdd 0) amplifier", "tran tran stop=20u maxstep=10n", "save inp out", "saveOptions options save=allpub"]
    return "\n".join(lines)+"\n"
