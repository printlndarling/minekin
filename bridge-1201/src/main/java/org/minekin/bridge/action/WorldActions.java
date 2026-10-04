package org.minekin.bridge.action;

import io.minekin.protocol.v1.AimTarget;
import io.minekin.protocol.v1.AimTargetKind;
import io.minekin.protocol.v1.BlockFace;
import io.minekin.protocol.v1.BlockTarget;
import io.minekin.protocol.v1.GuiScreen;
import io.minekin.protocol.v1.MiningProgress;
import java.util.List;
import java.util.Optional;
import java.util.Set;

/**
 * The decisions S2 makes, with no Minecraft in sight.
 *
 * <p>Everything the Bridge must refuse by name, every clamp that keeps a turn a
 * turn, and every mapping from a client reading to a wire record is decided here as
 * arithmetic over the values the client handed over. What reads the client is the
 * controller and the collector; what they could get wrong — a stale sync id clicking
 * the wrong container, an aim that teleports the view, a crosshair read as a block it
 * was not on — is decided here and is testable here, which is the whole reason it is
 * separated. A rule you cannot exercise without a running client is a rule you find
 * out about in production.
 *
 * <p>Nothing in this file imports Minecraft. The names it speaks are the wire's own
 * generated types and primitives, so the same logic compiles in the stub build CI runs
 * and in the client the mod ships into.
 */
public final class WorldActions {

    /**
     * The most a single {@code AimInput} may move the view, in degrees.
     *
     * <p>A build constant, not a request rate, exactly like the observation cadence:
     * "turn to face the thing behind me" has to arrive as a sequence of observable
     * steps, and the only way a reader can tell an unfinished turn from a finished one
     * is by comparing the angle it asked for against the angle the next observation
     * reports. That comparison is worthless if one command is allowed to snap the whole
     * way, so the limit lives on the client and not in whatever Core computes.
     */
    public static final float MAX_AIM_DEGREES_PER_COMMAND = 20.0F;

    /**
     * The cadence of the recurring player-equivalent view, in game ticks.
     *
     * <p>A constant of the build rather than a poll rate: one session costs the same
     * however urgently the other side asks, and the cost of the read is not something
     * the reader gets to set.
     */
    public static final int WORLD_OBSERVATION_INTERVAL_TICKS = 10;

    // The named refusals. Spec §1 and §3 name each one because "an action did not
    // happen" and "an action was refused for this reason" are different facts, and the
    // second is the one Core can act on. They are strings on the wire, so they are
    // written once here and referenced everywhere else.
    public static final String REFUSED_CAPABILITY_NOT_GRANTED = "CAPABILITY_NOT_GRANTED";
    public static final String REFUSED_MINE_TARGET_NOT_AIMED = "MINE_TARGET_NOT_AIMED";
    public static final String REFUSED_HOTBAR_OUT_OF_RANGE = "HOTBAR_SLOT_OUT_OF_RANGE";
    public static final String REFUSED_GUI_SYNC_ID_MISMATCH = "GUI_SYNC_ID_MISMATCH";
    public static final String REFUSED_GUI_RECIPE_UNKNOWN = "GUI_RECIPE_UNKNOWN";
    /**
     * The command named the current generation and its capability was granted, but the
     * client has no world to act in this instant — the player or level went away between
     * the command arriving and the client tick applying it. Refused by name rather than
     * answered with a partial action: a Kin that was told to turn or break something and
     * is standing in no world must be able to record that, not read silence.
     */
    public static final String REFUSED_NOT_IN_WORLD = "NOT_IN_WORLD";
    /**
     * A {@code GuiClickInput} whose oneof named neither a slot nor a recipe. Refused at the
     * point a click is applied, on top of the shape check that already rejected it inbound:
     * a command with no click is not a click that did nothing, it is a command that could not
     * be answered, and the safe answer is a named refusal rather than a silent fall-through.
     */
    public static final String REFUSED_MALFORMED_CLICK = "MALFORMED_CLICK";
    /** Not a refusal: the in-progress signal that accompanies a clamped turn. */
    public static final String AIM_IN_PROGRESS = "AIM_IN_PROGRESS";

    /** The last hotbar slot a {@code HotbarSelectInput} may name — the hotbar is nine. */
    public static final int MAX_HOTBAR_SLOT = 8;

    private static final float EPSILON_DEGREES = 1.0E-3F;

    private WorldActions() {}

    /**
     * Whether a command's capability was negotiated, or refused by name for not being.
     *
     * <p>A refusal and not a dropped connection: spec §1 makes the two directions of
     * the mistake matter — Core sending something it never agreed to, and the Bridge
     * honouring something it never accepted. The second is the dangerous one, so the
     * Bridge refuses by name; the first is Core's bug to see, and a named code in the
     * reply is how it becomes visible rather than silent.
     */
    public static Optional<String> capabilityRefusal(Set<String> granted, String required) {
        if (granted != null && required != null && granted.contains(required)) {
            return Optional.empty();
        }
        return Optional.of(REFUSED_CAPABILITY_NOT_GRANTED);
    }

