"""What the iOS app talks to: pairing, device registry, position intake, and sending alerts to the
push relay. docs/app-contract.md is the contract. Knows nothing about receptors: canarito.py
passes in what it needs (status, language, where positions go)."""
import fcntl
import hashlib
import hmac
import json
import os
import re
import secrets
import time
import urllib.error
import urllib.parse
import urllib.request
from contextlib import contextmanager
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

PAIRING_TTL_S = 10 * 60
ALERT_TTL_S = 180
LATE_AFTER_S = 60
RETRY_EVERY_S = 5
# About 190 bytes per handle: 15 stay well under the 4 KB an older relay accepts.
PUSH_CHUNK = 15
PUSH_FAILURE_MEMORY_S = 15 * 60
RELAY_CHECK_EVERY_S = 5 * 60
POSITION_EVERY_S = 10
TEST_EVERY_S = 10 * 60
DRILL_EVERY_S = 10 * 60
DEMO_TEST_EVERY_S = 10
# A demo secret is reusable, so its devices are capped: the oldest go first.
MAX_DEMO_DEVICES = 50
MAX_BODY = 2048
MAGNITUDE = re.compile(r"\bM(\d+(?:\.\d+)?)")


def sha(text):
    return hashlib.sha256(text.encode()).hexdigest()


class Devices:
    """devices.json: open pairings and paired phones. Secrets and keys are kept as hashes. Several
    processes use it (pair, serve, every receptor), so every change runs under a file lock."""

    def __init__(self, config_dir):
        self.path = config_dir / "devices.json"
        self.lock_path = config_dir / "devices.lock"

    @contextmanager
    def _locked(self):
        with open(self.lock_path, "a") as lock:
            fcntl.flock(lock, fcntl.LOCK_EX)
            yield

    def snapshot(self):
        try:
            data = json.loads(self.path.read_text())
        except (OSError, ValueError):
            data = {}
        data.setdefault("server_url", "")
        data.setdefault("pairings", {})
        data.setdefault("devices", {})
        return data

    def _change(self, change):
        with self._locked():
            data = self.snapshot()
            result = change(data)
            temporary = self.path.with_suffix(".tmp")
            temporary.write_text(json.dumps(data, indent=1))
            temporary.chmod(0o600)
            temporary.replace(self.path)
            return result

    def set_server_url(self, url):
        self._change(lambda data: data.update(server_url=url.rstrip("/")))

    def set_serve_port(self, port):
        """Where `serve` listens, so the watchdog knows there is an app server to watch."""
        self._change(lambda data: data.update(serve_port=port))

    def new_pairing(self, receptor, now, demo=False):
        """A pairing secret: single use for 10 minutes. Demo (App Review): reusable and without
        expiry until end_demo(), and the devices it pairs get test pushes only."""
        secret = secrets.token_hex(16)

        def add(data):
            # Expired ones go; a new demo secret replaces the old demo one.
            data["pairings"] = {key: p for key, p in data["pairings"].items()
                                if (not demo if p.get("demo") else p["expires"] > now)}
            data["pairings"][sha(secret)] = (
                {"receptor": receptor, "expires": None, "demo": True} if demo
                else {"receptor": receptor, "expires": now + PAIRING_TTL_S})
        self._change(add)
        return secret

    def end_demo(self):
        """Turns demo mode off: the reusable secret stops working and its devices are removed."""
        def remove(data):
            data["pairings"] = {key: p for key, p in data["pairings"].items() if not p.get("demo")}
            gone = [device_id for device_id, device in data["devices"].items() if device.get("demo")]
            for device_id in gone:
                del data["devices"][device_id]
            return len(gone)
        return self._change(remove)

    def pair(self, secret, handle, name, now):
        """The new device, or None for a secret that is wrong, used or expired. A normal secret is
        burned on first use; the demo one stays."""
        def add(data):
            pairing = data["pairings"].get(sha(secret))
            if not pairing or (pairing["expires"] is not None and pairing["expires"] <= now):
                return None
            if not pairing.get("demo"):
                del data["pairings"][sha(secret)]
            device_id = "d_" + secrets.token_hex(4)
            key = secrets.token_hex(32)
            data["devices"][device_id] = {"receptor": pairing["receptor"], "key_hash": sha(key),
                                          "handle": handle, "name": name[:60], "paired_at": int(now)}
            if pairing.get("demo"):
                data["devices"][device_id]["demo"] = True
                demo_ids = sorted((d["paired_at"], i) for i, d in data["devices"].items() if d.get("demo"))
                for _, old_id in demo_ids[:-MAX_DEMO_DEVICES]:
                    del data["devices"][old_id]
            return {"device_id": device_id, "device_key": key, "receptor": pairing["receptor"]}
        return self._change(add)

    def by_key(self, key):
        """(device_id, device) for a device key, or None."""
        wanted = sha(key)
        for device_id, device in self.snapshot()["devices"].items():
            if hmac.compare_digest(device["key_hash"], wanted):
                return device_id, device
        return None

    def update_device(self, device_id, **fields):
        def apply(data):
            if device_id in data["devices"]:
                data["devices"][device_id].update(fields)
        self._change(apply)

    def remove(self, device_id):
        self._change(lambda data: data["devices"].pop(device_id, None))

    def handles_for(self, receptor):
        """{device_id: handle} of the phones that belong to this receptor. Never demo devices:
        they are not people, and a real alert must not go to a reviewer."""
        return {device_id: device["handle"] for device_id, device in self.snapshot()["devices"].items()
                if device["receptor"] == receptor and device.get("handle") and not device.get("demo")}


