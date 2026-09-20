package org.minekin.bridge.host;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertThrows;
import static org.junit.jupiter.api.Assertions.assertTrue;

import org.junit.jupiter.api.Test;

/**
 * The two shapes a publication may take, and the invariant that keeps them apart.
 *
 * <p>The rule this record exists for: a publication that says it opened must name a
 * port, and one that did not must say why and name none. It is the one thing here that
 * a caller cannot get wrong quietly — "published on port 0" is a world nobody can join
 * that reads on the wire exactly like one they can.
 */
final class LanPublicationTest {

    @Test
    void aPublicationNamesThePortItIsPublishedOn() {
        LanPublication publication = LanPublication.published(25565);

        assertTrue(publication.opened());
        assertEquals(25565, publication.boundPort());
        assertEquals(null, publication.refusal());
    }

    @Test
    void aPublicationWithoutAPortIsRefusedRatherThanReported() {
        // What `getServerPort()` and the client's own log say when the request was zero.
        // The socket is listening somewhere; this read does not know where, and a
        // success that cannot name an address is worse than a failure.
        assertThrows(IllegalArgumentException.class, () -> LanPublication.published(0));
        assertThrows(IllegalArgumentException.class, () -> LanPublication.published(70000));
    }

    @Test
    void aRefusalMustSayWhyAndCannotCarryAPort() {
        assertThrows(IllegalArgumentException.class, () -> new LanPublication(false, 0, null));
        assertThrows(
                IllegalArgumentException.class,
                () -> new LanPublication(false, 25565, LanRefusal.NOT_HOSTING));
        assertThrows(
                IllegalArgumentException.class,
                () -> new LanPublication(true, 25565, LanRefusal.BIND_FAILED));
    }

    @Test
    void aRefusalNamesAReasonFromTheClosedSet() {
        LanPublication refusal = LanPublication.refused(LanRefusal.BIND_FAILED);

        assertEquals(LanRefusal.BIND_FAILED, refusal.refusal());
        assertEquals(0, refusal.boundPort());
        assertEquals(3, LanRefusal.values().length);
    }
}
