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
  useMemo,
  useRef,
  useState,
} from "react";

import { AgentPill } from "~/components/AgentPill";
import { ArrowLayer } from "~/components/ArrowLayer";
import { Canvas } from "~/components/Canvas";
import { CardFrame } from "~/components/CardFrame";
import { Chat } from "~/components/Chat";
import { FeedbackPanel } from "~/components/FeedbackPanel";
import { HistoryDrawer } from "~/components/HistoryDrawer";
import { MarkdownEditor } from "~/components/MarkdownEditor";
import { ShortcutSheet } from "~/components/ShortcutSheet";
import { TextButton } from "~/components/TextButton";
import { Toolbar } from "~/components/Toolbar";
import { cardIn } from "~/data/boardModel";
import type { TCardView } from "~/data/boardModel";
import { useBoard, useStore } from "~/data/context";
import { ActionKind, Reaction } from "~/domain/actions";
import { newId, refsWithFeedback, threadOf, versionsOf } from "~/domain/board";
import { cardTitle, nameOf } from "~/domain/parts";
import type { TArrow, TPoint } from "~/domain/board";
import { reactionKeys, toggleReaction } from "~/domain/reactions";
import { cardOf, isCardRef } from "~/domain/ref";
import { useLayout } from "~/hooks/useLayout";
import { useLinking } from "~/hooks/useLinking";
import { useSelection } from "~/hooks/useSelection";
import { RemovedKind, useUndo } from "~/hooks/useUndo";
import type { TRemoved } from "~/hooks/useUndo";
import { SelectionKind, WhiteboardContext } from "~/hooks/useWhiteboard";
import type { TEditing, TSelection } from "~/hooks/useWhiteboard";
import { elementOf, rectOnBoard, textOf } from "~/lib/dom";
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
import type { TDirection, TSize, TView } from "~/lib/geometry";
import { invariant } from "~/lib/invariant";

const home: TView = { x: 64, y: 64, scale: 1 };

/** The factor of one step of zoom, from the keys and the toolbar. */
const zoomStep = 1.25;

/** The size of the feedback panel before it is measured: its w-72 and a few comments. */
const panelGuess: TSize = { width: 288, height: 260 };

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

type TNewCardChipProps = {
  id: string;
  at: TPoint & { direction: TDirection };
  show: (ref: string) => void;
};

