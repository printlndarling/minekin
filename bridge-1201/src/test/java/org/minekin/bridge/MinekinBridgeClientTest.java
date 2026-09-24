package org.minekin.bridge;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertFalse;

import net.minecraft.client.gui.screen.Screen;
import net.minecraft.text.Text;
import org.junit.jupiter.api.Test;

/**
 * The label the Bridge puts on a screen that has taken the keyboard.
 *
 * <p>What the real client shows is verified on the controlled runner; what is
 * decidable here is that the label is one a reader can use.
 */
final class MinekinBridgeClientTest {

    /** A screen the Bridge has no name for, which is most of them. */
    private static final class UnnamedScreen extends Screen {
        UnnamedScreen() {
            super(Text.empty());
        }

        @Override
        protected void init() {}
    }

    @Test
    void aClientWithNoScreenHasNoLabel() {
        assertEquals("", MinekinBridgeClient.screenLabel(null));
    }

    @Test
    void aScreenTheBridgeCannotNameIsLabelledAsAScreen() {
        // Never the class's own name: at runtime a production client's classes are
        // intermediary, so the death screen's is `class_418` — measured on a run,
        // and meaningless to anyone reading the log it lands in.
        String label = MinekinBridgeClient.screenLabel(new UnnamedScreen());

        assertEquals("SomeScreen", label);
        assertFalse(label.startsWith("class_"), "the label is not an obfuscated token");
    }
}
