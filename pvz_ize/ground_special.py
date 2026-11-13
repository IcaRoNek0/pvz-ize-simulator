"""Ground-special zombie states; animation-dependent timings are explicit."""

POLE_JUMP_FRAMES = 180
POLE_JUMP_DURATION = 43 / 24 * 100
LADDER_PLACE_FRAMES = 50
DIGGER_STUN_FRAMES = 350
LADDER_CLIMB_FRAMES = 120
WALK_SPEED = 0.143
DIGGER_REVERSE_SPEED = 0.11

SPECIAL_TYPES = {"pole_vaulting", "ladder", "digger"}
UNDERGROUND = {"digger_tunneling", "digger_axe_pause"}
RISING = {"digger_rising", "digger_rising_no_axe"}
OFF_GROUND = RISING | {"pole_jumping", "digger_axe_pause"}


def _state(sim, z):
    if not hasattr(sim, "_ground_special_state"):
        sim._ground_special_state = {}
    return sim._ground_special_state.setdefault(z.id, {})


def _phase(sim, z, phase, timer=0):
    previous = z.phase
    z.phase, z.phase_timer = phase, timer
    if z.type == "digger":
        z.underground = phase in UNDERGROUND
    z.eating = False
    sim.emit("zombie_phase", zombie=z.id, previous=previous, phase=phase)


def initialize(sim, z):
    """Initialize only new units, preserving explicit noninitial phases."""
    if z.phase != "initial":
        return
    if z.type == "pole_vaulting":
        _phase(sim, z, "pole_running" if z.tool else "pole_walking")
        if not z.tool:
            z.speed = WALK_SPEED
    elif z.type == "ladder":
        z.tool = z.tool and z.shield_hp > 0
        if not z.tool:
            z.shield_hp = 0
        _phase(sim, z, "ladder_carrying" if z.tool else "walking")
        if not z.tool:
            z.speed = WALK_SPEED
    elif z.type == "digger":
        z.direction = -1
        _phase(sim, z, "digger_tunneling" if z.tool else "digger_axe_pause",
               0 if z.tool else 200)


def targetable(z, attack="ground"):
    """Filter attack ranges without treating a live headless unit as dead."""
    phase = z.phase
    if attack in {"all", "magnet", "explosion"}:
        return True
    if phase == "digger_tunneling":
        return attack == "underground"
    if phase in OFF_GROUND:
        return attack == "off_ground"
    return attack != "underground"


def mouth(z, x=None):
    """World-space attack interval, with the original 120 px sprite mirror."""
    if z.type == "pole_vaulting" and z.phase == "pole_running":
        offset, width = -29, 70
    elif z.type == "pole_vaulting" and z.phase == "pole_jumping":
        offset, width = -40, 100
    elif z.type == "ladder" and z.phase in {"ladder_carrying", "ladder_placing"}:
        offset, width = 10, 50
    elif z.type == "pogo":
        offset, width = (10, 30) if z.tool else (20, 50)
    else:
        offset, width = 50, 20
    if z.direction > 0 and z.type in {"digger", "pogo"}:
        offset = 120 - offset - width
    left = int(z.x if x is None else x) + offset
    return left, left + width


def _plant_bounds(p):
    if p.type == "pumpkin":
        return p.x, p.x + 60
    return p.x + 10, p.x + (90 if p.type == "tallnut" else 70)


