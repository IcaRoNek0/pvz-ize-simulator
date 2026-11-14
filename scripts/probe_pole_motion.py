"""Observe collision X and the first tall-nut block tick, without graphics."""

import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from tests.test_ground_special import Board, plant, unit
from pvz_ize import ground_special as ground


def probe(kind, chilled=0):
    sim = Board([plant(kind)])
    z = unit("pole_vaulting", x=198, chilled=chilled)
    rows = []
    for tick in range(1, 402):
        ground.update(sim, z)
        if tick in (1, 90, 108, 109, 180, 181) or z.phase == "pole_walking":
            rows.append({"tick": tick, "x": z.x, "phase": z.phase})
        if z.phase == "pole_walking":
            break
    return {"kind": kind, "chilled": bool(chilled), "observations": rows,
            "events": [name for name, _ in sim.events]}


if __name__ == "__main__":
    print(json.dumps([probe("wallnut"), probe("tallnut"), probe("wallnut", 1000)], indent=2))
