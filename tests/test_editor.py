import json
from http.server import ThreadingHTTPServer
import threading
import unittest
from urllib.request import Request, urlopen
from urllib.error import HTTPError

from pvz_ize.catalog import PLANTS, ZOMBIES
from pvz_ize.editor import Handler, catalog


class EditorTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        cls.thread = threading.Thread(target=cls.server.serve_forever, daemon=True)
        cls.thread.start()
        cls.base = f"http://127.0.0.1:{cls.server.server_port}"

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()
        cls.server.server_close()
        cls.thread.join()

    def request(self, path, body=None, **headers):
        data = json.dumps(body).encode() if body is not None else None
        request = Request(self.base + path, data=data, headers={"Content-Type": "application/json", **headers})
        try:
            response = urlopen(request)
        except HTTPError as error:
            response = error
        with response:
            return response.status, json.loads(response.read())

    def test_catalog_all_nonboss_units_and_editable_jack_field(self):
        status, data = self.request("/api/catalog")
        self.assertEqual(status, 200)
        self.assertEqual(set(data["plants"]), set(PLANTS))
        self.assertEqual(set(data["zombies"]), set(ZOMBIES) - {"boss"})
        self.assertIn("jack_countdown_frames", {f["name"] for f in data["zombie_fields"]})

    def test_packaged_static_assets(self):
        for route, content_type, marker in (("/", "text/html", b"formation-code"),
                                            ("/app.js", "text/javascript", b"jack_countdown_frames"),
                                            ("/style.css", "text/css", b"@media")):
            with urlopen(self.base + route) as response:
                self.assertEqual(response.status, 200)
                self.assertIn(content_type, response.headers["Content-Type"])
                self.assertIn(marker, response.read())

    def test_code_import_and_complete_json_roundtrip(self):
        status, data = self.request("/api/normalize", {"code": "P28|_|_|_|_|_|Z17|_|_"})
        self.assertEqual(status, 200)
        scenario = data["scenario"]
        self.assertEqual(scenario["plants"][0]["type"], "split_pea")
        self.assertEqual(scenario["zombies"][0]["type"], "digger")
        self.assertEqual(self.request("/api/normalize", {"scenario": scenario})[1], data)

    def test_jack_attribute_survives_json_import_and_prediction(self):
        scenario = {"max_frames": 200, "zombies": [{"type": "jack_in_the_box", "row": 3,
                    "x": 600, "jack_countdown_frames": 3}]}
        status, normalized = self.request("/api/normalize", {"code": json.dumps(scenario)})
        self.assertEqual(status, 200)
        self.assertEqual(normalized["scenario"]["zombies"][0]["jack_countdown_frames"], 3)
        status, result = self.request("/api/simulate", {"scenario": normalized["scenario"]})
        self.assertEqual((status, result["frames"], result["winner"]), (200, 113, "plants"))

    def test_bad_input_boss_and_cross_origin_rejected(self):
        self.assertEqual(self.request("/api/normalize", {"code": "bad"})[0], 400)
        self.assertEqual(self.request("/api/normalize", {"code": "_|_|_|_|_|_|Z25|_|_"})[0], 400)
        self.assertEqual(self.request("/api/normalize", {"code": "_|_|_|_|_|_|_|_|_"}, Origin="http://example.com")[0], 403)

    def test_frame_budget_does_not_force_winner(self):
        status, result = self.request("/api/simulate", {"scenario": {"max_frames": 1,
                    "zombies": [{"type": "normal", "row": 3, "col": 9}]}})
        self.assertEqual((status, result["winner"], result["reason"]), (200, "undecided", "max_frames_reached"))

    def test_all_roster_units_can_be_imported(self):
        for group, names in (("plants", PLANTS), ("zombies", set(ZOMBIES) - {"boss"})):
            for name in names:
                status, result = self.request("/api/normalize", {"scenario": {
                    group: [{"type": name, "row": 3, "col": 4}]}})
                self.assertEqual(status, 200, (group, name, result))
                self.assertEqual(result["scenario"][group][0]["type"], name)

    def test_stack_and_species_attributes_survive(self):
        scenario = {"allow_stacking": True, "plants": [
            {"type": "garlic", "row": 3, "col": 3, "hp": 100, "garlic_direction": "down"},
            {"type": "pumpkin", "row": 3, "col": 3, "hp": 1200}], "zombies": [
            {"type": "digger", "row": 3, "col": 6, "underground": False, "hypnotized": True},
            {"type": "buckethead", "row": 3, "col": 6, "helmet_hp": 200, "hp": 150}]}
        status, result = self.request("/api/normalize", {"scenario": scenario})
        self.assertEqual(status, 200)
        value = result["scenario"]
        self.assertEqual(value["plants"][0]["garlic_direction"], "down")
        self.assertEqual(value["plants"][1]["hp"], 1200)
        self.assertFalse(value["zombies"][0]["underground"])
        self.assertTrue(value["zombies"][0]["hypnotized"])
        self.assertEqual(value["zombies"][1]["helmet_hp"], 200)