    /**
     * One clamped step toward an absolute heading, and whether more steps are owed.
     *
     * <p>The turn is expressed as the delta the client's own look path consumes,
     * because that path is what clamps pitch to what a player could actually look at
     * and wraps yaw — writing an angle directly would be a second rule for the same
     * state and one the client would not know about.
     */
    public static AimStep clampAim(
            float currentYaw,
            float currentPitch,
            float targetYaw,
            float targetPitch) {
        float neededYaw = wrapDegrees(targetYaw - currentYaw);
        float neededPitch = clampPitch(targetPitch) - currentPitch;
        float appliedYaw = clampMagnitude(neededYaw, MAX_AIM_DEGREES_PER_COMMAND);
        float appliedPitch = clampMagnitude(neededPitch, MAX_AIM_DEGREES_PER_COMMAND);
        boolean inProgress =
                Math.abs(neededYaw - appliedYaw) > EPSILON_DEGREES
                        || Math.abs(neededPitch - appliedPitch) > EPSILON_DEGREES;
        return new AimStep(appliedYaw, appliedPitch, inProgress);
    }

    /**
     * Whether a hotbar slot is one of the nine the message is allowed to name.
     *
     * <p>Out of range refuses rather than wraps: this is the hotbar and not the whole
     * inventory, so a Kin that wants something outside it has to move it in the way a
     * player does.
     */
    public static Optional<String> hotbarRefusal(int slot) {
        if (slot < 0 || slot > MAX_HOTBAR_SLOT) {
            return Optional.of(REFUSED_HOTBAR_OUT_OF_RANGE);
        }
        return Optional.empty();
    }

    /**
     * Whether a {@code MineInput} still names the block the crosshair is on.
     *
     * <p>Checked and not believed. A plan written a moment ago against a block the
     * client has since looked away from must not break whatever is now in front of it,
     * so the target has to equal the block and face the client's own crosshair reports
     * this instant, or the command is refused by name.
     */
    public static Optional<String> mineTargetRefusal(
            BlockTarget requested, AimCrosshair current) {
        if (requested == null || current == null || current.kind() != CrosshairKind.BLOCK) {
            return Optional.of(REFUSED_MINE_TARGET_NOT_AIMED);
        }
        if (requested.getX() != current.x()
                || requested.getY() != current.y()
                || requested.getZ() != current.z()
                || requested.getFace() != current.face()) {
            return Optional.of(REFUSED_MINE_TARGET_NOT_AIMED);
        }
        return Optional.empty();
    }

    /**
     * Whether a GUI click's sync id still names the screen the client has open.
     *
     * <p>The contract forbids carrying a stale syncId into the next container, and the
     * client's own handler is the only authority on what its clicks land on. A click
     * against a screen that is no longer there, or with the id of one it replaced, is
     * refused before any packet goes out.
     */
    public static Optional<String> guiSyncIdRefusal(
            int requested, boolean screenOpen, int currentSyncId) {
        if (!screenOpen || requested != currentSyncId) {
            return Optional.of(REFUSED_GUI_SYNC_ID_MISMATCH);
        }
        return Optional.empty();
    }

    /**
     * Whether the client could resolve a recipe id against the rules this version has.
     *
     * <p>A name the Kin invented is not a recipe the server will honour, so an id that
     * resolves to nothing is refused by name rather than sent.
     */
    public static Optional<String> recipeRefusal(boolean recipeKnown) {
        return recipeKnown ? Optional.empty() : Optional.of(REFUSED_GUI_RECIPE_UNKNOWN);
    }

    /**
     * The crosshair reading as the wire spells it, and the one thing that decides it.
     *
     * <p>{@code NOT_READ} omits the whole target: the Bridge never looked. {@code MISS}
     * says it looked and found nothing. Collapsing the two would let a plan that never
     * aimed break a block it never saw, which is the exact failure the observation
     * surface exists to prevent.
     */
    public enum CrosshairKind {
        NOT_READ,
        MISS,
        BLOCK,
        ENTITY
    }

    /** One crosshair reading, already resolved to the fields the wire carries. */
    public record AimCrosshair(
            CrosshairKind kind,
            int x,
            int y,
            int z,
            BlockFace face,
            String targetedBlockId,
            String entityObservationId,
            String entityType,
            double distance) {

        public static AimCrosshair notRead() {
            return new AimCrosshair(CrosshairKind.NOT_READ, 0, 0, 0, BlockFace.BLOCK_FACE_UNKNOWN, "", "", "", 0.0);
        }

        public static AimCrosshair miss() {
            return new AimCrosshair(CrosshairKind.MISS, 0, 0, 0, BlockFace.BLOCK_FACE_UNKNOWN, "", "", "", 0.0);
        }
    }

