# PasalKini: the API and the four screens.
#
# Ollama is not in this image. It stays on the host, where it has the GPU, and the app reaches
# it over HTTP (see compose.yaml): passing a GPU into a container is the harder road on Windows.
#
# Build from the repository root:
#   docker compose -f docker/compose.yaml up --build
FROM python:3.12-slim

COPY --from=ghcr.io/astral-sh/uv:0.11.1 /uv /uvx /bin/

ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    UV_NO_DEV=1 \
    UV_PYTHON_DOWNLOADS=0 \
    PYTHONUNBUFFERED=1 \
    PATH="/app/.venv/bin:$PATH"

WORKDIR /app

# Dependencies first: a change in the code then does not reinstall them.
RUN --mount=type=cache,target=/root/.cache/uv \
    --mount=type=bind,source=uv.lock,target=uv.lock \
    --mount=type=bind,source=pyproject.toml,target=pyproject.toml \
    uv sync --locked --extra tracing --no-install-project

# The code, the source list and the reports the build steps rewrite. Not the data: the PDFs,
# the parsed text, the index, the answer cache and the question log live in a volume.
COPY pyproject.toml uv.lock README.md ./
COPY src ./src
COPY sources ./sources
COPY docs ./docs
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --locked --extra tracing

EXPOSE 8000

# First start with an empty volume: download, parse, build and index (a few minutes, and it
# needs Ollama for the embeddings). Later starts find the data and go straight to serving.
CMD ["sh", "-c", "[ -f data/processed/pasalkini.db ] || pasalkini setup; exec pasalkini serve --host 0.0.0.0 --port 8000"]
