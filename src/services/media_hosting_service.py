"""Service for media_hosting module (Phase B shell)."""

from __future__ import annotations

from src.core.services import Services


class MediaHostingService:
    def __init__(self, services: Services) -> None:
        self.services = services
        self.config = services.config
        self.api = services.api
        self.storage = getattr(services, "storage", None)

    # TODO: extract business logic from src/media_hosting.py tools into methods here.
