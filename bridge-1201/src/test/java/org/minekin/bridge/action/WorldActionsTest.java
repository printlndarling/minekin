package org.minekin.bridge.action;

import static org.junit.jupiter.api.Assertions.*;

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
}
