package org.minekin.bridge.input;

import net.minecraft.client.MinecraftClient;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;

/**
 * Presses and releases the client's own movement bindings.
 *
 * <p>Bindings are the client's state, and that state belongs to the client
 * thread. The worker therefore hands input commands to the bounded client-tick
 * inbox before this sink is called. Applying synchronously here keeps the
 * ownership ledger truthful: a returned release has actually lifted the key.
 *
 * <p>This is the only place a key goes down, so it is also the only place that
 * has to be honest about what it did: every change is logged with the capability
 * and the reason, because "the Kin kept walking" is a report that needs a
 * matching line in the log.
 */
public final class VanillaKeySink implements KeySink {

    private static final Logger LOGGER = LoggerFactory.getLogger("minekin-bridge");

    /**
     * The client is looked up per call rather than held: a mod is initialised
     * before there is a client to hold, while every input this sink is asked for
     * arrives after the handshake, by which point there is one. Resolving it here
     * is also what keeps the answer honest — it is the client that is running, not
     * the one that happened to exist when the mod loaded.
     */
    private static MinecraftClient runningClient() {
        return MinecraftClient.getInstance();
    }

    @Override
    public void press(String capability) {
        apply(capability, true);
    }

    @Override
    public void release(String capability) {
        apply(capability, false);
    }

    private void apply(String capability, boolean pressed) {
        MovementBinding.of(capability)
                .ifPresentOrElse(
                        binding -> {
                            MinecraftClient client = runningClient();
                            if (client == null) {
                                LOGGER.warn(
                                        "bridge could not {} {} because the client no longer exists",
                                        pressed ? "press" : "release",
                                        capability);
                                return;
                            }
                            if (!client.isOnThread()) {
                                throw new IllegalStateException(
                                        "Minecraft input may only change on the client thread");
                            }
                            binding.select(client.options).setPressed(pressed);
                            LOGGER.info(
                                    "bridge {} {}", pressed ? "pressed" : "released", capability);
                        },
                        () -> LOGGER.warn(
                                "bridge was asked for an input it does not drive: {}", capability));
    }
}
