#!/usr/bin/env bash
# ---------------------------------------------------------------------------
# Single data-root / single Kin exclusive guard primitives.
#
# Sourced by demo.sh (which sets the `command`, `LOCK_DIR` and `SECONDS_LIMIT`
# globals and owns the acquire/refuse/reclaim flow). They are kept in their own
# file so a behavioral test can drive the real functions in isolation, without
# launching a container. `take_kin_lock_once` installs its release trap in the
# sourcing shell, so sourcing preserves the same semantics the inline definitions
# had.
#
# Why mkdir and not flock: there is no `flock` on a Windows/MSYS runner, and
# `mkdir` is atomic on every host this runs on. A lock left by a wrapper killed
# before its EXIT trap ran must not wedge the store forever, so the lock is treated
# as fresh for one session window — a second run inside that window is refused, and
# past it the holder is presumed gone and the lock reclaimed. A lock whose owner
# line cannot be read fails closed (refused), never reclaimed.
# ---------------------------------------------------------------------------

write_lock_owner() {
    printf 'pid=%s\nepoch=%s\ncommand=%s\n' "$$" "$(date +%s)" "${command}" \
        > "${LOCK_DIR}/owner" 2>/dev/null || true
}

take_kin_lock_once() {
    if mkdir "${LOCK_DIR}" 2>/dev/null; then
        write_lock_owner
        trap 'rm -rf "${LOCK_DIR}"' EXIT INT TERM
        return 0
    fi
    return 1
}

held_lock_is_live() {
    local held_epoch now
    held_epoch="$(sed -n 's/^epoch=//p' "${LOCK_DIR}/owner" 2>/dev/null || true)"
    if [ -z "${held_epoch}" ]; then
        # No readable owner: not proof of a live holder and not proof of a dead one.
        # Fail closed — refuse rather than open one save in two sessions.
        return 0
    fi
    now="$(date +%s)"
    [ $(( now - held_epoch )) -le "${SECONDS_LIMIT}" ]
}
