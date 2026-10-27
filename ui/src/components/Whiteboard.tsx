import {
  ArrowDown,
  ArrowLeft,
  ArrowRight,
  ArrowUp,
  WifiOff,
} from "lucide-react";
import type { LucideIcon } from "lucide-react";
import {
  useCallback,
  useEffect,
  useEffectEvent,
  useLayoutEffect,
  useMemo,
  useRef,
  useState,
} from "react";
import type { MouseEvent } from "react";

import { AgentPill } from "~/components/AgentPill";
import { ArrowLayer } from "~/components/ArrowLayer";
import { Canvas } from "~/components/Canvas";
import { CardFrame } from "~/components/CardFrame";
import { Chat } from "~/components/Chat";
import { HistoryDrawer } from "~/components/HistoryDrawer";
import { MarkdownEditor } from "~/components/MarkdownEditor";
import { SelectionToolbar } from "~/components/SelectionToolbar";
import { ShortcutSheet } from "~/components/ShortcutSheet";
import { TextButton } from "~/components/TextButton";
import { ThreadPopover } from "~/components/ThreadPopover";
import { Toolbar } from "~/components/Toolbar";
import type { TCardView } from "~/data/boardModel";
import { useBoard, useStore } from "~/data/context";
import { boardInUrl } from "~/data/boards";
import { ActionKind } from "~/domain/actions";
import { anchorsOn, newId, versionsOf } from "~/domain/board";
import type { TAnchor, TArrow, TPoint } from "~/domain/board";
import { cardTitle, short, squeeze } from "~/domain/text";
import { useLayout } from "~/hooks/useLayout";
import { useLinking } from "~/hooks/useLinking";
import { useSelection } from "~/hooks/useSelection";
import { RemovedKind, useUndo } from "~/hooks/useUndo";
import type { TRemoved } from "~/hooks/useUndo";
import { SelectionKind, WhiteboardContext } from "~/hooks/useWhiteboard";
import type { TEditing, TSelection } from "~/hooks/useWhiteboard";
import { anchorOfRange } from "~/lib/anchor";
import {
  anchorRange,
  cardElement,
  clientOnBoard,
  rectOnBoard,
} from "~/lib/dom";
import {
  centreOn,
  edgeTowards,
  fitAll,
  onScreen,
  overlap,
  placePanel,
  toBoard,
  zoomAt,
} from "~/lib/geometry";
import type { TDirection, TRect, TSize, TView } from "~/lib/geometry";
import { markRanges } from "~/lib/highlights";
import { invariant } from "~/lib/invariant";
import { LookContext, useLook } from "~/lib/look";

const home: TView = { x: 64, y: 64, scale: 1 };

/** The factor of one step of zoom, from the keys and the toolbar. */
const zoomStep = 1.25;

/** The size of a thread before it is measured: its 220 px width and a few comments. */
const panelGuess: TSize = { width: 220, height: 160 };

/** The size of a chip that points at a new card: its h-8 and max-w-45. */
const chipSize: TSize = { width: 180, height: 32 };

/** The size of a note being written, before it is measured: its w-96 and a few lines. */
const draftSize: TSize = { width: 384, height: 144 };

/** Whether a key goes to a field the user types in, rather than to the board. */
const typing = (target: EventTarget | null) =>
  target instanceof HTMLElement &&
  (target.isContentEditable ||
    ["INPUT", "TEXTAREA", "SELECT"].includes(target.tagName));

const chipArrows: Record<TDirection, LucideIcon> = {
  up: ArrowUp,
  down: ArrowDown,
  left: ArrowLeft,
  right: ArrowRight,
};

/** The title of the card on the board, or its id when it has none or is gone. */
const titleOf = (cards: Record<string, { md: string }>, id: string) => {
  const md = cards[id]?.md;
  return md === undefined ? id : cardTitle(md) || id;
};

/** The key that keeps, in the browser, how many comments of each thread the user has read on this board. */
const seenKey = () => `agent-hud:seen:${boardInUrl() ?? ""}`;

