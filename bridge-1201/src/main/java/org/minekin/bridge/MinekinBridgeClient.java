package org.minekin.bridge;

import java.nio.file.Path;
import java.time.Duration;
import io.minekin.protocol.v1.CallbackBudgetWindow;
import io.minekin.protocol.v1.WorldObservation;
import net.fabricmc.api.ClientModInitializer;
import net.fabricmc.fabric.api.client.event.lifecycle.v1.ClientLifecycleEvents;
import net.fabricmc.fabric.api.client.event.lifecycle.v1.ClientTickEvents;
import net.fabricmc.fabric.api.client.networking.v1.ClientLoginConnectionEvents;
import net.fabricmc.fabric.api.client.networking.v1.ClientPlayConnectionEvents;
import net.minecraft.client.MinecraftClient;
import net.minecraft.client.gui.screen.DeathScreen;
import net.minecraft.client.gui.screen.GameMenuScreen;
import net.minecraft.client.gui.screen.Screen;
import net.minecraft.client.gui.screen.TitleScreen;
import net.minecraft.client.gui.screen.ConnectScreen;
import org.minekin.bridge.action.WorldActionController;
import org.minekin.bridge.action.WorldActions;
import org.minekin.bridge.input.BridgeInputController;
import org.minekin.bridge.input.VanillaKeySink;
import org.minekin.bridge.input.VanillaViewSink;
import org.minekin.bridge.protocol.HandshakeGate;
import org.minekin.bridge.runtime.BridgeIpcWorker;
import org.minekin.bridge.runtime.BridgeMetrics;
import org.minekin.bridge.runtime.BridgePhaseMachine;
import org.minekin.bridge.runtime.ClientAdmissionController;
import org.minekin.bridge.runtime.ClientRuntimeIdentity;
import org.minekin.bridge.runtime.HostController;
import org.minekin.bridge.runtime.WorldObservationCollector;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;

/** Thin client entrypoint that only registers hooks and starts the daemon IPC worker. */
public final class MinekinBridgeClient implements ClientModInitializer {
    static final String DESCRIPTOR_ENVIRONMENT_VARIABLE = "MINEKIN_BRIDGE_DESCRIPTOR";
    private static final Logger LOGGER = LoggerFactory.getLogger("minekin-bridge");
    private static final int MAX_NOTICES_PER_TICK = 8;
    private BridgeIpcWorker worker;
    private ClientAdmissionController admission;
    /**
     * Ticks counted toward the next {@code WorldObservation}.
     *
     * <p>A field on the single client instance rather than a local: the observation is a
     * recurring action tied to the client's own clock, and there is exactly one client tick
     * driving it, so no synchronisation is needed and the cadence simply walks down every tick
     * it is spent in a world. Reset while the client is not in one, so a rejoin publishes
     * promptly rather than waiting out a countdown held against a world that was gone.
     */
    private int observationTicksElapsed;

