from agent_hud.boards import TBoardName
from agent_hud.models.state import BoardState


class MemoryStore:
    """The state of each board in a dict, for the tests: each change is durable at once."""

    def __init__(self) -> None:
        self.states: dict[TBoardName, BoardState] = {}

    def list_board_names(self) -> list[TBoardName]:
        return list(self.states)

    def add_board(self, name: TBoardName) -> None:
        if name in self.states:
            raise ValueError(f"a board '{name}' exists")
        self.states[name] = BoardState()

    def remove_board(self, name: TBoardName) -> None:
        del self.states[name]

    def load_board_state(self, name: TBoardName) -> BoardState:
        return self.states[name]

    def save_board_state(self, name: TBoardName, state: BoardState) -> None:
        self.states[name] = state

    def commit(self) -> None:
        pass
