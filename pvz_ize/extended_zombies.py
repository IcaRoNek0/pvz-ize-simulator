"""Additional land zombies, with explicit approximate animation state machines.

Health, damage, phase triggers and random choices follow Portable Zombie.cpp;
animation durations are model constants, not claims of frame equivalence.
"""

import math

from . import ground_special

GIANTS = {"gargantuar", "red_eye_gargantuar"}
MACHINES = {"catapult", "zamboni"}
NO_HEAD_LOSS = GIANTS | MACHINES
SPECIAL_TYPES = GIANTS | MACHINES | {"balloon", "newspaper", "jack_in_the_box", "flag", "pogo", "yeti"}
SMASH_FRAMES = 207
THROW_FRAMES = 142
CATAPULT_SHOOT_FRAMES = 134
BALLOON_POP_FRAMES = 117
NEWSPAPER_GASP_FRAMES = 163
IMP_LAND_FRAMES = 25
POGO_BOUNCE_FRAMES = 80


def _state(sim, z):
    if not hasattr(sim, "_extended_zombie_state"):
        sim._extended_zombie_state = {}
    return sim._extended_zombie_state.setdefault(z.id, {})


def _phase(sim, z, name, frames=0):
    old = z.phase
    z.phase, z.phase_timer, z.eating = name, frames, False
    sim.emit("zombie_phase", zombie=z.id, previous=old, phase=name)


def _tick(z, slowed=True):
    z.phase_timer = max(0, z.phase_timer - (.5 if slowed and z.chilled else 1))
    return z.phase_timer == 0


def _hypnotized(z):
    return getattr(z, "hypnotized", False)


def initialize(sim, z):
    if z.type not in SPECIAL_TYPES or z.phase != "initial":
        return
    data = _state(sim, z)
    if z.type in GIANTS:
        _phase(sim, z, "giant_walking")
    elif z.type == "catapult":
        data["ammo"] = 20
        _phase(sim, z, "catapult_walking")
    elif z.type == "balloon":
        _phase(sim, z, "balloon_flying" if z.tool else "balloon_walking")
        if not z.tool:
            z.speed = .143
    elif z.type == "newspaper":
        _phase(sim, z, "newspaper_reading" if z.shield_hp else "newspaper_mad")
        if not z.shield_hp:
            z.speed = .4
    elif z.type == "jack_in_the_box":
        if not z.tool:
            z.speed = .143
            _phase(sim, z, "walking")
            return
        countdown = getattr(z, "jack_countdown_frames", None)
        if countdown is not None:
            _phase(sim, z, "jack_running", countdown)
            return
        distance = 450 + sim.rng.randrange(300)
        if sim.rng.randrange(20) == 0:
            distance //= 3
        # Portable stores nominal speed and divides motion by two; our speed
        # is already effective pixels/tick, so do not apply that factor twice.
        _phase(sim, z, "jack_running", max(1, int(distance / z.speed)))
    elif z.type == "pogo":
        data.update(pogo_stage="bounce", altitude=0,
                    pogo_velocity=getattr(z, "velocity_parameter", None) or z.speed,
                    pogo_base_velocity=getattr(z, "velocity_parameter", None) or z.speed)
        _phase(sim, z, "pogo_bouncing" if z.tool else "pogo_walking",
               sim.rng.randint(1, POGO_BOUNCE_FRAMES) if z.tool else 0)
        if not z.tool:
            velocity = getattr(z, "velocity_parameter", None)
            if velocity is None:
                velocity = .45 if z.speed == .45 else z.speed / .47
            z.speed, z.velocity_parameter = velocity * .47, velocity
        elif z.headless:
            remove_tool(sim, z)
    elif z.type == "yeti":
        _phase(sim, z, "yeti_walking", sim.rng.randint(1500, 2000))
    else:
        _phase(sim, z, "walking")


def targetable(z, attack="ground"):
    if z.phase == "balloon_flying":
        return attack in {"air", "all", "explosion", "homing"}
    if z.phase in {"balloon_popping", "imp_thrown", "imp_landing"}:
        return attack in {"all", "off_ground", "explosion"}
    # air is a widened ground attack (cactus/cattail), not air-only targeting.
    return True


def pop_balloon(sim, z):
    if z.phase == "balloon_flying":
        z.tool = False
        _phase(sim, z, "balloon_popping", BALLOON_POP_FRAMES)
        sim.emit("balloon_popped", zombie=z.id)


