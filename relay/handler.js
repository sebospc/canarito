"use strict";
// Canarito push relay. Stateless: servers and pairings are proven by HMAC and AES-GCM keyed from
// one master secret, so nothing about a server, a phone or an alert is stored. docs/app-contract.md.
const crypto = require("node:crypto");
const apns = require("./apns");

const MAX_BODY_BYTES = 32 * 1024; // 100 handles of up to 1000 chars each, plus the alert
const MAX_HANDLES = 100;
const CLOCK_SKEW_S = 60;
const RATE_LIMIT_PER_MIN = 30;
const ALERT_TTL_S = 180;
const SECRET_CACHE_MS = 5 * 60 * 1000;
const HEX_TOKEN = /^[0-9a-fA-F]{64,200}$/;
const HEX_ID = /^[0-9a-f]{32}$/;

const reply = (statusCode, body, headers = {}) => ({
  statusCode,
  headers: { "content-type": "application/json", ...headers },
  body: JSON.stringify(body),
});
const fail = (statusCode, error, headers) => reply(statusCode, { error }, headers);

const hmac = (keyBytes, text) => crypto.createHmac("sha256", keyBytes).update(text).digest();

function serverKey(master, serverId) {
  return hmac(Buffer.from(master, "hex"), `server:${serverId}`).toString("hex");
}

function seal(master, plain) {
  const iv = crypto.randomBytes(12);
  const cipher = crypto.createCipheriv("aes-256-gcm", hmac(Buffer.from(master, "hex"), "handle"), iv);
  const body = Buffer.concat([cipher.update(JSON.stringify(plain)), cipher.final()]);
  return Buffer.concat([iv, cipher.getAuthTag(), body]).toString("base64url");
}

// null for anything that is not a handle this relay sealed.
function open(master, handle) {
  try {
    const raw = Buffer.from(handle, "base64url");
    const decipher = crypto.createDecipheriv("aes-256-gcm", hmac(Buffer.from(master, "hex"), "handle"), raw.subarray(0, 12));
    decipher.setAuthTag(raw.subarray(12, 28));
    const plain = JSON.parse(Buffer.concat([decipher.update(raw.subarray(28)), decipher.final()]).toString());
    return plain && plain.t && plain.s && plain.e ? plain : null;
  } catch {
    return null;
  }
}

function safeEqualHex(a, b) {
  const left = Buffer.from(String(a), "utf8");
  const right = Buffer.from(String(b), "utf8");
  return left.length === right.length && crypto.timingSafeEqual(left, right);
}

function validAlert(alert) {
  return alert && typeof alert === "object"
    && ["id", "receptor", "lang", "title", "body"].every((key) => typeof alert[key] === "string" && alert[key])
    && Number.isFinite(alert.sent_at);
}

// Fixed window per server id, in this container's memory. Concurrency cap bounds the total.
function rateLimiter(now) {
  const windows = new Map();
  return (serverId) => {
    const nowMs = now();
    for (const [id, window] of windows) if (nowMs - window.start >= 60000) windows.delete(id);
    const window = windows.get(serverId) || { start: nowMs, count: 0 };
    window.count += 1;
    windows.set(serverId, window);
    return window.count > RATE_LIMIT_PER_MIN ? Math.ceil((60000 - (nowMs - window.start)) / 1000) : 0;
  };
}

