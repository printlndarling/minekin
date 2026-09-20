package org.minekin.bridge.host;

/**
 * Where a world ended up reachable, or that it did not.
 *
 * <p>Naming the port is the part of publishing that is easy to get wrong, so it is the
 * part that lives on its own. The client's log line ({@code Started serving on {}}) and
 * {@code IntegratedServer.getServerPort()} both report the port that was <em>asked
 * for</em> — measured in 1.21.4, the value is stored as it was passed in — and nothing
 * public reports the one it bound: asking for zero makes both say {@code 0} while the
 * world listens somewhere else, and the one method that returns an address
 * ({@code ServerNetworkIo.bindLocal()}) binds a separate local channel rather than
 * describing that socket. So a port is chosen before the call and named into it, which
 * is what the game's own "Open to LAN" screen does; a publication that cannot name a
 * port is a refusal rather than a success, because a success nobody can join looks
 * like one.
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
}
