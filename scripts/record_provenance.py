"""Record local source revisions/hashes without redistributing game assets."""

import hashlib
import json
from pathlib import Path
import struct
import subprocess

ROOT = Path(__file__).resolve().parents[1]


def digest(path):
    h = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            h.update(chunk)
    return {"path": str(path.relative_to(ROOT)), "bytes": path.stat().st_size,
            "sha256": h.hexdigest()}


def revision(path):
    proc = subprocess.run(["git", "-C", str(path), "rev-parse", "HEAD"],
                          capture_output=True, text=True, check=False)
    return proc.stdout.strip() if proc.returncode == 0 else None


def main():
    paths = [
        "ref/PvZ-Portable/src/Lawn/Board.cpp",
        "ref/PvZ-Portable/src/Lawn/Challenge.cpp",
        "ref/PvZ-Portable/src/Lawn/Plant.cpp",
        "ref/PvZ-Portable/src/Lawn/Zombie.cpp",
        "ref/PvZ-Portable/src/Lawn/Projectile.cpp",
        "ref/PvZ-Portable/src/ConstEnums.h",
        "ref/PvZ-Portable/src/PvzpLib/Reanimator.cpp",
        "ref/rpze/src/rpze/iztest/consts.py",
        "ref/rpze/src/rpze/iztest/plant_modifier.py",
        "ref/rpze/src/rpze/iztest/iztest.py",
        "game/Plants vs. Zombies 1.0.0.1051 EN/PlantsVsZombies.exe",
        "game/Plants vs. Zombies 1.0.0.1051 EN/main.pak",
    ]
    files = [digest(ROOT / p) for p in paths if (ROOT / p).is_file()]
    exe = ROOT / paths[-2]
    machine = None
    if exe.is_file():
        with exe.open("rb") as stream:
            stream.seek(0x3C)
            offset, = struct.unpack("<I", stream.read(4))
            stream.seek(offset)
            if stream.read(4) == b"PE\x00\x00":
                machine, = struct.unpack("<H", stream.read(2))
    result = {
        "method": "static_source_inspection_asset_numeric_parsing_and_readonly_executable_disassembly",
        "original_game_executed": False,
        "portable_game_executed": False,
        "game_version_from_directory_label_only": "1.0.0.1051 EN",
        "pe_machine": hex(machine) if machine is not None else None,
        "references": {p: revision(ROOT / p) for p in ("ref/PvZ-Portable", "ref/rpze")},
        "files": files,
    }
    dest = ROOT / "outputs" / "provenance.json"
    dest.parent.mkdir(exist_ok=True)
    dest.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(dest)


if __name__ == "__main__":
    main()
