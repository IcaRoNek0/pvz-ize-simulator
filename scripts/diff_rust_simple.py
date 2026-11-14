#!/usr/bin/env python3
"""Differential check for the first Rust vertical slice.

The reference here is deliberately the small fixed-tick contract, not the full
Python Simulator: peashooter, ordinary zombie, straight projectile, bite and
brain terminal.  The full engine remains the fidelity oracle until each module
is ported.
"""
from __future__ import annotations
import argparse, json, subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
FP = 1000

def python_reference(data):
    plants=[]
    for i,p in enumerate(data.get("plants", [])):
        col=int(p.get("col",1)); kind=p.get("type","peashooter")
        if kind == "cob_cannon" and col >= 9:
            raise ValueError("cob_cannon left column must be 1..8")
        default_hp={"wallnut":4000,"tallnut":8000,"spikerock":450}.get(kind,300)
        plants.append({"id":p.get("id",f"p{i+1}"),"type":kind,"row":int(p.get("row",3)),"col":col,"footprint":[col,col+1] if kind=="cob_cannon" else [col],"hp":int(p.get("hp",default_hp)),"cooldown":int(p.get("cooldown",0)),"state_timer":int(p.get("state_timer",0)),"layer":p.get("layer","main")})
    zombies=[]
    for i,z in enumerate(data.get("zombies", [])):
        kind=z.get("type","normal"); col=z.get("col")
        x=float(z["x"]) if "x" in z else 10.0+80.0*(int(col)-1)
        default_hp = 500 if kind == "ladder" else 270
        default_helmet = 100 if kind == "digger" else 0
        default_shield = 500 if kind == "ladder" else 0
        zombies.append({"id":z.get("id",f"z{i+1}"),"type":kind,"row":int(z.get("row",3)),"col":int(round((x-10.0)/80.0))+1,"x":x,"x_fp":int(round(x*FP)),"hp":int(z.get("hp",default_hp)),"helmet_hp":int(z.get("helmet_hp",default_helmet)),"shield_hp":int(z.get("shield_hp",default_shield)),"speed":float(z.get("speed",0.143)),"age":int(z.get("age",0)),"chilled":int(z.get("chilled",0)),"headless":bool(z.get("headless",False)),"hypnotized":bool(z.get("hypnotized",False)),"tool":bool(z.get("tool",True)),"underground":z.get("underground") if isinstance(z.get("underground"),bool) else None,"status":"active"})
    brains=[]
    for b in data.get("brains",[3]): brains.append({"row":int(b if isinstance(b,int) else b["row"]),"hp":70 if isinstance(b,int) else int(b.get("hp",70))})
    mode = str(data.get("mode", "ize"))
    rakes=[{"row":int(r["row"]),"col":int(r["col"])} for r in data.get("rakes",[])]
    ladders=[{"row":int(l["row"]),"col":int(l["col"])} for l in data.get("ladders",[])]
    projectiles=[]; events={}; frame=0
    def ev(name,n=1): events[name]=events.get(name,0)+n
    def terminal():
        if all(b["hp"]<=0 for b in brains): return ("zombies","all_brains_eaten")
        if mode == "who_will_win":
            if not any(z["status"]=="active" and z["hp"]>0 and z["row"]==3
                       and not z["hypnotized"] and not z["headless"] for z in zombies):
                return ("plants", "no_row_3_threats")
            return None
        if not any(z["status"]=="active" and z["hp"]>0 and not z["hypnotized"] for z in zombies): return ("plants","no_on_board_zombies")
    max_frames=int(data.get("max_frames",100000))
    squash_hits=0; potato_kills=0; potato_explosions=0; cherry_kills=0; cherry_explosions=0; jalapeno_kills=0; jalapeno_explosions=0
    spikeweed_pulses=0; spikerock_pulses=0; hazard_kills=0; hazard_damage=0
    result=terminal()
    while result is None and frame<max_frames:
        frame+=1
        squash_hits=0
        potato_kills=0; potato_explosions=0; cherry_kills=0; cherry_explosions=0; jalapeno_kills=0; jalapeno_explosions=0
        spikeweed_pulses=0; spikerock_pulses=0; hazard_kills=0; hazard_damage=0
        for p in plants:
            if p["hp"]<=0 or p["type"]!="cherry_bomb": continue
            if p["state_timer"]==0: p["state_timer"]=100
            p["state_timer"]-=1
            if p["state_timer"]==0:
                px_fp=int(round((40.0+80.0*(p["col"]-1))*FP))
                for z in zombies:
                    if z["status"]=="active" and z["hp"]>0 and not z["hypnotized"] and abs(z["row"]-p["row"])<=1 and abs(z["x_fp"]-px_fp)<=115000:
                        z["hp"]=0; z["status"]="dead"; cherry_kills+=1
                p["hp"]=0; cherry_explosions+=1
        for p in plants:
            if p["hp"]<=0 or p["type"]!="jalapeno": continue
            if p["state_timer"]==0: p["state_timer"]=100
            p["state_timer"]-=1
            if p["state_timer"]==0:
                row=p["row"]
                for z in zombies:
                    if z["status"]=="active" and z["hp"]>0 and not z["hypnotized"] and z["row"]==row:
                        z["hp"]=0; z["status"]="dead"; jalapeno_kills+=1
                ladders=[ladder for ladder in ladders if ladder["row"]!=row]
                p["hp"]=0; jalapeno_explosions+=1
        for p in plants:
            if p["hp"]<=0 or p["type"]!="potato_mine": continue
            px_fp=int(round((40.0+80.0*(p["col"]-1))*FP))
            triggered=any(z["status"]=="active" and z["hp"]>0 and not z["hypnotized"]
                          and z["row"]==p["row"] and z["x_fp"]>=px_fp and z["x_fp"]-px_fp<=55000
                          for z in zombies)
            if triggered:
                for z in zombies:
                    if z["status"]=="active" and z["hp"]>0 and not z["hypnotized"] and z["row"]==p["row"]:
                        z["hp"]=0; z["status"]="dead"; potato_kills+=1
                p["hp"]=0; potato_explosions+=1
        # Ground spikes arm on overlap, pulse on their native wind-up timers,
        # and are never selected as zombie bite targets.  The Python oracle's
        # bypass damage ignores shields but still consumes helmet armor.
        for p in plants:
            if p["hp"]<=0 or p["type"] not in ("spikeweed", "spikerock"): continue
            px_fp=int(round((40+80*(p["col"]-1))*FP)); row=p["row"]
            def in_range(z, strict=False):
                return (z["status"]=="active" and z["hp"]>0 and not z["hypnotized"]
                        and z["row"]==row
                        and ((z["x_fp"]+36000 < px_fp+50000 and z["x_fp"]+78000 > px_fp+20000)
                             if strict else
                             (z["x_fp"]+36000 <= px_fp+50000 and z["x_fp"]+78000 >= px_fp+20000)))
            if p["state_timer"] == 0:
                if any(in_range(z, False) for z in zombies): p["state_timer"] = 100
                continue
            p["state_timer"] -= 1
            pulse = (p["type"] == "spikeweed" and p["state_timer"] == 75) or \
                    (p["type"] == "spikerock" and p["state_timer"] in (70, 32))
            if pulse:
                hit = False
                for z in zombies:
                    if not in_range(z, True): continue
                    hit = True
                    hazard_damage += 1
                    remaining = max(0, 20)
                    if z["helmet_hp"] > 0:
                        absorbed = min(z["helmet_hp"], remaining)
                        z["helmet_hp"] -= absorbed; remaining -= absorbed
                    z["hp"] = max(0, z["hp"] - remaining)
                    if z["hp"] == 0:
                        z["status"] = "dead"; hazard_kills += 1
                if hit:
                    if p["type"] == "spikeweed": spikeweed_pulses += 1
                    else: spikerock_pulses += 1
        for p in plants:
            if p["hp"]<=0 or p["type"]!="squash": continue
            px_fp=int(round((40.0+80.0*(p["col"]-1))*FP))
            for z in zombies:
                if z["status"]=="active" and z["hp"]>0 and not z["hypnotized"] and z["row"]==p["row"] and z["x_fp"]>=px_fp and z["x_fp"]-px_fp<=120000:
                    z["hp"]=0; z["status"]="dead"; p["hp"]=0; squash_hits+=1; break
        for p in plants:
            if p["hp"]<=0 or p["type"] not in ("peashooter","snow_pea","repeater"): continue
            if p["cooldown"]>0: p["cooldown"]-=1
            if p["cooldown"]==0:
                px=40.0+80.0*(p["col"]-1); shots=2 if p["type"]=="repeater" else 1
                for _ in range(shots): projectiles.append({"row":p["row"],"kind":"ice" if p["type"]=="snow_pea" else "pea","x_fp":int(round((px+50)*FP)),"x":px+50,"damage":20,"active":True})
                p["cooldown"]=150; ev("projectile_fired",shots)
        for q in projectiles:
            if q["active"]: q["x_fp"]+=8000; q["x"]=q["x_fp"]/FP
        for q in projectiles:
            if not q["active"]: continue
            for z in zombies:
                if z["status"]=="active" and z["hp"]>0 and z["row"]==q["row"] and abs(z["x_fp"]-q["x_fp"])<=25000:
                    remaining = max(0, q["damage"])
                    # The normal Simulator damage path strips shield, then
                    # helmet, before applying damage to body HP.
                    if z["shield_hp"] > 0 and remaining:
                        absorbed = min(z["shield_hp"], remaining)
                        z["shield_hp"] -= absorbed; remaining -= absorbed
                        if z["shield_hp"] == 0: ev("armor_lost")
                    if z["helmet_hp"] > 0 and remaining:
                        absorbed = min(z["helmet_hp"], remaining)
                        z["helmet_hp"] -= absorbed; remaining -= absorbed
                        if z["helmet_hp"] == 0: ev("armor_lost")
                    z["hp"] = max(0, z["hp"]-remaining); q["active"]=False; ev("projectile_hit")
                    if q["kind"]=="ice": z["chilled"]=300; ev("chill_applied")
                    if z["hp"]==0: z["status"]="dead"; ev("zombie_died")
                    break
        projectiles=[q for q in projectiles if q["active"] and q["x_fp"]<900000]
        for z in zombies:
            if z["status"]!="active" or z["hp"]<=0: continue
            z["age"]+=1
            if z["chilled"]>0: z["chilled"]-=1
            if z["hypnotized"]:
                # Charmed zombies are friendly: walk right and leave the
                # board, without biting plants/brains.  Friendly-vs-hostile
                # combat is intentionally deferred to the social-special
                # migration slice.
                z["x_fp"] += max(1, int(round(z["speed"]*FP)))
                z["x"] = z["x_fp"]/FP
                if z["x_fp"] > 850000:
                    z["status"] = "exited"; ev("zombie_exited")
                continue
            if z.get("underground") is True:
                if z["age"]>=2: z["underground"]=False; ev("digger_emerged")
                continue
            if z["type"]=="ladder" and z["tool"] and z["shield_hp"]==0:
                z["tool"]=False
            if z["type"]=="ladder" and z["tool"] and z["shield_hp"]>0:
                target=next((p for p in plants if p["hp"]>0 and p["type"] in ("wallnut","tallnut") and p["row"]==z["row"] and int(round((40+80*(p["col"]-1))*FP))-60000<=z["x_fp"]<=int(round((40+80*(p["col"]-1))*FP))+70000 and not any(l["row"]==p["row"] and l["col"]==p["col"] for l in ladders)),None)
                if target is not None:
                    ladders.append({"row":target["row"],"col":target["col"]}); z["tool"]=False; z["shield_hp"]=0; ev("ladder_placed"); continue
            zx_fp=z["x_fp"]; row=z["row"]
            target=next((p for p in plants if p["hp"]>0 and p["type"] not in ("spikeweed", "spikerock") and p["row"]==row and not any(l["row"]==p["row"] and l["col"]==p["col"] for l in ladders) and zx_fp>=int(round((40+80*(p["col"]-1))*FP)) and zx_fp-int(round((40+80*(p["col"]-1))*FP))<=60000),None)
            if target is not None:
                if z["age"]%4==0: target["hp"]=max(0,target["hp"]-4); ev("plant_bitten")
            else:
                speed_fp=max(1,int(round(z["speed"]*FP))) if z["chilled"]==0 else max(1,int(round(z["speed"]*FP))//2)
                z["x_fp"]-=speed_fp; z["x"]=z["x_fp"]/FP
                if z["x_fp"]<=20000:
                    z["status"]="entered_house"
                    brain=next((b for b in brains if b["row"]==row and b["hp"]>0),None)
                    if brain is not None: brain["hp"]=0; ev("brain_eaten")
        result=terminal()
        rake_hits=0
        remaining_rakes=[]
        for rake in rakes:
            rx_fp=int(round((40.0+80.0*(rake["col"]-1))*FP))
            target=next((z for z in zombies if z["status"]=="active" and z["hp"]>0 and not z["hypnotized"] and z["row"]==rake["row"] and rx_fp-60000<=z["x_fp"]<=rx_fp+63000),None)
            if target is None:
                remaining_rakes.append(rake)
            else:
                target["hp"]=0; target["status"]="dead"; rake_hits+=1; ev("rake_triggered"); ev("zombie_died")
        rakes=remaining_rakes
        result=terminal()
    if result is None: winner,reason="undecided","max_frames_reached"
    else: winner,reason=result
    if potato_explosions: ev("explosion", potato_explosions)
    if cherry_explosions: ev("explosion", cherry_explosions)
    if jalapeno_explosions: ev("explosion", jalapeno_explosions)
    if spikeweed_pulses: ev("spikeweed_pulse", spikeweed_pulses)
    if spikerock_pulses: ev("spikerock_pulse", spikerock_pulses)
    if hazard_damage: ev("damage", hazard_damage)
    if squash_hits:
        ev("squash_impact", squash_hits)
    if squash_hits or potato_kills or cherry_kills or jalapeno_kills or hazard_kills:
        ev("zombie_died", squash_hits + potato_kills + cherry_kills + jalapeno_kills + hazard_kills)
    public_zombies=[{k:v for k,v in z.items() if k!="x_fp"} for z in zombies]
    return {"winner":winner,"reason":reason,"frames":frame,"state":{"frame":frame,"mode":mode,"plants":plants,"zombies":public_zombies,"brains":brains,"projectiles":[{k:v for k,v in q.items() if k!="x_fp"} for q in projectiles],"events":events,"rakes":rakes,"ladders":ladders}}

def main():
    ap=argparse.ArgumentParser(); ap.add_argument("scenarios",nargs="+",type=Path); ap.add_argument("--rust-binary",type=Path,default=ROOT/"native_sim/target/release/pvz-ize-native-sim"); args=ap.parse_args()
    failed=False
    for path in args.scenarios:
        data=json.loads(path.read_text()); expected=python_reference(data)
        p=subprocess.run([str(args.rust_binary),"--slice","simple"],input=json.dumps(data),text=True,capture_output=True,check=False,cwd=ROOT)
        if p.returncode: raise SystemExit(f"Rust exited {p.returncode}: {p.stderr}")
        actual=json.loads(p.stdout); ok=actual==expected; failed|=not ok
        print(json.dumps({"scenario":str(path),"status":"match" if ok else "mismatch","python":expected,"rust":actual},ensure_ascii=False,indent=2))
    return 2 if failed else 0
if __name__=="__main__": raise SystemExit(main())
