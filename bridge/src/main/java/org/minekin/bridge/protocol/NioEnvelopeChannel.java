package org.minekin.bridge.protocol;

import com.google.protobuf.InvalidProtocolBufferException;
import io.minekin.protocol.v1.Channel;
import io.minekin.protocol.v1.Envelope;
import java.io.EOFException;
import java.io.IOException;
import java.nio.ByteBuffer;
import java.nio.channels.SelectionKey;
import java.nio.channels.Selector;
import java.nio.channels.SocketChannel;
import java.time.Duration;
import java.util.ArrayDeque;
import java.util.Objects;

/** Deadline-aware nonblocking socket transport owned by one IPC worker. */
public final class NioEnvelopeChannel implements AutoCloseable {
    private static final int READ_BUFFER_BYTES = 8 * 1024;
    private static final int MAX_BUFFERED_FRAMES = 32;

    private final SocketChannel socket;
    private final Selector selector;
    private final SelectionKey key;
    private final Channel channel;
    private final int maxFrameBytes;
    private final FrameCodec.Decoder decoder;
    private final ByteBuffer readBuffer = ByteBuffer.allocateDirect(READ_BUFFER_BYTES);
    private final ArrayDeque<Envelope> decoded = new ArrayDeque<>();

    public NioEnvelopeChannel(SocketChannel socket, Channel channel, int maxFrameBytes)
            throws IOException {
        this.socket = Objects.requireNonNull(socket, "socket");
        this.channel = Objects.requireNonNull(channel, "channel");
        if (socket.isBlocking() || channel == Channel.CHANNEL_UNSPECIFIED) {
            throw new IllegalArgumentException("a nonblocking socket and concrete channel are required");
        }
        this.maxFrameBytes = maxFrameBytes;
        decoder = new FrameCodec.Decoder(maxFrameBytes);
        selector = Selector.open();
        key = socket.register(selector, 0);
    }

    public void write(Envelope envelope, Duration timeout) throws IOException {
        Objects.requireNonNull(envelope, "envelope");
        if (envelope.getChannel() != channel) {
            throw new IllegalArgumentException("envelope is assigned to the wrong IPC channel");
        }
        long deadline = EndpointConnector.deadline(timeout);
        ByteBuffer frame = FrameCodec.encode(envelope.toByteArray(), maxFrameBytes);
        while (frame.hasRemaining()) {
            if (socket.write(frame) == 0) {
                await(SelectionKey.OP_WRITE, deadline, "IPC frame write timed out");
            }
        }
    }

    public Envelope read(Duration timeout) throws IOException {
        long deadline = EndpointConnector.deadline(timeout);
        Envelope ready = decoded.pollFirst();
        while (ready == null) {
            int count = socket.read(readBuffer);
            if (count < 0) {
                throw new EOFException(decoder.hasPartialFrame()
                        ? "IPC channel closed with a partial frame"
                        : "IPC channel closed");
            }
            if (count == 0) {
                await(SelectionKey.OP_READ, deadline, "IPC frame read timed out");
                continue;
            }
            readBuffer.flip();
            try {
                decoder.accept(readBuffer, this::decode);
            } catch (IllegalArgumentException error) {
                throw new IOException("IPC frame is invalid", error);
            } finally {
                readBuffer.compact();
            }
            ready = decoded.pollFirst();
        }
        return ready;
    }

    @Override
    public void close() throws IOException {
        key.cancel();
        selector.close();
        socket.close();
    }

    private void await(int operation, long deadline, String message) throws IOException {
        key.interestOps(operation);
        try {
            EndpointConnector.await(selector, deadline, message);
        } finally {
            if (key.isValid()) {
                key.interestOps(0);
            }
        }
    }

    private void decode(byte[] payload) {
        if (decoded.size() >= MAX_BUFFERED_FRAMES) {
            throw new IllegalArgumentException("too many IPC frames arrived in one read");
        }
        try {
            Envelope envelope = Envelope.parseFrom(payload);
            if (envelope.getChannel() != channel) {
                throw new IllegalArgumentException("framed envelope uses the wrong IPC channel");
            }
            decoded.addLast(envelope);
        } catch (InvalidProtocolBufferException error) {
            throw new IllegalArgumentException("IPC frame is not a protobuf envelope", error);
        }
    }
}
