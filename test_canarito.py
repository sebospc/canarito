"""python3 -m unittest test_canarito"""
import base64
import hmac
import hashlib
import urllib.error
import urllib.parse
import json
import os
import tempfile
import time
import unittest
from pathlib import Path
from unittest import mock

import appserver
import canarito
import catalogs
import qr

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

    def test_a_lost_location_is_not_told_to_the_family_as_no_coverage(self):
        self.health.problem("location_stale")
        self.now += canarito.FAMILY_AFTER_S * 5
        self.health.tick()
        self.assertEqual([audience for audience, _ in self.sent], ["admin"])
        self.health.problem("aea")
        self.now += canarito.FAMILY_AFTER_S + 1
        self.health.tick()
        self.health.clear("aea")
        self.assertEqual([audience for audience, _ in self.sent][-1], "family")
        self.assertIn("volvió a tener cobertura", self.sent[-1][1])

    def test_says_when_it_was_off_and_tells_the_family_only_when_it_was_long(self):
        canarito.down_notice(self.health, None, self.now, None)
        canarito.down_notice(self.health, self.now - 60, self.now, None)
        self.assertEqual(self.sent, [])
        canarito.down_notice(self.health, self.now - 600, self.now, self.now - 300)
        self.assertEqual([audience for audience, _ in self.sent], ["admin"])
        self.assertIn("se reinició", self.sent[0][1])
        canarito.down_notice(self.health, self.now - canarito.FAMILY_AFTER_S - 1, self.now, None)
        self.assertEqual([audience for audience, _ in self.sent], ["admin", "admin", "family"])
        self.assertNotIn("se reinició", self.sent[1][1])

    def test_morning_message_once_a_day_from_one_receptor_with_every_state(self):
        with tempfile.TemporaryDirectory() as home, mock.patch.object(canarito, "CONFIG_DIR", Path(home)):
            for name in ("ana", "beto", "carla", "dani"):
                Path(home, f"{name}.json").write_text(json.dumps({"name": name, "avd": name}))
                Path(home, f"{name}.alive").write_text(str(self.now))
            Path(home, "dani.alive").write_text(str(self.now - 3600))
            canarito.write_status("ana", covered=True)
            canarito.write_status("beto", covered=False, relay_by="ana")
            canarito.write_status("carla", covered=False)
            morning = time.mktime(time.localtime(self.now)[:3] + (9, 0, 0, 0, 0, -1))
            for path in Path(home).glob("*.alive"):
                path.write_text(str(morning - (3600 if path.name == "dani.alive" else 0)))
            canarito.maybe_daily({"name": "beto"}, self.health, morning)
            self.assertEqual(self.sent, [])
            canarito.maybe_daily({"name": "ana"}, self.health, morning - 2 * 3600)
            self.assertEqual(self.sent, [])
            canarito.maybe_daily({"name": "ana"}, self.health, morning)
            canarito.maybe_daily({"name": "ana"}, self.health, morning + 60)
            self.assertEqual(len(self.sent), 1)
            text = self.sent[0][1]
            for line in ("ana: cubierto", "beto: cubierto por el receptor de ana", "carla: SIN COBERTURA", "dani: NO RESPONDE"):
                self.assertIn(line, text)

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

    def test_never_sleeps_on_a_home_receptor_that_cannot_get_alerts(self):
        # 9-oct-2026: a phone slept on "casa" while casa had no AEA, and a M8 quake went unheard.
        home_ok = {"casa": False}
        follower = canarito.Follower(self.HOME, clock=lambda: self.now, home_covered=lambda name: home_ok[name])
        follower.update(4.72, -74.07)
        follower.step()
        self.now += canarito.ASLEEP_AFTER_S * 3
        self.assertNotEqual(follower.step(), "sleep")
        home_ok["casa"] = True
        follower.step()
        self.now += canarito.ASLEEP_AFTER_S
        self.assertEqual(follower.step(), "sleep")
        home_ok["casa"] = False
        self.assertEqual(follower.step(), "wake")

    def test_home_coverage_comes_from_the_fixed_receptor_status_and_missing_means_no(self):
        with tempfile.TemporaryDirectory() as home, mock.patch.object(canarito, "CONFIG_DIR", Path(home)):
            self.assertFalse(canarito.home_covered("casa"))
            Path(home, "casa.status.json").write_text(json.dumps({"covered": True}))
            self.assertTrue(canarito.home_covered("casa"))
            Path(home, "casa.status.json").write_text(json.dumps({"covered": False}))
            self.assertFalse(canarito.home_covered("casa"))
            Path(home, "casa.status.json").write_text("garbage")
            self.assertFalse(canarito.home_covered("casa"))

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
            Path(home, "ana.status.json").write_text(json.dumps({"asleep": True, "relay_by": "casa", "notify_url": "https://ntfy.sh/ana"}))
            Path(home, "luis.status.json").write_text(json.dumps({"asleep": False, "relay_by": None, "notify_url": "https://ntfy.sh/luis"}))
            Path(home, "eva.status.json").write_text(json.dumps({"asleep": True, "relay_by": "finca", "notify_url": "https://ntfy.sh/eva"}))
            self.assertEqual(canarito.sleeping_neighbours("casa"), ["https://ntfy.sh/ana"])
            Path(home, "casa.json").write_text(json.dumps({"name": "casa", "avd": "a", "lat": 4.7, "lon": -74.1, "port": 5554}))
            Path(home, "ana.json").write_text(json.dumps({"name": "ana", "avd": "b", "lat": 4.7, "lon": -74.1, "port": 5556, "follow": True}))
            self.assertEqual(canarito.fixed_receptors(), [("casa", 4.7, -74.1)])
            self.assertEqual(canarito.free_port(), 5558)
        relay = json.loads(canarito.relay_config(CONFIG, ["https://ntfy.sh/b", "https://ntfy.sh/a"]))
        self.assertEqual(relay["extra_urls"], ["https://ntfy.sh/a", "https://ntfy.sh/b"])
        self.assertNotIn("extra_urls", json.loads(canarito.relay_config(CONFIG)))

    def test_a_just_woken_receptor_is_still_sent_alerts_until_it_can_get_them(self):
        with tempfile.TemporaryDirectory() as home, mock.patch.object(canarito, "CONFIG_DIR", Path(home)):
            canarito.write_status("sebastian", asleep=False, covered=False, relay_by="novia",
                                  notify_url="https://ntfy.sh/s")
            self.assertEqual(canarito.sleeping_neighbours("novia"), ["https://ntfy.sh/s"])
            canarito.write_status("sebastian", covered=True, relay_by=None)
            self.assertEqual(canarito.sleeping_neighbours("novia"), [])
            self.assertEqual(canarito.read_status("sebastian")["notify_url"], "https://ntfy.sh/s")

    def test_people_sleep_only_on_awake_receptors_of_names_before_theirs(self):
        with tempfile.TemporaryDirectory() as home, mock.patch.object(canarito, "CONFIG_DIR", Path(home)):
            canarito.write_status("ana", follow=True, asleep=False, position=[4.60, -74.08])
            canarito.write_status("beto", follow=True, asleep=True, position=[4.60, -74.08])
            canarito.write_status("zoe", follow=True, asleep=False, position=[4.60, -74.08])
            self.assertEqual(canarito.sleep_hosts("carla"), [("ana", 4.60, -74.08)])
            self.assertEqual(canarito.sleep_hosts("ana"), [])

    def test_a_receptor_someone_sleeps_on_stays_awake(self):
        follower = canarito.Follower(self.HOME, clock=lambda: self.now, can_sleep=lambda: False)
        follower.update(4.72, -74.07)
        follower.step()
        self.now += canarito.ASLEEP_AFTER_S * 3
        self.assertIsNone(follower.step())
        self.assertFalse(follower.asleep)

    def test_a_receptor_that_cannot_get_alerts_falls_back_to_the_nearest_one_that_can(self):
        with tempfile.TemporaryDirectory() as home, mock.patch.object(canarito, "CONFIG_DIR", Path(home)):
            for name, lat in (("ana", 4.60), ("beto", 3.16), ("carla", 4.70)):
                Path(home, f"{name}.json").write_text(json.dumps({"name": name, "avd": name, "lat": lat, "lon": -74.1}))
            canarito.write_status("ana", covered=False)
            canarito.write_status("beto", covered=True)
            canarito.write_status("carla", covered=True)
            self.assertEqual(canarito.fallback_host("ana", (4.60, -74.1), None), "carla")
            self.assertEqual(canarito.fallback_host("ana", (4.60, -74.1), "beto"), "beto")
            canarito.write_status("carla", covered=False)
            self.assertEqual(canarito.fallback_host("ana", (4.60, -74.1), "carla"), "beto")
            canarito.write_status("beto", covered=False)
            self.assertIsNone(canarito.fallback_host("ana", (4.60, -74.1), "beto"))

    def test_reboots_only_while_every_other_awake_receptor_can_get_alerts(self):
        with tempfile.TemporaryDirectory() as home, mock.patch.object(canarito, "CONFIG_DIR", Path(home)):
            for name in ("ana", "beto", "carla"):
                Path(home, f"{name}.json").write_text(json.dumps({"name": name, "avd": name, "lat": 6, "lon": -75}))
            canarito.write_status("beto", covered=True)
            canarito.write_status("carla", covered=False, asleep=True)
            self.assertTrue(canarito.others_covered("ana"))
            canarito.write_status("beto", covered=False)
            self.assertFalse(canarito.others_covered("ana"))

    def test_each_emulator_process_is_told_apart_from_the_others(self):
        with mock.patch.object(canarito, "sdk_tool", return_value="adb"):
            five = canarito.Emulator({"avd": "canarito-ana", "port": 5554, "lat": 1, "lon": 1})
            fifty = canarito.Emulator({"avd": "canarito-ana2", "port": 5556, "lat": 1, "lon": 1})
        started_as = "qemu -avd canarito-ana2 -port 5556 -no-window"
        self.assertIn(fifty.process_pattern(), started_as)
        self.assertNotIn(five.process_pattern(), started_as)

    def test_a_receptor_about_to_go_down_wakes_its_sleepers_and_still_sends_until_they_can(self):
        with tempfile.TemporaryDirectory() as home, mock.patch.object(canarito, "CONFIG_DIR", Path(home)):
            for name in ("ana", "beto"):
                Path(home, f"{name}.json").write_text(json.dumps({"name": name, "avd": name, "lat": 6, "lon": -75}))
            canarito.write_status("ana", covered=True, draining=True)
            canarito.write_status("beto", covered=False, asleep=True, relay_by="ana", notify_url="https://ntfy.sh/b")
            self.assertFalse(canarito.home_covered("ana"))
            self.assertEqual(canarito.fallback_host("beto", (6, -75), "ana"), "ana")
            self.assertFalse(canarito.safe_to_stop("ana"))
            canarito.write_status("beto", asleep=False)
            self.assertFalse(canarito.safe_to_stop("ana"))
            canarito.write_status("beto", covered=True, relay_by=None)
            self.assertTrue(canarito.safe_to_stop("ana"))

    def test_owntracks_link_carries_the_location_link(self):
        import urllib.parse
        link = canarito.owntracks_link("https://ntfy.sh/canarito-where-x?cache=no", "ana")
        self.assertTrue(link.startswith("owntracks:///config?inline="))
        settings = json.loads(base64.b64decode(urllib.parse.unquote(link.split("inline=", 1)[1])))
        self.assertEqual(settings["url"], "https://ntfy.sh/canarito-where-x?cache=no")
        self.assertEqual(settings["mode"], 3)


