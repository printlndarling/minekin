package org.minekin.bridge.runtime;

import java.util.Objects;
import java.util.concurrent.ArrayBlockingQueue;
import java.util.concurrent.atomic.AtomicLong;
import java.util.function.Consumer;

/** Non-blocking bounded handoff used between IPC workers and the client tick. */
public final class BoundedChannel<T> {
    private final ArrayBlockingQueue<T> queue;
    private final AtomicLong rejected = new AtomicLong();

    public BoundedChannel(int capacity) {
        if (capacity < 1) {
            throw new IllegalArgumentException("capacity must be positive");
        }
        queue = new ArrayBlockingQueue<>(capacity);
    }

    public boolean offer(T value) {
        Objects.requireNonNull(value, "value");
        boolean accepted = queue.offer(value);
        if (!accepted) {
            rejected.incrementAndGet();
        }
        return accepted;
    }

    /** Drop queued work and guarantee one terminal safety message is next. */
    public synchronized void replaceWith(T value) {
        Objects.requireNonNull(value, "value");
        int dropped = queue.size();
        queue.clear();
        if (!queue.offer(value)) {
            throw new IllegalStateException("bounded channel could not accept terminal value");
        }
        rejected.addAndGet(dropped);
    }

    public int drain(int limit, Consumer<T> consumer) {
        Objects.requireNonNull(consumer, "consumer");
        if (limit < 0) {
            throw new IllegalArgumentException("limit cannot be negative");
        }
        int drained = 0;
        T value;
        while (drained < limit && (value = queue.poll()) != null) {
            consumer.accept(value);
            drained++;
        }
        return drained;
    }

    public int size() {
        return queue.size();
    }

    public long rejectedCount() {
        return rejected.get();
    }
}
