-- Remove email from stakeholders. We don't track contact emails for anyone.
ALTER TABLE stakeholders DROP COLUMN email
