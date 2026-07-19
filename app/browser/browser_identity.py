"""BrowserIdentity — objet métier principal.

Gère l'état général, le score, les sessions de domaine, l'historique,
et décide de la rotation. Toutes les mutations passent par des méthodes métier
et sont thread-safe (RLock). Aucun accès direct aux attributs internes.
"""

from __future__ import annotations

import threading
from datetime import UTC, datetime
from typing import TYPE_CHECKING
from urllib.parse import urlparse

from loguru import logger

from app.browser.domain_session import DomainSession
from app.browser.identity_history import IdentityHistory
from app.browser.identity_policy import IdentityPolicy
from app.browser.protection_detector import ProtectionDetector
from app.models.enums import IdentityEvent, IdentityState
from app.models.metrics import IdentityMetrics, IdentityRecord
from app.models.schemas import FetchResult, ProtectionResult

if TYPE_CHECKING:
    from app.browser.browser_manager import BrowserManager
    from app.config.settings import Settings


class BrowserIdentity:
    """Identité persistante du navigateur — cœur métier du Browser Gateway.

    Encapsule :
    - l'état général (STARTING, READY, DEGRADED, BLOCKED, ROTATING, STOPPED)
    - le score de confiance (0 à score_initial)
    - les sessions de domaine (onglets persistants)
    - l'historique d'événements
    - les métriques
    - la politique de rotation
    """

    def __init__(self, settings: Settings, browser_manager: BrowserManager) -> None:
        self._s = settings
        self._browser = browser_manager
        self._policy = IdentityPolicy(settings)
        self._history = IdentityHistory(settings.history_max_records)
        self._metrics = IdentityMetrics()
        self._detector = ProtectionDetector()

        self._lock = threading.RLock()
        self._state: IdentityState = IdentityState.STARTING
        self._score: int = self._policy.score_initial
        self._sessions: dict[str, DomainSession] = {}
        self._created_at: datetime = datetime.now(UTC)
        self._last_rotation: datetime = datetime.now(UTC)

    # --- Accès en lecture (public) ---

    @property
    def state(self) -> IdentityState:
        with self._lock:
            return self._state

    @property
    def score(self) -> int:
        with self._lock:
            return self._score

    @property
    def domains(self) -> list[str]:
        with self._lock:
            return list(self._sessions.keys())

    @property
    def metrics(self) -> IdentityMetrics:
        with self._lock:
            return self._metrics

    @property
    def age_days(self) -> float:
        return (datetime.now(UTC) - self._created_at).total_seconds() / 86400.0

    @property
    def is_ready(self) -> bool:
        with self._lock:
            return self._state == IdentityState.READY

    @property
    def is_blocked(self) -> bool:
        with self._lock:
            return self._state == IdentityState.BLOCKED

    # --- Cycle de vie ---

    async def start(self) -> None:
        """Démarre l'identité : lance le navigateur et passe en READY."""
        with self._lock:
            if self._state != IdentityState.STARTING:
                logger.warning("Identity déjà démarrée — ignore")
                return

        logger.info("Démarrage BrowserIdentity")
        await self._browser.start()

        with self._lock:
            self._state = self._policy.state_for_score(self._score)
            self._record_event(IdentityEvent.STARTUP, "", "BrowserIdentity démarrée")
            logger.info(
                "BrowserIdentity démarrée — état={} score={}",
                self._state.value,
                self._score,
            )

    async def stop(self) -> None:
        """Arrête l'identité : ferme toutes les sessions et le navigateur."""
        logger.info("Arrêt BrowserIdentity")

        with self._lock:
            await self._close_all_sessions_locked()
            self._state = IdentityState.STOPPED
            self._record_event(IdentityEvent.SHUTDOWN, "", "BrowserIdentity arrêtée")

        await self._browser.stop()

    # --- Sessions de domaine ---

    async def get_or_create_session(self, domain: str) -> DomainSession:
        """Retourne la session existante pour le domaine, ou en crée une nouvelle.

        Raises:
            RuntimeError: si le navigateur n'est pas démarré.
        """
        with self._lock:
            if domain in self._sessions and not self._sessions[domain].is_closed:
                logger.debug("Session existante réutilisée pour {}", domain)
                return self._sessions[domain]

        # Création hors lock (await)
        logger.info("Création session pour domaine {}", domain)
        page = await self._browser.new_page()
        session = DomainSession(domain, page, self._s)

        with self._lock:
            self._sessions[domain] = session
            self._record_event(IdentityEvent.DOMAIN_WARMUP, domain, f"Session créée pour {domain}")

        return session

    async def close_session(self, domain: str) -> None:
        """Ferme et supprime la session pour un domaine."""
        with self._lock:
            session = self._sessions.pop(domain, None)

        if session:
            await session.close()
            logger.info("Session {} fermée et supprimée", domain)

    # --- Opérations métier ---

    async def warmup(self, domain: str) -> dict[str, str | int]:
        """Réchauffe un domaine : ouvre la page d'accueil, attend, scroll léger.

        Returns:
            Dict avec status, title, domain.
        """
        url = f"https://{domain}" if not domain.startswith("http") else domain
        parsed = urlparse(url)
        clean_domain = parsed.netloc or parsed.path

        logger.info("Warmup domaine {}", clean_domain)
        session = await self.get_or_create_session(clean_domain)

        min_wait, max_wait = self._s.warmup_wait_range
        wait = (min_wait + max_wait) // 2  # au milieu, le random est dans le scroll

        status, html, title = await session.controller.navigate(url, wait=wait)

        # Détection de protection
        cookies = await self._browser.get_cookies()
        protection = self._detector.detect(
            html=html,
            status=status,
            cookies=cookies,
            final_url=url,
        )

        with self._lock:
            self._handle_protection_locked(protection, clean_domain, status)
            if protection.detected:
                session.record_failure()
            else:
                session.record_success()

        return {"status": status, "title": title, "domain": clean_domain}

    async def fetch(self, url: str, wait: int = 0) -> FetchResult:
        """Charge une URL et retourne le HTML, les cookies, et les protections détectées.

        Args:
            url: URL complète à charger.
            wait: secondes d'attente supplémentaires.

        Returns:
            FetchResult normalisé.
        """
        parsed = urlparse(url)
        domain = parsed.netloc or parsed.path

        if not domain:
            raise ValueError(f"URL invalide — domaine non extractible: {url}")

        logger.info("Fetch url={} domain={}", url, domain)
        session = await self.get_or_create_session(domain)

        status, html, title = await session.controller.navigate(url, wait=wait)

        cookies = await self._browser.get_cookies()
        protection = self._detector.detect(
            html=html,
            status=status,
            cookies=cookies,
            final_url=await session.controller.get_url(),
        )

        with self._lock:
            self._metrics.total_requests += 1

            event = self._determine_event(status, protection)
            self._apply_delta_locked(event, domain)
            self._handle_protection_locked(protection, domain, status)

            if protection.detected or status >= 400:
                session.record_failure()
                self._metrics.failed_requests += 1
            else:
                session.record_success()
                self._metrics.successful_requests += 1

        return FetchResult(
            url=url,
            status=status,
            html=html,
            cookies=cookies,
            protection=protection,
            title=title,
        )

    async def screenshot(self, url: str, full_page: bool = True, wait: int = 0) -> bytes:
        """Capture une page en PNG bytes.

        Args:
            url: URL à capturer.
            full_page: capture pleine page si True.
            wait: secondes d'attente avant capture.

        Returns:
            Bytes PNG.
        """
        parsed = urlparse(url)
        domain = parsed.netloc or parsed.path

        logger.info("Screenshot url={} domain={}", url, domain)
        session = await self.get_or_create_session(domain)

        # Navigation d'abord
        status, html, title = await session.controller.navigate(url, wait=wait)

        # Détection sur la page chargée
        cookies = await self._browser.get_cookies()
        protection = self._detector.detect(
            html=html,
            status=status,
            cookies=cookies,
            final_url=await session.controller.get_url(),
        )

        with self._lock:
            self._metrics.total_requests += 1
            event = self._determine_event(status, protection)
            self._apply_delta_locked(event, domain)
            self._handle_protection_locked(protection, domain, status)

            if protection.detected or status >= 400:
                session.record_failure()
                self._metrics.failed_requests += 1
            else:
                session.record_success()
                self._metrics.successful_requests += 1

        # Capture après navigation
        return await session.controller.screenshot(full_page=full_page)

    # --- Rotation ---

    async def rotate(self, reason: str = "manual") -> bool:
        """Rotation de l'identité — ferme tout et recrée un profil neuf.

        Returns:
            True si la rotation a eu lieu, False si refusée.
        """
        with self._lock:
            if self._state == IdentityState.ROTATING:
                logger.warning("Rotation déjà en cours — ignore")
                return False
            self._state = IdentityState.ROTATING
            event = (
                IdentityEvent.AUTOMATIC_ROTATION
                if reason == "automatic"
                else IdentityEvent.MANUAL_ROTATION
            )
            self._record_event(event, "", f"Rotation: {reason}")

        logger.info("Rotation identité — raison={}", reason)

        # Ferme tout
        await self._browser.stop()
        with self._lock:
            await self._close_all_sessions_locked()
            self._history.clear()
            self._metrics.reset()
            self._score = self._policy.score_initial
            self._last_rotation = datetime.now(UTC)
            self._created_at = datetime.now(UTC)

        # Redémarre
        await self._browser.start()

        with self._lock:
            self._state = self._policy.state_for_score(self._score)
            logger.info("Rotation terminée — état={} score={}", self._state.value, self._score)

        return True

    # --- Internes (doivent être appelées avec le lock) ---

    def _record_event(
        self,
        event: IdentityEvent,
        domain: str,
        comment: str = "",
    ) -> None:
        """Enregistre un événement dans l'historique. Lock requis."""
        record = IdentityRecord(
            timestamp=datetime.now(UTC),
            event=event.value,
            domain=domain,
            score_before=self._score,
            score_after=self._score,  # sera mis à jour par l'appelant si delta
            comment=comment,
        )
        self._history.append(record)

    def _apply_delta_locked(self, event: IdentityEvent, domain: str) -> None:
        """Applique le delta de score pour un événement et met à jour l'état. Lock requis."""
        delta = self._policy.delta_for(event)
        if delta == 0:
            self._record_event(event, domain)
            return

        score_before = self._score
        self._score = self._policy.clamp_score(self._score + delta)

        # Record avec score avant/après
        record = IdentityRecord(
            timestamp=datetime.now(UTC),
            event=event.value,
            domain=domain,
            score_before=score_before,
            score_after=self._score,
            comment=f"delta={delta:+d}",
        )
        self._history.append(record)

        # Mise à jour de l'état
        new_state = self._policy.state_for_score(self._score)
        if new_state != self._state:
            old_state = self._state
            self._state = new_state
            logger.info(
                "État {} → {} (score {} → {})",
                old_state.value,
                new_state.value,
                score_before,
                self._score,
            )

    def _determine_event(self, status: int, protection: ProtectionResult) -> IdentityEvent:
        """Détermine l'événement IdentityEvent à partir du statut et de la protection."""
        if protection.detected:
            provider = protection.provider.lower()
            event_map = {
                "datadome": IdentityEvent.DATADOME,
                "cloudflare": IdentityEvent.CLOUDFLARE,
                "perimeterx": IdentityEvent.PERIMETERX,
                "akamai": IdentityEvent.AKAMAI,
            }
            return event_map.get(provider, IdentityEvent.NAVIGATION_FAILURE)

        if status == 403:
            return IdentityEvent.HTTP_403
        if status == 429:
            return IdentityEvent.HTTP_429
        if status == 0 or status >= 500:
            return IdentityEvent.NAVIGATION_FAILURE
        return IdentityEvent.NAVIGATION_SUCCESS

    def _handle_protection_locked(
        self,
        protection: ProtectionResult,
        domain: str,
        status: int,
    ) -> None:
        """Met à jour les métriques spécifiques selon la protection. Lock requis."""
        if not protection.detected:
            return

        provider = protection.provider.lower()
        if provider == "datadome":
            self._metrics.datadome_hits += 1
        elif provider == "cloudflare":
            self._metrics.cloudflare_hits += 1
        elif provider in ("perimeterx", "akamai"):
            # Compté comme captcha potentiel
            self._metrics.captcha_hits += 1

        logger.warning(
            "Protection {} détectée sur {} (status={})",
            provider,
            domain,
            status,
        )

    async def _close_all_sessions_locked(self) -> None:
        """Ferme toutes les sessions. Lock requis."""
        for domain, session in list(self._sessions.items()):
            try:
                await session.close()
            except Exception as e:
                logger.debug("Erreur fermeture session {}: {}", domain, e)
        self._sessions.clear()

    # --- Stats publiques ---

    def stats(self) -> dict[str, object]:
        """Retourne un snapshot des statistiques complètes."""
        with self._lock:
            return {
                "state": self._state.value,
                "score": self._score,
                "age_days": self.age_days,
                "domains": list(self._sessions.keys()),
                "total_requests": self._metrics.total_requests,
                "successful_requests": self._metrics.successful_requests,
                "failed_requests": self._metrics.failed_requests,
                "datadome_hits": self._metrics.datadome_hits,
                "captcha_hits": self._metrics.captcha_hits,
                "success_rate": self._metrics.success_rate,
                "uptime_seconds": self._metrics.uptime_seconds,
                "history_count": self._history.count,
            }

    def should_rotate(self) -> bool:
        """Vérifie si une rotation automatique est nécessaire."""
        with self._lock:
            return self._policy.should_rotate(self._score, self.age_days)
