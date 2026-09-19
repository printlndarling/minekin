package org.minekin.bridge.runtime;

import static org.junit.jupiter.api.Assertions.assertEquals;

import io.minekin.protocol.v1.AdmissionFailureReason;
import java.net.ConnectException;
import java.net.SocketTimeoutException;
import java.net.UnknownHostException;
import org.junit.jupiter.api.Test;

/**
 * The category a failed connection gets, from the exception itself.
 *
 * <p>These three never reach a login handler, so nothing else in the Bridge can
 * classify them: measured, a run against a closed port produced no Bridge line at
 * all. The exception's type is exact for all three, which is why the hook was
 * worth finding.
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
                AdmissionFailureReason.ADMISSION_FAILURE_REASON_ADDRESS_INVALID,
                ConnectFailure.classify(new ConnectException("Connection refused")));
    }

    @Test
    void aFailureNobodyRecognisesStaysUnclassified() {
        assertEquals(
                AdmissionFailureReason.ADMISSION_FAILURE_REASON_UNEXPECTED_DISCONNECT,
                ConnectFailure.classify(new IllegalStateException("something else")));
    }
}
