package app.canarito.receptor;

import android.app.Activity;
import android.content.Intent;
import android.graphics.Typeface;
import android.net.Uri;
import android.os.Bundle;
import android.provider.Settings;
import android.view.View;
import android.widget.Button;
import android.widget.LinearLayout;
import android.widget.TextView;
import android.widget.Toast;

import org.json.JSONObject;

import java.io.FileInputStream;
import java.io.OutputStream;

public final class MainActivity extends Activity {
    private static final int EXPORT_REQUEST = 10;
    private TextView status;

    @Override
    protected void onCreate(Bundle state) {
        super.onCreate(state);

        LinearLayout layout = new LinearLayout(this);
        layout.setOrientation(LinearLayout.VERTICAL);
        int padding = dp(20);
        layout.setPadding(padding, padding, padding, padding);

        TextView title = new TextView(this);
        title.setText("Canarito");
        title.setTextSize(24);
        title.setTypeface(Typeface.DEFAULT_BOLD);
        layout.addView(title);

        TextView warning = new TextView(this);
        warning.setText("Receptor. Sends Google's earthquake early warnings from this emulator to your phone. The evidence file keeps every Play Services notification it sees.");
        warning.setPadding(0, dp(12), 0, dp(12));
        layout.addView(warning);

        status = new TextView(this);
        layout.addView(status);

        layout.addView(button("Grant notification access", view ->
                startActivity(new Intent(Settings.ACTION_NOTIFICATION_LISTENER_SETTINGS))));
        layout.addView(button("Mark AEA demo start", view -> writeMarker("AEA_DEMO_START")));
        layout.addView(button("Mark AEA demo end", view -> writeMarker("AEA_DEMO_END")));
        layout.addView(button("Export JSONL evidence", view -> exportEvidence()));
        setContentView(layout);
    }

    @Override
    protected void onResume() {
        super.onResume();
        String listeners = Settings.Secure.getString(
                getContentResolver(), "enabled_notification_listeners");
        boolean enabled = listeners != null && listeners.contains(getPackageName());
        long bytes = EvidenceStore.file(this).length();
        status.setText("Listener: " + (enabled ? "enabled" : "disabled")
                + "\nLocal evidence: " + bytes + " bytes");
    }

    private void writeMarker(String type) {
        JSONObject marker = CaptureService.baseEvent(this, type);
        EvidenceStore.append(this, marker);
        Toast.makeText(this, "Marker saved", Toast.LENGTH_SHORT).show();
        onResume();
    }

    private void exportEvidence() {
        Intent intent = new Intent(Intent.ACTION_CREATE_DOCUMENT)
                .setType("application/x-ndjson")
                .putExtra(Intent.EXTRA_TITLE, EvidenceStore.FILE_NAME);
        startActivityForResult(intent, EXPORT_REQUEST);
    }

    @Override
    protected void onActivityResult(int requestCode, int resultCode, Intent data) {
        super.onActivityResult(requestCode, resultCode, data);
        if (requestCode != EXPORT_REQUEST || resultCode != RESULT_OK || data == null) return;
        Uri destination = data.getData();
        try (FileInputStream input = new FileInputStream(EvidenceStore.file(this));
             OutputStream output = getContentResolver().openOutputStream(destination)) {
            byte[] buffer = new byte[8192];
            int count;
            while ((count = input.read(buffer)) != -1) output.write(buffer, 0, count);
            Toast.makeText(this, "Evidence exported", Toast.LENGTH_SHORT).show();
        } catch (Exception error) {
            Toast.makeText(this, "Export failed: " + error, Toast.LENGTH_LONG).show();
        }
    }

    private Button button(String text, View.OnClickListener listener) {
        Button button = new Button(this);
        button.setText(text);
        button.setOnClickListener(listener);
        return button;
    }

    private int dp(int value) {
        return Math.round(value * getResources().getDisplayMetrics().density);
    }
}
