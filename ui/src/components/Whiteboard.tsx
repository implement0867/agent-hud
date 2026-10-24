import {
  ArrowDown,
  ArrowLeft,
  ArrowRight,
  ArrowUp,
  WifiOff,
} from "lucide-react";
import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import type { PointerEvent } from "react";

import { AgentPill } from "~/components/AgentPill";
import { ArrowLayer } from "~/components/ArrowLayer";
import { Canvas } from "~/components/Canvas";
import { CardFrame, Editor } from "~/components/CardFrame";
import { Chat } from "~/components/Chat";
import { FeedbackPanel } from "~/components/FeedbackPanel";
import { HistoryDrawer } from "~/components/HistoryDrawer";
import { ShortcutSheet } from "~/components/ShortcutSheet";
import { reactionKeys, userReaction } from "~/lib/reactions";
import { Toolbar } from "~/components/Toolbar";
import {
  centreOn,
  edgeTowards,
  endOnBoard,
  fitAll,
  freeArea,
  freePlace,
  onScreen,
  overlap,
  placePanel,
  pushedBelow,
  rectOnBoard,
  toBoard,
  zoomAt,
} from "~/lib/geometry";
import type { TDirection, TRect, TSize, TView } from "~/lib/geometry";
import { SelectionKind, ToolContext, newId, useTools } from "~/lib/whiteboard";
import type { TAct, TLinking, TSelection } from "~/lib/whiteboard";
import { ActionKind, Reaction } from "~/schemas/actions";
import type { TPoint } from "~/schemas/board";
import type { TSnapshot } from "~/schemas/events";

const home: TView = { x: 64, y: 64, scale: 1 };

const samePoint = (a: TPoint | undefined, b: TPoint) =>
  a?.x === b.x && a.y === b.y;

const typing = (target: EventTarget | null) =>
  target instanceof HTMLElement &&
  (target.isContentEditable ||
    ["INPUT", "TEXTAREA", "SELECT"].includes(target.tagName));

/** The size of the feedback panel before it is measured. */
const panelGuess: TSize = { width: 288, height: 260 };

/** The size of a chip that points at a new card, for placing it at the edge. */
const chipSize: TSize = { width: 180, height: 32 };

const arrows: Record<TDirection, typeof ArrowUp> = {
  up: ArrowUp,
  down: ArrowDown,
  left: ArrowLeft,
  right: ArrowRight,
};

/** A chip at the edge of the view nearest to a card that arrived out of view; a click shows the card. */
const NewCardChip = ({
  id,
  at,
  show,
}: {
  id: string;
  at: TPoint & { direction: TDirection };
  show: (ref: string) => void;
}) => {
  const Arrow = arrows[at.direction];
  return (
    <button
      type="button"
      aria-label={`New card ${id}`}
      className="pointer-events-auto absolute flex h-8 max-w-45 animate-pop items-center gap-1.5 rounded-full bg-sky-600 pr-3 pl-2 text-sm text-white shadow-lg hover:bg-sky-700"
      style={{ left: at.x, top: at.y }}
      onClick={() => {
        show(id);
      }}
    >
      <Arrow className="size-4 shrink-0" />
      <span className="truncate">
        new: <span className="font-mono">{id}</span>
      </span>
    </button>
  );
};

/** A note that the user is writing; it goes on the board when the user saves it. */
const DraftNote = ({ at, close }: { at: TPoint; close: () => void }) => {
  const { act, select } = useTools();
  const save = async (md: string) => {
    const id = newId("note");
    if (!(await act({ kind: ActionKind.enum.put, id, md }))) return;
    await act({ kind: ActionKind.enum.move, id, ...at });
    select({ kind: SelectionKind.enum.ref, ref: id });
    close();
  };
  return (
    <div
      className="pointer-events-auto absolute w-96 animate-pop rounded-xl bg-white px-4 pt-3 pb-3 shadow-[0_1px_2px_rgba(0,0,0,0.06),0_10px_30px_-12px_rgba(0,0,0,0.18)] ring-2 ring-sky-400"
      style={{ left: at.x, top: at.y }}
    >
      <Editor
        md=""
        label="New note"
        warning={null}
        save={(md) => {
          void save(md);
        }}
        cancel={close}
      />
    </div>
  );
};

