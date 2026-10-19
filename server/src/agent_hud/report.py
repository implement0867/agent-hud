from agent_hud.changes import Change, ChangeKind
from agent_hud.primitives import Element
from agent_hud.primitives.base import Author, quote
from agent_hud.state import BoardState


def _part_line(el: Element, anchor: str, group: list[Change], since: int) -> str | None:
    kinds = {c.kind for c in group}
    part = el.part(anchor)
    label = el.label(anchor)
    if part is None or label is None:
        removed = next((c for c in group if c.kind == ChangeKind.REMOVE), None)
        if removed is None or ChangeKind.ADD in kinds:
            return None
        return f"{removed.label} removed {quote(removed.text or '', 60)}"
    parts: list[str] = []
    if ChangeKind.ADD in kinds:
        parts.append(f"added {quote(part.text)}")
    elif ChangeKind.EDIT in kinds:
        parts.append(f"= {quote(part.text)}")
    fb = el.feedback.get(anchor)
    if ChangeKind.REACT in kinds:
        parts.append(fb.reaction if fb is not None and fb.reaction else "cleared reaction")
    if fb is not None:
        parts += [quote(c.text) for c in fb.comments if c.author == Author.USER and c.seq > since]
    return f"{label} {'; '.join(parts)}" if parts else None


def summarize(state: BoardState, since: int) -> list[str]:
    """One line per element the user created or deleted, per part they touched, and per Send."""
    lifecycle: dict[str, list[Change]] = {}
    touched: dict[tuple[str, str], list[Change]] = {}
    submits: list[Change] = []
    for change in (c for c in state.changes if c.seq > since):
        match change.kind:
            case ChangeKind.SUBMIT:
                submits.append(change)
            case ChangeKind.CREATE | ChangeKind.DELETE:
                lifecycle.setdefault(change.id, []).append(change)
            case _:
                touched.setdefault((change.id, change.anchor), []).append(change)
    lines: list[str] = []
    for el_id, changes in lifecycle.items():
        deleted = next((c for c in changes if c.kind == ChangeKind.DELETE), None)
        if deleted is not None:
            if changes[0].kind != ChangeKind.CREATE:
                lines.append(f"deleted {deleted.text or el_id}")
        elif (el := state.elements.get(el_id)) is not None:
            lines.append(el.render(state.label_of))
    for (el_id, anchor), group in touched.items():
        el = state.elements.get(el_id)
        if el_id in lifecycle or el is None:
            continue
        if (line := _part_line(el, anchor, group, since)) is not None:
            lines.append(line)
    lines += [f"submit {quote(s.text)}" if s.text else "submit" for s in submits]
    return lines


def report(state: BoardState) -> str:
    """The user's changes since the last report; marks them read."""
    lines = summarize(state, since=state.cursor)
    state.cursor = state.seq
    return "\n".join(lines) if lines else "no changes"


def show_cards(state: BoardState, ids: list[str]) -> str:
    wanted = list(state.elements) if ids == ["*"] else ids
    out = [
        el.render(state.label_of) if (el := state.elements.get(el_id)) is not None else f"{el_id}: no such element"
        for el_id in wanted
    ]
    return "\n\n".join(out) if out else "board is empty"
