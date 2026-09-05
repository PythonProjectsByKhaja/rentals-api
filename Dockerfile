# syntax=docker/dockerfile:1

# ---- builder -------------------------------------------------------------
FROM python:3.14-slim-bookworm AS builder

# Copy the uv binary from its official image rather than pip-installing it.
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    UV_PYTHON_DOWNLOADS=never

WORKDIR /app

# Install dependencies first, in their own layer, so that editing source code
# does not invalidate the (slow) dependency install.
COPY pyproject.toml uv.lock* ./
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --frozen --no-install-project --no-default-groups

COPY . .
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --frozen --no-default-groups

# ---- runtime -------------------------------------------------------------
FROM python:3.14-slim-bookworm AS runtime

# Run unprivileged.
RUN useradd --create-home --uid 1000 app
WORKDIR /app

COPY --from=builder --chown=app:app /app /app

# Put the venv first on PATH so `uvicorn` resolves without activation
# (activation scripts are shell-specific and have no place in a container).
ENV PATH="/app/.venv/bin:$PATH" \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1

USER app
EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=3s --start-period=10s --retries=3 \
    CMD python -c "import urllib.request,sys; sys.exit(0 if urllib.request.urlopen('http://127.0.0.1:8000/health').status==200 else 1)"

CMD ["uvicorn", "rentals_api.main:app", "--host", "0.0.0.0", "--port", "8000"]
