-- The identity root: exactly one row, created only by an explicit init.
--
-- `kin_id` is the one column that never changes. The offline UUID is derived
-- from `username` by `uuid_algorithm` rather than stored, so a stored value
-- cannot disagree with the rule that produces it; the algorithm column exists so
-- a future rule change is visible instead of silently rewriting the identity.
--
-- There is no `active_run` or `last_session` here on purpose: those are
-- transient state that must not survive a restart.
CREATE TABLE kin_identity (
    singleton INTEGER PRIMARY KEY CHECK (singleton = 1),
    kin_id TEXT NOT NULL UNIQUE,
    local_profile_id TEXT NOT NULL,
    identity_revision INTEGER NOT NULL CHECK (identity_revision >= 1),
    username TEXT NOT NULL,
    uuid_algorithm TEXT NOT NULL,
    created_at_utc TEXT NOT NULL
) STRICT;