def remove_tool(sim, z):
    if z.type == "pogo" and z.tool:
        z.tool, z.speed = False, .45 * .47
        z.velocity_parameter = .45
        z.shield_hp = 0
        _state(sim, z)["pogo_falling"] = True
        _phase(sim, z, "pogo_walking")
        sim.emit("tool_removed", zombie=z.id, tool="pogo")
    elif z.type == "jack_in_the_box" and z.tool and z.phase == "jack_running":
        z.tool, z.speed = False, .143
        _phase(sim, z, "walking")
        sim.emit("tool_removed", zombie=z.id, tool="jack_box")


def after_damage(sim, z):
    if z.type == "newspaper" and not z.shield_hp and z.phase == "newspaper_reading":
        _phase(sim, z, "newspaper_maddening", NEWSPAPER_GASP_FRAMES)


def _plants(sim, z, left, right, spiky=False):
    candidates = [p for p in sim.plants if p.hp > 0 and p.row == z.row
            and (spiky or p.type not in {"spikeweed", "spikerock"})
            and not (p.type == "squash" and p.state == "airborne")
            and min(right, p.x + 70) - max(left, p.x + 10) >= 0]
    return sorted(candidates, key=lambda p: {"main": 0, "shell": 1, "base": 2}.get(
        getattr(p, "layer", "shell" if p.type == "pumpkin" else "main"), 1))


def _giant_enemies(sim, z):
    excluded = {"digger_tunneling", "digger_axe_pause", "balloon_flying",
                "balloon_popping", "imp_thrown", "imp_landing",
                "bungee_diving", "bungee_rising"}
    return [other for other in sim.active(z.row) if other.id != z.id
            and _hypnotized(other) != _hypnotized(z)
            and other.phase not in excluded and not other.headless
            and abs(other.x-z.x) < 100]


def _move(sim, z, slow=True):
    if slow and hasattr(sim, "move"):
        sim.move(z)
    else:
        z.x += z.direction * z.speed * (.5 if slow and z.chilled else 1)


def advance_pogo_fall(sim, z):
    data = _state(sim, z)
    if data.get("pogo_falling"):
        data["altitude"] = max(0, data.get("altitude", 0) - 1)
        if data["altitude"] == 0:
            data["pogo_falling"] = False


def _pogo(sim, z, *, fall_updated=False):
    data = _state(sim, z)
    if getattr(z, "frozen", 0) or z.buttered:
        return True
    if not z.tool:
        if not fall_updated:
            advance_pogo_fall(sim, z)
        if data.get("pogo_falling"):
            _move(sim, z)
            return True
        return False
    if z.headless:
        remove_tool(sim, z)
        return True

    _tick(z, slowed=False)
    stage = data["pogo_stage"]
    # Native mX is the preceding tick's integer position; mPosX moves before
    # UpdateZombiePogo, but its target query still uses that old collision X.
    collision_x = int(z.x)
    target = ground_special._target(sim, z)
    z.eating = False
    z.x += z.direction * data["pogo_velocity"] * (.4 if z.chilled else 1)
    mode = getattr(getattr(sim, "scenario", None), "mode", "ize")
    if ((mode == "who_will_win" and z.x < -15)
            or mode != "who_will_win" and _brain(sim, z)):
        remove_tool(sim, z)
        return True

    bounce = 1 - abs(2 * (1 - z.phase_timer / POGO_BOUNCE_FRAMES) - 1)
    height = 50 if stage == "high" else 90 if stage == "forward" else 40
    data["altitude"] = 9 + height * (2 * bounce - bounce * bounce)
    if stage == "forward" and z.phase_timer == 70 and target and target.type == "tallnut":
        remove_tool(sim, z)
        sim.emit("pogo_blocked", zombie=z.id, plant=target.id)
        return True
    if z.phase_timer == 0:
        if target is None:
            stage, velocity = "bounce", data["pogo_base_velocity"]
        elif stage == "high":
            stage, velocity = "forward", (collision_x - target.x + 60) / POGO_BOUNCE_FRAMES
        else:
            stage, velocity = "high", 0
        data.update(pogo_stage=stage, pogo_velocity=velocity)
        z.phase_timer = POGO_BOUNCE_FRAMES
        sim.emit("pogo_stage", zombie=z.id, stage=stage, velocity=velocity)
    return True


def _squish(sim, z, p):
    for plant in sim.plants:
        if plant.hp > 0 and (plant.row, plant.col) == (p.row, p.col):
            sim.destroy_plant(plant, z.id)


def _brain(sim, z):
    if _hypnotized(z) or z.direction > 0 or z.x + 50 > 20:
        return None
    return next((b for b in sim.brains if b.row == z.row and b.hp > 0), None)


