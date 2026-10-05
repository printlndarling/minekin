package org.minekin.bridge.action;

import static org.junit.jupiter.api.Assertions.*;

import io.minekin.protocol.v1.BlockFace;
import org.junit.jupiter.api.Test;

class WorldActionsTest {
    @Test
    void observedYawStaysCanonicalAfterCrossingEitherSeamAndManyTurns() {
        assertEquals(-179.0F, WorldActions.LookAngles.of(181.0F, 20.0F).orElseThrow().yawDegrees());
        assertEquals(179.0F, WorldActions.LookAngles.of(-181.0F, -20.0F).orElseThrow().yawDegrees());
        assertEquals(180.0F, WorldActions.LookAngles.of(-540.0F, 0.0F).orElseThrow().yawDegrees());
        assertEquals(25.0F, WorldActions.LookAngles.of(36025.0F, 10.0F).orElseThrow().yawDegrees());
        assertEquals(10.0F, WorldActions.LookAngles.of(36025.0F, 10.0F).orElseThrow().pitchDegrees());
    }

    @Test
    void unreadNonFiniteAnglesRemainUnread() {
        assertTrue(WorldActions.LookAngles.of(Float.NaN, 0.0F).isEmpty());
        assertTrue(WorldActions.LookAngles.of(Float.POSITIVE_INFINITY, 0.0F).isEmpty());
        assertTrue(WorldActions.LookAngles.of(0.0F, Float.NEGATIVE_INFINITY).isEmpty());
    }

    @Test
    void aMineWithoutANamedBlockSwingsOnlyAtAnEntity() {
        WorldActions.AimCrosshair entity =
                new WorldActions.AimCrosshair(
                        WorldActions.CrosshairKind.ENTITY,
                        0,
                        0,
                        0,
                        BlockFace.BLOCK_FACE_UNKNOWN,
                        "",
                        "uuid-1",
                        "minecraft:slime",
                        2.0);
        WorldActions.AimCrosshair block =
                new WorldActions.AimCrosshair(
                        WorldActions.CrosshairKind.BLOCK,
                        4,
                        64,
                        9,
                        BlockFace.BLOCK_FACE_UP,
                        "minecraft:oak_log",
                        "",
                        "",
                        2.0);
        WorldActions.AimCrosshair miss =
                new WorldActions.AimCrosshair(
                        WorldActions.CrosshairKind.MISS, 0, 0, 0, BlockFace.BLOCK_FACE_UNKNOWN, "", "", "", 0.0);

        // No block named: an entity under the crosshair is the one thing a swing can land on.
        assertTrue(WorldActions.mineTargetRefusal(null, entity).isEmpty());
        // Air and a block are both refused: one has nothing to hit, the other was not the
        // shape this call asked for.
        assertEquals(
                WorldActions.REFUSED_MINE_TARGET_NOT_AIMED,
                WorldActions.mineTargetRefusal(null, miss).orElseThrow());
        assertEquals(
                WorldActions.REFUSED_MINE_TARGET_NOT_AIMED,
                WorldActions.mineTargetRefusal(null, block).orElseThrow());
    }
}
