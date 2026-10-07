package app.canarito.receptor;

import android.content.Context;
import android.os.SystemClock;
import android.util.Log;

import org.json.JSONObject;

import java.io.File;
import java.io.FileInputStream;
import java.io.OutputStream;
import java.net.HttpURLConnection;
import java.net.URL;
import java.nio.charset.StandardCharsets;
import java.util.Collections;
import java.util.LinkedHashMap;
import java.util.Map;
import java.util.Set;
import java.util.concurrent.ExecutorService;
import java.util.concurrent.Executors;
import java.util.concurrent.ScheduledExecutorService;
import java.util.concurrent.ScheduledFuture;
import java.util.concurrent.TimeUnit;

/**
 * Sends an early warning to an ntfy topic the moment it is posted. Every phone subscribed to
 * that topic in the ntfy app gets it. No server of ours in between.
 *
 * Config lives in files/relay.json, written by canarito.py with adb:
 * {"notify_url": "https://ntfy.sh/<topic>", "name": "home",
 *  "notify_token": "<optional>", "heartbeat_url": "<optional>", "language": "es|en"}.
 * No config means capture only: the evidence file fills, nothing is sent.
 */
final class Forwarder {
    static final String CONFIG_FILE = "relay.json";
    private static final long[] RETRY_BACKOFF_MS = {0, 500, 1000, 2000, 4000};
    // ponytail: one sender thread. With ntfy down an alert holds it up to ~47 s and the
    // next one waits; a pool per alert if two alerts within a minute ever matter.
    private static final ExecutorService SENDER = Executors.newSingleThreadExecutor();
    // Own thread: an alert must never wait behind a heartbeat stuck on its timeouts.
    private static final ScheduledExecutorService MONITOR = Executors.newSingleThreadScheduledExecutor();
    /**
     * Alerts already sent by this process. A warning still on screen is sent again at every
     * listener reconnect; this keeps it to one. A process restart forgets it, and the phone
     * may then get the same alert twice: better twice than never.
     */
    private static final Set<String> SENT = Collections.synchronizedSet(Collections.newSetFromMap(
            new LinkedHashMap<String, Boolean>() {
                @Override
                protected boolean removeEldestEntry(Map.Entry<String, Boolean> eldest) {
                    return size() > 100;
                }
            }));
    private static ScheduledFuture<?> heartbeatTask;
    private static volatile boolean invalidConfigReported;
    // New per listener connection, like invalidConfigReported: a reconnect logs the first failure again.
    private static volatile RelayPolicy.HeartbeatFailureLog heartbeatFailures = new RelayPolicy.HeartbeatFailureLog();

    private Forwarder() {}

    static void relay(Context context, Float magnitude, Double distanceKm,
                      Long timeOccurredS, long postTimeMs) {
        JSONObject config = readConfig(context);
        if (config == null) return;
        String eventId = RelayPolicy.eventId(config.optString("name"), timeOccurredS, postTimeMs);
        if (!SENT.add(eventId)) return;
        String language = config.optString("language");
        // NaN would make String.format print "MNaN"; better the text without a number.
        Float finiteMagnitude = RelayPolicy.finiteOrNull(magnitude);
        byte[] body = RelayPolicy.bodyFor(finiteMagnitude, language).getBytes(StandardCharsets.UTF_8);
        String title = RelayPolicy.titleFor(language);
        String url = config.optString("notify_url");
        String token = config.optString("notify_token");
        long deadline = System.currentTimeMillis() + RelayPolicy.ALERT_TTL_MS;

        SENDER.execute(() -> {
            // A retry after a lost answer can deliver twice. Twice is fine, never is not.
            for (long backoff : RETRY_BACKOFF_MS) {
                if (System.currentTimeMillis() + backoff > deadline) break;
                sleep(backoff);
                PostResult result = post(url, token, title, body);
                JSONObject attempt = CaptureService.baseEvent(context, "RELAY_ATTEMPT");
                CaptureService.put(attempt, "event_id", eventId);
                CaptureService.put(attempt, "magnitude", finiteMagnitude);
                CaptureService.put(attempt, "distance_km", RelayPolicy.finiteOrNull(distanceKm));
                CaptureService.put(attempt, "http_status", result.status());
                CaptureService.put(attempt, "request_written_at_ms", result.writtenAtMs());
                CaptureService.put(attempt, "error", result.error());
                EvidenceStore.append(context, attempt);
                if (result.isSuccess()) return;
                // Wrong token or a topic that is not ours: retrying cannot fix it.
                if (result.status() == 401 || result.status() == 403) return;
            }
            // Out of retries: let a reconnect replay try again while the warning is still on screen.
            SENT.remove(eventId);
        });
    }

    static synchronized void startMonitoring(Context context) {
        stopMonitoring();
        invalidConfigReported = false;
        heartbeatFailures = new RelayPolicy.HeartbeatFailureLog();
        Context appContext = context.getApplicationContext();
        heartbeatTask = MONITOR.scheduleAtFixedRate(() -> {
            // An exception escaping here would silently cancel every later run.
            try {
                sendHeartbeat(appContext);
            } catch (Exception error) {
                Log.e("Forwarder", "heartbeat failed", error);
            }
        }, 0, RelayPolicy.HEARTBEAT_INTERVAL_MS, TimeUnit.MILLISECONDS);
    }

    static synchronized void stopMonitoring() {
        if (heartbeatTask != null) heartbeatTask.cancel(false);
        heartbeatTask = null;
    }

    /** A device with a valid relay.json relays; without one it only captures. */
    static boolean isRelaySensor(Context context) {
        return readConfig(context) != null;
    }

