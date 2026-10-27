import sqlite3
from pathlib import Path
from typing import Protocol

from agent_hud.models.actions import Action
from agent_hud.models.board import Board


class Store(Protocol):
    """
    The state of one board: the board at a checkpoint, the actions from there on, each at its sequence number, and
    the sequence number up to which an agent has had the actions.
    """

    def load(self) -> tuple[int, Board, list[Action], int]:
        """
        The checkpoint's sequence number and board, the actions from there on, and the agent's sequence number.
        ValidationError when the store holds a board or an action that this version does not take.
        """
        ...

    def append(self, seq: int, actions: list[Action]) -> None:
        """Keep the actions, the first at the sequence number."""
        ...

    def compact(self, seq: int, board: Board, read: int) -> None:
        """Make the board, which the actions before the sequence number made, the checkpoint; drop those actions; keep the agent's sequence number."""
        ...

    def keep_read(self, read: int) -> None:
        """Keep the sequence number up to which an agent has had the actions."""
        ...

    def close(self) -> None: ...


class SqliteStore:
    """
    The state in one SQLite file: the board at a checkpoint, the actions from there on, each at its sequence number,
    and the sequence number up to which an agent has had the actions. One process holds the file: RuntimeError when
    another does, so that two processes never keep two boards.
    """

    def __init__(self, path: Path) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        # Each "with self._db:" block is one transaction, committed at its end or rolled back on an error.
        self._db = sqlite3.connect(path, isolation_level="EXCLUSIVE", timeout=0.5)
        try:
            self._db.execute("PRAGMA locking_mode = EXCLUSIVE")
            self._db.execute("BEGIN EXCLUSIVE")
        except sqlite3.OperationalError as error:
            self._db.close()
            raise RuntimeError(
                f"another agent-hud holds {path}: the board lives in one process, so run one worker, "
                "or give this one its own AGENT_HUD_STATE_DIR"
            ) from error
        with self._db:
            self._db.execute("CREATE TABLE IF NOT EXISTS checkpoint (seq INTEGER NOT NULL, board TEXT NOT NULL)")
            self._db.execute("CREATE TABLE IF NOT EXISTS actions (seq INTEGER PRIMARY KEY, action TEXT NOT NULL)")
            self._db.execute("CREATE TABLE IF NOT EXISTS agent (seq INTEGER NOT NULL)")
            if self._db.execute("SELECT count(*) FROM checkpoint").fetchone() == (0,):
                self._db.execute("INSERT INTO checkpoint (seq, board) VALUES (0, ?)", (Board().model_dump_json(),))
                self._db.execute("INSERT INTO agent (seq) VALUES (0)")

    def load(self) -> tuple[int, Board, list[Action], int]:
        """
        The checkpoint's sequence number and board, the actions from there on, and the agent's sequence number.
        ValidationError when the file holds a board or an action that this version does not take.
        """
        seq, board = self._db.execute("SELECT seq, board FROM checkpoint").fetchone()
        rows = self._db.execute("SELECT action FROM actions WHERE seq >= ? ORDER BY seq", (seq,)).fetchall()
        (read,) = self._db.execute("SELECT seq FROM agent").fetchone()
        return seq, Board.model_validate_json(board), [Action.model_validate_json(row) for (row,) in rows], read

    def append(self, seq: int, actions: list[Action]) -> None:
        """Keep the actions, the first at the sequence number."""
        with self._db:
            self._db.executemany(
                "INSERT INTO actions (seq, action) VALUES (?, ?)",
                [(seq + n, action.model_dump_json()) for n, action in enumerate(actions)],
            )

    def compact(self, seq: int, board: Board, read: int) -> None:
        """Make the board, which the actions before the sequence number made, the checkpoint; drop those actions; keep the agent's sequence number."""
        with self._db:
            self._db.execute("UPDATE checkpoint SET seq = ?, board = ?", (seq, board.model_dump_json()))
            self._db.execute("DELETE FROM actions WHERE seq < ?", (seq,))
            self._db.execute("UPDATE agent SET seq = ?", (read,))

    def keep_read(self, read: int) -> None:
        """Keep the sequence number up to which an agent has had the actions."""
        with self._db:
            self._db.execute("UPDATE agent SET seq = ?", (read,))

    def close(self) -> None:
        self._db.close()
