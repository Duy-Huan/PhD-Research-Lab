"""Read-only historical OpenCode sessions; the standalone software runtime is retired.

No OpenCode client, server, CLI, plugin or model call is imported or started here.
"""
from __future__ import annotations
import json
import re
import sqlite3
from contextlib import closing

from fastapi import APIRouter, Depends, HTTPException
from backend.api.common import call
from backend.core.config import data_dir, project_scope
from backend.knowledge.research_store import safe_child


async def bind_project():
    with project_scope(data_dir()):yield


router=APIRouter(dependencies=[Depends(bind_project)])


def _public(value):
    from backend.core.telemetry import redact
    if isinstance(value,dict):
        return {key:_public(item) for key,item in value.items()
                if not re.search(r'(?i)token|secret|password|credential|cookie|authorization|api_key|environment',key)}
    if isinstance(value,list):return [_public(item) for item in value]
    return redact(value) if isinstance(value,str) else value


def _history(tid: str, sid: str='') -> list:
    path=safe_child(data_dir(),'workspace','research','research.sqlite3')
    if not path.is_file():return []
    with closing(sqlite3.connect(path.as_uri()+'?mode=ro',uri=True)) as connection:
        connection.row_factory=sqlite3.Row
        connection.execute('BEGIN')
        tables={row[0] for row in connection.execute("SELECT name FROM sqlite_master WHERE type='table'")}
        if 'topics' not in tables or not connection.execute('SELECT 1 FROM topics WHERE id=?',(tid,)).fetchone():
            raise HTTPException(404,'Historical topic not found in this project')
        if 'opencode_sessions' not in tables:return []
        rows=connection.execute("SELECT * FROM opencode_sessions WHERE topic_id=? AND (?='' OR id=?) ORDER BY updated DESC LIMIT 100",(tid,sid,sid)).fetchall()
        result=[]
        for row in rows:
            value=dict(row)
            try:value['payload']=json.loads(value['payload'])
            except (ValueError,TypeError):value['payload']={'unavailable':'Original payload is retained on disk for recovery'}
            result.append({**_public(value),'historical':True,'read_only':True,'retired_software':True,
                           'native_execution_observed':False})
        return result


@router.get('/api/opencode/status')
async def status():
    return {'engine':'opencode','state':'RETIRED','ready':False,'running':False,
            'detail':'Standalone software retired. Use native coding tools and Models; historical sessions remain read-only.'}


@router.get('/api/research/topics/{tid}/opencode/sessions')
async def sessions(tid: str):
    return {'sessions':await call(_history,tid),'read_only':True,'retired_software':True}


@router.get('/api/research/topics/{tid}/opencode/sessions/{sid}')
async def session(tid: str,sid: str):
    rows=await call(_history,tid,sid)
    if not rows:raise HTTPException(404,'Historical session not found')
    return rows[0]


@router.post('/api/opencode/{path:path}')
@router.post('/api/research/topics/{tid}/opencode/{path:path}')
async def retired(path: str,tid: str=''):
    raise HTTPException(410,'Standalone OpenCode software is retired. No process was launched or history modified. Use native code tools.')
