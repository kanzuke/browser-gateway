# Browser Gateway - microservice de contournement anti-bot (DataDome/Cloudflare/etc.)
# Inclut Xvfb pour mode headed (requis par DataDome — headless est détecté).

FROM python:3.13-slim

# Dépendances système pour Chromium + Xvfb (display virtuel pour mode headed)
RUN apt-get update && apt-get install -y --no-install-recommends \
    libnss3 libatk-bridge2.0-0 libdrm2 libxkbcommon0 libxcomposite1 libxdamage1 \
    libxfixes3 libxrandr2 libgbm1 libasound2 libpangocairo-1.0-0 libpango-1.0-0 \
    libcairo2 libatspi2.0-0 libxshmfence1 libwoff1 libopus0 libwebp7 \
    fonts-liberation wget ca-certificates \
    libcups2 \
    xvfb xauth \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# uv pour gestion des dépendances
COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

# Dépendances Python
COPY pyproject.toml uv.lock ./
RUN uv sync --no-dev

# Playwright + Chromium (full, pas headless-shell)
RUN uv run playwright install chromium

# Code source
COPY app/ ./app/

# Variables d'environnement
ENV DISPLAY=:99
ENV LOG_LEVEL=INFO

# Script d'entrée: lance Xvfb puis l'application
COPY entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh

EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=10s --start-period=40s --retries=3 \
    CMD python3 -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/health', timeout=5)" || exit 1

ENTRYPOINT ["/entrypoint.sh"]
CMD ["uv", "run", "uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
