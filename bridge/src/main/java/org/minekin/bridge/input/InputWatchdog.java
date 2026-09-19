package org.minekin.bridge.input;

/**
 * The Bridge's own silence detector, and the final release guarantee.
 *
 * <p>Contract §12 puts the last line of defence here rather than in Core: "Bridge
 * 本地 watchdog 才是最终松键保障。Core watchdog 是第二层。" Core can only stop
 * asking; it cannot press anything, so if Core goes away the keys stay down
 * unless the Bridge notices by itself.
 *
 * <p>It is armed by the first thing it hears, not by being constructed. A Bridge
 * whose IPC never came up has heard nothing and is not "on time" — the failure
 * this exists to catch is Core dying during startup, where no message ever
 * arrives and a watchdog that started counting at construction would be the only
 * thing that noticed.
 *
 * <p>Times are monotonic nanoseconds, and an observation that is older than the
 * last one is not new information: it neither counts nor extends the deadline.
 * Otherwise a single out-of-order arrival would look like a heartbeat.
 */
public final class InputWatchdog {

    private final long toleranceNanos;
    private long lastObservedNanos;
    private boolean armed;

    /**
     * @param intervalNanos how often Core said it would speak
     * @param toleratedMisses how many intervals of silence are allowed, which is
     *     more than one because a single missed interval is ordinary scheduling
     *     jitter rather than a reason to let go of the player's controls
     */
    public InputWatchdog(long intervalNanos, int toleratedMisses) {
        if (intervalNanos <= 0) {
            throw new IllegalArgumentException("intervalNanos must be positive");
        }
        if (toleratedMisses < 1) {
            throw new IllegalArgumentException("toleratedMisses must be at least one");
        }
        this.toleranceNanos = Math.multiplyExact(intervalNanos, (long) toleratedMisses);
    }

    /** Arms on the first observation, and records when this one arrived. */
    public synchronized void observe(long nowNanos) {
        armed = true;
        lastObservedNanos = Math.max(lastObservedNanos, nowNanos);
    }

    /** Stops the watchdog, for a session that ended on purpose. */
    public synchronized void disarm() {
        armed = false;
    }

    public synchronized boolean armed() {
        return armed;
    }

    /**
     * Whether silence has gone on long enough to let go of everything.
     *
     * <p>An unarmed watchdog is never expired, and the boundary is exclusive:
     * exactly the tolerated silence is still silence within tolerance.
     */
    public synchronized boolean expired(long nowNanos) {
        if (!armed || nowNanos <= lastObservedNanos) {
            return false;
        }
        return nowNanos - lastObservedNanos > toleranceNanos;
    }

    public synchronized long deadlineNanos() {
        return armed ? lastObservedNanos + toleranceNanos : 0L;
    }
}
