-- Stakeholders: account managers, clients, or any external party
-- relevant to a person's work.
CREATE TABLE IF NOT EXISTS stakeholders (
    id           TEXT PRIMARY KEY,
    owner_id     TEXT NOT NULL DEFAULT 'default',
    name         TEXT NOT NULL,
    type         TEXT NOT NULL DEFAULT 'other'
                      CHECK (type IN ('am', 'client', 'internal', 'other')),
    organization TEXT,
    email        TEXT,
    notes        TEXT,
    created_at   TEXT NOT NULL,
    updated_at   TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_stakeholders_owner ON stakeholders (owner_id);

CREATE TABLE IF NOT EXISTS stakeholder_feedback (
    id              TEXT PRIMARY KEY,
    owner_id        TEXT NOT NULL DEFAULT 'default',
    person_id       TEXT NOT NULL REFERENCES people(id) ON DELETE CASCADE,
    stakeholder_id  TEXT REFERENCES stakeholders(id) ON DELETE SET NULL,
    received_date   TEXT NOT NULL,
    content         TEXT NOT NULL,
    tags            TEXT NOT NULL DEFAULT '[]',
    created_at      TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_stakeholder_feedback_person
    ON stakeholder_feedback (person_id, received_date DESC);
CREATE INDEX IF NOT EXISTS idx_stakeholder_feedback_stakeholder
    ON stakeholder_feedback (stakeholder_id);
