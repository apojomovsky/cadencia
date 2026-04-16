-- Add per-person 1:1 cadence override.
-- NULL means: use the global default from ONE_ON_ONE_STALE_DAYS env var.
ALTER TABLE people ADD COLUMN one_on_one_cadence_days INTEGER;
