"""Board state shared by the agent (MCP tools) and the user (canvas websocket).

The board is the single source of truth. Agent writes apply atomically. User actions
append to a change log; the agent reads the log as a compact delta since its last read.
"""

import asyncio
import contextlib
import time
from collections.abc import Awaitable, Callable
from typing import ClassVar

from pydantic import BaseModel, ConfigDict, Field, ValidationError

from agent_hud.changes import Change, ChangeKind
from agent_hud.markdown import MarkdownError
from agent_hud.ops import ClearOp, InsertOp, LinkOp, Op, PutOp, RemoveOp, ReplyOp, SetOp
from agent_hud.primitives import AnchorRef, Box, Element, LinkEl, TextEl, build_box
from agent_hud.primitives.base import AnchorRefLike, Author, Comment, ElementKind, PathError
from agent_hud.protocol import (
    AddMsg,
    ClientMsg,
    CommentMsg,
    DeleteMsg,
    EditMsg,
    GoneMsg,
    HelloMsg,
    LinkMsg,
    MoveMsg,
    NoteMsg,
    PlaceMsg,
    ReactMsg,
    RemoveMsg,
    ResizeMsg,
    ServerMsg,
    ServerType,
    Status,
    StatusMsg,
    SubmitMsg,
    UncommentMsg,
    UpsertMsg,
)
from agent_hud.report import label_in, render_element, summarize


class BoardState(BaseModel):
    """Everything needed to restore a board."""

    model_config: ClassVar[ConfigDict] = ConfigDict(extra="forbid")

    elements: list[Element] = Field(description="Elements in creation order", examples=[[]])
    changes: list[Change] = Field(description="User change log", examples=[[]])
    seq: int = Field(ge=0, description="Last change sequence", examples=[12])
    next_id: int = Field(ge=0, description="Id counter", examples=[40])
    cursor: int = Field(ge=0, description="Last change sequence the agent read", examples=[9])


class OpError(ValueError):
    """An agent op failed; the batch was not applied."""

    status_code: ClassVar[int] = 400


class UserError(ValueError):
    """A page message could not be applied."""


type Listener = Callable[[ServerMsg], None]


