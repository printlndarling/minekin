PRAGMA application_id = 1296783694;

CREATE TABLE schema_version (
    singleton INTEGER PRIMARY KEY CHECK (singleton = 1),
    version INTEGER NOT NULL CHECK (version >= 1),
    applied_at_utc TEXT NOT NULL
) STRICT;

CREATE TABLE schema_migration (
    migration_id INTEGER PRIMARY KEY,
    from_version INTEGER NOT NULL,
    to_version INTEGER NOT NULL,
    application_version TEXT NOT NULL,
    started_at_utc TEXT NOT NULL,
    completed_at_utc TEXT,
    backup_ref TEXT
) STRICT;

CREATE TABLE event (
    position INTEGER PRIMARY KEY AUTOINCREMENT,
    event_id TEXT NOT NULL UNIQUE,
    event_type TEXT NOT NULL,
    schema_version INTEGER NOT NULL CHECK (schema_version >= 1),
    kin_id TEXT NOT NULL,
    run_id TEXT NOT NULL,
    client_instance_id TEXT,
    session_id TEXT,
    generation TEXT CHECK (
        generation IS NULL OR (
            generation NOT GLOB '*[^0-9]*' AND generation NOT LIKE '0%'
            AND length(generation) BETWEEN 1 AND 20
            AND (length(generation) < 20 OR generation <= '18446744073709551615')
        )
    ),
    world_context_id TEXT,
    sequence TEXT NOT NULL CHECK (
        sequence NOT GLOB '*[^0-9]*' AND sequence NOT LIKE '0%'
        AND length(sequence) BETWEEN 1 AND 20
        AND (length(sequence) < 20 OR sequence <= '18446744073709551615')
    ),
    correlation_id TEXT NOT NULL,
    causation_id TEXT,
    monotonic_ns INTEGER NOT NULL CHECK (monotonic_ns >= 0),
    observed_at_utc TEXT NOT NULL,
    source TEXT NOT NULL CHECK (source IN ('CORE', 'BRIDGE', 'LAUNCHER', 'OPERATOR_CLI')),
    trust_class TEXT NOT NULL,
    payload_json TEXT NOT NULL,
    payload_hash TEXT NOT NULL CHECK (
        length(payload_hash) = 64 AND payload_hash NOT GLOB '*[^0-9a-f]*'
    )
) STRICT;

CREATE INDEX event_kin_position ON event (kin_id, position);
CREATE INDEX event_session_position ON event (session_id, position);
CREATE INDEX event_correlation ON event (correlation_id);

CREATE TABLE outbox (
    outbox_id TEXT PRIMARY KEY,
    effect_type TEXT NOT NULL,
    idempotency_key TEXT NOT NULL UNIQUE,
    payload_json TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'pending'
        CHECK (status IN ('pending', 'completed', 'failed')),
    attempts INTEGER NOT NULL DEFAULT 0 CHECK (attempts >= 0),
    created_at_utc TEXT NOT NULL,
    completed_at_utc TEXT,
    last_error TEXT
) STRICT;

CREATE INDEX outbox_pending ON outbox (status, created_at_utc, outbox_id);

CREATE TABLE projection (
    projection_name TEXT NOT NULL,
    projection_key TEXT NOT NULL,
    last_event_position INTEGER NOT NULL CHECK (last_event_position >= 0),
    value_json TEXT NOT NULL,
    updated_at_utc TEXT NOT NULL,
    PRIMARY KEY (projection_name, projection_key)
) STRICT, WITHOUT ROWID;

PRAGMA user_version = 1;
