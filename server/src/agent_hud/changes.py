import asyncio


class Changes:
    """Wakes the pages that wait for the next board change."""

    def __init__(self) -> None:
        self.next = asyncio.Event()

    def notify(self) -> None:
        self.next.set()
        self.next = asyncio.Event()
