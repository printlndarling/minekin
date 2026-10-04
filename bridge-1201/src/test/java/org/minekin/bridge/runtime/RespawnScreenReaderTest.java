package org.minekin.bridge.runtime;

import static org.junit.jupiter.api.Assertions.*;

import net.minecraft.client.gui.screen.DeathScreen;
import net.minecraft.client.gui.widget.ButtonWidget;
import net.minecraft.text.Text;
import org.junit.jupiter.api.Test;

class RespawnScreenReaderTest {
    private static final class WithButton extends DeathScreen {
        final ButtonWidget button;
        int presses;

        WithButton(Text label) {
            super(null, false);
            button = addDrawableChild(ButtonWidget.builder(label, ignored -> presses++).build());
        }
    }

    @Test
    void onlyAnEnabledVisibleRespawnOnADeadBodyIsAvailable() {
        WithButton screen = new WithButton(Text.translatable("deathScreen.respawn"));
        assertTrue(RespawnScreenReader.available(screen, false));
        assertFalse(RespawnScreenReader.available(screen, true));
        screen.button.active = false;
        assertFalse(RespawnScreenReader.available(screen, false));
        screen.button.active = true;
        screen.button.visible = false;
        assertFalse(RespawnScreenReader.available(screen, false));
    }

    @Test
    void spectatingQuittingAndLiteralLabelsCannotGrantRespawning() {
        for (Text label : new Text[] {
            Text.translatable("deathScreen.spectate"),
            Text.translatable("deathScreen.titleScreen"),
            Text.literal("deathScreen.respawn"),
            Text.literal("Respawn")
        }) {
            assertFalse(RespawnScreenReader.available(new WithButton(label), false));
        }
        assertFalse(RespawnScreenReader.available(null, false));
    }
    @Test
    void executionRechecksTheActualButtonAndCallsItsVanillaCallbackOnce() {
        WithButton screen = new WithButton(Text.translatable("deathScreen.respawn"));
        assertTrue(RespawnScreenReader.available(screen, false));
        screen.button.active = false;
        assertFalse(RespawnScreenReader.press(screen, false));
        assertEquals(0, screen.presses);
        screen.button.active = true;
        assertTrue(RespawnScreenReader.press(screen, false));
        assertEquals(1, screen.presses);
        assertFalse(RespawnScreenReader.press(screen, true));
        assertEquals(1, screen.presses);
        WithButton spectate = new WithButton(Text.translatable("deathScreen.spectate"));
        assertFalse(RespawnScreenReader.press(spectate, false));
        assertEquals(0, spectate.presses);
    }

}
