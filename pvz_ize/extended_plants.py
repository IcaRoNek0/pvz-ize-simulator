"""Additional PvZ plants; source-backed timings with explicit geometric approximations.

All hooks return True when they handled the update. No hidden global state is used.
"""

import math
from . import plant_animation


# hp, launch period, first release delay (centiseconds).
SPECS = {
    "cactus": (300, 150, 34), "cattail": (300, 150, 31),
    "gatling_pea": (300, 150, 32), "cabbage_pult": (300, 300, 31),
    "melon_pult": (300, 300, 35), "winter_melon": (300, 300, 35),
    "gloom_shroom": (300, 200, 74), "garlic": (400, 0, 0),
    "cherry_bomb": (300, 0, 0), "jalapeno": (300, 0, 0),
    "ice_shroom": (300, 0, 0), "doom_shroom": (300, 0, 0),
    "hypno_shroom": (300, 0, 0), "pumpkin": (4000, 0, 0),
    "lily_pad": (300, 0, 0), "flower_pot": (300, 0, 0),
    "spikerock": (450, 100, 0), "blover": (300, 0, 0),
    # Native COB cannon: 500-frame arming, then a 3000-frame reload after
    # each manually targeted shot.  The simulator auto-targets the nearest
    # live zombie because it has no mouse-input stream.
    "cob_cannon": (300, 3000, 500),
}
INSTANTS = {"cherry_bomb", "jalapeno", "ice_shroom", "doom_shroom"}
LOBS = {"cabbage_pult": "cabbage", "melon_pult": "melon",
        "winter_melon": "winter_melon"}
EXTENDED_PROJECTILES = {"cactus_spike", "cattail_spike", *LOBS.values()}
YUCKY_FACE = {"normal", "conehead", "buckethead", "flag", "screen_door",
              "ducky_tube", "dancing", "backup_dancer", "newspaper", "pole_vaulting"}


def _flying(z):
    return z.type == "balloon" and z.phase in {"balloon_flying", "balloon_popping"}


def _targets(sim, p):
    if p.type == "cattail":
        return sorted((z for z in sim.active() if sim.targetable(z, "homing")),
                      key=lambda z: (not _flying(z), math.hypot(
                          sum(sim.hitbox(z)) / 2 - p.x - 40, 100 * (z.row - p.row))))
    if p.type == "gloom_shroom":
        return [z for z in sim.active() if abs(z.row - p.row) <= 1
                and sim.targetable(z)
                and sim.hitbox(z)[0] < p.x + 160
                and sim.hitbox(z)[1] > p.x - 80]
    if p.type == "cactus":
        return [z for z in sim.in_range(p.row, p.x + 60, 900, attack="air")
                if z.phase != "balloon_popping"]
    return sim.in_range(p.row, p.x + 60, 900,
                        attack="lob" if p.type in LOBS else "ground")


def _queue(sim, p):
    if not _targets(sim, p):
        return
    delays = {"gatling_pea": (32, 49, 65, 82),
              "gloom_shroom": (74, 102, 130, 158)}.get(p.type, (SPECS[p.type][2],))
    for delay in delays:
        p.shots.append({"due": sim.frame + delay, "direction": 1, "extended": True})
    sim.emit("attack_started", plant=p.id, direction=1)


def _fire(sim, p):
    targets = _targets(sim, p)
    if p.type == "gloom_shroom":
        for z in targets:
            sim.damage(z, 20, p.id, both=True)
        sim.emit("gloom_pulse", plant=p.id)
        return
    if p.type == "gatling_pea":
        offset = (plant_animation.muzzle_offset(p)[0]
                  if sim.scenario.movement_mode == "animation" else 60)
        sim.add_projectile(p, p.row, p.x + offset, "pea")
        return
    if p.type == "cactus":
        airborne = any(_flying(z) for z in targets)
        sim.add_projectile(p, p.row, p.x + (93 if airborne else 70), "cactus_spike",
                           target="air" if airborne else "ground")
        return
    if p.type == "cattail":
        if targets:
            sim.add_projectile(p, p.row, p.x + 20, "cattail_spike",
                               y=p.y - 3, vx=2.0, vy=0.0, motion="homing",
                               target=targets[0].id)
        return
    if p.type in LOBS:
        target = targets[0] if targets else None
        x, y = p.x + (5 if p.type == "cabbage_pult" else 25), p.y - (12 if p.type == "cabbage_pult" else 46)
        if target:
            lead = 0 if target.eating or target.buttered or getattr(target, "frozen", 0) else target.direction * target.speed * (0.5 if target.chilled else 1) * 50
            dx = sum(sim.hitbox(target)) / 2 + lead - x - 30
            dy = 80 + 100 * (target.row - 1) - 30 - y
        else:
            dx, dy = 700 - x, 0
        sim.add_projectile(p, p.row, x, LOBS[p.type], y=y, vx=max(40, dx) / 120,
                           vz=dy / 120 - 7, motion="lob", target=target.id if target else None)


