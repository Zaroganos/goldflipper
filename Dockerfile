FROM python:3.13-slim

# Install uv from official image
COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

ENV PYTHONUNBUFFERED=1 \
    UV_SYSTEM_PYTHON=0 \
    UV_LINK_MODE=copy

WORKDIR /app

# Copy dependency manifests first — layer cache is only busted on lockfile changes
COPY pyproject.toml uv.lock ./

# Install all dependencies except the project itself
RUN uv sync --frozen --no-dev --no-install-project

# Copy project source
COPY . .

# Install the project (entry points etc.)
RUN uv sync --frozen --no-dev

EXPOSE 8501

CMD ["uv", "run", "streamlit", "run", "web/app.py"]
