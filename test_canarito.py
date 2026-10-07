"""python3 -m unittest test_canarito"""
import base64
import hashlib
import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest import mock

import canarito
import catalogs

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


# Chaparral, Colombia: the 23-Sep-2026 M4.5 reached an emulator 19.5 km away.
CHAPARRAL = (3.72, -75.48)
QUAKE_T = 1_790_190_000.0


def quake(source="USGS", mag=4.5, km_north=19.5, dt=0.0, ident="a"):
    return {"id": ident, "source": source, "time": QUAKE_T + dt, "mag": mag,
            "lat": CHAPARRAL[0] + km_north / 111.2, "lon": CHAPARRAL[1]}


class MissedQuakeTest(unittest.TestCase):
    def judge(self, events, early=(), late=(), now=QUAKE_T + 3600, reported=None):
        return catalogs.missed(events, *CHAPARRAL, list(early), list(late), now,
                               {} if reported is None else reported)

    def test_radius_follows_googles_table(self):
        self.assertEqual(catalogs.radius_km(4.4), 0)
        self.assertEqual(catalogs.radius_km(4.5), 31)
        self.assertAlmostEqual(catalogs.radius_km(5.05), 86, delta=0.5)
        self.assertEqual(catalogs.radius_km(9.0), 669)

    def test_a_quake_inside_the_radius_with_no_alert_is_missed(self):
        [(event, km, verdict)] = self.judge([quake()])
        self.assertEqual(verdict, "missed")
        self.assertAlmostEqual(km, 19.5, delta=0.5)

    def test_an_alert_soon_after_the_quake_means_nothing_to_report(self):
        self.assertEqual(self.judge([quake()], early=[QUAKE_T + 18]), [])

    def test_only_the_late_notice_is_reported_as_late(self):
        [(_, _, verdict)] = self.judge([quake()], late=[QUAKE_T + 321])
        self.assertEqual(verdict, "late")

    def test_inside_only_with_more_magnitude_is_possibly_missed(self):
        # M4.2 has no radius; M4.7 (4.2 + 0.5) reaches 45 km.
        [(_, _, verdict)] = self.judge([quake(mag=4.2, km_north=40)])
        self.assertEqual(verdict, "possibly")
        self.assertEqual(self.judge([quake(mag=4.2, km_north=60)]), [])

    def test_two_catalogs_are_one_quake_and_the_larger_magnitude_counts(self):
        [(event, _, verdict)] = self.judge([quake("USGS", mag=4.3, ident="u"), quake("EMSC", mag=4.6, dt=20, ident="e")])
        self.assertEqual(event["sources"], ["USGS", "EMSC"])
        self.assertEqual(verdict, "missed")

    def test_each_quake_is_judged_once_and_only_after_it_settles(self):
        reported = {}
        self.assertEqual(self.judge([quake()], now=QUAKE_T + 60, reported=reported), [])
        self.assertEqual(len(self.judge([quake()], reported=reported)), 1)
        self.assertEqual(self.judge([quake()], reported=reported), [])

    def test_national_catalogs_apply_only_inside_their_area(self):
        self.assertIn("sgc", catalogs.catalogs_for(4.711, -74.072))
        self.assertNotIn("sgc", catalogs.catalogs_for(-33.45, -70.66))
        self.assertEqual(catalogs.catalogs_for(35.68, 139.69), ["usgs", "emsc"])

    def test_reads_early_alerts_and_late_notices_from_the_evidence(self):
        evidence = "\n".join(json.dumps(e) for e in (
            {"event_type": "NOTIFICATION_POSTED", "channel_id": "eew_alert_v2", "captured_at_ms": 1000},
            {"event_type": "NOTIFICATION_POSTED", "channel_id": "eew_update", "captured_at_ms": 2000},
            {"event_type": "NOTIFICATION_POSTED", "channel_id": "finder", "captured_at_ms": 3000},
            {"event_type": "RELAY_ATTEMPT", "captured_at_ms": 4000})) + "\nnot json"
        self.assertEqual(canarito.alert_times(evidence), ([1.0], [2.0]))


