package org.minekin.bridge;

import java.nio.file.Path;
import java.time.Duration;
import net.fabricmc.api.ClientModInitializer;
import net.fabricmc.fabric.api.client.event.lifecycle.v1.ClientLifecycleEvents;
import net.fabricmc.fabric.api.client.event.lifecycle.v1.ClientTickEvents;
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
                phases);
        ClientAdmissionController controller =
                new ClientAdmissionController(phases, created::publishLifecycle);
        ClientTickEvents.END_CLIENT_TICK.register(
                client -> created.drainClientMessages(
                        MAX_NOTICES_PER_TICK,
                        message -> {
                            try {
                                controller.handle(client, message);
                            } catch (RuntimeException error) {
                                controller.safeStop(client);
                                created.close();
                            }
                        }));
        ClientLifecycleEvents.CLIENT_STOPPING.register(client -> {
            controller.safeStop(client);
            created.close();
        });
        admission = controller;
        worker = created;
        created.start();
    }
}
