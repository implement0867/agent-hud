import { useCallback, useState } from "react";
import type { ChangeEvent, KeyboardEvent } from "react";

import { useStore } from "~/lib/store";
import { useSend } from "~/store/socket";
import { setTool, uiStore } from "~/store/ui";

const stop = (e: { stopPropagation: () => void }) => {
  e.stopPropagation();
};

/** Sticky note being typed, positioned in world units inside the canvas layer. */
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
  const onChange = useCallback((e: ChangeEvent<HTMLTextAreaElement>) => {
    setText(e.target.value);
  }, []);
  const finish = useCallback(() => {
    if (text.trim() !== "") send({ t: "note", x, y, text: text.trim() });
    setTool("select");
  }, [send, x, y, text]);
  const onKeyDown = useCallback(
    (e: KeyboardEvent<HTMLTextAreaElement>) => {
      e.stopPropagation();
      if (e.key === "Escape") setTool("select");
      if (e.key === "Enter" && !e.shiftKey) {
        e.preventDefault();
        finish();
      }
    },
    [finish],
  );
  return (
    <textarea
      className="note-draft"
      style={{ left: x, top: y }}
      value={text}
      onChange={onChange}
      onKeyDown={onKeyDown}
      onBlur={finish}
      onPointerDown={stop}
      placeholder="Note for the agent… Enter to place"
      autoFocus
    />
  );
};

/** Text prompt for a new arrow, shown in screen space near the arrow head. */
export const LinkDraft = () => {
  const draft = useStore(uiStore, (s) => s.linkDraft);
  if (draft === null) return null;
  return (
    <LinkEditor
      key={`${draft.src.id}|${draft.src.anchor}|${draft.dst.id}|${draft.dst.anchor}`}
    />
  );
};

const LinkEditor = () => {
  const send = useSend();
  const [text, setText] = useState("");
  const draft = useStore(uiStore, (s) => s.linkDraft);
  const onChange = useCallback((e: ChangeEvent<HTMLInputElement>) => {
    setText(e.target.value);
  }, []);
  const cancel = useCallback(() => {
    uiStore.set((s) => ({ ...s, linkDraft: null }));
  }, []);
  const finish = useCallback(() => {
    if (draft !== null)
      send({
        t: "link",
        src: draft.src,
        dst: draft.dst,
        text: text.trim() === "" ? null : text.trim(),
      });
    cancel();
  }, [send, draft, text, cancel]);
  const onKeyDown = useCallback(
    (e: KeyboardEvent<HTMLInputElement>) => {
      e.stopPropagation();
      if (e.key === "Escape") cancel();
      if (e.key === "Enter") finish();
    },
    [finish, cancel],
  );
  if (draft === null) return null;
  return (
    <div
      className="link-draft"
      style={{ left: draft.sx + 12, top: draft.sy + 12 }}
      onPointerDown={stop}
    >
      <input
        value={text}
        onChange={onChange}
        onKeyDown={onKeyDown}
        placeholder="Arrow text, e.g. “entails?” — Enter"
        autoFocus
      />
    </div>
  );
};
