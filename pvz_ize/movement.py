"""Numeric ground-track motion, following Portable's reanimation formulas.

Only walking segments are modeled here; attacks and transitions keep their
explicit phase machines. These data are local transforms, not rendered assets.
"""

import json
from functools import lru_cache
from importlib.resources import files


@lru_cache(maxsize=1)
def tracks():
    return json.loads(files("pvz_ize").joinpath("movement_tracks.json").read_text())["tracks"]


def track_name(z):
    if z.type == "pea_head":
        return "Zombie/anim_walk2"
    if z.type in {"wallnut_head", "tallnut_head", "jalapeno_head", "gatling_head", "squash_head"}:
        return "Zombie/anim_walk2" if z.walk_variant == 0 else "Zombie/anim_walk"
    if z.type in {"normal", "conehead", "buckethead", "screen_door", "flag"}:
        return "Zombie/anim_walk2" if z.walk_variant == 0 else "Zombie/anim_walk"
    if z.type == "pole_vaulting":
        return "Zombie_polevaulter/anim_run" if z.phase == "pole_running" else "Zombie_polevaulter/anim_walk"
    if z.type == "ladder":
        return "Zombie_ladder/anim_ladderwalk" if z.tool else "Zombie_ladder/anim_walk"
    if z.type == "digger":
        return "Zombie_digger/anim_walk" if z.phase.startswith("digger_walking") else None
    if z.type in {"gargantuar", "red_eye_gargantuar"}:
        return "Zombie_gargantuar/anim_walk"
    if z.type == "newspaper":
        return "Zombie_paper/anim_walk_nopaper" if z.phase == "newspaper_mad" else "Zombie_paper/anim_walk"
    if z.type == "balloon":
        return "Zombie_balloon/anim_walk" if z.phase == "balloon_walking" else None
    if z.type == "pogo":
        return "Zombie_pogo/anim_walk" if not z.tool else None
    asset = {"football": "Zombie_football", "imp": "Zombie_imp"}.get(z.type)
    return f"{asset}/anim_walk" if asset else None


def _walk_rate(z):
    name = track_name(z)
    if name is None:
        return None
    xs = tracks()[name]
    n, distance = len(xs), xs[-1] - xs[0]
    # UpdateAnimSpeed: rate = mVelX * frameCount / groundDistance * 47.
    rate = z.velocity_parameter * n / distance * 47
    if z.chilled:
        rate *= .5
    return xs, rate


def advance_phase(z):
    walk = _walk_rate(z)
    if walk is not None:
        xs, rate = walk
        z.animation_phase = (z.animation_phase + .01 * rate / len(xs)) % 1


def displacement(z):
    walk = _walk_rate(z)
    if walk is None:
        return None
    xs, rate = walk
    n = len(xs)
    phase = z.animation_phase
    before = min(n - 1, int(phase * (n - 1)))
    after = min(n - 1, before + 1)
    speed = (xs[after] - xs[before]) * .01 * rate
    z.animation_phase = (phase + .01 * rate / n) % 1
    return speed
