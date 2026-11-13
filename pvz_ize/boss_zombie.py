"""Zomboss's source-backed attack scheduler and persistent ice/fire balls.

Animation lengths come from the supplied IZC 0.7.1 Pro compiled resources.
The scheduler follows Portable Zombie.cpp's Boss* routines; row selection is
uniform rather than Board::PickRowForNewZombie's board-history weighting.
"""

import math


BOSS_HP = 60000
HEAD_PHASES = {"boss_head_idle_before_spit", "boss_head_spit", "boss_head_idle_after_spit"}
SUMMON_TYPES = ("conehead", "buckethead", "football", "pole_vaulting",
                "jack_in_the_box", "ladder", "zamboni", "catapult", "pogo",
                "newspaper", "screen_door", "gargantuar")
ANIMATION_FRAMES = {
    "spawn": (22, 21, 21, 21, 21),
    "stomp": (31, 31, 29, 29),
    "head_spit": (40, 40, 40, 40, 43),
    "head_enter": 57, "head_leave": 45, "rv": 38,
    "bungee_enter": 25, "bungee_leave": 18,
}
# GetTrackVelocity(_ground) at rate 2.0, from the supplied ball resources.
BALL_SPEED = {"fire": 1036.8999787 / 56 * .02,
              "ice": 1036.8999787 / 58 * .02}


def _state(sim, z):
    if not hasattr(sim, "_boss_state"):
        sim._boss_state = {}
    return sim._boss_state.setdefault(z.id, {})


def _phase(sim, z, name, timer=0, *, animated=False):
    old = z.phase
    z.phase, z.phase_timer, z.eating = name, timer, False
    _state(sim, z).update(duration=timer, animated=animated, contact=False)
    sim.emit("zombie_phase", zombie=z.id, previous=old, phase=name)


def _duration(frames, rate=12):
    return math.ceil(frames * 100 / rate)


def initialize(sim, z):
    if z.type != "boss" or z.phase != "initial":
        return
    data = _state(sim, z)
    data.update(mode=0, summon=500, head=5000, stomp=-1, bungee=-1,
                balls=[], followers=[], max_hp=BOSS_HP)
    # IZC's native creation wrapper forces boss world x=0 and internal row=0.
    z.x, z.row, z.headless, z.eating = 0.0, 1, False, False
    _phase(sim, z, "boss_enter")


def targetable(z, attack="ground"):
    return z.type != "boss" or z.phase in HEAD_PHASES


def can_chill(z):
    return z.type != "boss" or z.phase in HEAD_PHASES


def hitbox(z):
    """The original boss damage rectangle spans all five lawn rows."""
    return (700, 790) if z.type == "boss" else None


def rect(z):
    return (700, 80, 90, 430) if z.type == "boss" else None


def row_matches(z, row):
    return row is None or z.type == "boss" or z.row == row


def distance_to(z, x, y):
    """Distance from a world-space blast center to the native boss rectangle."""
    if z.type != "boss":
        return None
    dx, dy = max(700 - x, x - 790, 0), max(80 - y, y - 510, 0)
    return math.hypot(dx, dy)


def receive_damage(sim, z, amount, source, *, chill=False, **unused):
    """Boss TakeBodyDamage keeps one HP until its head-death state runs."""
    if z.type != "boss":
        return False
    if z.status == "active" and targetable(z):
        z.hp = max(1, z.hp - amount)
        z.last_damage_age = z.age + 25
        if chill and can_chill(z):
            z.chilled = max(z.chilled, 1000)
        sim.emit("damage", zombie=z.id, source=source, amount=amount,
                 hp=z.hp, helmet_hp=z.helmet_hp, shield_hp=z.shield_hp)
    return True


def _idle(sim, z):
    _phase(sim, z, "boss_idle", sim.rng.randint(100, 200))


