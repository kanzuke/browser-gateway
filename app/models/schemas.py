"""Modèles de réponse API et structures normalisées."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime

from pydantic import BaseModel, Field

from app.models.enums import IdentityState

# --- Structures internes ---


@dataclass(slots=True)
class ProtectionResult:
    """Résultat normalisé de la détection anti-bot."""

    detected: bool = False
    provider: str = ""  # "datadome", "cloudflare", "perimeterx", "akamai", ""
    indicator: str = ""  # description courte du signal détecté


@dataclass(slots=True)
class FetchResult:
    """Résultat d'une récupération de page."""

    url: str
    status: int
    html: str
    cookies: list[dict[str, str]] = field(default_factory=list)
    protection: ProtectionResult = field(default_factory=ProtectionResult)
    title: str = ""
    fetched_at: datetime = field(default_factory=datetime.utcnow)


# --- Schémas API (Pydantic) ---


class WarmupRequest(BaseModel):
    """Requête POST /warmup."""

    domain: str = Field(..., description="Domaine à réchauffer, ex: lacentrale.fr")


class FetchRequest(BaseModel):
    """Requête POST /fetch."""

    url: str = Field(..., description="URL complète à charger")
    wait: int = Field(default=0, ge=0, le=60, description="Secondes d'attente après chargement")


class ScreenshotRequest(BaseModel):
    """Requête POST /screenshot."""

    url: str = Field(..., description="URL à capturer")
    full_page: bool = Field(default=True, description="Capture pleine page")
    wait: int = Field(default=0, ge=0, le=60, description="Secondes d'attente avant capture")


class FetchResponse(BaseModel):
    """Réponse de POST /fetch."""

    url: str
    status: int
    html: str
    title: str = ""
    protection_detected: bool = False
    protection_provider: str = ""
    cookies: list[dict[str, str]] = Field(default_factory=list)


class ScreenshotResponse(BaseModel):
    """Réponse de POST /screenshot — base64 PNG."""

    url: str
    image_base64: str
    width: int
    height: int


class IdentityResponse(BaseModel):
    """Réponse de GET /identity."""

    state: IdentityState
    score: int
    domains: list[str]
    total_requests: int
    successful_requests: int
    failed_requests: int
    datadome_hits: int
    captcha_hits: int
    uptime_seconds: float
    success_rate: float


class HealthResponse(BaseModel):
    """Réponse de GET /health."""

    status: str = "ok"
    browser_running: bool = False
    identity_state: IdentityState = IdentityState.STOPPED
