-- Cadencia initial schema
-- All datetimes stored as ISO 8601 UTC text. All PKs are UUIDs (TEXT).
-- Foreign keys enforced at connection time via PRAGMA foreign_keys = ON.

CREATE TABLE IF NOT EXISTS people (
    id          TEXT PRIMARY KEY,
    owner_id    TEXT NOT NULL DEFAULT 'default',
    name        TEXT NOT NULL,
    role        TEXT,
    seniority   TEXT CHECK (seniority IN ('P1', 'P2', 'P3') OR seniority IS NULL),
    start_date  TEXT,
    status      TEXT NOT NULL DEFAULT 'active'
                     CHECK (status IN ('active', 'leaving', 'left')),
    created_at  TEXT NOT NULL,
    updated_at  TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_people_owner_status ON people (owner_id, status);
CREATE INDEX IF NOT EXISTS idx_people_name ON people (name);

CREATE TABLE IF NOT EXISTS observations (
    id          TEXT PRIMARY KEY,
    owner_id    TEXT NOT NULL DEFAULT 'default',
    person_id   TEXT NOT NULL REFERENCES people(id) ON DELETE CASCADE,
    observed_at TEXT NOT NULL,
    created_at  TEXT NOT NULL,
    text        TEXT NOT NULL,
    tags        TEXT NOT NULL DEFAULT '[]',
    source      TEXT NOT NULL DEFAULT 'manual'
                     CHECK (source IN ('manual', 'one_on_one', 'mcp', 'imported')),
    sensitivity TEXT NOT NULL DEFAULT 'normal'
                     CHECK (sensitivity IN ('normal', 'personal', 'confidential'))
);

CREATE INDEX IF NOT EXISTS idx_observations_person ON observations (person_id, observed_at DESC);
CREATE INDEX IF NOT EXISTS idx_observations_owner  ON observations (owner_id);

CREATE TABLE IF NOT EXISTS one_on_ones (
    id              TEXT PRIMARY KEY,
    owner_id        TEXT NOT NULL DEFAULT 'default',
    person_id       TEXT NOT NULL REFERENCES people(id) ON DELETE CASCADE,
    scheduled_date  TEXT NOT NULL,
    completed       INTEGER NOT NULL DEFAULT 0 CHECK (completed IN (0, 1)),
    notes           TEXT,
    created_at      TEXT NOT NULL,
    updated_at      TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_one_on_ones_person ON one_on_ones (person_id, scheduled_date DESC);

CREATE TABLE IF NOT EXISTS action_items (
    id                      TEXT PRIMARY KEY,
    owner_id                TEXT NOT NULL DEFAULT 'default',
    person_id               TEXT NOT NULL REFERENCES people(id) ON DELETE CASCADE,
    source_one_on_one_id    TEXT REFERENCES one_on_ones(id) ON DELETE SET NULL,
    text                    TEXT NOT NULL,
    owner_role              TEXT NOT NULL DEFAULT 'manager'
                                 CHECK (owner_role IN ('manager', 'report')),
    due_date                TEXT,
    status                  TEXT NOT NULL DEFAULT 'open'
                                 CHECK (status IN ('open', 'done', 'dropped')),
    created_at              TEXT NOT NULL,
    completed_at            TEXT
);

CREATE INDEX IF NOT EXISTS idx_action_items_person ON action_items (person_id, status);
CREATE INDEX IF NOT EXISTS idx_action_items_status ON action_items (status, due_date);

CREATE TABLE IF NOT EXISTS allocations (
    id                  TEXT PRIMARY KEY,
    owner_id            TEXT NOT NULL DEFAULT 'default',
    person_id           TEXT NOT NULL REFERENCES people(id) ON DELETE CASCADE,
    type                TEXT NOT NULL CHECK (type IN ('client', 'internal', 'bench')),
    client_or_project   TEXT,
    percent             INTEGER CHECK (percent IS NULL OR (percent >= 0 AND percent <= 100)),
    rate_band           TEXT CHECK (rate_band IN ('P1', 'P2', 'P3') OR rate_band IS NULL),
    start_date          TEXT NOT NULL,
    end_date            TEXT,
    last_confirmed_date TEXT NOT NULL,
    notes               TEXT,
    created_at          TEXT NOT NULL,
    updated_at          TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_allocations_person ON allocations (person_id, end_date);
CREATE INDEX IF NOT EXISTS idx_allocations_current ON allocations (person_id)
    WHERE end_date IS NULL;

-- Migration tracking table (managed by the migration runner, not manually)
CREATE TABLE IF NOT EXISTS _migrations (
    id          TEXT PRIMARY KEY,
    applied_at  TEXT NOT NULL
);
