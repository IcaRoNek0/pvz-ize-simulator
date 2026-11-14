#!/usr/bin/env python3
"""Extract numeric idle body tracks from local Creative compiled resources."""

import argparse
import hashlib
import json
from pathlib import Path

from inspect_reanimations import decode_reanimation, summarize


ROOT = Path(__file__).resolve().parents[1]
ASSETS = {
    "peashooter": ("PeaShooterSingle", "anim_stem"),
    "repeater": ("PeaShooter", "anim_stem"),
    "snow_pea": ("SnowPea", "anim_stem"),
    "split_pea": ("SplitPea", "anim_idle"),
    "gatling_pea": ("GatlingPea", "anim_idle"),
}


def build(source):
    result = {"sampling": "REANIM_LOOP: phase * (frame_count - 1)", "tracks": {}}
    for kind, (asset, name) in ASSETS.items():
        path = source / f"{asset}.reanim.compiled"
        data = path.read_bytes()
        tracks, _ = decode_reanimation(data)
        segment = summarize(tracks)["animations"]["anim_idle"]
        start, count = segment["frame_start"], segment["frame_count"]
        result["tracks"][kind] = {
            "asset": path.name, "sha256": hashlib.sha256(data).hexdigest(),
            "track": name, "frame_start": start, "frame_count": count,
            "xy": [list(frame[:2]) for frame in tracks[name][start:start + count]],
        }
    return result


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source", type=Path, help="compiled/reanim directory")
    parser.add_argument("--output", type=Path, default=ROOT / "pvz_ize/plant_animation_tracks.json")
    args = parser.parse_args()
    args.output.write_text(json.dumps(build(args.source), indent=2) + "\n", encoding="utf-8")
