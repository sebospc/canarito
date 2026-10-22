"use strict";
// node --test relay/   (Node 22, no dependencies). The fake APNs is a local HTTP/2 server.
const test = require("node:test");
const assert = require("node:assert");
const crypto = require("node:crypto");
const http2 = require("node:http2");
const { createRelay } = require("./handler");

const MASTER = "ab".repeat(32);
const { privateKey } = crypto.generateKeyPairSync("ec", { namedCurve: "P-256" });
const SECRETS = {
  master: MASTER, keyId: "KEY1234567", teamId: "TEAM123456", topic: "app.example.canarito",
  p8: privateKey.export({ type: "pkcs8", format: "pem" }),
};
const NOW = 1_791_650_000_000;
const TOKEN = "cd".repeat(32);

async function setup(apnsAnswer = () => ({ status: 200 })) {
  const received = [];
  const server = http2.createServer();
  server.on("stream", (stream, headers) => {
    const chunks = [];
    stream.on("data", (chunk) => chunks.push(chunk));
    stream.on("end", () => {
      received.push({ headers, body: JSON.parse(Buffer.concat(chunks).toString()) });
      const answer = apnsAnswer(headers[":path"]);
      stream.respond({ ":status": answer.status });
      stream.end(answer.reason ? JSON.stringify({ reason: answer.reason }) : "");
    });
  });
  await new Promise((resolve) => server.listen(0, "127.0.0.1", resolve));
  const origin = `http://127.0.0.1:${server.address().port}`;
  let clock = NOW;
  const relay = createRelay({
    readSecret: async () => SECRETS, origins: { production: origin, sandbox: origin }, now: () => clock,
  });
  const call = (path, body, headers = {}) => relay({
    rawPath: path, requestContext: { http: { method: "POST" } }, headers,
    body: typeof body === "string" ? body : JSON.stringify(body),
  }).then((res) => ({ ...res, json: JSON.parse(res.body) }));
  const register = async () => (await call("/v1/servers", {})).json;
  const handleFor = async (serverId, token = TOKEN) =>
    (await call("/v1/handles", { server_id: serverId, apns_token: token, environment: "production" })).json.handle;
  const signedPush = (server, body, { timestamp = String(NOW / 1000), tamper = false } = {}) => {
    const raw = JSON.stringify(body);
    const signature = crypto.createHmac("sha256", Buffer.from(server.server_key, "hex")).update(`${timestamp}\n${raw}`).digest("hex");
    return call("/v1/push", raw, {
      "X-Canarito-Server": server.server_id, "X-Canarito-Timestamp": timestamp,
      "X-Canarito-Signature": tamper ? "0".repeat(64) : signature,
    });
  };
  return { call, register, handleFor, signedPush, received, setClock: (ms) => { clock = ms; }, close: () => server.close() };
}

const ALERT = { id: "evt1", receptor: "sebastian", lang: "es", title: "Alerta de sismo",
  body: "Sismo M5.4 cerca de tu zona. Protégete ahora.", sent_at: NOW / 1000 };

test("a paired phone gets the alert with the contract payload and a signed JWT", async () => {
  const world = await setup();
  const server = await world.register();
  const handle = await world.handleFor(server.server_id);
  const res = await world.signedPush(server, { handles: [handle], alert: ALERT });
  assert.strictEqual(res.statusCode, 200);
  assert.deepStrictEqual(res.json.results, [{ status: "sent" }]);
  const [sent] = world.received;
  assert.strictEqual(sent.headers[":path"], `/3/device/${TOKEN}`);
  assert.strictEqual(sent.headers["apns-topic"], SECRETS.topic);
  assert.strictEqual(sent.headers["apns-expiration"], String(NOW / 1000 + 180));
  assert.strictEqual(sent.body.aps.alert.title, "Alerta de sismo");
  assert.strictEqual(sent.body.aps["interruption-level"], "time-sensitive");
  assert.strictEqual(sent.body.aps["content-available"], 1, "the open app must get the alert with notifications off");
  assert.strictEqual(sent.body.canarito.id, "evt1");
  const [head, claims, signature] = sent.headers.authorization.replace("bearer ", "").split(".");
  assert.deepStrictEqual(JSON.parse(Buffer.from(head, "base64url")), { alg: "ES256", kid: "KEY1234567" });
  assert.strictEqual(JSON.parse(Buffer.from(claims, "base64url")).iss, "TEAM123456");
  const ok = crypto.verify("sha256", Buffer.from(`${head}.${claims}`), { key: privateKey, dsaEncoding: "ieee-p1363" }, Buffer.from(signature, "base64url"));
  assert.ok(ok);
  world.close();
});

