"""Pea-family muzzle positions sampled from numeric body animation tracks."""

import json
from functools import lru_cache
from importlib.resources import files


TYPES = frozenset({"peashooter", "repeater", "snow_pea", "split_pea", "gatling_pea"})


@lru_cache(maxsize=1)
def tracks():
    return json.loads(files("pvz_ize").joinpath("plant_animation_tracks.json").read_text(encoding="utf-8"))["tracks"]


def sample_transform(kind, phase):
    """Interpolate ordinary LOOP frames, before C++ integer truncation."""
    xy = tracks()[kind]["xy"]
    position = (phase % 1) * (len(xy) - 1)
    before = int(position)
    after = min(before + 1, len(xy) - 1)
    fraction = position - before
    return tuple(a + (b - a) * fraction for a, b in zip(xy[before], xy[after]))


def muzzle_offset(plant, direction=1):
    x, y = sample_transform(plant.type, plant.animation_phase or 0)
    # GetPeaHeadOffset truncates the transform before Fire adds its constants.
    x, y = int(x), int(y)
    if direction < 0:
        if plant.type != "split_pea":
            raise ValueError("only split_pea has a rear muzzle")
        return x - 64, y - 33
    return x + (34 if plant.type == "gatling_pea" else 24), y - 33


def advance_phase(kind, phase, rate):
    return (phase + .01 * rate / tracks()[kind]["frame_count"]) % 1


def advance(plant):
    """Plant::UpdateReanim advances attached bodies after abilities."""
    plant.animation_phase = advance_phase(plant.type, plant.animation_phase or 0, plant.animation_rate)
