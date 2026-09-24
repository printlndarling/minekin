package org.minekin.bridge.mixin;

import net.minecraft.client.network.ClientPlayNetworkHandler;
import net.minecraft.network.packet.s2c.play.DisconnectS2CPacket;
import org.minekin.bridge.runtime.ClientAdmissionController;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.spongepowered.asm.mixin.Mixin;
import org.spongepowered.asm.mixin.injection.At;
import org.spongepowered.asm.mixin.injection.Inject;
import org.spongepowered.asm.mixin.injection.callback.CallbackInfo;

/**
 * A session the server ended, and the reason it gave for ending it.
 *
 * <p>The rule this exists for: a disconnect *without* a reason is a session that
 * ended, and a disconnect *with* one is a session the server ended. Vanilla
 * sends this packet for the second — measured, it is how a duplicate login is
 * delivered: `You logged in from another location` arrives mid-session, after
 * the client is already in the world. Without this hook the Bridge saw only the
 * connection going away, reported `DISCONNECTED` with no reason, and recorded a
 * session the server threw out as one that simply stopped.
 *
 * <p>Bound to the play handler, which in 1.20.1 declares `onDisconnect` itself
 * (measured against the 1.20.1 mappings jar; there is no common network handler
 * at this version). The reason is known here before Fabric's disconnect event
 * fires.
 */
@Mixin(ClientPlayNetworkHandler.class)
public abstract class CommonDisconnectMixin {
    private static final Logger LOGGER = LoggerFactory.getLogger("minekin-bridge");

    @Inject(method = "onDisconnect", at = @At("HEAD"))
    private void minekin$rememberKick(DisconnectS2CPacket packet, CallbackInfo callback) {
        String reason = packet.getReason().getString();
        LOGGER.warn("bridge observed a disconnect from the server: {}", reason);
        ClientAdmissionController.rememberDisconnectReason(reason);
    }
}
