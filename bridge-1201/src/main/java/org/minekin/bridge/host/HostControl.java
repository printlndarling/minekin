package org.minekin.bridge.host;

import net.minecraft.client.MinecraftClient;

/**
 * What the rest of the Bridge is allowed to ask the host adapter.
 *
 * <p>Two calls, and both of them touch a client. Everything else about publishing a
 * world — when to ask for it, what to do while there is nothing to publish yet, what
 * to report — is decided where it can be decided without Minecraft, and this is the
 * seam that keeps it that way.
 */
public interface HostControl {

    /** Whether this client is in a world it hosts, and so has something to publish. */
    boolean isHosting(MinecraftClient client);

    /** Publish that world, on {@code requestedPort} or on one the system chooses. */
    LanPublication publish(MinecraftClient client, int requestedPort);
}
