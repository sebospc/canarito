package app.canarito.receptor;

final class EventClassifier {
    static final String GOOGLE_PLAY_SERVICES = "com.google.android.gms";

    private EventClassifier() {}

    static String sourceFor(String packageName) {
        return GOOGLE_PLAY_SERVICES.equals(packageName) ? "GMS_CANDIDATE" : "IGNORED";
    }

    static boolean shouldCapture(String packageName) {
        return GOOGLE_PLAY_SERVICES.equals(packageName);
    }
}
