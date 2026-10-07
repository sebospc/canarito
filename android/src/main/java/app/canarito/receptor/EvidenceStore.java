package app.canarito.receptor;

import android.content.Context;
import android.util.Log;

import org.json.JSONObject;

import java.io.File;
import java.io.FileOutputStream;
import java.nio.charset.StandardCharsets;

final class EvidenceStore {
    static final String FILE_NAME = "notification-evidence.jsonl";
    private static final Object LOCK = new Object();

    private EvidenceStore() {}

    static File file(Context context) {
        return new File(context.getFilesDir(), FILE_NAME);
    }

    /**
     * Never throws. It runs on the main thread and inside the relay loop, where a full
     * disk would otherwise crash the listener or cut an alert's retries short.
     */
    static void append(Context context, JSONObject event) {
        synchronized (LOCK) {
            try (FileOutputStream output = new FileOutputStream(file(context), true)) {
                output.write((event.toString() + "\n").getBytes(StandardCharsets.UTF_8));
                output.getFD().sync();
            } catch (Exception error) {
                Log.e("EvidenceStore", "could not persist evidence", error);
            }
        }
    }
}
