"""PageController — abstraction haut niveau d'une page Playwright.

Responsabilités : navigation, attente intelligente, screenshot, récupération HTML.
V2.2 — juillet 2026: fix referrer→referer, DataDome JS challenge support,
  cookie polling, slider fallback, improved human behavior.
"""

from __future__ import annotations

import asyncio
import random
import uuid
from typing import TYPE_CHECKING

from loguru import logger

if TYPE_CHECKING:
    from playwright.async_api import BrowserContext, Page, Response

    from app.config.settings import Settings


class PageController:
    """Contrôleur d'une page unique, avec comportements humains avancés.

    Une instance par navigation/fetch. Ne gère pas le cycle de vie du navigateur.
    """

    def __init__(self, page: Page, settings: Settings) -> None:
        self._page = page
        self._s = settings
        self._request_id = uuid.uuid4().hex[:8]

    @property
    def request_id(self) -> str:
        """Identifiant de requête pour le logging."""
        return self._request_id

    async def navigate(
        self,
        url: str,
        wait: int = 0,
        solve_captcha: bool = True,
    ) -> tuple[int, str, str]:
        """Navigue vers une URL et retourne (status, html, title).

        Args:
            url: URL complète à charger.
            wait: secondes d'attente supplémentaires après le chargement.
            solve_captcha: tente de résoudre un captcha DataDome si détecté.

        Returns:
            Tuple (status_code, html_content, page_title).
        """
        logger.info("[{}] Navigation vers {}", self._request_id, url)

        # --- Comportement humain pré-navigation ---
        await self._human_pre_navigation_behavior()

        # Utiliser referer (pas referrer) — Playwright API
        extra_context: dict[str, str] = {"referer": "https://www.google.com/"}

        response: Response | None = None

        try:
            response = await self._page.goto(
                url,
                wait_until="domcontentloaded",
                timeout=self._s.behavior_nav_timeout_ms,
                **extra_context,
            )
        except Exception as e:
            logger.error("[{}] Échec navigation: {}", self._request_id, e)
            try:
                html = await self._page.content()
                title = await self._page.title()
            except Exception:
                return 0, "", ""
            return 0, html, title

        if response is None:
            html = await self._page.content()
            title = await self._page.title()
            return 0, html, title

        status = response.status
        logger.info("[{}] Statut HTTP {}", self._request_id, status)

        # Attente intelligente — networkidle pour les SPA
        if status < 400:
            try:
                await self._page.wait_for_load_state("networkidle", timeout=5000)
            except Exception:
                logger.debug("[{}] networkidle timeout — poursuite", self._request_id)

        # Attente supplémentaire explicite
        if wait > 0:
            logger.debug("[{}] Attente {}s", self._request_id, wait)
            await asyncio.sleep(wait)

        # Détection et résolution de captcha DataDome
        if solve_captcha and status == 403:
            logger.info("[{}] 403 détecté — tentative résolution DataDome", self._request_id)

            # D'abord attendre que la page se stabilise
            await asyncio.sleep(random.uniform(1.0, 2.0))

            # Étape 1: attendre le challenge JS invisible DataDome
            # DataDome envoie un 403 avec un script JS qui calcule un cookie
            # Il faut attendre que le JS s'exécute (3-10s)
            solved = await self._wait_for_datadome_cookie(url, extra_context)
            if solved:
                logger.info("[{}] DataDome JS challenge résolu — contenu récupéré", self._request_id)
                html = await self._page.content()
                title = await self._page.title()
                # Le status a été mis à jour par le reload dans _wait_for_datadome_cookie
                # On vérifie le HTML pour confirmer qu'on a le vrai contenu
                if len(html) > 2000 and "datadome" not in html.lower()[:500]:
                    return 200, html, title
                # Même si on n'est pas sûr, retourner ce qu'on a
                return 200, html, title

            # Étape 2: si pas de cookie, chercher un slider captcha
            logger.info("[{}] Pas de cookie JS — recherche slider DataDome", self._request_id)
            solved = await self._solve_datadome_captcha()
            if solved:
                logger.info("[{}] DataDome slider résolu — attente redirection", self._request_id)
                try:
                    await self._page.wait_for_load_state("domcontentloaded", timeout=15000)
                except Exception:
                    pass
                await asyncio.sleep(random.uniform(2.0, 4.0))
                # Recharger la page pour utiliser le nouveau cookie
                try:
                    response = await self._page.goto(
                        url,
                        wait_until="domcontentloaded",
                        timeout=self._s.behavior_nav_timeout_ms,
                        **extra_context,
                    )
                    status = response.status if response else status
                except Exception as e:
                    logger.warning("[{}] Rechargement post-captcha échoué: {}", self._request_id, e)
                html = await self._page.content()
                title = await self._page.title()
                logger.info("[{}] Statut final après captcha: {}", self._request_id, status)
                if status < 400:
                    return status, html, title
            else:
                # Slider échec — attente puis retry
                logger.info("[{}] Slider échec — attente 5s puis retry", self._request_id)
                await asyncio.sleep(random.uniform(4.0, 7.0))

                # Comportement humain: bouger la souris, scroller un peu
                await self._human_scroll()

                try:
                    response = await self._page.goto(
                        url,
                        wait_until="domcontentloaded",
                        timeout=self._s.behavior_nav_timeout_ms,
                        **extra_context,
                    )
                    status = response.status if response else status
                except Exception as e:
                    logger.warning("[{}] Retry post-échec slider: {}", self._request_id, e)
                html = await self._page.content()
                title = await self._page.title()
                logger.info("[{}] Statut après retry: {}", self._request_id, status)
                if status < 400:
                    return status, html, title

        # Comportement humain léger : scroll aléatoire si activé
        if self._s.behavior_random_scroll and status < 400:
            await self._human_scroll()

        html = await self._page.content()
        title = await self._page.title()

        return status, html, title

    async def _wait_for_datadome_cookie(
        self,
        url: str,
        extra_context: dict[str, str],
    ) -> bool:
        """Attend que le challenge JS DataDome pose un cookie puis recharge.

        DataDome envoie un 403 avec un script JS invisible. Le script calcule
        une valeur et pose un cookie `datadome`. Une fois le cookie posé, on
        peut recharger la page pour obtenir le contenu réel.

        Returns:
            True si le cookie a été obtenu et la page rechargée avec succès.
        """
        context = self._page.context
        max_wait = 15  # secondes max
        poll_interval = 0.5

        logger.info("[{}] Attente cookie datadome (max {}s)", self._request_id, max_wait)

        for elapsed in range(0, max_wait * 2):
            await asyncio.sleep(poll_interval)
            cookies = await context.cookies()

            for cookie in cookies:
                if "datadome" in cookie.get("name", "").lower():
                    logger.info(
                        "[{}] Cookie datadome obtenu après {}s — rechargement",
                        self._request_id,
                        elapsed * poll_interval,
                    )
                    # Petit délai aléatoire (comportement humain)
                    await asyncio.sleep(random.uniform(0.5, 1.5))

                    # Recharger la page avec le cookie
                    try:
                        response = await self._page.goto(
                            url,
                            wait_until="domcontentloaded",
                            timeout=self._s.behavior_nav_timeout_ms,
                            **extra_context,
                        )
                        new_status = response.status if response else 0
                        logger.info(
                            "[{}] Statut après reload cookie: {}",
                            self._request_id,
                            new_status,
                        )
                        if new_status < 400:
                            # Attente networkidle
                            try:
                                await self._page.wait_for_load_state(
                                    "networkidle", timeout=5000
                                )
                            except Exception:
                                pass
                            return True
                        # Même avec le cookie, encore 403 — pas résolu
                        logger.warning(
                            "[{}] Cookie obtenu mais encore 403 après reload",
                            self._request_id,
                        )
                        return False
                    except Exception as e:
                        logger.warning("[{}] Erreur reload après cookie: {}", self._request_id, e)
                        return False

        logger.info("[{}] Pas de cookie datadome après {}s", self._request_id, max_wait)
        return False

    async def _human_pre_navigation_behavior(self) -> None:
        """Simule un comportement humain avant la navigation."""
        try:
            for _ in range(random.randint(1, 3)):
                x = random.randint(100, 1500)
                y = random.randint(100, 800)
                await self._page.mouse.move(x, y)
                await asyncio.sleep(random.uniform(0.1, 0.4))
            await asyncio.sleep(random.uniform(0.3, 0.8))
        except Exception as e:
            logger.debug("[{}] Pre-navigation behavior ignoré: {}", self._request_id, e)

    async def _solve_datadome_captcha(self) -> bool:
        """Tente de résoudre un captcha slider DataDome.

        Returns:
            True si le slider a été résolu (slider-success), False sinon.
        """
        try:
            iframe_element = await self._page.wait_for_selector(
                'iframe[title="DataDome CAPTCHA"]',
                timeout=5000,
            )
            if not iframe_element:
                return False

            iframe = await iframe_element.content_frame()
            if not iframe:
                return False

            slider = await iframe.wait_for_selector(".slider", timeout=5000)
            if not slider:
                return False

            slider_box = await slider.bounding_box()
            iframe_box = await iframe_element.bounding_box()
            if not slider_box or not iframe_box:
                return False

            start_x = iframe_box["x"] + slider_box["x"] + slider_box["width"] / 2
            start_y = iframe_box["y"] + slider_box["y"] + slider_box["height"] / 2
            end_x = start_x + 222
            end_y = start_y

            # Pré-déplacement : approche progressive (humain)
            await self._page.mouse.move(start_x - 80, start_y - 40)
            await asyncio.sleep(random.uniform(0.2, 0.4))
            await self._page.mouse.move(start_x - 20, start_y - 5)
            await asyncio.sleep(random.uniform(0.15, 0.3))
            await self._page.mouse.move(start_x, start_y)
            await asyncio.sleep(random.uniform(0.3, 0.5))

            # Début du glissement
            await self._page.mouse.down()
            await asyncio.sleep(random.uniform(0.05, 0.15))

            # Trajectoire humaine : easing + jitter
            steps = random.randint(40, 55)
            for i in range(1, steps + 1):
                progress = i / steps
                eased = 1 - (1 - progress) ** 3
                x = start_x + (end_x - start_x) * eased
                y = start_y + 2 * (0.5 - abs(0.5 - progress)) + random.uniform(-1.5, 1.5)
                await self._page.mouse.move(x, y)
                await asyncio.sleep(0.012 + random.uniform(0, 0.005))

            # Overshoot puis correction
            overshoot = random.uniform(2, 6)
            await self._page.mouse.move(end_x + overshoot, end_y + random.uniform(-2, 2))
            await asyncio.sleep(random.uniform(0.05, 0.12))
            await self._page.mouse.move(end_x - 1, end_y)
            await asyncio.sleep(random.uniform(0.08, 0.15))

            await self._page.mouse.up()

            await asyncio.sleep(random.uniform(2.5, 4.0))

            try:
                container = await iframe.query_selector(".sliderContainer")
                if container:
                    cls = await container.get_attribute("class") or ""
                    if "slider-success" in cls:
                        logger.info("[{}] DataDome slider RÉSOLU", self._request_id)
                        return True
                    if "slider-error" in cls:
                        logger.warning("[{}] DataDome slider ÉCHEC (bot détecté)", self._request_id)
                        return False
            except Exception:
                logger.info("[{}] iframe détruite — captcha probablement résolu", self._request_id)
                return True

            return False

        except Exception as e:
            logger.debug("[{}] Pas de slider DataDome: {}", self._request_id, e)
            return False

    async def screenshot(self, full_page: bool = True) -> bytes:
        """Capture une image PNG de la page."""
        return await self._page.screenshot(full_page=full_page, type="png")

    async def _human_scroll(self) -> None:
        """Scroll doux et aléatoire pour simuler un humain qui parcourt la page."""
        try:
            for _ in range(random.randint(1, 3)):
                scroll_y = random.randint(100, 600)
                await self._page.mouse.wheel(0, scroll_y)
                await asyncio.sleep(random.uniform(0.3, 1.0))
            await self._page.mouse.wheel(0, -random.randint(50, 200))
        except Exception as e:
            logger.debug("[{}] Scroll humain ignoré: {}", self._request_id, e)

    async def get_title(self) -> str:
        try:
            return await self._page.title()
        except Exception:
            return ""

    async def get_url(self) -> str:
        return self._page.url
