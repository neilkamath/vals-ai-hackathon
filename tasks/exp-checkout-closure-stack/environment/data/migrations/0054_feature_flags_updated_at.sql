-- housekeeping
ALTER TABLE feature_flags ALTER COLUMN updated_at SET DEFAULT 'unknown';
