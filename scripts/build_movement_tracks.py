"""Build compact numeric walking tracks from the retained asset inspections."""

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def main():
    tracks, sources = {}, {}
    for filename in ("reanimation-inspection.json", "extended-zombie-reanimations.json",
                     "who-will-win/pogo/reanimations.json"):
        inspection = json.loads((ROOT / "outputs" / filename).read_text())
        for asset, metadata in inspection["assets"].items():
            for name, animation in metadata["animations"].items():
                ground = animation.get("ground")
                if ground and ground["distance"] > 0 and ("walk" in name or name == "anim_run"):
                    tracks[f"{asset}/{name}"] = ground["x_by_frame"]
                    sources[asset] = metadata["compiled_sha256"]
    target = ROOT / "pvz_ize" / "movement_tracks.json"
    target.write_text(json.dumps({"sources": sources, "tracks": tracks}, indent=2) + "\n")
    print(target)


if __name__ == "__main__":
    main()