def _ice(sim, p):
    from .boss_zombie import clear_balls
    clear_balls(sim, kind="fire", source=p.id)
    for z in sim.active():
        if not sim.can_chill(z):
            continue
        cold = z.chilled > 0 or getattr(z, "frozen", 0) > 0
        z.chilled = max(z.chilled, 2000)
        if not sim.can_freeze(z):
            continue
        z.frozen = sim.rng.randint(300, 400) if cold else sim.rng.randint(400, 600)
        sim.damage(z, 20, p.id, bypass=True)
        sim.emit("frozen", plant=p.id, zombie=z.id, frames=z.frozen)


def _instant(sim, p):
    if p.type == "ice_shroom":
        _ice(sim, p)
    else:
        if p.type == "jalapeno":
            from .boss_zombie import clear_balls
            clear_balls(sim, kind="ice", row=p.row, source=p.id)
            targets = [z for z in sim.active(p.row) if sim.targetable(z, "explosion")]
            for z in targets:
                z.chilled = 0
                z.frozen = 0
            sim.ladders = {(r, c) for r, c in sim.ladders if r != p.row}
        else:
            targets = sim.near(p, 250 if p.type == "doom_shroom" else 115,
                               3 if p.type == "doom_shroom" else 1, attack="explosion")
        for z in targets:
            sim.damage(z, 1800, p.id, both=True)
        if p.type == "doom_shroom":
            for other in sim.plants:
                if other.hp > 0 and other.row == p.row and other.col == p.col:
                    sim.destroy_plant(other, p.id)
        sim.emit("explosion", plant=p.id, kind=p.type)
    if p.hp > 0:
        sim.destroy_plant(p, "activated")


def update(sim, p):
    """Call before the existing per-plant shot/timer handling."""
    if p.type not in SPECS:
        return False
    if p.hp <= 0:
        return True
    if p.type == "cob_cannon":
        p.cooldown -= 1
        if p.cooldown > 0:
            return True
        targets = sorted((z for z in sim.active() if sim.targetable(z, "explosion")),
                         key=lambda z: (z.x, z.id))
        if not targets:
            return True
        target = targets[0]
        x, y = p.x + 20, p.y - 35
        dx = (sum(sim.hitbox(target)) / 2) - x - 30
        dy = (80 + 100 * (target.row - 1) - 30) - y
        sim.add_projectile(p, p.row, x, "cob", y=y,
                           vx=max(40, dx) / 120, vz=dy / 120 - 7,
                           target=target.id, motion="lob")
        p.cooldown = SPECS[p.type][1]
        sim.emit("cob_fired", plant=p.id, target=target.id,
                 target_row=target.row, target_x=round(sum(sim.hitbox(target)) / 2))
        return True
    if p.type == "blover":
        if p.state == "ready":
            p.state = "activating"
            if not p.state_timer:
                p.state_timer = 50
        p.state_timer = max(0, p.state_timer - 1)
        if not p.state_timer:
            for z in sim.active():
                if z.phase == "balloon_flying":
                    z.status, z.eating = "exited", False
                    sim.emit("zombie_exited", zombie=z.id, side="air", source=p.id)
            sim.emit("blover_activated", plant=p.id)
            sim.destroy_plant(p, "activated")
        return True
    if p.type == "spikerock":
        if p.state == "attacking":
            p.state_timer = max(0, p.state_timer - 1)
            if p.state_timer in {70, 32}:
                for z in sim.in_range(p.row, p.x + 20, p.x + 50, strict=True):
                    machine = z.type in {"zamboni", "catapult"}
                    sim.damage(z, 1800 if machine else 20, p.id, bypass=True)
                    if machine:
                        if z.status == "active":
                            sim.kill(z, p.id)
                        p.hp = max(0, p.hp - 50)
                        if not p.hp:
                            sim.destroy_plant(p, z.id)
                            return True
                sim.emit("spikerock_pulse", plant=p.id)
            if not p.state_timer:
                p.state = "ready"
        elif sim.in_range(p.row, p.x + 20, p.x + 50):
            p.state, p.state_timer = "attacking", 100
        return True
    if p.type in INSTANTS:
        # Initial state_timer overrides the standard 100 cs activation delay.
        if p.state == "ready":
            p.state = "activating"
            if not p.state_timer:
                p.state_timer = 100
        p.state_timer = max(0, p.state_timer - 1)
        if not p.state_timer:
            _instant(sim, p)
        return True
    if p.state_timer:
        p.state_timer -= 1
    if p.recently_eaten:
        p.recently_eaten -= 1
    pending = []
    for shot in p.shots:
        if shot["due"] <= sim.frame:
            _fire(sim, p)
        else:
            pending.append(shot)
    p.shots = pending
    period = SPECS[p.type][1]
    if period:
        p.cooldown -= 1
        if p.type == "cattail" and p.cooldown == 50:
            _queue(sim, p)
        if p.cooldown <= 0:
            _queue(sim, p)
            p.cooldown = period - sim.rng.randrange(15)
    return True


