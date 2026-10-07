package app.canarito.receptor;

import java.util.Locale;

/** What gets relayed to the phone, and with which words. Pure so it can be tested off-device. */
final class RelayPolicy {
    static final String PLAY_SERVICES_SIGNER =
            "5f2391277b1dbd489000467e4c2fa6af802430080457dce2f618992e9dfb5402";
    /** A warning is only useful while the S wave is still travelling: ~86 s reach 300 km. */
    static final long ALERT_TTL_MS = 3 * 60_000;
    /** How often the receptor tells an uptime monitor it is alive, when one is configured. */
    static final long HEARTBEAT_INTERVAL_MS = 5 * 60_000;

    private RelayPolicy() {}

    /**
     * Only the early warning is relayed. A channel Google renames to some other eew_* is
     * NOT relayed on purpose: guessing it is a warning risks a false one. The evidence file
     * still records it, so a human can decide.
     * eew_update arrives minutes after the shaking
     * (5 min 21 s on 24-sep); sending it as "take cover" would be wrong advice.
     */
    static boolean isRelayable(String packageName, String signerSha256, String channelId) {
        return EventClassifier.GOOGLE_PLAY_SERVICES.equals(packageName)
                && PLAY_SERVICES_SIGNER.equals(signerSha256)
                && channelId != null
                && channelId.startsWith("eew_alert");
    }

    /**
     * Own wording, never Google's text or brand: facts only. No distance: the one AEA gives
     * is from this receptor to the quake, and a phone reading "a ~16 km" takes it as its own
     * (seen in the 24-sep Chaparral alert). "en" gives English, anything else Spanish.
     */
    static String titleFor(String language) {
        return "en".equals(language) ? "Earthquake alert" : "Alerta de sismo";
    }

    static String bodyFor(Float magnitude, String language) {
        boolean english = "en".equals(language);
        if (magnitude == null) {
            return english ? "Possible earthquake near you. Take cover now."
                    : "Posible sismo cerca de su zona. Protéjase ahora.";
        }
        return String.format(Locale.ROOT,
                english ? "Earthquake M%.1f near you. Take cover now." : "Sismo M%.1f cerca de su zona. Protéjase ahora.",
                magnitude);
    }

    /**
     * The same quake seen twice by one sensor must collapse, and two quakes must not.
     * The notification tag is reused across quakes (seen 23/24-sep), so it cannot be the key.
     */
    static String eventId(String sensorId, Long timeOccurredS, long postTimeMs) {
        String origin = timeOccurredS != null ? "t" + timeOccurredS : "p" + postTimeMs;
        return sensorId + ":" + origin + ":alert";
    }

    /** NTP stepping the clock back can put a fresh warning's post time slightly ahead of now. */
    static final long CLOCK_STEP_TOLERANCE_MS = 30_000;

    /**
     * A warning found on screen at reconnect is still worth sending while inside the TTL.
     * A post time further in the future than an NTP step means a clock jump, and nothing
     * about its age can be trusted.
     */
    static boolean isReplayable(long postTimeMs, long nowMs) {
        long ageMs = nowMs - postTimeMs;
        return ageMs >= -CLOCK_STEP_TOLERANCE_MS && ageMs < ALERT_TTL_MS;
    }

    static Float finiteOrNull(Float value) {
        return value != null && Float.isFinite(value) ? value : null;
    }

    static Double finiteOrNull(Double value) {
        return value != null && Double.isFinite(value) ? value : null;
    }

    /**
     * Which failed heartbeats reach the evidence file. A monitor that is down refuses every
     * beat, 288 lines a day. The first failure of a streak, then one line an hour with the
     * count in between, then the recovery: still loud, just shorter. The monitor's own
     * silence check is the alarm; this file is the evidence behind it.
     */
    static final class HeartbeatFailureLog {
        static final long LOG_INTERVAL_MS = 60 * 60_000;

        private String streakFailure;
        private long lastLoggedAtMs;
        private int unloggedFailures;
        private int streakFailures;

        /**
         * The number of failures left out since the last line, to log with this one, or null
         * when this failure stays out of the file. A failure unlike the last logged one is
         * logged at once. Compared on the status and the exception class, not the message:
         * Android's connect errors carry a new local port each time.
         */
        synchronized Integer onFailure(final int httpStatus, final String error, final long nowMs) {
            final String failure = httpStatus + " " + (error == null ? "" : error.split(":", 2)[0]);
            streakFailures++;
            if (failure.equals(streakFailure) && nowMs - lastLoggedAtMs < LOG_INTERVAL_MS) {
                unloggedFailures++;
                return null;
            }
            final int repeated = unloggedFailures;
            streakFailure = failure;
            lastLoggedAtMs = nowMs;
            unloggedFailures = 0;
            return repeated;
        }

        /** How many beats in a row failed before this success, or null when none did. */
        synchronized Integer onSuccess() {
            if (streakFailure == null) return null;
            final int failed = streakFailures;
            streakFailure = null;
            streakFailures = 0;
            unloggedFailures = 0;
            return failed;
        }
    }
}