const readSeen = (): Record<string, number> => {
  try {
    const kept: unknown = JSON.parse(localStorage.getItem(seenKey()) ?? "{}");
    return typeof kept === "object" && kept !== null
      ? Object.fromEntries(
          Object.entries(kept).filter(
            (entry): entry is [string, number] => typeof entry[1] === "number",
          ),
        )
      : {};
  } catch {
    return {};
  }
};

type TNewCardChipProps = {
  id: string;
  at: TPoint & { direction: TDirection };
  show: (card: string) => void;
};

/** A chip at the edge of the view nearest to a card that arrived out of view; a click shows the card. */
const NewCardChip = ({ id, at, show }: TNewCardChipProps) => {
  const { model } = useBoard();
  const Arrow = chipArrows[at.direction];
  return (
    <button
      type="button"
      aria-label={`New card ${id}`}
      className="pointer-events-auto absolute flex h-8 max-w-45 animate-pop items-center gap-1.5 rounded-full bg-accent pr-3 pl-2 text-sm text-on-accent shadow-pop hover:bg-accent-strong"
      style={{ left: at.x, top: at.y }}
      onClick={() => {
        show(id);
      }}
    >
      <Arrow className="size-4 shrink-0" />
      <span className="truncate">new: {titleOf(model.board.cards, id)}</span>
    </button>
  );
};

type TDraftNoteProps = { at: TPoint; close: () => void };

/** A note that the user is writing; it goes on the board where it is when the user saves it. */
const DraftNote = ({ at, close }: TDraftNoteProps) => {
  const store = useStore();
  const save = async (md: string) => {
    const id = newId("note");
    if (!(await store.act({ kind: ActionKind.enum.put, id, md }))) return;
    await store.act({ kind: ActionKind.enum.move, id, ...at });
    close();
  };
  return (
    <div
      className="card pointer-events-auto absolute w-96 animate-pop px-[var(--pad)] py-[var(--pad-y)] shadow-[var(--shadow-card),0_0_0_2px_var(--accent-ring)]"
      style={{ left: at.x, top: at.y }}
    >
      <MarkdownEditor
        md=""
        label="New note"
        blurSaves
        save={(md) => {
          void save(md);
        }}
        cancel={close}
      />
    </div>
  );
};

/** The banner while the server is away; the board shows as it last was. */
const OfflineBanner = () => (
  <div role="alert" className="toast top-16 bg-danger! text-white!">
    <WifiOff className="size-4" />
    Board server not reachable, retrying…
  </div>
);

type TUndoToastProps = {
  removed: TRemoved;
  restore: (removed: TRemoved) => void;
};

/** The toast that offers the last removed card or arrow back; a removed card is named by the title of its last version. */
const UndoToast = ({ removed, restore }: TUndoToastProps) => {
  const { model } = useBoard();
  const last = model.board.history[removed.id]?.at(-1);
  return (
    <div role="status" className="toast bottom-20 gap-3">
      Removed{" "}
      {removed.kind === RemovedKind.enum.arrow
        ? "the arrow"
        : `“${last === undefined ? removed.id : cardTitle(last.card.md)}”`}
      <TextButton
        variant="onDark"
        onClick={() => {
          restore(removed);
        }}
      >
        Undo
      </TextButton>
    </div>
  );
};

type TLostArrowToastProps = { lost: { id: string; arrow: TArrow } };

/** The toast that says the agent removed one of the user's arrows, with a button that puts it back. */
const LostArrowToast = ({ lost: { id, arrow } }: TLostArrowToastProps) => {
  const store = useStore();
  const { model } = useBoard();
  const from =
    arrow.quote === ""
      ? titleOf(model.board.cards, arrow.card)
      : short(arrow.quote);
  return (
    <div
      role="status"
      aria-label="Arrow removed by the agent"
      className="toast bottom-32 gap-3"
    >
      The agent removed your arrow from “{from}” to “
      {titleOf(model.board.cards, arrow.dst)}”
      {arrow.text === "" ? "" : `, “${arrow.text}”`}
      <TextButton
        variant="onDark"
        onClick={() => {
          const { card, quote, occurrence, dst, text } = arrow;
          void store
            .act({
              kind: ActionKind.enum.link,
              id,
              card,
              quote,
              occurrence: quote === "" ? null : occurrence,
              dst,
              text,
            })
            .then((taken) => {
              if (taken) store.forgetLostArrow(id);
            });
        }}
      >
        Put it back
      </TextButton>
      <TextButton
        variant="onDark"
        label="Dismiss"
        onClick={() => {
          store.forgetLostArrow(id);
        }}
      >
        OK
      </TextButton>
    </div>
  );
};

