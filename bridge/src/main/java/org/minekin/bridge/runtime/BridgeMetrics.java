package org.minekin.bridge.runtime;

import java.util.List;

/**
 * The Bridge's own cost on the client thread, in windows.
 *
 * <p>The contract asks the prototype to record callback wall time and its
 * P50/P95/P99, and separately forbids the IPC path from stalling the client thread.
 * Those are one requirement about one measurement: you cannot show the Bridge does
 * not stall the tick by measuring the tick from somewhere the tick does not run. So
 * the series are written from inside the callback and read on a cadence.
 *
 * <p>Two of them, because they answer two questions. {@code tick} is what the
 * Bridge's own callback body cost — the work this mod adds to the client's frame.
 * {@code tick_interval} is the period between one client tick and the next, which is
 * where everything else about the frame shows up: vanilla's tick, the renderer, a
 * garbage collection. A render-path stall and a Bridge-path stall are different
 * faults and only one of them is this repository's, so a single number could not
 * tell them apart — and a Bridge that measured only itself would report a healthy
 * budget while the client stalled for reasons it caused elsewhere.
 *
 * <p><b>A window that was built and not delivered is visible as a hole.</b> The
 * ordinal is taken when the window closes, not when it is published, so a reader
 * holding windows 1, 2 and 4 can see that 3 existed. That is deliberate rather than
 * incidental: the alternative is a shed counter travelling in a later message, which
 * is a second place for one fact and is lost entirely if the run ends first. The
 * reason a window goes missing is the publisher's — a full outbox — and it is logged
 * where it happens.
 *
 * <p>Dependency-free, so the repository's own JDK check can exercise it.
 */
public final class BridgeMetrics {
    /** What the Bridge's own client-tick callback body cost. */
    public static final String TICK_LABEL = "tick";

    /** The period between one client tick and the next. */
    public static final String INTERVAL_LABEL = "tick_interval";

    /** Ten seconds, which is the cadence the soak baseline already samples at. */
    public static final long DEFAULT_WINDOW_NANOS = 10_000_000_000L;

    private final CallbackBudget ticks;
    private final CallbackBudget intervals;
    private final long windowNanos;
    private long windowOpenedAt;
    private long window;
    private long lastTickAt;
    private boolean opened;

    public BridgeMetrics(int capacity, long windowNanos) {
        if (windowNanos <= 0) {
            throw new IllegalArgumentException("a window of " + windowNanos + "ns never closes");
        }
        this.ticks = new CallbackBudget(capacity);
        this.intervals = new CallbackBudget(capacity);
        this.windowNanos = windowNanos;
    }

    public static BridgeMetrics withDefaults() {
        // 4096 samples is over three minutes of ticks at twenty per second, and the
        // window is ten seconds: the ring is sized so a window cannot outrun it, and
        // a window that somehow does says so instead of silently keeping the tail.
        return new BridgeMetrics(4096, DEFAULT_WINDOW_NANOS);
    }

    /**
     * Records one client tick. Allocation-free, like the series it writes to.
     *
     * <p>Returns whether a window has closed and is waiting for {@link #takeWindows}.
     * The caller publishes it; this class does not, because whether a window can be
     * delivered is the channel's business and a metrics sampler that could fail a
     * session would be measuring the fault it causes.
     *
     * <p>The first tick of a run has no predecessor and so contributes no interval.
     * That is a missing sample rather than a zero one, and storing a zero would put a
     * fabricated minimum into a distribution whose whole job is to be believed.
     *
     * <p>{@code atNanos} is the instant the callback began, so the interval series is
     * the period between one tick and the next and not the idle time between two
     * callbacks. The period is the frame: it is what a stall lengthens, and measuring
     * around the callback instead would subtract exactly the cost under measurement.
     */
    public boolean recordTick(long durationNanos, long atNanos) {
        ticks.record(durationNanos);
        if (opened) {
            intervals.record(atNanos - lastTickAt);
        } else {
            opened = true;
            windowOpenedAt = atNanos;
        }
        lastTickAt = atNanos;
        return atNanos - windowOpenedAt >= windowNanos;
    }

    /**
     * The windows that have closed since the last read, and the next window opens.
     *
     * <p>Empty before the first window closes, which is not the same as a window that
     * held nothing: this is called on every tick that says a window closed, and only
     * those ticks get here.
     */
    public List<Snapshot> takeWindows() {
        window++;
        long openedAt = windowOpenedAt;
        windowOpenedAt = lastTickAt;
        CallbackBudget.Window tickWindow = ticks.take();
        CallbackBudget.Window intervalWindow = intervals.take();
        return List.of(
                new Snapshot(window, TICK_LABEL, openedAt, tickWindow.recorded(), tickWindow.nanos()),
                new Snapshot(
                        window,
                        INTERVAL_LABEL,
                        openedAt,
                        intervalWindow.recorded(),
                        intervalWindow.nanos()));
    }

    /** How many windows have closed, delivered or not. */
    public long windowCount() {
        return window;
    }

    /**
     * One series over one window.
     *
     * <p>{@code openedAtNanos} is this Bridge process's own clock and is not
     * comparable with anything outside it — the same rule the deadline translation in
     * {@link BridgeIpcWorker} lives under. It travels so that two windows of one run
     * can be ordered and sized against each other, and for no other purpose.
     */
    public record Snapshot(
            long window, String label, long openedAtNanos, long recorded, long[] nanos) {}
}
