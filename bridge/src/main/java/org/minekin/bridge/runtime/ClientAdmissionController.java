package org.minekin.bridge.runtime;

import io.minekin.protocol.v1.ConnectWorld;
import io.minekin.protocol.v1.AdmissionFailureReason;
import io.minekin.protocol.v1.ConnectionLifecycle;
import io.minekin.protocol.v1.ConnectionPhase;
import io.minekin.protocol.v1.ResourcePackPolicy;
import io.netty.channel.ChannelFuture;
import java.util.Locale;
import java.util.function.Predicate;
import net.minecraft.client.MinecraftClient;
import net.minecraft.client.gui.screen.Screen;
import net.minecraft.client.gui.screen.TitleScreen;
import net.minecraft.client.gui.screen.multiplayer.ConnectScreen;
import net.minecraft.client.network.ServerAddress;
import net.minecraft.client.network.ServerInfo;
import net.minecraft.network.ClientConnection;
import org.minekin.bridge.mixin.ConnectScreenAccessor;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;

/** Executes already-validated admission commands only from the client tick. */
public final class ClientAdmissionController {
    private static final Logger LOGGER = LoggerFactory.getLogger("minekin-bridge");
    private final BridgePhaseMachine phases;
    private final Predicate<ConnectionLifecycle> lifecycleSink;
    private long activeGeneration;
    private String activeProfileId;
    private String activeProfileRevision;
    private ConnectScreen activeScreen;
    private Screen parentScreen;

    public ClientAdmissionController(
            BridgePhaseMachine phases, Predicate<ConnectionLifecycle> lifecycleSink) {
        this.phases = java.util.Objects.requireNonNull(phases, "phases");
        this.lifecycleSink = java.util.Objects.requireNonNull(lifecycleSink, "lifecycleSink");
    }

    public void handle(MinecraftClient client, BridgeIpcWorker.ClientMessage message) {
        java.util.Objects.requireNonNull(client, "client");
        java.util.Objects.requireNonNull(message, "message");
        if (message == BridgeIpcWorker.Notice.OBSERVE_ONLY) {
            return;
        }
        if (message == BridgeIpcWorker.Notice.SAFE_STOP) {
            safeStop(client);
            return;
        }
        if (message instanceof BridgeIpcWorker.ConnectCommand connect) {
            connect(client, connect.value());
            return;
        }
        if (message instanceof BridgeIpcWorker.CancelCommand cancel) {
            cancel(client, cancel.value().getGeneration());
            return;
        }
        throw new IllegalStateException("unknown client admission message");
    }

    public void safeStop(MinecraftClient client) {
        activeGeneration = 0;
        phases.safeStop();
        try {
            cancelVanilla(client);
        } finally {
            clearGeneration();
        }
    }

    /**
     * The client started negotiating a login with a server.
     *
     * <p>Everything the client reports about itself arrives through one of these
     * five methods, and each is fired by vanilla for *every* server the client
     * talks to — including connections this Bridge never asked for. A report is
     * therefore only made while a generation is ours to report on: an event with
     * no active generation is not evidence about anything, and attributing it to
     * whatever attempt happens to be current is how an unrelated connection
     * would advance this one.
     */
    public void loginNegotiating() {
        report(
                ConnectionPhase.CONNECTION_PHASE_LOGIN_NEGOTIATING,
                AdmissionFailureReason.ADMISSION_FAILURE_REASON_UNSPECIFIED,
                false);
    }

    /** The play network handler exists: the server completed the login handshake. */
    public void playInit() {
        report(
                ConnectionPhase.CONNECTION_PHASE_PLAY_INIT,
                AdmissionFailureReason.ADMISSION_FAILURE_REASON_UNSPECIFIED,
                false);
    }

    /** The client is in the world. A snapshot still has to be accepted for PLAYABLE. */
    public void joinSeen() {
        report(
                ConnectionPhase.CONNECTION_PHASE_JOIN_SEEN,
                AdmissionFailureReason.ADMISSION_FAILURE_REASON_UNSPECIFIED,
                false);
    }

