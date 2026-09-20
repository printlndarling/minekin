package org.minekin.bridge.host;

import java.net.InetSocketAddress;
import java.net.SocketAddress;

/**
 * Where a world ended up reachable, or that it did not.
 *
 * <p>Reading the port is the part of publishing that is easy to get wrong, so it is
 * the part that lives on its own and can be tested. The client's own log line
 * ({@code Started serving on {}}) and {@code IntegratedServer.getServerPort()} both
 * report the port that was <em>asked for</em>: measured in 1.21.4, the value is
 * stored as it was passed in. Ask for zero — let the operating system choose — and
 * both say {@code 0}, while the world is actually listening somewhere else. A
 * publication built from those reads would be a success that names no address, which
 * is worse than a failure, because it looks like one.
 *
 * <p>The port that exists is the one on the socket, so that is what is read.
 *
 * @param opened whether the world is published
 * @param boundPort the port it is reachable on, and 0 when it is not published
 * @param refusal why it is not published, and {@code null} when it is
 */
public record LanPublication(boolean opened, int boundPort, LanRefusal refusal) {

    public LanPublication {
        if (opened && (refusal != null || boundPort <= 0 || boundPort > 65535)) {
            throw new IllegalArgumentException(
                    "a published world must name the port it is published on");
        }
        if (!opened && refusal == null) {
            throw new IllegalArgumentException("a world that is not published must say why");
        }
        if (!opened && boundPort != 0) {
            throw new IllegalArgumentException("a world that is not published has no port");
        }
    }

    public static LanPublication published(int boundPort) {
        return new LanPublication(true, boundPort, null);
    }

    public static LanPublication refused(LanRefusal refusal) {
        return new LanPublication(false, 0, refusal);
    }

    /**
     * The publication a bound address describes, if it describes one.
     *
     * <p>A socket address that is not an {@link InetSocketAddress}, one with no port,
     * or one whose port is zero, cannot be joined by anybody: this is where "the call
     * said yes" stops being the same question as "the world is reachable", and where
     * answering the first when only the second matters would put a lie on the wire.
     */
    public static LanPublication of(SocketAddress bound) {
        if (!(bound instanceof InetSocketAddress address)) {
            return refused(LanRefusal.NO_BOUND_ADDRESS);
        }
        int port = address.getPort();
        if (port <= 0) {
            return refused(LanRefusal.NO_BOUND_ADDRESS);
        }
        return published(port);
    }
}
