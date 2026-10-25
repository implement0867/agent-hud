import { Whiteboard } from "~/components/Whiteboard";
import { BoardProvider } from "~/data/BoardProvider";

export const App = () => (
  <main className="flex h-screen flex-col">
    <BoardProvider>
      <Whiteboard />
    </BoardProvider>
  </main>
);
