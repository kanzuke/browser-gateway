"""BrowserManager — unique composant autorisé à importer Playwright.

Responsabilités : démarrer/arrêter Chromium, créer contextes, ouvrir pages,
restaurer les profils persistants. Aucune logique métier ici.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from loguru import logger

if TYPE_CHECKING:
    from playwright.async_api import BrowserContext, Page, Playwright

    from app.config.settings import Settings


class BrowserManager:
    """Gestionnaire du cycle de vie Chromium via Playwright.

    Utilise un profil persistant (user-data-dir) pour conserver cookies, cache,
    IndexedDB, LocalStorage, etc. entre les redémarrages.
    """

    def __init__(self, settings: Settings) -> None:
        self._s = settings
        self._playwright: Playwright | None = None
        self._browser: BrowserContext | None = None
        self._context: BrowserContext | None = None
        self._running = False

    @property
    def is_running(self) -> bool:
        """Indique si Chromium est démarré."""
        return self._running

    async def start(self) -> None:
        """Démarre Chromium avec un profil persistant + scripts stealth anti-bot."""
        if self._running:
            logger.warning("BrowserManager déjà démarré — ignore")
            return

        from playwright.async_api import async_playwright

        from app.browser.stealth import STEALTH_INIT_SCRIPT

        logger.info("Démarre Chromium (profile={})", self._s.browser_profile_dir)
        self._playwright = await async_playwright().start()

        # S'assurer que le dossier profil existe
        self._s.browser_profile_dir.mkdir(parents=True, exist_ok=True)

        launch_kwargs: dict[str, Any] = {
            "headless": self._s.browser_headless,
            "args": self._s.launch_args_list,
            "viewport": {
                "width": self._s.browser_viewport_width,
                "height": self._s.browser_viewport_height,
            },
            "locale": "fr-FR",
            "timezone_id": "Europe/Paris",
            "ignore_default_args": ["--enable-automation"],
        }
        if self._s.browser_executable_path:
            launch_kwargs["executable_path"] = self._s.browser_executable_path
        if self._s.browser_user_agent:
            launch_kwargs["user_agent"] = self._s.browser_user_agent

        self._browser = await self._playwright.chromium.launch_persistent_context(
            user_data_dir=str(self._s.browser_profile_dir),
            **launch_kwargs,
        )
        self._context = self._browser  # persistent_context IS the context

        # --- Injection des scripts stealth anti-détection (DataDome/Cloudflare/...) ---
        # add_init_script s'exécute avant tout code page/frame, ce qui est critique
        # pour masquer navigator.webdriver et autres fingerprints d'automation.
        await self._context.add_init_script(STEALTH_INIT_SCRIPT)
        logger.info("Scripts stealth injectés (anti-DataDome/Cloudflare)")

        self._running = True
        logger.info("Chromium démarré avec succès")

    async def stop(self) -> None:
        """Arrête proprement Chromium."""
        if not self._running:
            return

        logger.info("Arrêt Chromium")
        if self._browser:
            await self._browser.close()
        if self._playwright:
            await self._playwright.stop()

        self._browser = None
        self._context = None
        self._playwright = None
        self._running = False
        logger.info("Chromium arrêté")

    async def new_page(self) -> Page:
        """Ouvre une nouvelle page/onglet dans le contexte persistant.

        Raises:
            RuntimeError: si le navigateur n'est pas démarré.
        """
        if not self._context:
            raise RuntimeError("BrowserManager non démarré — appeler start() d'abord")
        page = await self._context.new_page()
        logger.debug("Nouvelle page ouverte")
        return page

    async def close_page(self, page: Page) -> None:
        """Ferme une page proprement."""
        try:
            await page.close()
            logger.debug("Page fermée")
        except Exception as e:
            logger.debug("Erreur fermeture page: {}", e)

    async def get_cookies(self) -> list[dict[str, str]]:
        """Retourne tous les cookies du contexte persistant."""
        if not self._context:
            return []
        cookies = await self._context.cookies()
        # Normalise en dict simple pour nos modèles
        return [
            {"name": c.get("name", ""), "value": c.get("value", ""), "domain": c.get("domain", "")}
            for c in cookies
        ]

    @property
    def context(self) -> BrowserContext | None:
        """Accès au contexte persistant (pour tests avancés)."""
        return self._context
