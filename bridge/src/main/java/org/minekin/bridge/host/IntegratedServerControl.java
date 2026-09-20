package org.minekin.bridge.host;

import java.io.IOException;
import java.net.ServerSocket;
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
public final class IntegratedServerControl implements HostControl {

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
    @Override
    public boolean isHosting(MinecraftClient client) {
        if (!client.isOnThread()) {
            throw new IllegalStateException(
                    "whether a client is hosting may only be asked on the client thread");
        }
        IntegratedServer server = client.getServer();
        // Having a server is not the same fact as being in it. Measured in the runner:
        // the integrated server starts at :56 and the player joins at :59, and a
        // publication attempted in between threw inside the client's own call, because
        // that call reads the client's player and the player was still null. The
        // precondition for publishing is a Kin in the world, so that is what is asked.
        return server != null && !server.isRemote() && client.player != null;
    }

    @Override
    public LanPublication publish(MinecraftClient client, int requestedPort) {
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
        // A world that is published authenticates its joiners, and that is vanilla's own
        // choice: `IntegratedServer.setupServer` calls `setOnlineMode(true)` at startup,
        // right before it generates the keypair the encryption uses. Measured twice over
        // — read out of the 1.21.4 bytecode, and then observed: an offline managed client
        // dialling the published port was answered with `Failed to log in: Invalid
        // session`, and the second Kin never arrived.
        //
        // Every other join in this project is offline — the controlled dedicated server
        // builds its properties from the reviewed profile's `auth_mode`, and the P0
        // identity is an offline one — so a world the Kin hosts has to be in the same
        // online-ness as the world a Kin joins, or hosting is a capability only clients
        // with Microsoft accounts can use. This is a lifecycle call on the server, which
        // is exactly what this adapter is for, and it happens before the port is bound
        // so no joiner can arrive under the old mode.
        server.setOnlineMode(false);

        // The port has to be chosen *before* the call, because 1.21.4 offers no way to
        // read the one it bound: `getServerPort()` returns whatever was asked for, and
        // the only address-returning method on the network object (`bindLocal()`)
        // binds a separate local channel rather than reporting where the world is.
        // Measured, after a run that published a world nobody could name: the client
        // logged `Started serving on 0` while the socket was listening somewhere else.
        int port = requestedPort != 0 ? requestedPort : freePort();
        if (port == 0) {
            return refuse(LanRefusal.NO_BOUND_ADDRESS);
        }
        if (!server.openToLan(null, false, port)) {
            // Worth saying out loud: the client catches its own IOException and returns
            // false without logging anything at all, so a bind that failed leaves no
            // trace in its log. This line is the only record it happened.
            return refuse(LanRefusal.BIND_FAILED);
        }
        // Now that the port was named rather than chosen by the system, the server's own
        // answer is the truth: it stores the port it was asked for, and it was asked for
        // this one.
        return server.getServerPort() > 0
                ? LanPublication.published(server.getServerPort())
                : LanPublication.refused(LanRefusal.NO_BOUND_ADDRESS);
    }

    /**
     * A port nothing is using at this moment, as the operating system sees it.
     *
     * <p>Asking and letting go is what every tool does, and the gap between letting go
     * and binding is real: somebody else can take it. That case comes back as a bind
     * failure rather than as a wrong answer, which is the property that matters — this
     * is not a guarantee, it is a choice made honestly in advance.
     */
    static int freePort() {
        try (ServerSocket socket = new ServerSocket(0)) {
            return socket.getLocalPort();
        } catch (IOException error) {
            LOGGER.warn("bridge could not find a free port to publish on", error);
            return 0;
        }
    }

    private static LanPublication refuse(LanRefusal refusal) {
        LOGGER.warn("bridge did not publish this world: {}", refusal);
        return LanPublication.refused(refusal);
    }
}