class RelayError(Exception):
    def __init__(self, message, status=None, code=""):
        super().__init__(message)
        self.status, self.code = status, code


class RelayClient:
    def __init__(self, url, server_id, server_key, clock=time.time, opener=urllib.request.urlopen):
        self.url, self.server_id, self.server_key = url.rstrip("/"), server_id, server_key
        self.clock, self.opener = clock, opener

    def _signed_post(self, body):
        timestamp = str(int(self.clock()))
        signature = hmac.new(bytes.fromhex(self.server_key), f"{timestamp}\n{body}".encode(), "sha256").hexdigest()
        return post_json(self.url + "/v1/push", body, {
            "X-Canarito-Server": self.server_id, "X-Canarito-Timestamp": timestamp,
            "X-Canarito-Signature": signature}, self.opener)

    def push(self, handles, alert, critical=False):
        """One result per handle: {"status": "sent" | "gone" | "rejected" | "failed", "reason"?}."""
        answer = self._signed_post(json.dumps({"handles": handles, "alert": alert, "critical": critical},
                                              separators=(",", ":")))
        results = answer.get("results") if isinstance(answer, dict) else None
        if not isinstance(results, list) or len(results) != len(handles):
            raise RelayError("the relay answered something else than one result per phone")
        return results

    def check(self):
        """Raises RelayError unless the relay is up, knows this server's signature and has its APNs
        settings. A signed push with no phones: a healthy relay refuses it with 400 bad_request
        and sends nothing. It does not prove the APNs key itself is still valid."""
        try:
            self._signed_post('{"handles":[]}')
        except RelayError as error:
            if error.status == 400 and error.code == "bad_request":
                return
            raise
        raise RelayError("the relay accepted a push with no phones; it is not the Canarito relay")


def post_json(url, body, headers, opener=urllib.request.urlopen):
    request = urllib.request.Request(url, method="POST", data=body.encode(),
                                     headers={"Content-Type": "application/json", **headers})
    try:
        with opener(request, timeout=10) as response:
            return json.loads(response.read())
    except urllib.error.HTTPError as error:
        try:
            code = json.loads(error.read()).get("error", "")
        except (ValueError, AttributeError):
            code = ""
        raise RelayError(f"relay answered {error.code} {code}".strip(), error.code, code) from error
    except (OSError, ValueError) as error:
        raise RelayError(f"relay not reachable: {error}") from error


def relay_file(config_dir):
    return config_dir / "relay-server.json"


def load_relay(config_dir):
    """The relay this server is registered at, or None."""
    try:
        saved = json.loads(relay_file(config_dir).read_text())
        return RelayClient(saved["url"], saved["server_id"], saved["server_key"])
    except (OSError, ValueError, KeyError):
        return None


def register_relay(config_dir, url, opener=urllib.request.urlopen):
    """Gets this server's id and key from the relay, once. Raises RelayError."""
    answer = post_json(url.rstrip("/") + "/v1/servers", "{}", {}, opener)
    saved = {"url": url.rstrip("/"), "server_id": answer.get("server_id"), "server_key": answer.get("server_key")}
    if not all(isinstance(value, str) and value for value in saved.values()):
        raise RelayError("the relay did not answer with a server id and key")
    path = relay_file(config_dir)
    path.write_text(json.dumps(saved))
    path.chmod(0o600)
    return load_relay(config_dir)


def pairing_url(server_url, secret, relay):
    query = urllib.parse.urlencode({"v": 1, "server": server_url, "secret": secret,
                                    "relay": relay.url, "sid": relay.server_id}, quote_via=urllib.parse.quote)
    return "canarito://pair?" + query


