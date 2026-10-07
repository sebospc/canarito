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


if __name__ == "__main__":
    unittest.main()
