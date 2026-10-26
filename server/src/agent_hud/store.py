import logging
import sqlite3
from collections.abc import Generator
from contextlib import contextmanager
from pathlib import Path

from pydantic import ValidationError

from agent_hud.models.actions import Action
from agent_hud.models.board import Board


class Store:
    """
    The state in one SQLite file: the board at a checkpoint, the actions from there on, each at its sequence number,
    and the sequence number up to which an agent has had the actions. One process holds the file: RuntimeError when
    another does, so that two processes never keep two boards.
    """

    def __init__(self, path: Path) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        self._db = sqlite3.connect(path, isolation_level=None, timeout=0.5)
        try:
            self._db.execute("PRAGMA locking_mode = EXCLUSIVE")
            self._db.execute("BEGIN EXCLUSIVE")
        except sqlite3.OperationalError as error:
            self._db.close()
            raise RuntimeError(
                f"another agent-hud holds {path}: the board lives in one process, so run one worker, "
                "or give this one its own AGENT_HUD_STATE_DIR"
            ) from error
        self._db.execute("CREATE TABLE IF NOT EXISTS checkpoint (seq INTEGER NOT NULL, board TEXT NOT NULL)")
        self._db.execute("CREATE TABLE IF NOT EXISTS actions (seq INTEGER PRIMARY KEY, action TEXT NOT NULL)")
        self._db.execute("CREATE TABLE IF NOT EXISTS agent (seq INTEGER NOT NULL)")
        if self._db.execute("SELECT count(*) FROM checkpoint").fetchone() == (0,):
            self._db.execute("INSERT INTO checkpoint (seq, board) VALUES (0, ?)", (Board().model_dump_json(),))
            self._db.execute("INSERT INTO agent (seq) VALUES (0)")
        self._db.execute("COMMIT")

    def load(self) -> tuple[int, Board, list[Action], int]:
        """The checkpoint's sequence number and board, the actions from there on, and the agent's sequence number."""
        seq, board = self._db.execute("SELECT seq, board FROM checkpoint").fetchone()
        rows = self._db.execute("SELECT action FROM actions WHERE seq >= ? ORDER BY seq", (seq,)).fetchall()
        (read,) = self._db.execute("SELECT seq FROM agent").fetchone()
        try:
            return seq, Board.model_validate_json(board), [Action.model_validate_json(row) for (row,) in rows], read
        except ValidationError:
            # A board of an earlier agent-hud, whose cards had parts and inputs, does not fit this one: start empty.
            logging.getLogger("agent_hud").warning(
                "the board in the state file is of an earlier version: starting empty"
            )
            self.compact(0, Board(), 0)
            self._db.execute("DELETE FROM actions")
            return 0, Board(), [], 0

    def append(self, seq: int, actions: list[Action]) -> None:
        """Keep the actions, the first at the sequence number."""
        with self._write():
            self._db.executemany(
                "INSERT INTO actions (seq, action) VALUES (?, ?)",
                [(seq + n, action.model_dump_json()) for n, action in enumerate(actions)],
            )

    def compact(self, seq: int, board: Board, read: int) -> None:
        """Make the board, which the actions before the sequence number made, the checkpoint; drop those actions; keep the agent's sequence number."""
        with self._write():
            self._db.execute("UPDATE checkpoint SET seq = ?, board = ?", (seq, board.model_dump_json()))
            self._db.execute("DELETE FROM actions WHERE seq < ?", (seq,))
            self._db.execute("UPDATE agent SET seq = ?", (read,))

    def keep_read(self, read: int) -> None:
        """Keep the sequence number up to which an agent has had the actions."""
        with self._write():
            self._db.execute("UPDATE agent SET seq = ?", (read,))

    def close(self) -> None:
        self._db.close()

    @contextmanager
    def _write(self) -> Generator[None]:
        """One transaction: all of the writes, or none."""
        self._db.execute("BEGIN")
        try:
            yield
        except BaseException:
            self._db.execute("ROLLBACK")
            raise
        self._db.execute("COMMIT")
