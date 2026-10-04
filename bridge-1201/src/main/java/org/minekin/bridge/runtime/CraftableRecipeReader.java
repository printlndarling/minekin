package org.minekin.bridge.runtime;

import java.util.ArrayList;
import java.util.List;
import net.minecraft.client.MinecraftClient;
import net.minecraft.client.gui.screen.recipebook.RecipeResultCollection;
import net.minecraft.client.network.ClientPlayerEntity;
import net.minecraft.client.recipebook.ClientRecipeBook;
import net.minecraft.recipe.Recipe;
import net.minecraft.recipe.RecipeMatcher;
import net.minecraft.screen.AbstractRecipeScreenHandler;

/**
 * The recipe book's craftable set for the grid the player has open, as namespaced recipe ids.
 *
 * <p>The same computation the vanilla recipe book widget performs for its own craftable
 * highlight, run from the same inputs: the player's inventory and the open handler's grid
 * ({@code populateRecipeFinder} on both) feed a {@link RecipeMatcher}, and every ordered
 * result collection is asked {@code computeCraftables} for the open grid's width and height.
 * A recipe the client does not name is answered as not-craftable-now — this reading never
 * guesses an unlock or a grid shape, and clicking is still validated by the client against
 * the game's real recipe set.
 *
 * <p>Empty whenever the client has no screen displayed: with the world in view there is no
 * grid the client is speaking for, which is the contract's own sentence about this field.
 * An open crafting-capable screen (the inventory's 2x2 or the crafting table's 3x3) reports
 * its grid like any other.
 */
public final class CraftableRecipeReader {
    private CraftableRecipeReader() {}

    /** The craftable recipe ids for the open screen's grid, or empty when none is open. */
    public static List<String> readable(MinecraftClient client) {
        if (client == null || client.currentScreen == null) {
            return List.of();
        }
        ClientPlayerEntity player = client.player;
        if (player == null
                || !(player.currentScreenHandler
                        instanceof AbstractRecipeScreenHandler<?> handler)) {
            return List.of();
        }
        ClientRecipeBook book = player.getRecipeBook();
        RecipeMatcher matcher = new RecipeMatcher();
        player.getInventory().populateRecipeFinder(matcher);
        handler.populateRecipeFinder(matcher);
        return craftable(
                handler.getCraftingWidth(),
                handler.getCraftingHeight(),
                book,
                matcher,
                book.getOrderedResults());
    }

    /**
     * Package-private so a test can drive the walk with a collection it built itself, the
     * same shape {@code RespawnScreenReader}'s screen seam uses.
     */
    static List<String> craftable(
            int gridWidth,
            int gridHeight,
            ClientRecipeBook book,
            RecipeMatcher matcher,
            List<RecipeResultCollection> results) {
        List<String> ids = new ArrayList<>();
        for (RecipeResultCollection collection : results) {
            collection.computeCraftables(matcher, gridWidth, gridHeight, book);
            for (Recipe<?> recipe : collection.getAllRecipes()) {
                if (collection.isCraftable(recipe)) {
                    ids.add(recipe.getId().toString());
                }
            }
        }
        return List.copyOf(ids);
    }
}
