#!/usr/bin/env python3
"""Canarito: run an Android emulator that receives Google's earthquake early warnings at a
place you choose, and forward them through ntfy to any device you subscribe.

    canarito.py setup --name home --lat 4.711 --lon -74.072
    canarito.py run --name home
    canarito.py test --name home
    canarito.py evidence --name home

Needs Python 3.9+ and the Android SDK command line tools (sdkmanager, avdmanager) with
ANDROID_HOME set; a JDK only if you build the APK yourself, otherwise run downloads it. Read README.md first: this is not an
official alert system and it can miss alerts.
"""
import argparse
import base64
import hashlib
import json
import os
import platform
import secrets
import subprocess
import sys
import threading
import time
import urllib.parse
import urllib.request
from pathlib import Path

import catalogs

PACKAGE = "app.canarito.receptor"
LISTENER = f"{PACKAGE}/.CaptureService"
CONFIG_DIR = Path(os.environ.get("CANARITO_HOME", Path.home() / ".canarito"))
DEFAULT_APK = Path(__file__).resolve().parent / "android/build/outputs/apk/debug/android-debug.apk"
# Used only when nothing was built locally. Pinned to one release and checked against this hash,
# so a replaced file on GitHub is refused instead of installed.
RELEASE_APK_URL = "https://github.com/sebospc/canarito/releases/download/v0.1.0/android-debug.apk"
RELEASE_APK_SHA256 = "c5f5612ba26399467896444e394431cf5358fa228452c6bd0bf073385f141239"
API_LEVEL = 35
# Play Services asks for a GPS fix once, some 5-7 minutes into a boot, and AEA keeps that
# position. A geo fix sent later changes nothing, so it is repeated through the whole window.
BOOT_WINDOW_S = 12 * 60
FIX_EVERY_S = 3
IDLE_EVERY_S = 30
# An alert was lost on 24-sep-2026 with a ~25 h old location. A fresh boot gets a fresh fix.
# ponytail: blind reboot, ~10 min without coverage each time; reading AEA's own location
# age from dumpsys (the old sensor-health.py) avoids the gap if it ever matters.
REBOOT_EVERY_S = 18 * 60 * 60
# A new emulator took 13 to 60 min before AEA registered, and 1 in 8 never did.
AEA_CHECK_EVERY_S = 5 * 60
AEA_GIVE_UP_S = 90 * 60
EMULATOR_DOWN_AFTER_S = 5 * 60
# The family hears about a problem only when coverage is gone this long; the admin hears at once.
FAMILY_AFTER_S = 60 * 60
# A gap between wall clock and monotonic clock this big means the computer was asleep.
SLEPT_AFTER_S = 60
# An emulator that dies at once must not be relaunched in a tight loop.
RESTART_EVERY_S = 60
MISSED_CHECK_EVERY_S = 10 * 60
# Following receptors. Google takes a new location at most every 5 minutes and only after more
# than 1 km, so moving more often or for less changes nothing.
MOVE_AFTER_KM = 1.0
MOVE_EVERY_S = 5 * 60
HOME_KM = 5.0
ASLEEP_AFTER_S = 30 * 60
# OwnTracks stays quiet while a phone does not move, so silence is normal for hours at night.
# ponytail: fixed 6 h; a stricter check needs the phone to send a keep-alive.
NO_POSITION_AFTER_S = 6 * 3600
EMULATOR_GB = 4

