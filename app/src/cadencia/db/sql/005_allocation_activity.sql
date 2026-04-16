-- Bench/internal allocation activity fields.
-- focus: free-form description of what the person is working on.
-- activity_type: generic structural category.
-- stakeholder_id: optional link to a stakeholder (project owner, AM, client, etc.).
ALTER TABLE allocations ADD COLUMN focus TEXT;
ALTER TABLE allocations ADD COLUMN activity_type TEXT
    CHECK (activity_type IN ('training','collaboration','research','client_prep','other')
           OR activity_type IS NULL);
ALTER TABLE allocations ADD COLUMN stakeholder_id TEXT
    REFERENCES stakeholders(id) ON DELETE SET NULL;
