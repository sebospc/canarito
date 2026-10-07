package app.canarito.receptor;

import android.app.Notification;
import android.content.ComponentName;
import android.content.Context;
import android.content.pm.PackageInfo;
import android.content.pm.PackageManager;
import android.os.Build;
import android.os.Bundle;
import android.os.SystemClock;
import android.provider.Settings;
import android.service.notification.NotificationListenerService;
import android.service.notification.StatusBarNotification;

import org.json.JSONArray;
import org.json.JSONObject;

import java.security.MessageDigest;
import java.util.ArrayList;
import java.util.Arrays;
import java.util.Collections;
import java.util.List;

public final class CaptureService extends NotificationListenerService {
    /** Play Services ships the alert's real numbers in these, not in the text. */
    private static final List<String> EARTHQUAKE_EXTRAS = Arrays.asList(
            "MAGNITUDE_EXTRA", "DISTANCE_EXTRA", "TIME_OCCURRED_EXTRA");

    @Override
    public void onListenerConnected() {
        super.onListenerConnected();
        EvidenceStore.append(this, baseEvent(this, "LISTENER_CONNECTED"));
        Forwarder.startMonitoring(this);
        replayMissedWarnings();
    }

    @Override
    public void onListenerDisconnected() {
        Forwarder.stopMonitoring();
        EvidenceStore.append(this, baseEvent(this, "LISTENER_DISCONNECTED"));
        requestRebind(new ComponentName(this, CaptureService.class));
        super.onListenerDisconnected();
    }

    /**
     * A warning posted while the listener was unbound (boot, rebind, app update) never
     * reaches onNotificationPosted. It is still on screen, so pick it up now; the forwarder
     * skips any this process already sent.
     */
    private void replayMissedWarnings() {
        StatusBarNotification[] active = getActiveNotifications();
        if (active == null) return;
        long now = System.currentTimeMillis();
        for (StatusBarNotification sbn : active) {
            boolean relayable = RelayPolicy.isRelayable(sbn.getPackageName(),
                    signerSha256(sbn.getPackageName()), sbn.getNotification().getChannelId());
            if (relayable && RelayPolicy.isReplayable(sbn.getPostTime(), now)) {
                onNotificationPosted(sbn);
            }
        }
    }

    @Override
    public void onNotificationPosted(StatusBarNotification sbn) {
        if (!EventClassifier.shouldCapture(sbn.getPackageName())) return;

        Notification notification = sbn.getNotification();
        String signer = signerSha256(sbn.getPackageName());
        // Relay first: every millisecond here is a millisecond less of warning.
        if (RelayPolicy.isRelayable(sbn.getPackageName(), signer, notification.getChannelId())) {
            Bundle extras = notification.extras != null ? notification.extras : Bundle.EMPTY;
            Forwarder.relay(this,
                    extras.get("MAGNITUDE_EXTRA") instanceof Float magnitude ? magnitude : null,
                    extras.get("DISTANCE_EXTRA") instanceof Double distance ? distance : null,
                    extras.get("TIME_OCCURRED_EXTRA") instanceof Long occurred ? occurred : null,
                    sbn.getPostTime());
        }
        JSONObject event = baseEvent(this, "NOTIFICATION_POSTED");
        put(event, "source_label", EventClassifier.sourceFor(sbn.getPackageName()));
        put(event, "package_name", sbn.getPackageName());
        put(event, "package_signer_sha256", signer);
        put(event, "uid", sbn.getUid());
        put(event, "notification_key", sbn.getKey());
        put(event, "notification_id", sbn.getId());
        put(event, "tag", sbn.getTag());
        put(event, "post_time_ms", sbn.getPostTime());
        put(event, "channel_id", notification.getChannelId());
        put(event, "category", notification.category);
        put(event, "priority", notification.priority);
        put(event, "flags", notification.flags);
        put(event, "when_ms", notification.when);
        put(event, "has_content_intent", notification.contentIntent != null);
        put(event, "has_full_screen_intent", notification.fullScreenIntent != null);
        if (notification.fullScreenIntent != null) {
            put(event, "full_screen_creator", notification.fullScreenIntent.getCreatorPackage());
        }
        addExtras(event, notification.extras);
        EvidenceStore.append(this, event);
    }

    @Override
    public void onNotificationRemoved(StatusBarNotification sbn) {
        if (!EventClassifier.shouldCapture(sbn.getPackageName())) return;
        JSONObject event = baseEvent(this, "NOTIFICATION_REMOVED");
        put(event, "source_label", EventClassifier.sourceFor(sbn.getPackageName()));
        put(event, "package_name", sbn.getPackageName());
        put(event, "notification_key", sbn.getKey());
        EvidenceStore.append(this, event);
    }

    static JSONObject baseEvent(Context context, String type) {
        JSONObject event = new JSONObject();
        put(event, "schema_version", 1);
        put(event, "event_type", type);
        put(event, "captured_at_ms", System.currentTimeMillis());
        put(event, "elapsed_realtime_ms", SystemClock.elapsedRealtime());
        put(event, "boot_count", Settings.Global.getInt(
                context.getContentResolver(), Settings.Global.BOOT_COUNT, -1));
        put(event, "build_fingerprint", Build.FINGERPRINT);
        return event;
    }

    private void addExtras(JSONObject event, Bundle extras) {
        JSONObject values = new JSONObject();
        JSONArray types = new JSONArray();
        if (extras != null) {
            List<String> keys = new ArrayList<>(extras.keySet());
            Collections.sort(keys);
            for (String key : keys) {
                Object value = extras.get(key);
                JSONObject typed = new JSONObject();
                put(typed, "key", key);
                put(typed, "type", value == null ? "null" : value.getClass().getName());
                types.put(typed);
                if (Notification.EXTRA_TITLE.equals(key)
                        || Notification.EXTRA_TEXT.equals(key)
                        || Notification.EXTRA_BIG_TEXT.equals(key)
                        || Notification.EXTRA_SUB_TEXT.equals(key)
                        || EARTHQUAKE_EXTRAS.contains(key)) {
                    put(values, key, truncate(value));
                }
            }
        }
        put(event, "selected_extras", values);
        put(event, "extra_types", types);
    }

    private String signerSha256(String packageName) {
        try {
            PackageInfo info = getPackageManager().getPackageInfo(
                    packageName, PackageManager.GET_SIGNING_CERTIFICATES);
            byte[] certificate = info.signingInfo.getApkContentsSigners()[0].toByteArray();
            byte[] digest = MessageDigest.getInstance("SHA-256").digest(certificate);
            StringBuilder hex = new StringBuilder();
            for (byte value : digest) hex.append(String.format("%02x", value));
            return hex.toString();
        } catch (Exception error) {
            return "UNAVAILABLE:" + error.getClass().getSimpleName();
        }
    }

    private static String truncate(Object value) {
        if (value == null) return null;
        String text = String.valueOf(value);
        return text.length() <= 1000 ? text : text.substring(0, 1000);
    }

    static void put(JSONObject object, String key, Object value) {
        try {
            object.put(key, value == null ? JSONObject.NULL : value);
        } catch (Exception error) {
            throw new IllegalStateException(error);
        }
    }
}
