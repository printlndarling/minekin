package org.minekin.bridge;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertTrue;

import java.io.IOException;
import java.io.InputStream;
import java.nio.charset.StandardCharsets;
import java.util.List;
import net.fabricmc.api.ClientModInitializer;
import org.junit.jupiter.api.Test;

/**
 * The manifest names an entrypoint class, and a manifest naming a class that does
 * not exist or does not implement the client interface is a classic Fabric
 * startup failure that a text-only check cannot catch.
 *
 * <p>These run against the compiled classes, so they need the Fabric API on the
 * classpath but no Minecraft runtime. Behaviour that needs a real client is
 * verified on the controlled runner, not here.
 */
final class BridgeEntrypointTest {
    private static final String ENTRYPOINT = "org.minekin.bridge.MinekinBridgeClient";

    /** The dependency set reviewed for *this* Minecraft version, pinned exactly. */
    private static final List<String> REVIEWED_PINS = List.of(
            "\"environment\": \"client\"",
            "\"fabricloader\": \"=0.19.5\"",
            "\"fabric-api\": \"=0.92.12+1.20.1\"",
            "\"java\": \">=17\"",
            "\"minecraft\": \"=1.20.1\"");

    private static String manifest() throws IOException {
        try (InputStream stream = BridgeEntrypointTest.class.getResourceAsStream("/fabric.mod.json")) {
            assertTrue(stream != null, "fabric.mod.json must be on the test classpath");
            return new String(stream.readAllBytes(), StandardCharsets.UTF_8);
        }
    }

    @Test
    void theManifestNamesAnEntrypointThatExists() throws Exception {
        assertTrue(
                manifest().contains(ENTRYPOINT),
                "the manifest must name " + ENTRYPOINT + " as its client entrypoint");

        Class<?> entrypoint = Class.forName(ENTRYPOINT);

        assertTrue(
                ClientModInitializer.class.isAssignableFrom(entrypoint),
                ENTRYPOINT + " must implement ClientModInitializer");
    }

    @Test
    void theEntrypointCanBeInstantiatedByName() throws Exception {
        Class<?> entrypoint = Class.forName(ENTRYPOINT);

        assertTrue(
                java.lang.reflect.Modifier.isPublic(entrypoint.getModifiers()),
                "Fabric loads the entrypoint by name, so the class must be public");
        assertEquals(
                0,
                entrypoint.getDeclaredConstructors()[0].getParameterCount(),
                "Fabric instantiates the entrypoint with no arguments");
    }

    @Test
    void theManifestKeepsTheReviewedDependencySet() throws Exception {
        String document = manifest();

        for (String pin : REVIEWED_PINS) {
            assertTrue(document.contains(pin), "the manifest must keep the reviewed pin " + pin);
        }
    }

    @Test
    void theBridgeIsClientOnly() throws Exception {
        assertTrue(
                manifest().contains("\"environment\": \"client\""),
                "the Bridge must never load on a dedicated server");
    }

    @Test
    void theVersionPinnedConnectCancellationMixinIsDeclared() throws Exception {
        String document = manifest();

        assertTrue(document.contains("minekin_bridge.mixins.json"));
        try (InputStream stream = BridgeEntrypointTest.class.getResourceAsStream(
                "/minekin_bridge.mixins.json")) {
            assertTrue(stream != null, "the declared mixin config must be packaged");
            String mixins = new String(stream.readAllBytes(), StandardCharsets.UTF_8);
            assertTrue(mixins.contains("ConnectScreenAccessor"));
            assertTrue(mixins.contains("\"required\": true"));
        }
    }
}
