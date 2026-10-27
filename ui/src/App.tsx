import { BoardPicker } from "~/components/BoardPicker";
import { Whiteboard } from "~/components/Whiteboard";
import { BoardProvider } from "~/data/BoardProvider";
import { boardInUrl } from "~/data/boards";

export const App = () => (
  <main className="flex h-screen flex-col">
    {boardInUrl() === null ? (
      <BoardPicker />
    ) : (
      <BoardProvider>
        <Whiteboard />
      </BoardProvider>
    )}
  </main>
);
