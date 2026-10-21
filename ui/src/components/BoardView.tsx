import { useRef } from "react";

import { Arrows } from "~/components/Arrows";
import type { TBoardSocket } from "~/api/boardSocket";
import { Cards } from "~/components/Cards";
import { Notice } from "~/components/Notice";
import { SendForm } from "~/components/SendForm";
import { ConnectionStatus, useBoard } from "~/hooks/useBoard";
import type { TConnection } from "~/hooks/useBoard";
import { assertNever } from "~/lib/assertNever";
import { ActionKind } from "~/schemas/actions";
import type { TBoard } from "~/schemas/board";

const LiveBoard = ({
  board,
  act,
}: {
  board: TBoard;
  act: TBoardSocket["act"];
}) => {
  const container = useRef<HTMLDivElement>(null);
  return (
    <div ref={container} className="relative flex flex-col gap-4">
      <Cards board={board} act={act} />
      <Arrows board={board} container={container} act={act} />
    </div>
  );
};

const BoardContent = ({ connection }: { connection: TConnection }) => {
  switch (connection.status) {
    case ConnectionStatus.enum.connecting:
      return <Notice>Connecting to the agent…</Notice>;
    case ConnectionStatus.enum.live:
      return <LiveBoard board={connection.board} act={connection.act} />;
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

export const BoardView = () => {
  const connection = useBoard();
  return (
    <>
      <BoardContent connection={connection} />
      <SendForm
        connection={connection}
        label="Note for the agent"
        button="Add note"
        body={(md) => ({
          kind: ActionKind.enum.put,
          id: `note-${crypto.randomUUID().slice(0, 8)}`,
          md,
        })}
      />
      <SendForm
        connection={connection}
        label="Message to the agent"
        button="Send"
        body={(text) => ({ kind: ActionKind.enum.say, text })}
      />
    </>
  );
};
