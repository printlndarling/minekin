package org.minekin.bridge.input;

import net.minecraft.client.MinecraftClient;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;

/**
 * The client's own look path, which is the mouse's.
 *
 * <p>{@code changeLookDirection} is what {@code Mouse} calls with a cursor delta,
 * and its scale is its own: 0.15 degrees per cursor unit, read out of the
 * compiled method rather than assumed, because a command that says degrees has to
 * mean degrees. A turn of ninety degrees is therefore sixty cursor units.
 *
 * <p>Going through it — instead of writing yaw and pitch — is what makes the
 * result the client's own: the client clamps pitch to what a player could look
 * at, wraps yaw, and does it on the thread that owns the view.
 */
public final class VanillaViewSink implements ViewSink {

    private static final Logger LOGGER = LoggerFactory.getLogger("minekin-bridge");

    /** Read from `Entity.changeLookDirection`, not guessed. */
    private static final float DEGREES_PER_CURSOR_UNIT = 0.15F;

    @Override
    public void turn(float yawDegrees, float pitchDegrees) {
        MinecraftClient client = MinecraftClient.getInstance();
        if (client == null || client.player == null) {
            LOGGER.warn("bridge could not turn the view because there is no client in a world");
            return;
        }
        if (!client.isOnThread()) {
            throw new IllegalStateException("Minecraft's view may only change on the client thread");
        }
        client.player.changeLookDirection(
                yawDegrees / DEGREES_PER_CURSOR_UNIT, pitchDegrees / DEGREES_PER_CURSOR_UNIT);
        LOGGER.info("bridge turned the view by {} yaw, {} pitch degrees", yawDegrees, pitchDegrees);
    }
}
