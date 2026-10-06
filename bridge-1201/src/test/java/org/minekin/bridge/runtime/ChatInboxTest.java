package org.minekin.bridge.runtime;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertTrue;

import java.util.List;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;

final class ChatInboxTest {
    @BeforeEach
    void startEmpty() {
        ChatInbox.clear();
    }

    @Test
    void aDrainCarriesOldestFirstAndEachLineExactlyOnce() {
        ChatInbox.record(90L, "Alex", "", "one");
        ChatInbox.record(95L, "Steve", "", "two");

        ChatInbox.Drain first = ChatInbox.drain();

        assertEquals(
                List.of(
                        new ChatInbox.Line(90L, "Alex", "", "one"),
                        new ChatInbox.Line(95L, "Steve", "", "two")),
                first.lines());
        assertEquals(0, first.omitted());
        assertTrue(ChatInbox.drain().lines().isEmpty());
    }

    @Test
    void anAccountKeyRidesTheDrainBesideTheName() {
        // The stable anchor later memory uses. A blank key is legal — the line
        // stands on its name — and a null one is normalised to blank rather than
        // reaching the wire as a null-shaped value.
        ChatInbox.record(90L, "Alex", "f84c6a79-0a4e-45e0-879b-cd49ebd4c4e2", "keyed");
        ChatInbox.record(91L, "Steve", null, "unkeyed");

        ChatInbox.Drain drain = ChatInbox.drain();

        assertEquals("f84c6a79-0a4e-45e0-879b-cd49ebd4c4e2", drain.lines().get(0).senderId());
        assertEquals("", drain.lines().get(1).senderId());
    }

    @Test
    void oneDrainTakesTheLimitAndTheRestWaitInOrder() {
        for (int index = 0; index < ChatInbox.DRAIN_LIMIT + 2; index++) {
            ChatInbox.record(index, "Alex", "", "m" + index);
        }

        ChatInbox.Drain first = ChatInbox.drain();

        assertEquals(ChatInbox.DRAIN_LIMIT, first.lines().size());
        assertEquals("m0", first.lines().get(0).text());
        // Waiting for the next drain is not omission: the count stays zero.
        assertEquals(0, first.omitted());
        assertEquals(
                List.of("m8", "m9"),
                ChatInbox.drain().lines().stream().map(ChatInbox.Line::text).toList());
    }

    @Test
    void aFloodOverflowDropsTheOldestAndReportsItOnce() {
        for (int index = 0; index < ChatInbox.CAPACITY + 3; index++) {
            ChatInbox.record(index, "Alex", "", "m" + index);
        }

        ChatInbox.Drain first = ChatInbox.drain();

        // The three oldest lines fell out of the ring; the rest drain in order.
        assertEquals("m3", first.lines().get(0).text());
        assertEquals(3, first.omitted());
        ChatInbox.drain();
        assertEquals(0, ChatInbox.drain().omitted());
    }

    @Test
    void aBlankSenderOrAnEmptyLineIsNotALine() {
        ChatInbox.record(1L, "", "key", "no attribution");
        ChatInbox.record(2L, "   ", "key", "blank name");
        ChatInbox.record(3L, "Alex", "key", "");
        ChatInbox.record(4L, "Alex", "key", "fine");

        ChatInbox.Drain drain = ChatInbox.drain();

        assertEquals(List.of(new ChatInbox.Line(4L, "Alex", "key", "fine")), drain.lines());
        assertEquals(0, drain.omitted());
    }

    @Test
    void aLongLineIsClippedWithAnEllipsisNotDropped() {
        ChatInbox.record(1L, "Alex", "", "x".repeat(ChatInbox.MAX_TEXT_CHARS + 100));

        ChatInbox.Line line = ChatInbox.drain().lines().get(0);

        assertEquals(ChatInbox.MAX_TEXT_CHARS, line.text().length());
        assertTrue(line.text().endsWith("…"));
    }

    @Test
    void aClearDropsTheBacklogAndTheCountTogether() {
        for (int index = 0; index < ChatInbox.CAPACITY + 3; index++) {
            ChatInbox.record(index, "Alex", "", "m" + index);
        }

        ChatInbox.clear();

        ChatInbox.Drain after = ChatInbox.drain();
        assertTrue(after.lines().isEmpty());
        assertEquals(0, after.omitted());
    }
}