def _start(sim, z, action):
    data = _state(sim, z)
    if action != "head_enter":
        z.chilled, z.frozen = 0, 0
    if action == "spawn":
        data["summon"] = sim.rng.randint(*((450, 550), (350, 450), (150, 250))[data["mode"]])
        data["target_row"] = sim.rng.randint(1, 5)
        frames = ANIMATION_FRAMES["spawn"][data["target_row"] - 1]
        phase, rate = "boss_spawning", 12
    elif action == "stomp":
        data["stomp"] = sim.rng.randint(5500, 6500)
        rows = [row for row in range(1, 5) if any(
            p.hp > 0 and row <= p.row <= row + 1 and p.col >= 6
            and p.state != "airborne" for p in sim.plants)]
        # BossStompAttack still animates the retained target if no row qualifies.
        data["target_row"] = sim.rng.choice(rows) if rows else data.get("target_row", 1)
        frames = ANIMATION_FRAMES["stomp"][min(3, data["target_row"] - 1)]
        phase, rate = "boss_stomping", 12
    elif action == "bungee_enter":
        data["bungee"] = sim.rng.randint(4000, 5000)
        data["target_col"] = sim.rng.randint(1, 3)
        frames, phase, rate = ANIMATION_FRAMES[action], "boss_bungees_enter", 12
    elif action == "rv":
        data["target_row"], data["target_col"] = sim.rng.randint(1, 4), sim.rng.randint(1, 3)
        frames, phase, rate = ANIMATION_FRAMES[action], "boss_drop_rv", 16
    elif action == "head_enter":
        data["head"] = sim.rng.randint(4000, 5000)
        frames, phase, rate = ANIMATION_FRAMES[action], "boss_head_enter", 12
    elif action == "head_spit":
        data["ball_row"] = sim.rng.randint(1, 5)
        data["ball_kind"] = sim.rng.choice(("fire", "ice"))
        # A new spit replaces the old ball, as BossHeadSpit does.
        data["balls"].clear()
        frames = ANIMATION_FRAMES[action][data["ball_row"] - 1]
        phase, rate = "boss_head_spit", 12
    elif action == "head_leave":
        frames, phase, rate = ANIMATION_FRAMES[action], "boss_head_leave", 12
    elif action == "bungee_leave":
        frames, phase, rate = ANIMATION_FRAMES[action], "boss_bungees_leave", 18
    else:
        raise ValueError(f"unknown boss action: {action}")
    _phase(sim, z, phase, _duration(frames, rate), animated=True)


def clear_balls(sim, *, kind, row=None, source=None):
    """Ice-shroom removes fire balls; same-row jalapeno removes ice balls."""
    for ident, data in getattr(sim, "_boss_state", {}).items():
        kept = []
        for ball in data["balls"]:
            if ball["kind"] == kind and (row is None or ball["row"] == row):
                sim.emit("boss_ball_destroyed", zombie=ident, kind=kind,
                         row=ball["row"], source=source)
            else:
                kept.append(ball)
        data["balls"] = kept


def _balls(sim, z):
    data = _state(sim, z)
    kept = []
    for ball in data["balls"]:
        if ball["forming"]:
            ball["forming"] -= 1
        else:
            ball["x"] -= BALL_SPEED[ball["kind"]]
        # Native PixelToGridX(x+75): grid col 0 starts at x=40, width 80.
        col = math.floor((ball["x"] + 75 - 40) / 80) + 1
        for p in sim.plants:
            if (p.hp > 0 and p.row == ball["row"] and p.col == col
                    and p.type not in {"spikeweed", "spikerock"}):
                sim.destroy_plant(p, z.id)
        if ball["x"] >= -180:
            kept.append(ball)
    data["balls"] = kept