def alert_from_event(event, receptor, language, now):
    """The alert to push for an ntfy event, or None when it is not one. The receptor posts its
    alerts as urgent (priority 5); notices and tests use lower ones."""
    if event.get("event") != "message" or event.get("priority") != 5:
        return None
    sent_at = event.get("time") or int(now)
    alert = {"id": event.get("id") or f"{receptor}-{sent_at}", "receptor": receptor, "lang": language,
             "title": event.get("title") or "Canarito", "body": event.get("message") or "", "sent_at": sent_at}
    magnitude = MAGNITUDE.search(alert["body"])
    if magnitude:
        alert["magnitude"] = float(magnitude.group(1))
    if now - sent_at > LATE_AFTER_S:
        alert["late"] = True
    return alert


DRILL_TEXT = {
    "es": ("SIMULACRO de Canarito", "SIMULACRO. No hay ningún sismo, es una prueba de Canarito. No hagas nada."),
    "en": ("Canarito DRILL", "DRILL. There is no earthquake, this is a Canarito test. Do nothing."),
}


def drill_alert(receptor, language, now):
    """A fake alert for the phones of one receptor. It is not an ntfy event, so the receptor's own
    link, and the Android phones on it, never see it. Marked in the title, the body and `drill`."""
    title, body = DRILL_TEXT.get(language, DRILL_TEXT["es"])
    return {"id": f"drill-{secrets.token_hex(4)}", "receptor": receptor, "lang": language,
            "title": title, "body": body, "sent_at": int(now), "drill": True}


def drill_wait(stamp_path, now):
    """Seconds until a drill is allowed again; 0 when it is, and then the time is recorded."""
    try:
        wait = float(stamp_path.read_text()) + DRILL_EVERY_S - now
    except (OSError, ValueError):
        wait = 0
    if wait > 0:
        return wait
    stamp_path.write_text(str(now))
    stamp_path.chmod(0o600)
    return 0


def check_relay(devices, relay_loader, health, receptor, set_relay_ok, clock=time.time, sleep=time.sleep):
    """Between alerts: tells the admin and the app that the relay is down before a quake finds out.
    Silent for a receptor with no phones. A failure is confirmed once more before it is told."""
    if not devices.handles_for(receptor):
        return
    failure = None
    for attempt in range(2):
        try:
            relay = relay_loader()
            if relay is None:
                raise RelayError("no relay configured; run canarito.py pair --relay-url ...")
            relay.check()
            failure = None
            break
        except RelayError as error:
            failure = str(error)
            if attempt == 0:
                sleep(RETRY_EVERY_S)
    if failure:
        health.problem("relay", error=failure)
        set_relay_ok(False)
    elif clock() - getattr(health, "push_failed_at", -PUSH_FAILURE_MEMORY_S) >= PUSH_FAILURE_MEMORY_S:
        # A recent failed alert push stays the last word: the check cannot see an APNs problem.
        health.clear("relay")
        set_relay_ok(True)


def deliver_alert(devices, relay_loader, health, receptor, alert, set_relay_ok,
                  clock=time.time, sleep=time.sleep):
    """Pushes an alert to every phone of a receptor and keeps trying, for as long as the alert is
    still worth sending, until each one got it. Whatever does not work is told to the admin: a
    failure here is never silent."""
    pending = devices.handles_for(receptor)
    if not pending:
        return 0
    while True:
        failure = None
        ids = list(pending)
        # Chunks, because a relay refuses a request over its body limit and then nobody gets it.
        for start in range(0, len(ids), PUSH_CHUNK):
            chunk = ids[start:start + PUSH_CHUNK]
            try:
                relay = relay_loader()
                if relay is None:
                    raise RelayError("no relay configured; run canarito.py pair --relay-url ...")
                results = relay.push([pending[device_id] for device_id in chunk], alert)
            except RelayError as error:
                failure = str(error)
                continue
            for device_id, result in zip(chunk, results):
                status = result.get("status") if isinstance(result, dict) else None
                if status == "sent":
                    del pending[device_id]
                elif status in ("gone", "rejected"):
                    name = devices.snapshot()["devices"].get(device_id, {}).get("name", device_id)
                    devices.remove(device_id)
                    del pending[device_id]
                    health.note("device_gone", device=name)
                else:
                    failure = f"{result.get('reason', 'unknown') if isinstance(result, dict) else 'unknown'}"
        if failure:
            health.push_failed_at = clock()
            health.problem("relay", error=failure)
            set_relay_ok(False)
        else:
            health.clear("relay")
            set_relay_ok(True)
        if not pending:
            return 0
        if clock() - alert["sent_at"] > ALERT_TTL_S:
            health.note("alert_not_pushed", count=len(pending), error=failure or "")
            return len(pending)
        sleep(RETRY_EVERY_S)


