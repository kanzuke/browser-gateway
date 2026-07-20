"""Enums métier pour l'identité du navigateur."""

from __future__ import annotations

from enum import StrEnum


class IdentityState(StrEnum):
    """États possibles d'une BrowserIdentity."""

    STARTING = "STARTING"
    READY = "READY"
    DEGRADED = "DEGRADED"
    BLOCKED = "BLOCKED"
    ROTATING = "ROTATING"
    STOPPED = "STOPPED"


class IdentityEvent(StrEnum):
    """Événements enregistrés dans l'historique de l'identité."""

    STARTUP = "STARTUP"
    DOMAIN_WARMUP = "DOMAIN_WARMUP"
    NAVIGATION_SUCCESS = "NAVIGATION_SUCCESS"
    NAVIGATION_FAILURE = "NAVIGATION_FAILURE"
    HTTP_403 = "HTTP_403"
    HTTP_429 = "HTTP_429"
    DATADOME = "DATADOME"
    CLOUDFLARE = "CLOUDFLARE"
    PERIMETERX = "PERIMETERX"
    AKAMAI = "AKAMAI"
    CAPTCHA = "CAPTCHA"
    BROWSER_CRASH = "BROWSER_CRASH"
    MANUAL_ROTATION = "MANUAL_ROTATION"
    AUTOMATIC_ROTATION = "AUTOMATIC_ROTATION"
    SCHEDULED_ROTATION = "SCHEDULED_ROTATION"
    SHUTDOWN = "SHUTDOWN"
