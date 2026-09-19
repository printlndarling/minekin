package org.minekin.bridge.input;

import static org.junit.jupiter.api.Assertions.assertFalse;
import static org.junit.jupiter.api.Assertions.assertThrows;
import static org.junit.jupiter.api.Assertions.assertTrue;

import org.junit.jupiter.api.Test;

/** The watchdog that has to notice Core going away without being told. */
final class InputWatchdogTest {

    private static final long INTERVAL = 1_000_000_000L; // one second
    private static final int MISSES = 3;

    private static InputWatchdog armed(long atNanos) {
        InputWatchdog watchdog = new InputWatchdog(INTERVAL, MISSES);
        watchdog.observe(atNanos);
        return watchdog;
    }

    @Test
    void aWatchdogThatHasHeardNothingNeverExpires() {
        InputWatchdog watchdog = new InputWatchdog(INTERVAL, MISSES);

        assertFalse(watchdog.armed());
        assertFalse(watchdog.expired(Long.MAX_VALUE / 2));
        assertFalse(
                watchdog.expired(Long.MAX_VALUE),
                "a Bridge that never heard Core has nothing to release, and a watchdog that "
                        + "fired anyway would report a timeout it never had");
    }

    @Test
    void silenceWithinToleranceIsSilenceWithinTolerance() {
        InputWatchdog watchdog = armed(0L);

        assertFalse(watchdog.expired(INTERVAL * MISSES));
        assertTrue(watchdog.expired(INTERVAL * MISSES + 1));
    }

    @Test
    void aFreshObservationMovesTheDeadline() {
        InputWatchdog watchdog = armed(0L);
        long now = INTERVAL * MISSES + 1;
        assertTrue(watchdog.expired(now));

        watchdog.observe(now);

        assertFalse(watchdog.expired(now));
        assertTrue(watchdog.expired(now + INTERVAL * MISSES + 1));
    }

    @Test
    void anOutOfOrderObservationIsNotNewInformation() {
        InputWatchdog watchdog = armed(INTERVAL * 10);

        watchdog.observe(INTERVAL);
        assertFalse(
                watchdog.expired(INTERVAL * 10),
                "an old arrival must not extend the deadline, which is what the Core-side "
                        + "watchdog also refuses to do with a stale timestamp");
        assertTrue(watchdog.expired(INTERVAL * 10 + INTERVAL * MISSES + 1));
    }

    @Test
    void aDisarmedWatchdogDoesNotExpire() {
        InputWatchdog watchdog = armed(0L);

        watchdog.disarm();

        assertFalse(watchdog.armed());
        assertFalse(watchdog.expired(INTERVAL * 100));
    }

    @Test
    void aWatchdogWithNoToleranceIsRefused() {
        assertThrows(IllegalArgumentException.class, () -> new InputWatchdog(INTERVAL, 0));
        assertThrows(IllegalArgumentException.class, () -> new InputWatchdog(0L, MISSES));
        assertThrows(IllegalArgumentException.class, () -> new InputWatchdog(-1L, MISSES));
    }
}
