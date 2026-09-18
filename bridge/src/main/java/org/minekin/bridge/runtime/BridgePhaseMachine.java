package org.minekin.bridge.runtime;

import java.util.EnumMap;
import java.util.EnumSet;
import java.util.Map;
import java.util.Objects;

/** W20 lifecycle gate. OBSERVE_ONLY is the highest phase available before world admission. */
public final class BridgePhaseMachine {
    public enum Phase {
        MOD_LOADED,
        IPC_CONNECTING,
        OBSERVE_ONLY,
        CONNECTING_WORLD,
        PLAYABLE,
        SAFE_STOP
    }

    private static final Map<Phase, EnumSet<Phase>> ALLOWED = allowedTransitions();
    private Phase phase = Phase.MOD_LOADED;

    public synchronized Phase phase() {
        return phase;
    }

    public synchronized void transition(Phase next) {
        Objects.requireNonNull(next, "next");
        if (!ALLOWED.get(phase).contains(next)) {
            throw new IllegalStateException("illegal Bridge phase transition");
        }
        phase = next;
    }

    public synchronized void safeStop() {
        if (phase != Phase.SAFE_STOP) {
            phase = Phase.SAFE_STOP;
        }
    }

    public synchronized boolean permitsInput() {
        return false; // W20 is deliberately read-only in every phase.
    }

    private static Map<Phase, EnumSet<Phase>> allowedTransitions() {
        Map<Phase, EnumSet<Phase>> allowed = new EnumMap<>(Phase.class);
        allowed.put(Phase.MOD_LOADED, EnumSet.of(Phase.IPC_CONNECTING, Phase.SAFE_STOP));
        allowed.put(Phase.IPC_CONNECTING, EnumSet.of(Phase.OBSERVE_ONLY, Phase.SAFE_STOP));
        allowed.put(Phase.OBSERVE_ONLY, EnumSet.of(Phase.CONNECTING_WORLD, Phase.SAFE_STOP));
        allowed.put(
                Phase.CONNECTING_WORLD,
                EnumSet.of(Phase.PLAYABLE, Phase.OBSERVE_ONLY, Phase.SAFE_STOP));
        allowed.put(Phase.PLAYABLE, EnumSet.of(Phase.OBSERVE_ONLY, Phase.SAFE_STOP));
        allowed.put(Phase.SAFE_STOP, EnumSet.noneOf(Phase.class));
        return Map.copyOf(allowed);
    }
}
