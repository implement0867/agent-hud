import { CornerDownLeft } from "lucide-react";
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

/** The comment box: Enter posts the comment and Shift+Enter starts a new line; the text stays until the server takes it. The comment is pending until Send, in the chat. */
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
    <div className="flex items-end gap-1 rounded-2xl bg-surface-sunken p-1 focus-within:ring-2 focus-within:ring-accent-ring">
      <textarea
        rows={1}
        aria-label={label}
        placeholder={label}
        id={id}
        className="field-sizing-content max-h-40 min-h-8 flex-1 resize-none bg-transparent px-2 py-1.5 text-sm outline-none"
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
      <button
        type="button"
        aria-label="Post it"
        title="Post the comment (Enter); Send, in the chat, sends it"
        disabled={!ready}
        className="grid size-8 place-items-center rounded-full bg-accent text-white transition-opacity disabled:opacity-30"
        onClick={() => {
          void submit();
        }}
      >
        <CornerDownLeft className="size-4" />
      </button>
    </div>
  );
};