class Board:
    def __init__(self, *, project: str) -> None:
        self.project: str = project
        self.elements: dict[str, Element] = {}
        self.changes: list[Change] = []
        self.seq: int = 0
        self.next_id: int = 0
        self.cursor: int = 0
        self.viewers: int = 0
        self.waiting: int = 0
        self.on_persist: Callable[[], None] | None = None
        self._listeners: set[Listener] = set()
        self._submitted: asyncio.Event = asyncio.Event()
        self._joined: asyncio.Event = asyncio.Event()

    # -- state ---------------------------------------------------------------------------------

    def dump(self) -> BoardState:
        return BoardState(
            elements=list(self.elements.values()),
            changes=self.changes,
            seq=self.seq,
            next_id=self.next_id,
            cursor=self.cursor,
        )

    def restore(self, state: BoardState) -> None:
        self.elements = {el.id: el for el in state.elements}
        self.changes = state.changes
        self.seq, self.next_id, self.cursor = state.seq, state.next_id, state.cursor

    def new_id(self, prefix: str) -> str:
        while True:
            self.next_id += 1
            if (candidate := f"{prefix}{self.next_id}") not in self.elements:
                return candidate

    @property
    def pending(self) -> int:
        return sum(1 for c in self.changes if c.seq > self.cursor)

    def status(self) -> Status:
        return Status(waiting=self.waiting > 0, pending=self.pending, viewers=self.viewers)

    def hello(self) -> HelloMsg:
        return HelloMsg(
            t=ServerType.HELLO, project=self.project, elements=list(self.elements.values()), status=self.status()
        )

    # -- fan-out -------------------------------------------------------------------------------

    def subscribe(self, listener: Listener) -> None:
        self._listeners.add(listener)
        self.viewers += 1
        self._joined.set()
        self._joined = asyncio.Event()
        self._emit_status()

    async def wait_for_viewer(self, limit: float) -> bool:
        """Wait up to `limit` seconds for a canvas tab to connect."""
        if self.viewers > 0:
            return True
        with contextlib.suppress(TimeoutError):
            async with asyncio.timeout(limit):
                await self._joined.wait()
        return self.viewers > 0

    def unsubscribe(self, listener: Listener) -> None:
        self._listeners.discard(listener)
        self.viewers -= 1
        self._emit_status()

    def _emit(self, msg: ServerMsg) -> None:
        for listener in list(self._listeners):
            listener(msg)

    def _emit_status(self) -> None:
        self._emit(StatusMsg(t=ServerType.STATUS, status=self.status()))

    def _publish(self, upserted: list[str], gone: list[str]) -> None:
        for el_id in gone:
            self._emit(GoneMsg(t=ServerType.GONE, id=el_id))
        for el_id in upserted:
            if (el := self.elements.get(el_id)) is not None:
                self._emit(UpsertMsg(t=ServerType.UPSERT, element=el))
        self._emit_status()
        if self.on_persist is not None:
            self.on_persist()

    def _log(self, kind: ChangeKind, el_id: str = "", anchor: str = "", **extra: str | None) -> int:
        self.seq += 1
        self.changes.append(Change(seq=self.seq, kind=kind, id=el_id, anchor=anchor, **extra))
        return self.seq

    # -- labels --------------------------------------------------------------------------------

    def label_of(self, ref: AnchorRef) -> str | None:
        return label_in(self.elements, ref)

    @staticmethod
    def _find(work: dict[str, Element], el_id: str) -> Element:
        if (el := work.get(el_id)) is None:
            known = ", ".join(work) or "none"
            raise PathError(f"no element '{el_id}' (ids: {known})")
        return el

    def _resolve(self, work: dict[str, Element], label: str) -> tuple[Element, str]:
        el_id, _, suffix = label.partition(".")
        el = self._find(work, el_id)
        return el, el.resolve(suffix)

    @staticmethod
    def _drop_dangling(work: dict[str, Element]) -> list[str]:
        """Remove elements, such as links, whose ends no longer exist; returns their ids."""

        def alive(ref: AnchorRefLike) -> bool:
            el = work.get(ref.id)
            return el is not None and ref.anchor in el.anchor_keys()

        dead = [el.id for el in work.values() if not all(alive(ref) for ref in el.ends())]
        for el_id in dead:
            del work[el_id]
        return dead

    # -- agent ---------------------------------------------------------------------------------

    def apply(self, ops: list[Op]) -> None:
        """Apply agent ops all-or-nothing."""
        work: dict[str, Element] = {k: v.model_copy(deep=True) for k, v in self.elements.items()}
        touched: list[str] = []
        for n, op in enumerate(ops, start=1):
            try:
                touched += self._apply_op(work, op)
            except (PathError, MarkdownError, ValidationError) as exc:
                raise OpError(f"op {n} ({op.op}) failed, nothing applied: {exc}") from None
        gone = [el_id for el_id in self.elements if el_id not in work]
        gone += self._drop_dangling(work)
        for el in work.values():
            el.prune_feedback()
        self.elements = work
        self._publish(upserted=list(dict.fromkeys(t for t in touched if t in work)), gone=gone)

    def _apply_op(self, work: dict[str, Element], op: Op) -> list[str]:
        match op:
            case PutOp():
                return [self._put(work, op)]
            case SetOp(at=at, value=value):
                el, anchor = self._resolve(work, at)
                el.set_value(anchor, value)
                el.mark_revised(anchor)
                return [el.id]
            case InsertOp(at=at, value=value):
                el_id, _, suffix = at.partition(".")
                el = self._find(work, el_id)
                el.insert(suffix, value, self.new_id, Author.AGENT)
                return [el.id]
            case RemoveOp(at=at):
                el, anchor = self._resolve(work, at)
                if anchor == "":
                    del work[el.id]
                    return []
                el.remove(anchor)
                return [el.id]
            case ReplyOp(at=at, text=text):
                el, anchor = self._resolve(work, at)
                el.feedback_at(anchor).comments.append(
                    Comment(id=self.new_id("c"), author=Author.AGENT, text=text, seq=self.seq)
                )
                return [el.id]
            case LinkOp(src=src, dst=dst, text=text, id=link_id):
                (a, a_anchor), (b, b_anchor) = self._resolve(work, src), self._resolve(work, dst)
                link = LinkEl(
                    kind=ElementKind.LINK,
                    id=link_id or self.new_id("l"),
                    author=Author.AGENT,
                    src=AnchorRef(id=a.id, anchor=a_anchor),
                    dst=AnchorRef(id=b.id, anchor=b_anchor),
                    text=text,
                )
                work[link.id] = link
                return [link.id]
            case ClearOp():
                work.clear()
                return []

    def _put(self, work: dict[str, Element], op: PutOp) -> str:
        new: Box = build_box(id=op.id, md=op.md, title=op.title, kind=op.kind, ids=self.new_id, author=Author.AGENT)
        if (old := work.get(op.id)) is not None:
            new.succeed(old)
        work[op.id] = new
        return op.id

    def report(self) -> str:
        """Compact delta of user changes since the last read; advances the cursor."""
        lines = summarize(self.elements, self.changes, since=self.cursor)
        self.cursor = self.seq
        self._emit_status()
        if self.on_persist is not None:
            self.on_persist()
        return "\n".join(lines) if lines else "no changes"

    def show(self, ids: list[str]) -> str:
        wanted = list(self.elements) if ids == ["*"] else ids
        out = [
            render_element(self.elements, el) if (el := self.elements.get(el_id)) else f"{el_id}: no such element"
            for el_id in wanted
        ]
        return "\n\n".join(out) if out else "board is empty"

    def unread_submit(self) -> bool:
        return any(c.kind == ChangeKind.SUBMIT and c.seq > self.cursor for c in self.changes)

    async def wait_for_submit(
        self, limit: float, tick: Callable[[float], Awaitable[None]], interval: float = 15.0
    ) -> bool:
        """Block until the user submits or `limit` seconds pass; `tick` runs every `interval`."""
        start = time.monotonic()
        self.waiting += 1
        self._emit_status()
        try:
            while not self.unread_submit():
                remaining = limit - (time.monotonic() - start)
                if remaining <= 0:
                    return False
                event = self._submitted
                try:
                    async with asyncio.timeout(min(interval, remaining)):
                        await event.wait()
                except TimeoutError:
                    await tick(time.monotonic() - start)
            return True
        finally:
            self.waiting -= 1
            self._emit_status()

    # -- user ----------------------------------------------------------------------------------

    def handle(self, msg: ClientMsg) -> None:
        """Apply one page message. Raises UserError when it does not apply."""
        try:
            self._handle(msg)
        except PathError as exc:
            raise UserError(str(exc)) from None

    def _box(self, el_id: str) -> Box:
        match self._find(self.elements, el_id):
            case LinkEl():
                raise PathError(f"{el_id} is a link")
            case box:
                return box

    def _handle(self, msg: ClientMsg) -> None:
        match msg:
            case MoveMsg(id=el_id, x=x, y=y):
                box = self._box(el_id)
                box.x, box.y = x, y
                self._publish([el_id], [])
            case PlaceMsg(id=el_id, x=x, y=y):
                box = self._box(el_id)
                if box.x is None or box.y is None:
                    box.x, box.y = x, y
                    self._publish([el_id], [])
            case ResizeMsg(id=el_id, w=w):
                self._box(el_id).w = w
                self._publish([el_id], [])
            case ReactMsg(id=el_id, anchor=anchor, reaction=reaction):
                el = self._find(self.elements, el_id)
                fb = el.feedback_at(anchor)
                fb.reaction, fb.revised = reaction, False
                el.prune_feedback()
                self._log(ChangeKind.REACT, el_id, anchor)
                self._publish([el_id], [])
            case CommentMsg(id=el_id, anchor=anchor, text=text):
                el = self._find(self.elements, el_id)
                fb = el.feedback_at(anchor)
                seq = self._log(ChangeKind.COMMENT, el_id, anchor)
                fb.comments.append(Comment(id=self.new_id("c"), author=Author.USER, text=text, seq=seq))
                fb.revised = False
                self._publish([el_id], [])
            case UncommentMsg(id=el_id, anchor=anchor, cid=cid):
                el = self._find(self.elements, el_id)
                fb = el.feedback_at(anchor)
                fb.comments = [c for c in fb.comments if not (c.id == cid and c.author == Author.USER)]
                el.prune_feedback()
                self._publish([el_id], [])
            case EditMsg(id=el_id, anchor=anchor, value=value):
                el = self._find(self.elements, el_id)
                el.set_value(anchor, value)
                self._log(ChangeKind.EDIT, el_id, anchor)
                self._publish([el_id], [])
            case AddMsg(id=el_id, value=value):
                el = self._find(self.elements, el_id)
                anchor = el.insert("", value, self.new_id, Author.USER)
                self._log(ChangeKind.ADD, el_id, anchor)
                self._publish([el_id], [])
            case RemoveMsg(id=el_id, anchor=anchor):
                self._remove_part(el_id, anchor)
            case NoteMsg(x=x, y=y, text=text):
                note = TextEl(
                    kind=ElementKind.TEXT, id=self.new_id("n"), author=Author.USER, title=None, body=text, x=x, y=y
                )
                self.elements[note.id] = note
                self._log(ChangeKind.CREATE, note.id)
                self._publish([note.id], [])
            case LinkMsg(src=src, dst=dst, text=text):
                for ref in (src, dst):
                    if ref.anchor not in self._find(self.elements, ref.id).anchor_keys():
                        raise PathError(f"{ref.id} has no anchor '{ref.anchor}'")
                link = LinkEl(
                    kind=ElementKind.LINK, id=self.new_id("l"), author=Author.USER, src=src, dst=dst, text=text
                )
                self.elements[link.id] = link
                self._log(ChangeKind.CREATE, link.id)
                self._publish([link.id], [])
            case DeleteMsg(id=el_id):
                self._delete(el_id)
            case SubmitMsg(message=message):
                self._log(ChangeKind.SUBMIT, text=message.strip() if message and message.strip() else None)
                self._submitted.set()
                self._submitted = asyncio.Event()
                self._publish([], [])

    def _remove_part(self, el_id: str, anchor: str) -> None:
        el = self._find(self.elements, el_id)
        label = el.label(anchor)
        text = el.remove(anchor)
        el.prune_feedback()
        gone = self._drop_dangling(self.elements)
        self._log(ChangeKind.REMOVE, el_id, anchor, label=label, text=text)
        self._publish([el_id], gone)

    def _delete(self, el_id: str) -> None:
        el = self._find(self.elements, el_id)
        if el.author != Author.USER:
            raise PathError(f"{el_id} belongs to the agent; react or comment instead")
        snapshot = render_element(self.elements, el)
        del self.elements[el_id]
        gone = [el_id, *self._drop_dangling(self.elements)]
        self._log(ChangeKind.DELETE, el_id, text=snapshot)
        self._publish([], gone)