class FakeRelay:
    """Stands in for the relay: answers per handle from a script, and remembers what it was sent."""

    def __init__(self, answers, max_handles=None, checks=()):
        self.answers = list(answers)
        self.url, self.server_id = "https://relay.example.org", "a1" * 16
        self.pushes = []
        self.max_handles = max_handles  # an old relay refuses a body over 4 KB, about 18 handles
        self.checks = list(checks)

    def check(self):
        outcome = self.checks.pop(0) if self.checks else None
        if outcome:
            raise appserver.RelayError(outcome)

    def push(self, handles, alert, critical=False):
        if self.max_handles and len(handles) > self.max_handles:
            raise appserver.RelayError("relay answered 413 too_large")
        self.pushes.append((list(handles), alert))
        answer = self.answers.pop(0) if self.answers else "sent"
        if isinstance(answer, Exception):
            raise answer
        return [{"status": answer} if isinstance(answer, str) else answer for _ in handles]


class AppTest(unittest.TestCase):
    def setUp(self):
        self.folder = tempfile.TemporaryDirectory()
        self.addCleanup(self.folder.cleanup)
        self.config_dir = Path(self.folder.name)
        patcher = mock.patch.object(canarito, "CONFIG_DIR", self.config_dir)
        patcher.start()
        self.addCleanup(patcher.stop)
        self.devices = appserver.Devices(self.config_dir)
        self.now = 1_000_000.0
        self.sent = []
        self.health = canarito.Health({"name": "sebastian", "language": "es"},
                                      lambda audience, text, priority: self.sent.append((audience, text)),
                                      clock=lambda: self.now)

    def pair_phone(self, handle="handle-1", name="iPhone"):
        secret = self.devices.new_pairing("sebastian", self.now)
        return self.devices.pair(secret, handle, name, self.now)

    # --- pairing and the HTTP side
    def serve(self, relay=None):
        import threading
        import urllib.request
        (self.config_dir / "sebastian.json").write_text(json.dumps({**CONFIG, "name": "sebastian", "avd": "x", "follow": True}))
        server = appserver.make_server("127.0.0.1", 0, self.devices, lambda: relay, canarito.app_status,
                                       canarito.receptor_language, canarito.save_app_position,
                                       canarito.parse_position, clock=lambda: self.now)
        threading.Thread(target=server.serve_forever, daemon=True).start()
        self.addCleanup(server.server_close)
        self.addCleanup(server.shutdown)
        base = f"http://127.0.0.1:{server.server_address[1]}"

        def call(method, path, body=None, key=None):
            headers = {"Authorization": f"Bearer {key}"} if key else {}
            request = urllib.request.Request(base + path, method=method, headers=headers,
                                             data=json.dumps(body).encode() if body is not None else None)
            try:
                with urllib.request.urlopen(request) as response:
                    text = response.read()
                    return response.status, json.loads(text) if text else None
            except urllib.error.HTTPError as error:
                return error.code, json.loads(error.read())
        return call

    def test_a_secret_pairs_one_phone_once_and_only_in_time(self):
        call = self.serve()
        secret = self.devices.new_pairing("sebastian", self.now)
        status, paired = call("POST", "/v1/pair", {"secret": secret, "handle": "h1", "name": "iPhone"})
        self.assertEqual((status, paired["receptor"], paired["language"]), (200, "sebastian", "es"))
        self.assertEqual(call("POST", "/v1/pair", {"secret": secret, "handle": "h2"})[1], {"error": "bad_secret"})
        self.assertEqual(call("POST", "/v1/pair", {"secret": "nope", "handle": "h2"})[0], 403)
        late = self.devices.new_pairing("sebastian", self.now)
        self.now += appserver.PAIRING_TTL_S + 1
        self.assertEqual(call("POST", "/v1/pair", {"secret": late, "handle": "h3"})[0], 403)
        self.assertEqual(call("POST", "/v1/pair", {"handle": "h3"})[0], 400)
        # Keys are stored hashed.
        self.assertNotIn(paired["device_key"], (self.config_dir / "devices.json").read_text())

    def test_position_is_rounded_saved_for_the_receptor_and_rate_limited(self):
        call = self.serve()
        key = self.pair_phone()["device_key"]
        self.assertEqual(call("POST", "/v1/position", {"lat": 4.711234, "lon": -74.072987}, key)[0], 204)
        lat, lon, _ = canarito.read_app_position("sebastian")
        self.assertEqual((lat, lon), (4.71, -74.07))
        self.assertEqual(call("POST", "/v1/position", {"lat": 5, "lon": -74}, key)[1], {"error": "slow_down"})
        self.now += appserver.POSITION_EVERY_S
        self.assertEqual(call("POST", "/v1/position", {"lat": 95, "lon": 0}, key)[0], 400)
        self.assertEqual(call("POST", "/v1/position", {"lat": 5, "lon": -74})[0], 401)
        self.assertEqual(call("POST", "/v1/position", {"lat": 5, "lon": -74}, "wrong")[0], 401)

    def test_status_says_covered_only_when_the_receptor_is_up_and_covered(self):
        call = self.serve()
        key = self.pair_phone()["device_key"]
        self.assertEqual(call("GET", "/v1/status", key=key)[1],
                         {"receptor": "sebastian", "covered": False, "receptor_up": False, "relay_ok": True, "following": True})
        canarito.alive_path("sebastian").write_text(str(time.time()))
        canarito.write_status("sebastian", covered=True)
        canarito.set_relay_ok("sebastian", False)
        self.assertEqual(call("GET", "/v1/status", key=key)[1],
                         {"receptor": "sebastian", "covered": True, "receptor_up": True, "relay_ok": False, "following": True})

    def test_a_phone_can_change_its_token_and_leave(self):
        call = self.serve()
        paired = self.pair_phone()
        self.assertEqual(call("PUT", "/v1/device", {"handle": "new"}, paired["device_key"])[0], 204)
        self.assertEqual(self.devices.handles_for("sebastian"), {paired["device_id"]: "new"})
        self.assertEqual(call("DELETE", "/v1/device", key=paired["device_key"])[0], 204)
        self.assertEqual(self.devices.handles_for("sebastian"), {})
        self.assertEqual(call("GET", "/v1/status", key=paired["device_key"])[0], 401)

    def test_test_push_goes_to_that_phone_once_per_ten_minutes_and_a_relay_failure_shows(self):
        relay = FakeRelay(["sent", "failed"])
        call = self.serve(relay)
        key = self.pair_phone()["device_key"]
        self.assertEqual(call("POST", "/v1/test", key=key)[0], 204)
        handles, alert = relay.pushes[0]
        self.assertEqual((handles, alert["test"], alert["lang"]), (["handle-1"], True, "es"))
        self.assertEqual(call("POST", "/v1/test", key=key)[1], {"error": "slow_down"})
        self.now += appserver.TEST_EVERY_S
        self.assertEqual(call("POST", "/v1/test", key=key)[1], {"error": "relay_failed"})

    def test_no_relay_makes_the_test_fail_loud(self):
        call = self.serve(None)
        self.assertEqual(call("POST", "/v1/test", key=self.pair_phone()["device_key"])[1], {"error": "relay_failed"})

    # --- the QR
    def test_the_qr_url_carries_what_the_app_needs_and_the_code_draws(self):
        import urllib.parse
        relay = FakeRelay([])
        url = appserver.pairing_url("https://canarito.example.org", "s" * 32, relay)
        query = urllib.parse.parse_qs(urllib.parse.urlsplit(url).query)
        self.assertEqual(url.split("?")[0], "canarito://pair")
        self.assertEqual({key: value[0] for key, value in query.items()},
                         {"v": "1", "server": "https://canarito.example.org", "secret": "s" * 32,
                          "relay": "https://relay.example.org", "sid": "a1" * 16})
        modules = qr.encode(url)
        self.assertEqual(len(modules), len(modules[0]))
        self.assertTrue(all(modules[0][:7]) and all(modules[6][:7]))  # finder pattern, top left
        self.assertEqual(qr.png(modules)[:8], b"\x89PNG\r\n\x1a\n")
        with self.assertRaises(ValueError):
            qr.encode("x" * 400)

    def test_pair_command_writes_the_png_with_a_private_mode_and_burns_nothing_without_a_relay(self):
        (self.config_dir / "sebastian.json").write_text(json.dumps({**CONFIG, "name": "sebastian", "avd": "x"}))
        with self.assertRaises(SystemExit):
            canarito.main(["pair", "--name", "sebastian", "--server-url", "http://example.org"])
        with self.assertRaises(SystemExit) as no_relay:
            canarito.main(["pair", "--name", "sebastian", "--server-url", "https://canarito.example.org"])
        self.assertIn("relay", str(no_relay.exception))
        self.assertEqual(self.devices.snapshot()["pairings"], {})
        (self.config_dir / "relay-server.json").write_text(json.dumps(
            {"url": "https://relay.example.org", "server_id": "a1" * 16, "server_key": "b2" * 32}))
        with mock.patch("builtins.print"):
            canarito.main(["pair", "--name", "sebastian"])
        self.assertEqual(len(self.devices.snapshot()["pairings"]), 1)
        self.assertEqual((self.config_dir / "pair-sebastian.png").stat().st_mode & 0o777, 0o600)

    # --- demo mode (App Review)
    def test_demo_code_is_off_by_default_and_a_normal_secret_stays_single_use(self):
        self.assertEqual(self.devices.snapshot()["pairings"], {})
        secret = self.devices.new_pairing("sebastian", self.now)
        self.assertIsNotNone(self.devices.pair(secret, "h", "a", self.now))
        self.assertIsNone(self.devices.pair(secret, "h", "a", self.now))

    def test_demo_code_pairs_many_phones_never_expires_and_new_one_replaces_old(self):
        secret = self.devices.new_pairing("sebastian", self.now, demo=True)
        later = self.now + 365 * 86400
        self.assertIsNotNone(self.devices.pair(secret, "h1", "a", later))
        self.assertIsNotNone(self.devices.pair(secret, "h2", "b", later))
        newer = self.devices.new_pairing("sebastian", self.now, demo=True)
        self.assertIsNone(self.devices.pair(secret, "h3", "c", later))
        self.assertIsNotNone(self.devices.pair(newer, "h3", "c", later))
        normal = self.devices.new_pairing("sebastian", self.now)
        self.assertIsNotNone(self.devices.pair(newer, "h4", "d", later), "a normal pairing keeps the demo code")
        self.assertIsNotNone(self.devices.pair(normal, "h5", "e", self.now))

    def test_demo_phones_get_test_pushes_only_and_cannot_move_a_receptor(self):
        relay = FakeRelay(["sent", "sent"])
        call = self.serve(relay)
        real = self.pair_phone("real-handle")
        demo = self.devices.pair(self.devices.new_pairing("sebastian", self.now, demo=True), "demo-handle", "Reviewer", self.now)
        self.assertEqual(self.devices.handles_for("sebastian"), {real["device_id"]: "real-handle"})
        self.deliver(relay)
        self.assertEqual(relay.pushes[0][0], ["real-handle"])
        self.assertEqual(call("POST", "/v1/test", key=demo["device_key"])[0], 204)
        self.assertEqual(relay.pushes[1][0], ["demo-handle"])
        self.now += appserver.DEMO_TEST_EVERY_S
        self.assertEqual(call("POST", "/v1/test", key=demo["device_key"])[0], 204)
        self.assertEqual(call("POST", "/v1/position", {"lat": 4.7, "lon": -74.1}, demo["device_key"])[0], 204)
        self.assertIsNone(canarito.read_app_position("sebastian"))

    def test_turning_demo_off_removes_its_phones_and_the_code_but_not_real_phones(self):
        secret = self.devices.new_pairing("sebastian", self.now, demo=True)
        demo = self.devices.pair(secret, "h", "Reviewer", self.now)
        real = self.pair_phone()
        self.assertEqual(self.devices.end_demo(), 1)
        self.assertIsNone(self.devices.by_key(demo["device_key"]))
        self.assertIsNotNone(self.devices.by_key(real["device_key"]))
        self.assertIsNone(self.devices.pair(secret, "h", "x", self.now))

    def test_demo_devices_are_capped(self):
        secret = self.devices.new_pairing("sebastian", self.now, demo=True)
        for number in range(appserver.MAX_DEMO_DEVICES + 5):
            self.devices.pair(secret, "h", "x", self.now + number)
        self.assertEqual(sum(1 for d in self.devices.snapshot()["devices"].values() if d.get("demo")),
                         appserver.MAX_DEMO_DEVICES)

    def test_pair_command_demo_and_off(self):
        (self.config_dir / "sebastian.json").write_text(json.dumps({**CONFIG, "name": "sebastian", "avd": "x"}))
        (self.config_dir / "relay-server.json").write_text(json.dumps(
            {"url": "https://relay.example.org", "server_id": "a1" * 16, "server_key": "b2" * 32}))
        with mock.patch("builtins.print") as shown:
            canarito.main(["pair", "--name", "sebastian", "--server-url", "https://canarito.example.org", "--demo"])
            self.assertIn("--demo-off", " ".join(str(call.args[0]) for call in shown.call_args_list))
        self.assertTrue(next(iter(self.devices.snapshot()["pairings"].values()))["demo"])
        self.assertEqual((self.config_dir / "pair-sebastian-demo.png").stat().st_mode & 0o777, 0o600)
        with mock.patch("builtins.print"):
            canarito.main(["pair", "--name", "sebastian", "--demo-off"])
        self.assertEqual(self.devices.snapshot()["pairings"], {})

    # --- alerts to the relay
    def test_only_the_urgent_alert_becomes_a_push_with_magnitude_and_late(self):
        event = {"event": "message", "id": "e1", "time": 1000, "priority": 5, "title": "Alerta de sismo",
                 "message": "Sismo M5.4 cerca de tu zona. Protégete ahora."}
        alert = appserver.alert_from_event(event, "sebastian", "es", 1010)
        self.assertEqual(alert, {"id": "e1", "receptor": "sebastian", "lang": "es", "title": "Alerta de sismo",
                                 "body": event["message"], "sent_at": 1000, "magnitude": 5.4})
        self.assertTrue(appserver.alert_from_event(event, "sebastian", "es", 1061)["late"])
        for quiet in ({**event, "priority": 4}, {**event, "priority": None}, {**event, "event": "open"}):
            self.assertIsNone(appserver.alert_from_event(quiet, "sebastian", "es", 1010))

    def deliver(self, relay, sent_at=None):
        flags = []
        sleeps = []

        def sleep(seconds):
            sleeps.append(seconds)
            self.now += seconds
        alert = {"id": "e1", "receptor": "sebastian", "sent_at": sent_at or self.now}
        appserver.deliver_alert(self.devices, lambda: relay, self.health, "sebastian", alert, flags.append,
                                clock=lambda: self.now, sleep=sleep)
        return flags, sleeps

    def test_alert_reaches_every_phone_of_the_receptor_and_not_another_one(self):
        self.pair_phone("h1")
        self.pair_phone("h2")
        other = self.devices.pair(self.devices.new_pairing("novia", self.now), "h3", "x", self.now)
        relay = FakeRelay(["sent"])
        flags, _ = self.deliver(relay)
        self.assertEqual(sorted(relay.pushes[0][0]), ["h1", "h2"])
        self.assertEqual((flags, self.sent), ([True], []))
        self.assertIn(other["device_id"], self.devices.snapshot()["devices"])

    def test_a_relay_that_fails_is_told_to_the_admin_retried_and_cleared_when_it_works(self):
        self.pair_phone()
        flags, sleeps = self.deliver(FakeRelay([appserver.RelayError("relay answered 502"), "failed", "sent"]))
        self.assertEqual(flags, [False, False, True])
        self.assertEqual(len(sleeps), 2)
        self.assertEqual(len(self.sent), 2)  # one "relay down", one "relay ok", not one per retry
        self.assertIn("502", self.sent[0][1])
        self.assertEqual(self.sent[0][0], "admin")
        self.assertIn("vuelven a salir", self.sent[1][1])

    def test_an_alert_that_never_gets_through_ends_with_a_notice_and_stops_when_too_old(self):
        self.pair_phone()
        relay = FakeRelay([appserver.RelayError("relay not reachable")] * 100)
        flags, sleeps = self.deliver(relay)
        self.assertLessEqual(len(sleeps) * appserver.RETRY_EVERY_S, appserver.ALERT_TTL_S + appserver.RETRY_EVERY_S)
        self.assertEqual(set(flags), {False})
        self.assertIn("1 celular", self.sent[-1][1])

    def test_no_relay_configured_is_loud(self):
        self.pair_phone()
        flags, _ = self.deliver(None)
        self.assertEqual(flags[0], False)
        self.assertIn("pair --relay-url", self.sent[0][1])

    def test_a_dead_token_removes_the_phone_and_tells_the_admin_once(self):
        paired = self.pair_phone(name="Ana's iPhone")
        flags, _ = self.deliver(FakeRelay(["gone"]))
        self.assertEqual(self.devices.handles_for("sebastian"), {})
        self.assertEqual(len(self.sent), 1)
        self.assertIn("Ana's iPhone", self.sent[0][1])
        self.assertEqual(flags, [True])

    def test_a_receptor_without_phones_never_calls_the_relay(self):
        relay = FakeRelay([])
        self.deliver(relay)
        self.assertEqual(relay.pushes, [])

    def test_twenty_phones_all_get_the_alert_through_a_relay_that_refuses_big_requests(self):
        for number in range(20):
            self.pair_phone(f"h{number}")
        relay = FakeRelay([], max_handles=18)
        flags, sleeps = self.deliver(relay)
        self.assertEqual([len(handles) for handles, _ in relay.pushes], [15, 5])
        self.assertEqual(sorted(h for handles, _ in relay.pushes for h in handles), sorted(f"h{n}" for n in range(20)))
        self.assertEqual((flags, sleeps, self.sent), ([True], [], []))

    def test_one_chunk_failing_is_loud_and_only_that_chunk_is_retried(self):
        for number in range(20):
            self.pair_phone(f"h{number:02d}")
        relay = FakeRelay([appserver.RelayError("relay answered 502"), "sent", "sent"])
        flags, sleeps = self.deliver(relay)
        self.assertIn("502", self.sent[0][1])
        self.assertEqual(flags, [False, True])
        self.assertEqual(len(sleeps), 1)
        first_try, second_chunk, retry = (handles for handles, _ in relay.pushes)
        self.assertEqual(len(second_chunk), 5)
        self.assertEqual(sorted(retry), sorted(h for h in first_try))

    # --- relay checked between alerts
    def check(self, relay, ahead=0):
        flags = []
        appserver.check_relay(self.devices, lambda: relay, self.health, "sebastian", flags.append,
                              clock=lambda: self.now + ahead, sleep=lambda seconds: None)
        return flags

    def test_a_dead_relay_is_found_before_any_alert_and_clears_when_it_is_back(self):
        self.pair_phone()
        flags = self.check(FakeRelay([], checks=["relay not reachable", "relay not reachable"]))
        self.assertEqual(flags, [False])
        self.assertIn("relay not reachable", self.sent[0][1])
        self.assertEqual(self.check(FakeRelay([])), [True])
        self.assertIn("vuelven a salir", self.sent[1][1])

    def test_one_failed_check_is_confirmed_before_it_is_told(self):
        self.pair_phone()
        self.assertEqual(self.check(FakeRelay([], checks=["blip"])), [True])
        self.assertEqual(self.sent, [])

    def test_no_phones_no_check_and_no_relay_with_phones_is_loud(self):
        relay = FakeRelay([], checks=["never used"])
        self.assertEqual(self.check(relay), [])
        self.pair_phone()
        self.assertEqual(self.check(None), [False])
        self.assertIn("pair --relay-url", self.sent[0][1])

    def test_a_recent_failed_push_is_not_cleared_by_a_check_that_cannot_see_apns(self):
        self.pair_phone()
        self.health.push_failed_at = self.now
        self.health.problem("relay", error="apns_403")
        self.assertEqual(self.check(FakeRelay([]), ahead=60), [])
        self.assertEqual(len(self.sent), 1)
        self.assertEqual(self.check(FakeRelay([]), ahead=appserver.PUSH_FAILURE_MEMORY_S), [True])

    def test_client_check_accepts_only_the_relays_400_bad_request(self):
        import io

        def client(code, body=b""):
            def opener(request, timeout):
                if code == 200:
                    class Ok:
                        def __enter__(self): return self
                        def __exit__(self, *args): return False
                        def read(self): return b"{}"
                    return Ok()
                raise urllib.error.HTTPError(request.full_url, code, "x", {}, io.BytesIO(body))
            return appserver.RelayClient("https://relay.example.org", "a1" * 16, "b2" * 32, opener=opener)
        client(400, b'{"error":"bad_request"}').check()
        for bad in (client(401, b'{"error":"bad_signature"}'), client(502, b'{"error":"apns_unavailable"}'),
                    client(200), client(400, b'{"error":"other"}')):
            with self.assertRaises(appserver.RelayError):
                bad.check()

    def test_request_is_signed_the_way_the_relay_checks_it(self):
        seen = {}

        class Response:
            def __enter__(self):
                return self

            def __exit__(self, *args):
                return False

            def read(self):
                return b'{"results":[{"status":"sent"}]}'

        def opener(request, timeout):
            seen.update(url=request.full_url, headers={k.lower(): v for k, v in request.header_items()}, body=request.data.decode())
            return Response()
        client = appserver.RelayClient("https://relay.example.org/", "a1" * 16, "b2" * 32, clock=lambda: 1_791_650_000, opener=opener)
        self.assertEqual(client.push(["h"], {"id": "x"}), [{"status": "sent"}])
        expected = hmac.new(bytes.fromhex("b2" * 32), ("1791650000\n" + seen["body"]).encode(), "sha256").hexdigest()
        self.assertEqual(seen["headers"]["x-canarito-signature"], expected)
        self.assertEqual((seen["url"], seen["headers"]["x-canarito-server"], seen["headers"]["x-canarito-timestamp"]),
                         ("https://relay.example.org/v1/push", "a1" * 16, "1791650000"))


