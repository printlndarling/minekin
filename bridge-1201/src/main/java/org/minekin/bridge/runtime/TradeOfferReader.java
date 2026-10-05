package org.minekin.bridge.runtime;

import io.minekin.protocol.v1.TradeOffer.Builder;
import java.util.ArrayList;
import java.util.List;
import net.minecraft.client.MinecraftClient;
import net.minecraft.client.network.ClientPlayerEntity;
import net.minecraft.item.ItemStack;
import net.minecraft.registry.Registries;
import net.minecraft.screen.MerchantScreenHandler;
import net.minecraft.village.TradeOfferList;

/**
 * What an open merchant screen is offering, as rows a Core can choose between.
 *
 * <p>The same boundary the recipe book keeps: this reads the screen the player already sees
 * and nothing else. The price quoted is {@code getAdjustedFirstBuyItem} — the ask as it
 * stands this moment (demand and special prices applied), never the base price the offer
 * was built from, because a reading a Kin acts on has to be the price it will pay. The
 * second item is reported only when the offer has one; many asks are a single item, and an
 * empty second stack is "none", not "zero of something".
 *
 * <p>Empty whenever the client has no merchant screen displayed — a crafting table, an
 * inventory or a bare world all report no offers, which is the contract's own sentence
 * about this field. What the client cannot name is answered as nothing rather than guessed:
 * this reading never invents a trade.
 */
public final class TradeOfferReader {
    private TradeOfferReader() {}

    /** The open merchant's offers in the client's own order, or empty when none is open. */
    public static List<io.minekin.protocol.v1.TradeOffer> readable(MinecraftClient client) {
        if (client == null || client.currentScreen == null) {
            return List.of();
        }
        ClientPlayerEntity player = client.player;
        if (player == null || !(player.currentScreenHandler instanceof MerchantScreenHandler handler)) {
            return List.of();
        }
        return offers(handler.getRecipes());
    }

    /**
     * Package-private so a test can drive the walk with a list it built itself, the same
     * shape {@code CraftableRecipeReader}'s seam uses. The mapping below needs no world:
     * every field comes from the offer the client read.
     */
    static List<io.minekin.protocol.v1.TradeOffer> offers(TradeOfferList recipes) {
        List<io.minekin.protocol.v1.TradeOffer> rows = new ArrayList<>();
        for (var offer : recipes) {
            ItemStack first = offer.getAdjustedFirstBuyItem();
            ItemStack second = offer.getSecondBuyItem();
            ItemStack sell = offer.getSellItem();
            Builder row =
                    io.minekin.protocol.v1.TradeOffer.newBuilder()
                            .setFirstItemId(Registries.ITEM.getId(first.getItem()).toString())
                            .setFirstCount(first.getCount())
                            .setSellItemId(Registries.ITEM.getId(sell.getItem()).toString())
                            .setSellCount(sell.getCount())
                            .setUses(offer.getUses())
                            .setMaxUses(offer.getMaxUses())
                            .setDisabled(offer.isDisabled());
            if (!second.isEmpty()) {
                row.setSecondItemId(Registries.ITEM.getId(second.getItem()).toString())
                        .setSecondCount(second.getCount());
            }
            rows.add(row.build());
        }
        return List.copyOf(rows);
    }
}
