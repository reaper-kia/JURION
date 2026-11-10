\set ON_ERROR_STOP on
BEGIN;
SELECT pg_advisory_xact_lock(719337001);
CREATE TABLE IF NOT EXISTS jurion_schema_migrations (version text PRIMARY KEY, applied_at timestamptz NOT NULL DEFAULT now());
SELECT EXISTS (SELECT 1 FROM jurion_schema_migrations WHERE version = '001_init') AS already_applied \gset
\if :already_applied
  \echo 'Conversation migration 001_init already applied'
\else
  \ir /migrations/001_init.sql
  INSERT INTO jurion_schema_migrations(version) VALUES ('001_init');
\endif
COMMIT;
