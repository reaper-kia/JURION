"""Explicit corpus evaluation; --real-model also saves generated answers locally."""
import argparse
import csv
from dataclasses import asdict
import json
from pathlib import Path
import time
from legal_qa.context import parse_context
from legal_qa.corpus import build_snapshot
from legal_qa.evidence import retrieve
from legal_qa.answer import answer, ProxyGenerator
from solution import history

p=argparse.ArgumentParser()
p.add_argument('--corpus',required=True,type=Path)
p.add_argument('--questions',required=True,type=Path)
p.add_argument('--output',required=True,type=Path)
p.add_argument('--real-model',action='store_true')
a=p.parse_args()
start=time.monotonic(); manifest,_=build_snapshot(a.corpus); build_time=time.monotonic()-start
with a.questions.open(encoding='utf-8-sig',newline='') as f: rows=list(csv.DictReader(f))
results=[];start=time.monotonic()
for row in rows:
    messages=history(row['question']); context=parse_context(messages)
    evidence,missing=retrieve(manifest,context,messages)
    result={'id':row['id'],'sources':list(dict.fromkeys(e['source'] for e in evidence)), 'missing':missing}
    if a.real_model:
        t=time.monotonic()
        try: result['answer']=asdict(answer(manifest,messages,ProxyGenerator.from_env(),deadline=t+90))
        except Exception as exc: result['error']=type(exc).__name__
        result['duration_seconds']=time.monotonic()-t
    results.append(result)
a.output.write_text(json.dumps({'files':len(manifest['files']),'rows':len(rows),'mode':'real-model' if a.real_model else 'retrieval-only','build_seconds':build_time,'batch_seconds':time.monotonic()-start,'results':results},ensure_ascii=False,indent=2))
print(a.output)
