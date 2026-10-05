package org.minekin.bridge.runtime;

import static org.junit.jupiter.api.Assertions.assertTrue;

import net.minecraft.village.TradeOfferList;
import org.junit.jupiter.api.Test;

final class TradeOfferReaderTest {
    // The non-empty walk -- getAdjustedFirstBuyItem, the second buy, the sell stack -- is
    // proven where the reading matters: a live run opening a wandering trader's screen must
    // read its offers back (card D-ENTITY-BEHAVIORS-001). A unit test cannot build a real
    // offer: ItemStacks refuse to load unbootstrapped (the same wall CraftableRecipeReader's
    // test documents). What is pinned here is that every empty answer stays empty.

    @Test
    void aClientWithNothingOpenReportsNothing() {
        assertTrue(TradeOfferReader.readable(null).isEmpty());
    }

    @Test
    void anEmptyMerchantListReportsNothing() {
        assertTrue(TradeOfferReader.offers(new TradeOfferList()).isEmpty());
    }
}
