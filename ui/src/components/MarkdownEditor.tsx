import { useState } from "react";
import type { ReactNode } from "react";

import { TextButton } from "~/components/TextButton";
import { Row } from "~/components/primitives/Flex";
import { keeps } from "~/domain/text";
import { mod } from "~/lib/keys";

type TAlertProps = { children: ReactNode; actions: ReactNode };

/** A question to the user under the text, with the answers as buttons. */
const Alert = ({ children, actions }: TAlertProps) => (
  <div
    role="alert"
    className="mt-2 rounded-lg bg-warning-faint px-2.5 py-1.5 text-sm text-warning-strong"
  >
    {children}
    <span className="mt-1 flex gap-3">{actions}</span>
  </div>
);

type TMarkdownEditorProps = {
  md: string;
  label: string;
  /** The words of the card's threads and arrows, which a change that drops them moves to the history. */
  quotes?: string[];
  /** Whether the card got a new version since the editor opened. */
  changed?: boolean;
  /** Whether a click outside saves the changes, as for a new card, rather than asks. */
  blurSaves?: boolean;
  /** Saves the text; over is true to replace a newer version of the card. */
  save: (md: string, over: boolean) => void;
  cancel: () => void;
};

/**
 * The card as its markdown, in a borderless monospace field, with only the hint that ⌘↵ saves. Esc and a click outside
 * close the editor while the text is as it was; with changes, a click outside asks to save or discard, or saves when
 * the editor saves on blur, as a new card's does, and Esc asks for a second Esc. When the words of a thread or an arrow
 * are gone from the new text, the save asks once and says how many go to the history. When the card got a new version
 * since the editor opened, the editor says so and offers to save over it. Each question shows only when it applies.
 */
export const MarkdownEditor = ({
  md,
  label,
  quotes = [],
  changed = false,
  blurSaves = false,
  save,
  cancel,
}: TMarkdownEditorProps) => {
  const [text, setText] = useState(md);
  const [asking, setAsking] = useState<"save" | "discard" | "moving" | null>(
    null,
  );
  const dirty = text.trim() !== "" && text !== md;
  const moving = dirty
    ? quotes.filter((quote) => !keeps(text, quote)).length
    : 0;
  const done = () => {
    if (!dirty) cancel();
    else if (changed) return;
    else if (moving > 0 && asking !== "moving") setAsking("moving");
    else save(text, false);
  };
  return (
    <div
      onPointerDown={(event) => {
        event.stopPropagation();
      }}
    >
      <textarea
        aria-label={label}
        aria-describedby="editor-keys"
        autoFocus
        spellCheck={false}
        className="field-sizing-content block min-h-24 w-full resize-none bg-transparent font-mono text-lg/relaxed  whitespace-pre-wrap text-ink outline-none placeholder:text-ink-ghost"
        value={text}
        onChange={(event) => {
          setText(event.target.value);
          if (asking === "discard") setAsking(null);
        }}
        onBlur={() => {
          if (!dirty) cancel();
          else if (blurSaves) done();
          else setAsking("save");
        }}
        onKeyDown={(event) => {
          event.stopPropagation();
          if (event.key === "Escape") {
            if (!dirty || asking === "discard") cancel();
            else setAsking("discard");
          }
          if (event.key === "Enter" && (event.metaKey || event.ctrlKey)) done();
        }}
      />
      {changed ? (
        <Alert
          actions={
            <>
              <TextButton
                variant="link"
                onClick={() => {
                  save(text, true);
                }}
              >
                Save over it
              </TextButton>
              <TextButton variant="link" onClick={cancel}>
                Discard mine
              </TextButton>
            </>
          }
        >
          The agent put a new version of this card while you edited; a save
          would replace it.
        </Alert>
      ) : asking === "moving" ? (
        <Alert
          actions={
            <>
              <TextButton
                variant="link"
                onClick={() => {
                  save(text, false);
                }}
              >
                Save anyway
              </TextButton>
              <TextButton
                variant="link"
                onClick={() => {
                  setAsking(null);
                }}
              >
                Keep editing
              </TextButton>
            </>
          }
        >
          Saving moves {moving}{" "}
          {moving === 1 ? "thread or arrow" : "threads or arrows"} on words you
          changed to the history.
        </Alert>
      ) : asking === "save" && dirty ? (
        <Alert
          actions={
            <>
              <TextButton variant="link" onClick={done}>
                Save
              </TextButton>
              <TextButton variant="link" onClick={cancel}>
                Discard
              </TextButton>
            </>
          }
        >
          Unsaved changes.
        </Alert>
      ) : null}
      <footer
        id="editor-keys"
        className="mt-2 flex items-center justify-end gap-2.5 text-sm/4 text-ink-faint"
      >
        {asking === "discard" ? (
          <span>esc again discards your changes</span>
        ) : (
          <Row as="span" align="center" gap={0.5}>
            <kbd className="kbd">{mod}</kbd>
            <kbd className="kbd">↵</kbd>
            <span className="ml-1">save</span>
          </Row>
        )}
      </footer>
    </div>
  );
};
