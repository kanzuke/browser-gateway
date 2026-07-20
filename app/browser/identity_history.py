"""IdentityHistory — historique d'événements en deque limitée."""

from __future__ import annotations

from collections import deque
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Sequence

    from app.models.metrics import IdentityRecord


class IdentityHistory:
    """Historique immuable des événements de l'identité.

    Utilise une deque à taille fixe pour éviter la croissance mémoire infinie.
    Thread-safe via le RLock de BrowserIdentity (l'appelant verrouille).
    """

    def __init__(self, max_records: int = 500) -> None:
        self._records: deque[IdentityRecord] = deque(maxlen=max_records)
        self._max = max_records

    def append(self, record: IdentityRecord) -> None:
        """Ajoute un record à l'historique."""
        self._records.append(record)

    def recent(self, limit: int = 20) -> Sequence[IdentityRecord]:
        """Retourne les *limit* derniers records (ordre chronologique inversé)."""
        items = list(self._records)
        return list(reversed(items))[:limit]

    def all(self) -> list[IdentityRecord]:
        """Retourne tous les records (copie)."""
        return list(self._records)

    def clear(self) -> None:
        """Vide l'historique (après rotation)."""
        self._records.clear()

    @property
    def count(self) -> int:
        """Nombre de records stockés."""
        return len(self._records)

    def count_for_domain(self, domain: str) -> int:
        """Nombre de records pour un domaine donné."""
        return sum(1 for r in self._records if r.domain == domain)

    def count_for_event(self, event: str) -> int:
        """Nombre de records pour un type d'événement donné."""
        return sum(1 for r in self._records if r.event == event)