    /**
     * The login ended without becoming a play session.
     *
     * <p>A failure rather than a disconnect: nothing was joined, so there is no
     * session a normal end could have ended. The reason is the stable enum and
     * never the server's own words — a server may say anything, and this is a
     * product event. The words are still what decides *which* enum, so they are
     * read here and classified rather than forwarded.
     */
    public void loginFailed() {
        AdmissionFailureReason reason = classifyLoginFailure(takeLoginReason());
        LOGGER.info("bridge classified the login failure as {}", reason);
        report(ConnectionPhase.CONNECTION_PHASE_FAILED, reason, true);
    }

    /**
     * The reason a server gave for ending a login, held between the packet that
     * carried it and the report that classifies it.
     *
     * <p>Static because the two halves that meet here cannot see each other: a
     * mixin has no instance to hold, and the controller is per client — and
     * there is exactly one client per process, which the mod already enforces by
     * refusing to initialize twice. It is cleared as it is read, so a reason
     * from one attempt can never be classified against the next.
     */
    private static volatile String pendingLoginReason = "";

    public static void rememberLoginReason(String reason) {
        pendingLoginReason = reason == null ? "" : reason;
    }

    private static String takeLoginReason() {
        String reason = pendingLoginReason;
        pendingLoginReason = "";
        return reason;
    }

    /**
     * The stable classification for a login a server ended.
     *
     * <p>The server's own words are the only thing that tells a whitelist
     * rejection apart from an authentication mismatch — the protocol carries a
     * sentence, not a code — so this matches the sentences a *vanilla* server
     * sends and nothing more. A reason it does not recognise stays
     * UNEXPECTED_DISCONNECT rather than being forced into a category: a wrong
     * category is worse evidence than an honest "unclassified", because it is a
     * claim about the server that nobody made.
     */
    static AdmissionFailureReason classifyLoginFailure(String reason) {
        String text = reason == null ? "" : reason.toLowerCase(Locale.ROOT);
        if (text.isBlank()) {
            return AdmissionFailureReason.ADMISSION_FAILURE_REASON_UNEXPECTED_DISCONNECT;
        }
        if (text.contains("not white-listed") || text.contains("not whitelisted")) {
            return AdmissionFailureReason.ADMISSION_FAILURE_REASON_WHITELIST_REJECTED;
        }
        if (text.contains("already connected") || text.contains("logged in from another location")) {
            return AdmissionFailureReason.ADMISSION_FAILURE_REASON_DUPLICATE_LOGIN;
        }
        if (text.contains("failed to verify username") || text.contains("not authenticated")) {
            return AdmissionFailureReason.ADMISSION_FAILURE_REASON_AUTH_MODE_MISMATCH;
        }
        if (text.contains("outdated server") || text.contains("outdated client")) {
            return AdmissionFailureReason.ADMISSION_FAILURE_REASON_PROTOCOL_MISMATCH;
        }
        if (text.contains("resource pack")) {
            return AdmissionFailureReason.ADMISSION_FAILURE_REASON_RESOURCE_PACK_BLOCKED;
        }
        return AdmissionFailureReason.ADMISSION_FAILURE_REASON_UNEXPECTED_DISCONNECT;
    }

    /** A play session ended. Terminal, and deliberately without a reason. */
    public void playEnded() {
        report(
                ConnectionPhase.CONNECTION_PHASE_DISCONNECTED,
                AdmissionFailureReason.ADMISSION_FAILURE_REASON_UNSPECIFIED,
                true);
    }

