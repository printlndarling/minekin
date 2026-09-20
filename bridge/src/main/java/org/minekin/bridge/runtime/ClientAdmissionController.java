package org.minekin.bridge.runtime;

import io.minekin.protocol.v1.ConnectWorld;
import io.minekin.protocol.v1.AdmissionFailureReason;
import io.minekin.protocol.v1.ConnectionLifecycle;
import io.minekin.protocol.v1.ConnectionPhase;
import io.minekin.protocol.v1.InitialObservation;
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
    private final Predicate<InitialObservation> observationSink;
    private long activeGeneration;
    private String activeProfileId;
    private String activeProfileRevision;
    private ConnectScreen activeScreen;
    private Screen parentScreen;
    private boolean snapshotPending;
    /**
     * A connection this Bridge was asked for while the client was still starting.
     *
     * <p>Held rather than refused, and started on the first tick the client is loaded
     * enough for it — the same shape as the snapshot deferral below, and for the same
     * reason: what is missing is not permission but readiness, and the caller's own
     * deadline is what bounds the wait.
     */
    private ConnectWorld pendingConnect;
    private int ticksSinceJoin;
    private int lastProbeCount = -1;

    /**
     * How long the first snapshot waits for vanilla to say the client is in control.
     *
     * <p>Bounded so that a client whose screen never clears still produces a
     * snapshot: a session that never becomes playable because the Bridge is
     * waiting for a condition that will not arrive is worse than a snapshot taken
     * of a client that is still loading.
     */
    static final int SNAPSHOT_DEFERRAL_LIMIT_TICKS = 100;

    private final Predicate<MinecraftClient> readyToConnect;

    public ClientAdmissionController(
            BridgePhaseMachine phases,
            Predicate<ConnectionLifecycle> lifecycleSink,
            Predicate<InitialObservation> observationSink) {
        this(phases, lifecycleSink, observationSink, ClientAdmissionController::clientIsLoaded);
    }

    /**
     * The same, with the client-readiness question supplied.
     *
     * <p>Asking it reads Minecraft, and everything decided around it does not, which is
     * why it is a seam: the rule this holds — a command that arrives before the client
     * is ready waits instead of failing — can then be tested without a client.
     */
    public ClientAdmissionController(
            BridgePhaseMachine phases,
            Predicate<ConnectionLifecycle> lifecycleSink,
            Predicate<InitialObservation> observationSink,
            Predicate<MinecraftClient> readyToConnect) {
        this.phases = java.util.Objects.requireNonNull(phases, "phases");
        this.lifecycleSink = java.util.Objects.requireNonNull(lifecycleSink, "lifecycleSink");
        this.observationSink = java.util.Objects.requireNonNull(observationSink, "observationSink");
        this.readyToConnect = java.util.Objects.requireNonNull(readyToConnect, "readyToConnect");
    }

    /**
     * Whether the client has finished starting up.
     *
     * <p>A client with no screen is a client that is still loading: vanilla installs the
     * title screen when it is done, and until then there is nothing for a connection to
     * belong to. Measured: a join attempt made in that window reached the *other*
     * client's server — which logged the incoming player by name — and then the socket
     * closed with no reason on either side, which is what the client does to a
     * connection whose screen is replaced under it.
     */
    static boolean clientIsLoaded(MinecraftClient client) {
        // Vanilla's own word for it, rather than a predicate assembled from two
        // accessors: a client whose resources are still loading is a client that cannot
        // yet have a connection. Measured the hard way — a first attempt at this tested
        // `currentScreen != null`, which is already true during the load, so the hold
        // never fired and the failure looked unchanged.
        return client.isFinishedLoading();
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
        // A join is not the moment to take the snapshot, it is the moment to start
        // waiting for one — see collectSnapshotWhenPlayable. Armed only for a
        // generation of ours, on the same rule as the report above.
        if (activeGeneration != 0) {
            snapshotPending = true;
            ticksSinceJoin = 0;
            lastProbeCount = -1;
        }
    }

    /**
     * Take the first snapshot, once vanilla says the client is in control of the world.
     *
     * <p>Called every client tick, and does nothing until a join has armed it.
     *
     * <p>Not at the join, which is what this used to be and what a run showed to be
     * wrong. `JOIN_SEEN` is reported from the game-join packet, and the server's
     * entity-tracker packets for the world around the player arrive after it: a
     * snapshot taken there reported an empty visible world for a world that
     * contained a summoned pig. The counts were true about the client and false
     * about the world, which is the one thing a snapshot may not be.
     *
     * <p>So it waits for vanilla's own signal instead: no screen up, which is the
     * terrain-download screen having been dismissed, which happens when the
     * player's own spawn packet has been processed. The entity packets travel in
     * the same batch.
     *
     * <p>Every value in a snapshot is client-thread state, so this runs on that
     * thread. The generation is read here rather than passed in: only this
     * controller knows which attempt is current, and a snapshot attributed to the
     * wrong generation is one Core must refuse. A client that cannot honestly
     * describe itself sends nothing and the session stays joined, which the run
     * reports; it is not a reason to stop a client that is otherwise running.
     */
    public void collectSnapshotWhenPlayable(MinecraftClient client) {
        if (!snapshotPending) {
            return;
        }
        if (activeGeneration == 0) {
            snapshotPending = false;
            return;
        }
        if (client.world == null || client.player == null) {
            return;
        }
        ticksSinceJoin++;
        // Logged on change rather than per tick: this is the line that says whether
        // the world had anything in it and when the client learned of it, and a
        // line per tick would say the same thing unreadably.
        int candidates = ClientSnapshot.entityCandidates(client);
        if (candidates != lastProbeCount) {
            lastProbeCount = candidates;
            LOGGER.info(
                    "bridge knows of {} entity candidate(s) {} tick(s) after joining",
                    candidates,
                    ticksSinceJoin);
        }
        Screen screen = client.currentScreen;
        if (screen != null && ticksSinceJoin < SNAPSHOT_DEFERRAL_LIMIT_TICKS) {
            return;
        }
        if (screen != null) {
            LOGGER.warn(
                    "bridge waited {} ticks and the client still shows {}; taking the snapshot anyway",
                    ticksSinceJoin,
                    screen.getClass().getSimpleName());
        }
        snapshotPending = false;
        InitialObservation snapshot = ClientSnapshot.collect(client, activeGeneration);
        if (snapshot == null) {
            LOGGER.warn("bridge could not describe itself, so no first snapshot was sent");
            return;
        }
        if (!observationSink.test(snapshot)) {
            LOGGER.warn("bridge could not hand the first snapshot to the worker");
        }
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
        AdmissionFailureReason reason = classifyDisconnect(takeDisconnectReason());
        LOGGER.info("bridge classified the login failure as {}", reason);
        report(ConnectionPhase.CONNECTION_PHASE_FAILED, reason, true);
    }

    /**
     * The reason a server gave for ending a connection, held between the packet
     * that carried it and the report that classifies it.
     *
     * <p>Static because the two halves that meet here cannot see each other: a
     * mixin has no instance to hold, and the controller is per client — and
     * there is exactly one client per process, which the mod already enforces by
     * refusing to initialize twice. It is cleared as it is read, so a reason
     * from one attempt can never be classified against the next.
     */
    private static volatile String pendingDisconnectReason = "";

    public static void rememberDisconnectReason(String reason) {
        pendingDisconnectReason = reason == null ? "" : reason;
    }

    private static String takeDisconnectReason() {
        String reason = pendingDisconnectReason;
        pendingDisconnectReason = "";
        return reason;
    }

    /**
     * The stable classification for a connection a server ended.
     *
     * <p>The server's own words are the only thing that tells a whitelist
     * rejection apart from an authentication mismatch, or a duplicate login from
     * a session that simply ended — the protocol carries a sentence, not a code
     * — so this matches the sentences a *vanilla* server sends and nothing more.
     * A reason it does not recognise stays UNEXPECTED_DISCONNECT rather than
     * being forced into a category: a wrong category is worse evidence than an
     * honest "unclassified", because it is a claim about the server that nobody
     * made.
     */
    static AdmissionFailureReason classifyDisconnect(String reason) {
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

    /**
     * A connection the client could not make, between the thread that caught it and
     * the tick that reports it.
     *
     * <p>The connector thread has the exception and the client thread owns every
     * report, so the reason travels between them the way a disconnect reason does.
     * Null means nothing is waiting.
     */
    private static volatile AdmissionFailureReason pendingConnectFailure;

    public static void rememberConnectFailure(AdmissionFailureReason reason) {
        pendingConnectFailure = reason;
    }

    /**
     * Report a connection the client gave up on, if one is waiting.
     *
     * <p>Called from the client tick, because nothing else fires: the failure
     * happens before a login handler exists, so the events the other reports come
     * from never happen at all.
     */
    public void reportPendingConnectFailure() {
        AdmissionFailureReason reason = pendingConnectFailure;
        pendingConnectFailure = null;
        if (reason == null) {
            return;
        }
        LOGGER.info("bridge classified the connection failure as {}", reason);
        report(ConnectionPhase.CONNECTION_PHASE_FAILED, reason, true);
    }

    /**
     * The play session ended.
             *
     * <p>Two different events look identical from here, and what tells them
     * apart is whether the server said anything. A session that simply ends is
     * DISCONNECTED and carries no reason, which is the contract's rule. A
     * session the server *ended* arrives as a disconnect packet with its reason
     * — measured, that is how a duplicate login is delivered mid-session — and
     * reporting that as a plain disconnect records a Kin the server threw out
     * as one that stopped on its own. That is the same class of error as
     * inventing a reason: a fact in the evidence that is not what happened.
     */
    public void playEnded() {
        String reason = takeDisconnectReason();
        if (reason.isBlank()) {
            report(
                    ConnectionPhase.CONNECTION_PHASE_DISCONNECTED,
                    AdmissionFailureReason.ADMISSION_FAILURE_REASON_UNSPECIFIED,
                    true);
            return;
        }
        AdmissionFailureReason classified = classifyDisconnect(reason);
        LOGGER.info("bridge classified the disconnect as {}", classified);
        report(ConnectionPhase.CONNECTION_PHASE_FAILED, classified, true);
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
        // A snapshot owed to a generation that has ended is a snapshot of an
        // attempt that is over, and the next one arms its own.
        snapshotPending = false;
        ticksSinceJoin = 0;
        lastProbeCount = -1;
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

        beginGeneration(command);
        pendingConnect = command;
        startWhenReady(client);
    }

    /** One client tick: a held command gets its turn once the client is loaded enough. */
    public void tickConnect(MinecraftClient client) {
        java.util.Objects.requireNonNull(client, "client");
        startWhenReady(client);
    }

    private void startWhenReady(MinecraftClient client) {
        ConnectWorld command = pendingConnect;
        if (command == null || !readyToConnect.test(client)) {
            return;
        }
        pendingConnect = null;
        ServerAddress address = new ServerAddress(command.getOriginalHost(), command.getPort());
        ServerInfo server = new ServerInfo(
                command.getServerProfileId(), address.toString(), ServerInfo.ServerType.OTHER);
        server.setResourcePackPolicy(resourcePackPolicy(command.getResourcePackPolicy()));
        parentScreen = client.currentScreen != null ? client.currentScreen : new TitleScreen();
        LOGGER.info(
                "bridge asked vanilla to connect to {} for generation {} (finishedLoading={}, "
                        + "screen={}, overlay={})",
                address,
                command.getGeneration(),
                client.isFinishedLoading(),
                client.currentScreen == null ? "none" : client.currentScreen.getClass().getSimpleName(),
                client.getOverlay() == null ? "none" : client.getOverlay().getClass().getSimpleName());
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
        pendingConnect = null;
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
