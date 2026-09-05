# rentals-api

A FastAPI service which lists rentals backed by PostgreSQL.

FastAPI · SQLAlchemy 2.0 (async) · Alembic · PostgreSQL · Python 3.14

---

## Quick start

Every command below is run through `uv run`, which means **you never activate the
virtualenv**. That is deliberate: activation is the single least portable step in
a Python workflow (`source .venv/bin/activate` vs `.venv\Scripts\Activate.ps1`,
and the latter is blocked outright by Windows' default `ExecutionPolicy`).
Skipping it also makes local runs identical to CI.

```
uv sync
```

```
docker compose up -d db
uv run poe migrate
```

```
uv run poe dev
```

Then open <http://127.0.0.1:8000/docs>.

### The handful of commands that differ per shell

Everything in this README is byte-identical in bash and PowerShell **except**
these. `uv`, `git`, `docker compose` and `alembic` invocations are the same
everywhere.

| Task | bash / Git Bash | PowerShell |
| --- | --- | --- |
| Copy a file | `cp .env.example .env` | `Copy-Item .env.example .env` |
| Set an env var | `export DEBUG=true` | `$env:DEBUG = "true"` |
| Env var for one command | `DEBUG=true uv run poe dev` | `$env:DEBUG="true"; uv run poe dev` |
| Chain on success | `a && b` | `a; if ($?) { b }` — `&&` is a **parser error** in PowerShell 5.1 |
| Call curl | `curl http://...` | `curl.exe http://...` — bare `curl` is an alias for `Invoke-WebRequest` |

The generator already created your `.env`, so you should not need the first row.

## Commands

Run `uv run poe` with no arguments to list these with help text.

| Command | Does |
| --- | --- |
| `uv run poe dev` | Run the API with autoreload |
| `uv run poe test` | Run the test suite |
| `uv run poe cov` | Tests with a coverage report |
| `uv run poe lint` | ruff check, ruff format --check, mypy |
| `uv run poe fmt` | Auto-format and auto-fix |
| `uv run poe migrate` | Apply pending migrations |
| `uv run poe downgrade` | Roll back one migration |
| `uv run poe revision -m "add users"` | Autogenerate a migration |
| `uv run poe up` / `down` | Start / stop the database container |
| `uv run poe bootstrap` | Start the DB, then migrate |

These are [poethepoet](https://poethepoet.natn.io/) tasks in `pyproject.toml`
rather than a Makefile, so they behave the same on every OS and shell. Tasks use
`sequence` instead of `&&` and `env` tables instead of `export`, and none of them
invoke a shell.

## Layout

```
src/rentals_api/
  main.py            app, lifespan, exception handlers, GET /
  core/
    config.py        Settings + get_settings()
    logging.py       logging setup
  db/
    base_class.py    DeclarativeBase + constraint naming convention
    base.py          re-exports Base and every model  <- Alembic reads this
    session.py       engine, session factory, get_db()
  api/
    deps.py          DbSession / SettingsDep aliases
    router.py        aggregates feature routers under /api/v1
    health.py        /health and /health/ready
  items/             the example feature slice
    models.py        ORM only
    schemas.py       Pydantic request/response models
    service.py       business logic; owns the transaction; no FastAPI import
    router.py        HTTP only
    exceptions.py    domain errors, mapped to status codes in main.py
alembic/             migration environment and versions
tests/               conftest fixtures, smoke tests, drift test, API tests
docs/
  adding-a-feature.md  full Student CRUD walkthrough
```

### Adding a feature

1. Copy `src/rentals_api/items/` to `src/rentals_api/<feature>/`.
2. **Add the model to `src/rentals_api/db/base.py`.** If you skip this,
   `alembic revision --autogenerate` reports "no changes detected" and you will
   lose an afternoon to it. `tests/test_migrations.py` catches the mistake.
3. Include the router in `src/rentals_api/api/router.py`.
4. `uv run poe revision -m "add <feature>"`, review the generated file, then
   `uv run poe migrate`.

**New here? Follow [docs/adding-a-feature.md](docs/adding-a-feature.md)** — a
complete copy-paste walkthrough that builds a Student CRUD slice end to end,
including the enum and migration traps that are easy to hit and hard to diagnose.

### Why the layers are shaped this way

Slices are **vertical**, not layered: one feature lives in one directory instead
of being smeared across `models/`, `schemas/`, `services/` and `routers/`.

There is **no repository layer**. `AsyncSession` is already a Unit of Work plus
Data Mapper; a class wrapping `session.execute(select(Item))` adds a file and an
indirection and buys nothing. Add one when you genuinely have a second
persistence backend, or logic worth testing with no database at all.

The **service layer owns the transaction boundary** and never imports FastAPI —
Ruff's `banned-api` rule enforces that, so it cannot quietly rot. `get_db()`
deliberately does not commit: committing in the dependency commits even when the
handler decided not to, and it fires after response serialization, which makes
error mapping incoherent.

## Migrations

```
uv run poe revision -m "describe the change"
uv run poe migrate
```

Autogenerate **writes nothing when the models already match the database**, so
"no new file" is the success signal, not a bug.

Constraint names come from a naming convention in `db/base_class.py`, which is
what makes them stable enough to drop by name later. Do not remove it — the
initial migration already depends on those names.

## Tests

```
uv run poe test
```

- Tests that need no database always run.
- Database-backed tests run against a real PostgreSQL (`docker compose up -d db`)
  and **skip with an explanatory message** if it is unreachable, so a fresh clone
  never fails just because nothing is running.
- The schema is built once per session by running the **real migration chain**,
  so migrations are exercised on every test run.
- Each test runs inside a transaction that is rolled back, so tests do not
  interfere and nothing needs cleaning up.
- `tests/test_migrations.py` compares the ORM metadata against the migrated
  schema and fails if they have drifted.

Tests deliberately do **not** use SQLite. It does not enforce foreign keys by
default (integrity tests would pass vacuously), lacks `JSONB`/`ARRAY`/`UUID`, and
its limited `ALTER TABLE` would force Alembic into batch mode — meaning the
migration path you ship would never actually be executed by the suite.

To use [testcontainers](https://testcontainers-python.readthedocs.io/) instead of
a long-running database, replace the `db_url` fixture in `tests/conftest.py`.
It is the only seam; nothing else changes.

## Updating from the template

This project was generated with [Copier](https://copier.readthedocs.io/) and
records its answers in `.copier-answers.yml`. To pull in template improvements
while keeping your choices:

```
copier update --trust
```