    /**
     * Reports one phase the client reached, if that generation is still ours.
     *
     * <p>A terminal phase ends the generation: the attempt is over, so the
     * bookkeeping that would attribute a later event to it is cleared and the
     * phase machine returns to OBSERVE_ONLY so a new attempt may begin.
     * Publishing happens first, while the generation still names what it is
     * about.
     */
    private void report(ConnectionPhase phase, AdmissionFailureReason reason, boolean terminal) {
        if (activeGeneration == 0) {
            // Local only, and deliberately: a diagnostic is not an event. The
            // contract forbids a server's words from entering a product payload,
            // and this line carries none — but it does say that something was
            // seen and not attributed, which is the difference between "nothing
            // happened" and "something happened that we refused to believe".
            LOGGER.info("bridge saw {} with no generation of ours active; not reported", phase);
            return;
        }
        LOGGER.info(
                "bridge reporting {} for generation {} (terminal={}, reason={})",
                phase,
                activeGeneration,
                terminal,
                reason);
        publish(phase, reason, terminal);
        if (terminal) {
            activeGeneration = 0;
            clearGeneration();
            if (phases.phase() == BridgePhaseMachine.Phase.CONNECTING_WORLD
                    || phases.phase() == BridgePhaseMachine.Phase.PLAYABLE) {
                phases.transition(BridgePhaseMachine.Phase.OBSERVE_ONLY);
            }
        }
    }

    private void clearGeneration() {
        activeScreen = null;
        parentScreen = null;
        activeProfileId = null;
        activeProfileRevision = null;
    }

    /**
     * The bookkeeping that says an attempt has begun, apart from the vanilla call
     * that starts it.
     *
     * <p>Split out so that the part deciding what this controller believes can be
     * exercised without a client: every rule about which event may advance which
     * generation lives here, and none of it needs Minecraft.
     */
    void beginGeneration(ConnectWorld command) {
        activeGeneration = command.getGeneration();
        activeProfileId = command.getServerProfileId();
        activeProfileRevision = command.getServerProfileRevision();
        phases.transition(BridgePhaseMachine.Phase.CONNECTING_WORLD);
    }

    private void connect(MinecraftClient client, ConnectWorld command) {
        if (phases.phase() != BridgePhaseMachine.Phase.OBSERVE_ONLY
                || activeGeneration != 0
                || client.world != null
                || client.player != null
                || client.getNetworkHandler() != null
                || client.currentScreen instanceof ConnectScreen) {
            throw new IllegalStateException("client is not ready for a new connection generation");
        }

        ServerAddress address = new ServerAddress(command.getOriginalHost(), command.getPort());
        ServerInfo server = new ServerInfo(
                command.getServerProfileId(), address.toString(), ServerInfo.ServerType.OTHER);
        server.setResourcePackPolicy(resourcePackPolicy(command.getResourcePackPolicy()));
        parentScreen = client.currentScreen != null ? client.currentScreen : new TitleScreen();
        beginGeneration(command);
        LOGGER.info(
                "bridge asked vanilla to connect to {} for generation {}",
                address,
                command.getGeneration());
        try {
            publish(
                    ConnectionPhase.CONNECTION_PHASE_RESOLVING,
                    AdmissionFailureReason.ADMISSION_FAILURE_REASON_UNSPECIFIED,
                    false);
            ConnectScreen.connect(
                    parentScreen,
                    client,
                    address,
                    server,
                    false,
                    // Null, not an empty CookieStorage. Vanilla decides the
                    // handshake's intent from whether this is null:
                    //
                    //     cookieStorage == null ? LOGIN : TRANSFER
                    //
                    // so an empty storage is not "no cookies", it is a transfer
                    // with no cookies in it — and a vanilla server refuses a
                    // transfer it did not start, silently, by closing the socket
                    // with no disconnect packet. That is what a plain P0
                    // connection was doing: `next_state=3`, socket closed,
                    // nothing logged on either side. "Empty cookie storage" in
                    // the contract means absent.
                    null);
            if (!(client.currentScreen instanceof ConnectScreen screen)) {
                throw new IllegalStateException("vanilla did not install ConnectScreen");
            }
            activeScreen = screen;
        } catch (RuntimeException error) {
            activeGeneration = 0;
            clearGeneration();
            if (phases.phase() == BridgePhaseMachine.Phase.CONNECTING_WORLD) {
                phases.transition(BridgePhaseMachine.Phase.OBSERVE_ONLY);
            }
            throw error;
        }
    }

