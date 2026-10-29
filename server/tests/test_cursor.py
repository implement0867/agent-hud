from agent_hud.models.actions import Action, Author, TBody
from agent_hud.models.cursor import ReadCursor
from tests.factories import clear, comment, link, move, put, say


def note_all(cursor: ReadCursor, author: Author, *bodies: TBody) -> ReadCursor:
    for n, body in enumerate(bodies):
        cursor = cursor.note(Action(id=f"{author}{n}", author=author, body=body))
    return cursor


def test_the_unread_cards_are_the_cards_changed_since_the_last_read() -> None:
    """Assemble: a cursor that read four cards, after which the agent puts one, and the user comments on another, links the third to it, moves the fourth and says a message.
    Act: mark the first two cards read, with the five messages; then note a clear.
    Assert: all four cards are unread before the mark, the last two after it with the messages read, and none after the clear, which starts the messages again."""
    cursor = note_all(
        ReadCursor(), Author.agent, put("a", "1. a"), put("b", "1. b"), put("c", "1. c"), put("d", "1. d")
    )
    cursor = cursor.mark_read(frozenset(cursor.unread_cards), 0)
    cursor = note_all(cursor, Author.agent, put("a", "1. a2"))
    cursor = note_all(
        cursor, Author.user, comment("b", "why?", "b"), link("arrow", "c", "b", quote="c"), move("d", 1, 1), say("look")
    )
    assert cursor.unread_cards == {"a", "b", "c", "d"}
    cursor = cursor.mark_read(frozenset({"a", "b"}), 5)
    assert (cursor.unread_cards, cursor.read_message_count) == ({"c", "d"}, 5)
    cursor = note_all(cursor, Author.agent, clear())
    assert (cursor.unread_cards, cursor.read_message_count) == (frozenset(), 0)
