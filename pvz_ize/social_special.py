"""Dancer formations and bungee theft, with explicit animation approximations.

The caller advances age/cold/butter, invokes this module before ordinary walking,
and iterates a snapshot so newly summoned dancers first update next frame.
"""

import math

from . import ground_special


SOCIAL_TYPES = frozenset({"dancing", "backup_dancer", "bungee"})
DANCER_POINT_FRAMES = 42  # ceil(10 asset frames / 24 fps * 100).
BUNGEE_GRAB_FRAMES = 63  # ceil(15 asset frames / 24 fps * 100).
DANCE_PERIOD = 460
DANCE_WALK_FRAMES = 240
BACKUP_RISE_FRAMES = 150
BUNGEE_WAIT_FRAMES = 300
BUNGEE_RISE_FRAMES = 75


def _state(sim, z):
    if not hasattr(sim, "_social_state"):
        sim._social_state = {}
    return sim._social_state.setdefault(z.id, {})


def _phase(sim, z, phase, timer=0):
    z.phase, z.phase_timer = phase, timer
    sim.emit("zombie_phase", zombie=z.id, phase=phase)


def initialize(sim, z):
    """Initialize only new social units; explicit replay phases are preserved."""
    if z.type not in SOCIAL_TYPES:
        return
    data = _state(sim, z)
    if z.type == "dancing":
        data.setdefault("slots", [None, None, None, None])
    if z.type == "bungee":
        if z.target_col is None:
            z.target_col = min(9, max(1, round((z.x - 40) / 80) + 1))
        z.x = 40 + 80 * (z.target_col - 1)
    if z.phase != "initial":
        return
    if z.type == "dancing":
        z.direction = -1
        _phase(sim, z, "dancer_moonwalk", 300 + sim.rng.randrange(12))
    elif z.type == "backup_dancer":
        z.direction = -1
        _phase(sim, z, "dancer_walking")
    else:
        data["descent_frames"] = math.ceil((3000 + sim.rng.randrange(151)) / 8)
        _phase(sim, z, "bungee_diving", data["descent_frames"])
        z.eating = False


def targetable(z, attack="ground"):
    """Filter social phases, not global life/row/height or other-unit rules."""
    if z.type == "bungee":
        return z.phase in {"bungee_waiting", "bungee_grabbing"} and attack != "underground"
    if z.type == "backup_dancer" and z.phase == "backup_rising":
        return attack in {"off_ground", "all", "explosion"}
    return True


def _tick(z):
    if z.phase_timer > 0:
        z.phase_timer -= 1
    return z.phase_timer == 0


def _living(sim, ident):
    return next((unit for unit in sim.zombies if unit.id == ident
                 and unit.status == "active" and unit.hp > 0), None)


def _slots(z):
    return [(z.row - 1, z.x), (z.row + 1, z.x),
            (z.row, z.x - 100), (z.row, z.x + 100)]


def _sync_slots(sim, z):
    # Explicit initial followers also occupy formation slots; do not duplicate
    # them merely because they were not created by this module's summon call.
    data = _state(sim, z)
    for child in sim.active():
        if child.type != "backup_dancer" or child.leader != z.id or child.id in data["slots"]:
            continue
        if child.row == z.row - 1:
            slot = 0
        elif child.row == z.row + 1:
            slot = 1
        elif child.row == z.row:
            slot = 2 if child.x < z.x else 3
        else:
            continue
        if _living(sim, data["slots"][slot]) is None:
            data["slots"][slot] = child.id
    return data


def _missing(sim, z):
    data = _sync_slots(sim, z)
    return any(1 <= row <= 5 and _living(sim, data["slots"][slot]) is None
               for slot, (row, _) in enumerate(_slots(z)))


def _summon(sim, z):
    if z.headless:
        return
    data = _sync_slots(sim, z)
    for slot, (row, x) in enumerate(_slots(z)):
        if not 1 <= row <= 5 or _living(sim, data["slots"][slot]) is not None:
            continue
        child = sim.spawn_zombie("backup_dancer", row, x, leader=z.id)
        child.phase, child.phase_timer = "backup_rising", BACKUP_RISE_FRAMES
        child.direction = -1
        _state(sim, child)["born_frame"] = sim.frame
        data["slots"][slot] = child.id
        sim.emit("backup_summoned", zombie=z.id, backup=child.id, slot=slot,
                 row=row, x=x)


def _cohort_stopped(sim, z):
    leader = z if z.type == "dancing" else _living(sim, z.leader)
    if leader is None or leader.headless:
        return False
    cohort = [leader] + [unit for unit in sim.active() if unit.leader == leader.id]
    return any(unit.eating or unit.buttered > 0 for unit in cohort)


def _dance(sim, z):
    # Eating overrides the shared visual beat, including after the leader dies.
    if z.eating:
        return False
    walking = sim.frame % DANCE_PERIOD < DANCE_WALK_FRAMES
    phase = "dancer_walking" if walking else "dancer_dancing"
    if z.phase != phase:
        _phase(sim, z, phase)
    if walking and not _cohort_stopped(sim, z):
        z.direction = -1
        return False
    sim.chew(z)
    return True


