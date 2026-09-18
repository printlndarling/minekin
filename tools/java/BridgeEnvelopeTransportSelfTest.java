import com.google.protobuf.ByteString;
import io.minekin.protocol.v1.Channel;
import io.minekin.protocol.v1.Envelope;
import io.minekin.protocol.v1.ProtocolVersion;
import java.io.ByteArrayInputStream;
import java.io.ByteArrayOutputStream;
import java.nio.ByteBuffer;
import java.nio.channels.Channels;
import java.nio.channels.ReadableByteChannel;
import java.util.Set;
import org.minekin.bridge.protocol.EnvelopeGate;
import org.minekin.bridge.protocol.FrameCodec;
import org.minekin.bridge.protocol.FramedEnvelopeChannel;

/** Executable framing and envelope validation contract check. */
public final class BridgeEnvelopeTransportSelfTest {
    private static final int MAX_FRAME_BYTES = 1_048_576;
    private static final String TYPE = "minekin.v1.CoreHello";

    private BridgeEnvelopeTransportSelfTest() {}

    public static void main(String[] arguments) throws Exception {
        Envelope first = envelope(1);
        Envelope second = envelope(2);
        ByteArrayOutputStream bytes = new ByteArrayOutputStream();
        FramedEnvelopeChannel writer = new FramedEnvelopeChannel(
                Channels.newChannel(new ByteArrayInputStream(new byte[0])),
                Channels.newChannel(bytes),
                Channel.CHANNEL_CONTROL,
                MAX_FRAME_BYTES);
        writer.write(first);
        writer.write(second);

        ReadableByteChannel chunked = new ChunkedReader(bytes.toByteArray(), 3);
        FramedEnvelopeChannel reader = new FramedEnvelopeChannel(
                chunked,
                Channels.newChannel(new ByteArrayOutputStream()),
                Channel.CHANNEL_CONTROL,
                MAX_FRAME_BYTES);
        EnvelopeGate gate = new EnvelopeGate(
                new EnvelopeGate.Expected(1, 0, "kin-1", "session-1", 7, "client-1"),
                Channel.CHANNEL_CONTROL,
                Set.of(TYPE));
        Envelope decodedFirst = reader.read();
        Envelope decodedSecond = reader.read();
        assert decodedFirst.equals(first);
        assert decodedSecond.equals(second);
        gate.validate(decodedFirst);
        gate.validate(decodedSecond);

        assertRejected(() -> gate.validate(second), "replayed sequence was accepted");
        assertRejected(
                () -> new FramedEnvelopeChannel(
                                Channels.newChannel(new ByteArrayInputStream(new byte[0])),
                                Channels.newChannel(new ByteArrayOutputStream()),
                                Channel.CHANNEL_EVENT,
                                MAX_FRAME_BYTES)
                        .write(first),
                "cross-channel write was accepted");

        ByteBuffer oversized = ByteBuffer.allocate(4).putInt(MAX_FRAME_BYTES + 1).flip();
        assertRejected(
                () -> new FrameCodec.Decoder(MAX_FRAME_BYTES).accept(oversized, ignored -> {}),
                "oversized frame was accepted");
        System.out.println("Minekin Bridge envelope transport self-test: OK");
    }

    private static Envelope envelope(long sequence) {
        return Envelope.newBuilder()
                .setProtocol(ProtocolVersion.newBuilder().setMajor(1))
                .setMessageType(TYPE)
                .setChannel(Channel.CHANNEL_CONTROL)
                .setSequence(sequence)
                .setKinId("kin-1")
                .setSessionId("session-1")
                .setGeneration(7)
                .setClientInstanceId("client-1")
                .setMonotonicNs(sequence)
                .setPayload(ByteString.copyFromUtf8("payload"))
                .build();
    }

    private static void assertRejected(CheckedRunnable operation, String message) throws Exception {
        boolean rejected = false;
        try {
            operation.run();
        } catch (IllegalArgumentException expected) {
            rejected = true;
        }
        assert rejected : message;
    }

    @FunctionalInterface
    private interface CheckedRunnable {
        void run() throws Exception;
    }

    private static final class ChunkedReader implements ReadableByteChannel {
        private final byte[] bytes;
        private final int chunkSize;
        private int offset;
        private boolean open = true;

        private ChunkedReader(byte[] bytes, int chunkSize) {
            this.bytes = bytes.clone();
            this.chunkSize = chunkSize;
        }

        @Override
        public int read(ByteBuffer destination) {
            if (offset == bytes.length) {
                return -1;
            }
            int count = Math.min(Math.min(chunkSize, destination.remaining()), bytes.length - offset);
            destination.put(bytes, offset, count);
            offset += count;
            return count;
        }

        @Override
        public boolean isOpen() {
            return open;
        }

        @Override
        public void close() {
            open = false;
        }
    }
}
