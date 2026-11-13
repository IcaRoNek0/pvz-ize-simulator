"""Validated initial states. Public rows and columns are one-based."""

from dataclasses import asdict, dataclass, field
import math
import random

from .catalog import PLANTS, ZOMBIES, PLANT_ALIASES, ZOMBIE_ALIASES
from . import plant_animation


class ScenarioError(ValueError):
    pass


def _keys(value, allowed, path):
    if not isinstance(value, dict):
        raise ScenarioError(f"{path}: expected an object")
    extra = value.keys() - set(allowed)
    if extra:
        raise ScenarioError(f"{path}: unknown fields: {', '.join(sorted(extra))}")


def _number(value, path, low, high, integer=False):
    if (isinstance(value, bool) or not isinstance(value, (int, float))
            or not low <= value <= high or not math.isfinite(value)
            or (integer and not isinstance(value, int))):
        kind = "integer" if integer else "finite number"
        raise ScenarioError(f"{path}: expected {kind} in [{low}, {high}]")
    return value


def _int(value, path, low=0, high=1_000_000):
    return _number(value, path, low, high, integer=True)


def _list(value, path):
    if not isinstance(value, list):
        raise ScenarioError(f"{path}: expected an array")
    return value


def _animation_phase(item, path):
    if "animation_phase" not in item:
        return None
    value = _number(item["animation_phase"], f"{path}.animation_phase", 0, 1)
    if value == 1:
        raise ScenarioError(f"{path}.animation_phase: expected phase in [0, 1)")
    return value


@dataclass
class Plant:
    id: str
    type: str
    row: int
    col: int
    hp: int
    cooldown: int
    state_timer: int = 0
    shots: list = field(default_factory=list)
    target: str | None = None
    state: str = "ready"
    recently_eaten: int = 0
    layer: str = "main"
    garlic_direction: str = "random"
    animation_phase: float | None = None
    animation_rate: float | None = None

    @property
    def x(self):
        return 40 + 80 * (self.col - 1)

    @property
    def y(self):
        return 80 + 100 * (self.row - 1)


@dataclass
class Zombie:
    id: str
    type: str
    row: int
    x: float
    hp: int
    helmet_hp: int
    shield_hp: int
    speed: float
    age: int = 0
    chilled: int = 0
    headless: bool = False
    eating: bool = False
    status: str = "active"
    last_damage_age: int = 0
    phase: str = "initial"
    phase_timer: int = 0
    direction: int = -1
    target_col: int | None = None
    target: str | None = None
    tool: bool = True
    leader: str | None = None
    buttered: int = 0
    hypnotized: bool = False
    underground: bool | None = None
    animation_phase: float | None = None
    frozen: int = 0
    velocity_parameter: float | None = None
    walk_variant: int | None = None
    jack_countdown_frames: int | None = None


@dataclass
class Brain:
    row: int
    hp: int = 70


@dataclass
class Scenario:
    seed: int
    max_frames: int
    plants: list[Plant]
    zombies: list[Zombie]
    brains: list[Brain]
    runs: int = 1
    allow_stacking: bool = False
    movement_mode: str = "mean"
    magnet_distance_mode: str = "horizontal"
    mode: str = "ize"
    time_limit_frames: int | None = None
    timeout_winner: str = "undecided"
    # Optional one-shot lawn rakes.  Coordinates are public one-based cells.
    rakes: list[dict] = field(default_factory=list)
    # Persistent ladder grid items placed before the simulation starts.
    ladders: list[dict] = field(default_factory=list)

    def to_dict(self):
        return {
            "version": 2, "seed": self.seed, "max_frames": self.max_frames,
            "runs": self.runs, "allow_stacking": self.allow_stacking,
            "movement_mode": self.movement_mode,
            "magnet_distance_mode": self.magnet_distance_mode,
            "mode": self.mode,
            **({"time_limit_frames": self.time_limit_frames} if self.time_limit_frames is not None else {}),
            "timeout_winner": self.timeout_winner,
            "rakes": self.rakes,
            "ladders": self.ladders,
            "brains": [asdict(b) for b in self.brains],
            "plants": [{k: v for k, v in asdict(p).items() if k in {
                "id", "type", "row", "col", "hp", "cooldown", "state_timer",
                "layer", "animation_phase", "animation_rate"} and v is not None or
                k == "garlic_direction" and p.type == "garlic"}
                       for p in self.plants],
            "zombies": [{k: v for k, v in asdict(z).items() if k in {
                "id", "type", "row", "x", "hp", "helmet_hp", "shield_hp",
                "speed", "age", "chilled", "headless", "buttered", "hypnotized", "frozen", "tool"} or
                k in {"underground", "animation_phase", "velocity_parameter", "walk_variant", "jack_countdown_frames"} and v is not None or
                k == "target_col" and z.type == "bungee"} for z in self.zombies],
        }


