import { createStore } from "~/lib/store";
import type { AnchorRef } from "~/protocol/schema";

export type Tool = "select" | "hand" | "note" | "link";

export type Viewport = { x: number; y: number; zoom: number };

export type UiState = {
  tool: Tool;
  /** Selected element id (card or link). */
  selected: string | null;
  viewport: Viewport;
  /** First end of an arrow being drawn. */
  linkFrom: AnchorRef | null;
  /** Arrow waiting for its text, with the screen point to show the input at. */
  linkDraft: { src: AnchorRef; dst: AnchorRef; sx: number; sy: number } | null;
  /** Sticky note being typed at a world position. */
  noteDraft: { x: number; y: number } | null;
  /** Local positions for cards this tab placed, until the server echoes them. */
  placed: Readonly<Record<string, { x: number; y: number }>>;
};

export const uiStore = createStore<UiState>({
  tool: "select",
  selected: null,
  viewport: { x: 0, y: 0, zoom: 1 },
  linkFrom: null,
  linkDraft: null,
  noteDraft: null,
  placed: {},
});

export const setTool = (tool: Tool) => {
  uiStore.set((s) => ({
    ...s,
    tool,
    linkFrom: null,
    linkDraft: null,
    noteDraft: null,
  }));
};

export const select = (selected: string | null) => {
  uiStore.set((s) => (s.selected === selected ? s : { ...s, selected }));
};

/** Link tool: the first pick sets the tail, the second opens the text prompt. */
export const pickAnchor = (ref: AnchorRef, sx: number, sy: number) => {
  uiStore.set((s) => {
    if (s.linkFrom === null) return { ...s, linkFrom: ref };
    if (s.linkFrom.id === ref.id && s.linkFrom.anchor === ref.anchor)
      return { ...s, linkFrom: null };
    return {
      ...s,
      linkFrom: null,
      linkDraft: { src: s.linkFrom, dst: ref, sx, sy },
    };
  });
};

export const anchorKey = (id: string, anchor: string) => `${id}|${anchor}`;
