package org.minekin.bridge.action;

import io.minekin.protocol.v1.SlotClickMode;

/**
 * The Minecraft the S2 actions need, behind one Minecraft-free seam.
 *
 * <p>The worker on the other side owns every decision that can be made without a running
 * client — the lease, generation and deadline guard, the named refusals, the clamp and the
 * result status — and hands only the read or write that genuinely belongs to Minecraft here.
 * Keeping that boundary a type rather than a call into {@code MinecraftClient} is what lets
 * the worker compile and be tested without a client, and it is what keeps the whole
 * bridge-1201 runtime free of any Minecraft import.
 *
 * <p>Every method is called on the client thread (the worker drains its inbox from the
 * client tick), which is the only thread allowed to read a hit result, write a slot, or tap
 * a key binding. The implementation is {@code WorldActionController}.
 */
public interface WorldClientView {

    /** Whether the client is in a world it can act in — a player and a world are present. */
    boolean inWorld();

    /** The player's own look angles this instant, in degrees. Absent when not in a world. */
    WorldActions.LookAngles lookAngles();

    /**
     * The client's own crosshair this instant, already resolved to the wire's reading.
     *
     * <p>{@link WorldActions.CrosshairKind#NOT_READ} when the client is not in a world at
     * all; {@link WorldActions.CrosshairKind#MISS} when it looked and hit nothing. Only the
     * ray is read — never the loaded chunk.
     */
    WorldActions.AimCrosshair crosshair();

    /**
     * Puts the named hotbar slot in hand.
     *
     * @return whether the client was in a world to accept the selection
     */
    boolean selectHotbar(int slot);

    /** Opens the player's own inventory, by the client's own inventory key press. */
    void openInventory();

    /** Dismisses whatever screen the client has open. */
    void closeScreen();

    /** Whether a screen currently holds the keyboard. */
    boolean screenOpen();

    /** The handler id the client reports right now, and the id a click must match. */
    int screenSyncId();

    /** Whether this game version actually has a rule with that id. */
    boolean recipeKnown(String recipeId);

    /** Clicks a slot in the screen the client already has open. */
    void clickSlot(int slotId, int button, SlotClickMode mode);

    /** Crafts a known recipe from the screen the client already has open. */
    void clickRecipe(String recipeId, boolean craftAll);
}
