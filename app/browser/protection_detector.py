"""ProtectionDetector — détecte les protections anti-bot sur une page chargée.

V2.1 — juillet 2026: DataDome cookie seul ne suffit plus pour signaler un blocage.
  Le cookie datadome est posé sur tout visiteur légitime — il ne signifie un blocage
  que s'il est accompagné d'un status >= 400 ou d'une page de challenge DataDome.

Version initiale : DataDome, Cloudflare, PerimeterX, Akamai.
"""

from __future__ import annotations

import re

from loguru import logger

from app.models.schemas import ProtectionResult


class ProtectionDetector:
    """Détecteur de protections anti-bot.

    Analyse le HTML, les en-têtes HTTP, le statut, et les cookies pour identifier
    la présence de solutions anti-bot connues. Retourne une structure normalisée.
    """

    # Signatures DataDome — challenge page (pas le cookie de tracking)
    _DATADOME_HTML_PATTERNS = [
        r"datadome\\.co",
        r"dd://",
        r"cdn\\.datadome\\.co",
        r"var\\s+dd\\s*=",
        r"DataDome",
        r"dd\\.cid",
    ]
    _DATADOME_URL_PATTERNS = [r"datadome\\.co"]
    # Cookie qui indique un BLOCAGE (pas le cookie de tracking)
    # DataDome pose 'datadome' sur tous les visiteurs — ce n'est pas un signal de blocage

    # Signatures Cloudflare
    _CLOUDFLARE_COOKIE_PATTERNS = [r"cf_clearance", r"__cf_bm"]
    _CLOUDFLARE_HTML_PATTERNS = [
        r"cf-browser-verification",
        r"cdn-cgi/challenge-platform",
        r"cloudflare",
        r"cf_chl_",
        r"__cf_chl_",
    ]
    _CLOUDFLARE_HEADER_PATTERNS = [r"cloudflare", r"cf-ray"]

    # Signatures PerimeterX
    _PERIMETERX_COOKIE_PATTERNS = [r"_px", r"pxcts", r"pxcv"]
    _PERIMETERX_HTML_PATTERNS = [r"perimeterx", r"px-captcha", r"pxCaptcha"]

    # Signatures Akamai
    _AKAMAI_COOKIE_PATTERNS = [r"_abck", r"bm_sz", r"ak_bmsc"]
    _AKAMAI_HTML_PATTERNS = [r"akamai", r"bm-verify", r"/_bm/_data"]

    # --- Helpers ---

    @staticmethod
    def _compile(patterns: list[str]) -> list[re.Pattern[str]]:
        """Pré-compile une liste de patterns en regex compilées."""
        return [re.compile(p, re.IGNORECASE) for p in patterns]

    def __init__(self) -> None:
        self._datadome_html_re = self._compile(self._DATADOME_HTML_PATTERNS)
        self._datadome_url_re = self._compile(self._DATADOME_URL_PATTERNS)
        self._cf_cookie_re = self._compile(self._CLOUDFLARE_COOKIE_PATTERNS)
        self._cf_html_re = self._compile(self._CLOUDFLARE_HTML_PATTERNS)
        self._cf_header_re = self._compile(self._CLOUDFLARE_HEADER_PATTERNS)
        self._px_cookie_re = self._compile(self._PERIMETERX_COOKIE_PATTERNS)
        self._px_html_re = self._compile(self._PERIMETERX_HTML_PATTERNS)
        self._ak_cookie_re = self._compile(self._AKAMAI_COOKIE_PATTERNS)
        self._ak_html_re = self._compile(self._AKAMAI_HTML_PATTERNS)

    def detect(
        self,
        html: str,
        status: int,
        cookies: list[dict[str, str]],
        headers: dict[str, str] | None = None,
        final_url: str = "",
    ) -> ProtectionResult:
        """Analyse tous les signaux et retourne la première protection détectée.

        Ordre de priorité: DataDome > Cloudflare > PerimeterX > Akamai.
        """
        headers = headers or {}

        # --- DataDome ---
        if self._check_datadome(html, status, cookies, final_url):
            logger.warning("DataDome détecté (status={}, url={})", status, final_url)
            return ProtectionResult(
                detected=True,
                provider="datadome",
                indicator=f"http_{status}_datadome_signature",
            )

        # --- Cloudflare ---
        if self._check_cloudflare(html, status, cookies, headers):
            logger.warning("Cloudflare détecté (status={}, url={})", status, final_url)
            return ProtectionResult(
                detected=True,
                provider="cloudflare",
                indicator=f"http_{status}_cloudflare_signature",
            )

        # --- PerimeterX ---
        if self._check_perimeterx(html, cookies):
            logger.warning("PerimeterX détecté (url={})", final_url)
            return ProtectionResult(
                detected=True,
                provider="perimeterx",
                indicator="perimeterx_signature",
            )

        # --- Akamai ---
        if self._check_akamai(html, cookies):
            logger.warning("Akamai détecté (url={})", final_url)
            return ProtectionResult(
                detected=True,
                provider="akamai",
                indicator="akamai_signature",
            )

        return ProtectionResult(detected=False, provider="", indicator="")

    def _check_datadome(
        self,
        html: str,
        status: int,
        cookies: list[dict[str, str]],
        final_url: str,
    ) -> bool:
        """Détecte un blocage DataDome.

        Le cookie 'datadome' est posé sur tous les visiteurs légitimes — sa seule
        présence ne signifie PAS un blocage. On ne signale un blocage que si:
        - status >= 400 ET le HTML contient des signatures DataDome (challenge page)
        - OU l'URL finale est une redirection vers datadome.co
        """
        # URL de redirection DataDome — toujours un blocage
        if final_url and any(r.search(final_url) for r in self._datadome_url_re):
            return True

        # Status >= 400 + signatures HTML DataDome = challenge/blocage
        if status >= 400 and any(r.search(html) for r in self._datadome_html_re):
            return True

        # Status 403 spécifique à DataDome (page de challenge avec var dd=)
        if status == 403 and "var dd=" in html:
            return True

        # Sinon, pas de blocage (le cookie seul n'est pas un signal)
        return False

    def _check_cloudflare(
        self,
        html: str,
        status: int,
        cookies: list[dict[str, str]],
        headers: dict[str, str],
    ) -> bool:
        # Cookie Cloudflare
        for cookie in cookies:
            name = cookie.get("name", "")
            if any(r.search(name) for r in self._cf_cookie_re):
                return True
        # En-têtes Cloudflare
        for value in headers.values():
            if any(r.search(value) for r in self._cf_header_re):
                return True
        # HTML challenge
        return bool(status in (403, 503) and any(r.search(html) for r in self._cf_html_re))

    def _check_perimeterx(self, html: str, cookies: list[dict[str, str]]) -> bool:
        for cookie in cookies:
            name = cookie.get("name", "")
            if any(r.search(name) for r in self._px_cookie_re):
                return True
        return bool(any(r.search(html) for r in self._px_html_re))

    def _check_akamai(self, html: str, cookies: list[dict[str, str]]) -> bool:
        for cookie in cookies:
            name = cookie.get("name", "")
            if any(r.search(name) for r in self._ak_cookie_re):
                return True
        return bool(any(r.search(html) for r in self._ak_html_re))
