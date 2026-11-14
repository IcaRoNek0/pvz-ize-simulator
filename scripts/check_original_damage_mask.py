"""Verify the retained off-ground branch against local PE bytes, without execution."""

import hashlib
import json
from pathlib import Path
import struct

ROOT = Path(__file__).resolve().parents[1]


def main():
    path = ROOT / "game/Plants vs. Zombies 1.0.0.1051 EN/PlantsVsZombies.exe"
    data = path.read_bytes()
    pe, = struct.unpack_from("<I", data, 0x3c)
    if data[pe:pe+4] != b"PE\0\0":
        raise ValueError("not a PE executable")
    machine, count = struct.unpack_from("<HH", data, pe + 4)
    optional_size, = struct.unpack_from("<H", data, pe + 20)
    base, = struct.unpack_from("<I", data, pe + 24 + 28)
    sections = pe + 24 + optional_size

    def read_va(address, length):
        rva = address - base
        for index in range(count):
            offset = sections + index * 40
            virtual_size, virtual_address, size, raw = struct.unpack_from("<IIII", data, offset + 8)
            if virtual_address <= rva and rva + length <= virtual_address + size:
                start = raw + rva - virtual_address
                return data[start:start+length]
        raise ValueError(f"unmapped VA {address:#x}")

    checks = {0x531c74: "8ac3c0e8045f2401", 0x531c29: "f6c340", 0x531c32: "f6c302"}
    observed = []
    for address, expected in checks.items():
        actual = read_va(address, len(bytes.fromhex(expected))).hex()
        observed.append({"va": hex(address), "expected": expected, "actual": actual, "match": actual == expected})
    result = {"file": str(path.relative_to(ROOT)), "sha256": hashlib.sha256(data).hexdigest(),
              "machine": hex(machine), "executed": False, "checks": observed,
              "off_ground_mask": "0x10", "off_ground_branch": "mov al,bl; shr al,4; pop edi; and al,1",
              "scope": "Static branch check for this local binary only; not runtime or full-game equivalence."}
    dest = ROOT / "outputs/alignment/static-check.json"
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text(json.dumps(result, indent=2) + "\n")
    if not all(check["match"] for check in observed):
        raise ValueError("local binary differs from the inspected build")
    print(dest)


if __name__ == "__main__":
    main()
