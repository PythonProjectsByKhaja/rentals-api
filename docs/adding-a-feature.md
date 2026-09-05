# Adding a feature: a Student CRUD walkthrough

A complete, copy-paste walkthrough that builds a second feature slice from
nothing. Every command and every line of code here was executed against a real
PostgreSQL before being written down.

By the end you will have `/api/v1/students` with full CRUD, a unique-email
constraint that returns **409**, an enum column, two migrations, and tests.

If you only want the summary, it is seven files — see the [checklist](#checklist)
at the bottom.

---

## What you will build

| Method | Path | Returns |
| --- | --- | --- |
| `GET` | `/api/v1/students` | `200` list |
| `POST` | `/api/v1/students` | `201`, `409` on duplicate email, `422` on bad input |
| `GET` | `/api/v1/students/{student_id}` | `200`, or `404` |
| `PATCH` | `/api/v1/students/{student_id}` | `200`, or `404` |
| `DELETE` | `/api/v1/students/{student_id}` | `204`, or `404` |

The `Student` model is deliberately richer than the `items` slice you already
have. Each extra column exists to teach something:

- **`email`, unique** — produces `uq_students_email` from the naming convention,
  and drives the 409 path.
- **`year`, an enum** — creates a native PostgreSQL type, which is where the two
  nastiest migration traps live.
- **`gpa`** — deliberately *not* in the first version. You add it later as a
  second migration, which is the entire point of Step 12.

## Before you start

Get the app running as it ships, so you know your starting point is good.

```
docker compose up -d db
uv run poe migrate
uv run poe dev
```

Open <http://127.0.0.1:8000/docs>. You should see the `items` endpoints. Leave
this running in one terminal; `--reload` picks up every file you add.

### One extra dependency

`Student` validates real email addresses, and Pydantic keeps that validator in an
optional extra:

```
uv add "pydantic[email]"
```

This is also how you add any dependency — `uv add` updates `pyproject.toml` and
`uv.lock` in one step. Commit both.

---

## Step 1 — create the slice

```
src/rentals_api/students/
```

Add an `__init__.py` so it is a package:

```python
"""Student feature slice."""
```

Everything for this feature lives in this one directory. That is the point of
vertical slices: to delete the feature later, you delete the folder.

## Step 2 — the model

`src/rentals_api/students/models.py`

Write it **without** `gpa` for now — you add that in Step 12 to practise changing
a live schema.

```python
"""ORM model for the Student slice."""

from __future__ import annotations

import uuid
from datetime import date, datetime
from enum import StrEnum

from sqlalchemy import Date, DateTime, Enum, String, Uuid, func, text
from sqlalchemy.orm import Mapped, mapped_column

from rentals_api.db.base_class import Base


class YearLevel(StrEnum):
    """Academic year. StrEnum keeps the Python values plain strings."""

    FRESHMAN = "freshman"
    SOPHOMORE = "sophomore"
    JUNIOR = "junior"
    SENIOR = "senior"


class Student(Base):
    __tablename__ = "students"

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid,
        primary_key=True,
        server_default=text("gen_random_uuid()"),
    )
    full_name: Mapped[str] = mapped_column(String(200), index=True)
    email: Mapped[str] = mapped_column(String(320), unique=True)
    year: Mapped[YearLevel] = mapped_column(
        Enum(
            YearLevel,
            name="year_level",
            # WITHOUT values_callable SQLAlchemy stores the enum MEMBER NAME
            # ("FRESHMAN"), not its value ("freshman"). Set this before the first
            # migration or every stored row is wrong.
            values_callable=lambda enum_cls: [member.value for member in enum_cls],
        ),
    )
    enrolled_on: Mapped[date] = mapped_column(Date)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
    )

    def __repr__(self) -> str:  # pragma: no cover - debugging aid
        return f"<Student id={self.id!r} email={self.email!r}>"
```

### Enum trap 1: `values_callable` is not optional

By default SQLAlchemy stores the enum's **member name**, so you would get
`FRESHMAN` in the database while your Python code says `"freshman"`. The
`values_callable` line above stores the value instead.

Get this right *before* the first migration. Changing it afterwards means every
existing row holds the wrong string and needs a data migration.

### Why `enrolled_on` has no server default

It is tempting to write `server_default=func.current_date()`. Don't. This project
runs Alembic with `compare_server_default=True`, and server-side date defaults are
exactly where that comparison reports differences that are not real — which would
make `tests/test_migrations.py` fail on a schema that is actually correct. Let the
client supply the date.

> `native_enum=False` is a trap too: it creates an **unnamed** `CheckConstraint`,
> which raises at DDL time against the `ck_` pattern in `db/base_class.py`. Stick
> with the native PostgreSQL enum.

## Step 3 — register the model (do not skip this)

`src/rentals_api/db/base.py`

```python
from rentals_api.db.base_class import Base as Base
from rentals_api.items.models import Item as Item
from rentals_api.students.models import Student as Student

__all__ = ["Base", "Item", "Student"]
```

**This is the single most-forgotten step in the whole workflow.**

Importing the model module is what registers its table on `Base.metadata`.
Without this line `alembic revision --autogenerate` runs happily, finds nothing,
and writes no migration. You then lose an afternoon wondering why your table
never appears.

The good news: `tests/test_migrations.py` compares the ORM metadata against the
real migrated schema, so if you forget, the test suite tells you rather than
production.

## Step 4 — schemas

`src/rentals_api/students/schemas.py`

```python
"""Pydantic v2 schemas for the Student slice."""

from __future__ import annotations

import uuid
from datetime import date, datetime

from pydantic import BaseModel, ConfigDict, EmailStr, Field

from rentals_api.students.models import YearLevel


class StudentCreate(BaseModel):
    full_name: str = Field(min_length=1, max_length=200)
    email: EmailStr
    year: YearLevel
    enrolled_on: date


class StudentUpdate(BaseModel):
    full_name: str | None = Field(default=None, min_length=1, max_length=200)
    email: EmailStr | None = None
    year: YearLevel | None = None
    enrolled_on: date | None = None


class StudentRead(BaseModel):
    # from_attributes lets FastAPI serialize the ORM object directly.
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    full_name: str
    email: EmailStr
    year: YearLevel
    enrolled_on: date
    created_at: datetime
```

Three separate schemas is deliberate. `StudentCreate` requires everything;
`StudentUpdate` makes it all optional so `PATCH` can send one field; `StudentRead`
adds the server-generated `id` and `created_at`, which a client must never supply.

## Step 5 — domain errors

`src/rentals_api/students/exceptions.py`

```python
"""Domain errors for the Student slice.

Plain exceptions with no HTTP vocabulary. ``main.py`` maps them onto status
codes, so the service layer stays framework-free and unit-testable.
"""

from __future__ import annotations

import uuid


class StudentError(Exception):
    """Base class for student domain errors."""


class StudentNotFoundError(StudentError):
    def __init__(self, student_id: uuid.UUID) -> None:
        self.student_id = student_id
        super().__init__(f"Student {student_id} not found")


class DuplicateStudentEmailError(StudentError):
    def __init__(self, email: str) -> None:
        self.email = email
        super().__init__(f"A student with email {email} already exists")
```

The `Error` suffix is not stylistic — Ruff's `N818` rule requires it.

## Step 6 — the service

`src/rentals_api/students/service.py`

This is where business logic lives, and it must never import FastAPI. Ruff's
`banned-api` rule enforces that mechanically, so the boundary cannot quietly rot.

```python
"""Business logic for the Student slice.

Owns the transaction boundary and knows nothing about HTTP.
"""

from __future__ import annotations

import uuid
from collections.abc import Sequence

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from rentals_api.students.exceptions import (
    DuplicateStudentEmailError,
    StudentNotFoundError,
)
from rentals_api.students.models import Student
from rentals_api.students.schemas import StudentCreate, StudentUpdate

# The constraint name comes from NAMING_CONVENTION in db/base_class.py.
# Being able to identify a violated constraint BY NAME is exactly what that
# convention buys you -- without it PostgreSQL picks its own name and this
# check would be guesswork.
EMAIL_UNIQUE_CONSTRAINT = "uq_students_email"


async def list_students(db: AsyncSession, *, limit: int = 50, offset: int = 0) -> Sequence[Student]:
    stmt = select(Student).order_by(Student.full_name).limit(limit).offset(offset)
    result = await db.execute(stmt)
    return result.scalars().all()


async def get_student(db: AsyncSession, student_id: uuid.UUID) -> Student:
    student = await db.get(Student, student_id)
    if student is None:
        raise StudentNotFoundError(student_id)
    return student


async def _commit_or_translate(db: AsyncSession, email: str) -> None:
    """Commit, converting a unique-email violation into a domain error.

    The rollback is mandatory: after an IntegrityError the session is in a
    failed state and every later statement would raise until it is cleared.
    """
    try:
        await db.commit()
    except IntegrityError as exc:
        await db.rollback()
        if EMAIL_UNIQUE_CONSTRAINT in str(exc.orig):
            raise DuplicateStudentEmailError(email) from exc
        raise


async def create_student(db: AsyncSession, data: StudentCreate) -> Student:
    student = Student(**data.model_dump())
    db.add(student)
    await _commit_or_translate(db, data.email)
    # refresh() pulls server-generated columns (id, created_at) back from the DB.
    await db.refresh(student)
    return student


async def update_student(db: AsyncSession, student_id: uuid.UUID, data: StudentUpdate) -> Student:
    student = await get_student(db, student_id)
    for field, value in data.model_dump(exclude_unset=True).items():
        setattr(student, field, value)
    await _commit_or_translate(db, student.email)
    await db.refresh(student)
    return student


async def delete_student(db: AsyncSession, student_id: uuid.UUID) -> None:
    student = await get_student(db, student_id)
    await db.delete(student)
    await db.commit()
```

Three things worth pausing on:

1. **Checking the constraint by name.** `EMAIL_UNIQUE_CONSTRAINT` is why the
   naming convention in `db/base_class.py` earns its keep. Without it PostgreSQL
   invents a name and you would be matching on something unstable.
2. **The rollback is mandatory.** After an `IntegrityError` the session is
   poisoned — every later statement raises until you clear it.
3. **`exclude_unset=True`** distinguishes "field omitted" from "field set to
   null", which is what makes `PATCH` behave correctly.

> **Gotcha:** `session.rollback()` **expires every object in the session**, and it
> does so regardless of `expire_on_commit=False`. If you hold a reference to an
> ORM object across a possible rollback, read the attributes you need *first* —
> touching them afterwards triggers a lazy reload outside the async greenlet and
> raises `MissingGreenlet`.

## Step 7 — the router

`src/rentals_api/students/router.py`

```python
"""HTTP layer for the Student slice.

Paths, status codes and response models only.
"""

from __future__ import annotations

import uuid
from collections.abc import Sequence

from fastapi import APIRouter, status

from rentals_api.api.deps import DbSession
from rentals_api.students import service
from rentals_api.students.models import Student
from rentals_api.students.schemas import StudentCreate, StudentRead, StudentUpdate

router = APIRouter(prefix="/students", tags=["students"])


@router.get("", response_model=list[StudentRead])
async def list_students(db: DbSession, limit: int = 50, offset: int = 0) -> Sequence[Student]:
    return await service.list_students(db, limit=limit, offset=offset)


@router.post("", response_model=StudentRead, status_code=status.HTTP_201_CREATED)
async def create_student(payload: StudentCreate, db: DbSession) -> Student:
    return await service.create_student(db, payload)


@router.get("/{student_id}", response_model=StudentRead)
async def get_student(student_id: uuid.UUID, db: DbSession) -> Student:
    return await service.get_student(db, student_id)


@router.patch("/{student_id}", response_model=StudentRead)
async def update_student(student_id: uuid.UUID, payload: StudentUpdate, db: DbSession) -> Student:
    return await service.update_student(db, student_id, payload)


@router.delete("/{student_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_student(student_id: uuid.UUID, db: DbSession) -> None:
    await service.delete_student(db, student_id)
```

Handlers are annotated with the ORM type they really return; `response_model` does
the conversion. That keeps the annotation honest so mypy can check it.

`DbSession` is the shared `Annotated[AsyncSession, Depends(get_db)]` alias from
`api/deps.py` — never write `Depends(get_db)` inline.

## Step 8 — mount the router

`src/rentals_api/api/router.py`

```python
from fastapi import APIRouter

from rentals_api.items.router import router as items_router
from rentals_api.students.router import router as students_router

api_router = APIRouter()
api_router.include_router(items_router)
api_router.include_router(students_router)
```

## Step 9 — map errors to status codes

In `src/rentals_api/main.py`, add the import and two handlers:

```python
from rentals_api.students.exceptions import (
    DuplicateStudentEmailError,
    StudentNotFoundError,
)


@app.exception_handler(StudentNotFoundError)
async def student_not_found_handler(request: Request, exc: StudentNotFoundError) -> JSONResponse:
    return JSONResponse(
        status_code=status.HTTP_404_NOT_FOUND,
        content={"detail": str(exc)},
    )


@app.exception_handler(DuplicateStudentEmailError)
async def duplicate_student_email_handler(
    request: Request, exc: DuplicateStudentEmailError
) -> JSONResponse:
    """A second status code, mapped from a second domain error."""
    return JSONResponse(
        status_code=status.HTTP_409_CONFLICT,
        content={"detail": str(exc)},
    )
```

This is the seam that lets the service stay framework-free: it raises meaning,
`main.py` decides the status code.

Check your work before touching the database:

```
uv run poe lint
```

---

## Step 10 — your first migration

```
uv run poe revision -m "add students"
```

**Read the generated file before applying it.** Autogenerate is a good assistant
and a bad author. You should see:

```python
def upgrade() -> None:
    op.create_table(
        "students",
        sa.Column("id", sa.Uuid(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("full_name", sa.String(length=200), nullable=False),
        sa.Column("email", sa.String(length=320), nullable=False),
        sa.Column(
            "year",
            sa.Enum("freshman", "sophomore", "junior", "senior", name="year_level"),
            nullable=False,
        ),
        sa.Column("enrolled_on", sa.Date(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_students")),
        sa.UniqueConstraint("email", name=op.f("uq_students_email")),
    )
    op.create_index(op.f("ix_students_full_name"), "students", ["full_name"], unique=False)
```

Two things to confirm:

- The enum lists **lowercase values** (`"freshman"`), not member names
  (`"FRESHMAN"`). If you see uppercase, you missed `values_callable` in Step 2 —
  fix the model and regenerate now, before any data exists.
- Constraint names are `pk_students`, `uq_students_email`,
  `ix_students_full_name`. Those come from the naming convention, and
  `service.py` depends on that exact unique-constraint name.

### Enum trap 2: fix the downgrade by hand

The generated `downgrade()` is **incomplete**:

```python
def downgrade() -> None:
    op.drop_index(op.f("ix_students_full_name"), table_name="students")
    op.drop_table("students")
```

SQLAlchemy emits `CREATE TYPE` automatically inside `create_table`, but
`drop_table` does **not** drop the type. So a downgrade leaves `year_level`
behind, and the next upgrade fails with:

```
asyncpg.exceptions.DuplicateObjectError: type "year_level" already exists
```

Add the drop yourself:

```python
def downgrade() -> None:
    op.drop_index(op.f("ix_students_full_name"), table_name="students")
    op.drop_table("students")
    # Alembic never generates this. Without it, downgrade leaves the enum type
    # behind and the next upgrade fails with 'type already exists'.
    sa.Enum(name="year_level").drop(op.get_bind(), checkfirst=False)
```

Then format it. Alembic writes its own style (single quotes, its own wrapping),
which is not what `ruff format` produces, so `poe lint` fails right after every
`poe revision` until you do this:

```
uv run poe fmt
```

Now apply it, and confirm there is nothing left to generate:

```
uv run poe migrate
uv run poe revision -m "recheck"
```

The second command must write **no file**. That is the success signal: your
models and your schema agree. If it writes one, read it — you have drift.

Prove the downgrade actually works, because a migration you cannot reverse is a
migration you cannot deploy safely:

```
uv run poe downgrade
uv run poe migrate
```

## Step 11 — run it

With `poe dev` running, in another terminal:

```
curl -X POST http://127.0.0.1:8000/api/v1/students -H "Content-Type: application/json" -d "{\"full_name\":\"Ada Lovelace\",\"email\":\"ada@example.edu\",\"year\":\"freshman\",\"enrolled_on\":\"2026-09-01\"}"
```

> In PowerShell use **`curl.exe`** — bare `curl` is an alias for
> `Invoke-WebRequest` and takes completely different arguments. Or skip the shell
> entirely and use the Swagger UI at `/docs`, which is identical everywhere.

```json
{"id":"3eaf346a-...","full_name":"Ada Lovelace","email":"ada@example.edu",
 "year":"freshman","enrolled_on":"2026-09-01","created_at":"2026-09-05T04:56:30Z"}
```

Worth trying, to see each layer do its job:

| Request | Status | Who produced it |
| --- | --- | --- |
| Same email twice | `409` | `service.py` → `main.py` handler |
| `"year": "postgrad"` | `422` | Pydantic, before your code runs |
| `"email": "not-an-email"` | `422` | Pydantic + `email-validator` |
| `GET` a random UUID | `404` | `StudentNotFoundError` → handler |
| `DELETE` then `GET` | `204` then `404` | service |

## Step 12 — tests

`tests/students/test_students_api.py`

```python
"""End-to-end tests for the Student slice."""

from __future__ import annotations

import uuid
from datetime import date

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from rentals_api.students import service
from rentals_api.students.exceptions import DuplicateStudentEmailError, StudentNotFoundError
from rentals_api.students.models import YearLevel
from rentals_api.students.schemas import StudentCreate

pytestmark = pytest.mark.integration


def payload(**overrides: object) -> dict[str, object]:
    base: dict[str, object] = {
        "full_name": "Ada Lovelace",
        "email": "ada@example.edu",
        "year": "freshman",
        "enrolled_on": "2026-09-01",
    }
    return base | overrides


async def test_create_and_read_student(client: AsyncClient) -> None:
    created = await client.post("/api/v1/students", json=payload())
    assert created.status_code == 201

    body = created.json()
    assert body["full_name"] == "Ada Lovelace"
    assert body["year"] == "freshman"
    assert body["id"] and body["created_at"]

    fetched = await client.get(f"/api/v1/students/{body['id']}")
    assert fetched.status_code == 200
    assert fetched.json() == body


async def test_duplicate_email_returns_409(client: AsyncClient) -> None:
    first = await client.post("/api/v1/students", json=payload())
    assert first.status_code == 201

    second = await client.post("/api/v1/students", json=payload(full_name="Grace Hopper"))
    assert second.status_code == 409
    assert "already exists" in second.json()["detail"]


async def test_update_student(client: AsyncClient) -> None:
    created = (await client.post("/api/v1/students", json=payload())).json()

    updated = await client.patch(f"/api/v1/students/{created['id']}", json={"year": "senior"})

    assert updated.status_code == 200
    assert updated.json()["year"] == "senior"
    # Fields not supplied are untouched, thanks to exclude_unset.
    assert updated.json()["full_name"] == created["full_name"]


async def test_delete_student(client: AsyncClient) -> None:
    created = (await client.post("/api/v1/students", json=payload())).json()

    deleted = await client.delete(f"/api/v1/students/{created['id']}")
    assert deleted.status_code == 204

    missing = await client.get(f"/api/v1/students/{created['id']}")
    assert missing.status_code == 404


async def test_unknown_student_returns_404(client: AsyncClient) -> None:
    response = await client.get(f"/api/v1/students/{uuid.uuid4()}")

    assert response.status_code == 404
    assert "not found" in response.json()["detail"].lower()


async def test_invalid_year_is_rejected(client: AsyncClient) -> None:
    response = await client.post("/api/v1/students", json=payload(year="postgrad"))

    assert response.status_code == 422


async def test_service_raises_domain_errors(session: AsyncSession) -> None:
    """The service layer is a plain callable -- no app, no request needed."""
    student = await service.create_student(
        session,
        StudentCreate(
            full_name="Katherine Johnson",
            email="katherine@example.edu",
            year=YearLevel.JUNIOR,
            enrolled_on=date(2026, 9, 1),
        ),
    )
    assert student.year is YearLevel.JUNIOR

    # Capture the id BEFORE the duplicate attempt. The rollback inside the
    # service expires every instance in the session -- Session.rollback() does
    # this regardless of expire_on_commit -- so touching student.id afterwards
    # would trigger a lazy reload outside the greenlet and raise MissingGreenlet.
    student_id = student.id

    with pytest.raises(DuplicateStudentEmailError):
        await service.create_student(
            session,
            StudentCreate(
                full_name="Someone Else",
                email="katherine@example.edu",
                year=YearLevel.SENIOR,
                enrolled_on=date(2026, 9, 1),
            ),
        )

    await service.delete_student(session, student_id)
    with pytest.raises(StudentNotFoundError):
        await service.get_student(session, student_id)
```

```
uv run poe test
```

You write no fixtures. `client` and `session` come from `tests/conftest.py` and
share one transaction that is rolled back after each test, so tests never see one
another's rows and nothing needs cleaning up.

`tests/test_migrations.py` now covers your new table for free — it compares all
ORM metadata against the migrated schema.

## Step 13 — changing an existing schema

This is the part people get wrong in production. Add a nullable `gpa`.

**1. Change the model** (`students/models.py`):

```python
from decimal import Decimal
from sqlalchemy import Numeric  # add to the existing sqlalchemy import

    # inside class Student, after enrolled_on:
    gpa: Mapped[Decimal | None] = mapped_column(Numeric(3, 2), default=None)
```

**2. Expose it** in `schemas.py`, or the column exists but no client can see it:

```python
from decimal import Decimal

# StudentUpdate:
    gpa: Decimal | None = Field(default=None, ge=0, le=4, decimal_places=2)

# StudentRead:
    gpa: Decimal | None
```

**3. Generate, review, apply:**

```
uv run poe revision -m "add student gpa"
```

```python
def upgrade() -> None:
    op.add_column("students", sa.Column("gpa", sa.Numeric(precision=3, scale=2), nullable=True))


def downgrade() -> None:
    op.drop_column("students", "gpa")
```

Nullable, so no backfill and no table rewrite — safe on a live table.

```
uv run poe fmt
uv run poe migrate
uv run poe downgrade
uv run poe migrate
```

Always round-trip a migration before you ship it.

> `Numeric` returns `Decimal`, not `float`. That is correct for grades and money —
> never store either as a float.

---

## Migration recipes

| Situation | What to do |
| --- | --- |
| **"No changes detected"** | You forgot Step 3 — add the model to `db/base.py`. |
| **"Target database is not up to date"** | Autogenerate refuses to run unless the DB is at head. Run `uv run poe migrate` first. |
| **Adding a `NOT NULL` column to a populated table** | Autogenerate emits a statement that fails on existing rows. Either add `server_default=...`, or do it in three migrations: add nullable → backfill with `op.execute` → `alter_column(nullable=False)`. |
| **Renaming a column** | Autogenerate sees a drop plus an add, which **destroys the data**. Replace it by hand with `op.alter_column("students", "old", new_column_name="new")`. |
| **Dropping a table with an enum** | Add `sa.Enum(name="...").drop(op.get_bind(), checkfirst=False)` — Alembic never generates it. |
| **Adding a value to an enum** | Postgres needs `op.execute("ALTER TYPE year_level ADD VALUE 'alumni'")`. It cannot run inside a transaction on older Postgres, and it is **not reversible** — Postgres has no `DROP VALUE`. |
| **Data migration** | Use `op.execute("UPDATE ...")` inside `upgrade()`. Never import your ORM models into a migration: models describe *today*, migrations must keep working against the schema as it was. |
| **A migration you cannot reverse** | Make `downgrade()` raise `NotImplementedError` explicitly rather than leaving it silently wrong. |
| **`poe lint` fails right after `poe revision`** | Alembic's generated file is not ruff-formatted. Run `uv run poe fmt`. |

Before every commit:

```
uv run poe lint
uv run poe test
```

CI runs the same drift check: it applies migrations, runs autogenerate, and fails
if a new file appears.

## Checklist

Adding any feature slice touches seven things:

1. `src/rentals_api/<feature>/models.py` — the ORM model
2. `src/rentals_api/db/base.py` — **register it** (the one everyone forgets)
3. `src/rentals_api/<feature>/schemas.py` — Create / Update / Read
4. `src/rentals_api/<feature>/exceptions.py` — domain errors, `*Error` suffix
5. `src/rentals_api/<feature>/service.py` — logic; owns the commit; no FastAPI
6. `src/rentals_api/<feature>/router.py` — HTTP only, and include it in `api/router.py`
7. `tests/<feature>/` — plus a migration, reviewed and round-tripped

Or just copy `src/rentals_api/items/` and rename.
