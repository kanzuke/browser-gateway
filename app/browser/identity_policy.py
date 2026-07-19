"""IdentityPolicy — toutes les règles métier (scores, seuils, pénalités).

Aucune constante métier ne doit être codée directement dans BrowserIdentity.
Tout passe par ici, alimenté par Settings.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from app.models.enums import IdentityEvent, IdentityState

if TYPE_CHECKING:
    from app.config.settings import Settings


class IdentityPolicy:
    """Centralise les règles de scoring et de transition d'état.

    Les valeurs proviennent de Settings (donc .env / variables d'environnement),
    jamais codées en dur dans cette classe.
    """

    def __init__(self, settings: Settings) -> None:
        self._s = settings

    # --- Seuils ---

    @property
    def score_initial(self) -> int:
        return self._s.identity_score_initial

    @property
    def threshold_ready(self) -> int:
        return self._s.identity_score_ready

    @property
    def threshold_degraded(self) -> int:
        return self._s.identity_score_degraded

    @property
    def threshold_blocked(self) -> int:
        return self._s.identity_score_blocked

    @property
    def rotation_days(self) -> int:
        return self._s.identity_rotation_days

    # --- Pénalités / bonus ---

    def penalty_for(self, event: IdentityEvent) -> int:
        """Retourne la pénalité (négative) pour un événement, 0 si non pertinent."""
        penalties: dict[IdentityEvent, int] = {
            IdentityEvent.DATADOME: self._s.penalty_datadome,
            IdentityEvent.CLOUDFLARE: self._s.penalty_cloudflare,
            IdentityEvent.CAPTCHA: self._s.penalty_captcha,
            IdentityEvent.HTTP_403: self._s.penalty_http_403,
            IdentityEvent.HTTP_429: self._s.penalty_http_429,
            IdentityEvent.NAVIGATION_FAILURE: self._s.penalty_nav_fail,
        }
        return -penalties.get(event, 0)

    def bonus_for(self, event: IdentityEvent) -> int:
        """Retourne le bonus (positif) pour un événement, 0 si non pertinent."""
        bonuses: dict[IdentityEvent, int] = {
            IdentityEvent.NAVIGATION_SUCCESS: self._s.bonus_nav_success,
        }
        return bonuses.get(event, 0)

    def delta_for(self, event: IdentityEvent) -> int:
        """Delta net (bonus - pénalité) pour un événement."""
        return self.bonus_for(event) + self.penalty_for(event)

    # --- Transitions d'état ---

    def state_for_score(self, score: int) -> IdentityState:
        """Détermine l'état en fonction du score courant.

        - score >= threshold_ready → READY
        - score >= threshold_degraded → DEGRADED
        - score >= threshold_blocked → BLOCKED (toujours dégradé, mais blocage logique)
        - score < threshold_blocked → BLOCKED
        """
        if score >= self.threshold_ready:
            return IdentityState.READY
        if score >= self.threshold_degraded:
            return IdentityState.DEGRADED
        return IdentityState.BLOCKED

    def should_rotate(self, score: int, age_days: float) -> bool:
        """Décide si l'identité doit être rotée (âge ou score trop bas)."""
        if score < self.threshold_blocked:
            return True
        return age_days >= self.rotation_days

    def clamp_score(self, score: int) -> int:
        """Maintient le score dans [0, score_initial]."""
        return max(0, min(self.score_initial, score))
