# ==========================================================
# 🐍 Base image with Python + uv
# ==========================================================
FROM ghcr.io/astral-sh/uv:python3.12-bookworm AS base

WORKDIR /app

# Copy only dependency files first for better caching
COPY pyproject.toml uv.lock* ./

# ==========================================================
# 📦 Install project dependencies
# ==========================================================
# By default, we install runtime deps only.
# (In dev builds, we override with --dev using build args or compose override.)
ARG INCLUDE_DEV=false
RUN if [ "$INCLUDE_DEV" = "true" ]; then \
      echo "📦 Installing with dev dependencies..."; \
      uv sync --frozen --dev; \
    else \
      echo "📦 Installing production dependencies..."; \
      uv sync --frozen --no-dev; \
    fi

# ==========================================================
# 🧩 Playwright setup
# ==========================================================
# Ensure Playwright + Chromium inside uv env
RUN uv pip install playwright && uv run python -m playwright install --with-deps chromium

# ==========================================================
# 📂 Copy application source
# ==========================================================
COPY src ./src

# ==========================================================
# 🚀 Default Entrypoint (production)
# ==========================================================
CMD ["uv", "run", "-m", "src.main_channel"]
