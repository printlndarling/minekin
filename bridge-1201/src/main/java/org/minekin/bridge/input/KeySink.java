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
}
