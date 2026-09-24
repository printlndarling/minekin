package org.minekin.bridge.runtime;

/**
 * One callback-time series, sampled where the callback runs and read on a cadence.
 *
 * <p>The prototype contract's budget entry asks for callback wall time and its
 * P50/P95/P99, and §6 forbids the IPC path from stalling the client thread — so the
 * two requirements meet in this class: {@link #record} runs inside the callback and
 * therefore does no allocation, takes no lock, performs no I/O and never grows, while
 * everything expensive happens in {@link #take}, which runs once per window rather
 * than once per sample.
 *
 * <p>Memory is the ring, and the ring is the whole of it: a run of ten minutes and a
 * run of ten hours retain the same number of samples. That is what makes the bound a
 * property of the code rather than a hope about the run, and it is the reason a
 * window that recorded more than it could retain says so — {@code recorded} counts
 * what arrived and {@code nanos.length} counts what is still there, so a series that
 * outran its ring is visible in the window it happened rather than averaged away.
 *
 * <p>Deliberately dependency-free, like {@link BoundedChannel}: the repository's own
 * {@code tools/check_bridge_protocol.py} compiles and exercises it on a plain JDK, so
 * the bound and the allocation-free record are checked without a Minecraft client.
 */
public final class CallbackBudget {
    private final long[] samples;
    private int next;
    private int held;
    private long recorded;

    public CallbackBudget(int capacity) {
        if (capacity <= 0) {
            throw new IllegalArgumentException("a budget of " + capacity + " samples retains nothing");
        }
        this.samples = new long[capacity];
    }

    /**
     * Records one duration, in the callback it measures.
     *
     * <p>No allocation, no lock, no I/O, no branch that grows anything: a fixed store
     * at a moving index. A negative duration is refused rather than stored, because a
     * clock that went backwards is not a measurement and a series that accepted one
     * would report a negative percentile somewhere downstream.
     */
    public void record(long durationNanos) {
        if (durationNanos < 0) {
            return;
        }
        samples[next] = durationNanos;
        next++;
        if (next == samples.length) {
            next = 0;
        }
        if (held < samples.length) {
            held++;
        }
        recorded++;
    }

    /**
     * The window's retained samples in record order, and a new window begins.
     *
     * <p>Allocates, and is meant to: this is the once-per-window read, not the
     * per-sample write. A window that retained fewer than it recorded returns the
     * most recent {@code capacity} of them — the ring keeps the newest, because the
     * tail is the part a stall shows up in.
     */
    public Window take() {
        long[] retained = new long[held];
        int start = (next - held + samples.length) % samples.length;
        for (int index = 0; index < held; index++) {
            retained[index] = samples[(start + index) % samples.length];
        }
        long windowRecorded = recorded;
        held = 0;
        next = 0;
        recorded = 0;
        return new Window(windowRecorded, retained);
    }

    /** How many samples one window can retain. Fixed for the life of the series. */
    public int capacity() {
        return samples.length;
    }

    /**
     * One window's worth of a series: what arrived, and what is still held.
     *
     * <p>{@code recorded - nanos.length} is how many the ring could not retain, and
     * it is derived rather than carried: a field for it could disagree with the two
     * it comes from.
     */
    public record Window(long recorded, long[] nanos) {}
}
