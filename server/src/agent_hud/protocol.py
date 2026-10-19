"""Websocket messages between the canvas page and the server. Mirrored in `ui/src/protocol/schema.ts`."""

from enum import StrEnum
from functools import cache
from typing import Annotated, ClassVar, Literal

from pydantic import BaseModel, ConfigDict, Discriminator, Field, TypeAdapter

from agent_hud.primitives import AnchorRef, Element
from agent_hud.primitives.base import CellValue, ElementId, Reaction


class Message(BaseModel):
    model_config: ClassVar[ConfigDict] = ConfigDict(extra="forbid", frozen=True, use_enum_values=True)


# -- page to server -------------------------------------------------------------------------


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
    t: Literal[ClientType.MOVE] = Field(description="User dragged a card", examples=[ClientType.MOVE])
    id: ElementId = Field(description="Element id", examples=["plan"])
    x: float = Field(description="New left edge", examples=[120.0])
    y: float = Field(description="New top edge", examples=[80.0])


class PlaceMsg(Message):
    t: Literal[ClientType.PLACE] = Field(description="Page placed an unplaced card", examples=[ClientType.PLACE])
    id: ElementId = Field(description="Element id", examples=["plan"])
    x: float = Field(description="Left edge", examples=[40.0])
    y: float = Field(description="Top edge", examples=[40.0])


class ResizeMsg(Message):
    t: Literal[ClientType.RESIZE] = Field(description="User resized a card", examples=[ClientType.RESIZE])
    id: ElementId = Field(description="Element id", examples=["plan"])
    w: float = Field(gt=0, description="New width", examples=[480.0])


class ReactMsg(Message):
    t: Literal[ClientType.REACT] = Field(description="User set or cleared a verdict", examples=[ClientType.REACT])
    id: ElementId = Field(description="Element id", examples=["plan"])
    anchor: str = Field(description="Anchor key", examples=["k3"])
    reaction: Reaction | None = Field(description="Verdict, or null to clear", examples=[Reaction.APPROVE])


class CommentMsg(Message):
    t: Literal[ClientType.COMMENT] = Field(description="User commented", examples=[ClientType.COMMENT])
    id: ElementId = Field(description="Element id", examples=["plan"])
    anchor: str = Field(description="Anchor key", examples=["k2"])
    text: str = Field(min_length=1, description="Comment", examples=["Wording is unclear"])


class UncommentMsg(Message):
    t: Literal[ClientType.UNCOMMENT] = Field(description="User deleted a comment", examples=[ClientType.UNCOMMENT])
    id: ElementId = Field(description="Element id", examples=["plan"])
    anchor: str = Field(description="Anchor key", examples=["k2"])
    cid: str = Field(description="Comment id", examples=["c9"])


class EditMsg(Message):
    t: Literal[ClientType.EDIT] = Field(description="User changed content", examples=[ClientType.EDIT])
    id: ElementId = Field(description="Element id", examples=["opts"])
    anchor: str = Field(description="Anchor key", examples=["k7:pick"])
    value: CellValue = Field(description="New value", examples=[True])


class AddMsg(Message):
    t: Literal[ClientType.ADD] = Field(description="User appended an item or row", examples=[ClientType.ADD])
    id: ElementId = Field(description="Element id", examples=["plan"])
    value: str = Field(description="Item text, or the first cell of a row", examples=["Write docs"])


class RemoveMsg(Message):
    t: Literal[ClientType.REMOVE] = Field(description="User removed an item or row", examples=[ClientType.REMOVE])
    id: ElementId = Field(description="Element id", examples=["plan"])
    anchor: str = Field(description="Anchor key", examples=["k4"])


class NoteMsg(Message):
    t: Literal[ClientType.NOTE] = Field(description="User added a sticky note", examples=[ClientType.NOTE])
    x: float = Field(description="Left edge", examples=[300.0])
    y: float = Field(description="Top edge", examples=[200.0])
    text: str = Field(min_length=1, description="Markdown body", examples=["Consider caching"])


class LinkMsg(Message):
    t: Literal[ClientType.LINK] = Field(description="User drew an arrow", examples=[ClientType.LINK])
    src: AnchorRef = Field(description="Arrow tail", examples=[{"id": "plan", "anchor": "k6"}])
    dst: AnchorRef = Field(description="Arrow head", examples=[{"id": "plan", "anchor": "k1"}])
    text: str | None = Field(description="Arrow text", examples=["entails?"])


class DeleteMsg(Message):
    t: Literal[ClientType.DELETE] = Field(description="User deleted an element", examples=[ClientType.DELETE])
    id: ElementId = Field(description="Element id", examples=["n4"])


class SubmitMsg(Message):
    t: Literal[ClientType.SUBMIT] = Field(
        description="User sent the feedback to the agent", examples=[ClientType.SUBMIT]
    )
    message: str | None = Field(description="Optional note to the agent", examples=["Mostly fine, fix 2"])


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


# -- server to page -------------------------------------------------------------------------


class ServerType(StrEnum):
    HELLO = "hello"
    UPSERT = "upsert"
    GONE = "gone"
    STATUS = "status"
    ERROR = "error"


class Status(Message):
    waiting: bool = Field(description="The agent is blocked until the user submits", examples=[True])
    pending: int = Field(ge=0, description="User changes the agent has not read", examples=[3])
    viewers: int = Field(ge=0, description="Connected canvas tabs", examples=[1])


class HelloMsg(Message):
    t: Literal[ServerType.HELLO] = Field(description="Full board on connect", examples=[ServerType.HELLO])
    project: str = Field(description="Name of the agent's working directory", examples=["agent-hud"])
    elements: list[Element] = Field(description="Every element, in creation order", examples=[[]])
    status: Status = Field(description="Session status", examples=[{"waiting": False, "pending": 0, "viewers": 1}])


class UpsertMsg(Message):
    t: Literal[ServerType.UPSERT] = Field(description="An element was created or changed", examples=[ServerType.UPSERT])
    element: Element = Field(description="Full element", examples=[{"kind": "text", "id": "n1"}])


class GoneMsg(Message):
    t: Literal[ServerType.GONE] = Field(description="An element was removed", examples=[ServerType.GONE])
    id: ElementId = Field(description="Element id", examples=["plan"])


class StatusMsg(Message):
    t: Literal[ServerType.STATUS] = Field(description="Status changed", examples=[ServerType.STATUS])
    status: Status = Field(description="Session status", examples=[{"waiting": True, "pending": 2, "viewers": 1}])


class ErrorMsg(Message):
    t: Literal[ServerType.ERROR] = Field(description="The last page message was rejected", examples=[ServerType.ERROR])
    message: str = Field(description="Reason", examples=["plan has no item 'k99'"])


type ServerMsg = Annotated[HelloMsg | UpsertMsg | GoneMsg | StatusMsg | ErrorMsg, Discriminator("t")]


@cache
def server_messages() -> TypeAdapter[ServerMsg]:
    return TypeAdapter(ServerMsg)
