from enum import StrEnum
from typing import ClassVar

from pydantic import BaseModel, ConfigDict, Field


class ChangeKind(StrEnum):
    REACT = "react"
    COMMENT = "comment"
    EDIT = "edit"
    ADD = "add"
    REMOVE = "remove"
    CREATE = "create"
    DELETE = "delete"
    SUBMIT = "submit"


class Change(BaseModel):
    """One user action in the log the agent reads from."""

    model_config: ClassVar[ConfigDict] = ConfigDict(extra="forbid", frozen=True, use_enum_values=True)

    seq: int = Field(ge=1, description="Position in the change log", examples=[4])
    kind: ChangeKind = Field(description="What the user did", examples=[ChangeKind.REACT])
    id: str = Field(default="", description="Element id; empty for a submit", examples=["plan"])
    anchor: str = Field(default="", description="Anchor key", examples=["k3"])
    label: str | None = Field(default=None, description="Label of a removed part", examples=["plan.4"])
    text: str | None = Field(
        default=None, description="Removed text, deleted element or submit message", examples=["Deploy"]
    )
