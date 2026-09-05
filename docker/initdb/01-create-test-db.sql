-- Runs once, on first initialization of the data volume.
--
-- The test suite connects to a dedicated database so that a test run can never
-- touch development data. Creating it here means `docker compose up -d db` is
-- the only setup step required before `uv run poe test`.
--
-- If you recreate the volume (`docker compose down -v`), this runs again.
CREATE DATABASE app_test OWNER app;
