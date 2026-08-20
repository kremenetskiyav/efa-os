FROM python:3.13.13-slim-bookworm@sha256:355bfa66770995d7e9a0da4b3473b44d0cb451f6b56f5615ad9c39e3c4eca03f AS base

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

COPY requirements.txt /app/requirements.txt
RUN python -m pip install --no-cache-dir --requirement /app/requirements.txt

RUN addgroup --system --gid 10001 efa-mcp \
    && adduser --system --uid 10001 --ingroup efa-mcp --home /nonexistent --no-create-home efa-mcp

COPY --chown=efa-mcp:efa-mcp efa_read_mcp /app/efa_read_mcp

USER efa-mcp:efa-mcp


FROM base AS test
COPY --chown=efa-mcp:efa-mcp tests /app/tests
COPY --chown=efa-mcp:efa-mcp run-local.ps1 /app/run-local.ps1
CMD ["python", "-m", "unittest", "discover", "-s", "tests", "-v"]


FROM base AS runtime
ENTRYPOINT ["python", "-m", "efa_read_mcp"]
