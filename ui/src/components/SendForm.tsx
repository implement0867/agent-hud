import { useState } from "react";

import type { TBoardSocket } from "~/api/boardSocket";
import { ConnectionStatus } from "~/hooks/useBoard";
import type { TConnection } from "~/hooks/useBoard";
import { invariant } from "~/lib/invariant";
import { messageSchema } from "~/schemas/events";

/** Send is on while the page is live and the message has text. The message stays until the server confirms it. */
export const SendForm = ({ connection }: { connection: TConnection }) => {
  const [message, setMessage] = useState("");
  const [sending, setSending] = useState(false);
  const send =
    connection.status === ConnectionStatus.enum.live &&
    !sending &&
    messageSchema.safeParse(message).success
      ? connection.send
      : null;

  const sendMessage = async (send: TBoardSocket["send"]) => {
    setSending(true);
    if (await send(message)) setMessage("");
    setSending(false);
  };

  return (
    <div className="flex gap-2">
      <textarea
        className="flex-1 rounded-lg border border-stone-300 bg-white p-2"
        placeholder="Message to the agent"
        aria-label="Message to the agent"
        value={message}
        readOnly={sending}
        onChange={(event) => {
          setMessage(event.target.value);
        }}
      />
      <button
        type="button"
        className="rounded-lg bg-stone-800 px-4 text-white hover:bg-stone-700 disabled:bg-stone-400"
        disabled={send === null}
        onClick={() => {
          invariant(send !== null, "the button is off without send");
          void sendMessage(send);
        }}
      >
        Send
      </button>
    </div>
  );
};