def _moonwalk_contact(sim, z):
    left, right = ground_special.mouth(z)
    for p in sim.plants:
        if p.hp <= 0 or p.row != z.row or p.type in {"spikeweed", "spikerock"}:
            continue
        if p.type == "squash" and p.state == "airborne":
            continue
        end = p.x + (90 if p.type == "tallnut" else 70)
        if min(right, end) - max(left, p.x + 10) >= 20:
            return True
    return False


def _dancing(sim, z):
    data = _state(sim, z)
    if z.headless:
        z.direction = -1
        if z.phase in {"dancer_moonwalk", "dancer_summoning", "dancer_hold"}:
            _phase(sim, z, "dancer_walking")
        return _dance(sim, z)
    if z.eating:
        return False
    if z.phase == "dancer_moonwalk":
        if _moonwalk_contact(sim, z):
            z.direction = -1
            _phase(sim, z, "dancer_summoning", DANCER_POINT_FRAMES)
            return True
        # The original Jackson ground track has negative velocity: despite the
        # source's += motion branch the backwards-facing animation moves left.
        z.x -= 0.5 * (0.5 if z.chilled else 1)
        if _tick(z) or _moonwalk_contact(sim, z):
            z.direction = -1
            _phase(sim, z, "dancer_summoning", DANCER_POINT_FRAMES)
        return True
    if z.phase == "dancer_summoning":
        if _tick(z):
            _summon(sim, z)
            _phase(sim, z, "dancer_hold", 200)
        return True
    if z.phase == "dancer_hold":
        if not _tick(z):
            return True
        _phase(sim, z, "dancer_walking")
    if _missing(sim, z):
        if "resummon_due" not in data:
            data["resummon_due"] = sim.frame + 100
        if sim.frame >= data["resummon_due"] and sim.frame % DANCE_PERIOD // 20 == 12 and z.x < 700:
            data.pop("resummon_due", None)
            _phase(sim, z, "dancer_summoning", DANCER_POINT_FRAMES)
            return True
    else:
        data.pop("resummon_due", None)
    return _dance(sim, z)


def _backup(sim, z):
    if z.phase == "backup_rising":
        if _state(sim, z).get("born_frame", -1) == sim.frame:
            return True
        if not _tick(z):
            return True
        _phase(sim, z, "dancer_walking")
    if z.leader and _living(sim, z.leader) is None:
        z.leader = None
        sim.emit("backup_orphaned", zombie=z.id)
    return _dance(sim, z)


def _bungee_exit(sim, z):
    z.status, z.eating, z.phase_timer = "exited", False, 0
    _phase(sim, z, "bungee_exited")
    sim.emit("zombie_exited", zombie=z.id, side="air")


def _bungee(sim, z):
    z.eating = False
    if z.headless and z.phase != "bungee_rising":
        _phase(sim, z, "bungee_rising", BUNGEE_RISE_FRAMES)
    if not _tick(z):
        return True
    if z.phase == "bungee_diving":
        umbrella = sim.resolve_umbrella(z.row, z.target_col)
        if umbrella is not None:
            sim.emit("umbrella_block", plant=umbrella.id, zombie=z.id,
                     row=z.row, col=z.target_col)
            sim.emit("bungee_deflected", zombie=z.id, plant=umbrella.id)
            _phase(sim, z, "bungee_rising", BUNGEE_RISE_FRAMES)
        else:
            _phase(sim, z, "bungee_waiting", BUNGEE_WAIT_FRAMES)
    elif z.phase == "bungee_waiting":
        target = next((p for p in (sim.top_order() if hasattr(sim, "top_order") else sim.plants)
                       if p.hp > 0 and p.row == z.row
                       and p.col == z.target_col and p.state != "airborne"), None)
        z.target = target.id if target is not None else None
        _phase(sim, z, "bungee_grabbing", BUNGEE_GRAB_FRAMES)
    elif z.phase == "bungee_grabbing":
        target = next((p for p in sim.plants if p.id == z.target and p.hp > 0), None)
        if target is not None:
            sim.destroy_plant(target, z.id)
            sim.emit("plant_stolen", zombie=z.id, plant=target.id)
        _phase(sim, z, "bungee_rising", BUNGEE_RISE_FRAMES)
    elif z.phase == "bungee_rising":
        _bungee_exit(sim, z)
    return True


def update(sim, z):
    """Return true when special action consumes ordinary walking/chewing."""
    if z.type not in SOCIAL_TYPES:
        return False
    if z.status != "active" or z.hp <= 0:
        return True
    initialize(sim, z)
    if z.type == "bungee":
        return _bungee(sim, z)
    if z.type == "backup_dancer" and z.phase == "backup_rising":
        return _backup(sim, z)
    data = _state(sim, z)
    previous, remaining = z.phase, z.phase_timer
    if ground_special.update(sim, z):
        if previous != "ladder_climbing" and z.phase == "ladder_climbing":
            data["climb_resume"] = previous, remaining
        elif previous == "ladder_climbing" and z.phase != "ladder_climbing":
            resume = data.pop("climb_resume", None)
            if resume is not None and z.phase == resume[0]:
                z.phase_timer = resume[1]
        return True
    if z.type == "dancing":
        return _dancing(sim, z)
    return _backup(sim, z)
