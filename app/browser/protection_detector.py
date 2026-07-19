"""ProtectionDetector — détecte les protections anti-bot sur une page chargée.

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

    # Signatures DataDome
    _DATADOME_COOKIE_PATTERNS = [r"datadome"]
    _DATADOME_HTML_PATTERNS = [
        r"datadome\.co",
        r"dd://",
        r'cdn\.datadome\.co',
        r"_dd",
        r"DataDome",
    ]
    _DATADOME_URL_PATTERNS = [r"datadome\.co"]

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
        # Pré-compile les regex pour la performance
        self._datadome_cookie_re = self._compile(self._DATADOME_COOKIE_PATTERNS)
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
        # Cookie DataDome
        for cookie in cookies:
            name = cookie.get("name", "")
            if any(r.search(name) for r in self._datadome_cookie_re):
                return True
        # HTML signatures (DataDome bloque souvent avec 403 + page spécifique)
        if status == 403 and any(r.search(html) for r in self._datadome_html_re):
            return True
        # URL de redirection DataDome
        return bool(final_url and any(r.search(final_url) for r in self._datadome_url_re))

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
