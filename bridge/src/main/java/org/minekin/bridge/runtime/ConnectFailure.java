package org.minekin.bridge.runtime;

import io.minekin.protocol.v1.AdmissionFailureReason;
import java.net.ConnectException;
import java.net.SocketTimeoutException;
import java.net.UnknownHostException;

/**
 * Which of the three ways a connection can fail this was, from the exception.
 *
 * <p>Exact rather than approximate, which is why the hook that finds it was worth
 * looking for: the netty exception a refusal carries is an
 * `AbstractChannel$AnnotatedConnectException`, and that is a `ConnectException`.
 * Classifying by the sentence instead would be classifying by a translation, and a
 * wrong category is a claim about the world that nobody made.
 *
 * <p>It is public and in its own class because a mixin's methods have to be
 * private, so the mixin cannot own a rule that is worth testing directly.
 */
public final class ConnectFailure {

    private ConnectFailure() {}

    public static AdmissionFailureReason classify(Exception failure) {
        if (failure instanceof UnknownHostException) {
            return AdmissionFailureReason.ADMISSION_FAILURE_REASON_DNS_FAILED;
        }
        if (failure instanceof SocketTimeoutException) {
            return AdmissionFailureReason.ADMISSION_FAILURE_REASON_CONNECT_TIMEOUT;
        }
        if (failure instanceof ConnectException) {
            return AdmissionFailureReason.ADMISSION_FAILURE_REASON_ADDRESS_INVALID;
        }
        return AdmissionFailureReason.ADMISSION_FAILURE_REASON_UNEXPECTED_DISCONNECT;
    }
}
