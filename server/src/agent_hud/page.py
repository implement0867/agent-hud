from agent_hud.changes import ChangeKind
from agent_hud.primitives import LinkEl, TextEl
from agent_hud.primitives.base import Author, Comment, PathError
from agent_hud.protocol import (
    AddMsg,
    ClientMsg,
    CommentMsg,
    DeleteMsg,
    EditMsg,
    LinkMsg,
    MoveMsg,
    NoteMsg,
    PlaceMsg,
    ReactMsg,
    RemoveMsg,
    ResizeMsg,
    SubmitMsg,
    UncommentMsg,
)
from agent_hud.state import BoardState, Delta


class UserError(ValueError):
    pass


def handle(state: BoardState, msg: ClientMsg) -> Delta:
    """Apply one message from a canvas tab."""
    try:
        return _handle(state, msg)
    except PathError as exc:
        raise UserError(str(exc)) from None


def _handle(state: BoardState, msg: ClientMsg) -> Delta:
    match msg:
        case MoveMsg(id=el_id, x=x, y=y):
            box = state.box(el_id)
            box.x, box.y = x, y
            return Delta(upserted=[el_id])
        case PlaceMsg(id=el_id, x=x, y=y):
            box = state.box(el_id)
            if box.x is not None and box.y is not None:
                return Delta()
            box.x, box.y = x, y
            return Delta(upserted=[el_id])
        case ResizeMsg(id=el_id, w=w):
            state.box(el_id).w = w
            return Delta(upserted=[el_id])
        case ReactMsg(id=el_id, anchor=anchor, reaction=reaction):
            el = state.find(el_id)
            fb = el.feedback_at(anchor)
            fb.reaction, fb.revised = reaction, False
            el.prune_feedback()
            state.log(ChangeKind.REACT, el_id, anchor)
            return Delta(upserted=[el_id])
        case CommentMsg(id=el_id, anchor=anchor, text=text):
            fb = state.find(el_id).feedback_at(anchor)
            seq = state.log(ChangeKind.COMMENT, el_id, anchor)
            fb.comments.append(Comment(id=state.new_id("c"), author=Author.USER, text=text, seq=seq))
            fb.revised = False
            return Delta(upserted=[el_id])
        case UncommentMsg(id=el_id, anchor=anchor, cid=cid):
            el = state.find(el_id)
            fb = el.feedback_at(anchor)
            fb.comments = [c for c in fb.comments if not (c.id == cid and c.author == Author.USER)]
            el.prune_feedback()
            return Delta(upserted=[el_id])
        case EditMsg(id=el_id, anchor=anchor, value=value):
            state.find(el_id).set_value(anchor, value)
            state.log(ChangeKind.EDIT, el_id, anchor)
            return Delta(upserted=[el_id])
        case AddMsg(id=el_id, value=value):
            item_id = state.new_id("k")
            state.find(el_id).insert(None, value, item_id, Author.USER)
            state.log(ChangeKind.ADD, el_id, item_id)
            return Delta(upserted=[el_id])
        case RemoveMsg(id=el_id, anchor=anchor):
            el = state.find(el_id)
            label = el.label(anchor)
            text = el.remove(anchor)
            el.prune_feedback()
            state.log(ChangeKind.REMOVE, el_id, anchor, label=label, text=text)
            return Delta(upserted=[el_id], gone=state.drop_dangling())
        case NoteMsg(x=x, y=y, text=text):
            note = TextEl(id=state.new_id("n"), author=Author.USER, body=text, x=x, y=y)
            state.elements[note.id] = note
            state.log(ChangeKind.CREATE, note.id)
            return Delta(upserted=[note.id])
        case LinkMsg(src=src, dst=dst, text=text):
            for ref in (src, dst):
                if state.label_of(ref) is None:
                    raise PathError(f"{ref.id} has no anchor '{ref.anchor}'")
            link = LinkEl(id=state.new_id("l"), author=Author.USER, src=src, dst=dst, text=text)
            state.elements[link.id] = link
            state.log(ChangeKind.CREATE, link.id)
            return Delta(upserted=[link.id])
        case DeleteMsg(id=el_id):
            el = state.find(el_id)
            if el.author != Author.USER:
                raise PathError(f"{el_id} belongs to the agent; react or comment instead")
            snapshot = el.render(state.label_of)
            del state.elements[el_id]
            state.log(ChangeKind.DELETE, el_id, text=snapshot)
            return Delta(gone=[el_id, *state.drop_dangling()])
        case SubmitMsg(message=message):
            state.log(ChangeKind.SUBMIT, text=(message or "").strip() or None)
            return Delta(submitted=True)
