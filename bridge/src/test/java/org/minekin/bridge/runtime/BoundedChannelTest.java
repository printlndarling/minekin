package org.minekin.bridge.runtime;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertFalse;

import java.util.ArrayList;
import java.util.List;
import java.util.concurrent.CountDownLatch;
import org.junit.jupiter.api.Test;

final class BoundedChannelTest {
    @Test
    void terminalReplacementWinsEveryRaceWithOrdinaryOffers() throws Exception {
        for (int attempt = 0; attempt < 1_000; attempt++) {
            BoundedChannel<String> channel = new BoundedChannel<>(2);
            CountDownLatch start = new CountDownLatch(1);
            Thread producer = new Thread(() -> {
                await(start);
                channel.offer("ordinary");
            });
            Thread terminator = new Thread(() -> {
                await(start);
                channel.replaceWith("safe-stop");
            });

            producer.start();
            terminator.start();
            start.countDown();
            producer.join();
            terminator.join();

            List<String> drained = new ArrayList<>();
            channel.drain(2, drained::add);
            assertEquals(List.of("safe-stop"), drained);
            assertFalse(channel.offer("late"));
        }
    }

    private static void await(CountDownLatch latch) {
        try {
            latch.await();
        } catch (InterruptedException error) {
            Thread.currentThread().interrupt();
            throw new AssertionError(error);
        }
    }
}
