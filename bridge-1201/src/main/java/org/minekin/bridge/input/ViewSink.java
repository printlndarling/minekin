package org.minekin.bridge.input;

/**
 * Where a look actually goes.
 *
 * <p>Separate from the key sink because a look is not a held key: it is one
 * bounded turn, applied and then over. There is nothing in the ownership ledger
 * for it and nothing to release, which is also why it cannot be the thing a Kin
 * keeps doing after something has gone wrong.
 *
 * <p>The implementation that matters hands the turn to the client's own look
 * path rather than writing an angle, so the client clamps and wraps it exactly
 * as it does for a mouse. Every caller must invoke this on the client thread,
 * for the same reason the key sink demands it.
 */
public interface ViewSink {

    /**
     * Turn the view by this many degrees.
     *
     * <p>Positives turn right and up, which is the sign the client's own look
     * uses; a caller with a different convention would be a caller inventing one.
     */
    void turn(float yawDegrees, float pitchDegrees);
}
