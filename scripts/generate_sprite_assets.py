#!/usr/bin/env python3
"""Render complete static PvZ portraits from the shipped reanimation layers.

The web editor needs one image per unit, while the game stores every unit as
many transparent ``reanim/*.png`` layers.  This exporter renders frame zero
of each reanimation, placing layers at their authored x/y anchors and cropping
to a padded square.  It intentionally renders a static portrait (not an
animation) and is therefore safe to run at build time without a browser.
"""
from __future__ import annotations

import argparse
import re
import xml.etree.ElementTree as ET
from pathlib import Path

from PIL import Image


REANIM_MAP = {
    "normal": ("Zombie", "base"), "flag": ("Zombie", "flag"),
    "conehead": ("Zombie", "cone"), "buckethead": ("Zombie", "bucket"),
    "screen_door": ("Zombie", "screen"), "football": ("Zombie_football", "all"),
    "pole_vaulting": ("Zombie_polevaulter", "all"), "ladder": ("Zombie_ladder", "all"),
    "digger": ("Zombie_digger", "all"), "dancing": ("Zombie_dancer", "all"),
    "backup_dancer": ("Zombie_dancer", "all"), "bungee": ("Zombie_bungi", "all"),
    "gargantuar": ("Zombie_gargantuar", "all"), "red_eye_gargantuar": ("Zombie_gargantuar", "all"),
    "imp": ("Zombie_imp", "all"), "zamboni": ("Zombie_zamboni", "all"),
    "catapult": ("Zombie_catapult", "all"), "balloon": ("Zombie_balloon", "all"),
    "newspaper": ("Zombie_paper", "all"), "jack_in_the_box": ("Zombie_jackbox", "all"),
    "pogo": ("Zombie_pogo", "all"), "yeti": ("Zombie_yeti", "all"),
}


def _value(node: ET.Element, name: str, default: float = 0.0) -> float:
    value = node.findtext(name)
    try:
        return float(value) if value is not None else default
    except ValueError:
        return default


def _image_path(reanim_dir: Path, image_ref: str) -> Path | None:
    # IMAGE_REANIM_ZOMBIE_FOO maps to reanim/Zombie_foo.png.  A few source
    # files use inconsistent capitalization, hence the case-insensitive pass.
    stem = image_ref.replace("IMAGE_REANIM_", "")
    files = {p.stem.lower(): p for p in reanim_dir.glob("*.png")}
    exact = files.get(stem.lower())
    if exact:
        return exact
    # Some tracks point to ``...OUTERLEG_FOOL`` while the file is ``...FOOT``.
    candidates = [p for key, p in files.items() if key.startswith(stem.lower())]
    return sorted(candidates, key=lambda p: len(p.name))[0] if candidates else None


def _keep_track(name: str, mode: str) -> bool:
    low = name.lower()
    # The base Zombie reanimation contains conditional pool/screen-door/
    # helmet layers.  Select the visual variant explicitly instead of
    # accidentally displaying every conditional layer at once.
    optional = ("screendoor", "duckytube", "flag", "cone", "bucket")
    if mode == "base":
        return not any(part in low for part in optional)
    if mode == "cone":
        return "bucket" not in low and "screendoor" not in low and "duckytube" not in low and "flag" not in low
    if mode == "bucket":
        return "cone" not in low and "screendoor" not in low and "duckytube" not in low and "flag" not in low
    if mode == "screen":
        return "cone" not in low and "bucket" not in low and "duckytube" not in low and "flag" not in low
    if mode == "flag":
        return "cone" not in low and "bucket" not in low and "screendoor" not in low and "duckytube" not in low
    return True


def render(name: str, source: Path, out: Path) -> None:
    reanim, mode = REANIM_MAP[name]
    # Flag zombie uses the ordinary body plus a separate flag-pole
    # reanimation in the original game.
    reanim_files = [reanim, "Zombie_FlagPole"] if name == "flag" else [reanim]
    # Keep source dimensions large enough for gargantuar and vehicles; crop
    # after compositing so no sprite part is discarded.
    canvas = Image.new("RGBA", (420, 420), (0, 0, 0, 0))
    for reanim_file in reanim_files:
      root = ET.fromstring("<root>" + (source / f"{reanim_file}.reanim").read_text(encoding="utf-8") + "</root>")
      for track in root.findall("track"):
        track_name = track.findtext("name") or ""
        if reanim_file != "Zombie_FlagPole" and not _keep_track(track_name, mode):
            continue
        # Some animations reserve frame zero for a hidden/death pose.  Pick
        # the first authored visible frame for each image track.
        frame = next((candidate for candidate in track.findall("t")
                      if candidate.findtext("f") != "-1" and candidate.findtext("i")), None)
        if frame is None:
            continue
        image_ref = frame.findtext("i")
        if not image_ref:
            continue
        image_path = _image_path(source, image_ref)
        if image_path is None:
            continue
        image = Image.open(image_path).convert("RGBA")
        sx, sy = _value(frame, "sx", 1.0), _value(frame, "sy", 1.0)
        image = image.resize((max(1, round(image.width * sx)), max(1, round(image.height * sy))), Image.Resampling.LANCZOS)
        x, y = 180 + _value(frame, "x"), 24 + _value(frame, "y")
        # Most idle frame-zero layers are axis aligned.  Applying skew here
        # would rotate around each layer's unknown pivot; retaining authored
        # pixels avoids seams and matches the Almanac's static pose.
        # Flag-pole coordinates are authored against the same zombie origin.
        canvas.alpha_composite(image, (round(x), round(y)))
    bbox = canvas.getbbox()
    if bbox is None:
        raise RuntimeError(f"no visible layers in {reanim}")
    crop = canvas.crop((max(0, bbox[0] - 8), max(0, bbox[1] - 8), min(canvas.width, bbox[2] + 8), min(canvas.height, bbox[3] + 8)))
    side = max(crop.size)
    square = Image.new("RGBA", (side, side), (0, 0, 0, 0))
    square.alpha_composite(crop, ((side - crop.width) // 2, (side - crop.height) // 2))
    square.save(out / f"{name}.png", optimize=True)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", type=Path, required=True, help="directory containing reanim/*.reanim and layer PNGs")
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=True)
    for name in REANIM_MAP:
        render(name, args.source, args.output)
        print(name, (args.output / f"{name}.png").stat().st_size)


if __name__ == "__main__":
    main()
