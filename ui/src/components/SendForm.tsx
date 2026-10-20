import { useState } from "react";

import type { TBoardSocket } from "~/api/boardSocket";
import { Notice } from "~/components/Notice";
import { ConnectionStatus } from "~/hooks/useBoard";
import type { TConnection } from "~/hooks/useBoard";
import { assertNever } from "~/lib/assertNever";
import { invariant } from "~/lib/invariant";
import { Turn, messageSchema } from "~/schemas/events";
import type { TTurn } from "~/schemas/events";

const TurnNotice = ({ turn }: { turn: TTurn }) => {
  switch (turn) {
    case Turn.enum.agent:
      return <Notice>The agent is working. You can send when it waits.</Notice>;
    case Turn.enum.user:
      return <Notice>The agent waits for your message.</Notice>;
    default:
      return assertNever(turn);
  }
};

/** Send is on while the page is live, the agent waits, and the draft has text. The draft stays until the server confirms it. */
export const SendForm = ({ connection }: { connection: TConnection }) => {
  const [draft, setDraft] = useState("");
  const [sending, setSending] = useState(false);
  const send =
    connection.status === ConnectionStatus.enum.live &&
    connection.view.turn === Turn.enum.user &&
    !sending &&
    messageSchema.safeParse(draft).success
      ? connection.send
      : null;

  const sendDraft = async (send: TBoardSocket["send"]) => {
    setSending(true);
    if (await send(draft)) setDraft("");
    setSending(false);
  };

  return (
    <div className="flex flex-col gap-2">
      <div className="flex gap-2">
        <textarea
          className="flex-1 rounded-lg border border-stone-300 bg-white p-2"
          placeholder="Message to the agent"
          aria-label="Message to the agent"
          value={draft}
          readOnly={sending}
          onChange={(event) => {
            setDraft(event.target.value);
          }}
        />
        <button
          type="button"
          className="rounded-lg bg-stone-800 px-4 text-white hover:bg-stone-700 disabled:bg-stone-400"
          disabled={send === null}
          onClick={() => {
            invariant(send !== null, "the button is off without send");
            void sendDraft(send);
          }}
        >
          Send
        </button>
      </div>
      {connection.status === ConnectionStatus.enum.live ? (
        <TurnNotice turn={connection.view.turn} />
      ) : null}
    </div>
  );
};