test("optional alert facts reach the app, junk does not", async () => {
  const world = await setup();
  const server = await world.register();
  const handle = await world.handleFor(server.server_id);
  await world.signedPush(server, { handles: [handle], alert: { ...ALERT, magnitude: 5.4, late: true, test: true, occurred_at: "x", evil: 1 } });
  assert.deepStrictEqual(world.received[0].body.canarito, { v: 1, id: "evt1", receptor: "sebastian", lang: "es",
    sent_at: NOW / 1000, magnitude: 5.4, late: true, test: true });
  world.close();
});

test("critical alerts only when the server asks", async () => {
  const world = await setup();
  const server = await world.register();
  const handle = await world.handleFor(server.server_id);
  await world.signedPush(server, { handles: [handle], alert: ALERT, critical: true });
  assert.strictEqual(world.received[0].body.aps["interruption-level"], "critical");
  world.close();
});

test("real alerts and drills use the Canarito sound, tests keep the default one, the payload says which", async () => {
  const world = await setup();
  const server = await world.register();
  const handle = await world.handleFor(server.server_id);
  for (const [extra, critical] of [[{}, false], [{ drill: true }, false], [{ test: true }, false], [{}, true], [{ test: true }, true]]) {
    await world.signedPush(server, { handles: [handle], alert: { ...ALERT, ...extra }, critical });
  }
  const sounds = world.received.map(({ body }) => body.aps.sound);
  assert.deepStrictEqual(sounds, ["canarito-alert.caf", "canarito-alert.caf", "default",
    { critical: 1, name: "canarito-alert.caf", volume: 1.0 }, { critical: 1, name: "default", volume: 1.0 }]);
  const flags = world.received.map(({ body }) => [body.canarito.test, body.canarito.drill]);
  assert.deepStrictEqual(flags, [[undefined, undefined], [undefined, true], [true, undefined], [undefined, undefined], [true, undefined]]);
  world.close();
});

test("a handle paired to another server is rejected and nothing reaches APNs", async () => {
  const world = await setup();
  const mine = await world.register();
  const other = await world.register();
  const theirHandle = await world.handleFor(other.server_id);
  const res = await world.signedPush(mine, { handles: [theirHandle, "garbage"], alert: ALERT });
  assert.deepStrictEqual(res.json.results, [{ status: "rejected" }, { status: "rejected" }]);
  assert.strictEqual(world.received.length, 0);
  world.close();
});

test("bad signature, stale clock and unknown server are refused", async () => {
  const world = await setup();
  const server = await world.register();
  const handle = await world.handleFor(server.server_id);
  const body = { handles: [handle], alert: ALERT };
  assert.strictEqual((await world.signedPush(server, body, { tamper: true })).json.error, "bad_signature");
  assert.strictEqual((await world.signedPush(server, body, { timestamp: String(NOW / 1000 - 120) })).json.error, "bad_timestamp");
  const forged = { server_id: "f".repeat(32), server_key: "0".repeat(64) };
  assert.strictEqual((await world.signedPush(forged, body)).statusCode, 401);
  assert.strictEqual(world.received.length, 0);
  world.close();
});

test("31st push in a minute gets 429, next minute works", async () => {
  const world = await setup();
  const server = await world.register();
  const handle = await world.handleFor(server.server_id);
  const body = { handles: [handle], alert: ALERT };
  for (let i = 0; i < 30; i++) assert.strictEqual((await world.signedPush(server, body)).statusCode, 200);
  const limited = await world.signedPush(server, body);
  assert.strictEqual(limited.statusCode, 429);
  assert.ok(Number(limited.headers["retry-after"]) > 0);
  world.setClock(NOW + 61_000);
  assert.strictEqual((await world.signedPush(server, body, { timestamp: String(NOW / 1000 + 61) })).statusCode, 200);
  world.close();
});

