package org.minekin.bridge.runtime;

import io.minekin.protocol.v1.InitialObservation;
import io.minekin.protocol.v1.InventoryStack;
import io.minekin.protocol.v1.InventorySummary;
import io.minekin.protocol.v1.SelfState;
import io.minekin.protocol.v1.VisibleEntity;
import java.util.ArrayList;
import java.util.List;
import java.util.UUID;
import net.minecraft.client.MinecraftClient;
import net.minecraft.client.gui.screen.Screen;
import net.minecraft.client.network.ClientPlayerEntity;
import net.minecraft.client.session.Session;
import net.minecraft.entity.Entity;
import net.minecraft.entity.player.PlayerInventory;
import net.minecraft.item.ItemStack;
import net.minecraft.registry.Registries;
import net.minecraft.util.math.Box;
import net.minecraft.util.math.Vec3d;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.minekin.bridge.protocol.SessionIdentityReportAdapter;
import org.minekin.bridge.protocol.SessionIdentityReportAdapter.ObservedSession;

/**
 * The first authoritative snapshot: what this client can honestly say about itself.
 *
 * <p>It carries the client's own state and the entities this client can confirm
 * it can see. The contract is explicit that a snapshot "does not thereby open
 * entities behind walls, unseen containers, seeds or server-side world objects" —
 * so every candidate carries whether the client could actually see it, and a
 * candidate it could not is sent rather than dropped: Core counts those
 * rejections, and a silent omission would be the Bridge deciding policy it does
 * not own.
 *
 * <p>Everything here reads client-thread state, so it must run on that thread.
 */
public final class ClientSnapshot {
    private static final Logger LOGGER = LoggerFactory.getLogger("minekin-bridge");
    private static final double VISIBLE_RADIUS_BLOCKS = 64.0;

    private ClientSnapshot() {}

    /**
     * One snapshot, or `null` when the client cannot honestly describe itself.
     *
     * <p>Null rather than an exception: a session whose identity material is
     * missing is a session that cannot become playable, which the run reports,
     * and it is not a reason to stop a client that is otherwise running fine.
     */
    public static InitialObservation collect(MinecraftClient client, long generation) {
        ClientPlayerEntity player = client.player;
        if (player == null || client.world == null) {
            return null;
        }
        Session session = client.getSession();
        UUID uuid = session.getUuidOrNull();
        if (uuid == null || session.getUsername().isBlank()) {
            return null;
        }
        // The world's own clock is what a snapshot is a picture of, and it is the
        // inventory's revision too: Core reads revision zero as "the summary was
        // never populated", so a summary taken at tick zero would be
        // indistinguishable from one that carried nothing.
        long tick = Math.max(1, client.world.getTime());
        List<VisibleEntity> visible = visibleEntities(player);
        // Logged because the counts are the only place a run can show that the
        // world was looked at: Core's admission verdict is in the run document,
        // which a session bounded by a window never prints, while these two
        // numbers say whether the Kin had anything to see at all.
        LOGGER.info(
                "bridge collected {} entity candidate(s) within {} blocks, {} confirmed visible",
                visible.size(),
                VISIBLE_RADIUS_BLOCKS,
                visible.stream().filter(VisibleEntity::getLineOfSight).count());
        return InitialObservation.newBuilder()
                .setGeneration(generation)
                .setGameTick(tick)
                .setAuthoritative(true)
                .setSelf(selfState(client, player))
                .setInventory(inventory(player, tick))
                .addAllVisibleEntities(visible)
                .setSessionIdentity(SessionIdentityReportAdapter.toProto("", observed(session, uuid)))
                .build();
    }

