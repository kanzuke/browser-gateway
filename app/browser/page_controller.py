"""PageController — abstraction haut niveau d'une page Playwright.

Responsabilités : navigation, attente intelligente, screenshot, récupération HTML.
Les comportements humains seront progressivement ajoutés ici.
"""

from __future__ import annotations

import asyncio
import random
import uuid
from typing import TYPE_CHECKING

from loguru import logger

if TYPE_CHECKING:
    from playwright.async_api import Page, Response

    from app.config.settings import Settings


class PageController:
    """Contrôleur d'une page unique, avec comportements humains légers.

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

        response: Response | None = None
        try:
            response = await self._page.goto(
                url,
                wait_until="domcontentloaded",
                timeout=self._s.behavior_nav_timeout_ms,
            )
        except Exception as e:
            logger.error("[{}] Échec navigation: {}", self._request_id, e)
            # Même en cas d'échec, on tente de récupérer le HTML
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

        # Attente intelligente — networkidle pour les SPA, fallback domcontentloaded
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
            solved = await self._solve_datadome_captcha()
            if solved:
                # Attendre la redirection après résolution
                logger.info("[{}] DataDome résolu — attente redirection", self._request_id)
                try:
                    await self._page.wait_for_load_state("domcontentloaded", timeout=15000)
                except Exception:
                    pass
                await asyncio.sleep(3)
                # Recharger la page pour utiliser le nouveau cookie
                try:
                    response = await self._page.goto(
                        url,
                        wait_until="domcontentloaded",
                        timeout=self._s.behavior_nav_timeout_ms,
                    )
                    status = response.status if response else status
                except Exception as e:
                    logger.warning("[{}] Rechargement post-captcha échoué: {}", self._request_id, e)
                html = await self._page.content()
                title = await self._page.title()
                logger.info("[{}] Statut final après captcha: {}", self._request_id, status)
                if status < 400:
                    return status, html, title

        # Comportement humain léger : scroll aléatoire si activé
        if self._s.behavior_random_scroll and status < 400:
            await self._human_scroll()

        html = await self._page.content()
        title = await self._page.title()

        return status, html, title

    async def _solve_datadome_captcha(self) -> bool:
        """Tente de résoudre un captcha slider DataDome.

        DataDome affiche un iframe contenant un slider à glisser vers la droite.
        Cette méthode détecte l'iframe, localise le slider, et simule un
        glissement humain (courbe de Bézier, jitter, overshoot).

        Returns:
            True si le slider a été résolu (slider-success), False sinon.
        """
        try:
            # Attendre que l'iframe DataDome apparaisse
            iframe_element = await self._page.wait_for_selector(
                'iframe[title="DataDome CAPTCHA"]',
                timeout=10000,
            )
            if not iframe_element:
                logger.debug("[{}] Pas d'iframe DataDome", self._request_id)
                return False

            iframe = await iframe_element.content_frame()
            if not iframe:
                logger.debug("[{}] Impossible d'accéder au contenu de l'iframe", self._request_id)
                return False

            # Attendre que le slider se charge
            slider = await iframe.wait_for_selector(".slider", timeout=10000)
            if not slider:
                logger.debug("[{}] Pas de slider dans l'iframe", self._request_id)
                return False

            slider_box = await slider.bounding_box()
            iframe_box = await iframe_element.bounding_box()
            if not slider_box or not iframe_box:
                logger.debug("[{}] Bounding box manquante", self._request_id)
                return False

            # Coordonnées absolues sur la page
            start_x = iframe_box["x"] + slider_box["x"] + slider_box["width"] / 2
            start_y = iframe_box["y"] + slider_box["y"] + slider_box["height"] / 2
            end_x = start_x + 222  # sliderTarget est à left:222px
            end_y = start_y

            logger.info(
                "[{}] DataDome slider détecté — glissement {}px",
                self._request_id,
                int(end_x - start_x),
            )

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

            # Trajectoire humaine : easing cubic + jitter vertical
            steps = 45
            for i in range(1, steps + 1):
                progress = i / steps
                # Ease-out cubic (décélération naturelle)
                eased = 1 - (1 - progress) ** 3
                x = start_x + (end_x - start_x) * eased
                # Léger jitter vertical (les humains ne glissent pas parfaitement)
                y = start_y + 2 * (0.5 - abs(0.5 - progress)) + random.uniform(-1, 1)
                await self._page.mouse.move(x, y)
                await asyncio.sleep(0.012 + random.uniform(0, 0.003))

            # Petit overshoot puis correction (comportement humain)
            await self._page.mouse.move(end_x + 4, end_y + 2)
            await asyncio.sleep(random.uniform(0.05, 0.1))
            await self._page.mouse.move(end_x - 1, end_y)
            await asyncio.sleep(random.uniform(0.08, 0.15))

            # Relâchement
            await self._page.mouse.up()

            # Vérifier le résultat
            await asyncio.sleep(3)
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
                # L'iframe a pu être détruite (page rechargée)
                logger.info("[{}] iframe détruite — captcha probablement résolu", self._request_id)
                return True

            logger.warning("[{}] DataDome slider — résultat incertain", self._request_id)
            return False

        except Exception as e:
            logger.warning("[{}] Erreur résolution DataDome: {}", self._request_id, e)
            return False

    async def screenshot(self, full_page: bool = True) -> bytes:
        """Capture une image PNG de la page.

        Args:
            full_page: si True, capture la page entière, sinon le viewport seul.

        Returns:
            Bytes PNG.
        """
        logger.debug("[{}] Screenshot (full_page={})", self._request_id, full_page)
        return await self._page.screenshot(full_page=full_page, type="png")

    async def _human_scroll(self) -> None:
        """Scroll doux et aléatoire pour simuler un humain qui parcourt la page."""
        try:
            scroll_count = random.randint(1, 3)
            for _ in range(scroll_count):
                scroll_y = random.randint(100, 600)
                await self._page.mouse.wheel(0, scroll_y)
                await asyncio.sleep(random.uniform(0.3, 1.0))
            # Remonte un peu
            await self._page.mouse.wheel(0, -random.randint(50, 200))
        except Exception as e:
            logger.debug("[{}] Scroll humain ignoré: {}", self._request_id, e)

    async def get_title(self) -> str:
        """Retourne le titre de la page courante."""
        try:
            return await self._page.title()
        except Exception:
            return ""

    async def get_url(self) -> str:
        """Retourne l'URL finale de la page courante."""
        return self._page.url