def _giant(sim, z):
    data = _state(sim, z)
    if z.phase in {"giant_smashing", "giant_throwing"}:
        frames = SMASH_FRAMES if z.phase == "giant_smashing" else THROW_FRAMES
        previous = z.phase_timer
        _tick(z)
        trigger = frames * (1 - (.64 if z.phase == "giant_smashing" else .74))
        if previous > trigger >= z.phase_timer:
            if z.phase == "giant_smashing":
                if _hypnotized(z):
                    targets = _giant_enemies(sim, z)
                    if targets:
                        sim.damage(targets[0], 1000 if z.type == "red_eye_gargantuar" else 500, z.id)
                else:
                    plants = _plants(sim, z, z.x - 30, z.x + 59, spiky=True)
                    if plants:
                        p = plants[0]
                        if p.type == "spikerock":
                            p.hp = max(0, p.hp - 50)
                            sim.damage(z, 20, p.id, bypass=True)
                            if not p.hp:
                                _squish(sim, z, p)
                                sim.destroy_plant(p, z.id)
                        else:
                            _squish(sim, z, p)
                    brain = _brain(sim, z)
                    if brain:
                        brain.hp = 0
                        sim.emit("brain_eaten", zombie=z.id, row=brain.row)
                sim.emit("giant_smash", zombie=z.id)
            elif z.tool:
                z.tool = False
                distance = max(40, z.x - 360)
                if distance > 140:
                    distance -= sim.rng.uniform(0, 100)
                child = sim.spawn_zombie("imp", z.row, z.x + 180 if _hypnotized(z) else z.x - 133)
                child.hypnotized = _hypnotized(z)
                child.direction = z.direction
                child.chilled = z.chilled
                flight = max(1, math.ceil((distance / 3 + math.sqrt((distance / 3) ** 2 + 8 * 88 / .05)) / 2))
                _state(sim, child).update(destination=child.x + z.direction * 3 * flight)
                _phase(sim, child, "imp_thrown", flight)
                sim.emit("imp_thrown", zombie=z.id, imp=child.id)
        if z.phase_timer == 0:
            _phase(sim, z, "giant_walking")
        return True
    if z.headless:
        return False
    max_hp = 6000 if z.type == "red_eye_gargantuar" else 3000
    if z.tool and z.hp < max_hp / 2 and z.x > 400:
        _phase(sim, z, "giant_throwing", THROW_FRAMES)
    elif (_hypnotized(z) and _giant_enemies(sim, z)
          or not _hypnotized(z) and (_plants(sim, z, z.x-30, z.x+59, spiky=True) or _brain(sim, z))):
        _phase(sim, z, "giant_smashing", SMASH_FRAMES)
    else:
        _move(sim, z)
    return True


def _catapult_target(sim, z):
    candidates = [p for p in sim.plants if p.hp > 0 and p.row == z.row
                  and z.x >= p.x + 100 and p.type not in {"spikeweed", "spikerock"}
                  and not (p.type == "squash" and p.state == "airborne")]
    return min(candidates, key=lambda p: (p.col, {"main": 0, "shell": 1, "base": 2}.get(
        getattr(p, "layer", "shell" if p.type == "pumpkin" else "main"), 1)), default=None)


def update_projectiles(sim):
    """Tick once each simulation frame, even after the firing catapult dies."""
    pending = getattr(sim, "_basketballs", [])
    for ball in pending[:]:
        if ball["due"] > sim.frame:
            continue
        pending.remove(ball)
        candidates = [p for p in sim.plants if p.hp > 0 and p.row == ball["row"] and p.col == ball["col"]]
        p = min(candidates, key=lambda p: {"main": 0, "shell": 1, "base": 2}.get(
            getattr(p, "layer", "shell" if p.type == "pumpkin" else "main"), 1), default=None)
        if not p:
            continue
        umbrella = sim.resolve_umbrella(p.row, p.col)
        if umbrella:
            sim.emit("basketball_blocked", zombie=ball["owner"], plant=p.id, umbrella=umbrella.id)
        else:
            p.hp = max(0, p.hp - 75)
            sim.emit("basketball_hit", zombie=ball["owner"], plant=p.id, amount=75, hp=p.hp)
            if not p.hp:
                sim.destroy_plant(p, ball["owner"])


