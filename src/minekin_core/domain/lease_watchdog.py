"""Noticing a lease that has run out, and stopping the input because of it.

A lease is not a permission slip for one action; it is the whole authorisation to
drive the client, and it is granted with the moment it lapses already inside it.
This is what honours that moment. Without it, the deadline is a field that is
written and never read: the authorisation to hold a key would end when something
else happened to end it, which in practice means when the session ended — so a
"short move" would be exactly as long as the run.

It is deliberately not the arbiter. The arbiter answers "may this action be
applied now", a question asked by someone who wants to act. Nobody asks this one:
a lease that lapses while nothing is happening has to be *noticed*, and noticing
needs a clock rather than a caller.
"""

from __future__ import annotations

from minekin_core.domain.input_control import InputLease
from minekin_core.domain.time import MonotonicInstant


class LeaseWatchdog:
    """Holds at most one lease, and reports once when that lease has run out.

    It reports the lease rather than a verdict, because the caller is the only
    side that knows whether the lease it named is still the one in force — an
    expiry from an authorisation that was replaced a moment ago must not release
    the one that replaced it.
    """

    def __init__(self) -> None:
        self._lease: InputLease | None = None

    @property
    def armed(self) -> bool:
        return self._lease is not None

    @property
    def current(self) -> InputLease | None:
        return self._lease

    def arm(self, lease: InputLease) -> None:
        """Watch a lease. Arming replaces whatever was watched before.

        Replacement rather than accumulation: two leases cannot both be the one
        in force, and a watchdog holding both would have to pick a deadline by
        order of arrival rather than by what the arbiter granted.
        """

        self._lease = lease

    def disarm(self) -> None:
        """Stop watching, for authorisation the caller has already withdrawn."""

        self._lease = None

    def lapsed(self, now: MonotonicInstant) -> InputLease | None:
        """The lease that has run out, or `None` while there is still time.

        Reported once, because it stops watching what it reported: the second
        call after an expiry is not a second expiry, and a caller that released
        on every tick would send a release per tick. Clearing on report is what
        makes "once" true without the caller keeping a flag of its own.
        """

        lease = self._lease
        if lease is None or now.nanoseconds < lease.deadline_monotonic_ns:
            return None
        self._lease = None
        return lease
