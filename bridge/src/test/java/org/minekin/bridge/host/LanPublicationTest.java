package org.minekin.bridge.host;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertThrows;
import static org.junit.jupiter.api.Assertions.assertTrue;

import java.net.InetSocketAddress;
import java.net.SocketAddress;
import java.net.UnixDomainSocketAddress;
import org.junit.jupiter.api.Test;

/**
 * The rule for turning "it said yes" into "here is where it is".
 *
 * <p>These are the reads that decide what goes on the wire, and the trap is specific:
 * the port the client reports is the port that was requested, so a world published on
 * an operating-system-chosen port reports {@code 0}. Answering the client's word here
 * would put a published world with no address on the wire — a success that cannot be
 * joined, indistinguishable from one that works until somebody tries.
 */
final class LanPublicationTest {

    @Test
    void aBoundAddressWithAPortIsWhereTheWorldIs() {
        LanPublication publication =
                LanPublication.of(new InetSocketAddress("127.0.0.1", 25565));

        assertTrue(publication.opened());
        assertEquals(25565, publication.boundPort());
        assertEquals(null, publication.refusal());
    }

    @Test
    void anOperatingSystemChosenPortTheSocketDoesNotNameIsNotAPublication() {
        // What `getServerPort()` and the client's own log say when the requested port
        // was zero. The socket is listening somewhere; this read does not know where.
        LanPublication publication = LanPublication.of(new InetSocketAddress("127.0.0.1", 0));

        assertEquals(false, publication.opened());
        assertEquals(LanRefusal.NO_BOUND_ADDRESS, publication.refusal());
    }

    @Test
    void anAddressThatIsNotAnInternetAddressIsNotAPublication() {
        SocketAddress unix = UnixDomainSocketAddress.of("/tmp/minekin.sock");

        assertEquals(LanRefusal.NO_BOUND_ADDRESS, LanPublication.of(unix).refusal());
    }

    @Test
    void anAbsentAddressIsNotAPublication() {
        assertEquals(LanRefusal.NO_BOUND_ADDRESS, LanPublication.of(null).refusal());
    }

    @Test
    void aPublicationThatSaysItOpenedMustNameAPort() {
        assertThrows(IllegalArgumentException.class, () -> LanPublication.published(0));
        assertThrows(IllegalArgumentException.class, () -> LanPublication.published(70000));
        assertThrows(
                IllegalArgumentException.class,
                () -> new LanPublication(true, 25565, LanRefusal.BIND_FAILED));
    }

    @Test
    void aRefusalMustSayWhyAndCannotCarryAPort() {
        assertThrows(IllegalArgumentException.class, () -> new LanPublication(false, 0, null));
        assertThrows(
                IllegalArgumentException.class,
                () -> new LanPublication(false, 25565, LanRefusal.NOT_HOSTING));
    }

    @Test
    void aRefusalNamesAReasonFromTheClosedSet() {
        assertEquals(LanRefusal.BIND_FAILED, LanPublication.refused(LanRefusal.BIND_FAILED).refusal());
        assertEquals(3, LanRefusal.values().length);
    }
}
