#!/usr/bin/env python3
"""Differential check for the first Rust vertical slice.

This is intentionally separate from the full Simulator diff: the slice has a
small fixed contract (peashooter, ordinary zombie, one tick) while the full
Rust migration is still in progress.
"""
from __future__ import annotations
import argparse, json, subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

def python_reference(data):
    plant = {"id":"p1","type":"peashooter","row":3,"col":1,"hp":300,"cooldown":150,"state_timer":0,"layer":"main"}
    zombie = {"id":"z1","type":"normal","row":3,"col":2,"x":90.0,"hp":250,"helmet_hp":0,"shield_hp":0,"speed":0.143,"age":1,"chilled":0,"headless":False,"hypnotized":False,"tool":True,"underground":None,"status":"active"}
    return {"winner":"undecided","reason":"max_frames_reached","frames":1,"state":{"frame":1,"plants":[plant],"zombies":[zombie],"brains":[{"row":3,"hp":70}],"projectiles":[],"events":{"projectile_fired":1,"projectile_hit":1}}}

def main():
    ap=argparse.ArgumentParser(); ap.add_argument("scenario",type=Path); ap.add_argument("--rust-binary",type=Path,default=ROOT/"native_sim/target/release/pvz-ize-native-sim"); args=ap.parse_args()
    data=json.loads(args.scenario.read_text()); expected=python_reference(data)
    p=subprocess.run([str(args.rust_binary),"--slice","simple"],input=json.dumps(data),text=True,capture_output=True,check=False,cwd=ROOT)
    if p.returncode: raise SystemExit(f"Rust exited {p.returncode}: {p.stderr}")
    actual=json.loads(p.stdout)
    ok=actual==expected
    print(json.dumps({"status":"match" if ok else "mismatch","python":expected,"rust":actual},ensure_ascii=False,indent=2))
    return 0 if ok else 2
if __name__=="__main__": raise SystemExit(main())
