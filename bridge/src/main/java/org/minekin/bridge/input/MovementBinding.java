package org.minekin.bridge.input;

import java.util.Optional;
import net.minecraft.client.option.GameOptions;
import net.minecraft.client.option.KeyBinding;

/**
 * The capabilities the Bridge drives, and which vanilla binding each one is.
 *
 * <p>The Bridge drives the client's own bindings rather than synthesising input
 * events: a managed Kin is a player at a keyboard, and the client's view of what
 * is held is the binding's state. Pressing the binding is what makes a movement
 * key held, and it is also what makes releasing it complete — the client already
 * knows how to let go of a key it thinks is down.
 */
public enum MovementBinding {
    FORWARD(BridgeInputController.FORWARD),
    BACK(BridgeInputController.BACK),
    LEFT(BridgeInputController.LEFT),
    RIGHT(BridgeInputController.RIGHT),
    JUMP(BridgeInputController.JUMP),
    SNEAK(BridgeInputController.SNEAK);

    private final String capability;

    MovementBinding(String capability) {
        this.capability = capability;
    }

    public String capability() {
        return capability;
    }

    /** The binding for a capability, or empty when it is not one the Bridge holds. */
    public static Optional<MovementBinding> of(String capability) {
        for (MovementBinding binding : values()) {
            if (binding.capability.equals(capability)) {
                return Optional.of(binding);
            }
        }
        return Optional.empty();
    }

    public KeyBinding select(GameOptions options) {
        return switch (this) {
            case FORWARD -> options.forwardKey;
            case BACK -> options.backKey;
            case LEFT -> options.leftKey;
            case RIGHT -> options.rightKey;
            case JUMP -> options.jumpKey;
            case SNEAK -> options.sneakKey;
        };
    }
}
