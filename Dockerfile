# Standardized run path (see ADR-012): same locked environment on any OS.
FROM ghcr.io/astral-sh/uv:python3.12-bookworm-slim

WORKDIR /app

# Install dependencies first so code changes don't invalidate this layer.
COPY pyproject.toml uv.lock .python-version ./
RUN uv sync --locked --no-install-project --no-dev

COPY . .
RUN uv sync --locked --no-dev

EXPOSE 8501

# First start builds the local data artifacts (needs OPENAI_API_KEY at runtime,
# uses cents of API credit); later starts reuse them if the container is kept.
# The synced virtualenv is called directly so startup needs no package downloads.
CMD ["bash", "-c", "([ -f emporio.db ] && [ -d chroma ] || .venv/bin/emporio-setup) && .venv/bin/streamlit run app.py --server.headless true --server.address 0.0.0.0 --server.port ${PORT:-8501}"]
