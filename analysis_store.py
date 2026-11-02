"""Atomic, versioned analysis updates, independent from schematic data."""
from __future__ import annotations
import copy
import hashlib
import json
from pathlib import Path
import re
import threading
import time
import uuid

STORE_LOCK=threading.RLock()

class AnalysisConflict(RuntimeError):
    def __init__(self,current):
        super().__init__('讲解已被更新，本次旧结果未覆盖新结论')
        self.current=current

def require_snapshot(id):
    if not isinstance(id,str) or not re.fullmatch(r'[a-f0-9]{20}',id):
        raise ValueError('电路快照编号无效')
    return id

def analysis_version(analysis):
    if not analysis: return None
    if analysis.get('revisionId'): return analysis['revisionId']
    canonical=json.dumps(analysis,ensure_ascii=False,sort_keys=True)
    return 'legacy-'+hashlib.sha256(canonical.encode()).hexdigest()[:16]

def atomic_json(path,data):
    path=Path(path);path.parent.mkdir(parents=True,exist_ok=True)
    temp=path.with_name(path.name+'.'+uuid.uuid4().hex+'.tmp')
    temp.write_text(json.dumps(data,ensure_ascii=False,indent=2,allow_nan=False),encoding='utf-8')
    temp.replace(path)

def validate_analysis(result,names):
    if not isinstance(result,dict): raise ValueError('修订讲解格式无效')
    for key in ['title','summary']:
        if not isinstance(result.get(key),str) or not result[key].strip(): raise ValueError('修订缺少标题或摘要')
    identity=result.get('identity')
    if not isinstance(identity,dict) or not all(isinstance(identity.get(k),str) and identity[k].strip() for k in ['label','reason']):
        raise ValueError('修订缺少电路名称与判断依据')
    if identity.get('status') not in ['identified','hypothesis','unknown'] or identity.get('confidence') not in ['high','medium','low']:
        raise ValueError('修订缺少有效的置信度')
    for key in ['evidence','limitations']:
        if not isinstance(identity.get(key,[]),list) or any(not isinstance(v,str) for v in identity.get(key,[])): raise ValueError('判断依据格式无效')
    sections=result.get('sections')
    if not isinstance(sections,list) or (names and not sections) or len(sections)>12: raise ValueError('修订必须同时包含电路讲解')
    ids=set()
    for section in sections:
        if not isinstance(section,dict) or not all(isinstance(section.get(k),str) and section[k].strip() for k in ['id','title','body','effect']): raise ValueError('修订部分字段不完整')
        if section['id'] in ids: raise ValueError('修订部分编号重复')
        ids.add(section['id'])
        if not isinstance(section.get('devices'),list) or any(n not in names for n in section['devices']): raise ValueError('修订引用了当前电路不存在的器件')
    for key in ['caveats','contextNotes']:
        if not isinstance(result.get(key,[]),list) or any(not isinstance(v,str) for v in result.get(key,[])): raise ValueError('修订说明格式无效')
    return copy.deepcopy(result)

class AnalysisStore:
    def __init__(self,root,current):
        self.root=Path(root)
        self.current=current

    def publish(self,id,analysis,*,expected,reason,source):
        require_snapshot(id)
        with STORE_LOCK:
            current=self.current(id)
            if analysis_version(current)!=expected: raise AnalysisConflict(current)
            folder=self.root/'analysis-revisions'/id
            if current:
                old=copy.deepcopy(current)
                old['revisionId']=analysis_version(current)
                old.setdefault('revisionReason','原始分析')
                old.setdefault('updatedAt',old.get('generatedAt',time.time()))
                target=folder/(old['revisionId']+'.json')
                if not target.exists(): atomic_json(target,old)
            result=copy.deepcopy(analysis)
            result.update(snapshotId=id,schemaVersion=2,classificationOnly=bool(source=='user-restore' and analysis.get('classificationOnly')),revisionId=uuid.uuid4().hex[:16],parentRevision=expected,revisionReason=reason,source=source,updatedAt=time.time())
            atomic_json(folder/(result['revisionId']+'.json'),result)
            # The active file is replaced last, so readers see one whole version.
            atomic_json(self.root/('explanation-'+id+'.json'),result)
            return result

    def history(self,id):
        require_snapshot(id)
        with STORE_LOCK:
            current=self.current(id)
            active=analysis_version(current)
            rows=[]
            for p in (self.root/'analysis-revisions'/id).glob('*.json'):
                r=json.loads(p.read_text(encoding='utf-8'))
                rows.append(dict(revisionId=r['revisionId'],title=r.get('identity',{}).get('label',r.get('title','')),summary=r.get('summary',''),reason=r.get('revisionReason',''),source=r.get('source'),updatedAt=r.get('updatedAt',r.get('generatedAt',0)),active=r['revisionId']==active))
            return dict(activeRevision=active,revisions=sorted(rows,key=lambda r:r['updatedAt'],reverse=True))

    def restore(self,id,revision_id,expected):
        require_snapshot(id)
        if not re.fullmatch(r'(?:legacy-)?[a-f0-9]{12,32}',str(revision_id)): raise ValueError('修订编号无效')
        path=self.root/'analysis-revisions'/id/(revision_id+'.json')
        if not path.is_file(): raise ValueError('未找到该修订')
        result=json.loads(path.read_text(encoding='utf-8'))
        return self.publish(id,result,expected=expected,reason='恢复到历史修订 '+revision_id,source='user-restore')
