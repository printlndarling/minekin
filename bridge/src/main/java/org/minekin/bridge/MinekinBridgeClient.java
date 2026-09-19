package org.minekin.bridge;

import java.nio.file.Path;
import java.time.Duration;
import net.fabricmc.api.ClientModInitializer;
import net.fabricmc.fabric.api.client.event.lifecycle.v1.ClientLifecycleEvents;
import net.fabricmc.fabric.api.client.event.lifecycle.v1.ClientTickEvents;
import org.minekin.bridge.runtime.BridgeIpcWorker;
import org.minekin.bridge.runtime.BridgePhaseMachine;

/** Thin client entrypoint that only registers hooks and starts the daemon IPC worker. */
public final class MinekinBridgeClient implements ClientModInitializer {
    static final String DESCRIPTOR_ENVIRONMENT_VARIABLE = "MINEKIN_BRIDGE_DESCRIPTOR";
    private static final int MAX_NOTICES_PER_TICK = 8;
    private BridgeIpcWorker worker;
    private BridgeIpcWorker.ClientMessage lastMessage;

    @Override
    public void onInitializeClient() {
        if (worker != null) {
            throw new IllegalStateException("Minekin Bridge was initialized more than once");
        }
        String descriptor = System.getenv(DESCRIPTOR_ENVIRONMENT_VARIABLE);
        if (descriptor == null || descriptor.isBlank()) {
            throw new IllegalStateException("Minekin Bridge bootstrap descriptor is not configured");
        }

        BridgeIpcWorker created = new BridgeIpcWorker(
                Path.of(descriptor),
                Duration.ofSeconds(5),
                Duration.ofSeconds(5),
                16,
                new BridgePhaseMachine());
        ClientTickEvents.END_CLIENT_TICK.register(
                client -> created.drainClientMessages(MAX_NOTICES_PER_TICK, this::acceptMessage));
        ClientLifecycleEvents.CLIENT_STOPPING.register(client -> created.close());
        worker = created;
        created.start();
    }

    private void acceptMessage(BridgeIpcWorker.ClientMessage message) {
        // Runs only on the client tick. Admission execution is added after this
        // bounded, typed handoff is verified independently from socket I/O.
        lastMessage = message;
    }
}
