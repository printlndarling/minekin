package org.minekin.bridge.input;

import java.util.List;
import java.util.Objects;
import java.util.Set;
import java.util.TreeSet;

/**
 * The Bridge's whole input surface: one ledger, one watchdog, one sink.
 *
 * <p>Contract §12 gives the Bridge three duties and no more. It applies the
 * bounded movement a lease asks for; it keeps the pressed-key state; and when
 * anything goes wrong — IPC gone, generation moved, a screen took the keyboard,
 * Core went quiet, the Bridge's own fault, or the session leaving playable — it
 * lets go of everything it holds. Core can withdraw its intent, but only the
 * Bridge can lift a key.
 *
 * <p>Movement is applied as the *diff* against what is held, so a command is a
 * statement of where the player should be moving rather than a stream of presses:
 * a command that repeats what is already held presses nothing, and a command
 * that drops an axis releases exactly that axis. That is what makes letting go
 * complete — the ledger, not the last command, is what gets released.
 *
 * <p>Everything here is transient. Nothing is persisted, nothing is recovered,
 * and a new generation starts with an empty ledger.
 */
public final class BridgeInputController {

    /** Why the Bridge let go of the keys, for the log and for evidence. */
    public enum ReleaseReason {
        IPC_LOST,
        GENERATION_CHANGED,
        GUI_CONFLICT,
        TIMEOUT,
        BRIDGE_FAULT,
        CORE_REQUEST,
        LEFT_PLAYABLE,
        OPERATOR,
        SHUTDOWN
    }

    /** What a command did, in the terms the protocol reports it. */
    public record Outcome(boolean applied, String refusalCode, List<String> held) {
        static Outcome applied(List<String> held) {
            return new Outcome(true, "", List.copyOf(held));
        }

        static Outcome refused(String code) {
            return new Outcome(false, code, List.of());
        }
    }

    /** The capabilities a movement command can hold down. */
    public static final String FORWARD = "move.forward";
    public static final String BACK = "move.back";
    public static final String LEFT = "move.left";
    public static final String RIGHT = "move.right";
    public static final String JUMP = "move.jump";
    public static final String SNEAK = "move.sneak";

    public static final String REFUSED_STALE_GENERATION = "STALE_GENERATION";
    public static final String REFUSED_DEADLINE_EXCEEDED = "DEADLINE_EXCEEDED";
    public static final String REFUSED_MALFORMED = "MALFORMED_AXES";

    private final KeySink sink;
    private final InputWatchdog watchdog;
    private InputOwnership ownership;

    public BridgeInputController(KeySink sink, InputWatchdog watchdog, long generation) {
        this.sink = Objects.requireNonNull(sink, "sink");
        this.watchdog = Objects.requireNonNull(watchdog, "watchdog");
        this.ownership = new InputOwnership(generation);
    }

    public long generation() {
        return ownership.generation();
    }

    public List<String> held() {
        return ownership.held();
    }

    /** Any Core message is evidence that Core is alive. */
    public void observeCoreMessage(long nowNanos) {
        watchdog.observe(nowNanos);
    }

    /**
     * Applies a movement command, and answers for it.
     *
     * <p>The axes are refused rather than clamped when they are out of range or
     * not finite: a command the Bridge does not understand is not a command to
     * move a little, and quietly moving is the one thing input must never do.
     */
    public synchronized Outcome move(
            long nowNanos,
            long deadlineNanos,
            long generation,
            float forward,
            float strafe,
            boolean jump,
            boolean sneak) {
        observeCoreMessage(nowNanos);
        if (generation != ownership.generation()) {
            return Outcome.refused(REFUSED_STALE_GENERATION);
        }
        if (deadlineNanos != 0 && nowNanos > deadlineNanos) {
            return Outcome.refused(REFUSED_DEADLINE_EXCEEDED);
        }
        if (!axis(forward) || !axis(strafe)) {
            return Outcome.refused(REFUSED_MALFORMED);
        }
        Set<String> wanted = new TreeSet<>();
        if (forward > 0) {
            wanted.add(FORWARD);
        }
        if (forward < 0) {
            wanted.add(BACK);
        }
        if (strafe > 0) {
            wanted.add(RIGHT);
        }
        if (strafe < 0) {
            wanted.add(LEFT);
        }
        if (jump) {
            wanted.add(JUMP);
        }
        if (sneak) {
            wanted.add(SNEAK);
        }
        apply(wanted);
        return Outcome.applied(ownership.held());
    }

    /**
     * Releases everything held, for a named reason, and reports what that was.
     *
     * <p>The reason is the caller's, and it has to be the caller's: a fault in
     * the Bridge and a request from Core are different events with the same
     * effect, and a log that cannot tell them apart is a log that will be read
     * wrongly. Core's own words for why it withdrew travel beside the reason
     * rather than replacing it.
     *
     * <p>It reports even when the ledger is empty. A Bridge that believes it
     * holds nothing is not evidence that the client is holding nothing, and the
     * one caller that matters — the release path — is the last chance to say so.
     */
    public synchronized List<String> releaseAll(ReleaseReason reason) {
        Objects.requireNonNull(reason, "reason");
        // The worker records the reason after this synchronous state change;
        // the controller owns only the invariant that every held key is lifted.
        List<String> released = ownership.releaseAll();
        for (String capability : released) {
            sink.release(capability);
        }
        watchdog.disarm();
        return released;
    }

    /**
     * The watchdog's clock, from whatever thread is willing to run it.
     *
     * <p>Returns true when this tick was the one that let go, so a caller can
     * report it once rather than once per tick.
     */
    public synchronized boolean tick(long nowNanos) {
        if (!watchdog.expired(nowNanos)) {
            return false;
        }
        releaseAll(ReleaseReason.TIMEOUT);
        return true;
    }

    /** A new generation never inherits a key from the one that ended. */
    public synchronized List<String> beginGeneration(long generation) {
        List<String> released = releaseAll(ReleaseReason.GENERATION_CHANGED);
        ownership = new InputOwnership(generation);
        return released;
    }

    public boolean watchdogExpired(long nowNanos) {
        return watchdog.expired(nowNanos);
    }

    private void apply(Set<String> wanted) {
        Set<String> current = new TreeSet<>(ownership.held());
        for (String capability : wanted) {
            if (ownership.press(capability)) {
                sink.press(capability);
            }
        }
        for (String capability : current) {
            if (!wanted.contains(capability) && ownership.release(capability)) {
                sink.release(capability);
            }
        }
    }

    private static boolean axis(float value) {
        return Float.isFinite(value) && value >= -1.0f && value <= 1.0f;
    }
}