/** A half-written comment, keyed by its thread or words, with its card's number of earlier versions when the user last typed. */
type TCommentDraft = { text: string; versions: number };

/** The words that the user selected in a card, and their range on the page. */
type TPicked = { anchor: TAnchor; range: Range };

/** The thread on the same words of the card, at the same place, if the board has one. */
const threadAt = (
  threads: Record<string, { card: string; quote: string; occurrence: number }>,
  anchor: TAnchor,
) =>
  Object.entries(threads).find(
    ([, thread]) =>
      thread.card === anchor.card &&
      squeeze(thread.quote) === squeeze(anchor.quote) &&
      thread.occurrence === anchor.occurrence,
  )?.[0] ?? null;

/**
 * The live board as a whiteboard: cards at their places, arrows from words to cards, the threads on the words of the
 * cards, the chat, whose turn it is, and the history of the cards when the user opens it.
 */
export const Whiteboard = () => {
  const { model, offline } = useBoard();
  const store = useStore();
  const viewport = useRef<HTMLDivElement>(null);
  const world = useRef<HTMLDivElement>(null);
  const [view, setView] = useState(home);
  const [look, changeLook] = useLook();
  const { layout, trackChrome, trackCard, cardSizes } = useLayout();
  const { selection, select, started, deselectArrow } = useSelection();
  const {
    removed,
    remove: removeCard,
    unlink: unlinkArrow,
    restore,
  } = useUndo(store.act);
  const [editing, setEditing] = useState<TEditing | null>(null);
  const [notes, setNotes] = useState<Record<string, TPoint>>({});
  const [comments, setComments] = useState<Record<string, TCommentDraft>>({});
  const [history, setHistory] = useState<{ card: string | null } | null>(null);
  const [sheet, setSheet] = useState(false);
  const [lookOpen, setLookOpen] = useState(false);
  const [picked, setPicked] = useState<TPicked | null>(null);
  const [seen, setSeen] = useState(readSeen);
  const { area } = layout;

  useEffect(() => {
    invariant(viewport.current !== null, "the canvas renders the viewport");
    return trackChrome("viewport", viewport.current);
  }, [trackChrome]);
  const trackChat = useCallback(
    (element: HTMLElement) => trackChrome("chat", element),
    [trackChrome],
  );
  const trackPanel = useCallback(
    (element: HTMLElement) => trackChrome("panel", element),
    [trackChrome],
  );
  /** The history docks at the left: the view moves right by its width while it is open, so that the cards stay in view. */
  const trackHistory = useCallback(
    (element: HTMLElement) => {
      const untrack = trackChrome("history", element);
      const shift = element.offsetLeft + element.offsetWidth + 16;
      setView((current) => ({ ...current, x: current.x + shift }));
      return () => {
        untrack();
        setView((current) => ({ ...current, x: current.x - shift }));
      };
    },
    [trackChrome],
  );
  const trackToolbar = useCallback(
    (element: HTMLElement) => trackChrome("toolbar", element),
    [trackChrome],
  );
  /** A card's element, once it is laid out: its size is tracked, and a card without a place gets one. */
  const mountCard = useCallback(
    (id: string, element: HTMLElement) => {
      const untrack = trackCard(id, element);
      store.place(id, cardSizes());
      return untrack;
    },
    [trackCard, store, cardSizes],
  );

  /** The thread is read: its bubble's count of new comments clears, in this browser. */
  const read = useCallback(
    (thread: string) => {
      const count = store.read().board.threads[thread]?.comments.length;
      if (count === undefined) return;
      setSeen((current) => {
        if (current[thread] === count) return current;
        const next = { ...current, [thread]: count };
        try {
          localStorage.setItem(seenKey(), JSON.stringify(next));
        } catch {
          // A browser that keeps nothing counts the comments again on the next load.
        }
        return next;
      });
    },
    [store],
  );

  /** Selects; opening a thread, or leaving one, reads it, so that its bubble counts no new comments. */
  const choose = useCallback(
    (next: TSelection) => {
      if (selection?.kind === SelectionKind.enum.thread) read(selection.id);
      if (next?.kind === SelectionKind.enum.thread) read(next.id);
      select(next);
    },
    [selection, select, read],
  );

  const { linking, beginLink } = useLinking(world, store.act, choose);

  const show = useCallback(
    (card: string, thread: string | null = null) => {
      const root = world.current;
      invariant(root !== null, "the canvas renders the world");
      const element = cardElement(root, card);
      if (element === null) return;
      choose(
        thread !== null && Object.hasOwn(store.read().board.threads, thread)
          ? { kind: SelectionKind.enum.thread, id: thread }
          : { kind: SelectionKind.enum.card, id: card },
      );
      const rect = rectOnBoard(element, root);
      setView((current) => centreOn(current, rect, area));
    },
    [choose, area, store],
  );

  const edit = useCallback(
    (card: string | null) => {
      if (card === null) {
        setEditing(null);
        return;
      }
      if (editing?.card === card) return;
      store.sawChanges(card);
      const { board } = store.read();
      setEditing({
        card,
        versions: versionsOf(board, card),
        quotes: anchorsOn(board, card).map(({ quote }) => quote),
      });
    },
    [store, editing],
  );

  const openHistory = useCallback((card: string | null) => {
    setHistory({ card });
  }, []);

  /** Removes the card, unless a snapshot took it away since the user asked. */
  const remove = useCallback(
    (id: string) => {
      const card = store.read().cards.find((view) => view.id === id);
      if (card !== undefined) removeCard(id, card.at);
    },
    [store, removeCard],
  );

  /** Removes the arrow, unless a snapshot took it away since the user asked. */
  const unlink = useCallback(
    (id: string) => {
      const arrow = store.read().board.arrows[id];
      if (arrow === undefined) return;
      void unlinkArrow(id, arrow).then((taken) => {
        if (taken) deselectArrow(id);
      });
    },
    [store, unlinkArrow, deselectArrow],
  );

  const whiteboard = useMemo(
    () => ({
      selection,
      select: choose,
      show,
      linking,
      editing,
      edit,
      openHistory,
      remove,
      unlink,
      seen,
      look,
    }),
    [
      selection,
      choose,
      show,
      linking,
      editing,
      edit,
      openHistory,
      remove,
      unlink,
      seen,
      look,
    ],
  );

  /** The words the user selects in a card: the toolbar of the selection shows above them once the press ends. */
  useEffect(() => {
    const pick = () => {
      const chosen = window.getSelection();
      const range =
        chosen === null || chosen.isCollapsed || chosen.rangeCount === 0
          ? null
          : chosen.getRangeAt(0);
      const start =
        range?.startContainer.parentElement?.closest("[data-text-root]");
      const end =
        range?.endContainer.parentElement?.closest("[data-text-root]");
      const card = start
        ?.closest("article[data-card]")
        ?.getAttribute("data-card");
      if (range == null || start == null || start !== end || card == null) {
        setPicked(null);
        return;
      }
      const words = anchorOfRange(start, range);
      setPicked(words === null ? null : { anchor: { card, ...words }, range });
    };
    const collapse = () => {
      if (window.getSelection()?.isCollapsed !== false) setPicked(null);
    };
    const listening = new AbortController();
    const { signal } = listening;
    document.addEventListener("pointerup", () => requestAnimationFrame(pick), {
      signal,
    });
    document.addEventListener(
      "keyup",
      (event) => {
        if (event.shiftKey || event.key === "Shift") pick();
      },
      { signal },
    );
    document.addEventListener("selectionchange", collapse, { signal });
    return () => {
      listening.abort();
    };
  }, []);

  /** Opens the thread on the selected words, or a new one there, and lets the selection go. */
  const commentOnPicked = () => {
    if (picked === null) return;
    const thread = threadAt(model.board.threads, picked.anchor);
    choose(
      thread === null
        ? { kind: SelectionKind.enum.draft, anchor: picked.anchor }
        : { kind: SelectionKind.enum.thread, id: thread },
    );
    window.getSelection()?.removeAllRanges();
    setPicked(null);
    requestAnimationFrame(() => {
      document.getElementById("comment-box")?.focus();
    });
  };

  /** Starts an arrow at the end of the selected words. */
  const arrowFromPicked = (event: MouseEvent) => {
    const root = world.current;
    if (picked === null || root === null) return;
    const last = [...picked.range.getClientRects()].at(-1);
    if (last === undefined) return;
    const end = clientOnBoard(last, root);
    beginLink(
      picked.anchor,
      { x: end.x + end.width + 2, y: end.y + end.height / 2 },
      event,
    );
    window.getSelection()?.removeAllRanges();
    setPicked(null);
  };

  /** The words of a new thread keep their mark while the user writes the first comment. */
  const draftAnchor =
    selection?.kind === SelectionKind.enum.draft ? selection.anchor : null;
  useEffect(() => {
    const root = world.current;
    const range =
      draftAnchor === null || root === null
        ? null
        : anchorRange(root, draftAnchor);
    markRanges("quote", "draft", range === null ? [] : [range]);
  }, [draftAnchor, model.board.cards]);

  /** The card's rect as the viewport shows it, or null until it is placed and measured. */
  const onView = ({ id, at }: TCardView) => {
    const size = layout.cards[id];
    return at === null || size === undefined
      ? null
      : onScreen(view, { ...at, ...size });
  };

  /** The thread that is open, with its words: a thread of the board, or the words of a new one. */
  const opened: { thread: string | null; anchor: TAnchor } | null =
    selection?.kind === SelectionKind.enum.thread
      ? (() => {
          const thread = model.board.threads[selection.id];
          return thread === undefined
            ? null
            : { thread: selection.id, anchor: thread };
        })()
      : selection?.kind === SelectionKind.enum.draft
        ? { thread: null, anchor: selection.anchor }
        : null;
  const openedCard =
    opened === null
      ? null
      : (model.cards.find((card) => card.id === opened.anchor.card) ?? null);
  const versions = openedCard?.versions ?? 0;
  const draftKey =
    opened === null
      ? null
      : (opened.thread ??
        `${opened.anchor.card}:${opened.anchor.quote}:${String(opened.anchor.occurrence)}`);
  const comment = draftKey === null ? undefined : comments[draftKey];

  /** The fresh cards that the view shows now stop being fresh; the others get a chip at the edge that points at them. */
  const fresh = model.cards.flatMap((card) => {
    const rect = model.fresh.includes(card.id) ? onView(card) : null;
    return rect === null ? [] : [{ id: card.id, rect }];
  });
  const seenCards = fresh
    .filter(({ rect }) => overlap(rect, area))
    .map(({ id }) => id);
  useEffect(() => {
    if (seenCards.length > 0) store.saw(seenCards);
  });
  const chips = fresh
    .filter(({ id }) => !seenCards.includes(id))
    .map(({ id, rect }) => ({ id, at: edgeTowards(rect, area, chipSize) }));

  /** Zooms in by the steps, or out by negative steps, about the centre of the free area. */
  const zoom = (steps: number) => {
    setView((current) =>
      zoomAt(current, zoomStep ** steps, {
        x: area.x + area.width / 2,
        y: area.y + area.height / 2,
      }),
    );
  };

  /** Fits the cards by their sizes as laid out now, so that a card the observer has not yet measured is not left out. */
  const fit = () => {
    const sizes = cardSizes();
    const rects = model.cards.flatMap((card) => {
      const size = sizes.get(card.id);
      return card.at === null || size === undefined
        ? []
        : [{ ...card.at, ...size }];
    });
    if (rects.length > 0) setView(fitAll(rects, area));
  };

  const send = () => {
    if (model.pending.length > 0)
      void store.act({ kind: ActionKind.enum.send });
  };

  /** A new note at the point, or at the centre of the free area, kept whole inside that area with a margin. */
  const note = (at?: TPoint) => {
    const { x, y, width, height } = area;
    const margin = 16;
    const centre = toBoard(view, {
      x: x + (width - draftSize.width) / 2,
      y: y + (height - draftSize.height) / 2,
    });
    const low = toBoard(view, { x: x + margin, y: y + margin });
    const high = toBoard(view, {
      x: x + width - draftSize.width - margin,
      y: y + height - draftSize.height - margin,
    });
    const wanted = at ?? centre;
    const place = {
      x: Math.max(low.x, Math.min(wanted.x, high.x)),
      y: Math.max(low.y, Math.min(wanted.y, high.y)),
    };
    setNotes((current) => ({ ...current, [newId("draft")]: place }));
  };

  const toggleHistory = () => {
    setHistory(history === null ? { card: null } : null);
  };

  /** Moves the selected card by the distance, as a drop does. */
  const nudge = (id: string, by: TPoint) => {
    const card = model.cards.find((found) => found.id === id);
    if (card?.at == null) return;
    store.drop(id, { x: card.at.x + by.x, y: card.at.y + by.y });
  };

  const onKey = useEffectEvent((event: KeyboardEvent) => {
    if (typing(event.target)) return;
    if ((event.metaKey || event.ctrlKey) && event.key === "Enter") {
      event.preventDefault();
      send();
      return;
    }
    if (event.metaKey || event.ctrlKey || event.altKey) return;
    const key = event.key.toLowerCase();
    const card =
      selection?.kind === SelectionKind.enum.card ? selection.id : null;
    const step = event.shiftKey ? 32 : 8;
    const arrows: Record<string, TPoint> = {
      arrowup: { x: 0, y: -step },
      arrowdown: { x: 0, y: step },
      arrowleft: { x: -step, y: 0 },
      arrowright: { x: step, y: 0 },
    };
    if (key === "escape") {
      if (sheet) setSheet(false);
      else if (lookOpen) setLookOpen(false);
      else if (picked !== null) {
        window.getSelection()?.removeAllRanges();
        setPicked(null);
      } else choose(null);
    } else if (key === "?") setSheet(!sheet);
    else if (key === "c" && picked !== null) {
      event.preventDefault();
      commentOnPicked();
    } else if (key === "n") note();
    else if (key === "h") toggleHistory();
    else if (key === "1") fit();
    else if (key === "0") setView(home);
    else if (key === "+" || key === "=") zoom(1);
    else if (key === "-") zoom(-1);
    else if (key === "m") document.getElementById("message-box")?.focus();
    else if (selection?.kind === SelectionKind.enum.arrow) {
      if (key === "delete" || key === "backspace") unlink(selection.id);
    } else if (card !== null) {
      const by = arrows[key];
      if (by !== undefined) {
        event.preventDefault();
        nudge(card, by);
      } else if (key === "e" || key === "enter") {
        event.preventDefault();
        edit(card);
      } else if (key === "delete" || key === "backspace") remove(card);
    }
  });
  useEffect(() => {
    const listener = (event: KeyboardEvent) => {
      onKey(event);
    };
    window.addEventListener("keydown", listener);
    return () => {
      window.removeEventListener("keydown", listener);
    };
  }, []);

  /**
   * Where the thread goes: beside its words, clear of the cards when it can be, the size it was last; and where the
   * toolbar of the selected words goes: above their end. Both read the page's layout, once it is laid out.
   */
  const [spots, setSpots] = useState<{
    panel: TPoint | null;
    toolbar: TPoint | null;
  }>({
    panel: null,
    toolbar: null,
  });
  const place = useEffectEvent(() => {
    const root = world.current;
    const box = viewport.current?.getBoundingClientRect();
    if (root === null || box === undefined) return;
    const inViewport = (rect: DOMRect): TRect => ({
      x: rect.left - box.left,
      y: rect.top - box.top,
      width: rect.width,
      height: rect.height,
    });
    const card = openedCard === null ? null : onView(openedCard);
    const words =
      opened === null
        ? undefined
        : [...(anchorRange(root, opened.anchor)?.getClientRects() ?? [])][0];
    const panel =
      opened === null || card === null
        ? null
        : placePanel(
            card,
            words === undefined ? { ...card, height: 24 } : inViewport(words),
            layout.panel ?? panelGuess,
            area,
            model.cards.flatMap((other) => onView(other) ?? []),
          );
    const rects =
      picked === null || linking !== null
        ? []
        : [...picked.range.getClientRects()];
    const first = rects[0];
    const last = rects.at(-1);
    const toolbar =
      first === undefined || last === undefined
        ? null
        : (() => {
            const top = inViewport(first);
            const end = inViewport(last);
            return { x: Math.max(end.x + end.width, top.x + 72), y: top.y };
          })();
    setSpots((current) =>
      JSON.stringify(current) === JSON.stringify({ panel, toolbar })
        ? current
        : { panel, toolbar },
    );
  });
  const openedKey = opened === null ? null : JSON.stringify(opened);
  useLayoutEffect(() => {
    place();
  }, [view, picked, linking, openedKey, layout, model]);
  const panelAt = spots.panel;
  const pickedAt = spots.toolbar;

  return (
    <WhiteboardContext value={whiteboard}>
      <LookContext value={look}>
        <Canvas
          view={view}
          setView={setView}
          viewport={viewport}
          world={world}
          clear={() => {
            choose(null);
          }}
          create={note}
          dimmed={offline}
          overlay={
            <>
              <AgentPill />
              {offline ? <OfflineBanner /> : null}
              {sheet ? (
                <ShortcutSheet
                  close={() => {
                    setSheet(false);
                  }}
                />
              ) : null}
              {history !== null && (
                <HistoryDrawer
                  card={history.card}
                  close={() => {
                    setHistory(null);
                  }}
                  measure={trackHistory}
                />
              )}
              {chips.map(({ id, at }) => (
                <NewCardChip key={id} id={id} at={at} show={show} />
              ))}
              {pickedAt !== null && (
                <SelectionToolbar
                  at={pickedAt}
                  drawing={false}
                  comment={commentOnPicked}
                  arrow={arrowFromPicked}
                />
              )}
              {opened !== null &&
              panelAt !== null &&
              linking === null &&
              draftKey !== null ? (
                <div
                  className="absolute"
                  style={{ left: panelAt.x, top: panelAt.y }}
                >
                  <ThreadPopover
                    key={draftKey}
                    thread={opened.thread}
                    anchor={opened.anchor}
                    maxHeight={Math.max(160, area.height - 16)}
                    measure={trackPanel}
                    started={started}
                    draft={{
                      text: comment?.text ?? "",
                      changed:
                        comment !== undefined && comment.versions !== versions,
                      set: (text) => {
                        setComments(({ [draftKey]: _old, ...rest }) =>
                          text === ""
                            ? rest
                            : { ...rest, [draftKey]: { text, versions } },
                        );
                      },
                    }}
                  />
                </div>
              ) : null}
              {removed !== null && (
                <UndoToast removed={removed} restore={restore} />
              )}
              {model.lostArrows[0] !== undefined && (
                <LostArrowToast lost={model.lostArrows[0]} />
              )}
              <Toolbar
                scale={view.scale}
                atHome={
                  view.x === home.x &&
                  view.y === home.y &&
                  view.scale === home.scale
                }
                zoom={zoom}
                reset={() => {
                  setView(home);
                }}
                fit={fit}
                note={note}
                history={history !== null}
                toggleHistory={toggleHistory}
                shortcuts={sheet}
                toggleShortcuts={() => {
                  setSheet(!sheet);
                }}
                look={look}
                changeLook={changeLook}
                lookOpen={lookOpen}
                toggleLook={() => {
                  setLookOpen(!lookOpen);
                }}
                measure={trackToolbar}
              />
              <Chat send={send} above={layout.toolbar} measure={trackChat} />
            </>
          }
        >
          {/* One stacking context for the cards, so that their layers stay under the arrows and the panel. */}
          <div className="pointer-events-none absolute inset-0 isolate">
            {model.cards.map((card) => (
              <CardFrame
                key={card.id}
                view={card}
                scale={view.scale}
                mount={mountCard}
              />
            ))}
          </div>
          <ArrowLayer world={world} linking={linking} />
          {Object.entries(notes).map(([id, at]) => (
            <DraftNote
              key={id}
              at={at}
              close={() => {
                setNotes(({ [id]: _saved, ...rest }) => rest);
              }}
            />
          ))}
        </Canvas>
      </LookContext>
    </WhiteboardContext>
  );
};
