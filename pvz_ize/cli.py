"""Command-line entry points; diagnostics stay on stderr."""

import argparse
from contextlib import ExitStack
from dataclasses import asdict
import json
from pathlib import Path
import sys

from .catalog import MODEL, PLANTS, PLANT_ALIASES, WARNINGS, ZOMBIES, ZOMBIE_ALIASES
from .engine import Simulator
from .model import ScenarioError, parse_scenario
from .batch import run_batch


class Parser(argparse.ArgumentParser):
    def error(self, message):
        raise ScenarioError(message)


def parser():
    root = Parser(prog="pvz-ize", description="IZE / 谁会赢离线预测模拟器")
    commands = root.add_subparsers(dest="command", required=True, parser_class=Parser)
    run = commands.add_parser("run", help="运行 JSON 初态或直接布阵")
    run.add_argument("scenario", nargs="?", help="JSON 文件；- 表示标准输入")
    run.add_argument("--plant", action="append", default=[], metavar="TYPE,ROW,COL")
    run.add_argument("--zombie", action="append", default=[], metavar="TYPE,ROW,COL")
    run.add_argument("--zombie-x", action="append", default=[], metavar="TYPE,ROW,X")
    run.add_argument("--brain-row", action="append", type=int, help="脑子行号，可重复；默认 3")
    run.add_argument("--seed", type=int)
    run.add_argument("--max-frames", type=int)
    run.add_argument("--runs", type=int, help="独立模拟次数；覆盖 JSON runs（默认 1）")
    run.add_argument("--json", action="store_true", help="标准输出为完整 JSON")
    run.add_argument("--output", type=Path, help="另存完整 JSON 结果")
    run.add_argument("--trace", type=Path, help="逐事件 NDJSON 日志（非逐帧快照）")
    run.add_argument("--dump-initial", type=Path, help="保存可重新输入的实际初态")
    run.add_argument("--mode", choices=("ize", "who_will_win", "time_corridor"), help="覆盖场景模式")
    run.add_argument("--movement-mode", choices=("mean", "animation"))
    predict = commands.add_parser("predict", help="预测谁会赢九格代码")
    predict.add_argument("code", nargs="?", help="P0|_|Z0|... 九格代码；- 表示标准输入")
    predict.add_argument("--code-file", type=Path, help="从文本文件读取阵型代码")
    predict.add_argument("--row", type=int, default=3, help="布阵行，默认 3")
    predict.add_argument("--mode", choices=("ize", "who_will_win", "time_corridor"), default="who_will_win")
    # Share the execution options, not run's alternative placement inputs.
    for option in ("--seed", "--max-frames", "--runs"):
        predict.add_argument(option, type=int)
    predict.add_argument("--json", action="store_true")
    for option in ("--output", "--trace", "--dump-initial"):
        predict.add_argument(option, type=Path)
    predict.add_argument("--movement-mode", choices=("mean", "animation"))
    for command in (run, predict):
        command.add_argument("--time-limit-frames", type=int, help="显式截止帧；100 秒为 10000 帧")
        command.add_argument("--timeout-winner", choices=("plants", "zombies", "undecided"),
                             help="显式截止时的结果；不改变 max-frames 的未决语义")
    validate = commands.add_parser("validate", help="验证并显示规范化初态")
    validate.add_argument("scenario")
    validate.add_argument("--json", action="store_true")
    catalog = commands.add_parser("catalog", help="列出已实现单位及参数")
    catalog.add_argument("--json", action="store_true")
    editor = commands.add_parser("editor", help="打开本地可视化布阵器服务")
    editor.add_argument("--port", type=int, default=8765)
    return root


def _unique_object(pairs):
    obj = {}
    for key, value in pairs:
        if key in obj:
            raise ScenarioError(f"JSON: duplicate key {key!r}")
        obj[key] = value
    return obj


def load_json(path):
    content = sys.stdin.read() if path == "-" else Path(path).read_text(encoding="utf-8-sig")
    def invalid(value):
        raise ScenarioError(f"JSON: non-finite number {value}")
    return json.loads(content, object_pairs_hook=_unique_object, parse_constant=invalid)


def _placement(text, zombie=False, pixel=False):
    parts = [part.strip() for part in text.split(",")]
    if len(parts) != 3:
        raise ScenarioError(f"布阵格式应为 TYPE,ROW,{'X' if pixel else 'COL'}: {text!r}")
    coordinate = float(parts[2]) if zombie else int(parts[2])
    if zombie and not pixel and coordinate.is_integer():
        coordinate = int(coordinate)
    return {"type": parts[0], "row": int(parts[1]), "x" if pixel else "col": coordinate}


def _dump(data):
    return json.dumps(data, ensure_ascii=False, indent=2, allow_nan=False) + "\n"


def save(path, text):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def check_destinations(args):
    paths = [p.resolve() for p in (args.output, args.trace, args.dump_initial) if p]
    def same(a, b):
        return a == b or a.exists() and b.exists() and a.samefile(b)
    if any(same(a, b) for i, a in enumerate(paths) for b in paths[i+1:]):
        raise ScenarioError("输出、事件日志与初态必须使用不同文件")
    source = args.code_file if args.command == "predict" else args.scenario
    if source and str(source) != "-" and any(same(Path(source).resolve(), p) for p in paths):
        raise ScenarioError("输出文件不能覆盖输入场景")


