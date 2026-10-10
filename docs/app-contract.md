# App contract

One contract for three pieces: the iOS app, the Canarito server (`canarito.py`) and the push
relay (`relay/`). Version 1. If something here changes, the app, the server and the relay change
in the same commit.

All bodies are JSON (`Content-Type: application/json`), UTF-8. All URLs are HTTPS. Every error is
`{"error": "<code>"}` with the HTTP status in the table at the end. Examples use fake values.

## Who talks to whom

```
app  --QR-->      reads server URL, pairing secret, relay URL, server id
app  --relay-->   POST /v1/handles      (APNs token in, opaque handle out)
app  --server-->  POST /v1/pair         (secret + handle in, device key out)
app  --server-->  POST /v1/position     (every move)
server --relay--> POST /v1/push         (signed, one per alert)
relay --APNs-->   phone
```

The phone never talks to a receptor. The relay never talks to a server. The relay stores nothing:
no device, no pairing, no alert (see "Why the relay needs no database").

## 1. QR payload

The QR holds one URL. The iPhone camera can open it, and so can the in-app scanner.

```
canarito://pair?v=1&server=https%3A%2F%2Fcanarito.example.org&secret=3f9c...&relay=https%3A%2F%2Frelay.example.org&sid=a1b2...
```

| param | meaning |
|---|---|
| `v` | contract version, `1` |
| `server` | base URL of this server's app endpoints, no trailing slash |
| `secret` | pairing secret, 32 hex chars, single use, valid 10 minutes |
| `relay` | base URL of the push relay this server uses |
| `sid` | the server's id at that relay, 32 hex chars |

An app that sees `v` other than `1` says "update the app" and stops. `canarito.py pair --name X`
prints this QR in the terminal, writes `pair-X.png` and prints the URL as text (for a phone that
cannot scan).

## 2. Pairing

Done once per phone, in this order.

### 2a. App to relay: get a handle

`POST {relay}/v1/handles`

```json
{"server_id": "a1b2...", "apns_token": "<64+ hex chars>", "environment": "production"}
```

`environment` is `production` or `sandbox` (debug builds). Answer `200`:

```json
{"handle": "<base64url, opaque>"}
```

The handle is the APNs token sealed so that only the relay can open it, and bound to `server_id`.
The app treats it as a string. It asks for a new one whenever iOS gives it a new APNs token and
sends it to the server with `PUT /v1/device` (2c).

### 2b. App to server: pair

`POST {server}/v1/pair`

```json
{"secret": "3f9c...", "handle": "<from 2a>", "name": "Sebastian's iPhone"}
```

`name` is free text for the admin (max 60 chars). Answer `200`:

```json
{"device_id": "d_8f2a41c0", "device_key": "<64 hex chars>", "receptor": "sebastian", "language": "es"}
```

`device_key` is the app's only credential for the server. The app keeps it in the Keychain and
sends `Authorization: Bearer <device_key>` on every later call. `receptor` is the name of the
receptor this phone belongs to. `language` is `es` or `en`: the alert language of that receptor.
The secret is burned on first use. A wrong, used or expired secret gets `403 bad_secret`.

### 2c. New token or leaving

`PUT {server}/v1/device` (Bearer) with `{"handle": "<new handle>"}` answers `204`.
`DELETE {server}/v1/device` (Bearer) removes the phone from the server and answers `204`.

### 2d. Demo code (App Review)

`canarito.py pair --name X --demo` prints a QR with the same URL format whose secret is reusable
and never expires, until `pair --name X --demo-off`. The app sees no difference. On the server,
phones paired with it get `POST /v1/test` pushes only (rate: once per 10 s), never real alerts,
and their positions are ignored (`204`). Meant for a server with no real people.

## 3. Position

`POST {server}/v1/position` (Bearer)

```json
{"lat": 4.71, "lon": -74.07}
```

Numbers, WGS84. The server rounds to 2 decimals (about 1 km) and keeps nothing finer, the app
should round before sending too. Answer `204`. The server answers `429 slow_down` when the same
device sends more than once per 10 s; the app waits and sends the latest position later.

The app sends when the phone has moved more than about 1 km since the last position it sent, and
once after pairing. It need not send while still. The server does not need a heartbeat.

A phone paired to a receptor that does not follow (a fixed receptor at home) still gets `204`; the
position is ignored.

## 4. Alert push

The server sends an alert to the relay when its receptor posts one to the receptor's alert link
(the same event that goes to ntfy; both are sent). The app gets this APNs payload:

```json
{
  "aps": {
    "alert": {"title": "Alerta de sismo", "body": "Sismo M5.4 cerca de tu zona. Protégete ahora."},
    "sound": "default",
    "interruption-level": "time-sensitive"
  },
  "canarito": {
    "v": 1,
    "id": "ntfy-event-id",
    "receptor": "sebastian",
    "lang": "es",
    "sent_at": 1791650000,
    "magnitude": 5.4,
    "late": false
  }
}
```

- `title` and `body` are the receptor's own text, already in `es` or `en`. The app shows
  `aps.alert` as is and never rewrites it.
- `id` is the same for the same alert. The app drops an `id` it already showed (the server can
  send twice after a reconnect).