NOTICES = {
    "es": {
        "emulator_down": "El receptor “{name}” no responde desde las {since}.",
        "emulator_down_ok": "El receptor “{name}” volvió a responder.",
        "aea": "El servicio de sismos de Google no arrancó en “{name}” después de 90 minutos. Borra el emulador {avd} y vuelve a correr setup.",
        "aea_ok": "El servicio de sismos de Google ya arrancó en “{name}”.",
        "provision": "No se pudo preparar la app en “{name}”: {error}",
        "provision_ok": "La app en “{name}” quedó lista.",
        "slept": "El computador estuvo suspendido de {start} a {end}. “{name}” no tuvo cobertura en ese tiempo.",
        "family_down": "Canarito “{name}” no tiene cobertura desde las {since}. Te avisamos cuando vuelva.",
        "family_ok": "Canarito “{name}” volvió a tener cobertura.",
        "missed": "Sismo M{mag} a {km} km de “{name}” a las {when} ({sources}). Este receptor no recibió aviso.",
        "possibly": "Posible aviso perdido: sismo M{mag} a {km} km de “{name}” a las {when} ({sources}). Google usa su propia magnitud, así que puede que no haya avisado.",
        "late": "Sismo M{mag} a {km} km de “{name}” a las {when} ({sources}). Solo llegó el aviso tardío de Google, no la alerta temprana.",
        "location_stale": "Canarito no sabe dónde está “{name}” desde las {since}. Revisa OwnTracks en su celular.",
        "location_stale_ok": "Canarito volvió a saber dónde está “{name}”.",
        "location_invalid": "Llegó una posición que Canarito no entiende para “{name}”: {error}",
        "location_invalid_ok": "Las posiciones de “{name}” vuelven a llegar bien.",
    },
    "en": {
        "emulator_down": "Receptor “{name}” has not answered since {since}.",
        "emulator_down_ok": "Receptor “{name}” is answering again.",
        "aea": "Google's earthquake service did not start on “{name}” after 90 minutes. Delete the emulator {avd} and run setup again.",
        "aea_ok": "Google's earthquake service is now running on “{name}”.",
        "provision": "Could not set up the app on “{name}”: {error}",
        "provision_ok": "The app on “{name}” is set up.",
        "slept": "The computer was asleep from {start} to {end}. “{name}” had no coverage then.",
        "family_down": "Canarito “{name}” has no coverage since {since}. We will tell you when it is back.",
        "family_ok": "Canarito “{name}” has coverage again.",
        "missed": "Quake M{mag} {km} km from “{name}” at {when} ({sources}). This receptor got no alert.",
        "possibly": "Possibly missed: quake M{mag} {km} km from “{name}” at {when} ({sources}). Google uses its own magnitude, so it may not have alerted.",
        "late": "Quake M{mag} {km} km from “{name}” at {when} ({sources}). Only Google's later notice arrived, not the early alert.",
        "location_stale": "Canarito has not known where “{name}” is since {since}. Check OwnTracks on their phone.",
        "location_stale_ok": "Canarito knows where “{name}” is again.",
        "location_invalid": "A position for “{name}” arrived that Canarito does not understand: {error}",
        "location_invalid_ok": "Positions for “{name}” arrive fine again.",
    },
}


def log(message):
    print(time.strftime("%Y-%m-%d %H:%M:%S"), message, flush=True)


def sdk_root():
    root = os.environ.get("ANDROID_HOME") or os.environ.get("ANDROID_SDK_ROOT")
    if not root:
        sys.exit("Set ANDROID_HOME to your Android SDK (see README.md, Install).")
    return Path(root)


def sdk_tool(*parts):
    tool = sdk_root().joinpath(*parts)
    if not tool.exists():
        sys.exit(f"Missing {tool}. Install the Android SDK command line tools (README.md, Install).")
    return str(tool)


def system_image(machine):
    """An arm64 image on Apple Silicon and ARM Linux; an x86_64 one runs there only translated, if at all."""
    abi = "arm64-v8a" if machine.lower() in ("arm64", "aarch64") else "x86_64"
    # Play Store image: AEA ships inside Play Services, which plain google_apis images also have,
    # but this is the one measured receiving a real alert.
    return f"system-images;android-{API_LEVEL};google_apis_playstore;{abi}"


def relay_config(config, extra_urls=()):
    """What the app reads from files/relay.json. Only what the receptor needs. extra_urls are the
    links of people whose own following receptor sleeps near this one."""
    relay = {"notify_url": config["notify_url"], "name": config["name"], "language": config["language"]}
    for optional in ("notify_token", "heartbeat_url"):
        if config.get(optional):
            relay[optional] = config[optional]
    if extra_urls:
        relay["extra_urls"] = sorted(extra_urls)
    return json.dumps(relay, separators=(",", ":"), sort_keys=True)


def write_relay_command(relay_json):
    """Written from an argument, not stdin: adb sometimes delivered no stdin and left the file
    empty, and an empty relay.json is a receptor that never sends anything."""
    encoded = base64.b64encode(relay_json.encode()).decode()
    return f"run-as {PACKAGE} sh -c 'mkdir -p files && echo {encoded} | base64 -d > files/relay.json'"


def check_coordinates(lat, lon):
    if not (-90 <= lat <= 90 and -180 <= lon <= 180):
        raise ValueError(f"lat {lat}, lon {lon} is not a place on Earth")


def config_path(name):
    return CONFIG_DIR / f"{name}.json"


def load_config(name):
    try:
        return json.loads(config_path(name).read_text())
    except FileNotFoundError:
        sys.exit(f"No receptor called {name}. Run: canarito.py setup --name {name} --lat ... --lon ...")


