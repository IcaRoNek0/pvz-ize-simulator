"""Stable sequential 10 ms updates, without graphics or game injection."""

from collections import Counter
from copy import deepcopy
from dataclasses import asdict, dataclass
import math
import random

from .catalog import MODEL, PLANTS, WARNINGS, ZOMBIES
from .model import Zombie
from . import ground_special, social_special, extended_plants, extended_zombies, movement
from . import plant_head_zombies, boss_zombie, plant_animation


def overlap(a, b, c, d):
    # Native GetRectOverlap preserves this branch for negative-width rects
    # (the potato/pole scan can produce them); min/max is not equivalent.
    end, start, other_end = (b, c, d) if a < c else (d, a, b)
    return (min(end, other_end) if end > start else end) - start


@dataclass
class Projectile:
    id: str
    owner: str
    row: int
    x: float
    kind: str
    direction: int = 1
    age: int = 0
    last_torch: int = -1
    active: bool = True
    y: float | None = None
    vx: float | None = None
    vy: float = 0
    z: float = 0
    vz: float = 0
    target: str | None = None
    motion: str = "straight"


class Simulator:
    def __init__(self, scenario, event_sink=None):
        self.scenario = deepcopy(scenario)
        self.plants = self.scenario.plants
        self.zombies = self.scenario.zombies
        self.brains = self.scenario.brains
        self.rakes = deepcopy(self.scenario.rakes)
        self.frame = 0
        # Initialization has its own stream, so normalized inputs replay exactly.
        self.rng = random.Random(scenario.seed ^ 0x495A45)
        self.projectiles = []
        self.event_sink = event_sink
        self.counts = Counter()
        self.projectile_id = 0
        self.landing = {}
        self.ladders = {(item["row"], item["col"]) for item in self.scenario.ladders}
        self.spawn_id = 0
        self._result = None
        self._walk_segments = {}
        for rake in self.rakes:
            rake.setdefault("state", "attracting")
            rake.setdefault("counter", 0)
        for zombie in self.zombies:
            ground_special.initialize(self, zombie)
            social_special.initialize(self, zombie)
            extended_zombies.initialize(self, zombie)
            plant_head_zombies.initialize(self, zombie)
            boss_zombie.initialize(self, zombie)
            if zombie.hypnotized:
                self.hypnotize(zombie, "initial_state")
            self._walk_segments[zombie.id] = (movement.track_name(zombie), zombie.speed)

    def emit(self, event, **data):
        self.counts[event] += 1
        if self.event_sink:
            self.event_sink({"frame": self.frame, "event": event, **data})

    def active(self, row=None, headed=False):
        return [z for z in self.zombies if z.status == "active" and z.hp > 0
                and boss_zombie.row_matches(z, row) and (not headed or not z.headless)]

    def targetable(self, z, attack="ground"):
        return (z.status == "active" and z.hp > 0
                and not z.hypnotized
                and boss_zombie.targetable(z, attack)
                and extended_zombies.targetable(z, attack)
                and ground_special.targetable(z, attack)
                and social_special.targetable(z, attack))

    def spawn_zombie(self, type, row, x, leader=None):
        if not 1 <= row <= 5:
            raise ValueError("spawn row must be in 1..5")
        existing = {unit.id for unit in self.plants + self.zombies}
        while True:
            self.spawn_id += 1
            ident = f"spawn{self.spawn_id}"
            if ident not in existing:
                break
        spec = ZOMBIES[type]
        z = Zombie(ident, type, row, float(x), spec.hp, spec.helmet, spec.shield,
                   spec.speed, leader=leader)
        self.zombies.append(z)
        if self.scenario.movement_mode == "animation":
            z.animation_phase = self.rng.uniform(0, .99)
            z.velocity_parameter = .9 if type == "imp" else self.rng.uniform(.23, .37)
            z.walk_variant = self.rng.randrange(2)
        ground_special.initialize(self, z)
        social_special.initialize(self, z)
        extended_zombies.initialize(self, z)
        plant_head_zombies.initialize(self, z)
        boss_zombie.initialize(self, z)
        self._walk_segments[z.id] = (movement.track_name(z), z.speed)
        self.emit("zombie_spawned", zombie=z.id, type=type, row=row, x=x, leader=leader)
        return z

    def resolve_umbrella(self, row, col):
        return next((p for p in self.plants if p.hp > 0 and p.type == "umbrella_leaf"
                     and abs(p.row - row) <= 1 and abs(p.col - col) <= 1), None)

    def bite_order(self):
        return sorted(self.plants, key=lambda p: {"shell": 0, "main": 1, "base": 2}[p.layer])

    def top_order(self):
        return sorted(self.plants, key=lambda p: {"main": 0, "shell": 1, "base": 2}[p.layer])

    def chew_candidates(self):
        occupied = set()
        for p in self.bite_order():
            if p.hp <= 0 or p.type in {"spikeweed", "spikerock"} or p.state == "airborne":
                continue
            cell = (p.row, p.col)
            if cell not in occupied:
                occupied.add(cell)
                yield p

    @staticmethod
    def can_chill(z):
        return boss_zombie.can_chill(z) and not (z.hypnotized or z.headless or z.type == "zamboni" or z.phase in {
            "digger_tunneling", "digger_axe_pause", "digger_rising",
            "digger_rising_no_axe", "backup_rising"})

    def can_freeze(self, z):
        return self.can_chill(z) and z.phase not in {
            "pole_jumping", "balloon_flying", "balloon_popping", "imp_thrown", "imp_landing",
            "jack_popping", "pogo_bouncing"} and (
            z.type != "bungee" or z.phase == "bungee_waiting")

    def _restart_walk(self, z, *, stopped_eating=False):
        z.animation_phase = 0.0
        z.velocity_parameter = (self.rng.uniform(.89, .91) if z.phase == "newspaper_mad"
                                else .45 if z.type in {"flag", "pogo"} and z.speed == ZOMBIES[z.type].speed
                                else .9 if z.type == "imp" and z.speed == ZOMBIES[z.type].speed
                                else self.rng.uniform(.23, .37) if z.type == "newspaper" and z.speed == ZOMBIES[z.type].speed
                                else self.rng.uniform(.66, .68) if (z.type == "football" or z.phase == "pole_running") and z.speed == ZOMBIES[z.type].speed
                                else self.rng.uniform(.79, .81) if z.type in {"ladder", "squash_head"} and z.tool and z.speed == ZOMBIES[z.type].speed
                                else self.rng.uniform(.23, .37) if z.speed == .143
                                else .23 if z.type == "digger" and z.phase == "digger_walking"
                                else z.speed / .47)
        # StartWalkAnim draws speed before variant, even for one-track bodies.
        if stopped_eating and not (z.type == "ladder" and z.tool or z.phase == "newspaper_mad"):
            z.walk_variant = self.rng.randrange(2)
            if z.type in {"flag", "pea_head"}:
                z.walk_variant = 0
        name = movement.track_name(z)
        self._walk_segments[z.id] = (name, z.speed)
        self.emit("walk_segment_changed", zombie=z.id, track=name,
                  velocity_parameter=z.velocity_parameter)

    def move(self, z):
        speed = None
        if self.scenario.movement_mode == "animation":
            name = movement.track_name(z)
            previous = self._walk_segments.get(z.id)
            if previous and previous != (name, z.speed):
                self._restart_walk(z, stopped_eating=previous[0] == "eating")
            else:
                self._walk_segments[z.id] = (name, z.speed)
            speed = movement.displacement(z)
        z.x += z.direction * (z.speed * (.5 if z.chilled else 1) if speed is None else speed)

    def _stop_eating(self, z):
        if not z.eating:
            return
        z.eating = False
        self.emit("walking_started", zombie=z.id)
        if self.scenario.movement_mode == "animation":
            self._restart_walk(z, stopped_eating=True)
            # Native tick-end UpdateReanim advances the reset body,
            # but StopEating itself does not move the zombie.
            movement.advance_phase(z)

    def pop_balloon(self, z, source):
        extended_zombies.pop_balloon(self, z)

    def hypnotize(self, z, source):
        z.hypnotized, z.direction, z.eating = True, 1, False
        # Conversion cancels incompatible attack/tunnel phases, not HP or armor.
        if z.type == "digger":
            z.phase, z.speed, z.underground = "digger_walking", .11, False
        self.emit("hypnotized", zombie=z.id, source=source)

    def zombie_combat(self, z):
        if z.headless or z.type in extended_zombies.GIANTS | extended_zombies.MACHINES:
            return False
        if z.type == "pogo" and (z.tool or extended_zombies._state(self, z).get("pogo_falling")):
            return False
        unavailable = {"imp_thrown", "imp_landing", "jack_popping", "balloon_flying",
                       "balloon_popping", "bungee_diving", "bungee_rising", "bungee_exited",
                       "pole_jumping", "backup_rising"} | ground_special.UNDERGROUND | ground_special.RISING
        if z.phase in unavailable:
            return False
        targets = [other for other in self.active(z.row) if other.id != z.id
                   and other.hypnotized != z.hypnotized
                   and other.phase not in unavailable
                   and overlap(*ground_special.mouth(z), *self.hitbox(other))
                   >= (0 if other.eating else 20)]
        if not targets:
            return False
        z.eating = True
        if z.age % (8 if z.chilled else 4) == 0:
            self.damage(targets[0], 4, z.id, bypass=True)
        return True

    @staticmethod
    def hitbox(z):
        if z.type == "boss":
            return boss_zombie.hitbox(z)
        spec = ZOMBIES[z.type]
        offset = spec.hit_offset
        if z.type == "digger" and z.direction > 0:
            offset = 120 - offset - spec.hit_width
        left = int(z.x) + offset
        return left, left + spec.hit_width

    def in_range(self, row, left, right, *, strict=False, headed=False, attack="ground"):
        return sorted((z for z in self.active(row, headed)
                       if self.targetable(z, attack)
                       and overlap(left, right, *self.hitbox(z)) > (0 if strict else -1e-9)),
                      key=lambda z: self.hitbox(z)[0])

    def projectile_targets(self, row, left, right, *, attack="ground"):
        # FindCollisionTarget compares native integer mX, retaining array order
        # on ties, even for backward shots. Plant targeting has different rules.
        return sorted((z for z in self.active(row) if self.targetable(z, attack)
                       and overlap(left, right, *self.hitbox(z)) >= 0),
                      key=lambda z: int(z.x))

    def _imminent_torchwood(self, q, collision_x):
        # Backward peas use a separate native motion despite sharing our
        # straight mover. Only forward straight pea/ice shots can clip.
        if q.motion != "straight" or q.direction < 0 or q.kind not in {"pea", "ice"}:
            return None
        return next((p for p in self.plants if p.hp > 0 and p.type == "torchwood"
                     and p.row == q.row and p.col != q.last_torch
                     and overlap(p.x + 50, p.x + 80, collision_x + 25, collision_x + 80) > 10), None)

    def kill(self, z, source):
        if z.status != "active":
            return
        z.hp = 0
        z.status = "dead"
        z.eating = False
        self.emit("zombie_died", zombie=z.id, source=source)

    def damage(self, z, amount, source, *, bypass=False, chill=False, both=False):
        if boss_zombie.receive_damage(self, z, amount, source, chill=chill):
            return
        if z.status != "active" or z.hp <= 0:
            return
        if z.type == "zamboni":
            chill = False
        original = amount
        if not bypass and z.shield_hp:
            absorbed = min(z.shield_hp, amount)
            z.shield_hp -= absorbed
            amount -= absorbed
            if z.shield_hp == 0:
                self.emit("armor_lost", zombie=z.id, layer="shield", source=source)
            if both:
                amount = original
        if amount:
            if chill and self.can_chill(z):
                z.chilled = max(z.chilled, 1000)
            absorbed = min(z.helmet_hp, amount)
            z.helmet_hp -= absorbed
            amount -= absorbed
            if absorbed and z.helmet_hp == 0:
                self.emit("armor_lost", zombie=z.id, layer="helmet", source=source)
            z.hp = max(0, z.hp - amount)
        extended_zombies.after_damage(self, z)
        z.last_damage_age = z.age + 25
        self.emit("damage", zombie=z.id, source=source, amount=original,
                  hp=z.hp, helmet_hp=z.helmet_hp, shield_hp=z.shield_hp)
        if z.hp <= 0:
            self.kill(z, source)
        elif (ZOMBIES[z.type].can_lose_head or z.type == "balloon" and z.phase == "balloon_walking") and not z.headless and z.hp < ZOMBIES[z.type].hp // 3:
            z.headless = True
            z.eating = False
            z.buttered = 0
            if z.type == "pogo":
                extended_zombies.remove_tool(self, z)
            self.emit("head_lost", zombie=z.id, source=source)

    def destroy_plant(self, p, source):
        if p.hp <= 0 and p.state == "destroyed":
            return
        p.hp = 0
        p.state = "destroyed"
        p.shots.clear()
        self.ladders.discard((p.row, p.col))
        self.emit("plant_died", plant=p.id, source=source)

    def target_rows(self, p):
        return ([r for r in (p.row - 1, p.row, p.row + 1) if 1 <= r <= 5]
                if p.type == "threepeater" else [p.row])

    def targets(self, p, direction=1):
        if p.type == "starfruit":
            return self.star_targets(p)
        if direction < 0:
            return self.in_range(p.row, 0, p.x + 16)
        return [z for row in self.target_rows(p)
                for z in self.in_range(row, p.x + 60, p.x + 60 + PLANTS[p.type].reach,
                                       attack="lob" if p.type == "kernelpult" else "ground")]

    def star_targets(self, p):
        candidates = [z for z in self.active() if self.targetable(z)]
        if p.recently_eaten:
            return candidates
        result = []
        cx, cy = p.x + 40, p.y + 40
        for z in candidates:
            left, right = self.hitbox(z)
            if z.row == p.row:
                if right < cx:
                    result.append(z)
                continue
            zy = 80 + 100 * (z.row - 1) - 30 + 57.5
            time = math.hypot((left + right) / 2 - cx, zy - cy) / 3.33
            lead = 0 if z.eating or z.buttered else z.direction * z.speed * (0.5 if z.chilled else 1) * time
            left, right = left + lead, right + lead
            angle = math.degrees(math.atan2(zy - cy, (left + right) / 2 - cx))
            if left < cx < right or (
                (20 < angle < 40 or -45 < angle < -25) if abs(z.row - p.row) < 2
                else (25 < angle < 35 or -38 < angle < -28)
            ):
                result.append(z)
        return result

    def queue_shot(self, p, direction=1):
        if self.targets(p, direction):
            shot = {"due": self.frame + PLANTS[p.type].windup, "direction": direction}
            if p.type == "kernelpult":
                shot["kind"] = "butter" if self.rng.randrange(4) == 0 else "kernel"
            p.shots.append(shot)
            self.emit("attack_started", plant=p.id, direction=direction)

    def fire(self, p, direction, kind=None):
        if p.type == "starfruit":
            a = math.radians(30)
            for vx, vy in ((-3.33, 0), (0, 3.33), (0, -3.33),
                           (math.cos(a) * 3.33, math.sin(a) * 3.33),
                           (math.cos(a) * 3.33, -math.sin(a) * 3.33)):
                self.add_projectile(p, p.row, p.x + 25, "star",
                                    y=p.y + 25, vx=vx, vy=vy, motion="star")
            return
        if p.type == "kernelpult":
            kind = kind or "kernel"
            target = next(iter(self.targets(p)), None)
            x, y = p.x + (12 if kind == "butter" else 19), p.y - (56 if kind == "butter" else 37)
            if target:
                left, right = self.hitbox(target)
                lead = (0 if target.eating or target.buttered else
                        target.direction * target.speed * (0.5 if target.chilled else 1) * 50)
                dx = (left + right) / 2 + lead - x - 30
                dy = 80 + 100 * (target.row - 1) - 30 - y
            else:
                dx, dy = 700 - x, 0
            self.add_projectile(p, p.row, x, kind, y=y, vx=max(40, dx) / 120,
                                vz=dy / 120 - 7, target=target.id if target else None,
                                motion="lob")
            return
        if p.type == "fume_shroom":
            for z in self.in_range(p.row, p.x + 60, p.x + 400, strict=True):
                self.damage(z, 20, p.id, both=True)
            self.emit("fume", plant=p.id)
            return
        kind = ("ice" if p.type == "snow_pea" else
                "puff" if p.type == "puff_shroom" else
                "spore" if p.type == "scaredy_shroom" else "pea")
        offset = {"puff_shroom": 40, "scaredy_shroom": 29,
                  "threepeater": 45}.get(p.type, 60)
        offset = offset if direction > 0 else 10
        if p.type == "split_pea":
            offset = 61 if direction > 0 else -27
        if self.scenario.movement_mode == "animation" and p.type in plant_animation.TYPES:
            offset, _ = plant_animation.muzzle_offset(p, direction)
        for row in self.target_rows(p):
            self.add_projectile(p, row, p.x + offset, kind, direction)

    def add_projectile(self, p, row, x, kind, direction=1, **state):
        self.projectile_id += 1
        shot = Projectile(f"q{self.projectile_id}", p.id, row, x, kind, direction, **state)
        self.projectiles.append(shot)
        self.emit("projectile_fired", plant=p.id, projectile=shot.id,
                  row=row, direction=direction, kind=kind, x=shot.x)
        return shot

    def near(self, p, radius, max_rows, *, headed=False, attack="ground"):
        result = []
        for z in self.active(headed=headed):
            if not self.targetable(z, attack):
                continue
            if z.type == "boss":
                center_x = p.x + 40 if attack == "explosion" else p.x
                if boss_zombie.distance_to(z, center_x, p.y + 40) <= radius:
                    result.append(z)
                continue
            if abs(z.row - p.row) > max_rows:
                continue
            left, right = self.hitbox(z)
            # Ground zombie rect is y=plant_y-30, height=115.
            dy = 100 * (z.row - p.row)
            dx = max(left - p.x, p.x - right, 0)
            ydist = max(dy - 50, -dy - 65, 0)
            if dx * dx + ydist * ydist <= radius * radius:
                result.append(z)
        return result

    def potato_triggered(self, p):
        left, right = p.x, p.x + 55
        for z in self.active(p.row, headed=True):
            if not (self.targetable(z) or self.targetable(z, "underground")):
                continue
            if z.phase in {"pole_running", "pole_jumping"} or (z.type == "pogo" and z.tool):
                continue
            if z.type == "pole_vaulting":
                # FindTargetZombie mutates one attack rect throughout the scan;
                # even an out-of-range pole affects subsequent candidates.
                left += 40
            if z.type == "bungee" and z.target_col != p.col:
                continue
            if overlap(left, right, *self.hitbox(z)) >= (-30 if z.eating else 0):
                return True
        return False

    def special(self, p):
        if p.type == "spikeweed":
            if p.state == "attacking":
                if p.state_timer == 75:
                    for z in self.in_range(p.row, p.x + 20, p.x + 50, strict=True):
                        machine = z.type in extended_zombies.MACHINES
                        if machine:
                            self.destroy_plant(p, z.id)
                        self.damage(z, 1800 if machine else 20, p.id, bypass=True)
                        if machine and z.status == "active":
                            self.kill(z, p.id)
                if p.state_timer == 0:
                    p.state = "ready"
            elif self.in_range(p.row, p.x + 20, p.x + 50):
                p.state, p.state_timer = "attacking", 100
            return
        if p.state_timer:
            return
        if p.type == "potato_mine":
            if self.potato_triggered(p):
                for z in self.active(p.row):
                    if not (self.targetable(z) or self.targetable(z, "underground")):
                        continue
                    left, right = self.hitbox(z)
                    if max(left - (p.x + 20), p.x + 20 - right, 0) <= 60:
                        self.damage(z, 1800, p.id, both=True)
                self.emit("explosion", plant=p.id)
                self.destroy_plant(p, "exploded")
        elif p.type == "magnet_shroom":
            targets = [z for z in self.near(p, 320, 2, headed=True, attack="magnet")
                       if ZOMBIES[z.type].metal and (
                           z.tool if z.type in {"digger", "pogo"} else
                           z.tool and z.phase == "jack_running" if z.type == "jack_in_the_box"
                           else z.helmet_hp or z.shield_hp)
                       and z.x <= 800 and z in self.near(p, 320 if z.eating else 270, 2, attack="magnet")]
            if targets:
                def distance(z):
                    dx, dy = self.hitbox(z)[0] - p.x, z.row - p.row
                    base = (math.hypot(dx, 100 * dy - 30)
                            if self.scenario.magnet_distance_mode == "source" else abs(dx))
                    return base + 80 * abs(dy)
                z = min(targets, key=distance)
                layer = {"digger": "pickaxe", "pogo": "pogo", "jack_in_the_box": "jack_box"}.get(
                    z.type, "shield" if z.shield_hp else "helmet")
                if z.type in {"digger", "ladder"}:
                    ground_special.remove_tool(self, z)
                elif z.type in {"pogo", "jack_in_the_box"}:
                    extended_zombies.remove_tool(self, z)
                elif z.shield_hp:
                    z.shield_hp = 0
                else:
                    z.helmet_hp = 0
                p.state_timer = 1500
                self.emit("magnet", plant=p.id, zombie=z.id, layer=layer)
            else:
                ordered = sorted(self.ladders, key=lambda rc: (
                    max(abs(rc[0]-p.row), abs(rc[1]-p.col)) + .05*abs(rc[0]-p.row), rc))
                ladder = next(((r, c) for r, c in ordered
                               if abs(r - p.row) <= 2 and abs(c - p.col) <= 2), None)
                if ladder:
                    self.ladders.remove(ladder)
                    p.state_timer = 1500
                    self.emit("ladder_removed", plant=p.id, row=ladder[0], col=ladder[1])
        elif p.type == "chomper":
            if p.state == "digesting":
                p.state = "ready"
            targets = [z for z in self.active(p.row, headed=True)
                       if self.targetable(z)
                       and not (z.type == "bungee" and z.target_col == p.col)
                       if overlap(p.x + 80, p.x + 120, *self.hitbox(z))
                       >= (-60 if z.eating or p.state == "biting" else 0)]
            if p.state == "biting":
                if targets:
                    z = min(targets, key=lambda z: self.hitbox(z)[0])
                    if z.type in extended_zombies.GIANTS or z.type == "boss":
                        self.damage(z, 40, p.id)
                        p.state, p.state_timer = "ready", 70
                    elif z.phase in {"pole_running", "pogo_bouncing"} and not (z.frozen or z.buttered):
                        p.state, p.state_timer = "ready", 70
                    else:
                        self.kill(z, p.id)
                        p.state, p.state_timer = "digesting", 4000
                        self.emit("swallow", plant=p.id)
                else:
                    p.state = "ready"
            elif targets:
                p.state, p.state_timer = "biting", 70
                self.emit("chomp_started", plant=p.id)
        elif p.type == "squash":
            if p.state == "ready":
                targets = [z for z in self.active(p.row, headed=True)
                           if self.targetable(z)
                           if overlap(p.x + 20, p.x + 65, *self.hitbox(z))
                           >= (-110 if z.eating else -70)]
                if targets:
                    z = min(targets, key=lambda z: abs(self.hitbox(z)[0] - p.x))
                    p.target = z.id
                    p.state, p.state_timer = "looking", 80
                    self.emit("squash_started", plant=p.id, zombie=z.id)
            elif p.state == "looking":
                p.state, p.state_timer = "pre_jump", 45
            elif p.state == "pre_jump":
                z = next((z for z in self.active(p.row) if z.id == p.target), None)
                self.landing[p.id] = (self.hitbox(z)[0] - (0 if z.eating or z.type == "boss" else
                    z.speed * (0.5 if z.chilled else 1) * 30) if z else p.x)
                p.state, p.state_timer = "airborne", 55
            elif p.state == "airborne":
                x = self.landing[p.id]
                for z in self.active(p.row):
                    if not self.targetable(z):
                        continue
                    if overlap(x - 20, x + 60, *self.hitbox(z)) > (-20 if z.type == "football" else 0):
                        self.damage(z, 1800, p.id, both=True)
                self.emit("squash_impact", plant=p.id, x=x)
                self.destroy_plant(p, "squashed")

    def update_plant(self, p):
        if p.hp <= 0:
            return
        if any(z.type == "bungee" and z.status == "active"
               and z.phase == "bungee_grabbing" and z.target == p.id for z in self.zombies):
            return
        if extended_plants.update(self, p):
            return
        remaining = []
        for shot in p.shots:
            if shot["due"] <= self.frame:
                self.fire(p, shot["direction"], shot.get("kind"))
            else:
                remaining.append(shot)
        p.shots = remaining
        if p.state_timer > 0:
            p.state_timer -= 1
        if p.recently_eaten > 0:
            p.recently_eaten -= 1
        self.special(p)
        if p.hp <= 0:
            return
        if p.type == "torchwood":
            for q in self.projectiles:
                if q.active and q.row == p.row and q.kind in {"pea", "ice"} and q.last_torch != p.col:
                    if overlap(p.x + 50, p.x + 80, int(q.x) - 15, int(q.x) + 40) >= 10:
                        q.kind = "pea" if q.kind == "ice" else "fire"
                        q.last_torch = p.col
                        self.emit("torch", plant=p.id, projectile=q.id, kind=q.kind)
        spec = PLANTS[p.type]
        if not spec.windup:
            return
        if p.type == "scaredy_shroom" and not p.shots and self.near(p, 120, 1, headed=True):
            p.cooldown = 149
            return
        p.cooldown -= 1
        if p.cooldown == 25 and p.type in {"repeater", "split_pea"}:
            self.queue_shot(p, -1 if p.type == "split_pea" else 1)
        if p.cooldown <= 0:
            self.queue_shot(p)
            if p.type == "split_pea":
                self.queue_shot(p, -1)
            p.cooldown = spec.period - self.rng.randrange(15)

    def exit_or_die(self, z):
        if z.status != "active":
            return
        if z.hp <= 0:
            self.kill(z, "initial_state")
            return
        boundary = (-175 if z.type == "football" else -150 if z.type == "pole_vaulting"
                    else -130 if z.type in {"dancing", "backup_dancer"} else -100)
        if z.x > 850:
            z.status, z.eating = "exited", False
            self.emit("zombie_exited", zombie=z.id, side="right")
        elif z.headless and z.x <= boundary + 70:
            self.kill(z, "left_edge_headless")
        elif z.x <= boundary:
            z.status, z.eating = "entered_house", False
            self.emit("zombie_exited", zombie=z.id, side="house")

    def update_zombie(self, z):
        if z.status != "active":
            return
        z.age += 1
        if z.chilled:
            z.chilled -= 1
        if z.buttered:
            z.buttered -= 1
        if z.frozen:
            z.frozen -= 1
        if z.headless and self.rng.randrange(5) == 0:
            z.hp = max(0, z.hp - (3 if ZOMBIES[z.type].hp >= 500 else 1))
            if z.hp <= 0:
                self.kill(z, "headless_decay")
                return
        if boss_zombie.update(self, z):
            return
        if z.buttered or z.frozen:
            self.exit_or_die(z)
            return
        if plant_head_zombies.update(self, z):
            self.exit_or_die(z)
            return
        if extended_plants.update_zombie(self, z):
            self.exit_or_die(z)
            return
        if z.type == "pogo" and not z.tool:
            extended_zombies.advance_pogo_fall(self, z)
        if self.zombie_combat(z):
            self.exit_or_die(z)
            return
        if extended_zombies.update(self, z, pogo_fall_updated=True) or (not z.hypnotized and (
                social_special.update(self, z) or ground_special.update(self, z))):
            self.exit_or_die(z)
            return
        collision_x = int(z.x)
        if not z.eating:
            self.move(z)
        self.chew(z, collision_x=collision_x)
        self.exit_or_die(z)

    def chew(self, z, *, collision_x=None):
        """Shared bite cadence for ordinary movement and special idle phases."""
        if z.hypnotized:
            if not z.headless and z.age % (8 if z.chilled else 4) == 0:
                self._stop_eating(z)
            return
        if not z.headless and z.age % (8 if z.chilled else 4) == 0:
            # Native prey checks precede the tick-end float-to-integer sync.
            collision_x = int(z.x) if collision_x is None else collision_x
            mouth_left, mouth_right = ground_special.mouth(z, collision_x)
            brain_left = (collision_x + 50 if z.phase == "pole_running" else mouth_left)
            if z.type == "balloon":
                brain_left += 15
            plant = next((p for p in self.chew_candidates() if p.hp > 0 and p.row == z.row
                          and p.type not in {"spikeweed", "spikerock"}
                          and not (p.type == "squash" and p.state == "airborne")
                          and not ((p.row, p.col) in self.ladders and z.type != "digger")
                          and overlap(mouth_left, mouth_right, p.x + (0 if p.type == "pumpkin" else 10),
                                      p.x + (90 if p.type == "tallnut" else 60 if p.type == "pumpkin" else 70)) >= 20), None)
            brain = next((b for b in self.brains if b.row == z.row and b.hp > 0
                          and z.direction < 0 and brain_left <= 20), None)
            was_eating = z.eating
            if plant or brain:
                z.eating = True
                if not was_eating:
                    self.emit("eating_started", zombie=z.id)
            else:
                self._stop_eating(z)
            if plant:
                if extended_plants.on_bite(self, plant, z):
                    return
                invulnerable = (plant.type == "potato_mine" or
                                plant.type == "squash" and plant.state in {"looking", "pre_jump"})
                if not invulnerable:
                    damage = 8 if plant.type in {"wallnut", "tallnut"} and z.age - z.last_damage_age > 500 else 4
                    plant.hp = max(0, plant.hp - damage)
                    plant.recently_eaten = 50
                    self.emit("plant_bitten", zombie=z.id, plant=plant.id, amount=damage, hp=plant.hp)
                    if plant.hp <= 0:
                        self.destroy_plant(plant, z.id)
            elif brain:
                brain.hp -= 1
                self.emit("brain_bitten", zombie=z.id, row=brain.row, hp=brain.hp)
                if brain.hp == 0:
                    self.emit("brain_eaten", zombie=z.id, row=brain.row)

    def update_projectile(self, q):
        if plant_head_zombies.update_projectile(self, q):
            return
        if extended_plants.update_projectile(self, q):
            return
        # Both normal and lobbed collision precede tick-end mX synchronization.
        collision_x = int(q.x)
        q.age += 1
        if q.motion == "star":
            q.x += q.vx
            q.y += q.vy
            if q.vy:
                q.row = max(1, min(5, int((q.y - 80) // 100) + 1))
        elif q.motion == "lob":
            q.vz += 0.115
            q.x += q.vx
            q.z += q.vz
        else:
            q.x += 3.33 * q.direction
        if q.x < -80 or q.x > 900 or q.kind == "puff" and q.age >= 75:
            q.active = False
            return
        if q.motion == "star" and not 40 <= q.y <= 600:
            q.active = False
            return
        if q.kind == "cob" and (q.age <= 20 or q.vz < 0 or q.z <= -60):
            return
        if q.motion == "lob" and q.age > 20 and (q.vz < 0 or q.z <= (-32 if q.kind == "butter" else -30)):
            return
        left = collision_x - (15 if q.kind in {"pea", "ice"} else 0)
        right = collision_x + (30 if q.kind == "fire" else 40)
        torch = self._imminent_torchwood(q, collision_x)
        if torch is not None:
            self.emit("torch_clip", projectile=q.id, plant=torch.id, x=collision_x)
            return
        hits = self.projectile_targets(q.row, left, right,
                             attack="lob" if q.motion == "lob" else "ground")
        if q.kind == "star" and q.age < 25 and q.vx >= 0:
            hits = [z for z in hits if z.type != "digger"]
        if q.kind == "cob":
            # Native CobBig uses a 115px radius and affects the target row
            # plus one adjacent row.  Its 1800 damage hits shield and body.
            target = next((z for z in self.active() if z.id == q.target), None)
            center = (sum(self.hitbox(target)) / 2 if target else collision_x + 80)
            splash = [other for other in self.active()
                      if abs(other.row - q.row) <= 1
                      and self.targetable(other, "explosion")
                      and overlap(center - 115, center + 115, *self.hitbox(other)) >= 0]
            q.active = False
            for other in splash:
                self.damage(other, 1800, q.owner, both=True)
            self.emit("cob_impact", projectile=q.id, row=q.row, x=center,
                      zombies=[other.id for other in splash])
            return
        if not hits:
            if q.motion == "lob" and q.z > 80:
                q.active = False
                self.emit("projectile_missed", projectile=q.id, kind=q.kind)
            return
        z = hits[0]
        q.active = False
        if q.kind == "fire":
            z.chilled = 0
            z.frozen = 0
            resistant = lambda other: (other.type in extended_zombies.MACHINES
                                       or other.shield_hp > 0 and other.type in {"screen_door", "ladder"})
            if resistant(z):
                self.damage(z, 40, q.owner)
                self.emit("projectile_hit", projectile=q.id, zombie=z.id, kind=q.kind)
                return
            splash = [other for other in self.in_range(q.row, left, left + 100)
                      if other.id != z.id and not resistant(other)]
            splash_damage = 13 if 13 * len(splash) <= 40 else max(1, 1600 // (39 * len(splash)))
            self.damage(z, 40, q.owner, both=True)
            for other in splash:
                self.damage(other, splash_damage, q.owner, both=True)
        elif q.kind in {"kernel", "butter"}:
            self.damage(z, 40 if q.kind == "butter" else 20, q.owner, bypass=True)
            if q.kind == "butter" and z.status == "active" and z.type != "boss" and not z.headless and self.can_freeze(z):
                z.buttered = 400
                self.emit("butter_applied", zombie=z.id, frames=400, projectile=q.id)
        else:
            backward = q.vx < 0 if q.kind == "star" else q.direction < 0
            self.damage(z, 20, q.owner, bypass=backward, chill=q.kind == "ice")
        self.emit("projectile_hit", projectile=q.id, zombie=z.id, kind=q.kind)

    def terminal(self):
        if not any(b.hp > 0 for b in self.brains):
            return "zombies", "all_brains_eaten"
        if self.scenario.mode == "who_will_win":
            # IZC DLL board-update predicate, including its single-row scope.
            threats = [z for z in self.active() if z.row == 3 and not z.headless
                       and not z.hypnotized and z.phase not in {
                           "digger_walking", "yeti_running"}]
            if not threats:
                return "plants", "no_row_3_threats"
        elif self.scenario.mode != "time_corridor" and not any(not z.hypnotized for z in self.active()):
            return "plants", "no_on_board_zombies"
        if self.scenario.time_limit_frames is not None and self.frame >= self.scenario.time_limit_frames:
            return self.scenario.timeout_winner, "time_limit_reached"
        return None

    def update_rakes(self):
        """Apply the native one-shot rake hit (1800 damage) when occupied.

        Portable's GridItem uses a 63x80 rectangle, waits for the swing event,
        then removes itself after 200 frames.  We model the gameplay-visible
        state and damage while leaving animation timing to the event log.
        """
        for rake in self.rakes:
            if rake.get("state") == "dead":
                continue
            if rake.get("state") == "triggered":
                rake["counter"] -= 1
                if rake["counter"] <= 0:
                    rake["state"] = "dead"
                continue
            rx = 40 + 80 * (rake["col"] - 1)
            candidates = [z for z in self.zombies if z.status == "active" and z.hp > 0
                          and z.row == rake["row"] and not z.hypnotized
                          and rx - 60 <= z.x <= rx + 63]
            if candidates:
                target = min(candidates, key=lambda z: z.x)
                self.damage(target, 1800, "rake", bypass=True)
                rake["state"] = "triggered"
                rake["counter"] = 200
                self.emit("rake_triggered", row=rake["row"], col=rake["col"], zombie=target.id)

    def run(self):
        if self._result is not None:
            return deepcopy(self._result)
        for z in self.zombies:
            self.exit_or_die(z)
        terminal = self.terminal()
        while terminal is None and self.frame < self.scenario.max_frames:
            self.frame += 1
            for p in self.plants:
                self.update_plant(p)
                if (self.scenario.movement_mode == "animation" and p.hp > 0
                        and p.type in plant_animation.TYPES):
                    plant_animation.advance(p)
            for z in tuple(self.zombies):
                self.update_zombie(z)
            self.update_rakes()
            extended_zombies.update_projectiles(self)
            for q in self.projectiles:
                self.update_projectile(q)
            self.projectiles = [q for q in self.projectiles if q.active]
            terminal = self.terminal()
        winner, reason = terminal or ("undecided", "max_frames_reached")
        self.emit("finished", winner=winner, reason=reason)
        self._result = {
            "model": MODEL, "approximate": True, "warnings": list(WARNINGS),
            "seed": self.scenario.seed, "movement_mode": self.scenario.movement_mode,
            "mode": self.scenario.mode,
            "time_limit_frames": self.scenario.time_limit_frames,
            "timeout_winner": self.scenario.timeout_winner,
            "winner": winner, "reason": reason,
            "status": "timeout" if winner == "undecided" else "finished",
            "frames": self.frame, "seconds": self.frame / 100,
            "brains": [asdict(b) for b in self.brains],
            "plants": [asdict(p) for p in self.plants],
            "zombies": [asdict(z) for z in self.zombies],
            "projectiles": [asdict(q) for q in self.projectiles],
            "pending_effects": {
                "basketballs": deepcopy(getattr(self, "_basketballs", [])),
                "garlic": deepcopy(getattr(self, "garlic_timers", {})),
                "boss": deepcopy(getattr(self, "_boss_state", {})),
            },
            "zombie_special_state": deepcopy(getattr(self, "_extended_zombie_state", {})),
            "plant_head_state": deepcopy(getattr(self, "_plant_head_state", {})),
            "active_hostile_zombies": sum(not z.hypnotized for z in self.active()),
            "active_friendly_zombies": sum(z.hypnotized for z in self.active()),
            "ladders": [{"row": row, "col": col} for row, col in sorted(self.ladders)],
            "events": dict(sorted(self.counts.items())),
        }
        return deepcopy(self._result)