test("dead tokens are reported gone, other APNs errors failed", async () => {
  const world = await setup((path) => path.endsWith("11".repeat(32)) ? { status: 410, reason: "Unregistered" }
    : path.endsWith("22".repeat(32)) ? { status: 503 } : { status: 200 });
  const server = await world.register();
  const handles = [await world.handleFor(server.server_id, "11".repeat(32)),
    await world.handleFor(server.server_id, "22".repeat(32)), await world.handleFor(server.server_id)];
  const res = await world.signedPush(server, { handles, alert: ALERT });
  assert.deepStrictEqual(res.json.results, [{ status: "gone" }, { status: "failed", reason: "apns_503" }, { status: "sent" }]);
  world.close();
});

test("APNs unreachable is failed, not a silent 200 sent", async () => {
  const world = await setup();
  const server = await world.register();
  const handle = await world.handleFor(server.server_id);
  world.close();
  const res = await world.signedPush(server, { handles: [handle], alert: ALERT });
  assert.deepStrictEqual(res.json.results, [{ status: "failed", reason: "apns_unreachable" }]);
});

test("an alert older than 3 minutes is not sent late", async () => {
  const world = await setup();
  const server = await world.register();
  const handle = await world.handleFor(server.server_id);
  const res = await world.signedPush(server, { handles: [handle], alert: { ...ALERT, sent_at: NOW / 1000 - 200 } });
  assert.deepStrictEqual(res.json.results, [{ status: "failed", reason: "expired" }]);
  assert.strictEqual(world.received.length, 0);
  world.close();
});

test("bad shapes and big bodies", async () => {
  const world = await setup();
  const server = await world.register();
  assert.strictEqual((await world.call("/v1/handles", { server_id: server.server_id, apns_token: "xyz", environment: "production" })).json.error, "bad_request");
  assert.strictEqual((await world.signedPush(server, { handles: [], alert: ALERT })).json.error, "bad_request");
  assert.strictEqual((await world.call("/v1/push", "x".repeat(40000))).statusCode, 413);
  world.close();
});

test("100 handles in one push fit", async () => {
  const world = await setup();
  const server = await world.register();
  const handles = [];
  for (let i = 0; i < 100; i++) handles.push(await world.handleFor(server.server_id, i.toString(16).padStart(2, "0").repeat(32)));
  const res = await world.signedPush(server, { handles, alert: ALERT });
  assert.strictEqual(res.statusCode, 200);
  assert.strictEqual(res.json.results.length, 100);
  world.close();
});

test("a signed push with no phones is the health check: 400 when configured, 502 when not", async () => {
  const world = await setup();
  const server = await world.register();
  assert.strictEqual((await world.signedPush(server, { handles: [], alert: ALERT })).json.error, "bad_request");
  assert.strictEqual(world.received.length, 0);
  world.close();
  const relay = createRelay({ readSecret: async () => ({ master: MASTER }), now: () => NOW });
  const call = (path, body, headers) => relay({ rawPath: path, requestContext: { http: { method: "POST" } }, headers, body });
  const registered = JSON.parse((await call("/v1/servers", "{}", {})).body);
  const raw = JSON.stringify({ handles: [], alert: ALERT });
  const signature = crypto.createHmac("sha256", Buffer.from(registered.server_key, "hex")).update(`${NOW / 1000}\n${raw}`).digest("hex");
  const res = await call("/v1/push", raw, { "x-canarito-server": registered.server_id, "x-canarito-timestamp": String(NOW / 1000), "x-canarito-signature": signature });
  assert.strictEqual(res.statusCode, 502);
});

test("a secret without master fails loud with 502", async () => {
  const relay = createRelay({ readSecret: async () => ({ keyId: "x" }), now: () => NOW });
  const res = await relay({ rawPath: "/v1/servers", requestContext: { http: { method: "POST" } }, headers: {}, body: "" });
  assert.strictEqual(res.statusCode, 502);
});