def parse_scenario(data):
    _keys(data, {"version", "seed", "max_frames", "plants", "zombies", "brains", "runs", "allow_stacking", "movement_mode", "magnet_distance_mode", "mode", "formation_code", "formation_row", "time_limit_frames", "timeout_winner", "rakes", "ladders"}, "scenario")
    if "formation_code" in data:
        from .creative import decode_formation
        if "plants" in data or "zombies" in data:
            raise ScenarioError("formation_code cannot be combined with plants/zombies")
        data = {**data, **decode_formation(data["formation_code"], data.get("formation_row", 3))}
        data.setdefault("mode", "who_will_win")
        if data.get("mode") == "ize":
            data.setdefault("brains", [data.get("formation_row", 3)])
    elif "formation_row" in data:
        raise ScenarioError("formation_row requires formation_code")
    mode = data.get("mode", "ize")
    if not isinstance(mode, str) or mode not in {"ize", "who_will_win", "time_corridor"}:
        raise ScenarioError("mode: expected ize, who_will_win or time_corridor")
    time_limit = data.get("time_limit_frames", 10000 if mode == "time_corridor" else None)
    if time_limit is not None:
        time_limit = _int(time_limit, "time_limit_frames", 1, 10_000_000)
    timeout_winner = data.get("timeout_winner", "plants" if mode == "time_corridor" else "undecided")
    if not isinstance(timeout_winner, str) or timeout_winner not in {"plants", "zombies", "undecided"}:
        raise ScenarioError("timeout_winner: expected plants, zombies or undecided")
    if type(data.get("version", 1)) is not int or data.get("version", 1) not in {1, 2}:
        raise ScenarioError("version: only versions 1 and 2 are supported")
    seed = _int(data.get("seed", 0), "seed", -2**63, 2**63 - 1)
    max_frames = _int(data.get("max_frames", 100_000), "max_frames", 1, 10_000_000)
    runs = _int(data.get("runs", 1), "runs", 1, 100_000)
    allow_stacking = data.get("allow_stacking", False)
    if not isinstance(allow_stacking, bool):
        raise ScenarioError("allow_stacking: expected boolean")
    movement_mode = data.get("movement_mode", "mean" if mode == "ize" else "animation")
    if not isinstance(movement_mode, str) or movement_mode not in {"mean", "animation"}:
        raise ScenarioError("movement_mode: expected mean or animation")
    magnet_distance_mode = data.get("magnet_distance_mode", "horizontal")
    if not isinstance(magnet_distance_mode, str) or magnet_distance_mode not in {"horizontal", "source"}:
        raise ScenarioError("magnet_distance_mode: expected horizontal or source")
    rakes = []
    for i, item in enumerate(_list(data.get("rakes", []), "rakes")):
        path = f"rakes[{i}]"
        _keys(item, {"row", "col"}, path)
        rakes.append({"row": _int(item.get("row"), f"{path}.row", 1, 5),
                      "col": _int(item.get("col", 8), f"{path}.col", 1, 9)})
    ladders = []
    for i, item in enumerate(_list(data.get("ladders", []), "ladders")):
        path = f"ladders[{i}]"
        _keys(item, {"row", "col"}, path)
        ladders.append({"row": _int(item.get("row"), f"{path}.row", 1, 5),
                        "col": _int(item.get("col"), f"{path}.col", 1, 9)})
    rng = random.Random(seed)
    plants, zombies, brains = [], [], []
    occupied, ids = set(), set()

    def identifier(item, default):
        ident = item.get("id", default)
        if not isinstance(ident, str) or not ident or ident in ids:
            raise ScenarioError(f"{default}.id: expected a nonempty globally unique string")
        ids.add(ident)
        return ident

    def unit_type(item, specs, aliases, path):
        raw = item.get("type")
        if not isinstance(raw, str):
            raise ScenarioError(f"{path}.type: expected a supported type name")
        name = aliases.get(raw, raw)
        if name not in specs:
            raise ScenarioError(f"{path}.type: unsupported type {raw!r}; use 'catalog' to list supported types")
        return name

    for i, item in enumerate(_list(data.get("plants", []), "plants")):
        path = f"plants[{i}]"
        _keys(item, {"id", "type", "row", "col", "hp", "cooldown", "state_timer",
                     "layer", "garlic_direction", "animation_phase", "animation_rate"}, path)
        name = unit_type(item, PLANTS, PLANT_ALIASES, path)
        row = _int(item.get("row"), f"{path}.row", 1, 5)
        col = _int(item.get("col"), f"{path}.col", 1, 9)
        layer = item.get("layer", "shell" if name == "pumpkin" else
                         "base" if name in {"lily_pad", "flower_pot"} else "main")
        if not isinstance(layer, str) or layer not in {"base", "main", "shell"}:
            raise ScenarioError(f"{path}.layer: expected base, main or shell")
        footprint = [(row, col, layer)]
        if name == "cob_cannon":
            if col >= 9:
                raise ScenarioError(f"{path}.col: cob_cannon occupies columns col and col+1; left column must be 1..8")
            footprint.append((row, col + 1, layer))
        if not allow_stacking and any(slot in occupied for slot in footprint):
            raise ScenarioError(f"{path}: duplicate plant layer or cob cannon footprint; set allow_stacking=true for explicit same-layer stacking")
        occupied.update(footprint)
        garlic_direction = item.get("garlic_direction", "random")
        if not isinstance(garlic_direction, str) or garlic_direction not in {"up", "down", "random"}:
            raise ScenarioError(f"{path}.garlic_direction: expected up, down or random")
        if "garlic_direction" in item and name != "garlic":
            raise ScenarioError(f"{path}.garlic_direction: only garlic supports this option")
        animation_phase = _animation_phase(item, path)
        animation_rate = (_number(item["animation_rate"], f"{path}.animation_rate", .001, 100)
                          if "animation_rate" in item else None)
        if animation_rate is not None and name not in plant_animation.TYPES:
            raise ScenarioError(f"{path}.animation_rate: unsupported plant body animation")
        spec = PLANTS[name]
        # A seeded equilibrium phase, not the original game's random stream.
        cooldown = item.get("cooldown")
        if cooldown is None and "cooldown" not in item:
            if name == "cob_cannon":
                cooldown = 500
            else:
                cooldown = (rng.choices(range(1, spec.period + 1),
                        weights=[min(15, spec.period + 1 - n)
                                 for n in range(1, spec.period + 1)])[0]
                        if spec.windup else 0)
        plants.append(Plant(identifier(item, f"p{i+1}"), name, row, col,
                            _int(item.get("hp", spec.hp), f"{path}.hp", 0, spec.hp),
                            _int(cooldown, f"{path}.cooldown"),
                            _int(item.get("state_timer", 0), f"{path}.state_timer"),
                            layer=layer, garlic_direction=garlic_direction,
                            animation_phase=animation_phase, animation_rate=animation_rate))

    # Resolve body rates after the existing initialization draws, preserving the
    # random stream used for attack timers in mean-movement scenarios.
    if movement_mode == "animation":
        for plant in plants:
            if plant.type in plant_animation.TYPES:
                if plant.animation_phase is None:
                    plant.animation_phase = 0.0
                if plant.animation_rate is None:
                    plant.animation_rate = rng.uniform(15, 20)

    for i, item in enumerate(_list(data.get("zombies", []), "zombies")):
        path = f"zombies[{i}]"
        _keys(item, {"id", "type", "row", "col", "x", "hp", "helmet_hp", "shield_hp",
                     "speed", "age", "chilled", "headless", "buttered", "target_col",
                     "hypnotized", "underground", "animation_phase", "velocity_parameter", "walk_variant", "frozen", "tool", "phase", "phase_timer", "jack_countdown_frames"}, path)
        name = unit_type(item, ZOMBIES, ZOMBIE_ALIASES, path)
        spec = ZOMBIES[name]
        jack_countdown = (_int(item["jack_countdown_frames"], f"{path}.jack_countdown_frames", 0, 10000000)
                          if "jack_countdown_frames" in item else None)
        phase_name = item.get("phase", "initial")
        if not isinstance(phase_name, str) or len(phase_name) > 64:
            raise ScenarioError(f"{path}.phase: expected a short phase name")
        phase_timer = _int(item.get("phase_timer", 0), f"{path}.phase_timer", 0, 10000000)
        if jack_countdown is not None and name != "jack_in_the_box":
            raise ScenarioError(f"{path}.jack_countdown_frames: only jack_in_the_box supports this option")
        row = _int(item.get("row"), f"{path}.row", 1, 5)
        if ("x" in item) == ("col" in item):
            raise ScenarioError(f"{path}: specify exactly one of x or col")
        x = (_number(item["x"], f"{path}.x", -1000, 2000) if "x" in item
             else 40 + spec.spawn_offset + 80 * (
                 _number(item["col"], f"{path}.col", 1, 9, integer=name == "bungee") - 1))
        if name == "boss":
            # The supplied IZC placement wrapper forces native row/column zero.
            x, row = 0.0, 1
        target_col = None
        if name == "bungee":
            target_col = _int(item.get("target_col", max(1, min(9, round((x - 40) / 80) + 1))),
                              f"{path}.target_col", 1, 9)
        elif "target_col" in item:
            raise ScenarioError(f"{path}.target_col: only bungee has a target column")
        hp = _int(item.get("hp", spec.hp), f"{path}.hp", 0, spec.hp)
        headless = item.get("headless", False)
        if not isinstance(headless, bool):
            raise ScenarioError(f"{path}.headless: expected boolean")
        hypnotized = item.get("hypnotized", False)
        if not isinstance(hypnotized, bool):
            raise ScenarioError(f"{path}.hypnotized: expected boolean")
        tool = item.get("tool", True)
        if not isinstance(tool, bool):
            raise ScenarioError(f"{path}.tool: expected boolean")
        underground = item.get("underground", True if name == "digger" else None)
        if "underground" in item and name != "digger":
            raise ScenarioError(f"{path}.underground: only digger supports this option")
        if name == "digger" and not isinstance(underground, bool):
            raise ScenarioError(f"{path}.underground: expected boolean")
        animation_phase = _animation_phase(item, path)
        velocity_parameter = (_number(item["velocity_parameter"], f"{path}.velocity_parameter", .001, 5 / .47)
                              if "velocity_parameter" in item else None)
        walk_variant = (_int(item["walk_variant"], f"{path}.walk_variant", 0, 1)
                        if "walk_variant" in item else None)
        if movement_mode == "animation":
            if animation_phase is None:
                animation_phase = rng.uniform(0, .99)
            if walk_variant is None:
                walk_variant = 0 if name in {"flag", "pea_head", "gatling_head", "squash_head"} else rng.randrange(2)
            if velocity_parameter is None:
                if "speed" in item:
                    # Explicit mean speed remains an intentional velocity override.
                    velocity_parameter = _number(item["speed"], f"{path}.speed", .001, 5) / (
                        1 if name == "pogo" and tool else .47)
                elif name == "digger" and not underground:
                    velocity_parameter = .23
                elif name in {"pole_vaulting", "ladder"} and (
                        not tool or name == "ladder" and item.get("shield_hp", spec.shield) == 0):
                    velocity_parameter = rng.uniform(.23, .37)
                elif name == "newspaper" and item.get("shield_hp", spec.shield) == 0:
                    velocity_parameter = rng.uniform(.89, .91)
                elif name in {"football", "pole_vaulting", "digger", "jack_in_the_box"}:
                    velocity_parameter = rng.uniform(.66, .68)
                elif name == "ladder":
                    velocity_parameter = rng.uniform(.79, .81)
                elif name == "squash_head":
                    velocity_parameter = rng.uniform(.79, .81)
                elif name == "imp":
                    velocity_parameter = .9
                elif name in {"flag", "pogo", "dancing", "backup_dancer"}:
                    velocity_parameter = .45
                elif name in {"normal", "conehead", "buckethead", "screen_door", "newspaper",
                               "gargantuar", "red_eye_gargantuar", "balloon", "pea_head",
                               "gatling_head", "wallnut_head", "tallnut_head", "jalapeno_head"}:
                    velocity_parameter = rng.uniform(.23, .37)
                else:
                    # Preserve normalization for units whose motion has no track.
                    velocity_parameter = spec.speed / .47
        zombies.append(Zombie(
            identifier(item, f"z{i+1}"), name, row, float(x), hp,
            _int(item.get("helmet_hp", spec.helmet), f"{path}.helmet_hp", 0, spec.helmet),
            _int(item.get("shield_hp", spec.shield), f"{path}.shield_hp", 0, spec.shield),
            _number(item.get("speed", spec.speed), f"{path}.speed", 0.001, 5),
            _int(item.get("age", 0), f"{path}.age"),
            _int(item.get("chilled", 0), f"{path}.chilled"),
            headless or (getattr(spec, "can_lose_head", name not in {
                "gargantuar", "red_eye_gargantuar", "catapult", "zamboni", "bungee", "balloon"})
                         and hp < spec.hp // 3) or (name == "balloon" and not tool and hp < spec.hp // 3),
            target_col=target_col,
            buttered=_int(item.get("buttered", 0), f"{path}.buttered"),
            hypnotized=hypnotized, underground=underground,
            animation_phase=animation_phase, velocity_parameter=velocity_parameter,
            walk_variant=walk_variant,
            phase=phase_name if phase_name != "initial" else ("digger_walking" if name == "digger" and not underground else "initial"),
            phase_timer=phase_timer,
            direction=1 if name == "digger" and not underground else -1,
            tool=tool, frozen=_int(item.get("frozen", 0), f"{path}.frozen"),
            jack_countdown_frames=jack_countdown,
        ))
        if name == "digger" and not underground and "speed" not in item:
            zombies[-1].speed = 0.11

    rows = set()
    for i, item in enumerate(_list(data.get("brains", [1, 2, 3, 4, 5] if mode == "time_corridor" else [3]), "brains")):
        path = f"brains[{i}]"
        if isinstance(item, dict):
            _keys(item, {"row", "hp"}, path)
            row = _int(item.get("row"), f"{path}.row", 1, 5)
            hp = _int(item.get("hp", 70), f"{path}.hp", 1, 70)
        else:
            row, hp = _int(item, path, 1, 5), 70
        if row in rows:
            raise ScenarioError(f"{path}: duplicate brain row")
        rows.add(row)
        brains.append(Brain(row, hp))
    if not brains:
        raise ScenarioError("brains: at least one initial brain is required")
    if mode == "who_will_win" and rows != {3}:
        raise ScenarioError("who_will_win: the supplied game judges only row 3; brains must be [3]")
    return Scenario(seed, max_frames, plants, zombies, brains, runs, allow_stacking, movement_mode,
                    magnet_distance_mode, mode, time_limit, timeout_winner, rakes, ladders)
