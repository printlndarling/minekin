package org.minekin.bridge.runtime;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertTrue;

import io.minekin.protocol.v1.AdmissionFailureReason;
import io.minekin.protocol.v1.ConnectWorld;
import io.minekin.protocol.v1.ConnectionLifecycle;
import io.minekin.protocol.v1.ConnectionPhase;
import java.util.ArrayList;
import java.util.List;
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
    private final ClientAdmissionController controller =
            new ClientAdmissionController(phases, lifecycle -> {
                reported.add(lifecycle);
                return true;
            });

    private void inWorld() {
        phases.transition(BridgePhaseMachine.Phase.IPC_CONNECTING);
        phases.transition(BridgePhaseMachine.Phase.OBSERVE_ONLY);
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
}
