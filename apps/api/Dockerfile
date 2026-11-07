# Use the official uv image as the base
FROM ghcr.io/astral-sh/uv:python3.12-alpine

WORKDIR /app

# Compile bytecode for faster startup; copy instead of hardlinking (the cache is a separate mount in CI)
ENV UV_COMPILE_BYTECODE=1 UV_LINK_MODE=copy

# Install dependencies first (without the project itself) so this layer stays cached while only code changes
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev --no-install-project

# Copy the rest of the application and install the project
COPY . .
RUN uv sync --frozen --no-dev

# Run the tools of the virtual environment directly: "uv run" would check the environment on every start
ENV PATH="/app/.venv/bin:$PATH"

# The release version, set by CI from the git tag (vX.Y.Z) or as X.Y.Z-dev.N for builds of the dev branch
ARG APP_VERSION=0.0.0-dev
ENV APP_VERSION=$APP_VERSION

RUN adduser -D -u 1001 matchbase
USER matchbase

EXPOSE 8000

# Bring the database schema up to date, then serve. exec makes the server PID 1, so it gets the stop signal from Docker.
# Behind a proxy: FORWARDED_ALLOW_IPS decides whose X-Forwarded-* headers are trusted.
CMD ["sh", "-c", "alembic upgrade head && exec fastapi run main.py --host 0.0.0.0 --port 8000"]
