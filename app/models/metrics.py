"""Dataclasses métriques et records d'historique."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime


@dataclass(slots=True)
class IdentityMetrics:
    """Compteurs bruts de l'identité — aucune logique métier."""

    total_requests: int = 0
    successful_requests: int = 0
    failed_requests: int = 0
    datadome_hits: int = 0
    captcha_hits: int = 0
    cloudflare_hits: int = 0
    started_at: datetime = field(default_factory=lambda: datetime.now(UTC))

    def reset(self) -> None:
        """Remet tous les compteurs à zéro (après rotation)."""
        self.total_requests = 0
        self.successful_requests = 0
        self.failed_requests = 0
        self.datadome_hits = 0
        self.captcha_hits = 0
        self.cloudflare_hits = 0
        self.started_at = datetime.now(UTC)

    @property
    def success_rate(self) -> float:
        """Taux de réussite en pourcentage, 0.0 si aucune requête."""
        if self.total_requests == 0:
            return 0.0
        return (self.successful_requests / self.total_requests) * 100.0

    @property
    def uptime_seconds(self) -> float:
        """Temps écoulé depuis le démarrage, en secondes."""
        return (datetime.now(UTC) - self.started_at).total_seconds()


@dataclass(slots=True, frozen=True)
class IdentityRecord:
    """Entrée immuable de l'historique d'événements."""

    timestamp: datetime
    event: str
    domain: str
    score_before: int
    score_after: int
    comment: str = ""