    /**
     * One crosshair reading as an {@code AimTarget}, or absent when there was no read.
     *
     * <p>Only the branch the kind selects is filled, so a block reading never carries
     * an entity id and a miss carries neither — the reader can tell which it has from
     * the kind alone and not from guessing which fields happened to be zero.
     */
    public static Optional<AimTarget> aimTarget(AimCrosshair reading, long gameTick) {
        if (reading == null || reading.kind() == CrosshairKind.NOT_READ) {
            return Optional.empty();
        }
        AimTarget.Builder target = AimTarget.newBuilder().setGameTick(gameTick);
        switch (reading.kind()) {
            case MISS -> target.setKind(AimTargetKind.AIM_TARGET_KIND_MISS);
            case BLOCK -> {
                target.setKind(AimTargetKind.AIM_TARGET_KIND_BLOCK)
                        .setBlock(
                                BlockTarget.newBuilder()
                                        .setX(reading.x())
                                        .setY(reading.y())
                                        .setZ(reading.z())
                                        .setFace(reading.face()))
                        .setTargetedBlockId(reading.targetedBlockId())
                        .setDistance(reading.distance());
            }
            case ENTITY -> {
                target.setKind(AimTargetKind.AIM_TARGET_KIND_ENTITY)
                        .setEntityObservationId(reading.entityObservationId())
                        .setEntityType(reading.entityType())
                        .setDistance(reading.distance());
            }
            default -> {
                return Optional.empty();
            }
        }
        return Optional.of(target.build());
    }

    /**
     * The screen the client has open, and its handler id only when there is one, with the
     * recipe book's craftable set for that screen's grid.
     *
     * <p>{@code sync_id} is absent with no screen because sync id 0 is a real handler
     * (the player's own inventory) and cannot double as "there is none." A reader that
     * saw a 0 would believe a container were open when the game is taking keyboard
     * input. The craftable ids follow the same rule from the other side: with no screen
     * there is no grid the client is speaking for, so the set is empty and is only
     * carried while a screen is open.
     */
    public static GuiScreen guiScreen(
            String screenLabel, boolean screenOpen, int syncId, List<String> craftableRecipeIds) {
        GuiScreen.Builder screen =
                GuiScreen.newBuilder().setScreenId(screenLabel == null ? "" : screenLabel);
        if (screenOpen) {
            screen.setSyncId(syncId);
            screen.addAllCraftableRecipeIds(craftableRecipeIds);
        }
        return screen.build();
    }

    /** A clamped turn: the delta to apply and whether the heading is not yet reached. */
    public record AimStep(float deltaYaw, float deltaPitch, boolean inProgress) {}

    /** The client's own look angles, in its own units, read at a named instant. */
    public record LookAngles(float yawDegrees, float pitchDegrees) {

        /** Whether a real pair was read; a reader that has nothing must not report zero. */
        public static Optional<LookAngles> of(float yawDegrees, float pitchDegrees) {
            if (!Float.isFinite(yawDegrees) || !Float.isFinite(pitchDegrees)) {
                return Optional.empty();
            }
            return Optional.of(new LookAngles(wrapDegrees(yawDegrees), pitchDegrees));
        }
    }

    /**
     * The client's own break animation for the block it is hitting, as the wire spells it.
     *
     * <p>{@code progress} is clamped to {@code 0..1} here rather than trusted from the
     * read: it is the player-visible bar, and a value outside the bar is a reading error,
     * not a fact about a break that has finished twice over.
     */
    public static MiningProgress miningProgress(
            long gameTick, BlockTarget target, float progress) {
        float clamped = Math.max(0.0F, Math.min(1.0F, Float.isFinite(progress) ? progress : 0.0F));
        return MiningProgress.newBuilder()
                .setGameTick(gameTick)
                .setTarget(target)
                .setProgress(clamped)
                .build();
    }

    /** Wrap a signed angle difference into {@code (-180, 180]}, the shorter way round. */
    public static float wrapDegrees(float degrees) {
        float wrapped = degrees % 360.0F;
        while (wrapped > 180.0F) {
            wrapped -= 360.0F;
        }
        while (wrapped <= -180.0F) {
            wrapped += 360.0F;
        }
        return wrapped;
    }

    /** Clamp a pitch target to the range a player can look at: -90 straight up, 90 down. */
    public static float clampPitch(float pitch) {
        if (pitch < -90.0F) {
            return -90.0F;
        }
        return Math.min(pitch, 90.0F);
    }

    private static float clampMagnitude(float value, float limit) {
        return Math.max(-limit, Math.min(limit, value));
    }
}