/**
 * The live board as a whiteboard: cards at their places, arrows between parts, feedback beside the selection, the chat,
 * whose turn it is, and the history of the cards when the user opens it.
 */
export const Whiteboard = ({
  snapshot,
  act,
  offline = false,
}: {
  snapshot: TSnapshot;
  act: TAct;
  /** The server is away: the board shows as it last was, greyed, with a banner. */
  offline?: boolean;
}) => {
  const { board, agent, pending, unsent, waiting } = snapshot;
  const viewport = useRef<HTMLDivElement>(null);
  const world = useRef<HTMLDivElement>(null);
  const elements = useRef(new Map<string, HTMLElement>());
  /** The elements whose rects the board tracks: the viewport, the chat, the feedback panel and each card by id. */
  const tracked = useRef(new Map<string, HTMLElement>());
  /** The rect of each tracked element: its place in the viewport, and its size as laid out, before the view scales it. */
  const [rects, setRects] = useState<Record<string, TRect>>({});
  const observer = useRef<ResizeObserver | null>(null);
  useEffect(
    () => () => {
      observer.current?.disconnect();
    },
    [],
  );
  /** A ref callback that tracks the element's rect under the key, until the element goes. */
  const track = useCallback(
    (key: string) => (element: HTMLElement | null) => {
      observer.current ??= new ResizeObserver(() => {
        const origin = viewport.current?.getBoundingClientRect();
        setRects(
          Object.fromEntries(
            [...tracked.current].map(([id, tracking]) => {
              const box = tracking.getBoundingClientRect();
              return [
                id,
                {
                  x: box.left - (origin?.left ?? 0),
                  y: box.top - (origin?.top ?? 0),
                  width: tracking.offsetWidth,
                  height: tracking.offsetHeight,
                },
              ];
            }),
          ),
        );
      });
      const was = tracked.current.get(key);
      if (was !== undefined) {
        observer.current.unobserve(was);
        tracked.current.delete(key);
      }
      if (element === null) {
        setRects(({ [key]: _gone, ...rest }) => rest);
        return;
      }
      tracked.current.set(key, element);
      observer.current.observe(element);
    },
    [],
  );
  useEffect(() => {
    track("viewport")(viewport.current);
  }, [track]);
  const trackChat = useMemo(() => track("chat"), [track]);
  const trackPanel = useMemo(() => track("panel"), [track]);
  const placing = useRef(new Map<string, TPoint>());
  const heights = useRef(new Map<string, number>());
  const [view, setView] = useState(home);
  const viewNow = useRef(view);
  useEffect(() => {
    viewNow.current = view;
  });
  const [selection, setSelection] = useState<TSelection>(null);
  /** The selected part's rect in its card, and the card's size, in board units, so that the panel follows the card. */
  const [anchor, setAnchor] = useState<{ card: TSize; part: TRect } | null>(
    null,
  );
  /** The cards that arrived since the page saw the board, until the view shows each. */
  const [fresh, setFresh] = useState<string[]>([]);
  const [linking, setLinking] = useState<TLinking | null>(null);
  const [editing, setEditing] = useState<string | null>(null);
  const [drafts, setDrafts] = useState<Record<string, TPoint>>({});
  /** A half-written comment on each part, with the card's version count when it was last typed. */
  const [comments, setComments] = useState<
    Record<string, { text: string; version: number }>
  >({});
  /** The last removed card, to restore it where it was. */
  const [undo, setUndo] = useState<{
    id: string;
    at: TPoint | undefined;
  } | null>(null);
  const undoTimer = useRef<ReturnType<typeof setTimeout> | null>(null);
  useEffect(
    () => () => {
      if (undoTimer.current !== null) clearTimeout(undoTimer.current);
    },
    [],
  );
  const [dragging, setDragging] = useState<{ id: string; at: TPoint } | null>(
    null,
  );
  const [settling, setSettling] = useState<Record<string, TPoint>>({});
  const [placed, setPlaced] = useState<Record<string, TPoint>>({});
  const [history, setHistory] = useState<{ card: string | null } | null>(null);
  const [sheet, setSheet] = useState(false);
  const [toolbarHeight, setToolbarHeight] = useState(44);

  /** A card that left the board gets a new place when it comes back. */
  const gone = useCallback((id: string) => !(id in board.cards), [board.cards]);
  const [cardsSeen, setCardsSeen] = useState(board.cards);
  if (cardsSeen !== board.cards) {
    setCardsSeen(board.cards);
    setPlaced((current) =>
      Object.keys(current).some(gone)
        ? Object.fromEntries(
            Object.entries(current).filter(([id]) => !gone(id)),
          )
        : current,
    );
    setFresh((current) => [
      ...current.filter((id) => !gone(id)),
      ...Object.keys(board.cards).filter(
        (id) => !(id in cardsSeen) && !current.includes(id),
      ),
    ]);
  }

  const [positionsSeen, setPositionsSeen] = useState(board.positions);
  if (positionsSeen !== board.positions) {
    setPositionsSeen(board.positions);
    setSettling((current) =>
      Object.fromEntries(
        Object.entries(current).filter(
          ([id, at]) => !samePoint(board.positions[id], at),
        ),
      ),
    );
  }

  const shown = useMemo(
    () =>
      Object.fromEntries(
        Object.keys(board.cards).flatMap((id) => {
          const at =
            dragging?.id === id
              ? dragging.at
              : (settling[id] ?? board.positions[id] ?? placed[id]);
          return at === undefined ? [] : [[id, at]];
        }),
      ),
    [board.cards, board.positions, dragging, settling, placed],
  );
  const shownNow = useRef(shown);
  useEffect(() => {
    shownNow.current = shown;
  });

  /** Removes the card and offers, for a while, to put it back where it was. */
  const remove = useCallback(
    (id: string) => {
      const at = shownNow.current[id];
      void act({ kind: ActionKind.enum.remove, id }).then((taken) => {
        if (!taken) return;
        setUndo({ id, at });
        if (undoTimer.current !== null) clearTimeout(undoTimer.current);
        undoTimer.current = setTimeout(() => {
          setUndo(null);
        }, 8000);
      });
    },
    [act],
  );

  const restore = ({ id, at }: { id: string; at: TPoint | undefined }) => {
    setUndo(null);
    void act({ kind: ActionKind.enum.restore, id }).then((taken) => {
      if (taken && at !== undefined)
        void act({ kind: ActionKind.enum.move, id, ...at });
    });
  };

  /**
   * A card that has no place yet gets the free place below the others, once its size is known, and the page tells the
   * server, so that every tab and reload shows it there and the agent reads it; the first tab to do so wins.
   */
  const measure = useCallback(
    (id: string, element: HTMLElement | null) => {
      track(id)(element);
      if (element === null) {
        elements.current.delete(id);
        return;
      }
      elements.current.set(id, element);
      const shown = shownNow.current;
      if (shown[id] !== undefined || placing.current.has(id)) return;
      const taken: TRect[] = [...elements.current].flatMap(([other, card]) => {
        const at = shown[other] ?? placing.current.get(other);
        return at === undefined
          ? []
          : [{ ...at, width: card.offsetWidth, height: card.offsetHeight }];
      });
      const place = freePlace(taken);
      placing.current.set(id, place);
      setPlaced((current) => ({ ...current, [id]: place }));
      void act({ kind: ActionKind.enum.place, id, ...place });
    },
    [act, track],
  );

  /**
   * A card that grew with a new version or a new width pushes the cards below it down, so that it does not cover them.
   */
  useEffect(() => {
    for (const id of [...placing.current.keys()].filter(gone)) {
      placing.current.delete(id);
      heights.current.delete(id);
    }
    const rects = Object.fromEntries(
      [...elements.current].flatMap(([id, card]) => {
        const at = board.positions[id];
        return at === undefined
          ? []
          : [
              [
                id,
                { ...at, width: card.offsetWidth, height: card.offsetHeight },
              ],
            ];
      }),
    );
    const grown = Object.entries(rects).filter(([id, rect]) => {
      const was = heights.current.get(id);
      heights.current.set(id, rect.height);
      return was !== undefined && rect.height > was;
    });
    for (const [, rect] of grown) {
      for (const [id, to] of Object.entries(pushedBelow(rect, rects))) {
        const pushed = rects[id];
        if (pushed !== undefined) rects[id] = { ...pushed, ...to };
        void act({ kind: ActionKind.enum.move, id, ...to });
      }
    }
  }, [act, board.cards, board.positions, board.widths, gone]);

  /** Selecting a part also measures where it is in its card, for its feedback panel to go beside. */
  const select = useCallback((next: TSelection) => {
    setSelection(next);
    const root = world.current;
    if (root === null || next?.kind !== SelectionKind.enum.ref) {
      setAnchor(null);
      return;
    }
    const [cardId = ""] = next.ref.split("/");
    const card = root.querySelector(
      `article[data-ref="${CSS.escape(cardId)}"]`,
    );
    const part = root.querySelector(`[data-ref="${CSS.escape(next.ref)}"]`);
    if (card === null || part === null) {
      setAnchor(null);
      return;
    }
    const { scale } = viewNow.current;
    const cardRect = rectOnBoard(card, root, scale);
    const partRect = rectOnBoard(part, root, scale);
    setAnchor({
      card: { width: cardRect.width, height: cardRect.height },
      part: {
        ...partRect,
        x: partRect.x - cardRect.x,
        y: partRect.y - cardRect.y,
      },
    });
  }, []);

  const selectedRef =
    selection?.kind === SelectionKind.enum.ref ? selection.ref : null;

  const [selectedCard = ""] = (selectedRef ?? "").split("/");

  /** A new version of the card of the selected part closes the part's feedback, which went to the history. */
  const version = board.history[selectedCard]?.length ?? 0;
  const [versionSeen, setVersionSeen] = useState({
    card: selectedCard,
    version,
  });
  if (versionSeen.card !== selectedCard || versionSeen.version !== version) {
    setVersionSeen({ card: selectedCard, version });
    if (versionSeen.card === selectedCard && selectedRef?.includes("/"))
      setSelection(null);
  }
  /** The part of the viewport that the chat leaves free, which the view fits and centres in. */
  const area = freeArea(
    rects["viewport"] ?? { width: 0, height: 0 },
    rects["chat"] ?? null,
  );
  const areaNow = useRef(area);
  useEffect(() => {
    areaNow.current = area;
  });

  const cardAt = shown[selectedCard];
  const panelAt =
    cardAt === undefined || anchor === null
      ? null
      : placePanel(
          onScreen(view, { ...cardAt, ...anchor.card }),
          onScreen(view, {
            ...anchor.part,
            x: cardAt.x + anchor.part.x,
            y: cardAt.y + anchor.part.y,
          }),
          rects["panel"] ?? panelGuess,
          area,
        );

  /** Where each fresh card is in the viewport, once the page has placed and measured it. */
  const freshRects = Object.fromEntries(
    fresh.flatMap((id) => {
      const at = shown[id];
      const rect = rects[id];
      return at === undefined || rect === undefined
        ? []
        : [[id, onScreen(view, { ...rect, ...at })]];
    }),
  );
  const shownFresh = Object.entries(freshRects)
    .filter(([, rect]) => overlap(rect, area))
    .map(([id]) => id);
  if (shownFresh.length > 0)
    setFresh((current) => current.filter((id) => !shownFresh.includes(id)));
  const chips = Object.entries(freshRects)
    .filter(([id]) => !shownFresh.includes(id))
    .map(([id, rect]) => ({ id, at: edgeTowards(rect, area, chipSize) }));

  const zoom = (factor: number) => {
    const { x, y, width, height } = areaNow.current;
    setView((current) =>
      zoomAt(current, factor, { x: x + width / 2, y: y + height / 2 }),
    );
  };

  const fit = () => {
    const root = world.current;
    if (root === null) return;
    const cards = [...root.querySelectorAll("article")].map((card) =>
      rectOnBoard(card, root, view.scale),
    );
    if (cards.length > 0) setView(fitAll(cards, areaNow.current));
  };

  const show = useCallback(
    (ref: string) => {
      const root = world.current;
      const element = root?.querySelector(`[data-ref="${CSS.escape(ref)}"]`);
      if (root == null || element == null) return;
      select({ kind: SelectionKind.enum.ref, ref });
      setView((current) =>
        centreOn(
          current,
          rectOnBoard(element, root, current.scale),
          areaNow.current,
        ),
      );
    },
    [select, setView],
  );

  const openHistory = useCallback((card: string | null) => {
    setHistory({ card });
  }, []);

  const send = () => {
    if (unsent > 0) void act({ kind: ActionKind.enum.send });
  };

  const clear = () => {
    void act({ kind: ActionKind.enum.clear });
  };

  const note = (at?: TPoint) => {
    const { x, y, width, height } = areaNow.current;
    const centre = toBoard(view, {
      x: x + width / 2 - 128,
      y: y + height / 2 - 60,
    });
    setDrafts((current) => ({ ...current, [newId("draft")]: at ?? centre }));
  };

  const beginLink = useCallback(
    (from: string, event: PointerEvent) => {
      const box = viewport.current?.getBoundingClientRect();
      const root = world.current;
      const at = viewNow.current;
      const start = root === null ? null : endOnBoard(root, from, at.scale);
      if (box === undefined || start === null) return;
      const toPoint = (pointer: { clientX: number; clientY: number }) =>
        toBoard(at, {
          x: pointer.clientX - box.left,
          y: pointer.clientY - box.top,
        });
      setLinking({ from, start, to: toPoint(event) });
      const controller = new AbortController();
      window.addEventListener(
        "pointermove",
        (move) => {
          setLinking({ from, start, to: toPoint(move) });
        },
        { signal: controller.signal },
      );
      window.addEventListener(
        "pointerup",
        (up) => {
          controller.abort();
          setLinking(null);
          const dst = document
            .elementFromPoint(up.clientX, up.clientY)
            ?.closest("[data-ref]")
            ?.getAttribute("data-ref");
          if (dst == null || dst === from) return;
          const id = newId("arrow");
          void act({
            kind: ActionKind.enum.link,
            id,
            src: from,
            dst,
            text: "",
          }).then((taken) => {
            if (taken) select({ kind: SelectionKind.enum.arrow, id });
          });
        },
        { signal: controller.signal },
      );
      window.addEventListener(
        "keydown",
        (key) => {
          if (key.key !== "Escape") return;
          controller.abort();
          setLinking(null);
        },
        { signal: controller.signal },
      );
    },
    [act, select],
  );

  const onKey = (event: KeyboardEvent) => {
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
      setSheet(false);
      select(null);
    } else if (key === "?") setSheet(!sheet);
    else if (key === "n") note();
    else if (key === "h") setHistory(history === null ? { card: null } : null);
    else if (key === "1") fit();
    else if (key === "0") setView(home);
    else if (key === "+" || key === "=") zoom(1.25);
    else if (key === "-") zoom(1 / 1.25);
    else if (key === "m") document.getElementById("message-box")?.focus();
    else if (selection?.kind === SelectionKind.enum.arrow) {
      if (key === "delete" || key === "backspace")
        void act({ kind: ActionKind.enum.unlink, id: selection.id });
    } else if (selectedRef !== null) {
      const thread = board.threads[selectedRef];
      if (reaction !== undefined)
        void act(
          userReaction(thread) === reaction
            ? { kind: ActionKind.enum.unreact, ref: selectedRef }
            : { kind: ActionKind.enum.react, ref: selectedRef, reaction },
        );
      else if (key === "c" || key === "enter") {
        event.preventDefault();
        document.getElementById("comment-box")?.focus();
      } else if (!selectedRef.includes("/") && key === "e") {
        event.preventDefault();
        setEditing(selectedRef);
      } else if (
        !selectedRef.includes("/") &&
        (key === "delete" || key === "backspace")
      )
        remove(selectedRef);
    }
  };
  const keys = useRef(onKey);
  useEffect(() => {
    keys.current = onKey;
  });
  useEffect(() => {
    const listener = (event: KeyboardEvent) => {
      keys.current(event);
    };
    window.addEventListener("keydown", listener);
    return () => {
      window.removeEventListener("keydown", listener);
    };
  }, []);

  const tools = useMemo(
    () => ({
      board,
      act,
      selection,
      select,
      show,
      linking,
      beginLink,
      openHistory,
      remove,
      readOnly: false,
    }),
    [
      board,
      act,
      selection,
      select,
      show,
      linking,
      beginLink,
      openHistory,
      remove,
    ],
  );

  return (
    <ToolContext value={tools}>
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
            <AgentPill agent={agent} waiting={waiting} />
            {offline ? (
              <div
                role="alert"
                className="pointer-events-auto absolute top-16 left-1/2 flex -translate-x-1/2 animate-pop items-center gap-2 rounded-full bg-rose-600 px-4 py-1.5 text-sm text-white shadow-lg"
              >
                <WifiOff className="size-4" />
                Board server not reachable, retrying…
              </div>
            ) : null}
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
                choose={openHistory}
                close={() => {
                  setHistory(null);
                }}
              />
            )}
            {chips.map(({ id, at }) => (
              <NewCardChip key={id} id={id} at={at} show={show} />
            ))}
            {selectedRef !== null && panelAt !== null && linking === null && (
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
                    text: comments[selectedRef]?.text ?? "",
                    changed: comments[selectedRef]?.version !== version,
                    set: (text) => {
                      setComments(({ [selectedRef]: _old, ...rest }) =>
                        text === ""
                          ? rest
                          : { ...rest, [selectedRef]: { text, version } },
                      );
                    },
                  }}
                />
              </div>
            )}
            {undo !== null && (
              <div
                role="status"
                className="pointer-events-auto absolute bottom-20 left-1/2 flex -translate-x-1/2 animate-pop items-center gap-3 rounded-full bg-stone-900 px-4 py-2 text-sm text-white shadow-lg"
              >
                Removed <span className="font-mono">{undo.id}</span>
                <button
                  type="button"
                  className="font-semibold text-sky-300 hover:underline"
                  onClick={() => {
                    restore(undo);
                  }}
                >
                  Undo
                </button>
              </div>
            )}
            <Toolbar
              scale={view.scale}
              zoom={zoom}
              reset={() => {
                setView(home);
              }}
              fit={fit}
              note={() => {
                note();
              }}
              clear={clear}
              pending={pending}
              send={send}
              history={history !== null}
              toggleHistory={() => {
                setHistory(history === null ? { card: null } : null);
              }}
              shortcuts={sheet}
              toggleShortcuts={() => {
                setSheet(!sheet);
              }}
              onHeight={setToolbarHeight}
            />
            <Chat unsent={unsent} above={toolbarHeight} measure={trackChat} />
          </>
        }
      >
        <ArrowLayer world={world} scale={view.scale} layout={shown} />
        {Object.entries(board.cards).map(([id, card]) => (
          <CardFrame
            key={id}
            id={id}
            card={card}
            at={shown[id] ?? { x: 0, y: 0 }}
            placed={shown[id] !== undefined}
            scale={view.scale}
            editing={editing === id}
            edit={(on) => {
              setEditing(on ? id : null);
            }}
            move={(at) => {
              setDragging({ id, at });
            }}
            drop={(at) => {
              setDragging(null);
              setSettling((current) => ({ ...current, [id]: at }));
              void act({ kind: ActionKind.enum.move, id, ...at }).then(
                (taken) => {
                  if (!taken)
                    setSettling((current) =>
                      Object.fromEntries(
                        Object.entries(current).filter(
                          ([other]) => other !== id,
                        ),
                      ),
                    );
                },
              );
            }}
            measure={measure}
          />
        ))}
        {Object.entries(drafts).map(([id, at]) => (
          <DraftNote
            key={id}
            at={at}
            close={() => {
              setDrafts((current) =>
                Object.fromEntries(
                  Object.entries(current).filter(([other]) => other !== id),
                ),
              );
            }}
          />
        ))}
      </Canvas>
    </ToolContext>
  );
};
