from enum import StrEnum
from importlib.resources import files
from pathlib import Path
from typing import ClassVar

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Mode(StrEnum):
    MCP = "mcp"
    SERVE = "serve"


def packaged_ui() -> Path:
    match files("agent_hud").joinpath("static"):
        case Path() as path:
            return path
        case other:
            raise RuntimeError(
                f"agent_hud must be installed as plain files to serve its UI, not {type(other).__name__}"
            )


class HudSettings(BaseSettings):
    model_config: ClassVar[SettingsConfigDict] = SettingsConfigDict(
        env_prefix="AGENT_HUD_",
        extra="forbid",
        use_enum_values=True,
        cli_prog_name="agent-hud",
        cli_implicit_flags=True,
        cli_kebab_case=True,
    )

    mode: Mode = Field(
        default=Mode.MCP, description="`mcp` speaks MCP on stdio; `serve` runs only the canvas web server"
    )
    host: str = Field(default="127.0.0.1", description="Interface the canvas binds to")
    port: int = Field(
        default=7676, ge=0, le=65535, description="Preferred canvas port; a free port is used when this one is busy"
    )
    open_browser: bool = Field(
        default=True, description="Open the canvas in the default browser when no tab is connected"
    )
    max_wait: int = Field(default=1800, ge=1, description="Upper bound in seconds for one blocking read")
    state_file: Path | None = Field(default=None, description="Optional JSON file that keeps the board across restarts")
    extra_origins: list[str] = Field(
        default_factory=list,
        description="Additional browser origins allowed on the websocket, such as the Vite dev server",
    )
    demo: bool = Field(default=False, description="Seed the board with sample elements")
    static_dir: Path = Field(
        default_factory=packaged_ui,
        description="Directory of the built canvas UI; defaults to the copy inside the package",
    )