def free_port():
    """Each receptor gets its own console port, so several can run on one computer."""
    taken = set()
    for path in CONFIG_DIR.glob("*.json"):
        try:
            taken.add(json.loads(path.read_text())["port"])
        except (ValueError, KeyError):
            pass
    return next(port for port in range(5554, 5682, 2) if port not in taken)


def clock_time(epoch_s):
    return time.strftime("%H:%M", time.localtime(epoch_s))


def post_notice(url, token, body, priority="default", click=None):
    """Never raises: a notice that cannot go out is logged, and the receptor keeps running."""
    request = urllib.request.Request(url, method="POST", data=body.encode(),
                                     headers={"Title": "Canarito", "Priority": priority})
    if click:
        request.add_header("Click", click)
    if token:
        request.add_header("Authorization", f"Bearer {token}")
    try:
        with urllib.request.urlopen(request, timeout=10):
            return True
    except (OSError, ValueError) as error:
        log(f"NOTICE NOT SENT ({error}): {body}")
        return False


class Health:
    """What is wrong with one receptor right now. Each problem is told once when it starts and once
    when it ends: the admin at once, the family only when coverage is gone for FAMILY_AFTER_S."""

    def __init__(self, config, send, clock=time.time):
        self.config = config
        self.send = send  # send(audience, text, priority), audience "admin" or "family"
        self.clock = clock
        self.problems = {}
        self.family_told = False
        self.texts = NOTICES.get(config.get("language"), NOTICES["es"])

    def _text(self, key, **values):
        return self.texts[key].format(name=self.config["name"], avd=self.config.get("avd", ""), **values)

    def problem(self, key, **values):
        if key in self.problems:
            return
        self.problems[key] = self.clock()
        self.send("admin", self._text(key, since=clock_time(self.problems[key]), **values), "high")

    def clear(self, key):
        if self.problems.pop(key, None) is None:
            return
        self.send("admin", self._text(f"{key}_ok"), "default")
        if not self.problems and self.family_told:
            self.family_told = False
            self.send("family", self._text("family_ok"), "default")

    def note(self, key, **values):
        """Something that already ended, such as a sleep: one message, nothing to clear."""
        self.send("admin", self._text(key, **values), "high")

    def tick(self):
        if self.problems and not self.family_told:
            since = min(self.problems.values())
            if self.clock() - since > FAMILY_AFTER_S:
                self.family_told = True
                self.send("family", self._text("family_down", since=clock_time(since)), "high")


def alert_times(evidence_jsonl):
    """(early alerts, later notices): capture times in epoch seconds of Google's notifications."""
    early, late = [], []
    for line in evidence_jsonl.splitlines():
        try:
            event = json.loads(line)
        except ValueError:
            continue
        channel = event.get("channel_id") or ""
        if event.get("event_type") != "NOTIFICATION_POSTED" or not channel.startswith("eew"):
            continue
        (early if channel.startswith("eew_alert") else late).append(event["captured_at_ms"] / 1000)
    return early, late


def reported_path(name):
    return CONFIG_DIR / f"{name}.reported.json"


def check_missed(config, emulator, health, reported, lat, lon):
    """Tells the admin about quakes this receptor should have caught. Skips the round when the
    evidence cannot be read: no evidence must never read as "no alert"."""
    evidence = emulator.adb("exec-out", "run-as", PACKAGE, "cat", "files/notification-evidence.jsonl", timeout=60)
    if evidence is None:
        return
    names = config.get("catalogs") or catalogs.catalogs_for(lat, lon)
    events, failed = catalogs.fetch_events(lat, lon, names, time.time())
    for failure in failed:
        log(f"catalog not read: {failure}")
    if len(failed) == len(names):
        return
    early, late = alert_times(evidence)
    for event, km, verdict in catalogs.missed(events, lat, lon, early, late,
                                              time.time(), reported):
        health.note(verdict, mag=f"{event['mag']:.1f}", km=f"{km:.0f}", when=clock_time(event["time"]),
                    sources=", ".join(event["sources"]))
    # Only quakes still inside the look-back window can come up again; older keys are dropped.
    recent = {key: when for key, when in reported.items() if when > time.time() - 2 * catalogs.LOOK_BACK_S}
    reported.clear()
    reported.update(recent)
    reported_path(config["name"]).write_text(json.dumps(recent))