class WatchdogTest(unittest.TestCase):
    """The app server being down must reach the admin, once, and its return too."""

    def setUp(self):
        self.folder = tempfile.TemporaryDirectory()
        self.addCleanup(self.folder.cleanup)
        self.devices = appserver.Devices(Path(self.folder.name))
        self.devices.set_serve_port(8787)
        self.devices.set_server_url("https://canarito.example.org")
        self.sent = []
        self.health = canarito.Health({"name": "sebastian", "language": "es"},
                                      lambda audience, text, priority: self.sent.append((audience, text, priority)))
        self.health.strikes = {}
        self.up = {"127.0.0.1": True, "canarito.example.org": True}
        self.public_page = None

    def opener(self, request, timeout):
        import io
        host = urllib.parse.urlsplit(request.full_url).hostname
        if not self.up[host]:
            raise OSError("Connection refused")
        code, body = self.public_page if host == "canarito.example.org" and self.public_page else (401, b'{"error":"bad_key"}')
        raise urllib.error.HTTPError(request.full_url, code, "x", {}, io.BytesIO(body))

    def round(self):
        canarito.watch_app_server(self.health, self.devices, self.opener)

    def test_nothing_is_watched_until_serve_has_run(self):
        devices = appserver.Devices(Path(self.folder.name) / "other")
        Path(self.folder.name, "other").mkdir()
        canarito.watch_app_server(self.health, devices, self.opener)
        self.assertEqual(self.sent, [])

    def test_healthy_server_says_nothing(self):
        for _ in range(3):
            self.round()
        self.assertEqual(self.sent, [])

    def test_local_down_is_told_to_the_admin_after_two_misses_once_and_clears(self):
        self.up["127.0.0.1"] = False
        self.round()
        self.assertEqual(self.sent, [])
        self.round()
        self.round()
        self.assertEqual([(a, p) for a, _, p in self.sent], [("admin", "high")])
        self.assertIn("canarito.py serve", self.sent[0][1])
        self.up["127.0.0.1"] = True
        self.round()
        self.assertEqual(len(self.sent), 2)
        self.assertIn("responde otra vez", self.sent[1][1])

    def test_public_down_with_local_up_names_the_url(self):
        self.up["canarito.example.org"] = False
        self.round()
        self.round()
        self.assertIn("https://canarito.example.org", self.sent[0][1])
        self.assertEqual(len(self.sent), 1)

    def test_a_tunnel_error_page_is_not_our_server(self):
        self.public_page = (502, b"<html>Bad gateway</html>")
        self.round()
        self.round()
        self.assertIn("502", self.sent[0][1])

    def test_a_dead_local_server_gives_one_notice_not_two(self):
        self.up.update({"127.0.0.1": False, "canarito.example.org": False})
        for _ in range(4):
            self.round()
        self.assertEqual(len(self.sent), 1)

    def test_app_side_problems_never_reach_the_family(self):
        self.up["127.0.0.1"] = False
        for _ in range(2):
            self.round()
        self.health.problem("relay", error="x")
        self.health.clock = lambda: time.time() + canarito.FAMILY_AFTER_S * 2
        self.health.tick()
        self.assertEqual({audience for audience, _, _ in self.sent}, {"admin"})

    def test_only_a_canarito_401_counts_as_up(self):
        def probe(code, body):
            import io

            def opener(request, timeout):
                raise urllib.error.HTTPError(request.full_url, code, "x", {}, io.BytesIO(body))
            return canarito.probe_app_server("http://127.0.0.1:1", opener)
        self.assertIsNone(probe(401, b'{"error":"bad_key"}'))
        self.assertIsNotNone(probe(401, b'{"error":"other"}'))
        self.assertIsNotNone(probe(404, b"nope"))


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