    @Override
    public void onInitializeClient() {
        if (worker != null) {
            throw new IllegalStateException("Minekin Bridge was initialized more than once");
        }
        String descriptor = System.getenv(DESCRIPTOR_ENVIRONMENT_VARIABLE);
        if (descriptor == null || descriptor.isBlank()) {
            throw new IllegalStateException("Minekin Bridge bootstrap descriptor is not configured");
        }

        BridgePhaseMachine phases = new BridgePhaseMachine();
        VanillaKeySink keySink = new VanillaKeySink();
        BridgeIpcWorker created = new BridgeIpcWorker(
                Path.of(descriptor),
                ClientRuntimeIdentity.current(),
                Duration.ofSeconds(5),
                Duration.ofSeconds(5),
                16,
                phases,
                keySink,
                new VanillaViewSink());
        // The S2 actions are applied through the same client bindings the movement path uses,
        // so they are wired to one key sink rather than a second one — pressing the inventory
        // key and holding the attack key are the same vanilla state the movement keys write.
        // Attached before start so no command can be drained before the Minecraft seam exists.
        created.attachWorldView(new WorldActionController(keySink));
        ClientAdmissionController controller = new ClientAdmissionController(
                phases, created::publishLifecycle, created::publishObservation);
        HostController hostController = new HostController(created::publishHostLifecycle);
        // The budget's subject is this callback, so its clock brackets the callback
        // and nothing else. Constructed here rather than reached for globally because
        // it is per-client: two clients in one JVM would be two budgets, and there is
        // one.
        BridgeMetrics metrics = BridgeMetrics.withDefaults();
        ClientTickEvents.END_CLIENT_TICK.register(
                client -> {
                    long tickOpenedAtNanos = System.nanoTime();
                    created.drainClientMessages(
                            MAX_NOTICES_PER_TICK,
                            message -> {
                                try {
                                    if (!created.handleInputMessage(message)
                                            && !hostController.handle(client, message)) {
                                        controller.handle(client, message);
                                    }
                                } catch (RuntimeException error) {
                                    // Named, and the message named with it: this is the one
                                    // fault path on the tick that reads a command rather than
                                    // the world, so a stopped client with no cause here is a
                                    // run that cannot say which command it was holding. The
                                    // variant's own class name is the command — the inbox
                                    // carries the sealed ClientMessage set, not a wire enum.
                                    LOGGER.error(
                                            "bridge fault while handling {} from Core",
                                            message.getClass().getSimpleName(),
                                            error);
                                    stopSafely(
                                            client,
                                            controller,
                                            created,
                                            BridgeInputController.ReleaseReason.BRIDGE_FAULT,
                                            error);
                                }
                            });
                    // A command to publish a world that had none when it arrived is
                    // waiting for one; this is the tick it finds out. The same tick that
                    // drains the inbox, so the order commands arrived in is the order
                    // they are acted on.
                    // A connection that arrived while the client was still starting waits
                    // here for the tick that it is loaded enough to begin.
                    try {
                        controller.tickConnect(client);
                    } catch (RuntimeException error) {
                        LOGGER.error("bridge could not begin a held connection", error);
                        stopSafely(
                                client,
                                controller,
                                created,
                                BridgeInputController.ReleaseReason.BRIDGE_FAULT,
                                error);
                    }
                    try {
                        hostController.tick(client);
                    } catch (RuntimeException error) {
                        // Said out loud before stopping: the fault path logs the reason
                        // it stopped and not the cause, and this one cost a whole run's
                        // worth of guessing. The exception that stops a client is the
                        // most useful line in its log.
                        LOGGER.error("bridge could not ask the client to publish its world", error);
                        stopSafely(
                                client,
                                controller,
                                created,
                                BridgeInputController.ReleaseReason.BRIDGE_FAULT,
                                error);
                    }
                    // The input watchdog's clock. Ticking it from the client thread is the
                    // whole reason it exists beside the heartbeat loop: that loop cannot
                    // notice its own thread being wedged, and this can.
                    try {
                        created.tickInput();
                    } catch (RuntimeException error) {
                        stopSafely(
                                client,
                                controller,
                                created,
                                BridgeInputController.ReleaseReason.BRIDGE_FAULT,
                                error);
                    }
                    // Who owns the keyboard. §12 makes this a release trigger, and
                    // the client tick is where it is observable — nothing else in the
                    // Bridge can see that vanilla has handed the keyboard to a screen,
                    // which is also how the death screen and the title screen arrive.
                    try {
                        created.observeClientInput(screenLabel(client.currentScreen));
                    } catch (RuntimeException error) {
                        stopSafely(
                                client,
                                controller,
                                created,
                                BridgeInputController.ReleaseReason.BRIDGE_FAULT,
                                error);
                    }
                    // Finish pending connection failures and login failures on the
                    // client tick. The latter waits for vanilla's reason callback,
                    // which can arrive after Fabric's network-thread disconnect event.
                    try {
                        controller.reportPendingConnectFailure();
                        controller.reportPendingLoginFailure();
                    } catch (RuntimeException error) {
                        stopSafely(
                                client,
                                controller,
                                created,
                                BridgeInputController.ReleaseReason.BRIDGE_FAULT,
                                error);
                    }
                    // The first snapshot's clock, and it is a tick rather than the join
                    // event on purpose: the join is reported before the server's world
                    // has reached the client, so the snapshot is taken on the first tick
                    // the client is actually in control. See the method.
                    try {
                        controller.collectSnapshotWhenPlayable(client);
                    } catch (RuntimeException error) {
                        stopSafely(
                                client,
                                controller,
                                created,
                                BridgeInputController.ReleaseReason.BRIDGE_FAULT,
                                error);
                    }
                    // The recurring player-equivalent view: what this client can honestly
                    // say about itself right now. Published on a fixed tick cadence and only
                    // while a Core session holds observe.world.v1, so its cost is a constant of
                    // the build and not how urgently the other side asks. It reads the world on
                    // this thread because every value in it is client-thread state.
                    try {
                        publishWorldObservation(client, created);
                    } catch (RuntimeException error) {
                        stopSafely(
                                client,
                                controller,
                                created,
                                BridgeInputController.ReleaseReason.BRIDGE_FAULT,
                                error);
                    }
                    // Last, so the recorded cost is the whole callback: this is what
                    // the mod adds to the client's frame, and taking it anywhere else
                    // would be measuring part of the work and reporting it as all of
                    // it. Nothing below this line may be added without moving it.
                    recordTickCost(created, metrics, tickOpenedAtNanos);
                });
        ClientLifecycleEvents.CLIENT_STOPPING.register(client -> stopSafely(
                client, controller, created, BridgeInputController.ReleaseReason.SHUTDOWN));

        // The phases only the client can observe. Until these existed the Bridge
        // reported RESOLVING when it asked vanilla to connect and nothing else, so
        // a join that really happened looked exactly like a connection that never
        // got anywhere.
        //
        // Every one of them can fire for a server this Bridge never named, which
        // is why each report is dropped unless a generation of ours is active.
        // Each is also wrapped: an exception thrown into vanilla's event dispatch
        // would come out of the packet handler, so a fault here stops the Bridge
        // the same way a fault on the tick does.
        ClientLoginConnectionEvents.INIT.register((handler, client) -> observe(
                client, controller, created, () -> controller.loginNegotiating(handler)));
        ClientLoginConnectionEvents.DISCONNECT.register((handler, client) -> observe(
                client, controller, created, () -> controller.loginFailurePending(handler)));
        ClientPlayConnectionEvents.INIT.register((handler, client) -> observe(
                client, controller, created, controller::playInit));
        ClientPlayConnectionEvents.JOIN.register((handler, sender, client) -> observe(
                client,
                controller,
                created,
                // The join arms the snapshot, which the tick above then takes: it is
                // what Core admits to make the session playable, and it cannot be
                // taken here because the server's world has not reached the client.
                controller::joinSeen));
        ClientPlayConnectionEvents.DISCONNECT.register((handler, client) -> observe(
                client,
                controller,
                created,
                () -> {
                    // Dispatched to the client thread rather than done here: a play
                    // disconnect arrives on the network thread, and the keys belong to
                    // the client. Measured — releasing inline threw
                    // "Minecraft input may only change on the client thread", which the
                    // sink's guard turned into a Bridge fault and a stopped client, on
                    // the one path that exists to let go of the keys.
                    //
                    // Released before the report rather than after it, and named for
                    // what happened: the title screen vanilla shows next would otherwise
                    // be what an operator reads as the cause, which is a true fact about
                    // the keyboard standing in for the fact about the session.
                    client.execute(() -> created.releaseInputsOnClientThread(
                            BridgeInputController.ReleaseReason.LEFT_PLAYABLE, "PLAY_ENDED"));
                    controller.playEnded();
                }));

        admission = controller;
        worker = created;
        created.start();
    }

