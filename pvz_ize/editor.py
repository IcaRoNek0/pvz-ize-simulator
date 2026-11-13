"""Local formation editor; the simulator parser is the validation authority."""

from dataclasses import asdict
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from importlib.resources import files
import json
from urllib.parse import urlsplit

from .batch import run_batch
from .catalog import MODEL, PLANTS, ZOMBIES
from .engine import Simulator
from .model import ScenarioError, parse_scenario


def field(name, type="integer", low=0, high=1000000, **extra):
    return {"name": name, "type": type, "min": low, "max": high, **extra}


def catalog():
    """Return the schema consumed by the web editor.

    Field definitions are deliberately data driven: adding a field here is
    enough for the inspector to render it without changing the UI code.
    """
    plant_fields = [field("id", "string"), field("row", low=1, high=5), field("col", low=1, high=9),
                    field("hp"), field("cooldown"), field("state_timer", description="部分瞬发植物的 0 使用默认准备时间；不是任意中途状态恢复。"),
                    field("layer", "enum", options=["main", "shell", "base"]),
                    field("garlic_direction", "enum", options=["random", "up", "down"], applies_to=["garlic"]),
                    field("animation_phase", "number", high=.9999999999999999),
                    field("animation_rate", "number", low=.001, high=100,
                          applies_to=["peashooter", "snow_pea", "repeater", "split_pea", "gatling_pea"])]
    zombie_fields = [field("id", "string"), field("row", low=1, high=5),
                     field("col", "number", low=1, high=9), field("x", "number", low=-1000, high=2000),
                     field("hp"), field("helmet_hp"), field("shield_hp"),
                     field("speed", "number", low=.001, high=5), field("age"),
                     *[field(name) for name in ("chilled", "buttered", "frozen")],
                     *[field(name, "boolean") for name in ("headless", "hypnotized", "tool")],
                     field("underground", "boolean", applies_to=["digger"]),
                     field("target_col", low=1, high=9, applies_to=["bungee"]),
                     field("animation_phase", "number", high=.9999999999999999),
                     field("velocity_parameter", "number", low=.001, high=5/.47),
                     field("walk_variant", low=0, high=1),
                     field("phase", "string", description="僵尸当前阶段；与 phase_timer 配合用于预置出发/爆炸阶段"),
                     field("phase_timer", high=10000000, description="阶段剩余帧；礼盒另用 jack_countdown_frames"),
                     field("jack_countdown_frames", high=10000000, applies_to=["jack_in_the_box"],
                           description="开盒前倒计时；0 为首帧开盒，之后还需 110 个未定身帧才爆炸。")]
    plants = {k: asdict(v) for k, v in PLANTS.items()}
    zombies = {k: asdict(v) for k, v in ZOMBIES.items() if k != "boss"}
    # Keep a machine-readable schema version and per-unit defaults in the
    # response.  The browser can display newly added catalog attributes from
    # this data, while parse_scenario remains the validation authority.
    return {"schema_version": 1, "model": MODEL, "plants": plants,
            "zombies": zombies, "plant_fields": plant_fields,
            "zombie_fields": zombie_fields,
            "rake_fields": [field("row", low=1, high=5), field("col", low=1, high=9)],
            "special_objects": {"rake": {"label": "钉耙", "asset": "/assets/rake.png", "one_shot": True},
                                "ladder_object": {"label": "场上梯子", "asset": "/assets/ladder_object.png"}}}


def initial(body):
    if not isinstance(body, dict):
        raise ScenarioError("请求必须是 JSON 对象")
    if "code" in body:
        code = body["code"]
        if not isinstance(code, str):
            raise ScenarioError("code 必须是九格代码或完整 JSON 文本")
        data = json.loads(code) if code.lstrip().startswith("{") else {
            "formation_code": code, "mode": "who_will_win"}
    else:
        data = body.get("scenario")
    scenario = parse_scenario(data)
    if any(z.type == "boss" for z in scenario.zombies):
        raise ScenarioError("本轮布阵器不包含僵王博士")
    return scenario, data


class Handler(BaseHTTPRequestHandler):
    def log_message(self, format, *args):
        pass

    def respond(self, status, value, content_type="application/json; charset=utf-8"):
        raw = (json.dumps(value, ensure_ascii=False, allow_nan=False).encode()
               if content_type.startswith("application/json") else value)
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(raw)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(raw)

    def do_GET(self):
        route = urlsplit(self.path).path
        if route == "/api/catalog":
            return self.respond(200, catalog())
        assets = {"/": ("index.html", "text/html; charset=utf-8"),
                  "/app.js": ("app.js", "text/javascript; charset=utf-8"),
                  "/style.css": ("style.css", "text/css; charset=utf-8")}
        if route.startswith("/assets/"):
            name = route.removeprefix("/assets/")
            if "/" in name or not name.endswith(".png"):
                return self.respond(404, {"error": "未找到资源"})
            path = files("pvz_ize").joinpath("web", "assets", name)
            try:
                return self.respond(200, path.read_bytes(), "image/png")
            except FileNotFoundError:
                return self.respond(404, {"error": "未找到资源"})
        if route not in assets:
            return self.respond(404, {"error": "未找到资源"})
        name, content_type = assets[route]
        return self.respond(200, files("pvz_ize").joinpath("web", name).read_bytes(), content_type)

    def do_POST(self):
        origin = self.headers.get("Origin")
        if origin and origin != f"http://{self.headers.get('Host')}":
            return self.respond(403, {"error": "只接受本地同源请求"})
        if self.headers.get("Content-Type", "").split(";")[0] != "application/json":
            return self.respond(415, {"error": "使用 application/json"})
        try:
            length = int(self.headers.get("Content-Length", 0))
            if not 0 < length <= 2 * 1024 * 1024:
                return self.respond(413, {"error": "输入为空或超过 2 MiB"})
            body = json.loads(self.rfile.read(length))
            route = urlsplit(self.path).path
            if route not in {"/api/normalize", "/api/simulate"}:
                return self.respond(404, {"error": "未找到接口"})
            scenario, data = initial(body)
            result = ({"scenario": scenario.to_dict()} if route == "/api/normalize" else
                      run_batch(data) if scenario.runs > 1 else Simulator(scenario).run())
            return self.respond(200, result)
        except (ScenarioError, ValueError, TypeError, UnicodeError) as error:
            return self.respond(400, {"error": str(error)})


def serve(port=8765):
    with ThreadingHTTPServer(("127.0.0.1", port), Handler) as server:
        print(f"布阵器：http://127.0.0.1:{server.server_port} （Ctrl+C 停止）", flush=True)
        try:
            server.serve_forever()
        except KeyboardInterrupt:
            pass
