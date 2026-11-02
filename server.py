"""Loopback-only desktop web application; no remote shell endpoints."""
from __future__ import annotations
import argparse
from concurrent.futures import ThreadPoolExecutor
import json
import mimetypes
from http.server import BaseHTTPRequestHandler,ThreadingHTTPServer
from pathlib import Path
import secrets
import threading
import time
import traceback
from urllib.parse import parse_qs,urlsplit
import uuid
import bridge_service as service

ROOT=Path(__file__).resolve().parent
TOKEN=secrets.token_urlsafe(32)
JOBS={}
JOB_LOCK=threading.Lock()
POOL=ThreadPoolExecutor(max_workers=3)

def job(action,body):
    tasks={
        "sync":lambda:service.sync_libraries(),
        "load":lambda:service.load_circuit(body["lib"],body["cell"]),
        "analyze":lambda:service.explain(body["snapshotId"],force=body.get('force',False)),
        "identify":lambda:service.identify(body["snapshotId"]),
        "chat":lambda:service.chat(body["snapshotId"],body["message"],body.get("history",[]),body.get("changes",{}),body.get("runId"),body.get('syncExplanation',True)),
        "revise":lambda:service.revise_from_discussion(body['snapshotId'],body.get('history',[]),body.get('expectedVersion')),
        "restore-analysis":lambda:service.restore_analysis(body['snapshotId'],body['revisionId'],body.get('expectedVersion')),
        "simulate":lambda:service.simulate(body["snapshotId"],body.get("changes",{})),
        "status":lambda:service.status(),
        "connect":lambda:service.connect(),
    }
    if action not in tasks: raise ValueError("未知操作")
    id=uuid.uuid4().hex
    with JOB_LOCK:
        if sum(j["status"] in ["queued","running"] for j in JOBS.values())>=6: raise ValueError("正在处理其他操作，请稍后重试")
        if len(JOBS)>120:
            for key in list(JOBS)[:60]:
                if JOBS[key]["status"] not in ["queued","running"]: del JOBS[key]
        JOBS[id]=dict(id=id,status="queued",action=action,createdAt=time.time())
    def execute():
        with JOB_LOCK: JOBS[id]["status"]="running"
        try:
            result=tasks[action]()
            with JOB_LOCK: JOBS[id].update(status="done",result=result)
        except Exception as exc:
            with JOB_LOCK: JOBS[id].update(status="error",error=str(exc))
            with (service.RUNTIME/"errors.log").open("a",encoding="utf-8") as f:
                f.write(time.strftime("%Y-%m-%d %H:%M:%S")+" "+action+"\n"+traceback.format_exc()+"\n")
    POOL.submit(execute)
    return dict(jobId=id)

