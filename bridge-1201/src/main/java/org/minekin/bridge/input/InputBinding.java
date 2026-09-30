package org.minekin.bridge.input;

import java.util.Optional;
import net.minecraft.client.option.GameOptions;
import net.minecraft.client.option.KeyBinding;

/**
 * The keys the Bridge may hold, and which vanilla binding each one is.
 *
 * <p>The Bridge drives the client's own bindings rather than synthesising input
 * events: a managed Kin is a player at a keyboard, and the client's view of what
 * is held is the binding's state. Pressing the binding is what makes a movement
 * key held, and it is also what makes releasing it complete — the client already
 * knows how to let go of a key it thinks is down.
 */
public enum InputBinding {
    FORWARD(BridgeInputController.FORWARD),
    BACK(BridgeInputController.BACK),
    LEFT(BridgeInputController.LEFT),
    RIGHT(BridgeInputController.RIGHT),
    JUMP(BridgeInputController.JUMP),
    SNEAK(BridgeInputController.SNEAK),
    USE(BridgeInputController.USE),
    // The attack key, held while a block is being broken. Pressing it is what makes
    // the client break the block its crosshair is on at the client's own pace, so the
    // mining duration is vanilla's and not a second clock the Bridge would run.
    ATTACK(BridgeInputController.MINE),
    // The player's own inventory key. Not held: a screen is opened by one press, the
    // same transition a hand makes on `E`, so this is tapped rather than carried.
    INVENTORY(BridgeInputController.INVENTORY);

    private final String capability;

    InputBinding(String capability) {
        this.capability = capability;
    }

    public String capability() {
        return capability;
    }

    /** The binding for a capability, or empty when it is not one the Bridge holds. */
    public static Optional<InputBinding> of(String capability) {
        for (InputBinding binding : values()) {
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
            case USE -> options.useKey;
            case ATTACK -> options.attackKey;
            case INVENTORY -> options.inventoryKey;
        };
    }
}