def _contact(sim, z):
    data = _state(sim, z)
    phase = z.phase
    row = data.get("target_row", 1)
    if phase == "boss_spawning":
        kind = ("normal" if z.age < 3500 else "conehead" if z.age < 8000 else
                "buckethead" if z.age < 12500 else
                sim.rng.choice(SUMMON_TYPES[:-1] if row == 1 else SUMMON_TYPES))
        child = sim.spawn_zombie(kind, row, 600)
        sim.emit("boss_summoned", zombie=z.id, summoned=child.id, type=kind, row=row)
    elif phase in {"boss_stomping", "boss_drop_rv"}:
        col = data.get("target_col", 1)
        for p in sim.plants:
            eligible = (p.col >= 6 if phase == "boss_stomping" else col <= p.col <= col + 2)
            if p.hp > 0 and row <= p.row <= row + 1 and eligible:
                sim.destroy_plant(p, z.id)
        sim.emit("boss_stomp" if phase == "boss_stomping" else "boss_rv_landed",
                 zombie=z.id, row=row, col=col)
        if phase == "boss_drop_rv":
            data["summon"], data["head"] = 500, 5000
            if data["mode"] >= 1:
                data["stomp"] = 4000
            if data["mode"] >= 2:
                data["bungee"] = 6500
    elif phase == "boss_head_spit":
        ball = {"row": data["ball_row"], "kind": data["ball_kind"], "x": 455.0,
                "forming": 100}
        data["balls"].append(ball)
        sim.emit("boss_ball_fired", zombie=z.id, **ball)
    elif phase == "boss_bungees_enter":
        data["followers"] = []
        for col in range(data["target_col"], data["target_col"] + 3):
            plants = [p for p in sim.plants if p.hp > 0 and p.col == col]
            row = sim.rng.choice(plants).row if plants else sim.rng.randint(1, 5)
            child = sim.spawn_zombie("bungee", row, 40 + (col - 1) * 80)
            child.target_col = col
            data["followers"].append(child.id)
        _phase(sim, z, "boss_bungees_drop")


def update(sim, z):
    """Consume boss updates, including during freeze so existing balls roll."""
    if z.type != "boss":
        return False
    initialize(sim, z)
    if z.status != "active":
        return True
    data = _state(sim, z)
    _balls(sim, z)
    if z.frozen or z.buttered:
        return True
    for counter in ("summon", "head", "stomp", "bungee"):
        if data[counter] > 0:
            data[counter] -= 1
    if z.hp <= 1 and z.phase in {
            "boss_idle", "boss_head_idle_before_spit", "boss_head_idle_after_spit"}:
        data["balls"].clear()
        sim.kill(z, "boss_defeated")
        return True
    if z.phase == "boss_enter":
        _idle(sim, z)
        return True
    if z.phase == "boss_bungees_drop":
        followers = [other for other in sim.zombies if other.id in data["followers"]
                     and other.status == "active"]
        if not followers or any(other.phase == "bungee_rising" for other in followers):
            _start(sim, z, "bungee_leave")
        return True
    animated = data.get("animated", False)
    old_timer = z.phase_timer
    z.phase_timer = max(0, old_timer - (.5 if animated and z.chilled else 1))
    fraction = {"boss_spawning": .6, "boss_stomping": .5 if data.get("target_row", 1) < 3 else .55,
                "boss_drop_rv": .65, "boss_head_spit": .42,
                "boss_bungees_enter": .4}.get(z.phase)
    if fraction is not None and not data["contact"]:
        trigger = data["duration"] * (1 - fraction)
        if old_timer > trigger >= z.phase_timer:
            data["contact"] = True
            _contact(sim, z)
            if z.phase == "boss_bungees_drop":
                return True
    if z.phase_timer:
        return True
    if z.phase == "boss_idle":
        damage_mode = 2 if z.hp < data["max_hp"] / 2 else 1 if z.hp < data["max_hp"] * .8 else 0
        if data["mode"] != damage_mode:
            data["mode"] = damage_mode
            _start(sim, z, "bungee_enter" if damage_mode == 1 else "rv")
        elif data["stomp"] == 0:
            _start(sim, z, "stomp")
        elif data["bungee"] == 0:
            if sim.rng.randrange(2) == 0:
                data["bungee"] = sim.rng.randint(4000, 5000)
                _start(sim, z, "rv")
            else:
                _start(sim, z, "bungee_enter")
        elif data["head"] == 0:
            _start(sim, z, "head_enter")
        elif data["summon"] == 0:
            _start(sim, z, "spawn")
        else:
            _idle(sim, z)
    elif z.phase == "boss_head_enter":
        _phase(sim, z, "boss_head_idle_before_spit", 500)
    elif z.phase == "boss_head_idle_before_spit":
        _start(sim, z, "head_spit")
    elif z.phase == "boss_head_spit":
        _phase(sim, z, "boss_head_idle_after_spit", 300)
    elif z.phase == "boss_head_idle_after_spit":
        _start(sim, z, "head_leave")
    else:
        if z.phase == "boss_head_leave":
            z.chilled = 0
        _idle(sim, z)
    return True
