import { useCallback, useRef, useState } from "react";

import { CardFoldButton } from "~/components/CardFoldButton";
import { FoldedCard } from "~/components/FoldedCard";
import { MarkdownEditor } from "~/components/MarkdownEditor";
import { OpenCard } from "~/components/OpenCard";
import { ResizeOutline } from "~/components/ResizeOutline";
import type { THandle } from "~/components/ResizeOutline";
import { ScrollFades } from "~/components/ScrollFades";
import type { TCardView } from "~/data/boardModel";
import { useBoard, useStore } from "~/data/context";
import { ActionKind } from "~/domain/actions";
import { useFolds } from "~/hooks/useFolds";
import { usePointerDrag } from "~/hooks/usePointerDrag";
import { useScrollEnds } from "~/hooks/useScrollEnds";
import { SelectionKind, useWhiteboard } from "~/hooks/useWhiteboard";
import { FrameMode, findFrameStyle } from "~/lib/frame";
import type { TRect } from "~/lib/geometry";
import { invariant } from "~/lib/invariant";

type TCardFrameProps = {
  view: TCardView;
  scale: number;
  /** Takes the card's element when it mounts; returns what to do when it goes. */
  mount: (id: string, element: HTMLElement) => () => void;
};

/**
 * A card at its place on the board: its markdown from the first line, with no strip above it. A drag on the card's
 * padding moves it; the frame that shows on hover has a handle at each edge and corner, which sets the width, the height
 * or both. A click selects the card, a selection of its words opens the toolbar of the selection, and a double click
 * edits the markdown. A card shorter than its text scrolls, with fades at its ends. Cards may cross after their first
 * place; a touch puts the card on top of the others. A card without a place is hidden until the page gives it one.
 * The triangle at the card's first line folds it to that line on the sunken ground, with its threads' bubbles; each
 * heading's triangle folds its section. The folds are the viewer's own until the page reloads, and the agent's next
 * version opens the card.
 */
