package org.minekin.bridge;

import java.nio.file.Path;
import java.time.Duration;
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
import net.minecraft.client.gui.screen.multiplayer.ConnectScreen;
import org.minekin.bridge.input.BridgeInputController;
import org.minekin.bridge.input.VanillaKeySink;
import org.minekin.bridge.input.VanillaViewSink;
import org.minekin.bridge.runtime.BridgeIpcWorker;
import org.minekin.bridge.runtime.BridgePhaseMachine;
import org.minekin.bridge.runtime.ClientAdmissionController;
import org.minekin.bridge.runtime.HostController;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;

/** Thin client entrypoint that only registers hooks and starts the daemon IPC worker. */
public final class MinekinBridgeClient implements ClientModInitializer {
    static final String DESCRIPTOR_ENVIRONMENT_VARIABLE = "MINEKIN_BRIDGE_DESCRIPTOR";
    private static final Logger LOGGER = LoggerFactory.getLogger("minekin-bridge");
    private static final int MAX_NOTICES_PER_TICK = 8;
    private BridgeIpcWorker worker;
    private ClientAdmissionController admission;

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
        BridgeIpcWorker created = new BridgeIpcWorker(
                Path.of(descriptor),
                Duration.ofSeconds(5),
                Duration.ofSeconds(5),
                16,
                phases,
                new VanillaKeySink(),
                new VanillaViewSink());
        ClientAdmissionController controller = new ClientAdmissionController(
                phases, created::publishLifecycle, created::publishObservation);
        HostController hostController = new HostController(created::publishHostLifecycle);
        ClientTickEvents.END_CLIENT_TICK.register(
                client -> {
                    created.drainClientMessages(
                            MAX_NOTICES_PER_TICK,
                            message -> {
                                try {
                                    if (!created.handleInputMessage(message)
                                            && !hostController.handle(client, message)) {
                                        controller.handle(client, message);
                                    }
                                } catch (RuntimeException error) {
                                    stopSafely(
                                            client,
                                            controller,
                                            created,
                                            BridgeInputController.ReleaseReason.BRIDGE_FAULT);
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
                                BridgeInputController.ReleaseReason.BRIDGE_FAULT);
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
                                BridgeInputController.ReleaseReason.BRIDGE_FAULT);
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
                                BridgeInputController.ReleaseReason.BRIDGE_FAULT);
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
                                BridgeInputController.ReleaseReason.BRIDGE_FAULT);
                    }
                    // A connection the client gave up on, classified on the thread
                    // that caught it. Nothing else fires for one: the failure happens
                    // before a login handler exists.
                    try {
                        controller.reportPendingConnectFailure();
                    } catch (RuntimeException error) {
                        stopSafely(
                                client,
                                controller,
                                created,
                                BridgeInputController.ReleaseReason.BRIDGE_FAULT);
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
                                BridgeInputController.ReleaseReason.BRIDGE_FAULT);
                    }
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
                client, controller, created, controller::loginNegotiating));
        ClientLoginConnectionEvents.DISCONNECT.register((handler, client) -> observe(
                client, controller, created, controller::loginFailed));
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

    private static void stopSafely(
            MinecraftClient client,
            ClientAdmissionController controller,
            BridgeIpcWorker worker,
            BridgeInputController.ReleaseReason reason) {
        // Logged because this is the Bridge stopping the client, and a client
        // that simply stops with no cause recorded anywhere is unreadable: the
        // server it was talking to sees a connection that went away, and the
        // session sees a verdict rather than a reason.
        LOGGER.error("bridge is stopping the client: {}", reason);
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