    /**
     * Pings heartbeat_url (healthchecks.io, Uptime Kuma push, or your own) so a dead
     * receptor shows up as silence somewhere you look. Without one, nobody notices.
     */
    private static void sendHeartbeat(Context context) {
        // Read on every beat: relay.json is pushed after install, while the listener is already up.
        JSONObject config = readConfig(context);
        // Also the one place the GPS keeper follows relay.json, on connect and every 5 min.
        GpsKeeperService.sync(context, config != null);
        if (config == null || config.optString("heartbeat_url").isEmpty()) return;
        PostResult result = ping(config.optString("heartbeat_url"));
        // Only failures are logged: a success every 5 min would bury the captures.
        if (result.isSuccess()) {
            final Integer failed = heartbeatFailures.onSuccess();
            if (failed == null) return;
            final JSONObject record = CaptureService.baseEvent(context, "HEARTBEAT_RECOVERED");
            CaptureService.put(record, "failed", failed);
            EvidenceStore.append(context, record);
            return;
        }
        // Monotonic: a wall clock stepped back would hold every later line out of the file.
        final Integer repeated = heartbeatFailures.onFailure(result.status(), result.error(),
                SystemClock.elapsedRealtime());
        if (repeated == null) return;
        final JSONObject record = CaptureService.baseEvent(context, "HEARTBEAT_FAILED");
        CaptureService.put(record, "http_status", result.status());
        CaptureService.put(record, "error", result.error());
        CaptureService.put(record, "repeated", repeated);
        EvidenceStore.append(context, record);
    }

    /**
     * status -1 means the request never got an HTTP answer; `error` then says why. A bare -1
     * once hid a cleartext block for hours. writtenAtMs is when the whole body was on the
     * socket, null if it never got there.
     */
    record PostResult(int status, String error, Long writtenAtMs) {
        static PostResult failed(Exception error, Long writtenAtMs) {
            return new PostResult(-1, error.getClass().getName() + ": " + error.getMessage(), writtenAtMs);
        }

        boolean isSuccess() {
            return status >= 200 && status < 300;
        }
    }

    /** ntfy's publish call: the body is the message, headers carry title and priority. */
    static PostResult post(String url, String token, String title, byte[] body) {
        HttpURLConnection connection = null;
        Long writtenAtMs = null;
        try {
            connection = (HttpURLConnection) new URL(url).openConnection();
            connection.setRequestMethod("POST");
            connection.setConnectTimeout(3000);
            connection.setReadTimeout(5000);
            connection.setDoOutput(true);
            connection.setRequestProperty("content-type", "text/plain; charset=utf-8");
            // Headers are ISO-8859-1 on the wire: titles stay ASCII, accents go in the body.
            connection.setRequestProperty("Title", title);
            // "urgent" is ntfy's top priority: long vibration and a pop-up on Android.
            connection.setRequestProperty("Priority", "urgent");
            connection.setRequestProperty("Tags", "rotating_light");
            if (token != null && !token.isEmpty()) {
                connection.setRequestProperty("Authorization", "Bearer " + token);
            }
            // Streamed, not buffered: otherwise the body only leaves in getResponseCode and
            // writtenAtMs would stamp a request still sitting in memory.
            connection.setFixedLengthStreamingMode(body.length);
            try (OutputStream output = connection.getOutputStream()) {
                output.write(body);
            }
            writtenAtMs = System.currentTimeMillis();
            return new PostResult(connection.getResponseCode(), null, writtenAtMs);
        } catch (Exception error) {
            return PostResult.failed(error, writtenAtMs);
        } finally {
            if (connection != null) connection.disconnect();
        }
    }

    static PostResult ping(String url) {
        HttpURLConnection connection = null;
        try {
            connection = (HttpURLConnection) new URL(url).openConnection();
            connection.setConnectTimeout(3000);
            connection.setReadTimeout(5000);
            return new PostResult(connection.getResponseCode(), null, null);
        } catch (Exception error) {
            return PostResult.failed(error, null);
        } finally {
            if (connection != null) connection.disconnect();
        }
    }

    /** Missing file = capture only, silent. A file that is there but broken is a receptor gone quiet. */
    private static JSONObject readConfig(Context context) {
        File file = new File(context.getFilesDir(), CONFIG_FILE);
        if (!file.exists()) return null;
        try (FileInputStream input = new FileInputStream(file)) {
            byte[] raw = new byte[(int) file.length()];
            int read = input.read(raw);
            JSONObject config = new JSONObject(new String(raw, 0, Math.max(read, 0), StandardCharsets.UTF_8));
            boolean complete = !config.optString("notify_url").isEmpty()
                    && !config.optString("name").isEmpty();
            if (complete) return config;
            reportInvalidConfig(context, "missing field");
        } catch (Exception error) {
            reportInvalidConfig(context, error.getClass().getSimpleName());
        }
        return null;
    }

    // Once per listener connection: the heartbeat re-reads the config every 5 min.
    private static void reportInvalidConfig(Context context, String reason) {
        if (invalidConfigReported) return;
        invalidConfigReported = true;
        Log.e("Forwarder", "relay.json invalid: " + reason);
        JSONObject record = CaptureService.baseEvent(context, "RELAY_CONFIG_INVALID");
        CaptureService.put(record, "reason", reason);
        EvidenceStore.append(context, record);
    }

    private static void sleep(long millis) {
        if (millis <= 0) return;
        try {
            Thread.sleep(millis);
        } catch (InterruptedException interrupted) {
            Thread.currentThread().interrupt();
        }
    }
}