def _target(sim, z, *, nuts_only=False):
    left, right = mouth(z)
    vault = (z.type == "pole_vaulting" and z.phase in {"pole_running", "pole_jumping"}
             or z.type == "pogo" and z.tool)
    candidates = sim.plants if vault else (sim.bite_order() if hasattr(sim, "bite_order") else sim.plants)
    for p in candidates:
        if p.hp <= 0 or p.row != z.row or p.type in {"spikeweed", "spikerock"}:
            continue
        if p.type == "squash" and p.state == "airborne":
            continue
        if vault and (p.type in {"pumpkin", "lily_pad", "flower_pot"}
                      or getattr(p, "layer", "main") != "main"):
            # ATTACKTYPE_VAULT uses TOPPLANT_ONLY_NORMAL_POSITION, not
            # the shell-first chewing order. A living main plant masks it.
            if any(q.hp > 0 and q.row == p.row and q.col == p.col
                   and getattr(q, "layer", "main") == "main"
                   and q.type not in {"pumpkin", "lily_pad", "flower_pot", "spikeweed", "spikerock"}
                   and not (q.type == "squash" and q.state == "airborne")
                   for q in sim.plants):
                continue
        if nuts_only and p.type not in {"wallnut", "tallnut", "pumpkin"}:
            continue
        if nuts_only and (p.row, p.col) in sim.ladders:
            continue
        a, b = _plant_bounds(p)
        if min(right, b) - max(left, a) >= 20:
            return p
    return None


def _tick(z, *, animation=True):
    z.phase_timer = max(0, z.phase_timer - (0.5 if animation and z.chilled else 1))
    return z.phase_timer == 0


def _move(sim, z, *, tunnel=False):
    if not tunnel and hasattr(sim, "move"):
        sim.move(z)
    else:
        z.x += z.direction * z.speed * (1 if tunnel or not z.chilled else 0.5)


def _advance_pole_jump(sim, z):
    data = _state(sim, z)
    # Vault collision X uses direct mVelX, not the rendered 150*animTime
    # offset. Chill slows the animation, but not this direct displacement.
    z.x -= data["jump_velocity"]
    data["jump_elapsed"] += .5 if z.chilled else 1
    z.phase_timer = max(0, POLE_JUMP_DURATION - data["jump_elapsed"])


def remove_tool(sim, z):
    """Remove a ladder or pickaxe, not the digger's separate hardhat."""
    if z.type == "ladder":
        had_tool = z.tool or z.shield_hp > 0
        z.tool, z.shield_hp = False, 0
        z.speed = WALK_SPEED
        if z.phase in {"ladder_carrying", "ladder_placing"}:
            _phase(sim, z, "walking")
        if had_tool:
            sim.emit("tool_removed", zombie=z.id, tool="ladder")
    elif z.type == "digger" and z.tool:
        z.tool = False
        if z.phase == "digger_tunneling":
            _phase(sim, z, "digger_axe_pause", 200)
        sim.emit("tool_removed", zombie=z.id, tool="pickaxe")


def _start_climb(sim, z, p):
    data = _state(sim, z)
    data.update(resume=z.phase, destination=p.x - 70)
    z.target_col = p.col
    _phase(sim, z, "ladder_climbing", LADDER_CLIMB_FRAMES)
    sim.emit("ladder_climb_started", zombie=z.id, row=p.row, col=p.col)


def _existing_ladder(sim, z):
    if z.type == "digger" or z.direction > 0:
        return None
    left, right = mouth(z)
    for p in (sim.bite_order() if hasattr(sim, "bite_order") else sim.plants):
        if (p.hp > 0 and p.row == z.row and (p.row, p.col) in sim.ladders
                and p.col != z.target_col and p.type not in {"spikeweed", "spikerock"}):
            a, b = _plant_bounds(p)
            if min(right, b) - max(left, a) >= 20:
                return p
    return None


