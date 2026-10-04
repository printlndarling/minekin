package org.minekin.bridge.runtime;

import static org.junit.jupiter.api.Assertions.assertTrue;

import java.util.List;
import net.minecraft.client.recipebook.ClientRecipeBook;
import net.minecraft.recipe.RecipeMatcher;
import org.junit.jupiter.api.Test;

final class CraftableRecipeReaderTest {
    // The walk itself -- populateRecipeFinder, computeCraftables, isCraftable -- is the
    // vanilla recipe book widget's own sequence and is proven where this contract is proven:
    // a live run opening the crafting table must read the pickaxe back in this set (card
    // S3-WIDE-GRID-CRAFT-CLOSURE-001). A unit test cannot reach it: blocks and items refuse
    // to load unbootstrapped, the registry bootstrap then dies on the dev classpath's access
    // layer (measured), and pulling fabric-loader-junit in would move the supply chain for
    // a reading the world already answers. What is pinned here are the two empty answers
    // that must never become a guess.

    @Test
    void aClientWithNothingOpenReportsNothing() {
        assertTrue(CraftableRecipeReader.readable(null).isEmpty());
    }

    @Test
    void anEmptyBookOverAnEmptyResultSetReportsNothing() {
        assertTrue(
                CraftableRecipeReader.craftable(
                                2, 2, new ClientRecipeBook(), new RecipeMatcher(), List.of())
                        .isEmpty());
    }
}