    private static SelfState selfState(MinecraftClient client, ClientPlayerEntity player) {
        Screen screen = client.currentScreen;
        return SelfState.newBuilder()
                .setHealth(player.getHealth())
                .setMaxHealth(player.getMaxHealth())
                .setFood(player.getHungerManager().getFoodLevel())
                .setSaturation(player.getHungerManager().getSaturationLevel())
                .setOnGround(player.isOnGround())
                .setAlive(player.isAlive())
                // A screen *class*, never its text: the title of a screen can be
                // anything the client was told, and this is a product event.
                .setCurrentScreen(screen == null ? "" : screen.getClass().getSimpleName())
                .build();
    }

    private static InventorySummary inventory(ClientPlayerEntity player, long revision) {
        PlayerInventory inventory = player.getInventory();
        List<InventoryStack> stacks = new ArrayList<>();
        for (int slot = 0; slot < inventory.size(); slot++) {
            ItemStack stack = inventory.getStack(slot);
            if (stack.isEmpty()) {
                continue;
            }
            stacks.add(InventoryStack.newBuilder()
                    .setSlot(slot)
                    .setItemId(Registries.ITEM.getId(stack.getItem()).toString())
                    .setCount(stack.getCount())
                    .setDamage(stack.getDamage())
                    .build());
        }
        return InventorySummary.newBuilder()
                .setRevision(revision)
                .addAllStacks(stacks)
                .build();
    }

    /**
     * How many entities the client knows about in reach, and nothing more.
     *
     * <p>For the join diagnostic: the count is what tells a run whether a world
     * that contains something was seen as empty because it was empty or because
     * the client had not been told about it yet.
     */
    public static int entityCandidates(MinecraftClient client) {
        ClientPlayerEntity player = client.player;
        if (player == null || client.world == null) {
            return 0;
        }
        return visibleEntities(player).size();
    }

    /**
     * The entities within reach, each with whether the client could confirm it.
     *
     * <p>Bounded by radius and by nothing else. The radius is the same number
     * Core uses, but for a different reason: here it is the cost of a raycast per
     * entity, and the snapshot is taken once per join rather than per tick, so
     * there is no need for a second bound. A bound that dropped candidates
     * silently would be worse than the cost — Core counts what it rejects, and
     * those counts are the evidence that someone saw something.
     *
     * <p>`canSee` is vanilla's own line-of-sight test, so "the client can confirm
     * it" means exactly what it means when the client renders: a candidate behind
     * a wall is not confirmed, and Core drops it rather than guessing where it is.
     */
    private static List<VisibleEntity> visibleEntities(ClientPlayerEntity player) {
        Vec3d origin = player.getPos();
        Box reach = player.getBoundingBox().expand(VISIBLE_RADIUS_BLOCKS);
        List<VisibleEntity> visible = new ArrayList<>();
        for (Entity entity : player.getWorld().getOtherEntities(player, reach)) {
            Vec3d relative = entity.getPos().subtract(origin);
            visible.add(VisibleEntity.newBuilder()
                    // The entity's own UUID: the token upper layers act on has to
                    // be stable for as long as the entity exists, and an index
                    // into this list would mean something different next time.
                    .setObservationId(entity.getUuid().toString())
                    .setEntityType(Registries.ENTITY_TYPE.getId(entity.getType()).toString())
                    .setRelativeX((float) relative.x)
                    .setRelativeY((float) relative.y)
                    .setRelativeZ((float) relative.z)
                    .setLineOfSight(player.canSee(entity))
                    .build());
        }
        return visible;
    }

    private static ObservedSession observed(Session session, UUID uuid) {
        // The account type can be *absent*, and on the reviewed offline candidate
        // it is: measured, `--userType legacy` does not become `Session.AccountType`
        // for this client. Reporting "" is the verbatim answer and the interesting
        // one — inventing LEGACY would record an enum the client never held, which
        // is what the candidate matrix exists to find out.
        Session.AccountType accountType = session.getAccountType();
        return new ObservedSession(
                session.getUsername(),
                uuid.toString(),
                accountType == null ? "" : accountType.name(),
                session.getXuid().isPresent(),
                session.getClientId().isPresent());
    }
}
