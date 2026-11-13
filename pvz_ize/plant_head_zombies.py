"""Six ZomBotany zombies from Zombie.cpp's plant-head state machines.

Counters and collision rules follow the original, non-DO_FIX_BUGS branches.
Body-head x tracks are numeric translations from the local original Zombie
reanimation (compiled SHA256 f48b234be901473bc5bfdf49a6bda20c66cb041c61aab28644b8d84de159fb5b).
Animation blending and the body's y displacement remain approximations.
"""

TYPES = {"pea_head", "wallnut_head", "jalapeno_head", "gatling_head",
         "squash_head", "tallnut_head"}
SHOOTERS = {"pea_head", "gatling_head"}
LOW_PLANTS = {"puff_shroom", "sun_shroom", "potato_mine", "spikeweed",
              "spikerock", "lily_pad"}
SQUASH_PHASES = {"head_squash_rising", "head_squash_falling", "head_squash_landed"}

HEAD_X = {
    "walk2": (6.7, 7.1, 7.5, 8.0, 8.4, 8.8, 9.2, 9.7, 10.1, 10.5, 9.6,
              8.6, 7.7, 6.7, 5.7, 4.8, 3.8, 3.5, 3.4, 3.9, 4.4, 5.0,
              5.5, 6.0, 6.2, 6.3, 6.6, 6.8, 7.0, 7.2, 7.5, 7.7, 8.0,
              7.1, 6.3, 5.6, 4.8, 4.1, 3.3, 2.6, 2.6, 2.6, 3.5, 4.3,
              5.1, 5.9, 6.7),
    "walk": (6.7, 8.5, 10.4, 12.4, 14.5, 15.9, 17.2, 18.5, 19.9, 20.8,
             21.7, 22.7, 23.7, 22.8, 22.0, 21.2, 20.2, 15.6, 11.2, 6.8,
             2.6, 1.7, 0.9, 2.5, 4.5, 6.8, 9.2, 11.6, 13.9, 16.6, 19.1,
             21.9, 24.6, 25.3, 26.2, 26.8, 27.6, 21.9, 16.3, 10.7, 5.5,
             5.6, 5.8, 6.0, 6.1, 6.3, 6.7),
    "eat": (6.7, 7.3, 8.1, 8.7, 9.4, 8.2, 7.0, 5.8, 5.2, 4.6, 4.0,
            3.3, 2.6, 2.0, 2.8, 3.5, 4.3, 5.1, 5.9, 6.7, 7.2, 7.8,
            8.3, 8.9, 9.4, 8.2, 7.0, 5.8, 5.2, 4.6, 4.0, 3.3, 2.6,
            2.0, 2.8, 3.5, 4.3, 5.1, 5.9, 6.7),
}


def _state(sim, z):
    if not hasattr(sim, "_plant_head_state"):
        sim._plant_head_state = {}
    return sim._plant_head_state.setdefault(z.id, {})


def _phase(sim, z, name, frames=0):
    previous = z.phase
    z.phase, z.phase_timer = name, frames
    sim.emit("zombie_phase", zombie=z.id, previous=previous, phase=name)


def initialize(sim, z):
    if z.type not in TYPES or z.phase != "initial":
        return
    timer = 150 if z.type in SHOOTERS else 0
    if z.type == "jalapeno_head":
        velocity = z.velocity_parameter or z.speed / .47
        timer = int((275 + sim.rng.randrange(175)) / velocity) * 2
    _phase(sim, z, "head_squash_ready" if z.type == "squash_head" else "head_walking", timer)


def _head_x(sim, z):
    data = _state(sim, z)
    name = ("eat" if z.eating else "walk2" if z.type == "pea_head"
            or z.walk_variant in {None, 0} else "walk")
    if data.get("head_animation") != name:
        data["head_animation"], data["head_phase"] = name, 0.0
    phase = data["head_phase"]
    if name != "eat" and z.animation_phase is not None:
        phase = z.animation_phase
    samples = HEAD_X[name]
    position = phase * (len(samples) - 1)
    lower = min(len(samples) - 1, int(position))
    upper = min(len(samples) - 1, lower + 1)
    x = samples[lower] + (samples[upper] - samples[lower]) * (position - lower)
    # Eating runs at 36 fps; walking rate follows Zombie::UpdateAnimSpeed.
    rate = 36 if name == "eat" else (z.velocity_parameter or z.speed / .47) * 47 * 47 / 49.8
    data["head_phase"] = (phase + .01 * rate / len(samples) * (.5 if z.chilled else 1)) % 1
    return x


