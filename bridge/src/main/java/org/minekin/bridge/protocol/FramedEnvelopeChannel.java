package org.minekin.bridge.protocol;

import com.google.protobuf.InvalidProtocolBufferException;
import io.minekin.protocol.v1.Channel;
import io.minekin.protocol.v1.Envelope;
import java.io.EOFException;
import java.io.IOException;
import java.nio.ByteBuffer;
import java.nio.channels.ReadableByteChannel;
import java.nio.channels.WritableByteChannel;
import java.util.ArrayDeque;
import java.util.Objects;

/** Blocking worker-thread transport for length-prefixed protobuf envelopes. */
public final class FramedEnvelopeChannel {
    private static final int READ_BUFFER_BYTES = 8 * 1024;
    private static final int MAX_BUFFERED_FRAMES = 32;

    private final ReadableByteChannel reader;
    private final WritableByteChannel writer;
    private final Channel channel;
    private final int maxFrameBytes;
    private final FrameCodec.Decoder decoder;
    private final ByteBuffer readBuffer = ByteBuffer.allocateDirect(READ_BUFFER_BYTES);
    private final ArrayDeque<Envelope> decoded = new ArrayDeque<>();

    public FramedEnvelopeChannel(
            ReadableByteChannel reader,
            WritableByteChannel writer,
            Channel channel,
            int maxFrameBytes) {
        this.reader = Objects.requireNonNull(reader, "reader");
        this.writer = Objects.requireNonNull(writer, "writer");
        this.channel = Objects.requireNonNull(channel, "channel");
        if (channel == Channel.CHANNEL_UNSPECIFIED) {
            throw new IllegalArgumentException("channel must be concrete");
        }
        this.maxFrameBytes = maxFrameBytes;
        decoder = new FrameCodec.Decoder(maxFrameBytes);
    }

    public synchronized void write(Envelope envelope) throws IOException {
        Objects.requireNonNull(envelope, "envelope");
        if (envelope.getChannel() != channel) {
            throw new IllegalArgumentException("envelope is assigned to the wrong IPC channel");
        }
        ByteBuffer frame = FrameCodec.encode(envelope.toByteArray(), maxFrameBytes);
        while (frame.hasRemaining()) {
            int count = writer.write(frame);
            if (count < 0) {
                throw new EOFException("IPC channel closed while writing a frame");
            }
            if (count == 0) {
                throw new IOException("blocking IPC write made no progress");
            }
        }
    }

    public synchronized Envelope read() throws IOException {
        Envelope ready = decoded.pollFirst();
        if (ready != null) {
            return ready;
        }
        while (true) {
            int count = reader.read(readBuffer);
            if (count < 0) {
                if (decoder.hasPartialFrame()) {
                    throw new EOFException("IPC channel closed with a partial frame");
                }
                throw new EOFException("IPC channel closed");
            }
            if (count == 0) {
                throw new IOException("blocking IPC read made no progress");
            }
            readBuffer.flip();
            try {
                decoder.accept(readBuffer, this::decode);
            } catch (IllegalArgumentException error) {
                throw new IOException("IPC frame length is invalid", error);
            } finally {
                readBuffer.compact();
            }
            ready = decoded.pollFirst();
            if (ready != null) {
                return ready;
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