def parse_position(text):
    """The location contract: a JSON object with numeric "lat" and "lon". OwnTracks sends exactly
    that with "_type": "location"; its other messages (status, waypoints) are skipped with None.
    Anything else raises ValueError, which the admin hears about. Rounded to about 1 km: Google
    needs no more, and nothing finer is kept."""
    message = json.loads(text)
    if not isinstance(message, dict):
        raise ValueError("not a JSON object")
    if message.get("_type", "location") != "location":
        return None
    lat, lon = message.get("lat"), message.get("lon")
    if not all(isinstance(value, (int, float)) and not isinstance(value, bool) for value in (lat, lon)):
        raise ValueError("lat and lon must be numbers")
    check_coordinates(lat, lon)
    return round(lat, 2), round(lon, 2)


def fixed_receptors():
    """(name, lat, lon) of every receptor on this computer that stays at its place."""
    found = []
    for path in sorted(CONFIG_DIR.glob("*.json")):
        try:
            config = json.loads(path.read_text())
            if "avd" in config and not config.get("follow"):
                found.append((config["name"], config["lat"], config["lon"]))
        except (OSError, ValueError, KeyError, TypeError):
            continue
    return found


class Follower:
    """Decides what a following receptor does. Pure, so it can be tested without an emulator:
    feed it positions, call step() on every loop, act on what it returns."""

    def __init__(self, home_receptors, clock=time.monotonic):
        self.home_receptors = home_receptors
        self.clock = clock
        self.position = None
        self.applied = None
        self.applied_at = None
        self.near = None
        self.near_since = None
        self.asleep = False

    def update(self, lat, lon):
        self.position = (lat, lon)

    def nearest_home(self):
        if not self.position or not self.home_receptors:
            return None
        km, name = min((catalogs.km_between(*self.position, lat, lon), name)
                       for name, lat, lon in self.home_receptors)
        return name if km <= HOME_KM else None

    def step(self):
        """One of "sleep", "wake", "move" or None."""
        if not self.position:
            return None
        now = self.clock()
        near = self.nearest_home()
        if near != self.near:
            self.near, self.near_since = near, now
        if self.asleep:
            if near is None:
                self.asleep = False
                # It boots where the person is now, so that counts as the move.
                self.applied, self.applied_at = self.position, now
                return "wake"
            return None
        if near and now - self.near_since >= ASLEEP_AFTER_S:
            self.asleep = True
            return "sleep"
        if self.applied is None or (
                catalogs.km_between(*self.applied, *self.position) > MOVE_AFTER_KM
                and now - self.applied_at >= MOVE_EVERY_S):
            self.applied, self.applied_at = self.position, now
            return "move"
        return None


def status_path(name):
    return CONFIG_DIR / f"{name}.status.json"


def sleeping_neighbours(my_name):
    """Alert links of people whose following receptor sleeps near this fixed receptor."""
    links = []
    for path in CONFIG_DIR.glob("*.status.json"):
        try:
            status = json.loads(path.read_text())
        except (OSError, ValueError):
            continue
        if status.get("asleep") and status.get("near") == my_name and status.get("notify_url"):
            links.append(status["notify_url"])
    return sorted(links)


def follow_locations(url, token, on_message):
    """Reads the location link for ever, on its own thread. ntfy streams one JSON line per event;
    a dropped connection is retried, never fatal."""
    subscribe = urllib.parse.urlsplit(url)._replace(query="").geturl().rstrip("/") + "/json"
    while True:
        request = urllib.request.Request(subscribe)
        if token:
            request.add_header("Authorization", f"Bearer {token}")
        try:
            with urllib.request.urlopen(request, timeout=90) as stream:
                for line in stream:
                    event = json.loads(line)
                    if event.get("event") == "message":
                        on_message(event.get("message", ""))
        except (OSError, ValueError) as error:
            log(f"location link: {error}; reconnecting")
        time.sleep(10)


def owntracks_link(location_url, name):
    """Opens OwnTracks already pointed at the location link: HTTP mode, moves only."""
    settings = {"_type": "configuration", "mode": 3, "url": location_url, "monitoring": 1,
                "username": name, "deviceId": "canarito", "tid": name[:2]}
    encoded = base64.b64encode(json.dumps(settings).encode()).decode()
    return "owntracks:///config?inline=" + urllib.parse.quote(encoded, safe="")


def total_ram_gb():
    try:
        if sys.platform == "darwin":
            return int(subprocess.run(["sysctl", "-n", "hw.memsize"], capture_output=True, text=True).stdout) / 2**30
        with open("/proc/meminfo") as meminfo:
            return int(meminfo.readline().split()[1]) / 2**20
    except (OSError, ValueError):
        return None