def _machine(sim, z):
    data = _state(sim, z)
    if _hypnotized(z):
        # Root resolves opposing-zombie combat; never crush friendly plants.
        _move(sim, z, slow=z.type != "zamboni")
        return True
    if z.type == "catapult" and not _hypnotized(z):
        target = _catapult_target(sim, z)
        if z.phase == "catapult_launching":
            data["reload_remaining"] = max(0, data.get("reload_remaining", 300) - 1)
            before = z.phase_timer
            _tick(z)
            if before > CATAPULT_SHOOT_FRAMES * .455 >= z.phase_timer:
                target = _catapult_target(sim, z)
                if target:
                    if not hasattr(sim, "_basketballs"):
                        sim._basketballs = []
                    sim._basketballs.append(dict(due=sim.frame+120, row=target.row, col=target.col, owner=z.id))
                    sim.emit("basketball_fired", zombie=z.id, plant=target.id)
            if z.phase_timer == 0:
                data["ammo"] -= 1
                _phase(sim, z, "catapult_reloading", data["reload_remaining"])
            return True
        if z.phase == "catapult_reloading" and not _tick(z, slowed=False):
            return True
        if z.x <= 650 and target and data.get("ammo", 20) > 0:
            data["reload_remaining"] = 300
            _phase(sim, z, "catapult_launching", CATAPULT_SHOOT_FRAMES)
            return True
        _phase_name = "catapult_walking"
        if z.phase != _phase_name:
            _phase(sim, z, _phase_name)
    if z.type == "zamboni":
        z.speed = min(.25, max(.05, .05 + (z.x-300)*.0005)) if z.x > 400 else .1
    for p in _plants(sim, z, z.x + 10, z.x + 143, spiky=True):
        if p.type in {"spikeweed", "spikerock"}:
            if p.type == "spikeweed":
                sim.destroy_plant(p, z.id)
            else:
                p.hp = max(0, p.hp - 50)
                if not p.hp:
                    sim.destroy_plant(p, z.id)
            sim.kill(z, p.id)
            sim.emit("tires_popped", zombie=z.id, plant=p.id)
            return True
        _squish(sim, z, p)
    brain = _brain(sim, z)
    if brain:
        brain.hp = 0
        sim.emit("brain_eaten", zombie=z.id, row=brain.row)
    _move(sim, z, slow=z.type != "zamboni")
    return True


def update(sim, z, *, pogo_fall_updated=False):
    initialize(sim, z)
    if z.phase == "imp_thrown":
        _move_speed = 3 * z.direction
        z.x += _move_speed
        if _tick(z, slowed=False):
            z.x = _state(sim, z)["destination"]
            _phase(sim, z, "imp_landing", IMP_LAND_FRAMES)
        return True
    if z.phase == "imp_landing":
        if _tick(z):
            _phase(sim, z, "walking")
        return True
    if z.type not in SPECIAL_TYPES:
        return False
    if z.type in GIANTS:
        return _giant(sim, z)
    if z.type in MACHINES:
        return _machine(sim, z)
    if z.type == "balloon":
        if z.phase == "balloon_flying":
            if _brain(sim, z):
                pop_balloon(sim, z)
            else:
                _move(sim, z)
            return True
        if z.phase == "balloon_popping":
            if _tick(z):
                z.speed = .143
                _phase(sim, z, "balloon_walking")
            return True
    elif z.type == "newspaper":
        after_damage(sim, z)
        if z.phase == "newspaper_maddening":
            if _tick(z):
                z.speed = .4
                _phase(sim, z, "newspaper_mad")
            return True
    elif z.type == "jack_in_the_box" and z.tool:
        if z.phase == "jack_popping":
            if _tick(z, slowed=False):
                if not _hypnotized(z):
                    for p in sim.plants:
                        if p.hp > 0 and math.hypot(p.x+40-(z.x+60), (p.row-z.row)*100) <= 90:
                            sim.destroy_plant(p, z.id)
                for other in sim.active():
                    if other.id != z.id and _hypnotized(other) != _hypnotized(z) and math.hypot(other.x-z.x, (other.row-z.row)*100) <= 115:
                        sim.damage(other, 1800, z.id, both=True)
                sim.kill(z, "jack_explosion")
                sim.emit("jack_exploded", zombie=z.id)
            return True
        if not z.headless and _tick(z, slowed=False):
            _phase(sim, z, "jack_popping", 110)
            return True
    elif z.type == "pogo":
        return _pogo(sim, z, fall_updated=pogo_fall_updated)
    elif z.type == "yeti" and not _hypnotized(z):
        if z.phase == "yeti_walking" and _tick(z, slowed=False):
            z.direction, z.speed = 1, .4
            _phase(sim, z, "yeti_running")
    return False
