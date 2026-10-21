import { Notice } from "~/components/Notice";
import { Whiteboard } from "~/components/Whiteboard";
import { ConnectionStatus, useBoard } from "~/hooks/useBoard";
import { assertNever } from "~/lib/assertNever";

export const BoardView = () => {
  const connection = useBoard();
  switch (connection.status) {
    case ConnectionStatus.enum.connecting:
      return <Notice>Connecting to the agent…</Notice>;
    case ConnectionStatus.enum.live:
      return <Whiteboard board={connection.board} act={connection.act} />;
    case ConnectionStatus.enum.closed:
      return (
        <Notice>
          The agent closed the board. Reload the page after it starts again.
        </Notice>
      );
    default:
      return assertNever(connection);
  }
};