class Emulator:
    def __init__(self, config):
        self.config = config
        self.serial = f"emulator-{config['port']}"
        self.adb_path = sdk_tool("platform-tools", "adb")
        self.position = (config["lat"], config["lon"])
        self.extra_urls = []

    def adb(self, *args, timeout=30, check=False):
        try:
            result = subprocess.run([self.adb_path, "-s", self.serial, *args],
                                    capture_output=True, text=True, timeout=timeout)
        except subprocess.TimeoutExpired:
            if check:
                raise RuntimeError(f"adb {' '.join(args)} timed out")
            return None
        if check and result.returncode != 0:
            raise RuntimeError(f"adb {' '.join(args)}: {result.stderr.strip() or result.stdout.strip()}")
        return result.stdout if result.returncode == 0 else None

    def start(self):
        emulator = sdk_tool("emulator", "emulator")
        log(f"starting emulator {self.config['avd']} on port {self.config['port']}")
        # Cold boot every time: a snapshot would bring back an old location.
        return subprocess.Popen(
            [emulator, "-avd", self.config["avd"], "-port", str(self.config["port"]), "-no-window",
             "-no-audio", "-no-snapshot", "-no-boot-anim", "-gpu", "swiftshader_indirect"],
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

    def uptime_s(self):
        output = self.adb("shell", "cat", "/proc/uptime", timeout=5)
        try:
            return float(output.split()[0])
        except (AttributeError, IndexError, ValueError):
            return None

    def boot_id(self):
        output = self.adb("shell", "cat", "/proc/sys/kernel/random/boot_id", timeout=5)
        return output.strip() if output else None

    def booted(self):
        return (self.adb("shell", "getprop", "sys.boot_completed", timeout=5) or "").strip() == "1"

    def geo_fix(self):
        # The console wants longitude first.
        self.adb("emu", "geo", "fix", str(self.position[1]), str(self.position[0]), timeout=5)

    def stop(self):
        self.adb("emu", "kill", timeout=20)

    def aea_registered(self):
        """Play Services' earthquake code asks for location under this name once it is alive.
        Without it the emulator looks healthy and can never get an alert."""
        dump = self.adb("shell", "dumpsys", "activity", "service", "com.google.android.gms", timeout=90)
        return dump is not None and "earthquake_alerting" in dump

    def provision(self, apk):
        """Installs the app and its config. Safe to repeat; runs after every boot."""
        if PACKAGE not in (self.adb("shell", "pm", "list", "packages", PACKAGE) or ""):
            # -g grants location: without it the GPS keeper cannot hold GPS open, later geo
            # fixes are ignored and the location ages until AEA stops alerting.
            self.adb("install", "-r", "-g", str(apk), timeout=120, check=True)
        dump = self.adb("shell", "dumpsys", "package", PACKAGE) or ""
        if "android.permission.ACCESS_FINE_LOCATION: granted=true" not in dump:
            raise RuntimeError("the app has no location permission; reinstall it with -g")
        if (self.adb("shell", "cmd", "location", "is-location-enabled") or "").strip() != "true":
            # Only when off: switching it off and on wipes the last location.
            self.adb("shell", "cmd", "location", "set-location-enabled", "true", check=True)
        self.write_relay()

    def write_relay(self):
        relay_json = relay_config(self.config, self.extra_urls)
        for attempt in range(3):
            self.adb("shell", write_relay_command(relay_json))
            # Without a sync a stop soon after can lose the file.
            self.adb("shell", "sync")
            if self.adb("exec-out", "run-as", PACKAGE, "cat", "files/relay.json") == relay_json:
                break
            time.sleep(2)
        else:
            raise RuntimeError("relay.json did not read back as written: the receptor would send nothing")
        # Rebind so the listener reads the config now and not at its next 5 min beat.
        self.adb("shell", "cmd", "notification", "disallow_listener", LISTENER)
        self.adb("shell", "cmd", "notification", "allow_listener", LISTENER, check=True)


def setup(args):
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    existing = json.loads(config_path(args.name).read_text()) if config_path(args.name).exists() else {}
    # A random topic: anyone who knows an ntfy.sh topic name can read it and post to it.
    notify_url = args.notify_url or existing.get("notify_url") or f"https://ntfy.sh/canarito-{secrets.token_hex(12)}"
    admin_url = args.admin_url or existing.get("admin_url") or f"https://ntfy.sh/canarito-admin-{secrets.token_hex(12)}"
    # cache=no: ntfy passes each position on and stores none.
    location_url = (args.location_url or existing.get("location_url")
                    or f"https://ntfy.sh/canarito-where-{secrets.token_hex(12)}?cache=no") if args.follow else ""
    config = {
        "name": args.name,
        "avd": f"canarito-{args.name}",
        "lat": args.lat,
        "lon": args.lon,
        "port": existing.get("port") or free_port(),
        "notify_url": notify_url,
        "admin_url": admin_url,
        "notify_token": args.notify_token or existing.get("notify_token", ""),
        "heartbeat_url": args.heartbeat_url or existing.get("heartbeat_url", ""),
        "language": args.language,
    }
    if args.follow:
        config["follow"] = True
        config["location_url"] = location_url
    others = [path for path in CONFIG_DIR.glob("*.json")
              if path.name.count(".") == 1 and path != config_path(args.name)]
    ram = total_ram_gb()
    if ram and (len(others) + 1) * EMULATOR_GB > 0.75 * ram:
        print(f"WARNING: {len(others) + 1} receptors need about {(len(others) + 1) * EMULATOR_GB} GB of RAM and this "
              f"computer has {ram:.0f} GB. An emulator without memory is killed while it boots.")
    image = system_image(platform.machine())
    sdkmanager = sdk_tool("cmdline-tools", "latest", "bin", "sdkmanager")
    image_dir = sdk_root().joinpath(*image.split(";"))
    missing = [package for package, path in (("platform-tools", sdk_root() / "platform-tools"),
                                             ("emulator", sdk_root() / "emulator"),
                                             (image, image_dir)) if not path.exists()]
    if missing:
        log(f"installing {', '.join(missing)} (a few GB the first time)")
        subprocess.run([sdkmanager, *missing], check=True)
    avd_home = Path(os.environ.get("ANDROID_AVD_HOME", Path.home() / ".android/avd"))
    if not (avd_home / f"{config['avd']}.avd").exists():
        avdmanager = sdk_tool("cmdline-tools", "latest", "bin", "avdmanager")
        subprocess.run([avdmanager, "create", "avd", "--name", config["avd"], "--package", image,
                        "--device", "pixel_8"], input="no\n", text=True, check=True)
    config_path(args.name).write_text(json.dumps(config, indent=2) + "\n")
    config_path(args.name).chmod(0o600)
    print(f"""
Receptor "{args.name}" ready at {args.lat}, {args.lon}.

On each device that should get the alerts:
  1. Install ntfy (App Store, Google Play) or open https://ntfy.sh/app in a browser.
  2. Subscribe to: {notify_url}
  3. Allow notifications. On Android, set the subscription to "urgent" so it can ring.

For you, who runs this computer, also subscribe to:
  {admin_url}
It tells you when this receptor stops working and when it is back, and about quakes it missed.

Then start it, and leave it running:
  canarito.py run --name {args.name}
""")
    if args.follow:
        link = owntracks_link(location_url, args.name)
        sent = post_notice(notify_url, config["notify_token"], "Toca aquí con OwnTracks instalado para que Canarito "
                           "te siga. / Tap here with OwnTracks installed so Canarito can follow you.", click=link)
        print(f"""This receptor follows {args.name}. On {args.name}'s phone:
  1. Subscribe ntfy to the link above.
  2. Install OwnTracks (App Store or Google Play).
  3. Tap the Canarito message that just arrived{"" if sent else " (it could not be sent; open the link below instead)"}.
     It opens OwnTracks already set up. The same link: {link}
""")
        if urllib.parse.urlsplit(location_url).hostname == "ntfy.sh":
            print("The position passes through ntfy.sh on its way to this computer. ntfy.sh does not store it,\n"
                  "but it sees it. To keep it on your own server, run setup again with --location-url.\n")


def verified_download(url, expected_sha256, target):
    """Downloads url to target only when its SHA-256 matches; returns whether it did."""
    with urllib.request.urlopen(urllib.request.Request(url, headers={"User-Agent": "canarito"}),
                                timeout=60) as response:
        data = response.read()
    if hashlib.sha256(data).hexdigest() != expected_sha256:
        return False
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(data)
    return True


def find_apk(path):
    apk = Path(path)
    if apk.exists():
        return apk
    if apk != DEFAULT_APK:
        sys.exit(f"No APK at {apk}.")
    released = CONFIG_DIR / f"canarito-{RELEASE_APK_SHA256[:12]}.apk"
    if released.exists() and hashlib.sha256(released.read_bytes()).hexdigest() == RELEASE_APK_SHA256:
        return released
    print(f"No local build. Downloading the released APK from {RELEASE_APK_URL}")
    try:
        if verified_download(RELEASE_APK_URL, RELEASE_APK_SHA256, released):
            return released
        sys.exit("The downloaded APK does not match the expected SHA-256. Not installing it. "
                 "Build it yourself (README.md).")
    except OSError as error:
        sys.exit(f"Could not download the APK ({error}). Build it yourself (README.md) or pass --apk.")


def run(args):
    config = load_config(args.name)
    apk = find_apk(args.apk)
    links = {"family": config["notify_url"], "admin": config.get("admin_url") or config["notify_url"]}
    health = Health(config, lambda audience, text, priority: post_notice(
        links[audience], config.get("notify_token"), text, priority))
    emulator = Emulator(config)
    process = None
    provisioned_boot = None
    aea_seen = False
    aea_checked_at = 0
    down_since = None
    missed_checked_at = -MISSED_CHECK_EVERY_S
    try:
        reported = dict(json.loads(reported_path(config["name"]).read_text()))
    except (OSError, ValueError, TypeError):
        reported = {}
    started_at = -RESTART_EVERY_S
    follower = None
    if config.get("follow"):
        follower = Follower(fixed_receptors())
        positions, invalid = [], []

        def on_message(text):
            try:
                position = parse_position(text)
            except ValueError as error:
                invalid.append(str(error))
                return
            if position:
                positions.append(position)

        try:
            saved = json.loads(status_path(config["name"]).read_text()).get("position")
        except (OSError, ValueError):
            saved = None
        if saved:
            follower.update(*saved)
            emulator.position = tuple(saved)
        last_position_at = time.time()
        threading.Thread(target=follow_locations, daemon=True,
                         args=(config["location_url"], config.get("notify_token"), on_message)).start()
    last_wall, last_mono = time.time(), time.monotonic()
    while True:
        # Monotonic time stops while the computer sleeps; the wall clock does not.
        wall, mono = time.time(), time.monotonic()
        if (wall - last_wall) - (mono - last_mono) > SLEPT_AFTER_S:
            health.note("slept", start=clock_time(last_wall), end=clock_time(wall))
        last_wall, last_mono = wall, mono

        if follower:
            while positions:
                follower.update(*positions.pop(0))
                last_position_at = wall
                health.clear("location_stale")
                health.clear("location_invalid")
            if invalid:
                health.problem("location_invalid", error=invalid[-1])
                invalid.clear()
            if wall - last_position_at > NO_POSITION_AFTER_S:
                health.problem("location_stale")
            action = follower.step()
            if action in ("move", "wake"):
                emulator.position = follower.position
            if action == "move":
                log(f"moving to {follower.position[0]}, {follower.position[1]}")
            elif action == "sleep":
                log(f"asleep: {config['name']} is home, near {follower.near}")
                emulator.stop()
            elif action == "wake":
                log(f"awake: {config['name']} left home")
            if action:
                status_path(config["name"]).write_text(json.dumps({
                    "asleep": follower.asleep, "near": follower.near, "notify_url": config["notify_url"],
                    "position": follower.position}))
            if follower.asleep:
                down_since = None
                health.clear("emulator_down")
                health.tick()
                time.sleep(IDLE_EVERY_S)
                continue

        uptime = emulator.uptime_s()
        if uptime is None:
            down_since = down_since or mono
            if mono - down_since > EMULATOR_DOWN_AFTER_S:
                health.problem("emulator_down")
            if (process is None or process.poll() is not None) and mono - started_at >= RESTART_EVERY_S:
                process = emulator.start()
                started_at = mono
        else:
            down_since = None
            health.clear("emulator_down")
        booting = uptime is None or uptime < BOOT_WINDOW_S
        # A following receptor repeats its fix: one fix is enough with the GPS keeper, a repeat is free.
        if booting or follower:
            emulator.geo_fix()
        if uptime is not None and emulator.booted():
            boot_id = emulator.boot_id()
            if boot_id and boot_id != provisioned_boot:
                try:
                    emulator.provision(apk)
                    provisioned_boot = boot_id
                    health.clear("provision")
                    log("receptor provisioned; listening for alerts")
                except RuntimeError as error:
                    health.problem("provision", error=error)
                    log(f"PROVISION FAILED, retrying: {error}")
            if not aea_seen and mono - aea_checked_at > AEA_CHECK_EVERY_S:
                aea_checked_at = mono
                aea_seen = emulator.aea_registered()
                if aea_seen:
                    health.clear("aea")
                    log("AEA registered: this receptor can get alerts")
                elif uptime > AEA_GIVE_UP_S:
                    health.problem("aea")
                    log(f"AEA NOT REGISTERED after {uptime / 60:.0f} min. Some emulators never do: "
                        f"delete the AVD {config['avd']} and run setup again.")
            if uptime > REBOOT_EVERY_S:
                log("rebooting for a fresh location")
                emulator.adb("reboot")
                # Long enough for the guest to drop off adb, so this does not fire twice.
                time.sleep(IDLE_EVERY_S)
            if not follower and provisioned_boot == boot_id:
                neighbours = sleeping_neighbours(config["name"])
                if neighbours != emulator.extra_urls:
                    emulator.extra_urls = neighbours
                    try:
                        emulator.write_relay()
                        log(f"also sending to {len(neighbours)} sleeping following receptor(s)")
                    except RuntimeError as error:
                        log(f"could not update the links: {error}")
            if mono - missed_checked_at > MISSED_CHECK_EVERY_S:
                missed_checked_at = mono
                check_missed(config, emulator, health, reported, *emulator.position)
        health.tick()
        time.sleep(FIX_EVERY_S if booting else IDLE_EVERY_S)


def test(args):
    config = load_config(args.name)
    request = urllib.request.Request(config["notify_url"], method="POST",
                                     data="Canarito test. If you see this, the phone side works.".encode(),
                                     headers={"Title": "Canarito test", "Tags": "white_check_mark"})
    if config.get("notify_token"):
        request.add_header("Authorization", f"Bearer {config['notify_token']}")
    with urllib.request.urlopen(request, timeout=10) as response:
        print(f"ntfy answered {response.status}: check your phone.")
    if config.get("admin_url") and post_notice(config["admin_url"], config.get("notify_token"),
                                               "Canarito test on the admin link."):
        print("admin link: test sent.")
    emulator = Emulator(config)
    relay = emulator.adb("exec-out", "run-as", PACKAGE, "cat", "files/relay.json", timeout=10)
    listeners = emulator.adb("shell", "settings", "get", "secure", "enabled_notification_listeners", timeout=10) or ""
    uptime = emulator.uptime_s()
    print(f"emulator {emulator.serial}: {'up %.0f min' % (uptime / 60) if uptime else 'NOT RUNNING'}")
    print(f"relay.json: {'ok' if relay == relay_config(config) else 'MISSING OR STALE'}")
    print(f"listener: {'allowed' if PACKAGE in listeners else 'NOT ALLOWED'}")
    if uptime:
        print(f"AEA: {'registered' if emulator.aea_registered() else 'NOT REGISTERED (normal up to 60 min after the first boot)'}")
    print("A real alert can only be tested by a real quake. See README.md, What can go wrong.")


def evidence(args):
    output = Emulator(load_config(args.name)).adb(
        "exec-out", "run-as", PACKAGE, "cat", "files/notification-evidence.jsonl", timeout=30)
    if output is None:
        sys.exit("Could not read the evidence file. Is the emulator running?")
    sys.stdout.write(output)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    commands = parser.add_subparsers(dest="command", required=True)

    setup_parser = commands.add_parser("setup", help="create or update a receptor")
    setup_parser.add_argument("--name", default="home")
    setup_parser.add_argument("--lat", type=float, required=True)
    setup_parser.add_argument("--lon", type=float, required=True)
    setup_parser.add_argument("--notify-url", help="ntfy topic URL (default: a new random ntfy.sh topic)")
    setup_parser.add_argument("--follow", action="store_true",
                              help="this receptor follows one person's phone (lat/lon is where it starts)")
    setup_parser.add_argument("--location-url", help="ntfy topic URL the phone posts its position to")
    setup_parser.add_argument("--admin-url", help="ntfy topic URL for health notices (default: a new random ntfy.sh topic)")
    setup_parser.add_argument("--notify-token", help="ntfy access token, for a protected topic")
    setup_parser.add_argument("--heartbeat-url", help="pinged every 5 min, e.g. a healthchecks.io check")
    setup_parser.add_argument("--language", choices=("es", "en"), default="es")
    setup_parser.set_defaults(handler=setup)

    run_parser = commands.add_parser("run", help="start the receptor and keep it alive (foreground)")
    run_parser.add_argument("--name", default="home")
    run_parser.add_argument("--apk", default=str(DEFAULT_APK))
    run_parser.set_defaults(handler=run)

    test_parser = commands.add_parser("test", help="send a test message and check the receptor")
    test_parser.add_argument("--name", default="home")
    test_parser.set_defaults(handler=test)

    evidence_parser = commands.add_parser("evidence", help="print everything the receptor captured")
    evidence_parser.add_argument("--name", default="home")
    evidence_parser.set_defaults(handler=evidence)

    args = parser.parse_args(argv)
    if getattr(args, "lat", None) is not None:
        try:
            check_coordinates(args.lat, args.lon)
        except ValueError as error:
            parser.error(str(error))
    args.handler(args)


if __name__ == "__main__":
    main()
