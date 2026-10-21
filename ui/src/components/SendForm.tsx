import { useState } from "react";

import type { TBoardSocket } from "~/api/boardSocket";
import { ConnectionStatus } from "~/hooks/useBoard";
import type { TConnection } from "~/hooks/useBoard";
import { invariant } from "~/lib/invariant";
import { messageSchema } from "~/schemas/actions";
import type { TBody } from "~/schemas/actions";

/** The button is on while the page is live and the box has text. The text stays until the server takes the action. */
export const SendForm = ({
  connection,
  label,
  button,
  body,
}: {
  connection: TConnection;
  label: string;
  button: string;
  body: (text: string) => TBody;
}) => {
  const [message, setMessage] = useState("");
  const [sending, setSending] = useState(false);
  const act =
    connection.status === ConnectionStatus.enum.live &&
    !sending &&
    messageSchema.safeParse(message).success
      ? connection.act
      : null;

  const sendMessage = async (act: TBoardSocket["act"]) => {
    setSending(true);
    if (await act(body(message))) setMessage("");
    setSending(false);
  };

  return (
    <div className="flex gap-2">
      <textarea
        className="flex-1 rounded-lg border border-stone-300 bg-white p-2"
        placeholder={label}
        aria-label={label}
        value={message}
        readOnly={sending}
        onChange={(event) => {
          setMessage(event.target.value);
        }}
      />
      <button
        type="button"
        className="rounded-lg bg-stone-800 px-4 text-white hover:bg-stone-700 disabled:bg-stone-400"
        disabled={act === null}
        onClick={() => {
          invariant(act !== null, "the button is off without act");
          void sendMessage(act);
        }}
      >
        {button}
      </button>
    </div>
  );
};
