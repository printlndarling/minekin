package org.minekin.bridge.runtime;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertFalse;
import static org.junit.jupiter.api.Assertions.assertTrue;

import io.minekin.protocol.v1.ConnectWorld;
import io.minekin.protocol.v1.HostLifecycle;
import io.minekin.protocol.v1.HostPhase;
import io.minekin.protocol.v1.OpenLan;
import java.util.ArrayList;
import java.util.List;
import net.minecraft.client.MinecraftClient;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import org.minekin.bridge.host.HostControl;
import org.minekin.bridge.host.LanPublication;
import org.minekin.bridge.host.LanRefusal;

/**
 * When a command to publish a world is acted on, and what it is answered with.
 *
 * <p>None of this needs a client: the only Minecraft-touching part is the call
 * itself, which is behind the seam. What is decided here is the bookkeeping that the
 * client cannot do for us — the command and the world arrive in either order, and the
 * same command must not be acted on twice.
 */
final class HostControllerTest {

    private static final long GENERATION = 3;
    private static final long NOW = 1_000_000_000L;

    private final List<HostLifecycle> reported = new ArrayList<>();
    private final FakeHost host = new FakeHost();
    private final HostController controller = new HostController(host, lifecycle -> {
        reported.add(lifecycle);
        return true;
    });

    @BeforeEach
    void nothingReportedYet() {
        reported.clear();
        host.published.clear();
    }

    private static OpenLan command(long deadlineNanos, int port) {
        return OpenLan.newBuilder()
                .setRequestId("lan-1")
                .setGeneration(GENERATION)
                .setPort(port)
                .setDeadlineMonotonicNs(deadlineNanos)
                .build();
    }

    private void deliver(OpenLan value, long nowNanos) {
        assertTrue(controller.handle(null, new BridgeIpcWorker.OpenLanCommand(value), nowNanos));
    }

    @Test
    void aMessageThatIsNotAColourOfOursIsLeftForSomebodyElse() {
        boolean mine = controller.handle(
                null, new BridgeIpcWorker.ConnectCommand(ConnectWorld.getDefaultInstance()), NOW);

        assertFalse(mine);
        assertEquals(List.of(), reported);
    }

    @Test
    void aWorldThatExistsIsPublishedOnTheSpot() {
        host.hosting = true;
        host.next = LanPublication.published(25565);

        deliver(command(NOW + 30_000_000_000L, 0), NOW);

        // The command asked for zero — "choose one" — and the answer is where the
        // adapter says it landed, not what it was asked for.
        assertEquals(List.of(0), host.published);
        assertEquals(1, reported.size());
        assertEquals(HostPhase.HOST_PHASE_LAN_OPENED, reported.get(0).getPhase());
        assertEquals(25565, reported.get(0).getBoundPort());
        assertEquals("lan-1", reported.get(0).getRequestId());
    }

    @Test
    void aWorldThatDoesNotExistYetIsWaitedFor() {
        // The launcher is faster than the client: the command arrives before the
        // world does, which is the ordinary case rather than an error.
        host.hosting = false;

        deliver(command(NOW + 30_000_000_000L, 0), NOW);

        assertEquals(List.of(), host.published);
        assertEquals(List.of(), reported);

        host.hosting = true;
        controller.tick(null, NOW + 1_000_000_000L);

        assertEquals(List.of(0), host.published);
        assertEquals(HostPhase.HOST_PHASE_LAN_OPENED, reported.get(0).getPhase());
    }

    @Test
    void aWorldThatNeverArrivesIsReportedAsAFailureAtTheDeadline() {
        host.hosting = false;
        deliver(command(NOW + 5_000_000_000L, 0), NOW);

        controller.tick(null, NOW + 4_000_000_000L);
        assertEquals(List.of(), reported);

        controller.tick(null, NOW + 5_000_000_000L);

        assertEquals(1, reported.size());
        assertEquals(HostPhase.HOST_PHASE_LAN_OPEN_FAILED, reported.get(0).getPhase());
        assertEquals(0, reported.get(0).getBoundPort());
        // And it is not still waiting afterwards: one command, one answer.
        controller.tick(null, NOW + 6_000_000_000L);
        assertEquals(1, reported.size());
    }

    @Test
    void aPublicationThatWasRefusedIsAFailureWithoutAPort() {
        host.hosting = true;
        host.next = LanPublication.refused(LanRefusal.BIND_FAILED);

        deliver(command(NOW + 30_000_000_000L, 0), NOW);

        assertEquals(HostPhase.HOST_PHASE_LAN_OPEN_FAILED, reported.get(0).getPhase());
        assertEquals(0, reported.get(0).getBoundPort());
    }

    @Test
    void thePortThatIsReportedIsTheOneThatWasBoundAndNotTheOneThatWasAskedFor() {
        // Asking for zero means "choose one", and the answer is where it landed.
        host.hosting = true;
        host.next = LanPublication.published(54321);

        deliver(command(NOW + 30_000_000_000L, 0), NOW);

        assertEquals(List.of(0), host.published);
        assertEquals(54321, reported.get(0).getBoundPort());
    }

    @Test
    void theSameCommandIsNotActedOnTwice() {
        // Measured: the client's bind appends to its channel list, so a second call
        // listens on a second socket — and with a chosen port the second one is at a
        // port nothing reports, because the getter answers with the first.
        host.hosting = true;
        host.next = LanPublication.published(25565);

        deliver(command(NOW + 30_000_000_000L, 0), NOW);
        deliver(command(NOW + 30_000_000_000L, 0), NOW);

        assertEquals(List.of(0), host.published);
        assertEquals(2, reported.size());
        assertEquals(25565, reported.get(1).getBoundPort());
        assertEquals(HostPhase.HOST_PHASE_LAN_OPENED, reported.get(1).getPhase());
    }

    @Test
    void aFailureDoesNotStopTheWorldFromBeingPublishedLater() {
        host.hosting = true;
        host.next = LanPublication.refused(LanRefusal.NOT_HOSTING);
        deliver(command(NOW + 30_000_000_000L, 0), NOW);
        assertEquals(HostPhase.HOST_PHASE_LAN_OPEN_FAILED, reported.get(0).getPhase());

        // A second command, for the same generation, after the world really exists.
        host.next = LanPublication.published(25566);
        deliver(command(NOW + 30_000_000_000L, 0), NOW);

        assertEquals(HostPhase.HOST_PHASE_LAN_OPENED, reported.get(1).getPhase());
        assertEquals(25566, reported.get(1).getBoundPort());
    }

    private static final class FakeHost implements HostControl {

        boolean hosting;
        LanPublication next = LanPublication.published(25565);
        final List<Integer> published = new ArrayList<>();

        @Override
        public boolean isHosting(MinecraftClient client) {
            return hosting;
        }

        @Override
        public LanPublication publish(MinecraftClient client, int requestedPort) {
            published.add(requestedPort);
            return next;
        }
    }
}
