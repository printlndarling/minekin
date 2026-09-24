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
 * <p>A refusal is its own reason and not `ADDRESS_INVALID`. The admission
 * contract's table separates the stages: parse/resolve failures mean no connection
 * was created, while a refusal is proof that one was attempted — the address
 * resolved, the policy allowed it, and nothing was listening. Filing it under
 * resolve would put a claim in the ledger that the client's own log contradicts
 * ("Connection refused"), and it would sit next to `ADDRESS_POLICY_BLOCKED` as if
 * this client had refused an address it had in fact dialed.
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
            return AdmissionFailureReason.ADMISSION_FAILURE_REASON_CONNECTION_REFUSED;
        }
        return AdmissionFailureReason.ADMISSION_FAILURE_REASON_UNEXPECTED_DISCONNECT;
    }
}
