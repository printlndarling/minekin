package org.minekin.bridge.host;

import static org.junit.jupiter.api.Assertions.assertTrue;

import java.io.IOException;
import java.net.ServerSocket;
import org.junit.jupiter.api.Test;

/**
 * Choosing a port is the one piece of the adapter that needs no client, so it is the
 * one piece that can be checked here.
 *
 * <p>It has to be an actual free port rather than a plausible number: the port goes
 * into the client's own call and comes back in the report, so a wrong one is a
 * published world nobody can join. The check is the only honest one available — bind
 * it and see.
 */
final class IntegratedServerControlTest {

    @Test
    void thePortChosenIsAPortSomethingCanStillBind() throws IOException {
        int port = IntegratedServerControl.freePort();

        assertTrue(port > 0, "a chosen port must be a port");
        try (ServerSocket socket = new ServerSocket(port)) {
            assertTrue(socket.isBound());
        }
    }
}
