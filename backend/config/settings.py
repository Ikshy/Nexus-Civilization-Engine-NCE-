"""
Nexus Civilization Engine - Configuration Management
"""
from pydantic_settings import BaseSettings
from pydantic import Field
from typing import Optional
import os


class SimulationSettings(BaseSettings):
    # World
    world_width: int = Field(default=50, description="World grid width")
    world_height: int = Field(default=50, description="World grid height")
    tick_interval_ms: int = Field(default=500, description="Simulation tick interval in milliseconds")
    max_agents: int = Field(default=500, description="Maximum number of agents")
    initial_agents: int = Field(default=100, description="Initial agent count")

    # Time
    day_length_ticks: int = Field(default=24, description="Ticks per day")
    season_length_days: int = Field(default=90, description="Days per season")
    year_length_seasons: int = Field(default=4, description="Seasons per year")

    # Economy
    initial_resource_multiplier: float = Field(default=1.0)
    base_inflation_rate: float = Field(default=0.02)
    tax_rate: float = Field(default=0.1)
    black_market_multiplier: float = Field(default=1.5)

    # Social
    reputation_decay_rate: float = Field(default=0.01)
    gossip_spread_radius: int = Field(default=5)
    trust_update_rate: float = Field(default=0.05)

    # Conflict
    rebellion_threshold: float = Field(default=0.7)
    conflict_resource_drain: float = Field(default=0.1)

    class Config:
        env_prefix = "NCE_SIM_"


class DatabaseSettings(BaseSettings):
    postgres_url: str = Field(default="postgresql+asyncpg://nce:nce_password@localhost:5432/nce_db")
    redis_url: str = Field(default="redis://localhost:6379/0")
    pool_size: int = Field(default=10)
    echo_sql: bool = Field(default=False)

    class Config:
        env_prefix = "NCE_DB_"


class APISettings(BaseSettings):
    host: str = Field(default="0.0.0.0")
    port: int = Field(default=8000)
    debug: bool = Field(default=False)
    cors_origins: list[str] = Field(default=["http://localhost:3000", "http://localhost:3001"])
    api_key: Optional[str] = Field(default=None)
    jwt_secret: str = Field(default="nce-secret-change-in-production")

    class Config:
        env_prefix = "NCE_API_"


class LoggingSettings(BaseSettings):
    level: str = Field(default="INFO")
    json_format: bool = Field(default=True)
    log_dir: str = Field(default="logs")
    event_log_file: str = Field(default="logs/events.jsonl")
    max_file_size_mb: int = Field(default=100)

    class Config:
        env_prefix = "NCE_LOG_"


class Settings(BaseSettings):
    simulation: SimulationSettings = SimulationSettings()
    database: DatabaseSettings = DatabaseSettings()
    api: APISettings = APISettings()
    logging: LoggingSettings = LoggingSettings()
    environment: str = Field(default="development")

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"


settings = Settings()
