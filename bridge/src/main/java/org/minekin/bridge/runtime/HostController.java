package org.minekin.bridge.runtime;

import io.minekin.protocol.v1.HostLifecycle;
import io.minekin.protocol.v1.HostPhase;
import io.minekin.protocol.v1.OpenLan;
import java.util.Objects;
import java.util.function.Predicate;
import net.minecraft.client.MinecraftClient;
import org.minekin.bridge.host.HostControl;
import org.minekin.bridge.host.IntegratedServerControl;
import org.minekin.bridge.host.LanPublication;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;

/**
 * Publishing the world a Kin is hosting, from the client thread, when there is one.
 *
 * <p>The command and the world do not arrive in a fixed order. The client enters its
 * world asynchronously after launch, so an {@code OpenLan} can arrive before there is
 * anything to publish — and a command that failed for that reason would be a command
 * that fails every time the launcher is faster than the client. The wait is what the
 * command's own deadline is for: held while the world is missing, acted on the tick
 * it appears, and reported as failed if it never does.
 *
 * <p>A world is published at most once per generation, and that is a safety rule
 * rather than tidiness. Measured against 1.21.4: the client's bind appends to its
 * channel list, so calling it twice listens on two sockets — and with a
 * system-chosen port the second one is at a port nothing reports, because the getter
 * answers with the first. So a repeated command is answered from what is already
 * known and the client is not asked again.
 *
 * <p>What is left here is the bookkeeping: whether this message is ours, whether the
 * world exists yet, whether the deadline has passed, and what to report. The call
 * itself is behind {@link HostControl}, which is why all of it can be tested without
 * a client.
 */
public final class HostController {

    private static final Logger LOGGER = LoggerFactory.getLogger("minekin-bridge");

    private final HostControl host;
    private final Predicate<HostLifecycle> sink;

    /** The command whose world does not exist yet, if there is one. */
    private OpenLan waiting;
    /** The generation and port of the world this session published, if it has. */
    private long publishedGeneration;
    private int publishedPort;

    public HostController(Predicate<HostLifecycle> sink) {
        this(new IntegratedServerControl(), sink);
    }

    public HostController(HostControl host, Predicate<HostLifecycle> sink) {
        this.host = Objects.requireNonNull(host, "host");
        this.sink = Objects.requireNonNull(sink, "sink");
    }

    /** Whether this message was the host controller's, so the caller stops looking. */
    public boolean handle(MinecraftClient client, BridgeIpcWorker.ClientMessage message) {
        return handle(client, message, BridgeIpcWorker.monotonicNow());
    }

    /**
     * The same, on a clock the caller supplies.
     *
     * <p>The deadline is a duration the caller chose, so what it means depends on
     * which clock read it — and a test that could not place that clock would be a
     * test of whenever it happened to run. The worker's clock stays where it is.
     */
    public boolean handle(
            MinecraftClient client, BridgeIpcWorker.ClientMessage message, long nowNanos) {
        if (!(message instanceof BridgeIpcWorker.OpenLanCommand command)) {
            return false;
        }
        OpenLan value = command.value();
        if (value.getGeneration() == publishedGeneration && publishedPort > 0) {
            report(value, HostPhase.HOST_PHASE_LAN_OPENED, publishedPort);
            return true;
        }
        if (host.isHosting(client)) {
            publish(client, value);
            return true;
        }
        waiting = value;
        return true;
    }

    /**
     * One client tick, which is when a held command finds out whether it has a world.
     *
     * <p>Called from the same tick that drains the inbox, so a command waits in the
     * order it arrived and for no longer than its deadline.
     */
    public void tick(MinecraftClient client) {
        tick(client, BridgeIpcWorker.monotonicNow());
    }

    public void tick(MinecraftClient client, long nowNanos) {
        OpenLan value = waiting;
        if (value == null) {
            return;
        }
        if (host.isHosting(client)) {
            waiting = null;
            publish(client, value);
            return;
        }
        if (nowNanos >= value.getDeadlineMonotonicNs()) {
            // The deadline the caller set has passed with no world to publish. Said
            // out loud as a failure rather than silently dropped: the command was
            // accepted, so somebody is waiting for an answer either way.
            waiting = null;
            LOGGER.warn("bridge could not publish a world within the command's deadline");
            report(value, HostPhase.HOST_PHASE_LAN_OPEN_FAILED, 0);
        }
    }

    private void publish(MinecraftClient client, OpenLan value) {
        LanPublication publication = host.publish(client, value.getPort());
        if (publication.opened()) {
            publishedGeneration = value.getGeneration();
            publishedPort = publication.boundPort();
            report(value, HostPhase.HOST_PHASE_LAN_OPENED, publication.boundPort());
            return;
        }
        // The reason is the Bridge's own word, in the Bridge's own log. What goes to
        // Core is the outcome, because server-side prose does not travel this way.
        LOGGER.warn("bridge did not publish this world: {}", publication.refusal());
        report(value, HostPhase.HOST_PHASE_LAN_OPEN_FAILED, 0);
    }

    private void report(OpenLan value, HostPhase phase, int boundPort) {
        HostLifecycle.Builder lifecycle = HostLifecycle.newBuilder()
                .setRequestId(value.getRequestId())
                .setGeneration(value.getGeneration())
                .setPhase(phase)
                .setBoundPort(boundPort);
        if (!sink.test(lifecycle.build())) {
            LOGGER.warn("bridge could not report {} for {}", phase, value.getRequestId());
        }
    }
}
