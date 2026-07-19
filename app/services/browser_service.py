"""BrowserService — couche service entre l'API et BrowserIdentity.

Orchestre les appels, gère le cycle de vie, et traduit les résultats métier
en structures consommables par l'API.
"""

from __future__ import annotations

import base64
import uuid
from typing import TYPE_CHECKING

from loguru import logger

from app.browser.browser_identity import BrowserIdentity
from app.browser.browser_manager import BrowserManager
from app.models.schemas import FetchResponse, ScreenshotResponse

if TYPE_CHECKING:
    from app.config.settings import Settings


class BrowserService:
    """Service singleton orchestrant l'identité du navigateur.

    Initialise BrowserIdentity (qui contient BrowserManager) et expose
    des méthodes simples consommées par les routes FastAPI.
    """

    def __init__(self, settings: Settings) -> None:
        self._s = settings
        self._browser_manager = BrowserManager(settings)
        self._identity = BrowserIdentity(settings, self._browser_manager)
        self._started = False

    @property
    def identity(self) -> BrowserIdentity:
        """Accès à l'identité (pour l'API /identity)."""
        return self._identity

    @property
    def browser_manager(self) -> BrowserManager:
        """Accès au gestionnaire de navigateur (pour /health)."""
        return self._browser_manager

    async def start(self) -> None:
        """Démarre le service et l'identité."""
        if self._started:
            return
        logger.info("Démarrage BrowserService")
        await self._identity.start()
        self._started = True

    async def stop(self) -> None:
        """Arrête proprement."""
        if not self._started:
            return
        logger.info("Arrêt BrowserService")
        await self._identity.stop()
        self._started = False

    async def warmup(self, domain: str) -> dict[str, str | int]:
        """Réchauffe un domaine."""
        return await self._identity.warmup(domain)

    async def fetch(self, url: str, wait: int = 0) -> FetchResponse:
        """Charge une URL et retourne une réponse API."""
        result = await self._identity.fetch(url, wait=wait)
        return FetchResponse(
            url=result.url,
            status=result.status,
            html=result.html,
            title=result.title,
            protection_detected=result.protection.detected,
            protection_provider=result.protection.provider,
            cookies=result.cookies,
        )

    async def screenshot(
        self,
        url: str,
        full_page: bool = True,
        wait: int = 0,
    ) -> ScreenshotResponse:
        """Capture une page en screenshot base64."""
        png_bytes = await self._identity.screenshot(url, full_page=full_page, wait=wait)
        b64 = base64.b64encode(png_bytes).decode("ascii")
        return ScreenshotResponse(
            url=url,
            image_base64=b64,
            width=self._s.browser_viewport_width,
            height=self._s.browser_viewport_height,
        )

    def health(self) -> dict[str, str | bool]:
        """Retourne l'état de santé du service."""
        return {
            "status": "ok" if self._started else "starting",
            "browser_running": self._browser_manager.is_running,
            "identity_state": self._identity.state.value,
        }

    @property
    def request_id(self) -> str:
        """Génère un ID de requête pour logging."""
        return uuid.uuid4().hex[:8]
