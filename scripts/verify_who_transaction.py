"""Rebuild the retained delivery roles against the original v0.3.1 snapshot."""

import difflib
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import sys
import tarfile
import tempfile


ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "outputs/who-will-win"


def sha(data):
    return hashlib.sha256(data).hexdigest()


def run(command, directory):
    result = subprocess.run(command, cwd=directory, capture_output=True, text=True)
    return {"command": command, "cwd": str(directory), "stdout": result.stdout,
            "stderr": result.stderr, "exit_status": result.returncode}


def main():
    previous = json.loads((OUT / "VERIFICATION.txt").read_text())
    previous_model = json.loads(previous["checks"]["MODIFIED"]["stdout"])["model"]
    (OUT / f"fidelity/VERIFICATION-{previous_model}.json").write_text(json.dumps(previous, indent=2) + "\n")
    existing = json.loads((OUT / "managed-files.json").read_text())
    additions = {"pvz_ize/plant_animation.py", "pvz_ize/plant_animation_tracks.json",
                 "scripts/build_plant_animation_tracks.py", "scripts/verify_who_transaction.py",
                 "tests/test_plant_animation.py", "tests/test_fidelity_v41.py",
                 "scripts/probe_pole_motion.py", "pvz_ize/editor.py", "docs/EDITOR.md",
                 "pvz_ize/web/index.html", "pvz_ize/web/app.js", "pvz_ize/web/style.css",
                 "tests/test_editor.py", "tests/test_jack_input.py", "examples/jack-timer.json",
                 "tests/test_pogo_fidelity.py", "tests/test_walk_restart.py",
                 "tests/test_collision_timing.py", "tests/test_projectile_selection.py",
                 "tests/test_torchwood_fidelity.py", "tests/test_rake.py", "tests/test_cob_cannon.py", "tests/test_phase_input.py", "pyproject.toml"} | {str(path.relative_to(ROOT)) for path in (ROOT / "pvz_ize/web/assets").glob("*.png")}
    baseline = {}
    with tarfile.open(OUT / "baseline.tar.gz") as archive:
        for member in archive.getmembers():
            if member.isfile():
                baseline[member.name] = archive.extractfile(member).read()
    names = sorted(set(baseline) | set(existing) | additions)
    current = {name: (ROOT / name).read_bytes() for name in names}
    changed = [name for name in names if baseline.get(name) != current[name]]
    managed = {name: {"baseline": sha(baseline[name]) if name in baseline else None,
                      "modified": sha(current[name])} for name in changed}
    (OUT / "managed-files.json").write_text(json.dumps(managed, indent=2) + "\n")
    patch_parts = []
    for name in changed:
        before, after = baseline.get(name, b""), current[name]
        try:
            patch_parts.append("".join(difflib.unified_diff(
                before.decode().splitlines(keepends=True), after.decode().splitlines(keepends=True),
                fromfile="a/" + name if name in baseline else "/dev/null", tofile="b/" + name)))
        except UnicodeDecodeError:
            patch_parts.append(f"Binary files differ: {name}\n")
    patch = "".join(patch_parts)
    (OUT / "DIFF_FILE.patch").write_text(patch)
    with tarfile.open(OUT / "MODIFIED_FILE.tar.gz", "w:gz") as archive:
        for name in names:
            archive.add(ROOT / name, arcname=name)

    command = [sys.executable, "-m", "pvz_ize", "predict", "P7|_|_|_|_|_|Z0|_|_",
               "--seed", "3", "--json"]
    pole_command = [sys.executable, "-c", """from tests.test_ground_special import Board, plant, unit
from pvz_ize import ground_special as ground
sim, z = Board([plant('tallnut')]), unit('pole_vaulting', x=198)
for tick in range(1, 402):
    ground.update(sim, z)
    if z.phase == 'pole_walking':
        print(tick, z.x)
        break
else:
    raise SystemExit('no landing observed')
"""]
    jack_command = [sys.executable, "-c", """from pvz_ize.model import parse_scenario
from pvz_ize.engine import Simulator
try:
    scenario = parse_scenario({'max_frames':200, 'zombies':[{'type':'jack_in_the_box','row':3,'x':600,'jack_countdown_frames':3}]})
except ValueError as error:
    import sys
    print(str(error), file=sys.stderr)
    raise SystemExit(1)
result = Simulator(scenario).run()
print(result['winner'], result['frames'], result['events'].get('jack_exploded', 0))
"""]
    mine_command = [sys.executable, "-c", """from pvz_ize.model import parse_scenario
from pvz_ize.engine import Simulator
for kind, x, tool in [('pole_vaulting', -10, False), ('pogo', 50, True)]:
    sim = Simulator(parse_scenario({'plants':[{'type':'potato_mine','row':3,'col':1}],
        'zombies':[{'type':kind,'row':3,'x':x,'tool':tool}]}))
    sim.special(sim.plants[0])
    print(kind, sim.plants[0].hp, sim.zombies[0].hp)
"""]
    pogo_command = [sys.executable, "-c", """from pvz_ize.model import parse_scenario
from pvz_ize.engine import Simulator
from pvz_ize import extended_zombies as ext
sim = Simulator(parse_scenario({'plants':[{'type':'tallnut','row':3,'col':1}],
    'zombies':[{'type':'pogo','row':3,'x':100}]}))
z = sim.zombies[0]
ext._state(sim, z).update(pogo_stage='forward', pogo_velocity=1)
z.phase_timer = 71
sim.update_zombie(z)
print(z.tool, z.phase, sim.plants[0].hp)
"""]
    walk_command = [sys.executable, "-c", """from pvz_ize.model import parse_scenario
from pvz_ize.engine import Simulator
class Draws:
    def __init__(self): self.calls = []
    def uniform(self, a, b):
        self.calls.append('speed')
        return (a + b) / 2
    def randrange(self, n):
        self.calls.append('variant')
        return 1
for hypnotized in (False, True):
    sim = Simulator(parse_scenario({'movement_mode':'animation', 'seed':201,
        'zombies':[{'type':'conehead','row':3,'x':600,'hypnotized':hypnotized}]}))
    z = sim.zombies[0]
    z.eating, z.age, z.animation_phase = True, 3, .6
    sim.rng = Draws()
    sim.update_zombie(z)
    print('hypnotized', hypnotized, 'stopped', not z.eating, 'moved', z.x != 600,
          'reset_and_advanced', 0 < z.animation_phase < .1, 'draws', sim.rng.calls)
"""]
    collision_command = [sys.executable, "-c", """from pvz_ize.model import parse_scenario
from pvz_ize.engine import Simulator, Projectile
for kind, x, shot_x in [('puff',300,295.9),('fire',200,205)]:
    sim = Simulator(parse_scenario({'zombies':[{'type':'normal','row':3,'x':x}]}))
    sim.update_projectile(Projectile('q','p',3,shot_x,kind))
    print(kind, sim.zombies[0].hp)
sim = Simulator(parse_scenario({'plants':[{'type':'wallnut','row':3,'col':4}],
    'zombies':[{'type':'normal','row':3,'x':281.1,'speed':.2,'age':3}]}))
sim.update_zombie(sim.zombies[0])
print('bite', sim.zombies[0].eating, sim.plants[0].hp)
sim = Simulator(parse_scenario({'plants':[{'type':'spikeweed','row':3,'col':2}],
    'zombies':[{'type':'catapult','row':3,'x':100}]}))
p,z = sim.plants[0],sim.zombies[0]
p.state,p.state_timer = 'attacking',75
z.phase,z.phase_timer = 'catapult_launching',100
sim.special(p)
print('spike', p.hp, z.hp, z.status)
sim = Simulator(parse_scenario({'zombies':[{'type':'pogo','row':3,'x':0,'tool':False,'age':4}]}))
sim.chew(sim.zombies[0])
print('pogo_brain', sim.brains[0].hp)
"""]
    selection_command = [sys.executable, "-c", """from pvz_ize.model import parse_scenario
from pvz_ize.engine import Simulator, Projectile
for direction in (1, -1):
    sim = Simulator(parse_scenario({'zombies':[
        {'id':'normal','type':'normal','row':3,'x':200},
        {'id':'giant','type':'gargantuar','row':3,'x':220}]}))
    sim.update_projectile(Projectile('q','p',3,200,'pea',direction))
    print('order', direction, [(z.id,z.hp) for z in sim.zombies])
for kind, motion in [('star','star'),('kernel','lob'),('cabbage','lob'),
                     ('melon','lob'),('cactus_spike','straight')]:
    sim = Simulator(parse_scenario({'zombies':[{'type':'normal','row':3,'x':300}]}))
    q = Projectile('q','p',3,255.9 if kind=='melon' else 295.9,kind,
                   vx=3.33,vy=0,y=310,motion=motion,z=1)
    sim.update_projectile(q)
    print(kind, sim.zombies[0].hp, q.active)
"""]
    torch_command = [sys.executable, "-c", """from pvz_ize.engine import Simulator, Projectile
from pvz_ize.model import parse_scenario
for x in (20.9, 21):
    sim = Simulator(parse_scenario({'plants':[{'type':'torchwood','row':3,'col':1}],
        'zombies':[{'type':'normal','row':3,'x':0}]}))
    q = Projectile('q','p',3,x,'pea')
    sim.update_projectile(q)
    print('clip', x, sim.zombies[0].hp, q.active)
for direction, x in [(-1,75),(1,59.9),(1,60),(1,125.9)]:
    sim = Simulator(parse_scenario({'plants':[{'type':'torchwood','row':3,'col':1}]}))
    q = Projectile('q','p',3,x,'pea',direction)
    sim.projectiles.append(q)
    sim.update_plant(sim.plants[0])
    print('convert', direction, x, q.kind, q.last_torch)
"""]
    ledger = {"input": "nine-cell formation, seed 3", "changed_sites": changed,
              "checks": {}, "baseline_hashes": {name: sha(data) for name, data in baseline.items()}}
    with tempfile.TemporaryDirectory(prefix="pvz-transaction-") as tmp:
        base, modified, restored = [Path(tmp) / name for name in ("baseline", "modified", "rollback")]
        for name, data in baseline.items():
            path = base / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(data)
        shutil.copytree(base, modified)
        # Binary UI assets are copied into the verification checkout; unified patch
        # format intentionally records them as binary-difference markers.
        for name, data in current.items():
            if name.endswith(".png"):
                path = modified / name
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_bytes(data)
        ledger["checks"]["BASELINE"] = run(command, base)
        ledger["checks"]["POLE_BASELINE"] = run(pole_command, base)
        ledger["checks"]["JACK_BASELINE"] = run(jack_command, base)
        ledger["checks"]["MINE_BASELINE"] = run(mine_command, base)
        ledger["checks"]["POGO_BASELINE"] = run(pogo_command, base)
        ledger["checks"]["WALK_BASELINE"] = run(walk_command, base)
        ledger["checks"]["COLLISION_BASELINE"] = run(collision_command, base)
        ledger["checks"]["SELECTION_BASELINE"] = run(selection_command, base)
        ledger["checks"]["TORCH_BASELINE"] = run(torch_command, base)
        ledger["checks"]["PATCH"] = run(["patch", "-p1", "-i", str(OUT / "DIFF_FILE.patch")], modified)
        assert ledger["checks"]["PATCH"]["exit_status"] == 0
        assert all((modified / name).read_bytes() == data for name, data in current.items())
        ledger["checks"]["MODIFIED"] = run(command, modified)
        ledger["checks"]["POLE_MODIFIED"] = run(pole_command, modified)
        ledger["checks"]["JACK_MODIFIED"] = run(jack_command, modified)
        ledger["checks"]["MINE_MODIFIED"] = run(mine_command, modified)
        ledger["checks"]["POGO_MODIFIED"] = run(pogo_command, modified)
        ledger["checks"]["WALK_MODIFIED"] = run(walk_command, modified)
        ledger["checks"]["COLLISION_MODIFIED"] = run(collision_command, modified)
        ledger["checks"]["SELECTION_MODIFIED"] = run(selection_command, modified)
        ledger["checks"]["TORCH_MODIFIED"] = run(torch_command, modified)
        assert ledger["checks"]["TORCH_MODIFIED"]["stdout"] == (
            "clip 20.9 250 False\nclip 21 270 True\nconvert -1 75 fire 1\n"
            "convert 1 59.9 pea -1\nconvert 1 60 fire 1\nconvert 1 125.9 fire 1\n")
        assert ledger["checks"]["SELECTION_MODIFIED"]["stdout"] == (
            "order 1 [('normal', 250), ('giant', 3000)]\n"
            "order -1 [('normal', 250), ('giant', 3000)]\n"
            "star 270 True\nkernel 270 True\ncabbage 270 True\nmelon 270 True\ncactus_spike 270 True\n")
        assert ledger["checks"]["COLLISION_MODIFIED"]["stdout"] == (
            "puff 270\nfire 270\nbite False 4000\nspike 0 0 dead\npogo_brain 69\n")
        assert ledger["checks"]["WALK_MODIFIED"]["stdout"] == (
            "hypnotized False stopped True moved False reset_and_advanced True draws ['speed', 'variant']\n"
            "hypnotized True stopped True moved False reset_and_advanced True draws ['speed', 'variant']\n")
        assert ledger["checks"]["POGO_MODIFIED"]["stdout"] == "False pogo_walking 8000\n"
        assert ledger["checks"]["MINE_MODIFIED"]["stdout"] == "pole_vaulting 300 500\npogo 300 500\n"
        assert ledger["checks"]["JACK_MODIFIED"]["stdout"] == "plants 113 1\n"
        assert ledger["checks"]["MODIFIED"]["exit_status"] == 0
        shutil.copytree(modified, restored)
        ledger["checks"]["ROLLBACK_SCRIPT"] = run([str(OUT / "ROLLBACK.sh"), str(restored)], ROOT)
        assert ledger["checks"]["ROLLBACK_SCRIPT"]["exit_status"] == 0
        assert all((restored / name).read_bytes() == data for name, data in baseline.items())
        assert all(not (restored / name).exists() for name in set(current) - set(baseline))
        ledger["checks"]["ROLLBACK"] = run(command, restored)
        ledger["checks"]["POLE_ROLLBACK"] = run(pole_command, restored)
        ledger["checks"]["JACK_ROLLBACK"] = run(jack_command, restored)
        ledger["checks"]["MINE_ROLLBACK"] = run(mine_command, restored)
        ledger["checks"]["POGO_ROLLBACK"] = run(pogo_command, restored)
        ledger["checks"]["WALK_ROLLBACK"] = run(walk_command, restored)
        ledger["checks"]["COLLISION_ROLLBACK"] = run(collision_command, restored)
        ledger["checks"]["SELECTION_ROLLBACK"] = run(selection_command, restored)
        ledger["checks"]["TORCH_ROLLBACK"] = run(torch_command, restored)
        for key in ("stdout", "stderr", "exit_status"):
            assert ledger["checks"]["JACK_BASELINE"][key] == ledger["checks"]["JACK_ROLLBACK"][key]
            assert ledger["checks"]["MINE_BASELINE"][key] == ledger["checks"]["MINE_ROLLBACK"][key]
            assert ledger["checks"]["POGO_BASELINE"][key] == ledger["checks"]["POGO_ROLLBACK"][key]
            assert ledger["checks"]["WALK_BASELINE"][key] == ledger["checks"]["WALK_ROLLBACK"][key]
            assert ledger["checks"]["COLLISION_BASELINE"][key] == ledger["checks"]["COLLISION_ROLLBACK"][key]
            assert ledger["checks"]["SELECTION_BASELINE"][key] == ledger["checks"]["SELECTION_ROLLBACK"][key]
            assert ledger["checks"]["TORCH_BASELINE"][key] == ledger["checks"]["TORCH_ROLLBACK"][key]
        assert all(ledger["checks"]["TORCH_" + label]["exit_status"] == 0
                   for label in ("BASELINE", "MODIFIED", "ROLLBACK"))
        assert all(ledger["checks"]["SELECTION_" + label]["exit_status"] == 0
                   for label in ("BASELINE", "MODIFIED", "ROLLBACK"))
        assert all(ledger["checks"]["COLLISION_" + label]["exit_status"] == 0
                   for label in ("BASELINE", "MODIFIED", "ROLLBACK"))
        assert all(ledger["checks"]["WALK_" + label]["exit_status"] == 0
                   for label in ("BASELINE", "MODIFIED", "ROLLBACK"))
        assert all(ledger["checks"][label]["exit_status"] == 0
                   for label in ("MINE_BASELINE", "MINE_MODIFIED", "MINE_ROLLBACK"))
        assert all(ledger["checks"][label]["exit_status"] == 0
                   for label in ("POGO_BASELINE", "POGO_MODIFIED", "POGO_ROLLBACK"))
        assert all(ledger["checks"][label]["exit_status"] == 0
                   for label in ("POLE_BASELINE", "POLE_MODIFIED", "POLE_ROLLBACK"))
        assert ledger["checks"]["POLE_BASELINE"]["stdout"] == ledger["checks"]["POLE_ROLLBACK"]["stdout"]
        for field in ("stdout", "stderr", "exit_status"):
            assert ledger["checks"]["BASELINE"][field] == ledger["checks"]["ROLLBACK"][field]
        ledger["restored_hashes_equal_baseline"] = True
        ledger["checks"]["REAPPLY"] = run(["patch", "-p1", "-i", str(OUT / "DIFF_FILE.patch")], restored)
        assert ledger["checks"]["REAPPLY"]["exit_status"] == 0
        for name, data in current.items():
            if name.endswith(".png"):
                path = restored / name
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_bytes(data)
        assert all((restored / name).read_bytes() == data for name, data in current.items())
        ledger["reapplied_patch_matches_modified"] = True
    ledger["tests"] = (OUT / "tests.txt").read_text()
    ledger["preset_results"] = json.loads((OUT / "preset-results.json").read_text())["counts"]
    ledger["replay"] = json.loads((OUT / "nonboss/replay-check.json").read_text())
    ledger["nonboss_audit"] = json.loads((OUT / "nonboss/audit.json").read_text())
    ledger["potato_trigger"] = {"before": json.loads((OUT / "potato/before.json").read_text()),
                                 "after": json.loads((OUT / "potato/after.json").read_text()),
                                 "static_evidence": str(OUT / "nonboss/mine-static")}
    ledger["pogo_static_evidence"] = str(OUT / "nonboss/pogo-static")
    ledger["walk_restart_evidence"] = str(OUT / "lineup5-sweep/static/REPORT.md")
    ledger["walk_restart_results"] = json.loads((OUT / "walk-restart/results.json").read_text())
    ledger["collision_evidence"] = str(OUT / "puff-spike-static")
    ledger["collision_results"] = json.loads((OUT / "projectile-v54/results.json").read_text())
    ledger["projectile_selection_evidence"] = str(OUT / "projectile-v55/static")
    ledger["projectile_selection_results"] = json.loads((OUT / "projectile-v55/results.json").read_text())
    ledger["torch_evidence"] = str(OUT / "torch-v56/static")
    ledger["torch_results"] = json.loads((OUT / "torch-v56/results.json").read_text())
    ledger["pogo_preset_before_after"] = json.loads((OUT / "pogo/preset-before-after.json").read_text())
    ledger["artifacts"] = {}
    for name in ("MODIFIED_FILE.tar.gz", "DIFF_FILE.patch", "ROLLBACK.sh", "baseline.tar.gz", "managed-files.json"):
        path = OUT / name
        data = path.read_bytes()
        ledger["artifacts"][name] = {"path": str(path), "sha256": sha(data), "bytes": len(data)}
    ledger["corrected_errors"] = previous.get("corrected_errors", [])
    (OUT / "VERIFICATION.txt").write_text(json.dumps(ledger, ensure_ascii=False, indent=2) + "\n")
    # Reopen and parse all four roles, rather than relying on successful writes.
    with tarfile.open(OUT / "MODIFIED_FILE.tar.gz") as archive:
        assert all(archive.extractfile(name).read() == current[name] for name in names)
    assert (OUT / "DIFF_FILE.patch").read_text() == patch
    assert json.loads((OUT / "VERIFICATION.txt").read_text())["restored_hashes_equal_baseline"]
    assert (OUT / "ROLLBACK.sh").read_text().startswith("#!/bin/sh\n")
    assert (OUT / "ROLLBACK.sh").stat().st_mode & 0o111
    for name in ("MODIFIED_FILE.tar.gz", "DIFF_FILE.patch", "VERIFICATION.txt", "ROLLBACK.sh"):
        path = OUT / name
        data = path.read_bytes()
        print(path, sha(data), len(data))
    for label in ("BASELINE", "MODIFIED", "ROLLBACK"):
        result = ledger["checks"][label]
        print(label, "exit", result["exit_status"])
        if result["exit_status"] == 0:
            value = json.loads(result["stdout"])
            print(value["winner"], value["frames"], value["reason"])
        else:
            print(result["stderr"], end="")
    for label in ("POLE_BASELINE", "POLE_MODIFIED", "POLE_ROLLBACK"):
        result = ledger["checks"][label]
        print(label, "exit", result["exit_status"], result["stdout"].strip())
    for label in ("JACK_BASELINE", "JACK_MODIFIED", "JACK_ROLLBACK"):
        result = ledger["checks"][label]
        print(label, "exit", result["exit_status"], (result["stdout"] or result["stderr"]).strip())
    for label in ("MINE_BASELINE", "MINE_MODIFIED", "MINE_ROLLBACK"):
        result = ledger["checks"][label]
        print(label, "exit", result["exit_status"], result["stdout"].strip())
    for label in ("POGO_BASELINE", "POGO_MODIFIED", "POGO_ROLLBACK"):
        result = ledger["checks"][label]
        print(label, "exit", result["exit_status"], result["stdout"].strip())
    for label in ("WALK_BASELINE", "WALK_MODIFIED", "WALK_ROLLBACK"):
        result = ledger["checks"][label]
        print(label, "exit", result["exit_status"], result["stdout"].strip())
    for label in ("COLLISION_BASELINE", "COLLISION_MODIFIED", "COLLISION_ROLLBACK"):
        result = ledger["checks"][label]
        print(label, "exit", result["exit_status"], result["stdout"].strip())
    for label in ("SELECTION_BASELINE", "SELECTION_MODIFIED", "SELECTION_ROLLBACK"):
        result = ledger["checks"][label]
        print(label, "exit", result["exit_status"], result["stdout"].strip())
    for label in ("TORCH_BASELINE", "TORCH_MODIFIED", "TORCH_ROLLBACK"):
        result = ledger["checks"][label]
        print(label, "exit", result["exit_status"], result["stdout"].strip())


if __name__ == "__main__":
    main()
