import os
from functools import lru_cache
from importlib.resources import as_file, files
from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


def find_static_dir() -> Path:
    with as_file(files("agent_hud") / "static") as path:
        return path


def find_state_dir() -> Path:
    """The app's directory under the XDG state home, which is ~/.local/state unless XDG_STATE_HOME says otherwise."""
    return Path(os.environ.get("XDG_STATE_HOME") or Path.home() / ".local" / "state") / "agent-hud"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="AGENT_HUD_", extra="ignore", frozen=True)

    static_dir: Path = Field(default_factory=find_static_dir, description="Directory of the built UI")
    state_dir: Path = Field(
        default_factory=find_state_dir, description="Directory of the token file and of the board file by default"
    )
    state_file: Path | None = Field(
        default=None,
        description="SQLite file of the board's state, replayed on start; board.db in the state dir by default",
    )
    token: str | None = Field(
        default=None,
        description="The token that /mcp/ needs as a bearer token and the sockets as a query parameter; none makes one for the sockets only",
    )

    @property
    def board_file(self) -> Path:
        return self.state_file or self.state_dir / "board.db"


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
