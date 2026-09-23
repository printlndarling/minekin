package org.minekin.bridge.runtime;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertTrue;

import io.minekin.protocol.v1.AdmissionFailureReason;
import io.minekin.protocol.v1.ConnectWorld;
import io.minekin.protocol.v1.ConnectionLifecycle;
import io.minekin.protocol.v1.ConnectionPhase;
import io.minekin.protocol.v1.InitialObservation;
import java.util.ArrayList;
import java.util.List;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;

/**
 * Which client event may be reported, and on whose behalf.
 *
 * <p>The client fires these events for every server it talks to, so the rule that
 * matters is not "which phase does this event mean" but "is this generation still
 * ours to speak for". Both halves are decided here without a client: what needs
 * Minecraft is starting a connection, not believing one.
 */
final class ClientAdmissionControllerTest {

    private static final long GENERATION = 7;
    private static final String PROFILE_ID = "p0-controlled";
    private static final String REVISION = "ab".repeat(32);

    private final List<ConnectionLifecycle> reported = new ArrayList<>();
    private final BridgePhaseMachine phases = new BridgePhaseMachine();
    private final List<InitialObservation> observed = new ArrayList<>();
    private final ClientAdmissionController controller = new ClientAdmissionController(
            phases,
            lifecycle -> {
                reported.add(lifecycle);
                return true;
            },
            observation -> {
                observed.add(observation);
                return true;
            });

    private void inWorld() {
        // Idempotent, because a terminal report already puts the machine back at
        // OBSERVE_ONLY — which is the state a second attempt legitimately starts
        // from, and not an illegal transition.
        if (phases.phase() != BridgePhaseMachine.Phase.OBSERVE_ONLY) {
            phases.transition(BridgePhaseMachine.Phase.IPC_CONNECTING);
            phases.transition(BridgePhaseMachine.Phase.OBSERVE_ONLY);
        }
    }

    private void beginAttempt() {
        inWorld();
        controller.beginGeneration(ConnectWorld.newBuilder()
                .setRequestId("connect-1")
                .setGeneration(GENERATION)
                .setServerProfileId(PROFILE_ID)
                .setServerProfileRevision(REVISION)
                .setOriginalHost("127.0.0.1")
                .setPort(25565)
                .build());
    }

    private ConnectionLifecycle only() {
        assertEquals(1, reported.size(), "exactly one report was expected");
        return reported.get(0);
    }

    @BeforeEach
    void startFromNoRememberedReason() {
        // The reason holder is static — it is how a mixin reaches a controller —
        // so every test states the state it starts from rather than inheriting
        // whatever the last one left.
        ClientAdmissionController.rememberDisconnectReason("");
    }

    @Test
    void theLoginPhasesAreReportedInTheOrderTheAttemptMoves() {
        beginAttempt();

        controller.loginNegotiating();
        controller.playInit();
        controller.joinSeen();

        assertEquals(3, reported.size());
        assertEquals(
                List.of(
                        ConnectionPhase.CONNECTION_PHASE_LOGIN_NEGOTIATING,
                        ConnectionPhase.CONNECTION_PHASE_PLAY_INIT,
                        ConnectionPhase.CONNECTION_PHASE_JOIN_SEEN),
                reported.stream().map(ConnectionLifecycle::getPhase).toList());
        for (ConnectionLifecycle lifecycle : reported) {
            assertEquals(GENERATION, lifecycle.getGeneration());
            assertEquals(PROFILE_ID, lifecycle.getServerProfileId());
            assertEquals(REVISION, lifecycle.getServerProfileRevision());
            assertEquals(
                    AdmissionFailureReason.ADMISSION_FAILURE_REASON_UNSPECIFIED,
                    lifecycle.getFailureReason());
            assertTrue(!lifecycle.getTerminal(), "only an ending is terminal");
        }
    }

    @Test
    void aLoginThatEndsWithoutJoiningIsAFailureWithAStableReason() {
        beginAttempt();

        controller.loginFailed();

        ConnectionLifecycle lifecycle = only();
        assertEquals(ConnectionPhase.CONNECTION_PHASE_FAILED, lifecycle.getPhase());
        assertEquals(
                AdmissionFailureReason.ADMISSION_FAILURE_REASON_UNEXPECTED_DISCONNECT,
                lifecycle.getFailureReason());
        assertTrue(lifecycle.getTerminal());
    }

    @Test
    void aLoginFailureWaitsForTheReasonFromItsOwnHandler() {
        Object handler = new Object();
        beginAttempt();
        controller.loginNegotiating(handler);
        reported.clear();

        controller.loginFailurePending(handler);
        controller.reportPendingLoginFailure();
        assertTrue(reported.isEmpty(), "the network event arrives before vanilla's reason callback");

        ClientAdmissionController.rememberLoginDisconnected(
                handler, "Failed to log in: Invalid session (Try restarting your game and the launcher)");
        controller.reportPendingLoginFailure();
        ConnectionLifecycle lifecycle = only();
        assertEquals(ConnectionPhase.CONNECTION_PHASE_FAILED, lifecycle.getPhase());
        assertEquals(
                AdmissionFailureReason.ADMISSION_FAILURE_REASON_AUTH_MODE_MISMATCH,
                lifecycle.getFailureReason());
        assertTrue(lifecycle.getTerminal());
    }

