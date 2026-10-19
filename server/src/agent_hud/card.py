from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field, StringConstraints

type CardId = Annotated[str, StringConstraints(pattern=r"^[A-Za-z][A-Za-z0-9_-]{0,31}$")]


class Card(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    md: str = Field(min_length=1)