    /**
     * Publishes one {@code WorldObservation} every {@code WORLD_OBSERVATION_INTERVAL_TICKS}
     * ticks, and only while the session warrants it.
     *
     * <p>Two gates, both cheap and both honest. The capability gate asks the worker whether
     * Core negotiated {@code observe.world.v1} for this session — observation is read-only and
     * switches apart from every action surface, so a session that never asked for it never
     * pays for it. The world gate asks whether the client actually has a player and a level:
     * the Bridge's phase machine has no PLAYABLE reached on the client side yet, so what a Kin
     * may observe is grounded in the one fact that is a real read — a client that is in a world
     * can describe itself, and one that is not sends nothing rather than a snapshot of zeroes.
     *
     * <p>Collecting can fail to describe the client at all (the world went away between the
     * gate and the read); that is a dropped frame, not a fault, and the collector returns null
     * for it. A collection that throws is a Bridge bug and stops the client like every other
     * throw on this tick.
     */
    private void publishWorldObservation(MinecraftClient client, BridgeIpcWorker worker) {
        if (!worker.hasCapability(HandshakeGate.OBSERVE_WORLD_CAPABILITY)) {
            return;
        }
        if (client.player == null || client.world == null) {
            observationTicksElapsed = WorldActions.WORLD_OBSERVATION_INTERVAL_TICKS;
            return;
        }
        if (observationTicksElapsed < WorldActions.WORLD_OBSERVATION_INTERVAL_TICKS) {
            observationTicksElapsed++;
            return;
        }
        observationTicksElapsed = 0;
        WorldObservation observation =
                WorldObservationCollector.collect(client, worker.sessionGeneration());
        if (observation != null) {
            worker.publishWorldObservation(observation);
        }
    }

    /**
     * What the Bridge can say about the screen that has the keyboard, if any.

     * <p>Not the class's own name. A production client's Minecraft classes are
     * intermediary at runtime, so `getClass().getSimpleName()` is `class_418` for
     * the death screen — a token that means nothing to a reader and is a different
     * string in every version. Measured, and the reason this exists.

     * <p>So the Bridge names the screens it can prove it is looking at and says no
     * more than that about anything else. It is a label for a local log line:
     * which screen it is has no bearing on what the Bridge does, which is to let go
     * of every key.
     */
    static String screenLabel(Screen screen) {
        if (screen == null) {
            return "";
        }
        if (screen instanceof DeathScreen) {
            return "DeathScreen";
        }
        if (screen instanceof GameMenuScreen) {
            return "GameMenuScreen";
        }
        if (screen instanceof TitleScreen) {
            return "TitleScreen";
        }
        if (screen instanceof ConnectScreen) {
            return "ConnectScreen";
        }
        return "SomeScreen";
    }

