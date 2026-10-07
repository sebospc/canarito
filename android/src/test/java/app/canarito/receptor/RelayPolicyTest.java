package app.canarito.receptor;

import static org.junit.Assert.assertEquals;
import static org.junit.Assert.assertFalse;
import static org.junit.Assert.assertNotEquals;
import static org.junit.Assert.assertNull;
import static org.junit.Assert.assertTrue;

import org.junit.Test;

public class RelayPolicyTest {
    private static final String GMS = "com.google.android.gms";
    private static final String SIGNER = RelayPolicy.PLAY_SERVICES_SIGNER;

    @Test
    public void relaysOnlySignedEarlyWarnings() {
        assertTrue(RelayPolicy.isRelayable(GMS, SIGNER, "eew_alert_v2"));
        // The late "you may have felt shaking" notice must never become "take cover".
        assertFalse(RelayPolicy.isRelayable(GMS, SIGNER, "eew_update"));
        assertFalse(RelayPolicy.isRelayable(GMS, SIGNER, "finder-configuration"));
        assertFalse(RelayPolicy.isRelayable(GMS, "00", "eew_alert_v2"));
        assertFalse(RelayPolicy.isRelayable(GMS, "UNAVAILABLE:X", "eew_alert_v2"));
        assertFalse(RelayPolicy.isRelayable("com.example.fake", SIGNER, "eew_alert_v2"));
        assertFalse(RelayPolicy.isRelayable(GMS, SIGNER, null));
    }

    @Test
    public void usesOwnWordsFromTheStructuredExtras() {
        assertEquals("Sismo M4.5 cerca de su zona. Protéjase ahora.", RelayPolicy.bodyFor(4.45852f, "es"));
        assertEquals("Posible sismo cerca de su zona. Protéjase ahora.", RelayPolicy.bodyFor(null, ""));
        assertEquals("Earthquake M4.5 near you. Take cover now.", RelayPolicy.bodyFor(4.45852f, "en"));
        assertEquals("Alerta de sismo", RelayPolicy.titleFor(null));
        assertEquals("Earthquake alert", RelayPolicy.titleFor("en"));
        // The distance is from the receptor, never from the phone: it must not reach the text.
        assertFalse(RelayPolicy.bodyFor(4.48f, "es").contains("km"));
        assertFalse(RelayPolicy.bodyFor(4.48f, "en").contains("km"));
    }

    @Test
    public void sendsToItsOwnLinkFirstAndToEachSleepingNeighbourOnce() {
        assertEquals(java.util.Arrays.asList("https://ntfy.sh/casa", "https://ntfy.sh/ana"),
                RelayPolicy.targets("https://ntfy.sh/casa",
                        java.util.Arrays.asList("https://ntfy.sh/ana", "", null, "https://ntfy.sh/casa", "https://ntfy.sh/ana")));
        assertEquals(java.util.Collections.singletonList("https://ntfy.sh/casa"),
                RelayPolicy.targets("https://ntfy.sh/casa", java.util.Collections.emptyList()));
    }

    @Test
    public void keysOnQuakeOriginNotOnNotificationTag() {
        // The two real Chaparral quakes, 5 h apart, shared one tag but not one origin.
        String first = RelayPolicy.eventId("chaparral", 1790194179L, 0);
        String second = RelayPolicy.eventId("chaparral", 1790212783L, 0);
        assertNotEquals(first, second);
        assertEquals(first, RelayPolicy.eventId("chaparral", 1790194179L, 999));
        assertNotEquals(first, RelayPolicy.eventId("quibdo", 1790194179L, 0));
    }

    @Test
    public void replaysOnlyWarningsStillInsideTheirTtl() {
        long now = 1_790_230_000_000L;
        assertTrue(RelayPolicy.isReplayable(now, now));
        assertTrue(RelayPolicy.isReplayable(now - RelayPolicy.ALERT_TTL_MS + 1, now));
        assertFalse(RelayPolicy.isReplayable(now - RelayPolicy.ALERT_TTL_MS, now));
        // An NTP step back leaves a fresh warning a little in the future; a real jump does not.
        assertTrue(RelayPolicy.isReplayable(now + RelayPolicy.CLOCK_STEP_TOLERANCE_MS, now));
        assertFalse(RelayPolicy.isReplayable(now + RelayPolicy.CLOCK_STEP_TOLERANCE_MS + 1, now));
    }

