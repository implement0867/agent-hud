import { useState } from "react";
import type { ReactNode } from "react";

import { TextButton } from "~/components/TextButton";
import { mod } from "~/lib/keys";

/** The text with its whitespace collapsed, for a loose match of a part's text in markdown. */
const loose = (text: string) => text.replaceAll(/\s+/g, " ").trim();

/** The lines of the markdown as parts read them: without list markers, heading marks, quote marks and table pipes. */
const partLines = (md: string) =>
  md.split("\n").map((line) =>
    loose(
      line
        .replace(/^\s*(?:[-*+]|\d+[.)])\s+/, "")
        .replace(/^\s*#{1,6}\s+/, "")
        .replace(/^\s*>\s?/, "")
        .replaceAll("|", " "),
    ),
  );

type TAlertProps = { children: ReactNode; actions: ReactNode };

/** A question to the user under the text, with the answers as buttons. */
const Alert = ({ children, actions }: TAlertProps) => (
  <div
    role="alert"
    className="mt-2 rounded-lg bg-warning-faint px-2.5 py-1.5 text-[11px] text-warning-strong"
  >
    {children}
    <span className="mt-1 flex gap-3">{actions}</span>
  </div>
);

type TMarkdownEditorProps = {
  md: string;
  label: string;
  /** The page text of each part with feedback, values or arrows, which a change of the part moves to the history; "" moves on any change. */
  marked?: string[];
  /** Whether the card got a new version since the editor opened. */
  changed?: boolean;
  /** Whether a click outside saves the changes, as for a note, rather than asks. */
  blurSaves?: boolean;
  /** Saves the text; over is true to replace a newer version of the card. */
  save: (md: string, over: boolean) => void;
  cancel: () => void;
};

/**
 * A markdown editor with Save and Cancel; Cmd or Ctrl with Enter saves too. Esc and a click outside close the editor
 * while the text is as it was; with changes, a click outside keeps the editor open and asks to save or discard, or saves
 * when the editor saves on blur, as a note's does, and Esc asks for a second Esc. When the text of a part that has
 * feedback is gone from the new text, the save asks once and says how many parts lose their feedback to the history.
 * When the card got a new version since the editor opened, the editor says so and offers to save over it.
 */
export const MarkdownEditor = ({
  md,
  label,
  marked = [],
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
  const lines = partLines(text);
  const moving = marked.filter(
    (part) => part === "" || !lines.includes(loose(part)),
  ).length;
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
        autoFocus
        className="field-sizing-content min-h-24 w-full resize-none bg-transparent font-mono text-[13px] leading-relaxed text-ink outline-none"
        value={text}
        onChange={(event) => {
          setText(event.target.value);
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
          Saving moves the feedback on {moving}{" "}
          {moving === 1 ? "part" : "parts"} you changed to the history.
        </Alert>
      ) : (
        <p className="mt-1 flex items-center gap-3 text-[11px] text-ink-muted">
          <TextButton variant="link" onClick={done}>
            Save
          </TextButton>
          <TextButton variant="link" onClick={cancel}>
            Cancel
          </TextButton>
          <span className="text-ink-faint">
            {asking === "save"
              ? "unsaved changes"
              : asking === "discard"
                ? "esc again discards your changes"
                : `${mod}↵ saves`}
          </span>
        </p>
      )}
    </div>
  );
};
