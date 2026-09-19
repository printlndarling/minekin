package org.minekin.bridge.input;

/**
 * Where a key actually goes down or up.
 *
 * <p>The implementation that matters talks to Minecraft, whose input state
 * belongs to the client thread. Marshalling is the implementation's job rather
 * than the caller's, because the caller may be the watchdog — and the watchdog
 * is running precisely when something else is stuck.
 */
public interface KeySink {

    void press(String capability);

    void release(String capability);
}
