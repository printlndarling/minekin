package org.minekin.bridge.mixin;

import io.netty.channel.ChannelFuture;
import net.minecraft.client.gui.screen.ConnectScreen;
import net.minecraft.network.ClientConnection;
import org.spongepowered.asm.mixin.Mixin;
import org.spongepowered.asm.mixin.gen.Accessor;

/** Version-pinned access to the same state used by ConnectScreen's Cancel button. */
@Mixin(ConnectScreen.class)
public interface ConnectScreenAccessor {
    @Accessor("connectingCancelled")
    void minekin$setConnectingCancelled(boolean cancelled);

    @Accessor("future")
    ChannelFuture minekin$getFuture();

    @Accessor("future")
    void minekin$setFuture(ChannelFuture future);

    @Accessor("connection")
    ClientConnection minekin$getConnection();
}
