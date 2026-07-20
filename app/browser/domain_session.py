"""DomainSession — relation entre BrowserIdentity et un domaine.

Une session reste ouverte tant que possible. Une session par domaine.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import TYPE_CHECKING

from loguru import logger

from app.browser.page_controller import PageController

if TYPE_CHECKING:
    from playwright.async_api import Page

    from app.config.settings import Settings


class DomainSession:
    """Session persistante pour un domaine.

    Contient un onglet Playwright associé, les cookies, les statistiques,
    et le dernier moment d'accès.
    """

    def __init__(
        self,
        domain: str,
        page: Page,
        settings: Settings,
    ) -> None:
        self._domain = domain
        self._page = page
        self._s = settings
        self._controller = PageController(page, settings)
        self._last_access: datetime = datetime.now(UTC)
        self._created_at: datetime = datetime.now(UTC)
        self._request_count: int = 0
        self._success_count: int = 0
        self._fail_count: int = 0
        self._closed: bool = False

    @property
    def domain(self) -> str:
        return self._domain

    @property
    def controller(self) -> PageController:
        """Le PageController associé à cette session."""
        return self._controller

    @property
    def page(self) -> Page:
        """La page Playwright sous-jacente (pour gestion avancée)."""
        return self._page

    @property
    def last_access(self) -> datetime:
        return self._last_access

    @property
    def is_closed(self) -> bool:
        return self._closed

    @property
    def request_count(self) -> int:
        return self._request_count

    @property
    def success_count(self) -> int:
        return self._success_count

    @property
    def fail_count(self) -> int:
        return self._fail_count

    @property
    def age_seconds(self) -> float:
        """Âge de la session en secondes."""
        return (datetime.now(UTC) - self._created_at).total_seconds()

    def touch(self) -> None:
        """Met à jour le dernier accès."""
        self._last_access = datetime.now(UTC)

    def record_success(self) -> None:
        """Enregistre une requête réussie."""
        self._request_count += 1
        self._success_count += 1
        self.touch()

    def record_failure(self) -> None:
        """Enregistre une requête échouée."""
        self._request_count += 1
        self._fail_count += 1
        self.touch()

    async def close(self) -> None:
        """Ferme l'onglet associé."""
        if self._closed:
            return
        try:
            await self._page.close()
        except Exception as e:
            logger.debug("Erreur fermeture session {}: {}", self._domain, e)
        self._closed = True
        logger.info("Session domaine {} fermée", self._domain)

    def stats(self) -> dict[str, int | float | str]:
        """Retourne les statistiques de la session."""
        return {
            "domain": self._domain,
            "requests": self._request_count,
            "successes": self._success_count,
            "failures": self._fail_count,
            "age_seconds": self.age_seconds,
        }