function createRelay({ readSecret, origins = apns.ORIGINS, now = Date.now }) {
  const jwt = apns.jwtCache();
  const overLimit = rateLimiter(now);
  let secret = null;
  let secretAt = 0;

  async function config() {
    if (!secret || now() - secretAt > SECRET_CACHE_MS) {
      secret = await readSecret();
      secretAt = now();
    }
    return secret;
  }

  function registerServer(master) {
    const serverId = crypto.randomBytes(16).toString("hex");
    return reply(200, { server_id: serverId, server_key: serverKey(master, serverId) });
  }

  function makeHandle(master, body) {
    if (!body || !HEX_ID.test(body.server_id || "") || !HEX_TOKEN.test(body.apns_token || "")
        || !["production", "sandbox"].includes(body.environment)) return fail(400, "bad_request");
    return reply(200, { handle: seal(master, { t: body.apns_token, s: body.server_id, e: body.environment }) });
  }

  async function push(secrets, event, rawBody) {
    const serverId = event.headers["x-canarito-server"] || "";
    const timestamp = event.headers["x-canarito-timestamp"] || "";
    if (!HEX_ID.test(serverId)) return fail(401, "bad_signature");
    const expected = hmac(Buffer.from(serverKey(secrets.master, serverId), "hex"), `${timestamp}\n${rawBody}`).toString("hex");
    if (!safeEqualHex(expected, event.headers["x-canarito-signature"] || "")) return fail(401, "bad_signature");
    if (!/^\d+$/.test(timestamp) || Math.abs(now() / 1000 - Number(timestamp)) > CLOCK_SKEW_S) return fail(401, "bad_timestamp");
    const wait = overLimit(serverId);
    if (wait) return fail(429, "rate_limited", { "retry-after": String(wait) });

    let body;
    try { body = JSON.parse(rawBody); } catch { return fail(400, "bad_request"); }
    // Before the shape check, so a signed push with no phones doubles as a health check:
    // 400 means up and configured, 502 means the APNs settings are missing.
    if (!secrets.p8 || !secrets.keyId || !secrets.teamId || !secrets.topic) return fail(502, "apns_unavailable");
    const { handles, alert, critical = false } = body || {};
    if (!Array.isArray(handles) || handles.length < 1 || handles.length > MAX_HANDLES
        || !handles.every((handle) => typeof handle === "string") || !validAlert(alert) || typeof critical !== "boolean") {
      return fail(400, "bad_request");
    }

    const payload = apns.alertPayload(alert, critical);
    const expiration = Math.floor(alert.sent_at) + ALERT_TTL_S;
    const opened = handles.map((handle) => open(secrets.master, handle));
    const sessions = {};
    const token = jwt(secrets, Math.floor(now() / 1000));
    try {
      const results = await Promise.all(opened.map(async (device) => {
        if (!device || device.s !== serverId) return { status: "rejected" };
        if (expiration * 1000 < now()) return { status: "failed", reason: "expired" };
        sessions[device.e] = sessions[device.e] || apns.openApns(origins[device.e], secrets.topic);
        return apns.outcome(await sessions[device.e].send({ token: device.t, jwt: token, payload, expiration }));
      }));
      return reply(200, { results });
    } finally {
      Object.values(sessions).forEach((session) => session.close());
    }
  }

  return async function handler(event) {
    try {
      const method = event.requestContext.http.method;
      const path = event.rawPath;
      const headers = Object.fromEntries(Object.entries(event.headers || {}).map(([key, value]) => [key.toLowerCase(), value]));
      const rawBody = event.isBase64Encoded ? Buffer.from(event.body || "", "base64").toString() : event.body || "";
      if (Buffer.byteLength(rawBody) > MAX_BODY_BYTES) return fail(413, "too_large");
      if (method !== "POST") return fail(400, "bad_request");

      let secrets;
      try {
        secrets = await config();
        if (!secrets || !/^[0-9a-f]{64}$/.test(secrets.master || "")) throw new Error("no master");
      } catch (error) {
        console.error("secret not usable:", error.message);
        return fail(502, "apns_unavailable");
      }
      const request = { headers, requestContext: event.requestContext };
      if (path === "/v1/servers") return registerServer(secrets.master);
      if (path === "/v1/handles") {
        let body;
        try { body = JSON.parse(rawBody); } catch { return fail(400, "bad_request"); }
        return makeHandle(secrets.master, body);
      }
      if (path === "/v1/push") return await push(secrets, request, rawBody);
      return fail(400, "bad_request");
    } catch (error) {
      // Log the class only: an error message could carry a token or alert text.
      console.error("relay error:", error.name);
      return fail(502, "apns_unavailable");
    }
  };
}

let handler = null;
exports.handler = async (event) => {
  if (!handler) {
    // The AWS SDK v3 ships inside the nodejs22.x runtime.
    const { SecretsManagerClient, GetSecretValueCommand } = require("@aws-sdk/client-secrets-manager");
    const client = new SecretsManagerClient({});
    handler = createRelay({
      readSecret: async () => JSON.parse((await client.send(new GetSecretValueCommand({ SecretId: process.env.SECRET_ID }))).SecretString),
    });
  }
  return handler(event);
};
exports.createRelay = createRelay;
exports.serverKey = serverKey;
