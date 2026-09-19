package org.minekin.bridge.runtime;

import io.minekin.protocol.v1.InitialObservation;
import io.minekin.protocol.v1.InventoryStack;
import io.minekin.protocol.v1.InventorySummary;
import io.minekin.protocol.v1.SelfState;
import java.util.ArrayList;
import java.util.List;
import java.util.UUID;
import net.minecraft.client.MinecraftClient;
import net.minecraft.client.gui.screen.Screen;
import net.minecraft.client.network.ClientPlayerEntity;
import net.minecraft.client.session.Session;
import net.minecraft.entity.player.PlayerInventory;
import net.minecraft.item.ItemStack;
import net.minecraft.registry.Registries;
import org.minekin.bridge.protocol.SessionIdentityReportAdapter;
import org.minekin.bridge.protocol.SessionIdentityReportAdapter.ObservedSession;

/**
 * The first authoritative snapshot: what this client can honestly say about itself.
 *
 * <p>It carries the client's own state and nothing else. The contract's minimum
 * for a snapshot is the player's own state and the surrounding context, and it is
 * explicit that this "does not thereby open entities behind walls, unseen
 * containers, seeds or server-side world objects" — so what is absent here is
 * absent by rule, not by omission: the visible world is a separate collection
 * with its own line-of-sight confirmation, and a list of no entities would be a
 * claim that nothing is there rather than a statement that nothing was checked.
 *
 * <p>Everything here reads client-thread state, so it must run on that thread.
 */
public final class ClientSnapshot {
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
        return InitialObservation.newBuilder()
                .setGeneration(generation)
                .setGameTick(tick)
                .setAuthoritative(true)
                .setSelf(selfState(client, player))
                .setInventory(inventory(player, tick))
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