    private void cancel(MinecraftClient client, long generation) {
        if (generation != activeGeneration || generation == 0) {
            throw new IllegalStateException("cancel does not name the active client generation");
        }
        // Invalidate before touching the vanilla connection, mirroring the Core
        // and IPC-side rule for late callbacks.
        activeGeneration = 0;
        cancelVanilla(client);
        publish(
                generation,
                ConnectionPhase.CONNECTION_PHASE_CANCELLED,
                AdmissionFailureReason.ADMISSION_FAILURE_REASON_CANCELLED,
                true);
        clearGeneration();
        if (phases.phase() == BridgePhaseMachine.Phase.CONNECTING_WORLD
                || phases.phase() == BridgePhaseMachine.Phase.PLAYABLE) {
            phases.transition(BridgePhaseMachine.Phase.OBSERVE_ONLY);
        }
    }

    private void publish(
            ConnectionPhase phase, AdmissionFailureReason failureReason, boolean terminal) {
        publish(activeGeneration, phase, failureReason, terminal);
    }

    private void publish(
            long generation,
            ConnectionPhase phase,
            AdmissionFailureReason failureReason,
            boolean terminal) {
        if (generation == 0 || activeProfileId == null || activeProfileRevision == null) {
            throw new IllegalStateException("connection lifecycle has no active profile binding");
        }
        ConnectionLifecycle lifecycle = ConnectionLifecycle.newBuilder()
                .setGeneration(generation)
                .setServerProfileId(activeProfileId)
                .setServerProfileRevision(activeProfileRevision)
                .setPhase(phase)
                .setFailureReason(failureReason)
                .setTerminal(terminal)
                .build();
        if (!lifecycleSink.test(lifecycle)) {
            throw new IllegalStateException("connection lifecycle event was rejected");
        }
    }

    private void cancelVanilla(MinecraftClient client) {
        // Logged because this is the one place this code closes a connection, and
        // it closes it the way the vanilla Cancel button does — by cancelling the
        // connect future. That path produces no DisconnectionInfo, so a cancelled
        // connection is indistinguishable from a connection that failed on its
        // own unless this line says which one happened.
        LOGGER.warn(
                "bridge is cancelling the client's connection (screen matches: {})",
                activeScreen != null && client.currentScreen == activeScreen);
        if (activeScreen != null && client.currentScreen == activeScreen) {
            synchronized (activeScreen) {
                ConnectScreenAccessor accessor = (ConnectScreenAccessor) activeScreen;
                accessor.minekin$setConnectingCancelled(true);
                ChannelFuture future = accessor.minekin$getFuture();
                if (future != null) {
                    future.cancel(true);
                    accessor.minekin$setFuture(null);
                }
                ClientConnection connection = accessor.minekin$getConnection();
                if (connection != null) {
                    connection.disconnect(ConnectScreen.ABORTED_TEXT);
                }
            }
            client.setScreen(parentScreen);
            return;
        }
        if (client.getNetworkHandler() != null) {
            client.getNetworkHandler().getConnection().disconnect(ConnectScreen.ABORTED_TEXT);
        }
        if (parentScreen != null) {
            client.disconnect(parentScreen);
        }
    }

    private static ServerInfo.ResourcePackPolicy resourcePackPolicy(ResourcePackPolicy policy) {
        return switch (policy) {
            case RESOURCE_PACK_POLICY_DENY -> ServerInfo.ResourcePackPolicy.DISABLED;
            case RESOURCE_PACK_POLICY_PROMPT -> ServerInfo.ResourcePackPolicy.PROMPT;
            default -> throw new IllegalArgumentException("resource pack policy is not actionable");
        };
    }
}
