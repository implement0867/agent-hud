from functools import lru_cache
from importlib.resources import as_file, files
from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


def find_static_dir() -> Path:
    with as_file(files("agent_hud") / "static") as path:
        return path


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="AGENT_HUD_", extra="ignore", frozen=True)

    static_dir: Path = Field(default_factory=find_static_dir, description="Directory of the built UI")


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
