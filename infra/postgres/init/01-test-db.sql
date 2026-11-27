-- First start of the local compose db only (SCRUM-32): the database `uv run pytest` migrates
-- from scratch on every run (TEST_DATABASE_URL default). The app database comes from POSTGRES_DB.
CREATE DATABASE releaseguard_test;