def _fire(sim, z, head_x):
    # Original plant-headed zombies keep hostile backward peas after hypnosis.
    sim.add_projectile(z, z.row, z.x + head_x - 9, "zombie_pea", -1)
    sim.emit("zombie_shot", zombie=z.id)


def _squash(sim, z):
    if z.phase == "head_squash_ready":
        if z.headless or not z.eating:
            return False
        z.eating, z.headless = False, True
        _phase(sim, z, "head_squash_rising", 95)
        sim.emit("squash_head_launched", zombie=z.id)
        return True
    if z.phase not in SQUASH_PHASES:
        return False
    if z.phase == "head_squash_rising" and z.phase_timer == 0:
        _phase(sim, z, "head_squash_falling", 10)
    elif z.phase == "head_squash_falling":
        if z.phase_timer == 2:
            col = max(1, min(9, (int(z.x) - 40) // 80 + 1))
            for p in sim.plants:
                if p.hp > 0 and (p.row, p.col) == (z.row, col) and p.type != "spikerock":
                    sim.destroy_plant(p, z.id)
            sim.emit("squash_head_impact", zombie=z.id, row=z.row, col=col)
        if z.phase_timer == 0:
            _phase(sim, z, "head_squash_landed", 100)
    elif z.phase == "head_squash_landed" and z.phase_timer == 0:
        sim.damage(z, 1800, z.id, bypass=True)
    return True


def update(sim, z):
    """Run before ordinary movement/chewing; True means action is consumed."""
    if z.type not in TYPES:
        return False
    initialize(sim, z)
    if z.status != "active" or z.hp <= 0:
        return True
    if z.buttered or z.frozen:
        return True
    if z.phase_timer:
        z.phase_timer = max(0, z.phase_timer - 1)
    if z.type == "squash_head":
        return _squash(sim, z)
    if z.headless:
        return False
    if z.type in SHOOTERS:
        x = _head_x(sim, z)
        if (z.type == "pea_head" and z.phase_timer == 0
                or z.type == "gatling_head" and z.phase_timer in {68, 51, 35, 18}):
            _fire(sim, z, x)
        if z.phase_timer == 0:
            z.phase_timer = 150
    elif z.type == "jalapeno_head" and z.phase_timer == 0:
        for p in sim.plants:
            if p.hp > 0 and p.row == z.row and not (p.type == "squash" and p.state == "airborne"):
                sim.destroy_plant(p, z.id)
        sim.emit("jalapeno_head_exploded", zombie=z.id, row=z.row)
        sim.kill(z, "jalapeno_head_exploded")
        return True
    return False


def update_projectile(sim, q):
    """Zombie peas damage plants, skipping low targets and prioritizing shells."""
    if q.kind != "zombie_pea":
        return False
    if not q.active:
        return True
    collision_x = int(q.x)
    q.age += 1
    q.x -= 3.33
    if q.x < -80 or q.x > 900:
        q.active = False
        return True
    left, right = collision_x - 15, collision_x + 40
    for p in sim.plants:
        if p.hp <= 0 or p.row != q.row or p.type in LOW_PLANTS:
            continue
        if p.type == "squash" and p.state == "airborne":
            continue
        a = p.x + (0 if p.type == "pumpkin" else 10)
        b = p.x + (90 if p.type == "tallnut" else 60 if p.type == "pumpkin" else 70)
        if min(right, b) - max(left, a) <= 8:
            continue
        target = next((top for top in sim.bite_order() if top.hp > 0
                       and (top.row, top.col) == (p.row, p.col)
                       and not (top.type == "squash" and top.state == "airborne")), p)
        target.hp = max(0, target.hp - 20)
        q.active = False
        sim.emit("projectile_hit_plant", projectile=q.id, plant=target.id,
                 source=q.owner, kind=q.kind, amount=20, hp=target.hp)
        if target.hp == 0:
            sim.destroy_plant(target, q.owner)
        break
    return True
