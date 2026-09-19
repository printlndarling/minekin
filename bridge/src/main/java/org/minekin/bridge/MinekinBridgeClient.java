package org.minekin.bridge;

import java.nio.file.Path;
import java.time.Duration;
import net.fabricmc.api.ClientModInitializer;
import net.fabricmc.fabric.api.client.event.lifecycle.v1.ClientLifecycleEvents;
import net.fabricmc.fabric.api.client.event.lifecycle.v1.ClientTickEvents;
import net.fabricmc.fabric.api.client.networking.v1.ClientLoginConnectionEvents;
import net.fabricmc.fabric.api.client.networking.v1.ClientPlayConnectionEvents;
import net.minecraft.client.MinecraftClient;
import org.minekin.bridge.input.BridgeInputController;
import org.minekin.bridge.input.VanillaKeySink;
import org.minekin.bridge.runtime.BridgeIpcWorker;
import org.minekin.bridge.runtime.BridgePhaseMachine;
import org.minekin.bridge.runtime.ClientAdmissionController;

/** Thin client entrypoint that only registers hooks and starts the daemon IPC worker. */
public final class MinekinBridgeClient implements ClientModInitializer {
    static final String DESCRIPTOR_ENVIRONMENT_VARIABLE = "MINEKIN_BRIDGE_DESCRIPTOR";
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
                new VanillaKeySink());
        ClientAdmissionController controller =
                new ClientAdmissionController(phases, created::publishLifecycle);
        ClientTickEvents.END_CLIENT_TICK.register(
                client -> {
                    created.drainClientMessages(
                            MAX_NOTICES_PER_TICK,
                            message -> {
                                try {
                                    if (!created.handleInputMessage(message)) {
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
                client, controller, created, controller::joinSeen));
        ClientPlayConnectionEvents.DISCONNECT.register((handler, client) -> observe(
                client, controller, created, controller::playEnded));

        admission = controller;
        worker = created;
        created.start();
    }

    private static void observe(
            MinecraftClient client,
            ClientAdmissionController controller,
            BridgeIpcWorker worker,
            Runnable report) {
        try {
            report.run();
        } catch (RuntimeException error) {
            stopSafely(client, controller, worker, BridgeInputController.ReleaseReason.BRIDGE_FAULT);
        }
    }

    private static void stopSafely(
            MinecraftClient client,
            ClientAdmissionController controller,
            BridgeIpcWorker worker,
            BridgeInputController.ReleaseReason reason) {
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
