"""Line protocol worker used by the optional Rust batch coordinator."""
from __future__ import annotations
import json
import sys
from .batch import _run_replica


def main() -> None:
    for line in sys.stdin:
        try:
            request = json.loads(line)
            index = int(request["index"])
            scenario = request["scenario"]
            run_index, seed, initial, result = _run_replica((scenario, index))
            payload = {"index": run_index, "seed": seed, "initial": initial, "result": result}
            print(json.dumps(payload, ensure_ascii=False, allow_nan=False), flush=True)
        except Exception as exc:  # protocol errors must be one-line JSON
            print(json.dumps({"error": f"{type(exc).__name__}: {exc}"}, ensure_ascii=False), flush=True)


if __name__ == "__main__":
    main()
