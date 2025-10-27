# ==========================================================
# 🐍 ThreatMark Threat Intelligence Monitor (Dockerfile)
# ==========================================================
# - Uses uv + Python 3.12 for fast dependency management
# - Installs Playwright (Chromium) for URL crawling
# - Runs the Slack Channel Monitor by default
# ==========================================================

FROM ghcr.io/astral-sh/uv:python3.12-bookworm AS base

WORKDIR /app

# ==========================================================
# 📦 Dependency Installation (cached)
# ==========================================================
COPY pyproject.toml uv.lock* ./ 

ARG INCLUDE_DEV=false
RUN if [ "$INCLUDE_DEV" = "true" ]; then \
      echo "📦 Installing with dev dependencies..."; \
      uv sync --frozen --dev; \
    else \
      echo "📦 Installing production dependencies..."; \
      uv sync --frozen --no-dev; \
    fi

# ==========================================================
# 🧩 Playwright + Chromium Setup
# ==========================================================
RUN uv pip install --no-cache-dir playwright && \
    uv run python -m playwright install --with-deps chromium

# ==========================================================
# ⚙️ Environment defaults
# ==========================================================
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    LOGURU_LEVEL=INFO \
    TZ=Europe/Prague

# ==========================================================
# 📂 Copy Source Code
# ==========================================================
COPY src/ ./src/

# ==========================================================
# 📦 Optionally copy data & scripts (safe fallback)
# ==========================================================
RUN mkdir -p /app/data /app/scripts && \
    if [ -d "./data" ]; then cp -r ./data/* /app/data/ || true; fi && \
    if [ -d "./scripts" ]; then cp -r ./scripts/* /app/scripts/ || true; fi

# ==========================================================
# 🧪 Healthcheck (Slack token validation)
# ==========================================================
HEALTHCHECK --interval=60s --timeout=5s --retries=3 CMD \
    test -n "$SLACK_BOT_TOKEN" || exit 1

# ==========================================================
# 🚀 Default Entrypoint (Slack Channel Monitor)
# ==========================================================
CMD ["uv", "run", "-m", "src.main_threatintel"]
