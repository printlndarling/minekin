package org.minekin.bridge;

import net.fabricmc.api.ClientModInitializer;

/** Thin client entrypoint. W20 will attach bounded IPC without blocking this callback. */
public final class MinekinBridgeClient implements ClientModInitializer {
    @Override
    public void onInitializeClient() {
        // The W00 scaffold intentionally performs no I/O or game actions.
    }
}
