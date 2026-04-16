-- Per-person 1:1 recurrence pattern fields.
-- recurrence_weekday: 0=Mon .. 6=Sun. NULL = no weekday constraint, just use interval.
-- recurrence_week_of_month: 1-4 = first/second/third/fourth, -1 = last.
--   Only relevant when recurrence_weekday is also set and cadence is monthly (28+ days).
--   NULL = use interval-based snapping (bi-weekly pattern).
ALTER TABLE people ADD COLUMN recurrence_weekday INTEGER;
ALTER TABLE people ADD COLUMN recurrence_week_of_month INTEGER;
