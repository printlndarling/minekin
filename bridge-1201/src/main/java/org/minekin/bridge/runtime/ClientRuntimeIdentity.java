package org.minekin.bridge.runtime;

import java.util.Objects;
import net.fabricmc.loader.api.FabricLoader;
import net.fabricmc.loader.api.ModContainer;

/**
 * The Minecraft and Fabric Loader versions this process is actually running.
 *
 * <p>Both are read out of the loader's own mod containers: {@code minecraft} is
 * the builtin container the game provider registers for the jar it loaded, and
 * {@code fabricloader} is the metadata of the loader jar that is running this
 * mod. Neither is a value the Bridge chooses, which is the point — Core compares
 * the declaration against the reviewed recipe for this session, and a Bridge that
 * could pick its own answer would only be reporting an intention.
 *
 * <p>A missing container is a refusal rather than a fallback. There is no
 * plausible version to fall back to: declaring one the client is not running is
 * exactly the false statement this record exists to make impossible.
 */
public record ClientRuntimeIdentity(String minecraftVersion, String fabricLoaderVersion) {
    static final String GAME_MOD_ID = "minecraft";
    static final String LOADER_MOD_ID = "fabricloader";

    public ClientRuntimeIdentity {
        requireText(minecraftVersion, "minecraftVersion");
        requireText(fabricLoaderVersion, "fabricLoaderVersion");
    }

    public static ClientRuntimeIdentity current() {
        return new ClientRuntimeIdentity(
                modVersion(GAME_MOD_ID),
                modVersion(LOADER_MOD_ID));
    }

    private static String modVersion(String modId) {
        ModContainer container = FabricLoader.getInstance()
                .getModContainer(modId)
                .orElseThrow(() -> new IllegalStateException(
                        "this client exposes no " + modId + " mod container to report"));
        String version = container.getMetadata().getVersion().getFriendlyString();
        requireText(version, modId + " version");
        return version;
    }

    private static void requireText(String value, String field) {
        if (value == null || value.isBlank()) {
            throw new IllegalStateException(field + " is required");
        }
    }
}
