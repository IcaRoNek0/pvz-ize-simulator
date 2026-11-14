#!/usr/bin/env python3
"""Compare serial and process-parallel batch throughput.

Usage: python3 scripts/benchmark_batch.py examples/v2_random.json --runs 100 --workers 4
"""
from __future__ import annotations
import argparse, json, time
from pathlib import Path
from pvz_ize.batch import run_batch, run_batch_parallel

def main():
    ap=argparse.ArgumentParser(); ap.add_argument('scenario',type=Path); ap.add_argument('--runs',type=int,default=100); ap.add_argument('--workers',type=int,default=2); a=ap.parse_args()
    data=json.loads(a.scenario.read_text()); data['runs']=a.runs
    rows=[]
    for label, fn in [('serial',run_batch),('parallel',lambda x:run_batch_parallel(x,a.workers))]:
      t=time.perf_counter(); out=fn(data); elapsed=time.perf_counter()-t
      rows.append({'mode':label,'seconds':elapsed,'runs':a.runs,'runs_per_second':a.runs/elapsed,'outcomes':out['outcomes'],'parallel_workers':out.get('parallel_workers',1)})
    print(json.dumps({'benchmark':rows},ensure_ascii=False,indent=2))
if __name__=='__main__': main()