    @Test
    public void dropsNonFiniteNumbersInsteadOfCrashing() {
        // Both kinds of non-finite on both overloads: checking only NaN or only infinity passes half.
        assertNull(RelayPolicy.finiteOrNull(Float.NaN));
        assertNull(RelayPolicy.finiteOrNull(Float.NEGATIVE_INFINITY));
        assertNull(RelayPolicy.finiteOrNull(Double.NaN));
        assertNull(RelayPolicy.finiteOrNull(Double.POSITIVE_INFINITY));
        assertNull(RelayPolicy.finiteOrNull((Float) null));
        assertNull(RelayPolicy.finiteOrNull((Double) null));
        assertEquals(Float.valueOf(4.5f), RelayPolicy.finiteOrNull(4.5f));
        assertEquals(Double.valueOf(18.9089), RelayPolicy.finiteOrNull(18.9089));
    }

    private static final long BEAT_MS = RelayPolicy.HEARTBEAT_INTERVAL_MS;
    // An HTTP answer carries no error, only a status.
    private static final String NO_ERROR = null;

    @Test
    public void logsTheFirstRefusedBeatThenOneLineAnHourWithTheCount() {
        final RelayPolicy.HeartbeatFailureLog log = new RelayPolicy.HeartbeatFailureLog();
        assertEquals(Integer.valueOf(0), log.onFailure(400, NO_ERROR, 0));
        final long beatsPerHour = RelayPolicy.HeartbeatFailureLog.LOG_INTERVAL_MS / BEAT_MS;
        for (long beat = 1; beat < beatsPerHour; beat++) {
            assertNull(log.onFailure(400, NO_ERROR, beat * BEAT_MS));
        }
        assertEquals(Integer.valueOf(11), log.onFailure(400, NO_ERROR, beatsPerHour * BEAT_MS));
        assertNull(log.onFailure(400, NO_ERROR, (beatsPerHour + 1) * BEAT_MS));
    }

    @Test
    public void logsAChangedFailureAtOnce() {
        final RelayPolicy.HeartbeatFailureLog log = new RelayPolicy.HeartbeatFailureLog();
        log.onFailure(400, NO_ERROR, 0);
        assertNull(log.onFailure(400, NO_ERROR, BEAT_MS));
        assertEquals(Integer.valueOf(1), log.onFailure(503, NO_ERROR, 2 * BEAT_MS));
        assertEquals(Integer.valueOf(0),
                log.onFailure(-1, "java.net.SocketTimeoutException: connect timed out", 3 * BEAT_MS));
        // Same exception, new local port in the message: the same failure, not a new line.
        log.onFailure(-1, "java.net.ConnectException: failed to connect from /10.0.2.15 (port 41234)", 4 * BEAT_MS);
        assertNull(log.onFailure(-1, "java.net.ConnectException: failed to connect from /10.0.2.15 (port 41250)", 5 * BEAT_MS));
    }

    @Test
    public void reportsTheWholeStreakOnRecoveryAndStartsOver() {
        final RelayPolicy.HeartbeatFailureLog log = new RelayPolicy.HeartbeatFailureLog();
        assertNull(log.onSuccess());
        log.onFailure(400, NO_ERROR, 0);
        log.onFailure(400, NO_ERROR, BEAT_MS);
        log.onFailure(503, NO_ERROR, 2 * BEAT_MS);
        assertEquals(Integer.valueOf(3), log.onSuccess());
        assertNull(log.onSuccess());
        // After a recovery the next failure is news again, even inside the hour.
        assertEquals(Integer.valueOf(0), log.onFailure(400, NO_ERROR, 3 * BEAT_MS));
    }
}
