"""python3 -m unittest test_canarito"""
import base64
import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest import mock

import canarito

CONFIG = {"name": "home", "notify_url": "https://ntfy.sh/canarito-x", "language": "es",
          "notify_token": "", "heartbeat_url": "", "lat": 4.7, "lon": -74.1, "port": 5554}


class CanaritoTest(unittest.TestCase):
    def test_relay_config_sends_only_what_the_receptor_needs(self):
        relay = json.loads(canarito.relay_config(CONFIG))
        self.assertEqual(relay, {"name": "home", "notify_url": "https://ntfy.sh/canarito-x", "language": "es"})
        with_token = json.loads(canarito.relay_config({**CONFIG, "notify_token": "tk", "heartbeat_url": "https://hc/x"}))
        self.assertEqual(with_token["notify_token"], "tk")
        self.assertEqual(with_token["heartbeat_url"], "https://hc/x")

    def test_relay_file_is_written_from_an_argument_and_decodes_back(self):
        relay = canarito.relay_config(CONFIG)
        command = canarito.write_relay_command(relay)
        self.assertTrue(command.startswith("run-as app.canarito.receptor "))
        encoded = command.split("echo ", 1)[1].split(" ", 1)[0]
        self.assertEqual(base64.b64decode(encoded).decode(), relay)
        # Nothing the shell would expand inside the single quotes.
        self.assertNotIn("'", encoded)

    def test_picks_the_image_for_the_host_cpu(self):
        self.assertTrue(canarito.system_image("arm64").endswith(";arm64-v8a"))
        self.assertTrue(canarito.system_image("aarch64").endswith(";arm64-v8a"))
        self.assertTrue(canarito.system_image("x86_64").endswith(";x86_64"))
        self.assertIn("google_apis_playstore", canarito.system_image("x86_64"))

    def test_rejects_places_off_the_planet(self):
        canarito.check_coordinates(-33.45, -70.66)
        for lat, lon in ((91, 0), (0, 181), (-90.1, 0)):
            with self.assertRaises(ValueError):
                canarito.check_coordinates(lat, lon)
        with self.assertRaises(SystemExit):
            canarito.main(["setup", "--lat", "95", "--lon", "0"])

    def test_each_receptor_gets_its_own_port(self):
        with tempfile.TemporaryDirectory() as home, mock.patch.object(canarito, "CONFIG_DIR", Path(home)):
            self.assertEqual(canarito.free_port(), 5554)
            Path(home, "a.json").write_text(json.dumps({"port": 5554}))
            Path(home, "b.json").write_text("not json")
            self.assertEqual(canarito.free_port(), 5556)


class HealthTest(unittest.TestCase):
    def setUp(self):
        self.now = 1_000_000.0
        self.sent = []
        self.health = canarito.Health({"name": "casa", "avd": "canarito-casa", "language": "es"},
                                      lambda audience, text, priority: self.sent.append((audience, text)),
                                      clock=lambda: self.now)

    def test_tells_the_admin_once_when_it_starts_and_once_when_it_ends(self):
        self.health.problem("emulator_down")
        self.health.problem("emulator_down")
        self.health.tick()
        self.assertEqual([audience for audience, _ in self.sent], ["admin"])
        self.assertIn("casa", self.sent[0][1])
        self.health.clear("emulator_down")
        self.health.clear("emulator_down")
        self.assertEqual(len(self.sent), 2)
        self.assertIn("volvió", self.sent[1][1])

    def test_tells_the_family_only_after_an_hour_without_coverage(self):
        self.health.problem("aea")
        self.now += canarito.FAMILY_AFTER_S - 1
        self.health.tick()
        self.assertNotIn("family", [audience for audience, _ in self.sent])
        self.now += 2
        self.health.tick()
        self.health.tick()
        family = [text for audience, text in self.sent if audience == "family"]
        self.assertEqual(len(family), 1)
        self.assertIn("no tiene cobertura", family[0])

    def test_family_hears_it_is_back_only_when_every_problem_ended(self):
        self.health.problem("aea")
        self.health.problem("emulator_down")
        self.now += canarito.FAMILY_AFTER_S + 1
        self.health.tick()
        self.health.clear("aea")
        self.assertEqual(len([audience for audience, _ in self.sent if audience == "family"]), 1)
        self.health.clear("emulator_down")
        self.assertIn("volvió a tener cobertura", self.sent[-1][1])
        self.assertEqual(self.sent[-1][0], "family")

    def test_a_short_problem_never_reaches_the_family(self):
        self.health.problem("provision", error="boom")
        self.health.clear("provision")
        self.now += canarito.FAMILY_AFTER_S * 2
        self.health.tick()
        self.assertEqual([audience for audience, _ in self.sent], ["admin", "admin"])

    def test_every_problem_has_text_in_both_languages(self):
        for texts in canarito.NOTICES.values():
            for key in ("emulator_down", "aea", "provision"):
                self.assertIn(key, texts)
                self.assertIn(f"{key}_ok", texts)
        self.assertEqual(canarito.NOTICES["es"].keys(), canarito.NOTICES["en"].keys())

    def test_a_notice_that_cannot_go_out_does_not_stop_the_receptor(self):
        self.assertFalse(canarito.post_notice("http://127.0.0.1:1/x", "", "hola"))


if __name__ == "__main__":
    unittest.main()
