import { useState } from "react";

import { messageSchema } from "~/domain/actions";

/** Text that the user is writing, kept by the composer's parent so that it survives the composer closing. */
export type TDraft = { text: string; set: (text: string) => void };

type TComposerProps = {
  label: string;
  id: string;
  send: (text: string) => Promise<boolean>;
  draft: TDraft;
};

/** The reply field of a thread: Enter posts the comment and Shift+Enter starts a new line; the text stays until the server takes it. The comment is pending until Send, in the chat. */
export const Composer = ({ label, id, send, draft }: TComposerProps) => {
  const [sending, setSending] = useState(false);
  const ready = !sending && messageSchema.safeParse(draft.text).success;
  const submit = async () => {
    if (!ready) return;
    setSending(true);
    if (await send(draft.text)) draft.set("");
    setSending(false);
  };
  return (
    <textarea
      rows={1}
      aria-label={label}
      placeholder={label}
      id={id}
      title="Enter posts the comment; Send, in the chat, sends it"
      className="field-sizing-content max-h-32 min-h-6 w-full resize-none rounded-xl bg-surface-sunken px-2 py-1 text-md/4 text-ink outline-none placeholder:text-ink-ghost focus:ring-2 focus:ring-accent-ring"
      value={draft.text}
      readOnly={sending}
      onChange={(event) => {
        draft.set(event.target.value);
      }}
      onKeyDown={(event) => {
        event.stopPropagation();
        if (event.key === "Enter" && !event.shiftKey) {
          event.preventDefault();
          void submit();
        }
      }}
    />
  );
};
