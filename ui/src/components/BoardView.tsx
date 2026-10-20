import { Cards } from "~/components/Cards";
import { Notice } from "~/components/Notice";
import { SendForm } from "~/components/SendForm";
import { ConnectionStatus, useBoard } from "~/hooks/useBoard";
import { assertNever } from "~/lib/assertNever";

export const BoardView = () => {
  const connection = useBoard();
  switch (connection.status) {
    case ConnectionStatus.enum.connecting:
      return <Notice>Connecting to the agent…</Notice>;
    case ConnectionStatus.enum.live:
      return (
        <>
          <Cards board={connection.board} />
          <SendForm send={connection.send} />
        </>
      );
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