    @Test
    void aLateReasonFromAnotherHandlerCannotFinishTheCurrentLogin() {
        Object oldHandler = new Object();
        Object currentHandler = new Object();
        beginAttempt();
        controller.loginNegotiating(oldHandler);
        controller.loginFailed();
        reported.clear();

        beginAttempt();
        controller.loginNegotiating(currentHandler);
        reported.clear();
        controller.loginFailurePending(currentHandler);
        ClientAdmissionController.rememberLoginDisconnected(oldHandler, "Invalid session");
        controller.reportPendingLoginFailure();
        assertTrue(reported.isEmpty(), "another connection's reason cannot finish this one");

        ClientAdmissionController.rememberLoginDisconnected(currentHandler, "Server is restarting");
        controller.reportPendingLoginFailure();
        assertEquals(
                AdmissionFailureReason.ADMISSION_FAILURE_REASON_UNEXPECTED_DISCONNECT,
                only().getFailureReason());
    }

    @Test
    void aPlaySessionThatEndsIsADisconnectAndCarriesNoReason() {
        beginAttempt();
        controller.playInit();
        reported.clear();

        controller.playEnded();

        ConnectionLifecycle lifecycle = only();
        assertEquals(ConnectionPhase.CONNECTION_PHASE_DISCONNECTED, lifecycle.getPhase());
        assertEquals(
                AdmissionFailureReason.ADMISSION_FAILURE_REASON_UNSPECIFIED,
                lifecycle.getFailureReason());
        assertTrue(lifecycle.getTerminal());
    }

    @Test
    void aSessionTheServerEndedIsAFailureAndNotAPlainDisconnect() {
        // Measured: a duplicate login is delivered mid-session as a disconnect
        // packet carrying `You logged in from another location`. Reporting that
        // as DISCONNECTED would record a Kin the server threw out as one that
        // stopped on its own.
        beginAttempt();
        controller.playInit();
        controller.joinSeen();
        reported.clear();
        ClientAdmissionController.rememberDisconnectReason("You logged in from another location");

        controller.playEnded();

        ConnectionLifecycle lifecycle = only();
        assertEquals(ConnectionPhase.CONNECTION_PHASE_FAILED, lifecycle.getPhase());
        assertEquals(
                AdmissionFailureReason.ADMISSION_FAILURE_REASON_DUPLICATE_LOGIN,
                lifecycle.getFailureReason());
        assertTrue(lifecycle.getTerminal());
    }

    @Test
    void anEndingRetiresTheGenerationSoNoLaterEventSpeaksForIt() {
        beginAttempt();
        controller.loginFailed();
        reported.clear();

        // A late event from the connection that just ended must not be attributed
        // to it, and must not reopen it either.
        controller.playEnded();
        controller.joinSeen();

        assertEquals(List.of(), reported);
        assertEquals(BridgePhaseMachine.Phase.OBSERVE_ONLY, phases.phase());
    }

    @Test
    void anEventFromAnotherServerIsNotReported() {
        // No generation was ever begun: whatever the client connected to, this
        // Bridge did not ask for it.
        inWorld();

        controller.loginNegotiating();
        controller.playInit();
        controller.joinSeen();
        controller.loginFailed();
        controller.playEnded();

        assertEquals(List.of(), reported);
    }

    @Test
    void aServerReasonBecomesTheStableCategoryForIt() {
        // The exact sentence a vanilla 1.21.4 server sends, measured in the
        // controlled domain rather than invented here.
        assertEquals(
                AdmissionFailureReason.ADMISSION_FAILURE_REASON_WHITELIST_REJECTED,
                ClientAdmissionController.classifyDisconnect(
                        "You are not white-listed on this server!"));
        assertEquals(
                AdmissionFailureReason.ADMISSION_FAILURE_REASON_DUPLICATE_LOGIN,
                ClientAdmissionController.classifyDisconnect(
                        "You are already connected to this server!"));
        assertEquals(
                AdmissionFailureReason.ADMISSION_FAILURE_REASON_AUTH_MODE_MISMATCH,
                ClientAdmissionController.classifyDisconnect(
                        "Failed to verify username!"));
        assertEquals(
                AdmissionFailureReason.ADMISSION_FAILURE_REASON_AUTH_MODE_MISMATCH,
                ClientAdmissionController.classifyDisconnect(
                        "Failed to log in: Invalid session (Try restarting your game and the launcher)"));
        assertEquals(
                AdmissionFailureReason.ADMISSION_FAILURE_REASON_PROTOCOL_MISMATCH,
                ClientAdmissionController.classifyDisconnect("Outdated server!"));
    }

    @Test
    void aReasonNobodyRecognisesStaysUnclassified() {
        // A wrong category is a claim about the server that nobody made, so an
        // unknown sentence is an honest "unclassified" rather than a guess.
        assertEquals(
                AdmissionFailureReason.ADMISSION_FAILURE_REASON_UNEXPECTED_DISCONNECT,
                ClientAdmissionController.classifyDisconnect("Server is restarting, sorry!"));
        assertEquals(
                AdmissionFailureReason.ADMISSION_FAILURE_REASON_UNEXPECTED_DISCONNECT,
                ClientAdmissionController.classifyDisconnect(""));
        assertEquals(
                AdmissionFailureReason.ADMISSION_FAILURE_REASON_UNEXPECTED_DISCONNECT,
                ClientAdmissionController.classifyDisconnect(null));
    }

    @Test
    void aReasonIsClassifiedOnceAndThenForgotten() {
        beginAttempt();
        ClientAdmissionController.rememberDisconnectReason("You are not white-listed on this server!");
        controller.loginFailed();

        assertEquals(
                AdmissionFailureReason.ADMISSION_FAILURE_REASON_WHITELIST_REJECTED,
                only().getFailureReason());

        // The next attempt must not inherit the last one's reason: a rejection
        // attributed to a connection that never happened is worse than none.
        reported.clear();
        beginAttempt();
        controller.loginFailed();
        assertEquals(
                AdmissionFailureReason.ADMISSION_FAILURE_REASON_UNEXPECTED_DISCONNECT,
                only().getFailureReason());
    }

}
