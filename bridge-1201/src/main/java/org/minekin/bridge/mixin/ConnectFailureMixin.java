package org.minekin.bridge.mixin;

import com.llamalad7.mixinextras.injector.wrapoperation.Operation;
import com.llamalad7.mixinextras.injector.wrapoperation.WrapOperation;
import com.llamalad7.mixinextras.sugar.Local;
import io.minekin.protocol.v1.AdmissionFailureReason;
import net.minecraft.client.MinecraftClient;
import org.minekin.bridge.runtime.ClientAdmissionController;
import org.minekin.bridge.runtime.ConnectFailure;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.spongepowered.asm.mixin.Mixin;
import org.spongepowered.asm.mixin.injection.At;

/**
 * The connection failures vanilla never tells anyone about.
 *
 * <p>A refusal, an unknown host and a connect timeout all happen before a login
 * handler exists, so every Fabric event this Bridge listens to stays silent for
 * them: measured, a run against a closed port produced no Bridge line at all and
 * the ledger stopped at the phase before negotiation, which reads as a run that
 * went nowhere rather than one whose target was not listening.
 *
 * <p>Three earlier attempts at this are in the record and none of them works. A
 * screen carrying a failure message is built before the connection is attempted,
 * so it reports a failure for a login that then succeeds. The screen's own fields
 * cannot be read — the mixin annotation processor does not locate them. And
 * injecting at the logger call in the connector's catch fails to apply, because
 * that call is inside a lambda and the method containing it has no such call.
 *
 * <p>What is left, and is measured: `run` calls `execute` exactly twice. The first
 * is the path taken when the address does not resolve — vanilla's own resolver
 * returned nothing — and the second is the catch, which is reached for a refused
 * connection, a timeout, and anything else the attempt threw. The exception is
 * still in hand there, which is the whole reason to hook these two calls rather
 * than anything they lead to.
 */
@Mixin(targets = "net.minecraft.client.gui.screen.ConnectScreen$1")
public class ConnectFailureMixin {

    private static final Logger LOGGER = LoggerFactory.getLogger("minekin-bridge");

    /** The host did not resolve, so there was nothing to connect to. */
    @WrapOperation(
            method = "run",
            at =
                    @At(
                            value = "INVOKE",
                            target =
                                    "Lnet/minecraft/client/MinecraftClient;execute(Ljava/lang/Runnable;)V",
                            ordinal = 0))
    private void minekin$observeUnresolvedHost(
            MinecraftClient client, Runnable task, Operation<Void> original) {
        remember(AdmissionFailureReason.ADMISSION_FAILURE_REASON_DNS_FAILED, "unresolved address");
        original.call(client, task);
    }

    /** The connection was attempted and threw, before vanilla shows its screen. */
    @WrapOperation(
            method = "run",
            at =
                    @At(
                            value = "INVOKE",
                            target =
                                    "Lnet/minecraft/client/MinecraftClient;execute(Ljava/lang/Runnable;)V",
                            ordinal = 1))
    private void minekin$observeFailedConnect(
            MinecraftClient client,
            Runnable task,
            Operation<Void> original,
            @Local(ordinal = 0) Exception failure) {
        remember(
                ConnectFailure.classify(failure),
                failure == null ? "" : String.valueOf(failure.getMessage()));
        original.call(client, task);
    }

    private static void remember(AdmissionFailureReason reason, String said) {
        // Logged here, where the sentence is still in hand, and never reported: a
        // stable category is what the ledger takes.
        LOGGER.info("bridge observed a failed connection: {} ({})", said, reason);
        ClientAdmissionController.rememberConnectFailure(reason);
    }

}
