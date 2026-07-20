"""Point d'entrée FastAPI — Browser Gateway.

Lancement : uvicorn app.main:app --host 0.0.0.0 --port 8000
"""

from __future__ import annotations

import sys
from contextlib import asynccontextmanager
from typing import TYPE_CHECKING

from fastapi import FastAPI
from loguru import logger

from app.api.routes import router
from app.config.settings import get_settings
from app.services.browser_service import BrowserService

if TYPE_CHECKING:
    from collections.abc import AsyncIterator


def _setup_logging(log_level: str) -> None:
    """Configure Loguru avec niveau et format structuré."""
    logger.remove()
    logger.add(
        sys.stderr,
        level=log_level,
        format=(
            "<green>{time:YYYY-MM-DD HH:mm:ss.SSS}</green> | "
            "<level>{level: <8}</level> | "
            "<cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> | "
            "<level>{message}</level>"
        ),
    )
    logger.add(
        "logs/browser-gateway.log",
        level=log_level,
        rotation="10 MB",
        retention="7 days",
        compression="gz",
        format=(
            "{time:YYYY-MM-DD HH:mm:ss.SSS} | {level: <8} | "
            "{name}:{function}:{line} | {message}"
        ),
    )


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    """Gère le cycle de vie : démarrage et arrêt du BrowserService."""
    settings = get_settings()
    _setup_logging(settings.log_level)

    logger.info("Initialisation Browser Gateway")
    service = BrowserService(settings)
    app.state.service = service

    try:
        await service.start()
        logger.info("Browser Gateway prêt")
    except Exception as e:
        logger.error("Échec démarrage Browser Gateway: {}", e)
        # On laisse le service démarrer même si le navigateur échoue
        # (l'API répondra 503 sur les endpoints nécessitant le navigateur)

    yield

    logger.info("Arrêt Browser Gateway")
    await service.stop()
    logger.info("Browser Gateway arrêté")


app = FastAPI(
    title="Browser Gateway",
    description="Microservice de récupération de pages Web protégées par anti-bot",
    version="0.1.0",
    lifespan=lifespan,
)

app.include_router(router)
