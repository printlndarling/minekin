package org.minekin.bridge.protocol;

import java.nio.ByteBuffer;
import java.nio.ByteOrder;
import java.util.Objects;
import java.util.function.Consumer;

/** Four-byte network-order length framing with a fail-closed allocation bound. */
public final class FrameCodec {
    private FrameCodec() {}

    public static ByteBuffer encode(byte[] payload, int maxFrameBytes) {
        Objects.requireNonNull(payload, "payload");
        validateLength(payload.length, maxFrameBytes);
        return ByteBuffer.allocate(Integer.BYTES + payload.length)
                .order(ByteOrder.BIG_ENDIAN)
                .putInt(payload.length)
                .put(payload)
                .flip();
    }

    private static void validateLength(int length, int maxFrameBytes) {
        if (maxFrameBytes < 1) {
            throw new IllegalArgumentException("maxFrameBytes must be positive");
        }
        if (length < 1 || length > maxFrameBytes) {
            throw new IllegalArgumentException("frame length is outside the configured bound");
        }
    }

    /** Incremental decoder. One instance belongs to exactly one channel connection. */
    public static final class Decoder {
        private final int maxFrameBytes;
        private final ByteBuffer header = ByteBuffer.allocate(Integer.BYTES).order(ByteOrder.BIG_ENDIAN);
        private ByteBuffer payload;

        public Decoder(int maxFrameBytes) {
            if (maxFrameBytes < 1) {
                throw new IllegalArgumentException("maxFrameBytes must be positive");
            }
            this.maxFrameBytes = maxFrameBytes;
        }

        public void accept(ByteBuffer source, Consumer<byte[]> sink) {
            Objects.requireNonNull(source, "source");
            Objects.requireNonNull(sink, "sink");
            while (source.hasRemaining()) {
                if (payload == null) {
                    transfer(source, header);
                    if (header.hasRemaining()) {
                        return;
                    }
                    header.flip();
                    int length = header.getInt();
                    header.clear();
                    validateLength(length, maxFrameBytes);
                    payload = ByteBuffer.allocate(length);
                }
                transfer(source, payload);
                if (!payload.hasRemaining()) {
                    sink.accept(payload.array());
                    payload = null;
                }
            }
        }

        public boolean hasPartialFrame() {
            return header.position() != 0 || payload != null;
        }

        private static void transfer(ByteBuffer source, ByteBuffer destination) {
            int count = Math.min(source.remaining(), destination.remaining());
            int originalLimit = source.limit();
            source.limit(source.position() + count);
            destination.put(source);
            source.limit(originalLimit);
        }
    }
}
