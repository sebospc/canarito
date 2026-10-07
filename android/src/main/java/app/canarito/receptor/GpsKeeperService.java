package app.canarito.receptor;

import android.Manifest;
import android.app.Notification;
import android.app.NotificationChannel;
import android.app.NotificationManager;
import android.app.Service;
import android.content.Context;
import android.content.Intent;
import android.content.pm.PackageManager;
import android.content.pm.ServiceInfo;
import android.location.Location;
import android.location.LocationListener;
import android.location.LocationManager;
import android.os.Build;
import android.os.IBinder;
import android.os.Looper;
import android.util.Log;

import org.json.JSONObject;

/**
 * Keeps a GPS request open for as long as this device is a relay sensor.
 *
 * The emulator's GNSS HAL only takes a `geo fix` while someone is asking for GPS, and Play
 * Services asks once per boot. Without this, the location froze at the boot fix and aged
 * until AEA stopped alerting (~24 h, QA-84), and moving a sensor needed a reboot. With a
 * request always open, every `geo fix` reaches Play Services within a minute.
 *
 * Real GPS on purpose, never a mock provider: a mock location is flagged isMock, and Play
 * Services would likely ignore it.
 */
public final class GpsKeeperService extends Service implements LocationListener {
    private static final String CHANNEL_ID = "gps_keeper";
    private static final int NOTIFICATION_ID = 1;
    private static final long UPDATE_INTERVAL_MS = 60_000;

    /** Runs the service while relay.json exists and stops it when it goes away. */
    static void sync(Context context, boolean isRelaySensor) {
        Intent intent = new Intent(context, GpsKeeperService.class);
        if (!isRelaySensor) {
            context.stopService(intent);
            return;
        }
        // Without it startForeground throws, and Android kills the process that failed to
        // go foreground in time. Better not to start at all and say so.
        if (context.checkSelfPermission(Manifest.permission.ACCESS_FINE_LOCATION)
                != PackageManager.PERMISSION_GRANTED) {
            recordFailure(context, new SecurityException("ACCESS_FINE_LOCATION not granted"));
            return;
        }
        try {
            context.startForegroundService(intent);
        } catch (RuntimeException refused) {
            // Android may refuse a location service started from the background. That leaves
            // the location to freeze again, so it has to show, not fail quietly.
            recordFailure(context, refused);
        }
    }

    @Override
    public void onCreate() {
        super.onCreate();
        try {
            getSystemService(LocationManager.class).requestLocationUpdates(
                    LocationManager.GPS_PROVIDER, UPDATE_INTERVAL_MS, 0f, this, Looper.getMainLooper());
        } catch (SecurityException missingPermission) {
            recordFailure(this, missingPermission);
            stopSelf();
        }
    }

    @Override
    public int onStartCommand(Intent intent, int flags, int startId) {
        // Every startForegroundService call has to be answered with startForeground.
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.Q) {
            startForeground(NOTIFICATION_ID, notification(), ServiceInfo.FOREGROUND_SERVICE_TYPE_LOCATION);
        } else {
            startForeground(NOTIFICATION_ID, notification());
        }
        return START_STICKY;
    }

    @Override
    public void onDestroy() {
        getSystemService(LocationManager.class).removeUpdates(this);
        super.onDestroy();
    }

    @Override
    public void onLocationChanged(Location location) {
        // Nothing to do: the open request is what keeps the GNSS HAL taking geo fixes.
    }

    @Override
    public IBinder onBind(Intent intent) {
        return null;
    }

    private Notification notification() {
        NotificationManager manager = getSystemService(NotificationManager.class);
        manager.createNotificationChannel(new NotificationChannel(
                CHANNEL_ID, "Canarito receptor active", NotificationManager.IMPORTANCE_MIN));
        return new Notification.Builder(this, CHANNEL_ID)
                .setSmallIcon(android.R.drawable.ic_menu_mylocation)
                .setContentTitle("Canarito receptor active")
                .setOngoing(true)
                .build();
    }

    private static void recordFailure(Context context, Exception error) {
        Log.e("GpsKeeperService", "GPS keeper not running", error);
        JSONObject record = CaptureService.baseEvent(context, "GPS_KEEPER_FAILED");
        CaptureService.put(record, "error", error.getClass().getName() + ": " + error.getMessage());
        EvidenceStore.append(context, record);
    }
}