class FollowingReceptorTest(unittest.TestCase):
    HOME = [("casa", 4.71, -74.07)]

    def setUp(self):
        self.now = 0.0
        self.follower = canarito.Follower(self.HOME, clock=lambda: self.now)

    def test_reads_owntracks_and_plain_positions_rounded_to_about_a_kilometer(self):
        self.assertEqual(canarito.parse_position('{"_type":"location","lat":4.711234,"lon":-74.072987,"tst":1}'), (4.71, -74.07))
        self.assertEqual(canarito.parse_position('{"lat":-33.4489,"lon":-70.6693}'), (-33.45, -70.67))
        self.assertIsNone(canarito.parse_position('{"_type":"status","android":{}}'))
        for bad in ('[1,2]', '{"lat":"4.7","lon":-74}', '{"lat":true,"lon":1}', '{"lat":95,"lon":0}', 'nope'):
            with self.assertRaises(ValueError):
                canarito.parse_position(bad)

    def test_moves_only_after_a_kilometer_and_five_minutes(self):
        self.follower.update(4.90, -74.07)  # about 21 km from home
        self.assertEqual(self.follower.step(), "move")
        self.follower.update(5.00, -74.07)  # 11 km more, but only a minute later
        self.now += 60
        self.assertIsNone(self.follower.step())
        self.now += canarito.MOVE_EVERY_S
        self.assertEqual(self.follower.step(), "move")
        self.follower.update(5.005, -74.07)  # 0.6 km more, long after
        self.now += canarito.MOVE_EVERY_S * 3
        self.assertIsNone(self.follower.step())

    def test_sleeps_after_half_an_hour_home_and_wakes_when_leaving(self):
        self.follower.update(4.72, -74.07)  # 1 km from home
        self.follower.step()
        self.now += canarito.ASLEEP_AFTER_S - 1
        self.assertNotEqual(self.follower.step(), "sleep")
        self.now += 1
        self.assertEqual(self.follower.step(), "sleep")
        self.assertEqual(self.follower.near, "casa")
        self.follower.update(4.73, -74.07)  # still home
        self.assertIsNone(self.follower.step())
        self.follower.update(4.80, -74.07)  # 10 km away
        self.assertEqual(self.follower.step(), "wake")
        self.assertEqual(self.follower.applied, (4.80, -74.07))

    def test_a_short_stop_at_home_does_not_put_it_to_sleep(self):
        self.follower.update(4.71, -74.07)
        self.follower.step()
        self.now += 600
        self.follower.update(4.90, -74.07)
        self.follower.step()
        self.now += canarito.ASLEEP_AFTER_S
        self.assertNotEqual(self.follower.step(), "sleep")

    def test_home_receptor_also_sends_to_people_sleeping_near_it(self):
        with tempfile.TemporaryDirectory() as home, mock.patch.object(canarito, "CONFIG_DIR", Path(home)):
            Path(home, "ana.status.json").write_text(json.dumps({"asleep": True, "near": "casa", "notify_url": "https://ntfy.sh/ana"}))
            Path(home, "luis.status.json").write_text(json.dumps({"asleep": False, "near": "casa", "notify_url": "https://ntfy.sh/luis"}))
            Path(home, "eva.status.json").write_text(json.dumps({"asleep": True, "near": "finca", "notify_url": "https://ntfy.sh/eva"}))
            self.assertEqual(canarito.sleeping_neighbours("casa"), ["https://ntfy.sh/ana"])
            Path(home, "casa.json").write_text(json.dumps({"name": "casa", "avd": "a", "lat": 4.7, "lon": -74.1, "port": 5554}))
            Path(home, "ana.json").write_text(json.dumps({"name": "ana", "avd": "b", "lat": 4.7, "lon": -74.1, "port": 5556, "follow": True}))
            self.assertEqual(canarito.fixed_receptors(), [("casa", 4.7, -74.1)])
            self.assertEqual(canarito.free_port(), 5558)
        relay = json.loads(canarito.relay_config(CONFIG, ["https://ntfy.sh/b", "https://ntfy.sh/a"]))
        self.assertEqual(relay["extra_urls"], ["https://ntfy.sh/a", "https://ntfy.sh/b"])
        self.assertNotIn("extra_urls", json.loads(canarito.relay_config(CONFIG)))

    def test_owntracks_link_carries_the_location_link(self):
        import urllib.parse
        link = canarito.owntracks_link("https://ntfy.sh/canarito-where-x?cache=no", "ana")
        self.assertTrue(link.startswith("owntracks:///config?inline="))
        settings = json.loads(base64.b64decode(urllib.parse.unquote(link.split("inline=", 1)[1])))
        self.assertEqual(settings["url"], "https://ntfy.sh/canarito-where-x?cache=no")
        self.assertEqual(settings["mode"], 3)


class SubscribeTextTest(unittest.TestCase):
    def test_the_topic_is_what_people_type_in_ntfy(self):
        self.assertEqual(canarito.topic_of("https://ntfy.sh/canarito-ab12"), "canarito-ab12")
        self.assertEqual(canarito.server_hint("https://ntfy.sh/canarito-ab12"), "")
        self.assertIn("https://ntfy.example.org", canarito.server_hint("https://ntfy.example.org/canarito-ab12"))


class ApkDownloadTest(unittest.TestCase):
    def test_a_file_with_another_hash_is_never_written(self):
        with tempfile.TemporaryDirectory() as folder:
            source = Path(folder) / "served.apk"
            source.write_bytes(b"tampered")
            target = Path(folder) / "out.apk"
            good = hashlib.sha256(b"tampered").hexdigest()
            self.assertFalse(canarito.verified_download(source.as_uri(), "0" * 64, target))
            self.assertFalse(target.exists())
            self.assertTrue(canarito.verified_download(source.as_uri(), good, target))
            self.assertEqual(target.read_bytes(), b"tampered")


if __name__ == "__main__":
    unittest.main()
