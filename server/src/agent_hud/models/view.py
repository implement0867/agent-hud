from enum import StrEnum

from agent_hud.models.base import Model
from agent_hud.models.board import Board


class Turn(StrEnum):
    agent = "agent"
    user = "user"


class View(Model):
    """What the page shows: the board, and whose turn it is. It is the user's turn while the agent waits."""

    board: Board
    turn: Turn
