package org.minekin.bridge.host;

/**
 * Why a world is not published.
 *
 * <p>Local vocabulary, not wire vocabulary. The contract's event set has one failure
 * ({@code HOST_LAN_OPEN_FAILED}) and puts the reason in the Bridge's own log, so that
 * nothing Minecraft says reaches the product path. These tokens are what that line
 * carries, and they are closed on purpose: a reason nobody has measured yet does not
 * get to look like one that has.
 */
public enum LanRefusal {
    /** The client is in no world it hosts, so there is nothing to publish. */
    NOT_HOSTING,
    /** The client refused: it catches its own failure and returns false, silently. */
    BIND_FAILED,
    /** It said yes, and nothing can name where the world ended up. */
    NO_BOUND_ADDRESS
}
