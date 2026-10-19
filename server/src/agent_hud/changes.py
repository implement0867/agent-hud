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
    model_config: ClassVar[ConfigDict] = ConfigDict(extra="forbid", frozen=True, use_enum_values=True)

    seq: int = Field(ge=1)
    kind: ChangeKind
    id: str = ""
    anchor: str = ""
    label: str = ""
    """Label of a removed part, which can no longer be computed."""
    text: str = ""
    """Removed text, deleted element, or submit message."""
