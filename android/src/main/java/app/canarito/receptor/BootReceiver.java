package app.canarito.receptor;

import android.content.BroadcastReceiver;
import android.content.Context;
import android.content.Intent;

/**
 * Opens the GPS request right at boot, before the listener is bound and before Play Services
 * takes its first fix, and again after an APK update, which kills the service. Both
 * broadcasts may start a foreground service from the background; the listener's first
 * heartbeat after an update may not, and the receptor would stay without GPS until a reboot.
 */
public final class BootReceiver extends BroadcastReceiver {
    @Override
    public void onReceive(Context context, Intent intent) {
        if (!restartsGpsKeeper(intent.getAction())) return;
        GpsKeeperService.sync(context, Forwarder.isRelaySensor(context));
    }

    static boolean restartsGpsKeeper(String action) {
        return Intent.ACTION_BOOT_COMPLETED.equals(action)
                || Intent.ACTION_MY_PACKAGE_REPLACED.equals(action);
    }
}