def main(argv=None):
    try:
        args = parser().parse_args(argv)
        if args.command == "editor":
            from .editor import serve
            if not 0 <= args.port <= 65535:
                raise ScenarioError("port: expected 0..65535")
            serve(args.port)
            return 0
        if args.command == "catalog":
            from .creative import PLANT_CODES, ZOMBIE_CODES
            result = {"model": MODEL, "approximate": True, "warnings": WARNINGS,
                      "plants": {name: asdict(spec) for name, spec in PLANTS.items()},
                      "zombies": {name: asdict(spec) for name, spec in ZOMBIES.items()},
                      "plant_aliases": PLANT_ALIASES, "zombie_aliases": ZOMBIE_ALIASES,
                      "creative_codes": {**{f"P{k}": v for k, v in PLANT_CODES.items()},
                                         **{f"Z{k}": v for k, v in ZOMBIE_CODES.items()}},
                      "modes": {
                          "ize": "All configured brains and on-board hostile zombies; no game deadline.",
                          "who_will_win": "IZC row-3 terminal predicate; this iteration uses max_frames without an automatic game deadline.",
                          "time_corridor": "Fixed-initial-state phase 1 only; five brains, 10000 ticks."}}
            if args.json:
                print(_dump(result), end="")
            else:
                print("植物：" + ", ".join(PLANTS))
                print("僵尸：" + ", ".join(ZOMBIES))
                print("暂不支持的单位将报错，不会套用普通单位规则。")
            return 0
        if args.command == "validate":
            initial = parse_scenario(load_json(args.scenario))
            print(_dump(initial.to_dict()) if args.json else
                  f"场景有效：{len(initial.plants)} 株植物，{len(initial.zombies)} 只僵尸，"
                  f"{len(initial.brains)} 个脑子（{MODEL}，近似模型）", end="" if args.json else "\n")
            return 0
        if args.command == "predict":
            if bool(args.code is not None) == bool(args.code_file is not None):
                raise ScenarioError("predict: specify exactly one of CODE or --code-file")
            code = (args.code_file.read_text(encoding="utf-8-sig") if args.code_file else
                    sys.stdin.read() if args.code == "-" else args.code)
            data = {"formation_code": code, "formation_row": args.row,
                    "mode": args.mode}
        elif args.scenario:
            if args.plant or args.zombie or args.zombie_x or args.brain_row:
                raise ScenarioError("场景文件不能与直接布阵参数混用；seed/max-frames 可覆盖")
            data = load_json(args.scenario)
            if not isinstance(data, dict):
                raise ScenarioError("scenario: expected an object")
        else:
            data = {"plants": [_placement(p) for p in args.plant],
                    "zombies": [_placement(z, zombie=True) for z in args.zombie] +
                               [_placement(z, zombie=True, pixel=True) for z in args.zombie_x],
                    "brains": args.brain_row if args.brain_row is not None else [3]}
        if args.seed is not None:
            data["seed"] = args.seed
        if args.max_frames is not None:
            data["max_frames"] = args.max_frames
        if args.runs is not None:
            data["runs"] = args.runs
        if args.command == "run" and args.mode is not None:
            data["mode"] = args.mode
        if args.movement_mode is not None:
            data["movement_mode"] = args.movement_mode
        if args.time_limit_frames is not None:
            data["time_limit_frames"] = args.time_limit_frames
        if args.timeout_winner is not None:
            data["timeout_winner"] = args.timeout_winner
        initial = parse_scenario(data)
        check_destinations(args)
        if args.dump_initial and initial.runs == 1:
            save(args.dump_initial, _dump(initial.to_dict()))
        with ExitStack() as stack:
            sink = None
            if args.trace:
                args.trace.parent.mkdir(parents=True, exist_ok=True)
                stream = stack.enter_context(args.trace.open("w", encoding="utf-8"))
                def sink(event):
                    stream.write(json.dumps(event, ensure_ascii=False, allow_nan=False) + "\n")
            if initial.runs > 1:
                manifest = [] if args.dump_initial else None
                result = run_batch(data, event_sink=sink,
                                   initial_sink=manifest.append if manifest is not None else None)
                if args.dump_initial:
                    save(args.dump_initial, _dump({"batch_replay": True, "runs": manifest}))
            else:
                result = Simulator(initial, event_sink=sink).run()
        if args.output:
            save(args.output, _dump(result))
        if args.json:
            print(_dump(result), end="")
        elif result.get("batch"):
            print(f"完成 {result['runs']} 次模拟（样本频率，包含未决）")
            for key, label in (("plants", "植物获胜"), ("zombies", "僵尸获胜"), ("undecided", "未决")):
                outcome = result["outcomes"][key]
                lo, hi = outcome["wilson_95"]
                print(f"{label}：{outcome['count']} 次 / {outcome['probability']:.2%}；95% Wilson 区间 [{lo:.2%}, {hi:.2%}]")
            print(f"注意：{MODEL} 为近似模型；样本概率不等于原版真实概率。")
        else:
            winner = {"plants": "植物获胜", "zombies": "僵尸获胜", "undecided": "未决（达到帧数上限）"}[result["winner"]]
            print(f"{winner} | {result['frames']} 帧 / {result['seconds']:.2f} 秒")
            print("剩余脑子：" + (", ".join(f"第 {b['row']} 行 HP={b['hp']}" for b in result["brains"] if b["hp"] > 0) or "无"))
            states = {s: sum(z["status"] == s for z in result["zombies"])
                      for s in ("active", "dead", "entered_house", "exited")}
            print(f"僵尸：场上 {states['active']} / 死亡 {states['dead']} / 进家 {states['entered_house']} / 出界 {states['exited']}")
            print(f"场上阵营：敌方 {result['active_hostile_zombies']} / 魅惑友方 {result['active_friendly_zombies']}")
            print(f"注意：{MODEL} 为离线近似模型（{initial.movement_mode}），尚未与原版逐帧校准。")
        return 2 if (result["outcomes"]["undecided"]["count"] if result.get("batch")
                     else result["winner"] == "undecided") else 0
    except (OSError, ValueError, RecursionError) as exc:
        print(f"错误：{exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