export const CardFrame = ({ view, scale, mount }: TCardFrameProps) => {
  const { id, card, at, versions, layer } = view;
  const store = useStore();
  const { model } = useBoard();
  const { selection, select, editing, edit, linking } = useWhiteboard();
  const frame = useRef<HTMLElement | null>(null);
  const body = useRef<HTMLDivElement | null>(null);
  const article = useCallback(
    (element: HTMLElement) => {
      frame.current = element;
      const unmount = mount(id, element);
      return () => {
        frame.current = null;
        unmount();
      };
    },
    [id, mount],
  );
  const { folded, cardFolds } = useFolds(id, card.md, model.board);
  const { ends, measureEnds } = useScrollEnds(body);
  /** The rect that a resize shows before the server has it, and the handle that makes it. */
  const [resizing, setResizing] = useState<{
    rect: TRect;
    handle: string | null;
    over: string;
  } | null>(null);
  const sizeKey = `${String(view.width)}x${String(view.height)}`;
  const live = resizing !== null && resizing.over === sizeKey ? resizing : null;
  const width = live?.rect.width ?? view.width;
  const height = live?.rect.height ?? view.height;
  const place = live === null ? at : { x: live.rect.x, y: live.rect.y };
  const rect = (): TRect => {
    invariant(
      frame.current !== null && at !== null,
      "a placed card takes a resize",
    );
    return {
      ...at,
      width: frame.current.offsetWidth,
      height: frame.current.offsetHeight,
    };
  };
  const commit = (next: TRect, handle: THandle) => {
    invariant(at !== null, "a placed card takes a resize");
    setResizing({ rect: next, handle: null, over: sizeKey });
    if (next.x !== at.x || next.y !== at.y)
      store.drop(id, { x: next.x, y: next.y });
    const sides = {
      ...(handle.e || handle.w ? { width: next.width } : {}),
      ...(handle.n || handle.s ? { height: next.height } : {}),
    };
    void store
      .act({ kind: ActionKind.enum.resize, id, ...sides })
      .then((taken) => {
        if (!taken) setResizing(null);
      });
  };
  const drag = usePointerDrag({
    scale,
    // The padding of the card and its frame move it; its words take a selection instead.
    from: (event) => {
      const target = event.target;
      if (at === null || !(target instanceof Element)) return null;
      return target.closest("[data-text-root], button, input, textarea, a") ===
        null
        ? at
        : null;
    },
    move: (to) => {
      store.drag(id, to);
    },
    drop: (to) => {
      store.drop(id, to);
    },
    click: () => {
      select({ kind: SelectionKind.enum.card, id });
    },
  });
  const editor = editing?.card === id ? editing : null;
  const mode =
    editor !== null
      ? FrameMode.enum.editing
      : folded
        ? FrameMode.enum.folded
        : FrameMode.enum.open;
  const save = async (md: string, over: boolean) => {
    invariant(editor !== null, "the editor saves while it is open");
    const version = over ? {} : { version: editor.versions };
    if (await store.act({ kind: ActionKind.enum.put, id, md, ...version }))
      edit(null);
  };
  const selected =
    selection?.kind === SelectionKind.enum.card && selection.id === id;
  const dropTarget = linking?.over === id && linking.from.card !== id;
  const ring =
    editor !== null
      ? "shadow-[var(--shadow-card),0_0_0_2px_var(--accent-ring)]"
      : dropTarget
        ? "shadow-[var(--shadow-card),0_0_0_2px_var(--draw)]"
        : selected
          ? "shadow-[var(--shadow-card),0_0_0_1.5px_var(--accent-ring)]"
          : "shadow-[var(--shadow-card),0_0_0_1px_var(--edge-faint)]";
  const scrolls = height !== null && mode !== FrameMode.enum.folded;
  return (
    <article
      ref={article}
      data-card={id}
      aria-label={`Card ${id}`}
      style={findFrameStyle(mode, { place, width, height, layer })}
      className={`group/card pointer-events-auto absolute flex animate-rise flex-col rounded-card transition-shadow ${mode === FrameMode.enum.folded ? "bg-surface-sunken" : "bg-surface"} ${ring}`}
      onPointerDownCapture={() => {
        store.touch(id);
      }}
      onClick={(event) => {
        event.stopPropagation();
        if (window.getSelection()?.isCollapsed !== false)
          select({ kind: SelectionKind.enum.card, id });
      }}
      onDoubleClick={(event) => {
        event.stopPropagation();
        window.getSelection()?.removeAllRanges();
        edit(id);
      }}
      {...drag}
    >
      <div
        ref={body}
        className={`relative min-h-0 flex-1 overflow-y-auto overscroll-contain rounded-card py-[var(--pad-y)] pr-11 pl-[var(--pad)] [scrollbar-color:var(--ink-ghost)_transparent] [scrollbar-width:thin] ${mode === FrameMode.enum.folded ? "" : "pb-[var(--pad)]"}`}
        onScroll={measureEnds}
        onPointerEnter={measureEnds}
      >
        {editor !== null ? (
          <MarkdownEditor
            md={card.md}
            label={`Markdown of ${id}`}
            quotes={editor.quotes}
            changed={editor.versions !== versions}
            save={(md, over) => {
              void save(md, over);
            }}
            cancel={() => {
              edit(null);
            }}
          />
        ) : folded ? (
          <FoldedCard id={id} md={card.md} body={body} />
        ) : (
          <OpenCard
            id={id}
            md={card.md}
            versions={versions}
            width={width}
            body={body}
            folds={cardFolds}
          />
        )}
      </div>
      <CardFoldButton mode={mode} md={card.md} folds={cardFolds} />
      {scrolls ? <ScrollFades {...ends} /> : null}
      {editor === null && at !== null && (
        <ResizeOutline
          id={id}
          scale={scale}
          rect={rect}
          activeHandle={live?.handle ?? null}
          shown={live !== null || selected}
          resizable={mode === FrameMode.enum.open}
          show={(next, handle) => {
            setResizing({ rect: next, handle, over: sizeKey });
          }}
          commit={commit}
        />
      )}
    </article>
  );
};
