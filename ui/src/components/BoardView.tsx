import { Notice } from "~/components/Notice";
import { Whiteboard } from "~/components/Whiteboard";
import { ConnectionStatus, useBoard } from "~/hooks/useBoard";
import { assertNever } from "~/lib/assertNever";
import type { TAct } from "~/lib/whiteboard";

/** No action reaches the board while the server is away. */
const offline: TAct = () => Promise.resolve(false);

export const BoardView = () => {
  const connection = useBoard();
  switch (connection.status) {
    case ConnectionStatus.enum.connecting:
      return <Notice>Connecting to the board…</Notice>;
    case ConnectionStatus.enum.live:
      return <Whiteboard snapshot={connection.snapshot} act={connection.act} />;
    case ConnectionStatus.enum.offline:
      return (
        <Whiteboard snapshot={connection.snapshot} act={offline} offline />
      );
    default:
      return assertNever(connection);
  }
};
