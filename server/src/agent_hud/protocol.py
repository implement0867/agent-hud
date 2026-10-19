from enum import StrEnum
from functools import cache
from typing import Annotated, ClassVar, Literal

from pydantic import BaseModel, ConfigDict, Discriminator, Field, TypeAdapter

from agent_hud.primitives import AnchorRef, Element
from agent_hud.primitives.base import CellValue, ElementId, Reaction


class Message(BaseModel):
    model_config: ClassVar[ConfigDict] = ConfigDict(extra="forbid", frozen=True, use_enum_values=True)


class ClientType(StrEnum):
    MOVE = "move"
    PLACE = "place"
    RESIZE = "resize"
    REACT = "react"
    COMMENT = "comment"
    UNCOMMENT = "uncomment"
    EDIT = "edit"
    ADD = "add"
    REMOVE = "remove"
    NOTE = "note"
    LINK = "link"
    DELETE = "delete"
    SUBMIT = "submit"


class MoveMsg(Message):
    t: Literal[ClientType.MOVE]
    id: ElementId
    x: float
    y: float


class PlaceMsg(Message):
    """Position for a card that has none yet; ignored once the card is placed."""

    t: Literal[ClientType.PLACE]
    id: ElementId
    x: float
    y: float


class ResizeMsg(Message):
    t: Literal[ClientType.RESIZE]
    id: ElementId
    w: float = Field(gt=0)


class ReactMsg(Message):
    t: Literal[ClientType.REACT]
    id: ElementId
    anchor: str
    reaction: Reaction | None


class CommentMsg(Message):
    t: Literal[ClientType.COMMENT]
    id: ElementId
    anchor: str
    text: str = Field(min_length=1)


class UncommentMsg(Message):
    t: Literal[ClientType.UNCOMMENT]
    id: ElementId
    anchor: str
    cid: str


class EditMsg(Message):
    t: Literal[ClientType.EDIT]
    id: ElementId
    anchor: str
    value: CellValue


class AddMsg(Message):
    t: Literal[ClientType.ADD]
    id: ElementId
    value: str


class RemoveMsg(Message):
    t: Literal[ClientType.REMOVE]
    id: ElementId
    anchor: str


class NoteMsg(Message):
    t: Literal[ClientType.NOTE]
    x: float
    y: float
    text: str = Field(min_length=1)


class LinkMsg(Message):
    t: Literal[ClientType.LINK]
    src: AnchorRef
    dst: AnchorRef
    text: str | None


class DeleteMsg(Message):
    t: Literal[ClientType.DELETE]
    id: ElementId


class SubmitMsg(Message):
    t: Literal[ClientType.SUBMIT]
    message: str | None


type ClientMsg = Annotated[
    MoveMsg
    | PlaceMsg
    | ResizeMsg
    | ReactMsg
    | CommentMsg
    | UncommentMsg
    | EditMsg
    | AddMsg
    | RemoveMsg
    | NoteMsg
    | LinkMsg
    | DeleteMsg
    | SubmitMsg,
    Discriminator("t"),
]


@cache
def client_messages() -> TypeAdapter[ClientMsg]:
    return TypeAdapter(ClientMsg)


class ServerType(StrEnum):
    HELLO = "hello"
    UPSERT = "upsert"
    GONE = "gone"
    STATUS = "status"
    ERROR = "error"


class Status(Message):
    waiting: bool
    pending: int = Field(ge=0)
    viewers: int = Field(ge=0)


class HelloMsg(Message):
    t: Literal[ServerType.HELLO]
    project: str
    elements: list[Element]
    status: Status


class UpsertMsg(Message):
    t: Literal[ServerType.UPSERT]
    element: Element


class GoneMsg(Message):
    t: Literal[ServerType.GONE]
    id: ElementId


class StatusMsg(Message):
    t: Literal[ServerType.STATUS]
    status: Status


class ErrorMsg(Message):
    t: Literal[ServerType.ERROR]
    message: str


type ServerMsg = Annotated[HelloMsg | UpsertMsg | GoneMsg | StatusMsg | ErrorMsg, Discriminator("t")]