def update(sim, z):
    """Return True when the special state consumes movement and chewing."""
    initialize(sim, z)
    if z.status != "active":
        return True
    if z.buttered:
        return True
    if z.phase == "ladder_climbing":
        if (z.row, z.target_col) not in sim.ladders:
            _phase(sim, z, _state(sim, z)["resume"])
            sim.emit("ladder_climb_interrupted", zombie=z.id, col=z.target_col)
            return True
        if _tick(z, animation=False):
            data = _state(sim, z)
            z.x = min(z.x, data["destination"])
            _phase(sim, z, data["resume"])
            sim.emit("ladder_climb_finished", zombie=z.id, col=z.target_col)
        return True

    if z.type == "ladder" and z.phase in {"ladder_carrying", "ladder_placing"}:
        if not z.shield_hp:
            remove_tool(sim, z)
        elif not z.headless and z.phase == "ladder_placing":
            if _tick(z):
                p = _target(sim, z, nuts_only=True)
                if p:
                    sim.ladders.add((p.row, p.col))
                    remove_tool(sim, z)
                    sim.emit("ladder_placed", zombie=z.id, row=p.row, col=p.col)
                    _start_climb(sim, z, p)
                else:
                    _phase(sim, z, "ladder_carrying")
            return True
        elif z.phase == "ladder_placing":
            # No head: placement stops, while the engine's decay still runs.
            return True
        elif not z.headless:
            p = _target(sim, z, nuts_only=True)
            if p:
                z.target_col = p.col
                _phase(sim, z, "ladder_placing", LADDER_PLACE_FRAMES)
                return True

    if z.type == "pole_vaulting":
        if z.phase == "pole_jumping":
            data = _state(sim, z)
            progress = data["jump_elapsed"] / POLE_JUMP_DURATION
            p = _target(sim, z) if .6 < progress <= .7 else None
            blocked = p is not None and p.type == "tallnut"
            if blocked or progress >= 1:
                z.x = p.x if blocked else z.x - 150
                z.speed = WALK_SPEED
                _phase(sim, z, "pole_walking")
                sim.emit("pole_blocked" if blocked else "pole_landed", zombie=z.id)
                if blocked:
                    # The collision tick still walks, but HEIGHT_FALLING
                    # prevents chewing until the following actions update.
                    _move(sim, z)
                    return True
                return False
            _advance_pole_jump(sim, z)
            return True
        if z.phase == "pole_running":
            if not z.headless:
                p = _target(sim, z)
                if p and (p.row, p.col) not in sim.ladders:
                    z.target, z.target_col, z.tool = p.id, p.col, False
                    _state(sim, z).update(jump_velocity=(int(z.x) - int(p.x) - 80) / POLE_JUMP_DURATION,
                                          jump_elapsed=0)
                    _phase(sim, z, "pole_jumping", POLE_JUMP_FRAMES)
                    sim.emit("pole_jump_started", zombie=z.id, plant=p.id)
                    _advance_pole_jump(sim, z)
                    return True
                if int(z.x) + 50 <= 20 and any(b.row == z.row and b.hp > 0 for b in sim.brains):
                    z.speed = WALK_SPEED
                    _phase(sim, z, "pole_walking")
                    return False
            p = _existing_ladder(sim, z)
            if p:
                _start_climb(sim, z, p)
            else:
                _move(sim, z)
            return True

    if z.type == "digger":
        if z.phase == "digger_tunneling":
            if not z.tool:
                _phase(sim, z, "digger_axe_pause", 200)
            elif z.x < 10:
                z.direction = 1
                _phase(sim, z, "digger_rising", 130)
            else:
                _move(sim, z, tunnel=True)
            return True
        if z.phase == "digger_axe_pause":
            if _tick(z, animation=False):
                _phase(sim, z, "digger_rising_no_axe", 130)
            return True
        if z.phase in RISING:
            if _tick(z, animation=False):
                if z.phase == "digger_rising":
                    _phase(sim, z, "digger_stunned", DIGGER_STUN_FRAMES)
                else:
                    z.direction, z.speed = -1, WALK_SPEED
                    _phase(sim, z, "digger_walking_no_axe")
            return True
        if z.phase == "digger_stunned":
            if _tick(z):
                z.direction, z.speed = 1, DIGGER_REVERSE_SPEED
                _phase(sim, z, "digger_walking")
            return True
        return False

    p = _existing_ladder(sim, z)
    if p:
        _start_climb(sim, z, p)
        return True
    return False
