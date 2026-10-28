import os
from functools import lru_cache
from importlib.resources import as_file, files
from pathlib import Path
from secrets import token_urlsafe

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


def find_static_dir() -> Path:
    with as_file(files("agent_hud") / "static") as path:
        return path


def find_state_dir() -> Path:
    """The app's directory under the XDG state home, which is ~/.local/state unless XDG_STATE_HOME says otherwise."""
    return Path(os.environ.get("XDG_STATE_HOME") or Path.home() / ".local" / "state") / "agent-hud"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="AGENT_HUD_", extra="ignore", frozen=True, validate_by_name=True)

    static_dir: Path = Field(default_factory=find_static_dir, description="Directory of the built UI")
    state_dir: Path = Field(
        default_factory=find_state_dir, description="Directory of the token file and of the boards by default"
    )
    data_dir: Path = Field(
        default_factory=lambda data: data["state_dir"],
        validation_alias="CLAUDE_PLUGIN_DATA",
        description="The folder of the SQLite file of the boards: the plugin's data folder, which Claude Code sets as CLAUDE_PLUGIN_DATA, or the state dir",
    )
    build: str = Field(
        default="",
        description="A fingerprint of the sources the app runs from, which the hook sets and /health returns, so that the hook restarts an app from older sources",
    )
    token: str | None = Field(
        default=None,
        description="The token that /mcp/ needs as a bearer token, and the sockets and /boards as a query parameter; none leaves /mcp/ open",
    )
    socket_token: str = Field(
        default_factory=lambda data: data["token"] or token_urlsafe(32),
        description="The token that the sockets and /boards need as a query parameter: the token, or a new one",
    )
    idle_seconds: float = Field(
        default=3600,
        ge=0,
        description="How long the app runs with no page or monitor connected and no request before it stops; 0 keeps it running",
    )

    monitor_chars: int = Field(
        default=3000,
        ge=100,
        description="How many characters of one event Claude Code's Monitor shows; a turn with more goes to it in as many events as it needs",
    )
    monitor_gap: float = Field(
        default=0.5,
        ge=0,
        description="Seconds between the events of one turn, so that the Monitor shows them apart: it joins events closer than 0.2 s",
    )


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