- Optional, only when the server knows them: `magnitude` (number, read from the receptor's text),
  `occurred_at` (epoch s, not sent today, the receptor does not report it), `late: true` when the
  alert was more than 60 s old at send time, `test: true` for section 4a. Absent means the app
  shows only `aps.alert`.
- `sent_at` is epoch seconds when the receptor posted it. APNs `apns-expiration` is `sent_at + 180`:
  a warning older than 3 minutes is useless and is not delivered late.
- `interruption-level` is `time-sensitive` now. When Apple grants Critical Alerts the server sets
  `"critical": true` in the push request (section 5) and the relay sends `critical` with sound
  `{"critical": 1, "name": "default", "volume": 1.0}`. The app needs no change for the payload.

### 4a. Status and test

`GET {server}/v1/status` (Bearer) answers `200`:

```json
{"receptor": "sebastian", "covered": true, "receptor_up": true, "relay_ok": true, "following": false}
```

`covered`: this phone's receptor, or another one sending for it, can get alerts right now.
`receptor_up`: the receptor process answered in the last 2 minutes. `relay_ok`: the last push to
the relay worked. `following`: the receptor follows phones. `receptor_up` or `relay_ok` false: the
app says "alerts may not arrive" on the home screen. No answer from the server: "server unreachable".

`POST {server}/v1/test` (Bearer) pushes one test alert to this device only, in the receptor's
language, with `canarito.test: true`. Answer `204`; `429 slow_down` when asked again within 10 min;
`502 relay_failed` when the relay did not deliver (the app shows it).

Debug builds of the app may use `http://` for `localhost` and `127.0.0.1` only. A pasted
`canarito://pair?...` URL works like the QR.

## 5. Relay API

Base URL is `relay` from the QR. The relay is open source and anyone can run one; Canarito's own
runs on AWS Lambda.

### `POST /v1/servers`: register a server (once, by `canarito.py pair`)

No body. Answer `200`:

```json
{"server_id": "a1b2... (32 hex)", "server_key": "<64 hex>"}
```

The server stores both in `relay-server.json` (mode 600). The key is shown once by this call but
the relay can always recompute it, see below.

### `POST /v1/handles`: see 2a.

### `POST /v1/push`: send an alert

Headers:

| header | value |
|---|---|
| `X-Canarito-Server` | `server_id` |
| `X-Canarito-Timestamp` | epoch seconds, must be within 60 s of the relay's clock |
| `X-Canarito-Signature` | lowercase hex of `HMAC-SHA256(server_key, timestamp + "\n" + raw_body)` |

Body:

```json
{
  "handles": ["<handle>", "<handle>"],
  "alert": {"id": "ntfy-event-id", "receptor": "sebastian", "lang": "es",
            "title": "Alerta de sismo", "body": "Sismo M5.4 cerca de tu zona. Protégete ahora.",
            "sent_at": 1791650000},
  "critical": false
}
```

Up to 100 handles and 32 KB of body. The server sends at most 15 handles per request, so an older relay with a 4 KB limit still works. Answer `200` when the request was valid, even when some
phones failed:

```json
{"results": [{"status": "sent"}, {"status": "gone"}, {"status": "failed", "reason": "apns_503"}]}
```

One result per handle, same order. `gone` means APNs said the token is dead (410 or
`BadDeviceToken`): the server removes that device and tells the admin. `failed` is retried by the
server for as long as the alert is under 3 minutes old. A handle that was sealed for another
`server_id` gets `{"status": "rejected"}` and nothing is sent to it.

Rate limit: 30 requests per minute per `server_id`, then `429 rate_limited` with `Retry-After`.

## 6. Failures are loud

- Server cannot reach the relay, the relay answers 5xx, or every handle `failed`: the receptor's
  health says `relay` is down and the admin gets a notice on the admin link (`high`). The same
  alert still goes to ntfy. When a push works again the admin gets a "relay ok" notice.
- Relay answers `401 bad_signature` or `bad_timestamp`: same notice, with the code. A wrong clock
  on the host is a real cause.
- `gone` devices: one admin notice per device, and the device is removed.
- App: when a push cannot be registered (no APNs token, `/v1/handles` fails, `/v1/pair` fails) the
  app shows it on screen. It never says "protected" without a registered handle.

## 7. Why the relay needs no database

- The relay has one master secret, the field `master` (random, 64 hex chars) of the same Secrets
  Manager JSON that holds the APNs key (`p8`, `keyId`, `teamId`, `topic`). `topic` is the bundle id.
- `server_key = HMAC-SHA256(master, server_id)`. The relay recomputes it on every push, so it
  stores no server.
- `handle = AES-256-GCM(key derived from master, {apns_token, server_id, environment})`. The relay
  opens it on every push, checks `server_id` equals the signing server, then sends. So it stores
  no pairing and no token.
- Rate limit is a counter in the Lambda's memory. A Lambda concurrency cap bounds the total.
  ponytail: per container, so the real ceiling is 30/min times the concurrency cap; a table
  would make it exact and is not worth the state.
- Alert text passes through and is never logged. Logs hold status codes and server ids only.

## 8. Errors

| status | `error` | when |
|---|---|---|
| 400 | `bad_request` | body is not the shape above |
| 401 | `bad_signature` | relay: signature or server id wrong |
| 401 | `bad_timestamp` | relay: clock more than 60 s off |
| 401 | `bad_key` | server: missing or unknown device key |
| 403 | `bad_secret` | server: pairing secret wrong, used or expired |
| 403 | `wrong_server` | relay: handle belongs to another server (`/v1/push` reports it per handle) |
| 404 | `not_found` | server: unknown path |
| 413 | `too_large` | body over the limit |
| 429 | `rate_limited` | relay: over 30/min for this server |
| 429 | `slow_down` | server: position more than once per 10 s, or test more than once per 10 min |
| 502 | `relay_failed` | server: the relay did not deliver the test push |
| 502 | `apns_unavailable` | relay: APNs unreachable or not configured |
