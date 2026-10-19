-- Run once as the PostgreSQL administrator on a new dedicated database.
-- Enter the password interactively with psql \password minobr_app afterwards.
CREATE ROLE minobr_app LOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE NOREPLICATION;
CREATE DATABASE minobr OWNER minobr_app;
\connect minobr
REVOKE CREATE ON SCHEMA public FROM PUBLIC;
GRANT USAGE, CREATE ON SCHEMA public TO minobr_app;
-- Ownership is needed by the migration account. No cluster-wide privileges.
-- Production must not grant CREATEDB just to run tests: use a separate test cluster.
