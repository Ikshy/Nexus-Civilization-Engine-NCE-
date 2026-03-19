"""
Core configuration management for Nexus Civilization Engine.
"""
from __future__ import annotations

import os
from functools import lru_cache
from typing import List

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # Database
    database_url: str = "postgresql+asyncpg://nce:nce_password@localhost:5432/nexus_db"
    database_sync_url: str = "postgresql://nce:nce_password@localhost:5432/nexus_db"

    # Redis
    redis_url: str = "redis://localhost:6379/0"

    # API
    api_host: str = "0.0.0.0"
    api_port: int = 8000
    api_secret_key: str = "dev_secret_key"
    cors_origins: str = "http://localhost:3000"

    # Simulation
    world_size_x: int = 50
    world_size_y: int = 50
    agent_count: int = 200
    tick_rate: float = 5.0
    simulation_seed: int = 42
    max_ticks: int = 10000

    # Logging
    log_level: str = "INFO"
    log_format: str = "json"

    @property
    def cors_origins_list(self) -> List[str]:
        return [o.strip() for o in self.cors_origins.split(",")]


@lru_cache()
def get_settings() -> Settings:
    return Settings()
