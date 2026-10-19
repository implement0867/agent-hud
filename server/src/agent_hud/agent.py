from pydantic import ValidationError

from agent_hud.markdown import MarkdownError
from agent_hud.ops import ClearOp, InsertOp, LinkOp, Op, PutOp, RemoveOp, ReplyOp, SetOp
from agent_hud.primitives import AnchorRef, LinkEl, build_box
from agent_hud.primitives.base import Author, Comment, PathError
from agent_hud.state import BoardState, Delta


class OpError(ValueError):
    pass


def apply(state: BoardState, ops: list[Op]) -> Delta:
    """Apply agent ops to the state, all or nothing."""
    draft = state.model_copy(update={"elements": {k: v.model_copy(deep=True) for k, v in state.elements.items()}})
    touched: list[str] = []
    for n, op in enumerate(ops, start=1):
        try:
            touched += _apply_op(draft, op)
        except (PathError, MarkdownError, ValidationError) as exc:
            raise OpError(f"op {n} ({op.op}) failed, nothing applied: {exc}") from None
    gone = [el_id for el_id in state.elements if el_id not in draft.elements]
    gone += draft.drop_dangling()
    for el in draft.elements.values():
        el.prune_feedback()
    state.elements, state.next_id = draft.elements, draft.next_id
    return Delta(upserted=[t for t in touched if t in state.elements], gone=gone)


def _apply_op(draft: BoardState, op: Op) -> list[str]:
    match op:
        case PutOp(id=el_id, md=md, title=title, kind=kind):
            new = build_box(id=el_id, md=md, title=title, kind=kind, ids=draft.new_id, author=Author.AGENT)
            if (old := draft.elements.get(el_id)) is not None:
                new.succeed(old)
            draft.elements[el_id] = new
            return [el_id]
        case SetOp(at=at, value=value):
            el, anchor = draft.resolve(at)
            el.set_value(anchor, value)
            el.mark_revised(anchor)
            return [el.id]
        case InsertOp(at=at, value=value):
            el, anchor = draft.resolve(at)
            el.insert(anchor or None, value, draft.new_id("k"), Author.AGENT)
            return [el.id]
        case RemoveOp(at=at):
            el, anchor = draft.resolve(at)
            if anchor:
                el.remove(anchor)
                return [el.id]
            del draft.elements[el.id]
            return []
        case ReplyOp(at=at, text=text):
            el, anchor = draft.resolve(at)
            comment = Comment(id=draft.new_id("c"), author=Author.AGENT, text=text, seq=draft.seq)
            el.feedback_at(anchor).comments.append(comment)
            return [el.id]
        case LinkOp(src=src, dst=dst, text=text, id=link_id):
            (a, a_anchor), (b, b_anchor) = draft.resolve(src), draft.resolve(dst)
            link = LinkEl(
                id=link_id or draft.new_id("l"),
                author=Author.AGENT,
                src=AnchorRef(id=a.id, anchor=a_anchor),
                dst=AnchorRef(id=b.id, anchor=b_anchor),
                text=text,
            )
            draft.elements[link.id] = link
            return [link.id]
        case ClearOp():
            draft.elements.clear()
            return []
