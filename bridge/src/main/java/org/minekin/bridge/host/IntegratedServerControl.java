package org.minekin.bridge.host;

import net.minecraft.client.MinecraftClient;
import net.minecraft.server.integrated.IntegratedServer;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;

/**
 * The narrow lifecycle adapter: the one place in the Bridge allowed to touch the
 * integrated server.
 *
 * <p>The host boundary contract gives this package — and only this package — the
 * server lifecycle calls, and gives the reason: the integrated server runs in the same
 * JVM as the client, so the only thing standing between a Kin's perception and the
 * server's own truth is which types may be named where. Everything else in the Bridge
 * is refused {@code getServer()} by {@code tools/check_bridge_host_boundary.py}, which
 * is what this package exists to be the exception to.
 *
 * <p>What it may do is lifecycle and nothing else. It publishes, and it reports
 * whether it published and where; it does not read the world, the players, the chunks
 * or the save, because server truth reaching the product through the module that is
 * allowed to touch the server would be the boundary moving rather than holding.
 *
 * <p>Publishing also grants the host cheats and a permission level — measured: the
 * 1.21.4 method calls {@code setCheatsAllowed} and raises the host player's level.
 * That is authority, and authority is not something a wire message may ask for, so
 * neither is a field of the command: this call passes {@code false} and {@code null}
 * because there is nowhere for anything else to come from. The contract's policy is
 * survival, non-hardcore, normal difficulty and no commands, and a Kin that could
 * publish its world with cheats on would have been handed a way around it.
 */
public final class IntegratedServerControl {

    private static final Logger LOGGER = LoggerFactory.getLogger("minekin-bridge");

    /**
     * Publish the world this client is hosting, on {@code requestedPort} or on one the
     * operating system chooses when it is zero.
     *
     * <p>Client thread only, and it says so by refusing to run anywhere else rather
     * than by hoping: the method it wraps calls into {@link MinecraftClient} three
     * times, and the same rule is already enforced for input in {@code VanillaKeySink}.
     * A caller that wants this from the IPC worker submits it to the client thread,
     * which is what the contract's no-circular-wait rule is about.
     */
    public LanPublication openToLan(MinecraftClient client, int requestedPort) {
        if (!client.isOnThread()) {
            throw new IllegalStateException(
                    "a world may only be published on the client thread");
        }
        IntegratedServer server = client.getServer();
        if (server == null || server.isRemote()) {
            return refuse(LanRefusal.NOT_HOSTING);
        }
        // The parameters are the policy, and they are not on the wire: `null` leaves the
        // world's game mode alone and `false` withholds cheats. Everything that could
        // raise either would have to be a new field, which is a decision for a reviewed
        // change rather than a value that arrives from outside.
        if (!server.openToLan(null, false, requestedPort)) {
            // Worth saying out loud: the client catches its own IOException and returns
            // false without logging anything at all, so a bind that failed leaves no
            // trace in its log. This line is the only record it happened.
            return refuse(LanRefusal.BIND_FAILED);
        }
        return LanPublication.of(server.getNetworkIo().bindLocal());
    }

    private static LanPublication refuse(LanRefusal refusal) {
        LOGGER.warn("bridge did not publish this world: {}", refusal);
        return LanPublication.refused(refusal);
    }
}
