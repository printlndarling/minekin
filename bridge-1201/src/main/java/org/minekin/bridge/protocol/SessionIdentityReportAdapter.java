package org.minekin.bridge.protocol;

import io.minekin.protocol.v1.SessionIdentityReport;
import java.util.UUID;

/**
 * Builds the redacted session report that travels with the hello and the first
 * snapshot.
 *
 * <p>Redaction here is structural rather than a filter. {@link ObservedSession}
 * has no component for the Access Token, the xuid value or the clientId value,
 * and {@code SessionIdentityReport} has no {@code bytes} field, so a credential
 * body cannot reach the wire even if a caller wants it to. The account type is
 * recorded verbatim instead of validated against the client enum, because the
 * point of the offline candidates is to find out which names the client accepts.
 */
public final class SessionIdentityReportAdapter {
    private SessionIdentityReportAdapter() {}

    public static SessionIdentityReport toProto(
            String identityCandidateId, ObservedSession observed) {
        // A blank candidate id is allowed, and it is the honest value from the
        // client: the candidate names the Launcher's reviewed strategy, which a
        // client cannot see — it sees the argv it was given. Core reads a blank
        // one as "no claim", and a *named* one that disagrees is still refused.
        if (identityCandidateId == null) {
            throw new IllegalArgumentException("identity candidate id must be a string");
        }
        if (observed.username().isBlank()) {
            throw new IllegalArgumentException("session username is required");
        }
        if (!isUuid(observed.uuid())) {
            throw new IllegalArgumentException("session uuid must be canonical or id128 form");
        }
        // A blank account type is allowed because it is an observation: the
        // client can carry none at all, and the candidate matrix is what finds
        // out which candidates it carries one for. An invented enum here would
        // record a value the client never held.
        return SessionIdentityReport.newBuilder()
                .setIdentityCandidateId(identityCandidateId)
                .setSessionUsername(observed.username())
                .setSessionUuid(observed.uuid())
                .setSessionAccountType(observed.accountType())
                .setSessionXuidPresent(observed.xuidPresent())
                .setSessionClientIdPresent(observed.clientIdPresent())
                .setCredentialValuesExposed(false)
                .build();
    }

    /** Reject a report that claims to carry credential bodies instead of trusting it. */
    public static void requireRedacted(SessionIdentityReport report) {
        if (report.getCredentialValuesExposed()) {
            throw new IllegalStateException("a session report claimed to expose credentials");
        }
    }

    private static boolean isUuid(String value) {
        try {
            UUID.fromString(value);
            return true;
        } catch (IllegalArgumentException notCanonical) {
            return value.matches("[0-9a-fA-F]{32}");
        }
    }

    /**
     * What the client thread is allowed to observe about the live Session. There
     * is deliberately no component for the Access Token, the xuid value or the
     * clientId value.
     */
    public record ObservedSession(
            String username,
            String uuid,
            String accountType,
            boolean xuidPresent,
            boolean clientIdPresent) {}
}
