#!/usr/bin/env python3
"""Inspect local PvZ 32-bit reanimations without exporting asset files."""

import argparse
import hashlib
import json
from pathlib import Path
import struct
import sys
import zlib


ROOT = Path(__file__).resolve().parents[1]
XOR_TABLE = bytes(value ^ 0xF7 for value in range(256))
DEFAULT_ASSETS = (
    "Zombie", "Zombie_football", "Zombie_imp", "Zombie_polevaulter",
    "Zombie_ladder", "Zombie_digger", "Zombie_bungi", "Zombie_Jackson",
    "Zombie_dancer", "PeaShooter", "PeaShooterSingle", "SnowPea", "SplitPea",
    "Chomper", "ScaredyShroom",
)
FIELDS = ("x", "y", "skew_x", "skew_y", "scale_x", "scale_y", "frame", "alpha")
DEFAULTS = (0, 0, 0, 0, 1, 1, 0, 1)


class Reader:
    def __init__(self, data):
        self.data, self.pos = data, 0

    def take(self, size):
        if size < 0 or self.pos + size > len(self.data):
            raise ValueError(f"truncated data at {self.pos}, requested {size} bytes")
        result = self.data[self.pos:self.pos + size]
        self.pos += size
        return result

    def unpack(self, fmt):
        return struct.unpack(fmt, self.take(struct.calcsize(fmt)))

    def u32(self):
        return self.unpack("<I")[0]

    def string(self):
        return self.take(self.u32()).decode("utf-8")


def sha256(data):
    return hashlib.sha256(data).hexdigest()


def read_pak(path):
    original = path.read_bytes()
    data = original.translate(XOR_TABLE)
    reader = Reader(data)
    magic, version = reader.unpack("<II")
    if (magic, version) != (0xBAC04AC0, 0):
        raise ValueError("unsupported PAK header")
    records, offset = {}, 0
    while True:
        flags = reader.take(1)[0]
        if flags & 0x80:
            break
        name = reader.take(reader.take(1)[0]).decode("utf-8").replace("\\", "/")
        size, timestamp = reader.unpack("<IQ")
        if name.lower() in records:
            raise ValueError(f"duplicate PAK member {name}")
        records[name.lower()] = {"name": name, "size": size,
                                 "offset": offset, "filetime": timestamp}
        offset += size
    if reader.pos + offset != len(data):
        raise ValueError("PAK index payload size mismatch")
    return data, records, {"path": str(path.resolve()), "sha256": sha256(original),
                           "size": len(original), "version": version,
                           "member_count": len(records), "payload_offset": reader.pos}


def decode_reanimation(compiled):
    cookie, expected_size = struct.unpack_from("<II", compiled)
    if cookie != 0xDEADFED4 or expected_size > 100_000_000:
        raise ValueError("unsupported compiled definition header")
    decompressor = zlib.decompressobj()
    raw = decompressor.decompress(compiled[8:], expected_size + 1)
    if len(raw) != expected_size or not decompressor.eof or decompressor.unused_data:
        raise ValueError("compiled definition decompression size/stream mismatch")
    reader = Reader(raw)
    schema_hash = reader.u32()
    if schema_hash != 0xB393B4C0:
        raise ValueError(f"unsupported 32-bit reanimation schema 0x{schema_hash:08x}")
    pointer, track_count, fps, atlas_pointer = reader.unpack("<IIfI")
    stride = reader.u32()
    if stride != 12 or not 0 < track_count < 1000:
        raise ValueError("only the original 32-bit reanimation layout is supported")
    headers = [reader.unpack("<III") for _ in range(track_count)]
    tracks, duplicate_names = {}, []
    for name_pointer, transforms_pointer, count in headers:
        name = reader.string()
        transform_stride = reader.u32()
        if transform_stride != 44 or not 0 < count < 100_000:
            raise ValueError(f"unsupported transform layout/count: {name}")
        if name in tracks:
            duplicate_names.append(name)
            suffix = 2
            while f"{name}#{suffix}" in tracks:
                suffix += 1
            name = f"{name}#{suffix}"
        frames = [list(reader.unpack("<8fIII")[:8]) for _ in range(count)]
        for _ in range(count):
            # Deep pointer fixups follow all raw transforms, not each transform.
            reader.string()
            reader.string()
            reader.string()
        previous = list(DEFAULTS)
        for frame in frames:
            for index, value in enumerate(frame):
                if value == -10000.0:
                    frame[index] = previous[index]
                else:
                    previous[index] = value
        tracks[name] = frames
    if reader.pos != len(raw):
        raise ValueError(f"definition has {len(raw) - reader.pos} trailing bytes")
    return tracks, {"schema_hash_hex": f"0x{schema_hash:08x}",
                    "compiled_sha256": sha256(compiled), "decoded_sha256": sha256(raw),
                    "compiled_size": len(compiled), "decoded_size": len(raw),
                    "definition_fps": fps, "track_count": track_count,
                    "track_stride": stride, "transform_stride": 44,
                    "bytes_consumed": reader.pos, "complete_parse": True,
                    "duplicate_track_names": duplicate_names}


