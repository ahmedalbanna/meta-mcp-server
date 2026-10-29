"""Service container (composition)."""

from __future__ import annotations

from dataclasses import dataclass

from src.core.config import Config
from src.core.ports import Clock, MetaApiClient, Storage, Throttle


@dataclass
class Services:
    config: Config
    api: MetaApiClient
    storage: Storage
    clock: Clock
    throttle: Throttle | None = None

    @classmethod
    def default(cls) -> Services:
        from src.infra.clock import SystemClock
        from src.infra.meta_api import MetaApiAdapter
        from src.infra.persistence import SqliteStorage
        cfg = Config()
        return cls(
            config=cfg,
            api=MetaApiAdapter(cfg),
            storage=SqliteStorage(cfg.analytics_db_url),
            clock=SystemClock(),
        )