class Handler(BaseHTTPRequestHandler):
    server_version="CircuitStudio/0.1"
    def log_message(self,format,*args): pass
    def headers_ok(self):
        return self.headers.get("Host") in {f"127.0.0.1:{self.server.server_port}",f"localhost:{self.server.server_port}"}
    def send(self,data,status=200,content_type="application/json; charset=utf-8"):
        if not isinstance(data,bytes): data=json.dumps(data,ensure_ascii=False,allow_nan=False).encode()
        self.send_response(status)
        self.send_header("Content-Type",content_type)
        self.send_header("Content-Length",str(len(data)))
        self.send_header("Cache-Control","no-store")
        self.send_header("X-Content-Type-Options","nosniff")
        self.send_header("X-Frame-Options","DENY")
        self.send_header("Content-Security-Policy","default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; img-src 'self' data:; connect-src 'self'; frame-ancestors 'none'; base-uri 'none'")
        self.end_headers()
        try: self.wfile.write(data)
        except (BrokenPipeError,ConnectionResetError): pass
    def do_GET(self):
        if not self.headers_ok(): return self.send(dict(error="Invalid host"),403)
        parsed=urlsplit(self.path); path=parsed.path; query=parse_qs(parsed.query)
        try:
            if path=="/api/health": return self.send(dict(ok=True,app="Circuit Studio"))
            if path=="/api/bootstrap":
                latest=service.RUNTIME/"last-simulation.json"
                circuit=service.get_last()
                runs=[]
                if circuit:
                    for p in (service.RUNTIME/"runs").glob("*/result.json"):
                        r=json.loads(p.read_text(encoding="utf-8"))
                        if r.get("snapshotId")==circuit["id"]: runs.append(r)
                baseline=next((r for r in sorted(runs,key=lambda r:r["createdAt"]) if not r.get("changes")),None)
                runs=sorted(runs,key=lambda r:r["createdAt"])[-20:]
                return self.send(dict(libraries=service.libraries(),circuit=circuit,simulation=runs[-1] if runs else None,baseline=baseline,runs=runs))
            if path=="/api/cells": return self.send(service.cells(query.get("lib",[""])[0]))
            if path.startswith('/api/circuit-history/'):
                return self.send(service.simulation_history(path.rsplit('/',1)[-1]))
            if path.startswith('/api/conversation/'):
                return self.send(service.conversation(path.rsplit('/',1)[-1]))
            if path.startswith('/api/analysis-history/'):
                return self.send(service.analysis_store().history(path.rsplit('/',1)[-1]))
            if path.startswith("/api/jobs/"):
                id=path.rsplit("/",1)[-1]
                with JOB_LOCK: state=JOBS.get(id)
                return self.send(state or dict(error="任务不存在"),200 if state else 404)
            if path.startswith("/api/explanation/"):
                id=path.rsplit("/",1)[-1]
                if len(id)!=20 or any(c not in "0123456789abcdef" for c in id): return self.send(dict(error="无效快照"),400)
                return self.send(service.cached_identity(id))
            if path.startswith("/api/runs/"):
                parts=path.strip("/").split("/")
                if len(parts)!=5 or parts[2]!=parts[2].lower() or len(parts[2])!=12 or any(c not in "0123456789abcdef" for c in parts[2]) or parts[3] not in ["ac","tran"] or parts[4] not in ["input.scs","spectre.out","execution.json"]: return self.send(dict(error="未找到文件"),404)
                p=service.RUNTIME/"runs"/parts[2]/parts[3]/parts[4]
                if not p.is_file(): return self.send(dict(error="未找到文件"),404)
                return self.send(p.read_bytes(),content_type="text/plain; charset=utf-8")
            static={"/":"index.html","/index.html":"index.html","/app.js":"app.js","/device-edit.js":"device-edit.js","/native-scene.js":"native-scene.js","/upgrade.css":"upgrade.css","/style.css":"style.css","/favicon.svg":"favicon.svg"}
            if path in static:
                p=ROOT/"web"/static[path]
                content=p.read_bytes()
                if path in ["/","/index.html"]: content=content.replace(b"__CSRF_TOKEN__",TOKEN.encode())
                return self.send(content,content_type=mimetypes.guess_type(p)[0]+"; charset=utf-8")
            return self.send(dict(error="Not found"),404)
        except (ValueError,KeyError) as exc: self.send(dict(error=str(exc)),400)
        except Exception as exc: self.send(dict(error=str(exc)),500)
    def do_POST(self):
        if not self.headers_ok() or self.headers.get("X-Circuit-Token")!=TOKEN: return self.send(dict(error="会话校验失败，请刷新界面"),403)
        origin=self.headers.get("Origin")
        if origin and origin not in {f"http://127.0.0.1:{self.server.server_port}",f"http://localhost:{self.server.server_port}"}: return self.send(dict(error="Invalid origin"),403)
        try:
            size=int(self.headers.get("Content-Length",0))
            if size<1 or size>64000: raise ValueError("请求大小无效")
            body=json.loads(self.rfile.read(size))
            if not isinstance(body,dict): raise ValueError("请求格式无效")
            if self.path!="/api/jobs": return self.send(dict(error="Not found"),404)
            return self.send(job(body.get("action"),body),202)
        except (ValueError,KeyError) as exc: self.send(dict(error=str(exc)),400)

if __name__=="__main__":
    parser=argparse.ArgumentParser()
    parser.add_argument("--port",type=int,default=8765)
    args=parser.parse_args()
    server=ThreadingHTTPServer(("127.0.0.1",args.port),Handler)
    print(f"Circuit Studio ready: http://127.0.0.1:{args.port}",flush=True)
    try: server.serve_forever()
    except KeyboardInterrupt: pass
    finally: server.server_close(); POOL.shutdown(wait=False,cancel_futures=True)
