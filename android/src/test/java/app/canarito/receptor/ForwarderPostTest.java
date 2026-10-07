package app.canarito.receptor;

import static org.junit.Assert.assertEquals;
import static org.junit.Assert.assertNotNull;
import static org.junit.Assert.assertNull;
import static org.junit.Assert.assertTrue;

import java.io.ByteArrayOutputStream;
import java.io.InputStream;
import java.io.OutputStream;
import java.net.InetAddress;
import java.net.ServerSocket;
import java.net.Socket;
import java.nio.charset.StandardCharsets;
import java.util.Locale;

import org.junit.Test;

/** Runs on the JDK's HttpURLConnection, not Android's; both stream a fixed-length body. */
public class ForwarderPostTest {
    private static final long SERVER_READ_DELAY_MS = 300;
    // Far past the loopback socket buffers, so the write can only finish once the server reads.
    private static final int BODY_BYTES = 32 * 1024 * 1024;

    @Test
    public void stampsWhenTheBodyIsOnTheWireNotWhenItIsBuffered() throws Exception {
        try (ServerSocket server = new ServerSocket(0, 1, InetAddress.getLoopbackAddress())) {
            final Thread slowReader = new Thread(() -> readLateAndAccept(server));
            slowReader.start();
            final long startedAtMs = System.currentTimeMillis();
            final Forwarder.PostResult result = Forwarder.post(
                    "http://127.0.0.1:" + server.getLocalPort() + "/topic", "token", "Alerta de sismo", new byte[BODY_BYTES]);
            slowReader.join();

            assertEquals(202, result.status());
            assertNotNull(result.writtenAtMs());
            // A buffered body would be "written" at once and only sent in getResponseCode.
            assertTrue("stamped before the body left",
                    result.writtenAtMs() - startedAtMs >= SERVER_READ_DELAY_MS);
        }
    }

    @Test
    public void noStampWhenTheBodyNeverLeft() {
        final Forwarder.PostResult result = Forwarder.post("http://127.0.0.1:1/topic", null, "Alerta de sismo", new byte[] {1});
        assertEquals(-1, result.status());
        assertNull(result.writtenAtMs());
    }

    /** Reads the headers, waits, drains the body, then answers 202. */
    private static void readLateAndAccept(ServerSocket server) {
        try (Socket client = server.accept()) {
            final InputStream input = client.getInputStream();
            long length = -1;
            final StringBuilder headers = new StringBuilder();
            for (String line = readLine(input); !line.isEmpty(); line = readLine(input)) {
                headers.append(line.toLowerCase(Locale.ROOT)).append('\n');
                if (line.toLowerCase(Locale.ROOT).startsWith("content-length:")) {
                    length = Long.parseLong(line.substring("content-length:".length()).trim());
                }
            }
            assertEquals("not a fixed-length body", BODY_BYTES, length);
            // What makes ntfy ring the phone instead of filing the message quietly.
            assertTrue(headers.toString(), headers.toString().contains("priority: urgent\n"));
            assertTrue(headers.toString(), headers.toString().contains("title: alerta de sismo\n"));
            assertTrue(headers.toString(), headers.toString().contains("authorization: bearer token\n"));
            Thread.sleep(SERVER_READ_DELAY_MS);
            input.readNBytes(BODY_BYTES);
            final OutputStream output = client.getOutputStream();
            output.write("HTTP/1.1 202 Accepted\r\nContent-Length: 0\r\nConnection: close\r\n\r\n"
                    .getBytes(StandardCharsets.US_ASCII));
            output.flush();
        } catch (Exception error) {
            throw new AssertionError(error);
        }
    }

    private static String readLine(InputStream input) throws Exception {
        final ByteArrayOutputStream line = new ByteArrayOutputStream();
        for (int next = input.read(); next != '\n'; next = input.read()) {
            if (next != '\r') line.write(next);
        }
        return line.toString(StandardCharsets.US_ASCII);
    }
}