def update_projectile(sim, q):
    """Handle extension projectile movement, collision and damage in one pass."""
    if q.kind not in EXTENDED_PROJECTILES:
        return False
    collision_x = int(q.x)
    q.age += 1
    if q.motion == "homing":
        target = next((z for z in sim.active() if z.id == q.target and sim.targetable(z, "homing")), None)
        if target:
            dx = sum(sim.hitbox(target)) / 2 - q.x - 20
            dy = 80 + 100 * (target.row - 1) + 27.5 - q.y - 20
            distance = math.hypot(dx, dy) or 1
            vx, vy = q.vx + dx / distance * .001 * q.age, q.vy + dy / distance * .001 * q.age
            speed = math.hypot(vx, vy) or 1
            q.vx, q.vy = vx / speed * 2, vy / speed * 2
        q.x, q.y = q.x + q.vx, q.y + q.vy
        q.row = max(1, min(5, int((q.y - 80) // 100) + 1))
    elif q.motion == "lob":
        q.vz += .115
        q.x += q.vx
        q.z += q.vz
    else:
        q.x += 3.33
    if q.x < -80 or q.x > 900 or q.y is not None and not -150 <= q.y <= 700:
        q.active = False
        return True
    min_z = -35 if q.kind in {"melon", "winter_melon"} else -30
    if q.motion == "lob" and q.age > 20 and (q.vz < 0 or q.z <= min_z):
        return True
    attack = "homing" if q.kind == "cattail_spike" else "air" if q.kind == "cactus_spike" else "lob"
    left, right = ((collision_x + 20, collision_x + 80) if q.kind in {"melon", "winter_melon"}
                   else (collision_x - 25, collision_x + 40) if q.kind.endswith("spike")
                   else (collision_x, collision_x + 40))
    hits = sim.projectile_targets(q.row, left, right, attack=attack)
    if q.motion == "homing":
        # Unlike straight shots, homing spikes collide only with their assigned target.
        hits = [z for z in sim.active() if z.id == q.target and sim.targetable(z, "homing")
                and sim.hitbox(z)[0] <= right and sim.hitbox(z)[1] >= left
                and 50 + 100 * (z.row - 1) < q.y < 165 + 100 * (z.row - 1)]
    if q.kind == "cactus_spike":
        hits = [z for z in hits if z.phase != "balloon_popping"
                and _flying(z) == (q.target == "air")]
    if not hits:
        if q.motion == "lob" and q.z > 80:
            q.active = False
            sim.emit("projectile_missed", projectile=q.id, kind=q.kind)
        return True
    z = hits[0]
    q.active = False
    if _flying(z) and q.kind in {"cactus_spike", "cattail_spike"}:
        if hasattr(sim, "pop_balloon"):
            sim.pop_balloon(z, q.owner)
        else:
            z.phase, z.phase_timer = "balloon_popping", 100
            sim.emit("balloon_popped", zombie=z.id, source=q.owner)
    if q.kind in {"melon", "winter_melon"}:
        splash = [other for other in sim.active() if other.id != z.id
                  and abs(other.row - q.row) <= 1 and sim.targetable(other, "lob")
                  and sim.hitbox(other)[0] <= right
                  and sim.hitbox(other)[1] >= left]
        amount = 26 if 26 * len(splash) <= 560 else max(1, 44800 // (78 * len(splash)))
        sim.damage(z, 80, q.owner, both=True, chill=q.kind == "winter_melon")
        for other in splash:
            sim.damage(other, amount, q.owner, both=True, chill=q.kind == "winter_melon")
    else:
        sim.damage(z, 40 if q.kind == "cabbage" else 20, q.owner,
                   bypass=q.kind == "cabbage")
    sim.emit("projectile_hit", projectile=q.id, zombie=z.id, kind=q.kind)
    return True


def on_bite(sim, p, z):
    """Call before applying bite damage. True suppresses that damage."""
    if p.type in INSTANTS:
        return True
    if p.type == "hypno_shroom":
        sim.destroy_plant(p, z.id)
        sim.hypnotize(z, p.id)
        return True
    if p.type == "garlic":
        timers = getattr(sim, "garlic_timers", None)
        if timers is None:
            sim.garlic_timers = timers = {}
        if z.id not in timers:
            timers[z.id] = {"remaining": 170 if z.type in YUCKY_FACE else 21,
                            "direction": getattr(p, "garlic_direction", "random"), "plant": p.id}
            sim.emit("garlic_disgust", zombie=z.id, plant=p.id)
        else:
            return True
    return False


def update_zombie(sim, z):
    """Pause a garlic-affected zombie until its source-backed row-change tick."""
    timers = getattr(sim, "garlic_timers", {})
    entry = timers.get(z.id)
    if entry is None:
        return False
    z.eating = False
    entry["remaining"] -= 1
    if entry["remaining"] > 0:
        return True
    direction = entry["direction"]
    delta = -1 if direction == "up" else 1 if direction == "down" else sim.rng.choice((-1, 1))
    if not 1 <= z.row + delta <= 5:
        delta = -delta
    previous = z.row
    z.row += delta
    del timers[z.id]
    sim.emit("garlic_row_changed", zombie=z.id, plant=entry["plant"], previous_row=previous, row=z.row)
    return False
