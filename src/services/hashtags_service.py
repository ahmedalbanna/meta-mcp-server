"""Service for hashtags module (Phase B shell)."""

from __future__ import annotations

from src.core.services import Services


class HashtagsService:
    def __init__(self, services: Services) -> None:
        self.services = services
        self.config = services.config
        self.api = services.api
        self.storage = getattr(services, "storage", None)

    # TODO: extract business logic from src/hashtags.py tools into methods here.
