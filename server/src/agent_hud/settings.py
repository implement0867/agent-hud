from importlib.resources import files
from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


def packaged_ui() -> Path:
    match files("agent_hud").joinpath("static"):
        case Path() as path:
            return path
        case other:
            raise RuntimeError(
                f"agent_hud must be installed as plain files to serve its UI, not {type(other).__name__}"
            )


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="AGENT_HUD_", extra="forbid", frozen=True)

    port: int = Field(default=7676, ge=1, le=65535, description="Port of the board page on 127.0.0.1")
    static_dir: Path = Field(default_factory=packaged_ui, description="Directory of the built UI")