    private static void observe(
            MinecraftClient client,
            ClientAdmissionController controller,
            BridgeIpcWorker worker,
            Runnable report) {
        try {
            report.run();
        } catch (RuntimeException error) {
            // Named rather than swallowed: this wrapper is what turns a fault in a
            // listener into a stopped client, and a stopped client with no cause
            // recorded is the failure mode every diagnostic in this file exists
            // for. The exception is the cause.
            LOGGER.error("bridge fault while handling a client event", error);
            stopSafely(client, controller, worker, BridgeInputController.ReleaseReason.BRIDGE_FAULT);
        }
    }

    /**
     * The largest sample the wire can carry, in microseconds.
     *
     * <p>{@code uint32} microseconds is about seventy-one minutes, and a tick that
     * long cannot happen in a process that is still running. The clamp is here rather
     * than left to protobuf because the alternative on this path is an exception
     * thrown from the client tick, which stops the client — the sampler becoming the
     * fault it exists to measure. A sample already at this ceiling is a fact about the
     * run that dwarfs anything a distribution of it could add.
     */
    private static final long MAX_SAMPLE_MICROS = 0xFFFFFFFFL;

    /**
     * Records the cost of one client-tick callback, and publishes any window it closed.
     *
     * <p>Publishing is best-effort and deliberately cannot stop the client: a window
     * the outbox had no room for is dropped by the worker, which logs it, and the gap
     * it leaves in the window numbers is how a reader sees that it happened.
     *
     * <p>The window's samples are read out here, on the tick that closes it, rather
     * than per tick: {@code record} is the allocation-free half and this is the half
     * that builds a message, so a window every ten seconds means a message every ten
     * seconds and no garbage at twenty ticks a second.
     */
    private static void recordTickCost(
            BridgeIpcWorker worker, BridgeMetrics metrics, long tickOpenedAtNanos) {
        if (!metrics.recordTick(System.nanoTime() - tickOpenedAtNanos, tickOpenedAtNanos)) {
            return;
        }
        for (BridgeMetrics.Snapshot snapshot : metrics.takeWindows()) {
            worker.publishBudgetWindow(budgetWindow(snapshot));
        }
    }

    /**
     * One series' window, as the wire spells it.
     *
     * <p>The cast is protobuf's own unsigned encoding — a {@code uint32} accessor takes
     * an {@code int} and the bits are the value — so the ceiling survives the round
     * trip as the number it is rather than as a negative one.
     */
    private static CallbackBudgetWindow budgetWindow(BridgeMetrics.Snapshot snapshot) {
        CallbackBudgetWindow.Builder window =
                CallbackBudgetWindow.newBuilder()
                        .setLabel(snapshot.label())
                        .setWindow(snapshot.window())
                        .setOpenedAtNanos(snapshot.openedAtNanos())
                        .setRecorded(snapshot.recorded());
        for (long nanos : snapshot.nanos()) {
            window.addMicros((int) Math.min(nanos / 1_000L, MAX_SAMPLE_MICROS));
        }
        return window.build();
    }

    private static void stopSafely(
            MinecraftClient client,
            ClientAdmissionController controller,
            BridgeIpcWorker worker,
            BridgeInputController.ReleaseReason reason) {
        stopSafely(client, controller, worker, reason, null);
    }

    private static void stopSafely(
            MinecraftClient client,
            ClientAdmissionController controller,
            BridgeIpcWorker worker,
            BridgeInputController.ReleaseReason reason,
            RuntimeException error) {
        // Logged because this is the Bridge stopping the client, and a client
        // that simply stops with no cause recorded anywhere is unreadable: the
        // server it was talking to sees a connection that went away, and the
        // session sees a verdict rather than a reason.
        //
        // The cause is logged with it, and that is the whole point of the
        // overload. Every wrapped site on the tick passes the exception it
        // caught into a signature that then dropped it, which is how runs
        // stopped at the same millisecond after the join with nothing in either
        // log but the reason enum: the informative half of the fault was in hand
        // at the call site and thrown away here.
        if (error == null) {
            LOGGER.error("bridge is stopping the client: {}", reason);
        } else {
            LOGGER.error("bridge is stopping the client: {}", reason, error);
        }
        try {
            controller.safeStop(client);
        } finally {
            try {
                worker.releaseInputsOnClientThread(reason, "");
            } finally {
                worker.close();
            }
        }
    }
}
