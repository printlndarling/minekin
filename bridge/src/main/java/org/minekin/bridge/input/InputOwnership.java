package org.minekin.bridge.input;

import java.util.List;
import java.util.Set;
import java.util.TreeSet;

/**
 * What this Bridge has pressed, and nothing else.
 *
 * <p>Contract §12 says the pressed-key state is transient by design: it is never
 * persisted and never recovered, so a Bridge that has just started owns nothing,
 * whatever the previous one was doing. This is that whole state.
 *
 * <p>It belongs to one generation. A new generation does not inherit a single
 * key from the old one — the owner releases the old ledger and makes a new one —
 * because a key pressed under a generation that has ended is exactly the kind of
 * thing that would be pressed forever.
 *
 * <p>Every mutation is idempotent. Pressing a key that is already held reports
 * that it changed nothing (the caller should not re-apply it), and releasing
 * everything twice returns the held set once and then nothing.
 */
public final class InputOwnership {

    private final long generation;
    private final Set<String> pressed = new TreeSet<>();

    public InputOwnership(long generation) {
        this.generation = generation;
    }

    public synchronized long generation() {
        return generation;
    }

    /** Records a press, and reports whether it changed anything. */
    public synchronized boolean press(String capability) {
        return pressed.add(require(capability));
    }

    /** Records a release, and reports whether it changed anything. */
    public synchronized boolean release(String capability) {
        return pressed.remove(require(capability));
    }

    /** Whether this Bridge believes the capability is being held right now. */
    public synchronized boolean holds(String capability) {
        return pressed.contains(require(capability));
    }

    /**
     * Releases everything and reports what was released, in a stable order.
     *
     * <p>Reported rather than merely cleared because the caller has to act on it:
     * what the ledger held is what the client has to be told to let go of, and a
     * ledger that forgot first would have nothing to say.
     */
    public synchronized List<String> releaseAll() {
        List<String> released = List.copyOf(pressed);
        pressed.clear();
        return released;
    }

    public synchronized int size() {
        return pressed.size();
    }

    /** What is held right now, in a stable order. */
    public synchronized List<String> held() {
        return List.copyOf(pressed);
    }

    private static String require(String capability) {
        if (capability == null || capability.isBlank()) {
            throw new IllegalArgumentException("capability is required");
        }
        return capability;
    }
}
