package org.minekin.bridge.runtime;

import io.minekin.protocol.v1.AimTarget;
import io.minekin.protocol.v1.BlockFace;
import io.minekin.protocol.v1.BlockTarget;
import io.minekin.protocol.v1.InventoryStack;
import io.minekin.protocol.v1.InventorySummary;
import io.minekin.protocol.v1.MiningProgress;
import io.minekin.protocol.v1.SelfState;
import io.minekin.protocol.v1.VisibleEntity;
import io.minekin.protocol.v1.WorldObservation;
import java.util.ArrayList;
import java.util.List;
import net.minecraft.client.MinecraftClient;
import net.minecraft.client.gui.screen.Screen;
import net.minecraft.client.gui.screen.ingame.HandledScreen;
import net.minecraft.client.network.ClientPlayerEntity;
import net.minecraft.entity.Entity;
import net.minecraft.entity.ItemEntity;
import net.minecraft.item.ItemStack;
import net.minecraft.registry.Registries;
import net.minecraft.util.Identifier;
import net.minecraft.util.math.Box;
import net.minecraft.util.math.Vec3d;
import org.minekin.bridge.action.CrosshairReader;
import org.minekin.bridge.action.WorldActions;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;

/**
 * The recurring player-equivalent view: what this client can say about itself right now.
 *
 * <p>A second reader, not a second use of {@link ClientSnapshot}. The first snapshot is a
 * once-at-join admission proof and cannot carry the reads an action is checked against; this
 * is a fresh read of the same client state at a named tick, and it adds the fields a Kin acts
 * on — the position and angles behind the optional {@code SelfState} fields, the block under
 * the crosshair, the break animation, the screen and its handler, and — for a dropped item
 * only — what it is and how many.
 *
 * <p>Everything it reads is client-thread state and only the client's own crosshair: the
 * observation surface is the ray, never the loaded chunk. The added fields are optional, so a
 * value the client did not read is left absent rather than defaulted to zero — a yaw of 0 is
 * a player facing south, not a read that never happened.
 */
public final class WorldObservationCollector {

    private static final Logger LOGGER = LoggerFactory.getLogger("minekin-bridge");
    /** The same reach {@code ClientSnapshot} uses; one number for what "visible" costs. */
    private static final double VISIBLE_RADIUS_BLOCKS = 64.0;

    private WorldObservationCollector() {}

    /**
     * One observation, or null when the client cannot honestly describe itself.
     *
     * <p>Null rather than a partial message: an observation of a client not in a world would
     * carry zeroed angles and an empty hand as if they were reads, which is the exact
     * confusion the optional fields exist to prevent. The caller only invokes this while the
     * session is playable, so a null here means the world went away mid-tick.
     */
    public static WorldObservation collect(MinecraftClient client, long generation) {
        ClientPlayerEntity player = client.player;
        if (player == null || client.world == null) {
            return null;
        }
        long tick = Math.max(1L, client.world.getTime());
        WorldObservation.Builder view =
                WorldObservation.newBuilder()
                        .setGeneration(generation)
                        .setGameTick(tick)
                        .setSelf(selfState(client, player))
                        .setInventory(inventory(player, tick))
                        .addAllVisibleEntities(visibleEntities(player))
                        .setGui(
                                WorldActions.guiScreen(
                                        screenLabel(client),
                                        screenOpen(client),
                                        syncId(client),
                                        CraftableRecipeReader.readable(client)));
        WorldActions.aimTarget(CrosshairReader.read(client), tick).ifPresent(view::setAim);
        mining(client, tick).ifPresent(view::setMining);
        return view.build();
    }

    private static SelfState selfState(MinecraftClient client, ClientPlayerEntity player) {
        SelfState.Builder self =
                SelfState.newBuilder()
                        .setHealth(player.getHealth())
                        .setMaxHealth(player.getMaxHealth())
                        .setFood(player.getHungerManager().getFoodLevel())
                        .setSaturation(player.getHungerManager().getSaturationLevel())
                        .setOnGround(player.isOnGround())
                        .setAlive(player.isAlive())
                        .setRespawnAvailable(RespawnScreenReader.available(client));
        Vec3d position = player.getPos();
        self.setX(position.x).setY(position.y).setZ(position.z);
        WorldActions.LookAngles angles =
                WorldActions.LookAngles.of(player.getYaw(), player.getPitch()).orElse(null);
        if (angles != null) {
            self.setYawDegrees(angles.yawDegrees()).setPitchDegrees(angles.pitchDegrees());
        }
        self.setSelectedSlot(player.getInventory().selectedSlot);
        ItemStack mainHand = player.getInventory().getMainHandStack();
        if (!mainHand.isEmpty()) {
            self.setMainHandItemId(Registries.ITEM.getId(mainHand.getItem()).toString());
        }
        self.setCurrentScreen(currentScreenName(client));
        return self.build();
    }

    /**
     * The block under the crosshair's break animation, if the client is breaking one.
     *
     * <p>The target is the crosshair's block this instant, because the Bridge only ever mines
     * what its crosshair is on (a command naming a different block is refused before the key is
     * held), so the two agree while a break runs. The progress is the client's own stage,
     * scaled to the 0..1 bar the contract asks for; the continuous float behind the render is
     * private and not reached — this is a reading, and its being coarse is a fact a reader can
     * see rather than a precision the Bridge would invent.
     */
    private static java.util.Optional<MiningProgress> mining(MinecraftClient client, long tick) {
        if (client.interactionManager == null || !client.interactionManager.isBreakingBlock()) {
            return java.util.Optional.empty();
        }
        WorldActions.AimCrosshair crosshair = CrosshairReader.read(client);
        if (crosshair.kind() != WorldActions.CrosshairKind.BLOCK) {
            return java.util.Optional.empty();
        }
        BlockTarget target =
                BlockTarget.newBuilder()
                        .setX(crosshair.x())
                        .setY(crosshair.y())
                        .setZ(crosshair.z())
                        .setFace(crosshair.face() == null ? BlockFace.BLOCK_FACE_UNKNOWN : crosshair.face())
                        .build();
        float progress = client.interactionManager.getBlockBreakingProgress() / 10.0F;
        return java.util.Optional.of(WorldActions.miningProgress(tick, target, progress));
    }

