CREATE TABLE activities (
    id          TEXT PRIMARY KEY,
    owner_id    TEXT NOT NULL DEFAULT 'default',
    person_id   TEXT NOT NULL REFERENCES people(id),
    role        TEXT NOT NULL,
    power       TEXT,
    started_on  DATE NOT NULL,
    ended_on    DATE,
    notes       TEXT,
    created_at  TEXT NOT NULL,
    updated_at  TEXT NOT NULL
);
CREATE INDEX activities_person ON activities(person_id, owner_id);
