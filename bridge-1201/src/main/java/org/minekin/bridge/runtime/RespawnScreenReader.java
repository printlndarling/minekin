package org.minekin.bridge.runtime;

import net.minecraft.client.MinecraftClient;
import net.minecraft.client.gui.screen.DeathScreen;
import net.minecraft.client.gui.screen.Screen;
import net.minecraft.client.gui.widget.ButtonWidget;
import net.minecraft.text.TranslatableTextContent;

/** Reads only the enabled respawn affordance on the player's current death screen. */
public final class RespawnScreenReader {
    private RespawnScreenReader() {}

    public static boolean available(MinecraftClient client) {
        return client != null
                && client.player != null
                && available(client.currentScreen, client.player.isAlive());
    }

    static boolean available(Screen current, boolean alive) {
        return button(current, alive) != null;
    }

    public static boolean press(MinecraftClient client) {
        return client != null
                && client.player != null
                && press(client.currentScreen, client.player.isAlive());
    }

    static boolean press(Screen current, boolean alive) {
        ButtonWidget button = button(current, alive);
        if (button == null) {
            return false;
        }
        button.onPress();
        return true;
    }

    private static ButtonWidget button(Screen current, boolean alive) {
        if (alive || !(current instanceof DeathScreen screen)) {
            return null;
        }
        // Translation keys identify the vanilla action in every language. Literal
        // server text cannot manufacture permission; the hardcore spectate button
        // has a different key and is deliberately not a respawn affordance.
        for (var child : screen.children()) {
            if (child instanceof ButtonWidget button
                    && button.active
                    && button.visible
                    && button.getMessage().getContent() instanceof TranslatableTextContent text
                    && "deathScreen.respawn".equals(text.getKey())) {
                return button;
            }
        }
        return null;
    }
}