    private static InventorySummary inventory(ClientPlayerEntity player, long revision) {
        net.minecraft.entity.player.PlayerInventory inventory = player.getInventory();
        List<InventoryStack> stacks = new ArrayList<>();
        for (int slot = 0; slot < inventory.size(); slot++) {
            ItemStack stack = inventory.getStack(slot);
            if (stack.isEmpty()) {
                continue;
            }
            stacks.add(
                    InventoryStack.newBuilder()
                            .setSlot(slot)
                            .setItemId(Registries.ITEM.getId(stack.getItem()).toString())
                            .setCount(stack.getCount())
                            .setDamage(stack.getDamage())
                            .build());
        }
        return InventorySummary.newBuilder().setRevision(revision).addAllStacks(stacks).build();
    }

    /**
     * The entities within reach, with a stack pair for a dropped item and nothing else.
     *
     * <p>Position is relative to the observer, never a world coordinate: a world position would
     * locate every entity the renderer holds against server truth, including those nobody is
     * looking at, and the boundary contract refuses that. What a Kin needs to return somewhere
     * is the observer's own position from {@code SelfState} plus this offset. Only an entity the
     * client renders as an item carries {@code item_id} and {@code item_count} — an entity's own
     * inventory is not something looking at it shows.
     */
    private static List<VisibleEntity> visibleEntities(ClientPlayerEntity player) {
        Vec3d origin = player.getPos();
        Box reach = player.getBoundingBox().expand(VISIBLE_RADIUS_BLOCKS);
        List<VisibleEntity> visible = new ArrayList<>();
        for (Entity entity : player.getWorld().getOtherEntities(player, reach)) {
            Vec3d relative = entity.getPos().subtract(origin);
            VisibleEntity.Builder candidate =
                    VisibleEntity.newBuilder()
                            .setObservationId(entity.getUuid().toString())
                            .setEntityType(Registries.ENTITY_TYPE.getId(entity.getType()).toString())
                            .setRelativeX((float) relative.x)
                            .setRelativeY((float) relative.y)
                            .setRelativeZ((float) relative.z)
                            .setLineOfSight(player.canSee(entity));
            if (entity instanceof ItemEntity item && !item.getStack().isEmpty()) {
                ItemStack stack = item.getStack();
                candidate
                        .setItemId(Registries.ITEM.getId(stack.getItem()).toString())
                        .setItemCount(stack.getCount());
            }
            visible.add(candidate.build());
        }
        return visible;
    }

    private static boolean screenOpen(MinecraftClient client) {
        return client.currentScreen != null;
    }

    private static int syncId(MinecraftClient client) {
        // Guarded the same way `screenLabel` guards it, and for the same reason: on the first
        // tick after joining, before the server has opened any screen, vanilla's player can
        // still hold no handler at all. Reading through it there was a null pointer on the
        // world's first tick, which is the one tick every joining run has.
        if (client.player == null || client.player.currentScreenHandler == null) {
            return -1;
        }
        return client.player.currentScreenHandler.syncId;
    }

    /**
     * A stable, non-secret id for the open screen, and "" when there is none.
     *
     * <p>Not a class's simple name: at runtime the client's Minecraft classes are intermediary,
     * so that would be a token like {@code class_418} that means nothing and differs per
     * version. A handled screen is named by its screen-handler type from the game's own
     * registry, which is a real namespaced id ({@code minecraft:chest}).
     *
     * <p>Two screens have no id to report, and both are reported as {@code ""} rather than as
     * a name the game does not have: an unhandled screen, whose text is a server's words; and
     * the player's own inventory, whose handler vanilla builds without a screen-handler type at
     * all. The second is not a theory — {@code ScreenHandler.getType()} answers that case by
     * <em>throwing</em> {@code UnsupportedOperationException("Unable to construct this menu by
     * type")} instead of returning null, and it was measured on the tick after the inventory
     * opened, where the throw stopped the client with {@code BRIDGE_FAULT}. The window the
     * player opened was the reason the observation died, so the reading that would have proved
     * the window open was never sent.
     *
     * <p>What a screen still has to be reported is its handler's sync id: that one is read
     * separately, and it is the number a click has to match. So the player's own screen arrives
     * as open, with sync id 0, and no id — enough to act on, and nothing invented.
     */
    private static String screenLabel(MinecraftClient client) {
        // Read from the screen, not from what the player happens to hold: the player's
        // current handler is the inventory handler the client built for itself, and it is
        // what the player holds while an unhandled screen is up.
        if (!(client.currentScreen instanceof HandledScreen<?> handled)) {
            return "";
        }
        try {
            Identifier id =
                    Registries.SCREEN_HANDLER.getId(handled.getScreenHandler().getType());
            return id == null ? "" : id.toString();
        } catch (UnsupportedOperationException noTypeForThisHandler) {
            // A handler the game gave no type to. Nothing about the screen is unknown: the
            // open state and the sync id both came from other reads, and an id is only a name.
            // A name is not worth stopping a run for, so this answers "" and moves on.
            return "";
        }
    }

    private static String currentScreenName(MinecraftClient client) {
        Screen screen = client.currentScreen;
        return screen == null ? "" : screen.getClass().getSimpleName();
    }
}
