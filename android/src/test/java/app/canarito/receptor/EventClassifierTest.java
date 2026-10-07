package app.canarito.receptor;

import static org.junit.Assert.assertEquals;
import static org.junit.Assert.assertFalse;
import static org.junit.Assert.assertTrue;

import org.junit.Test;

public class EventClassifierTest {
    @Test
    public void capturesOnlyPlayServices() {
        assertEquals("GMS_CANDIDATE", EventClassifier.sourceFor("com.google.android.gms"));
        assertTrue(EventClassifier.shouldCapture("com.google.android.gms"));
        assertFalse(EventClassifier.shouldCapture("com.example.unrelated"));
    }
}
