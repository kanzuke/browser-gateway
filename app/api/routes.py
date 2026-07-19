"""Routes FastAPI pour le Browser Gateway.

Périmètre V1 volontairement réduit :
- GET  /health
- GET  /identity
- POST /warmup
- POST /fetch
- POST /screenshot
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from fastapi import APIRouter, Depends, HTTPException

from app.models.enums import IdentityState
from app.models.schemas import (
    FetchRequest,
    FetchResponse,
    HealthResponse,
    IdentityResponse,
    ScreenshotRequest,
    ScreenshotResponse,
    WarmupRequest,
)

if TYPE_CHECKING:
    from app.services.browser_service import BrowserService

router = APIRouter(prefix="", tags=["browser-gateway"])


def get_service() -> BrowserService:
    """Dépendance FastAPI — retourne le service depuis l'état de l'app.

    Note: l'instance réelle est stockée dans app.state.service au startup.
    """
    from app.main import app

    service: BrowserService | None = getattr(app.state, "service", None)
    if service is None:
        raise HTTPException(status_code=503, detail="Service non initialisé")
    return service


@router.get("/health", response_model=HealthResponse)
async def health() -> HealthResponse:
    """Retourne l'état du service."""
    service = get_service()
    info = service.health()
    return HealthResponse(
        status=str(info["status"]),
        browser_running=bool(info["browser_running"]),
        identity_state=IdentityState(str(info["identity_state"])),
    )


@router.get("/identity", response_model=IdentityResponse)
async def get_identity() -> IdentityResponse:
    """Retourne les informations de l'identité active."""
    service = get_service()
    identity = service.identity
    metrics = identity.metrics
    return IdentityResponse(
        state=identity.state,
        score=identity.score,
        domains=identity.domains,
        total_requests=metrics.total_requests,
        successful_requests=metrics.successful_requests,
        failed_requests=metrics.failed_requests,
        datadome_hits=metrics.datadome_hits,
        captcha_hits=metrics.captcha_hits,
        uptime_seconds=metrics.uptime_seconds,
        success_rate=metrics.success_rate,
    )


@router.post("/warmup")
async def warmup(
    req: WarmupRequest,
    service: BrowserService = Depends(get_service),
) -> dict[str, str | int]:
    """Réchauffe un domaine."""
    try:
        return await service.warmup(req.domain)
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Erreur warmup: {e}") from e


@router.post("/fetch", response_model=FetchResponse)
async def fetch(
    req: FetchRequest,
    service: BrowserService = Depends(get_service),
) -> FetchResponse:
    """Charge une URL et retourne le HTML, cookies, et protections détectées."""
    try:
        return await service.fetch(req.url, wait=req.wait)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Erreur fetch: {e}") from e


@router.post("/screenshot", response_model=ScreenshotResponse)
async def screenshot(
    req: ScreenshotRequest,
    service: BrowserService = Depends(get_service),
) -> ScreenshotResponse:
    """Capture une image de la page."""
    try:
        return await service.screenshot(req.url, full_page=req.full_page, wait=req.wait)
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Erreur screenshot: {e}") from e
