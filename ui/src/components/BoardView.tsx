import { Cards } from "~/components/Cards";
import { Notice } from "~/components/Notice";
import { SendForm } from "~/components/SendForm";
import { ConnectionStatus, useBoard } from "~/hooks/useBoard";
import type { TConnection } from "~/hooks/useBoard";
import { assertNever } from "~/lib/assertNever";

const BoardContent = ({ connection }: { connection: TConnection }) => {
  switch (connection.status) {
    case ConnectionStatus.enum.connecting:
      return <Notice>Connecting to the agent…</Notice>;
    case ConnectionStatus.enum.live:
      return <Cards board={connection.board} />;
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

/** The form stays mounted in every state, so its text stays when the connection changes. */
export const BoardView = () => {
  const connection = useBoard();
  return (
    <>
      <BoardContent connection={connection} />
      <SendForm connection={connection} />
    </>
  );
};