def summarize(tracks):
    animations = {}
    ground = tracks.get("_ground")
    for name, frames in tracks.items():
        if not name.startswith("anim_"):
            continue
        visible = [i for i, frame in enumerate(frames) if frame[6] >= 0]
        start, end = (visible[0], visible[-1]) if visible else (0, 0)
        entry = {"frame_start": start, "frame_count": end - start + 1,
                 "frame_end_inclusive": end, "visible_count": len(visible)}
        if ground and end < len(ground):
            xs = [round(frame[0], 7) for frame in ground[start:end + 1]]
            entry["ground"] = {"first_x": xs[0], "last_x": xs[-1],
                               "min_x": min(xs), "max_x": max(xs),
                               "distance": round(xs[-1] - xs[0], 7), "x_by_frame": xs}
        animations[name] = entry
    interesting = {}
    for name, frames in tracks.items():
        if any(term in name.lower() for term in ("mouth", "projectile", "shoot", "locator")):
            interesting[name] = {
                "x_min": min(frame[0] for frame in frames),
                "x_max": max(frame[0] for frame in frames),
                "y_min": min(frame[1] for frame in frames),
                "y_max": max(frame[1] for frame in frames),
                "note": "Local track translation only; not a world-space projectile origin.",
            }
    starts = {}
    for animation in ("anim_idle", "anim_head_idle", "anim_full_idle", "anim_shooting"):
        if animation not in animations:
            continue
        index = animations[animation]["frame_start"]
        names = [name for name in tracks if any(term in name.lower() for term in
                 ("anim_stem", "anim_idle", "anim_head", "anim_face", "mouth", "body"))]
        starts[animation] = {name: dict(zip(FIELDS, tracks[name][index])) for name in names
                             if index < len(tracks[name])}
    return {"track_names": list(tracks), "animations": animations,
            "local_transform_bounds": interesting, "layer_start_transforms": starts}


def inspect(path, names, requested_tracks=(), requested_frames=()):
    data, records, pak_info = read_pak(path)
    output = {"format": "pvz-reanimation-inspection-v1", "pak": pak_info,
              "notes": ["Numeric metadata only; no full assets are exported.",
                        "frame_count is animation frames, not centiseconds; runtime animation rate is separate.",
                        "Ground x samples are inherited local transforms, not zombie world coordinates.",
                        "Original asset values plus Portable source semantics do not establish original executable equivalence."],
              "assets": {}}
    for name in names:
        member = f"compiled/reanim/{name}.reanim.compiled".lower()
        if member not in records:
            output["assets"][name] = {"error": "asset not present"}
            continue
        record = records[member]
        begin = pak_info["payload_offset"] + record["offset"]
        try:
            tracks, metadata = decode_reanimation(data[begin:begin + record["size"]])
            output["assets"][name] = {"member": record["name"],
                                       **metadata, **summarize(tracks)}
            if requested_tracks:
                queries = {}
                for track_name in requested_tracks:
                    if track_name not in tracks:
                        queries[track_name] = {"error": "track not present"}
                        continue
                    frames = tracks[track_name]
                    indices = requested_frames or (0,)
                    queries[track_name] = {
                        "transform_count": len(frames),
                        "samples": {str(i): dict(zip(FIELDS, frames[i])) for i in indices
                                    if 0 <= i < len(frames)},
                        "out_of_range_indices": [i for i in indices if not 0 <= i < len(frames)],
                    }
                output["assets"][name]["queried_tracks"] = queries
        except (ValueError, struct.error, zlib.error, UnicodeError) as exc:
            output["assets"][name] = {"member": record["name"], "error": str(exc)}
    return output


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--pak", type=Path)
    parser.add_argument("--asset", action="append", help="reanimation basename; repeatable")
    parser.add_argument("--track", action="append", default=[], help="exact track name; repeatable")
    parser.add_argument("--frame", action="append", type=int, default=[],
                        help="zero-based transform sample for --track; repeatable, default 0")
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    candidates = list((ROOT / "game").glob("*/main.pak"))
    if args.pak is None and len(candidates) != 1:
        parser.error("specify --pak when exactly one game/*/main.pak is not available")
    path = args.pak or candidates[0]
    if args.output and (args.output.resolve() == path.resolve() or
                        args.output.exists() and path.exists() and args.output.samefile(path)):
        parser.error("output cannot overwrite the PAK")
    try:
        result = inspect(path, args.asset or DEFAULT_ASSETS, args.track, args.frame)
        serialized = json.dumps(result, indent=2, ensure_ascii=False, allow_nan=False) + "\n"
        if args.output:
            args.output.parent.mkdir(parents=True, exist_ok=True)
            args.output.write_text(serialized, encoding="utf-8")
        else:
            print(serialized, end="")
        return 1 if any("error" in value for value in result["assets"].values()) else 0
    except (OSError, ValueError, struct.error, zlib.error) as exc:
        print(f"inspection failed: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
