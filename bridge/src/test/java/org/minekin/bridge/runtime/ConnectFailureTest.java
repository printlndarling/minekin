package org.minekin.bridge.runtime;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertFalse;

import io.minekin.protocol.v1.AdmissionFailureReason;
import java.net.ConnectException;
import java.net.SocketTimeoutException;
import java.net.UnknownHostException;
import java.util.Set;
import org.junit.jupiter.api.Test;

/**
 * The category a failed connection gets, from the exception itself.
 *
 * <p>These three never reach a login handler, so nothing else in the Bridge can
 * classify them: measured, a run against a closed port produced no Bridge line at
 * all. The exception's type is exact for all three, which is why the hook was
 * worth finding.
 *
 * <p>Each category is also checkable against the contract's table of stages, which
 * is what the refusal assertion below is for: a refusal must land in the TCP stage
 * and not in parse/resolve, because the connection was attempted.
 */
final class ConnectFailureTest {

    @Test
    void eachWayAConnectionCanFailHasItsOwnCategory() {
        assertEquals(
                AdmissionFailureReason.ADMISSION_FAILURE_REASON_DNS_FAILED,
                ConnectFailure.classify(new UnknownHostException("no.example.invalid")));
        assertEquals(
                AdmissionFailureReason.ADMISSION_FAILURE_REASON_CONNECT_TIMEOUT,
                ConnectFailure.classify(new SocketTimeoutException("connect timed out")));
        assertEquals(
                AdmissionFailureReason.ADMISSION_FAILURE_REASON_CONNECTION_REFUSED,
                ConnectFailure.classify(new ConnectException("Connection refused")));
    }

    @Test
    void aRefusalBelongsToTheTcpStageAndNotToParseOrResolve() {
        // The admission contract's table, as a set: these three are the reasons
        // whose necessary action is "no connection is created". A refusal can never
        // be one of them, because a refusal is what comes back from a connection
        // that was made.
        Set<AdmissionFailureReason> noConnectionWasCreated =
                Set.of(
                        AdmissionFailureReason.ADMISSION_FAILURE_REASON_ADDRESS_INVALID,
                        AdmissionFailureReason.ADMISSION_FAILURE_REASON_DNS_FAILED,
                        AdmissionFailureReason.ADMISSION_FAILURE_REASON_ADDRESS_POLICY_BLOCKED);

        AdmissionFailureReason refusal =
                ConnectFailure.classify(new ConnectException("Connection refused"));

        assertFalse(
                noConnectionWasCreated.contains(refusal),
                "a refusal means a connection was attempted, so it is not a resolve-stage reason");
    }

    @Test
    void aFailureNobodyRecognisesStaysUnclassified() {
        assertEquals(
                AdmissionFailureReason.ADMISSION_FAILURE_REASON_UNEXPECTED_DISCONNECT,
                ConnectFailure.classify(new IllegalStateException("something else")));
    }
}
