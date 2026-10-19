"""Render user changes for the agent, one short line per touched part.

plan.3 approve
plan.2 question; "wording unclear"
plan.5 = "Use pnpm workspaces"
opts.r2.pick = yes
link l7 plan.6 -> plan.1 "entails?" by user
submit "Mostly fine"
"""

from agent_hud.changes import Change, ChangeKind
from agent_hud.primitives import AnchorRef, Element, LinkEl, TextEl
from agent_hud.primitives.base import Author, quote


def label_in(elements: dict[str, Element], ref: AnchorRef) -> str | None:
    el = elements.get(ref.id)
    return None if el is None else el.label(ref.anchor)


def render_element(elements: dict[str, Element], el: Element) -> str:
    match el:
        case LinkEl() as link:
            return link.render_with(lambda ref: label_in(elements, ref))
        case TextEl(author=Author.USER, body=body):
            return f"note {el.id} {quote(body)}{el.feedback_note('')}"
        case _:
            return el.render()


def _anchor_line(el: Element, anchor: str, group: list[Change], since: int) -> str | None:
    kinds = {c.kind for c in group}
    label = el.label(anchor)
    if label is None:
        removed = next((c for c in group if c.kind == ChangeKind.REMOVE), None)
        if removed is None or ChangeKind.ADD in kinds:
            return None
        return f"{removed.label} removed {quote(removed.text or '', 60)}"
    parts: list[str] = []
    if ChangeKind.ADD in kinds:
        parts.append(f"added {el.value_text(anchor)}")
    elif ChangeKind.EDIT in kinds:
        parts.append(f"= {el.value_text(anchor)}")
    fb = el.feedback.get(anchor)
    if ChangeKind.REACT in kinds:
        parts.append(fb.reaction if fb is not None and fb.reaction else "cleared reaction")
    if fb is not None:
        parts += [quote(c.text) for c in fb.comments if c.author == Author.USER and c.seq > since]
    if not parts:
        return None
    return f"{label} {'; '.join(parts)}"


def summarize(elements: dict[str, Element], changes: list[Change], since: int) -> list[str]:
    fresh = [c for c in changes if c.seq > since]
    created = {c.id for c in fresh if c.kind == ChangeKind.CREATE}
    deleted = {c.id: c for c in fresh if c.kind == ChangeKind.DELETE}
    groups: dict[tuple[str, str], list[Change]] = {}
    submits: list[Change] = []
    for change in fresh:
        match change.kind:
            case ChangeKind.SUBMIT:
                submits.append(change)
            case ChangeKind.CREATE | ChangeKind.DELETE:
                groups.setdefault((change.id, "\0"), []).append(change)
            case _:
                groups.setdefault((change.id, change.anchor), []).append(change)
    lines: list[str] = []
    for (el_id, anchor), group in groups.items():
        if el_id in created and el_id in deleted:
            continue
        if anchor == "\0":
            if el_id in deleted:
                lines.append(f"deleted {deleted[el_id].text or el_id}")
            elif (el := elements.get(el_id)) is not None:
                lines.append(render_element(elements, el))
            continue
        if el_id in created or el_id in deleted or (el := elements.get(el_id)) is None:
            continue
        if (line := _anchor_line(el, anchor, group, since)) is not None:
            lines.append(line)
    lines += [f"submit {quote(s.text)}" if s.text else "submit" for s in submits]
    return lines
