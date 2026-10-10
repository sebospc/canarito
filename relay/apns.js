"use strict";
// APNs over HTTP/2 with a token (ES256) JWT. Only node:http2 and node:crypto.
const http2 = require("node:http2");
const crypto = require("node:crypto");

const ORIGINS = {
  production: "https://api.push.apple.com",
  sandbox: "https://api.sandbox.push.apple.com",
};
// Apple wants a token refreshed no sooner than 20 min and no later than 60.
const JWT_MAX_AGE_S = 40 * 60;
const REQUEST_TIMEOUT_MS = 8000;
// Reasons that mean the token itself is dead, not that APNs is having a bad day.
const DEAD_TOKEN_REASONS = new Set(["BadDeviceToken", "Unregistered", "DeviceTokenNotForTopic"]);

const b64url = (buffer) => Buffer.from(buffer).toString("base64url");

function makeJwt({ p8, keyId, teamId }, nowS) {
  const header = b64url(JSON.stringify({ alg: "ES256", kid: keyId }));
  const claims = b64url(JSON.stringify({ iss: teamId, iat: nowS }));
  const signature = crypto.sign("sha256", Buffer.from(`${header}.${claims}`), {
    key: p8,
    dsaEncoding: "ieee-p1363",
  });
  return `${header}.${claims}.${b64url(signature)}`;
}

function jwtCache() {
  let cached = null;
  return (credentials, nowS) => {
    if (!cached || nowS - cached.at > JWT_MAX_AGE_S || cached.keyId !== credentials.keyId) {
      cached = { at: nowS, keyId: credentials.keyId, jwt: makeJwt(credentials, nowS) };
    }
    return cached.jwt;
  };
}

function alertPayload(alert, critical) {
  const aps = { alert: { title: alert.title, body: alert.body }, sound: "default", "interruption-level": "time-sensitive" };
  if (critical) {
    aps.sound = { critical: 1, name: "default", volume: 1.0 };
    aps["interruption-level"] = "critical";
  }
  const canarito = { v: 1, id: alert.id, receptor: alert.receptor, lang: alert.lang, sent_at: alert.sent_at };
  // Optional facts the app shows next to the text; passed on only when the server knew them.
  for (const key of ["magnitude", "occurred_at"]) if (Number.isFinite(alert[key])) canarito[key] = alert[key];
  for (const key of ["late", "test"]) if (alert[key] === true) canarito[key] = true;
  return { aps, canarito };
}

// One HTTP/2 connection for all the handles of one push request.
function openApns(origin, topic) {
  const session = http2.connect(origin);
  let sessionError = null;
  session.on("error", (error) => { sessionError = error; });

  function send({ token, jwt, payload, expiration }) {
    return new Promise((resolve) => {
      if (sessionError) return resolve({ status: 0, reason: "unreachable" });
      const request = session.request({
        ":method": "POST",
        ":path": `/3/device/${token}`,
        authorization: `bearer ${jwt}`,
        "apns-topic": topic,
        "apns-push-type": "alert",
        "apns-priority": "10",
        "apns-expiration": String(expiration),
      });
      const chunks = [];
      let status = 0;
      request.setTimeout(REQUEST_TIMEOUT_MS, () => request.close(http2.constants.NGHTTP2_CANCEL));
      request.on("response", (headers) => { status = headers[":status"]; });
      request.on("data", (chunk) => chunks.push(chunk));
      request.on("error", () => resolve({ status: 0, reason: "unreachable" }));
      request.on("close", () => {
        let reason = "";
        try { reason = JSON.parse(Buffer.concat(chunks).toString() || "{}").reason || ""; } catch { /* body is optional */ }
        resolve({ status, reason: status ? reason : "unreachable" });
      });
      request.end(JSON.stringify(payload));
    });
  }
  return { send, close: () => session.close() };
}

// "sent", "gone" or "failed" plus a reason a human can read in the admin notice.
function outcome({ status, reason }) {
  if (status === 200) return { status: "sent" };
  if (status === 410 || DEAD_TOKEN_REASONS.has(reason)) return { status: "gone" };
  return { status: "failed", reason: status ? `apns_${status}${reason ? `_${reason}` : ""}` : "apns_unreachable" };
}

module.exports = { ORIGINS, jwtCache, alertPayload, openApns, outcome, makeJwt };
