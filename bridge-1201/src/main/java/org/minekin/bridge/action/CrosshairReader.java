package org.minekin.bridge.action;

import io.minekin.protocol.v1.BlockFace;
import io.minekin.protocol.v1.BlockTarget;
import net.minecraft.client.MinecraftClient;
import net.minecraft.registry.Registries;
import net.minecraft.util.hit.BlockHitResult;
import net.minecraft.util.hit.EntityHitResult;
import net.minecraft.util.hit.HitResult;
import net.minecraft.util.math.BlockPos;
import net.minecraft.util.math.Direction;

/**
 * The client's own crosshair, read once and resolved to the wire's vocabulary.
 *
 * <p>This is the whole of the S2 observation surface for a target: one read of
 * {@code MinecraftClient.crosshairTarget}, the hit result vanilla already holds for what the
 * player is looking at. There is no ray cast of the Bridge's own and no scan of loaded
 * chunks — the contract is explicit that what a Kin may know about a block is what its
 * crosshair is on, and nothing behind or beside it. The block name it reports
 * ({@code targeted_block_id}) is exactly the line vanilla's own debug overlay shows a player
 * for the targeted block, so it grants no more than a person looking already has.
 *
 * <p>Every method must run on the client thread: a hit result is client-thread state.
 */
public final class CrosshairReader {

    private CrosshairReader() {}

    /**
     * The crosshair as the wire reads it, or {@code NOT_READ} when the client cannot look.
     *
     * <p>A client not in a world has no crosshair to read — that is {@code NOT_READ}, the
     * absence of the whole record, and it is kept distinct from {@code MISS} (looked, hit
     * nothing) for exactly the reason the contract gives: collapsing them would let a plan
     * that never aimed break a block it never saw.
     */
    public static WorldActions.AimCrosshair read(MinecraftClient client) {
        if (client == null || client.player == null || client.world == null) {
            return WorldActions.AimCrosshair.notRead();
        }
        HitResult hit = client.crosshairTarget;
        if (hit == null || hit.getType() == HitResult.Type.MISS) {
            return WorldActions.AimCrosshair.miss();
        }
        double distance = client.player.getEyePos().distanceTo(hit.getPos());
        if (hit instanceof BlockHitResult block) {
            BlockPos pos = block.getBlockPos();
            return new WorldActions.AimCrosshair(
                    WorldActions.CrosshairKind.BLOCK,
                    pos.getX(),
                    pos.getY(),
                    pos.getZ(),
                    toFace(block.getSide()),
                    Registries.BLOCK
                            .getId(client.world.getBlockState(pos).getBlock())
                            .toString(),
                    "",
                    "",
                    distance);
        }
        if (hit instanceof EntityHitResult entity) {
            return new WorldActions.AimCrosshair(
                    WorldActions.CrosshairKind.ENTITY,
                    0,
                    0,
                    0,
                    BlockFace.BLOCK_FACE_UNKNOWN,
                    "",
                    entity.getEntity().getUuid().toString(),
                    Registries.ENTITY_TYPE.getId(entity.getEntity().getType()).toString(),
                    distance);
        }
        // A hit result of a type this build does not resolve is "looked, hit nothing a Kin
        // may act on", which is a MISS and not a fabricated target.
        return WorldActions.AimCrosshair.miss();
    }

    /** The client's block hit, as the wire's {@code BlockTarget}: position and face only. */
    static BlockTarget blockTarget(BlockPos pos, Direction side) {
        return BlockTarget.newBuilder()
                .setX(pos.getX())
                .setY(pos.getY())
                .setZ(pos.getZ())
                .setFace(toFace(side))
                .build();
    }

    private static BlockFace toFace(Direction side) {
        if (side == null) {
            return BlockFace.BLOCK_FACE_UNKNOWN;
        }
        return switch (side) {
            case DOWN -> BlockFace.BLOCK_FACE_DOWN;
            case UP -> BlockFace.BLOCK_FACE_UP;
            case NORTH -> BlockFace.BLOCK_FACE_NORTH;
            case SOUTH -> BlockFace.BLOCK_FACE_SOUTH;
            case WEST -> BlockFace.BLOCK_FACE_WEST;
            case EAST -> BlockFace.BLOCK_FACE_EAST;
        };
    }
}