def make_server(bind, port, devices, relay_loader, status_for, language_for, save_position,
                read_position, clock=time.time):
    """The HTTP side of docs/app-contract.md, sections 2 to 4."""
    last_position, last_test = {}, {}

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *args):
            pass

        def reply(self, status, body=None, headers=()):
            payload = b"" if body is None else json.dumps(body).encode()
            self.send_response(status)
            if payload:
                self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(payload)))
            for name, value in headers:
                self.send_header(name, value)
            self.end_headers()
            self.wfile.write(payload)

        def fail(self, status, error):
            self.reply(status, {"error": error})

        def body(self):
            """The request text; replies and returns None when it is too big."""
            length = int(self.headers.get("Content-Length") or 0)
            if length > MAX_BODY:
                self.fail(413, "too_large")
                return None
            return self.rfile.read(length).decode(errors="replace")

        def json_body(self):
            text = self.body()
            if text is None:
                return None
            try:
                parsed = json.loads(text)
            except ValueError:
                parsed = None
            if not isinstance(parsed, dict):
                self.fail(400, "bad_request")
                return None
            return parsed

        def device(self):
            header = self.headers.get("Authorization", "")
            found = devices.by_key(header[7:]) if header.startswith("Bearer ") else None
            if not found:
                self.fail(401, "bad_key")
            return found

        def route(self, method):
            path = urllib.parse.urlsplit(self.path).path
            if (method, path) == ("POST", "/v1/pair"):
                return self.pair()
            if path not in ("/v1/device", "/v1/position", "/v1/status", "/v1/test"):
                return self.fail(404, "not_found")
            found = self.device()
            if not found:
                return None
            device_id, device = found
            now = clock()
            if (method, path) == ("PUT", "/v1/device"):
                body = self.json_body()
                if body is None:
                    return None
                handle = body.get("handle")
                if not isinstance(handle, str) or not 0 < len(handle) <= 1000:
                    return self.fail(400, "bad_request")
                devices.update_device(device_id, handle=handle)
                return self.reply(204)
            if (method, path) == ("DELETE", "/v1/device"):
                devices.remove(device_id)
                return self.reply(204)
            if (method, path) == ("GET", "/v1/status"):
                if device.get("demo"):  # a demo server has no receptor running; the reviewer must see a working app
                    return self.reply(200, {"receptor": device["receptor"], "covered": True, "receptor_up": True,
                                            "relay_ok": True, "following": False})
                return self.reply(200, status_for(device["receptor"]))
            if (method, path) == ("POST", "/v1/position"):
                text = self.body()
                if text is None:
                    return None
                if now - last_position.get(device_id, 0) < POSITION_EVERY_S:
                    return self.fail(429, "slow_down")
                try:
                    position = read_position(text)
                except ValueError:
                    position = None
                if not position:
                    return self.fail(400, "bad_request")
                last_position[device_id] = now
                if device.get("demo"):
                    return self.reply(204)  # a reviewer must not move a receptor
                save_position(device["receptor"], *position)
                return self.reply(204)
            if (method, path) == ("POST", "/v1/test"):
                return self.test(device_id, device, now)
            return self.fail(404, "not_found")

        def pair(self):
            body = self.json_body()
            if body is None:
                return None
            secret, handle, name = body.get("secret"), body.get("handle"), body.get("name", "")
            if not (isinstance(secret, str) and isinstance(handle, str) and isinstance(name, str)
                    and 0 < len(handle) <= 1000):
                return self.fail(400, "bad_request")
            paired = devices.pair(secret, handle, name, clock())
            if not paired:
                return self.fail(403, "bad_secret")
            return self.reply(200, {**paired, "language": language_for(paired["receptor"])})

        def test(self, device_id, device, now):
            every = DEMO_TEST_EVERY_S if device.get("demo") else TEST_EVERY_S
            if now - last_test.get(device_id, -every) < every:
                return self.fail(429, "slow_down")
            last_test[device_id] = now
            language = language_for(device["receptor"])
            alert = {"id": f"test-{secrets.token_hex(4)}", "receptor": device["receptor"], "lang": language,
                     "title": "Canarito", "test": True, "sent_at": int(now),
                     "body": "Prueba de Canarito. Si ves esto, las alertas llegan a tu iPhone." if language == "es"
                     else "Canarito test. If you see this, alerts reach your iPhone."}
            try:
                relay = relay_loader()
                result = relay.push([device["handle"]], alert)[0] if relay else {"status": "failed"}
            except RelayError:
                result = {"status": "failed"}
            return self.reply(204) if result.get("status") == "sent" else self.fail(502, "relay_failed")

        def do_GET(self):
            self.route("GET")

        def do_POST(self):
            self.route("POST")

        def do_PUT(self):
            self.route("PUT")

        def do_DELETE(self):
            self.route("DELETE")

    return ThreadingHTTPServer((bind, port), Handler)
