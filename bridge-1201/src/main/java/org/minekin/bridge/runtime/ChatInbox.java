package org.minekin.bridge.runtime;

import java.util.ArrayDeque;
import java.util.ArrayList;
import java.util.Deque;
import java.util.List;

/**
 * A bounded inbox of the player chat the client heard, drained by the observation reader.
 *
 * <p>Chat is an episode, not a state: the recurring {@code WorldObservation} carries
 * what was heard since the previous one, so each line is delivered exactly once across
 * the stream. The ring is bounded ({@link #CAPACITY}) and one drain takes at most
 * {@link #DRAIN_LIMIT} lines, oldest first — conversation order — while the rest wait
 * for the next drain rather than being dropped. Only a flood that overflows the ring
 * loses lines, and it loses the oldest and counts them; the count rides with the next
 * drain as {@code chat_omitted}, because the contract's rule is that what is not
 * carried is stated, not implied.
 *
 * <p>Only the chat display type is ever recorded here — the caller decides what reaches
 * {@link #record}, and server/system text is deliberately not a caller: the wire
 * surface excludes it and nothing here invents a channel for it. The text is clipped
 * to {@link #MAX_TEXT_CHARS} with an ellipsis at entry, so a long line is carried
 * shorter rather than dropped.
 */
public final class ChatInbox {

    /** How many heard lines the ring holds between drains. */
    static final int CAPACITY = 16;
    /** How many lines one drain carries; the rest wait for the next one. */
    static final int DRAIN_LIMIT = 8;
    /** The longest line carried, the same bound the proto comment states. */
    static final int MAX_TEXT_CHARS = 256;

    /** One heard line: the tick it arrived at, who the game attributes it to, and what was said. */
    public record Line(long gameTick, String sender, String senderId, String text) {}

    /** One drain: the lines in arrival order (oldest first) and any overflow since the last drain. */
    public record Drain(List<Line> lines, int omitted) {}

    private static final Deque<Line> PENDING = new ArrayDeque<>();
    private static int dropped;

    private ChatInbox() {}

    /**
     * One heard line. A blank sender or a blank line is not a line: an
     * unattributable quote would make every later reader guess whose words it
     * is, and there is nothing to carry in an empty message. The account key is
     * an enhancement rather than the attribution itself: a blank one is fine
     * and rides as blank — the line stands on its name.
     */
    public static synchronized void record(long gameTick, String sender, String senderId, String text) {
        if (sender == null || sender.isBlank() || text == null || text.isBlank()) {
            return;
        }
        if (PENDING.size() >= CAPACITY) {
            PENDING.removeFirst();
            dropped++;
        }
        PENDING.addLast(new Line(gameTick, sender, senderId == null ? "" : senderId, clip(text)));
    }

    /** The lines heard since the previous drain, oldest first, plus the overflow count, which resets once reported. */
    public static synchronized Drain drain() {
        List<Line> lines = new ArrayList<>(Math.min(DRAIN_LIMIT, PENDING.size()));
        while (lines.size() < DRAIN_LIMIT && !PENDING.isEmpty()) {
            lines.add(PENDING.removeFirst());
        }
        int omitted = dropped;
        dropped = 0;
        return new Drain(List.copyOf(lines), omitted);
    }

    /**
     * Drop everything: called when a play session begins, so a previous session's
     * unread backlog cannot surface as this one's conversation.
     */
    public static synchronized void clear() {
        PENDING.clear();
        dropped = 0;
    }

    private static String clip(String text) {
        return text.length() <= MAX_TEXT_CHARS ? text : text.substring(0, MAX_TEXT_CHARS - 1) + "…";
    }
}
