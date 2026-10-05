package org.minekin.bridge.action;

import io.minekin.protocol.v1.SlotClickMode;
import net.minecraft.client.MinecraftClient;
import net.minecraft.client.network.ClientPlayerEntity;
import net.minecraft.recipe.Recipe;
import net.minecraft.screen.slot.SlotActionType;
import net.minecraft.util.Identifier;
import org.minekin.bridge.input.BridgeInputController;
import org.minekin.bridge.input.KeySink;
import org.minekin.bridge.runtime.RespawnScreenReader;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;

/**
 * The S2 actions as the running client performs them — the Minecraft half of the seam.
 *
 * <p>Everything decided about a command before it gets here (the lease, the generation, the
 * deadline, the capability, the clamp, the named refusals) is not this class's business; it
 * is the worker's, made against a client-free controller so it can be tested without a game.
 * This class only performs the read or write that genuinely belongs to Minecraft, on the
 * client thread, and reports back what it observed so the worker can answer for it.
 *
 * <p>It is deliberately narrow about what it is allowed to touch: the player's own
 * crosshair, the player's own inventory and held slot, the screen the player already has
 * open and its handler id, and the interaction manager's own click and break calls. It never
 * reaches for a block behind the crosshair, never uses the {@code breakBlock} shortcut, and
 * has no creative-stack path — the contract forbids each of those, and here the method
 * simply does not exist.
 */
public final class WorldActionController implements WorldClientView {

    private static final Logger LOGGER = LoggerFactory.getLogger("minekin-bridge");

    private final KeySink keySink;

    public WorldActionController(KeySink keySink) {
        this.keySink = java.util.Objects.requireNonNull(keySink, "keySink");
    }

    private static MinecraftClient runningClient() {
        return MinecraftClient.getInstance();
    }

    @Override
    public boolean inWorld() {
        MinecraftClient client = runningClient();
        return client != null && client.player != null && client.world != null;
    }

    @Override
    public WorldActions.LookAngles lookAngles() {
        ClientPlayerEntity player = runningClient() == null ? null : runningClient().player;
        if (player == null) {
            return null;
        }
        return new WorldActions.LookAngles(player.getYaw(), player.getPitch());
    }

    @Override
    public WorldActions.AimCrosshair crosshair() {
        return CrosshairReader.read(runningClient());
    }

    @Override
    public boolean selectHotbar(int slot) {
        MinecraftClient client = runningClient();
        if (client == null || client.player == null || client.world == null) {
            return false;
        }
        // The hotbar selection is the player's own held slot, and writing it is exactly what
        // pressing a number key does: the client sends the slot-change packet on its own next
        // tick, so the Bridge does not send a second one and the read that confirms it is the
        // next observation's `selected_slot`. 1.20.1 exposes no setter for this — the field is
        // the state — measured from the pinned client.
        client.player.getInventory().selectedSlot = slot;
        LOGGER.info("bridge selected hotbar slot {}", slot);
        return true;
    }

    @Override
    public void openInventory() {
        // The same transition a hand makes on the inventory key: one tap of the client's own
        // binding, and vanilla's own poll opens the screen on its next frame. This is why it
        // goes through the key sink rather than `setScreen` — the contract asks that opening
        // the inventory be the player's own key path, and a screen installed behind it would
        // be a second door to the same window. It has to be a `tap` and not a press with a
        // release after it: the client opens the window from the edge a key event leaves, and
        // the held state on its own is a key nobody pressed.
        keySink.tap(BridgeInputController.INVENTORY);
    }

    @Override
    public void closeScreen() {
        MinecraftClient client = runningClient();
        if (client != null && client.currentScreen != null) {
            // The normal close path also returns the player to the inventory handler
            // and notifies the server. Removing only the screen strands container state.
            client.currentScreen.close();
        }
    }

    @Override
    public boolean respawn() {
        return RespawnScreenReader.press(runningClient());
    }

    @Override
    public boolean screenOpen() {
        MinecraftClient client = runningClient();
        return client != null && client.currentScreen != null;
    }

    @Override
    public int screenSyncId() {
        MinecraftClient client = runningClient();
        if (client == null || client.player == null) {
            return -1;
        }
        return client.player.currentScreenHandler.syncId;
    }

    @Override
    public boolean recipeKnown(String recipeId) {
        MinecraftClient client = runningClient();
        if (client == null || client.getNetworkHandler() == null) {
            return false;
        }
        Identifier identifier = parseIdentifier(recipeId);
        if (identifier == null) {
            return false;
        }
        return client.getNetworkHandler().getRecipeManager().get(identifier).isPresent();
    }

    @Override
    public void clickSlot(int slotId, int button, SlotClickMode mode) {
        MinecraftClient client = runningClient();
        if (client == null || client.player == null || client.interactionManager == null) {
            return;
        }
        int syncId = client.player.currentScreenHandler.syncId;
        client.interactionManager.clickSlot(
                syncId, slotId, button, toSlotAction(mode), client.player);
        LOGGER.info("bridge clicked slot {} (button {}, {})", slotId, button, mode);
    }

    @Override
    public void clickRecipe(String recipeId, boolean craftAll) {
        MinecraftClient client = runningClient();
        if (client == null || client.player == null || client.interactionManager == null) {
            return;
        }
        Identifier identifier = parseIdentifier(recipeId);
        if (identifier == null) {
            return;
        }
        Recipe<?> recipe =
                client.getNetworkHandler().getRecipeManager().get(identifier).orElse(null);
        if (recipe == null) {
            // Re-checked: the caller refused an unknown recipe before getting here, and a
            // recipe that resolved then failed to resolve now is a state change, not a name
            // to send. Nothing goes out.
            return;
        }
        int syncId = client.player.currentScreenHandler.syncId;
        client.interactionManager.clickRecipe(syncId, recipe, craftAll);
        LOGGER.info("bridge clicked recipe {} (craftAll={})", recipeId, craftAll);
    }

    @Override
    public void clickButton(int buttonId) {
        MinecraftClient client = runningClient();
        if (client == null || client.player == null || client.interactionManager == null) {
            return;
        }
        // The id is the screen's own vocabulary (a merchant's offer index, and whatever
        // other screens assign); an id the screen does not know is answered by the screen
        // itself with no effect, which is the client's validate-then-act order, not this
        // layer inventing a check it cannot make.
        int syncId = client.player.currentScreenHandler.syncId;
        client.interactionManager.clickButton(syncId, buttonId);
        LOGGER.info("bridge clicked button {}", buttonId);
    }

    private static SlotActionType toSlotAction(SlotClickMode mode) {
        return switch (mode) {
            case SLOT_CLICK_MODE_PICK -> SlotActionType.PICKUP;
            case SLOT_CLICK_MODE_QUICK_MOVE -> SlotActionType.QUICK_MOVE;
            case SLOT_CLICK_MODE_SWAP -> SlotActionType.SWAP;
            case SLOT_CLICK_MODE_THROW -> SlotActionType.THROW;
            // The caller validated that a slot click names a supported mode, so this is
            // reached only defensively; PICKUP is the least-surprising of the real actions.
            default -> SlotActionType.PICKUP;
        };
    }

    private static Identifier parseIdentifier(String recipeId) {
        if (recipeId == null || recipeId.isBlank()) {
            return null;
        }
        try {
            return new Identifier(recipeId);
        } catch (RuntimeException invalid) {
            // A name that is not a valid id is not a recipe this version has, which is the
            // same answer as an id that resolves to nothing and is refused by name upstream.
            return null;
        }
    }
}
