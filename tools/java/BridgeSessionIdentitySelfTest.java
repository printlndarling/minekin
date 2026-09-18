import io.minekin.protocol.v1.SessionIdentityReport;
import java.lang.reflect.RecordComponent;
import java.util.Arrays;
import java.util.Locale;
import java.util.Set;
import java.util.stream.Collectors;
import org.minekin.bridge.protocol.SessionIdentityReportAdapter;
import org.minekin.bridge.protocol.SessionIdentityReportAdapter.ObservedSession;

/**
 * Proves the session report cannot carry a credential body.
 *
 * <p>The shape of the message itself is asserted in Python against the shipped
 * descriptor, because protobuf-javalite does not ship {@code Descriptors}.
 */
public final class BridgeSessionIdentitySelfTest {
    private static final Set<String> REVIEWED_OBSERVATIONS =
            Set.of("username", "uuid", "accountType", "xuidPresent", "clientIdPresent");

    private BridgeSessionIdentitySelfTest() {}

    public static void main(String[] arguments) {
        reportCarriesTheReviewedObservations();
        theAdapterCannotBeHandedACredentialBody();
        malformedObservationsAreRejected();
        aReportClaimingExposureIsRefused();
        System.out.println("Minekin Bridge session identity self-test: OK");
    }

    private static void reportCarriesTheReviewedObservations() {
        SessionIdentityReport report = SessionIdentityReportAdapter.toProto(
                "prism-parity",
                new ObservedSession(
                        "Kin", "8f40376b-c23f-3ef1-b553-5564eea75639", "LEGACY", false, false));
        SessionIdentityReportAdapter.requireRedacted(report);
        assert report.getIdentityCandidateId().equals("prism-parity");
        assert report.getSessionUsername().equals("Kin");
        assert report.getSessionUuid().equals("8f40376b-c23f-3ef1-b553-5564eea75639");
        assert report.getSessionAccountType().equals("LEGACY");
        assert !report.getSessionXuidPresent();
        assert !report.getSessionClientIdPresent();
        assert !report.getCredentialValuesExposed();

        SessionIdentityReport id128 = SessionIdentityReportAdapter.toProto(
                "enum-aligned",
                new ObservedSession(
                        "Kin", "8f40376bc23f3ef1b5535564eea75639", "offline", true, true));
        assert id128.getSessionUuid().equals("8f40376bc23f3ef1b5535564eea75639");
        assert id128.getSessionAccountType().equals("offline");
        assert id128.getSessionXuidPresent();
        assert id128.getSessionClientIdPresent();
    }

    private static void theAdapterCannotBeHandedACredentialBody() {
        Set<String> components =
                Arrays.stream(ObservedSession.class.getRecordComponents())
                        .map(RecordComponent::getName)
                        .collect(Collectors.toUnmodifiableSet());
        assert components.equals(REVIEWED_OBSERVATIONS)
                : "observed session components drifted: " + components;
        for (String component : components) {
            String lowered = component.toLowerCase(Locale.ROOT);
            assert !lowered.contains("token")
                            && !lowered.contains("secret")
                            && !lowered.contains("key")
                    : "a credential component appeared: " + component;
        }
    }

    private static void malformedObservationsAreRejected() {
        expectRejected(() -> SessionIdentityReportAdapter.toProto(
                " ",
                new ObservedSession(
                        "Kin", "8f40376b-c23f-3ef1-b553-5564eea75639", "LEGACY", false, false)));
        expectRejected(() -> SessionIdentityReportAdapter.toProto(
                "prism-parity",
                new ObservedSession(
                        "", "8f40376b-c23f-3ef1-b553-5564eea75639", "LEGACY", false, false)));
        expectRejected(() -> SessionIdentityReportAdapter.toProto(
                "prism-parity", new ObservedSession("Kin", "not-a-uuid", "LEGACY", false, false)));
        expectRejected(() -> SessionIdentityReportAdapter.toProto(
                "prism-parity",
                new ObservedSession(
                        "Kin", "8f40376b-c23f-3ef1-b553-5564eea75639", "", false, false)));
    }

    private static void aReportClaimingExposureIsRefused() {
        SessionIdentityReport exposed = SessionIdentityReport.newBuilder()
                .setIdentityCandidateId("prism-parity")
                .setSessionUsername("Kin")
                .setSessionUuid("8f40376b-c23f-3ef1-b553-5564eea75639")
                .setSessionAccountType("LEGACY")
                .setCredentialValuesExposed(true)
                .build();
        boolean refused = false;
        try {
            SessionIdentityReportAdapter.requireRedacted(exposed);
        } catch (IllegalStateException expected) {
            refused = true;
        }
        assert refused : "a report claiming to expose credentials was accepted";
    }

    private static void expectRejected(Runnable operation) {
        try {
            operation.run();
            throw new AssertionError("expected the report builder to fail closed");
        } catch (IllegalArgumentException expected) {
            // Expected fail-closed result.
        }
    }
}