/** A chip at the edge of the view nearest to a card that arrived out of view; a click shows the card. */
const NewCardChip = ({ id, at, show }: TNewCardChipProps) => {
  const { model } = useBoard();
  const Arrow = chipArrows[at.direction];
  return (
    <button
      type="button"
      aria-label={`New card ${id}`}
      className="pointer-events-auto absolute flex h-8 max-w-45 animate-pop items-center gap-1.5 rounded-full bg-accent pr-3 pl-2 text-sm text-white shadow-lg hover:bg-accent-strong"
      style={{ left: at.x, top: at.y }}
      onClick={() => {
        show(id);
      }}
    >
      <Arrow className="size-4 shrink-0" />
      <span className="truncate">new: {nameOf(model.board, id)}</span>
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
      className="card pointer-events-auto absolute w-96 animate-pop px-4 py-3 ring-2 ring-accent-ring"
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
  <div role="alert" className="toast top-16 bg-danger">
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
    <div role="status" className="toast bottom-20 gap-3 bg-ink">
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
  return (
    <div
      role="status"
      aria-label="Arrow removed by the agent"
      className="toast bottom-32 gap-3 bg-ink"
    >
      The agent removed your arrow from “{nameOf(model.board, arrow.src)}” to “
      {nameOf(model.board, arrow.dst)}”
      {arrow.text === "" ? "" : `, “${arrow.text}”`}
      <TextButton
        variant="onDark"
        onClick={() => {
          const { src, dst, text } = arrow;
          void store
            .act({ kind: ActionKind.enum.link, id, src, dst, text })
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

/** A half-written comment on a part, with its card's number of earlier versions when the user last typed. */
type TCommentDraft = { text: string; versions: number };

/**
 * The live board as a whiteboard: cards at their places, arrows between parts, feedback beside the selection, the chat,
 * whose turn it is, and the history of the cards when the user opens it.
 */
export const Whiteboard = () => {
  const { model, offline } = useBoard();
  const store = useStore();
  const viewport = useRef<HTMLDivElement>(null);
  const world = useRef<HTMLDivElement>(null);
  const [view, setView] = useState(home);
  const { layout, trackChrome, trackCard, cardSizes } = useLayout();
  const {
    selection,
    anchor,
    feedbackOpen,
    setFeedbackOpen,
    select: choose,
    deselectArrow,
  } = useSelection(world);
  /** Selects; a selection on a card is a look at it, which clears the marks of the agent's last version. */
  const select = useCallback(
    (selection: TSelection, feedback?: boolean) => {
      if (selection?.kind === SelectionKind.enum.ref)
        store.sawChanges(cardOf(selection.ref));
      choose(selection, feedback);
    },
    [choose, store],
  );
  const { linking, beginLink } = useLinking(world, store.act, select);
  const linkingFrom = linking?.from ?? null;
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

  const show = useCallback(
    (ref: string) => {
      const root = world.current;
      invariant(root !== null, "the canvas renders the world");
      const element = elementOf(root, ref);
      if (element === null) return;
      select({ kind: SelectionKind.enum.ref, ref });
      const rect = rectOnBoard(element, root);
      setView((current) => centreOn(current, rect, area));
    },
    [select, area],
  );

  const edit = useCallback(
    (card: string | null) => {
      if (card === null) {
        setEditing(null);
        return;
      }
      if (editing?.card === card) return;
      const root = world.current;
      invariant(root !== null, "the canvas renders the world");
      store.sawChanges(card);
      const { board } = store.read();
      setEditing({
        card,
        versions: versionsOf(board, card),
        marked: refsWithFeedback(board, card).map((ref) =>
          isCardRef(ref) ? "" : textOf(root, ref),
        ),
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
      select,
      show,
      linkingFrom,
      beginLink,
      editing,
      edit,
      openHistory,
      remove,
      unlink,
    }),
    [
      selection,
      select,
      show,
      linkingFrom,
      beginLink,
      editing,
      edit,
      openHistory,
      remove,
      unlink,
    ],
  );

  /** The card's rect as the viewport shows it, or null until it is placed and measured. */
  const onView = ({ id, at }: TCardView) => {
    const size = layout.cards[id];
    return at === null || size === undefined
      ? null
      : onScreen(view, { ...at, ...size });
  };

  const selectedRef =
    selection?.kind === SelectionKind.enum.ref ? selection.ref : null;
  const selectedCard =
    selectedRef === null ? null : cardIn(model, cardOf(selectedRef));
  const versions = selectedCard === null ? 0 : selectedCard.versions;
  const cardAt = selectedCard?.at ?? null;
  /** Where the feedback panel goes: beside the selected part, clear of the cards when it can be, the size it was last. */
  const panelAt =
    cardAt === null || anchor === null
      ? null
      : placePanel(
          onScreen(view, { ...cardAt, ...anchor.card }),
          onScreen(view, {
            ...anchor.part,
            x: cardAt.x + anchor.part.x,
            y: cardAt.y + anchor.part.y,
          }),
          layout.panel ?? panelGuess,
          area,
          model.cards.flatMap((card) => onView(card) ?? []),
        );

  /** The fresh cards that the view shows now stop being fresh; the others get a chip at the edge that points at them. */
  const fresh = model.cards.flatMap((card) => {
    const rect = model.fresh.includes(card.id) ? onView(card) : null;
    return rect === null ? [] : [{ id: card.id, rect }];
  });
  const seen = fresh
    .filter(({ rect }) => overlap(rect, area))
    .map(({ id }) => id);
  useEffect(() => {
    if (seen.length > 0) store.saw(seen);
  });
  const chips = fresh
    .filter(({ id }) => !seen.includes(id))
    .map(({ id, rect }) => ({
      id,
      at: edgeTowards(rect, area, chipSize),
    }));

  /** Zooms in by the steps, or out by negative steps, about the centre of the free area. */
  const zoom = (steps: number) => {
    setView((current) =>
      zoomAt(current, zoomStep ** steps, {
        x: area.x + area.width / 2,
        y: area.y + area.height / 2,
      }),
    );
  };

  const fit = () => {
    const rects = model.cards.flatMap((card) => {
      const size = layout.cards[card.id];
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

  const onKey = useEffectEvent((event: KeyboardEvent) => {
    if (typing(event.target)) return;
    if ((event.metaKey || event.ctrlKey) && event.key === "Enter") {
      event.preventDefault();
      send();
      return;
    }
    if (event.metaKey || event.ctrlKey || event.altKey) return;
    const key = event.key.toLowerCase();
    const reaction = Reaction.options.find(
      (option) => reactionKeys[option] === key,
    );
    if (key === "escape") {
      if (sheet) setSheet(false);
      else if (feedbackOpen && selectedRef !== null) setFeedbackOpen(false);
      else select(null);
    } else if (key === "?") setSheet(!sheet);
    else if (key === "n") note();
    else if (key === "h") toggleHistory();
    else if (key === "1") fit();
    else if (key === "0") setView(home);
    else if (key === "+" || key === "=") zoom(1);
    else if (key === "-") zoom(-1);
    else if (key === "m") document.getElementById("message-box")?.focus();
    else if (selection?.kind === SelectionKind.enum.arrow) {
      if (key === "delete" || key === "backspace") unlink(selection.id);
    } else if (selectedRef !== null) {
      const thread = threadOf(model.board, selectedRef);
      if (reaction !== undefined)
        void store.act(toggleReaction(thread, selectedRef, reaction));
      else if (key === "c" || key === "enter") {
        event.preventDefault();
        setFeedbackOpen(true);
        requestAnimationFrame(() => {
          document.getElementById("comment-box")?.focus();
        });
      } else if (isCardRef(selectedRef) && key === "e") {
        event.preventDefault();
        edit(selectedRef);
      } else if (
        isCardRef(selectedRef) &&
        (key === "delete" || key === "backspace")
      )
        remove(selectedRef);
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

  const comment = selectedRef === null ? undefined : comments[selectedRef];

  return (
    <WhiteboardContext value={whiteboard}>
      <Canvas
        view={view}
        setView={setView}
        viewport={viewport}
        world={world}
        clear={() => {
          select(null);
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
            {selectedRef !== null &&
            panelAt !== null &&
            linking === null &&
            feedbackOpen ? (
              <div
                className="absolute"
                style={{ left: panelAt.x, top: panelAt.y }}
              >
                <FeedbackPanel
                  key={selectedRef}
                  target={selectedRef}
                  maxHeight={Math.max(160, area.height - 16)}
                  measure={trackPanel}
                  draft={{
                    text: comment?.text ?? "",
                    changed:
                      comment !== undefined && comment.versions !== versions,
                    set: (text) => {
                      setComments(({ [selectedRef]: _old, ...rest }) =>
                        text === ""
                          ? rest
                          : { ...rest, [selectedRef]: { text, versions } },
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
              measure={trackToolbar}
            />
            <Chat send={send} above={layout.toolbar} measure={trackChat} />
          </>
        }
      >
        <ArrowLayer world={world} linking={linking} />
        {/* One stacking context for the cards, so that their layers stay under the arrow labels and the panel. */}
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
    </WhiteboardContext>
  );
};
