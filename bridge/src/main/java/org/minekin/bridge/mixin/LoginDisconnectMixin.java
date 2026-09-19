package org.minekin.bridge.mixin;

import net.minecraft.client.network.ClientLoginNetworkHandler;
import net.minecraft.network.DisconnectionInfo;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.spongepowered.asm.mixin.Mixin;
import org.spongepowered.asm.mixin.injection.At;
import org.spongepowered.asm.mixin.injection.Inject;
import org.spongepowered.asm.mixin.injection.callback.CallbackInfo;

/**
 * The one place a failed login says why.
 *
 * <p>Vanilla draws the reason for a failed connection on the {@code
 * DisconnectedScreen} and does not write it to the log, so a client that cannot
 * join a world fails silently: the session sees a verdict, the server sees
 * nothing, and the reason exists only on a screen nobody is looking at. This is
 * therefore a diagnostic and not an event — the contract forbids a server's
 * words from entering a product payload, and it explicitly allows them somewhere
 * local instead.
 *
 * <p>It is hooked on the login handler rather than on the screen for two
 * reasons: the reason is known here with nothing drawn yet, and this fires for
 * a refusal that never reaches a server at all (the handler is constructed
 * before the socket is opened, so a refused connect lands here too).
 */
@Mixin(ClientLoginNetworkHandler.class)
public abstract class LoginDisconnectMixin {
    private static final Logger LOGGER = LoggerFactory.getLogger("minekin-bridge");

    @Inject(method = "onDisconnected", at = @At("HEAD"))
    private void minekin$recordDisconnectReason(DisconnectionInfo info, CallbackInfo callback) {
        LOGGER.warn("bridge observed a login disconnect: {}", info.reason().getString());
    }
}
