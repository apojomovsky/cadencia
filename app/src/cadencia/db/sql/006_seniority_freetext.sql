-- Remove the CHECK constraint on people.seniority so any short string is valid.
-- SQLite requires a full table rebuild to drop a CHECK constraint.

CREATE TABLE people_new (
    id          TEXT PRIMARY KEY,
    owner_id    TEXT NOT NULL DEFAULT 'default',
    name        TEXT NOT NULL,
    role        TEXT,
    seniority   TEXT,
    start_date  TEXT,
    status      TEXT NOT NULL DEFAULT 'active'
                     CHECK (status IN ('active', 'leaving', 'left')),
    created_at  TEXT NOT NULL,
    updated_at  TEXT NOT NULL,
    one_on_one_cadence_days  INTEGER,
    recurrence_weekday       INTEGER,
    recurrence_week_of_month INTEGER
);

INSERT INTO people_new
    SELECT id, owner_id, name, role, seniority, start_date, status,
           created_at, updated_at, one_on_one_cadence_days,
           recurrence_weekday, recurrence_week_of_month
    FROM people;

DROP TABLE people;

ALTER TABLE people_new RENAME TO people;

CREATE INDEX IF NOT EXISTS idx_people_owner_status ON people (owner_id, status);

CREATE INDEX IF NOT EXISTS idx_people_name ON people (name)
