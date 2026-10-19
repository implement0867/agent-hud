import { useState } from "react";

import { stop } from "~/lib/dom";
import { useStore } from "~/lib/store";
import { useSend } from "~/store/socket";
import { setTool, uiStore } from "~/store/ui";
import type { LinkDraft as LinkDraftState } from "~/store/ui";

/** A sticky note being typed, in world units inside the canvas layer. */
export const NoteDraft = () => {
  const draft = useStore(uiStore, (s) => s.noteDraft);
  if (draft === null) return null;
  return (
    <NoteEditor
      key={`${String(draft.x)},${String(draft.y)}`}
      x={draft.x}
      y={draft.y}
    />
  );
};

const NoteEditor = ({ x, y }: { x: number; y: number }) => {
  const send = useSend();
  const [text, setText] = useState("");
  const finish = () => {
    if (text.trim() !== "") send({ t: "note", x, y, text: text.trim() });
    setTool("select");
  };
  return (
    <textarea
      className="note-draft"
      style={{ left: x, top: y }}
      value={text}
      onChange={(e) => {
        setText(e.target.value);
      }}
      onKeyDown={(e) => {
        e.stopPropagation();
        if (e.key === "Escape") setTool("select");
        if (e.key === "Enter" && !e.shiftKey) {
          e.preventDefault();
          finish();
        }
      }}
      onBlur={finish}
      onPointerDown={stop}
      placeholder="Note for the agent… Enter to place"
      autoFocus
    />
  );
};

/** The text prompt for a new arrow, in screen space near the arrow head. */
export const LinkDraft = () => {
  const draft = useStore(uiStore, (s) => s.linkDraft);
  if (draft === null) return null;
  const { src, dst } = draft;
  return (
    <LinkEditor
      key={`${src.id}|${src.anchor}|${dst.id}|${dst.anchor}`}
      draft={draft}
    />
  );
};

const LinkEditor = ({ draft }: { draft: LinkDraftState }) => {
  const send = useSend();
  const [text, setText] = useState("");
  const cancel = () => {
    uiStore.set((s) => ({ ...s, linkDraft: null }));
  };
  return (
    <div
      className="link-draft"
      style={{ left: draft.sx + 12, top: draft.sy + 12 }}
      onPointerDown={stop}
    >
      <input
        value={text}
        onChange={(e) => {
          setText(e.target.value);
        }}
        onKeyDown={(e) => {
          e.stopPropagation();
          if (e.key === "Escape") cancel();
          if (e.key === "Enter") {
            send({
              t: "link",
              src: draft.src,
              dst: draft.dst,
              text: text.trim(),
            });
            cancel();
          }
        }}
        placeholder="Arrow text, e.g. “entails?” — Enter"
        autoFocus
      />
    </div>
  );
};
