package org.minekin.bridge.input;

/**
 * Where a key actually goes down or up.
 *
 * <p>The implementation that matters talks to Minecraft, whose input state
 * belongs to the client thread. Every caller must therefore invoke the sink on
 * that thread. Keeping this interface synchronous is deliberate: when a call
 * returns, the ownership ledger and the actual key binding describe the same
 * state; an asynchronously queued release must never be reported as completed.
 */
public interface KeySink {

    void press(String capability);

    void release(String capability);

    /**
     * Press and let go of one key, the way a hand taps it.
     *
     * <p>This is deliberately not {@code press} followed by {@code release}. Those two carry
     * the held state, which is what a movement key is about; a screen-opening key is not held,
     * and the client decides to open the window from the <em>edge</em> a real key event leaves
     * behind it. A sink that only writes the held state therefore never opens anything, and
     * the answer the caller gets back is a screen that is not there.
     */
    void tap(String capability);
}
