package app.canarito.receptor;

import static org.junit.Assert.assertFalse;
import static org.junit.Assert.assertTrue;

import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.nio.file.Paths;

import org.junit.Test;

public class BootReceiverTest {
    @Test
    public void restartsGpsKeeperAtBootAndAfterAnUpdate() throws Exception {
        assertTrue(BootReceiver.restartsGpsKeeper("android.intent.action.BOOT_COMPLETED"));
        assertTrue(BootReceiver.restartsGpsKeeper("android.intent.action.MY_PACKAGE_REPLACED"));
        assertFalse(BootReceiver.restartsGpsKeeper("android.intent.action.PACKAGE_REPLACED"));
        assertFalse(BootReceiver.restartsGpsKeeper(null));

        // The code alone is not enough: without the filter the broadcast never arrives.
        final String manifest = new String(Files.readAllBytes(Paths.get("src/main/AndroidManifest.xml")), StandardCharsets.UTF_8);
        assertTrue(manifest.contains("android.intent.action.BOOT_COMPLETED"));
        assertTrue(manifest.contains("android.intent.action.MY_PACKAGE_REPLACED"));
    }
}
