package org.minekin.bridge.mixin;

import net.minecraft.client.network.ClientLoginNetworkHandler;
import net.minecraft.network.DisconnectionInfo;
import net.minecraft.network.packet.s2c.login.LoginDisconnectS2CPacket;
import org.minekin.bridge.runtime.ClientAdmissionController;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.spongepowered.asm.mixin.Mixin;
import org.spongepowered.asm.mixin.injection.At;
import org.spongepowered.asm.mixin.injection.Inject;
import org.spongepowered.asm.mixin.injection.callback.CallbackInfo;

/**
 * Where a failed login says why, and the only place it can be read.
 *
 * <p>Vanilla draws the reason for a failed connection on the {@code
 * DisconnectedScreen} and does not write it to the log, so a client that cannot
 * join fails silently: the session sees a verdict, the server sees nothing, and
 * the reason exists only on a screen nobody is looking at.
 *
 * <p>Two hooks, because they answer different questions. {@code onDisconnect}
 * sees the packet the server actually sent, which is the only source of a
 * *classifiable* reason, and it runs before Fabric's own disconnect event — so
 * the reason is in hand by the time the controller reports the failure.
 * {@code onDisconnected} sees the end of the connection whatever caused it, and
 * carries a reason for a refusal that never reached a server at all. Both log
 * locally: the contract forbids a server's words from entering a product
 * payload, and allows them somewhere local instead.
 */
@Mixin(ClientLoginNetworkHandler.class)
public abstract class LoginDisconnectMixin {
    private static final Logger LOGGER = LoggerFactory.getLogger("minekin-bridge");

    @Inject(method = "onDisconnect", at = @At("HEAD"))
    private void minekin$rememberServerReason(
            LoginDisconnectS2CPacket packet, CallbackInfo callback) {
        String reason = packet.getReason().getString();
        LOGGER.warn("bridge observed a login disconnect from the server: {}", reason);
        ClientAdmissionController.rememberDisconnectReason(reason);
    }

    @Inject(method = "onDisconnected", at = @At("HEAD"))
    private void minekin$recordDisconnectReason(DisconnectionInfo info, CallbackInfo callback) {
        LOGGER.warn("bridge observed a login disconnect: {}", info.reason().getString());
    }
}
