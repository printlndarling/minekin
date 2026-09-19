import io.minekin.protocol.v1.CancelConnection;
import io.minekin.protocol.v1.ConnectWorld;
import io.minekin.protocol.v1.ConnectionCancelReason;
import io.minekin.protocol.v1.ResourcePackPolicy;
import java.util.Set;
import org.minekin.bridge.protocol.AdmissionCommandGate;
import org.minekin.bridge.protocol.HandshakeGate;

/** Negative controls for the generation and capability gate ahead of the client thread. */
public final class AdmissionCommandGateSelfTest {
    private static final Set<String> CAPABILITIES = Set.of(HandshakeGate.ADMISSION_CAPABILITY);

    private AdmissionCommandGateSelfTest() {}

    public static void main(String[] arguments) {
        AdmissionCommandGate gate = new AdmissionCommandGate();
        expectRejected(() -> gate.acceptConnect(connect(1, "127.0.0.1"), Set.of()));
        expectRejected(() -> gate.acceptConnect(connect(2, "127.0.0.1"), CAPABILITIES));
        expectRejected(() -> gate.acceptConnect(connect(1, "example.com"), CAPABILITIES));

        gate.acceptConnect(connect(1, "127.0.0.1"), CAPABILITIES);
        assert gate.activeGeneration() == 1;
        expectRejected(() -> gate.acceptConnect(connect(2, "127.0.0.1"), CAPABILITIES));
        expectRejected(() -> gate.acceptCancel(cancel(2), CAPABILITIES));
        assert gate.activeGeneration() == 1;

        gate.acceptCancel(cancel(1), CAPABILITIES);
        assert gate.activeGeneration() == 0;
        expectRejected(() -> gate.acceptConnect(connect(1, "127.0.0.1"), CAPABILITIES));
        gate.acceptConnect(connect(2, "::1"), CAPABILITIES);
        assert gate.activeGeneration() == 2;
        System.out.println("Minekin admission command gate self-test: OK");
    }

    private static ConnectWorld connect(long generation, String host) {
        return ConnectWorld.newBuilder()
                .setRequestId("connect-" + generation)
                .setGeneration(generation)
                .setServerProfileId("p0-controlled")
                .setServerProfileRevision("ab".repeat(32))
                .setOriginalHost(host)
                .setPort(25565)
                .setResourcePackPolicy(ResourcePackPolicy.RESOURCE_PACK_POLICY_DENY)
                .setDeadlineMonotonicNs(1)
                .build();
    }

    private static CancelConnection cancel(long generation) {
        return CancelConnection.newBuilder()
                .setRequestId("cancel-" + generation)
                .setGeneration(generation)
                .setReason(ConnectionCancelReason.CONNECTION_CANCEL_REASON_OPERATOR)
                .build();
    }

    private static void expectRejected(Runnable operation) {
        try {
            operation.run();
            throw new AssertionError("invalid admission command was accepted");
        } catch (IllegalArgumentException expected) {
            // Expected negative control.
        }
    }
}
