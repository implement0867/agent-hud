import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import type { PointerEvent } from "react";

import { ArrowLayer } from "~/components/ArrowLayer";
import { Canvas } from "~/components/Canvas";
import { CardFrame, Editor } from "~/components/CardFrame";
import { Chat } from "~/components/Chat";
import { FeedbackPanel } from "~/components/FeedbackPanel";
import { reactionKeys } from "~/lib/reactions";
import { Toolbar } from "~/components/Toolbar";
import {
  centreOn,
  endOnBoard,
  fitAll,
  freePlace,
  rectOnBoard,
  toBoard,
  zoomAt,
} from "~/lib/geometry";
import type { TRect, TView } from "~/lib/geometry";
import { SelectionKind, ToolContext, newId, useTools } from "~/lib/whiteboard";
import type { TAct, TLinking, TSelection } from "~/lib/whiteboard";
import { ActionKind, Reaction } from "~/schemas/actions";
import type { TBoard, TPoint } from "~/schemas/board";

const home: TView = { x: 64, y: 64, scale: 1 };

const samePoint = (a: TPoint | undefined, b: TPoint) =>
  a?.x === b.x && a.y === b.y;

const typing = (target: EventTarget | null) =>
  target instanceof HTMLElement &&
  (target.isContentEditable ||
    ["INPUT", "TEXTAREA", "SELECT"].includes(target.tagName));

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
      className="pointer-events-auto absolute w-64 -rotate-[0.6deg] animate-pop rounded-xl bg-amber-100 px-4 pt-3 pb-3 shadow-[0_8px_20px_-8px_rgba(120,80,0,0.35)] ring-2 ring-amber-300"
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

/** The live board as a whiteboard: cards at their places, arrows between parts, feedback beside the selection, and the chat. */
export const Whiteboard = ({ board, act }: { board: TBoard; act: TAct }) => {
  const viewport = useRef<HTMLDivElement>(null);
  const world = useRef<HTMLDivElement>(null);
  const elements = useRef(new Map<string, HTMLElement>());
  const placing = useRef(new Map<string, TPoint>());
  const [view, setView] = useState(home);
  const viewNow = useRef(view);
  useEffect(() => {
    viewNow.current = view;
  });
  const [selection, setSelection] = useState<TSelection>(null);
  const [panelOffset, setPanelOffset] = useState<TPoint | null>(null);
  const [linking, setLinking] = useState<TLinking | null>(null);
  const [editing, setEditing] = useState<string | null>(null);
  const [drafts, setDrafts] = useState<Record<string, TPoint>>({});
  const [dragging, setDragging] = useState<{ id: string; at: TPoint } | null>(
    null,
  );
  const [settling, setSettling] = useState<Record<string, TPoint>>({});
  const [placed, setPlaced] = useState<Record<string, TPoint>>({});

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

  /** A card that has no place yet gets the free place below the others, once its size is known. */
  const measure = (id: string) => (element: HTMLElement | null) => {
    if (element === null) {
      elements.current.delete(id);
      return;
    }
    elements.current.set(id, element);
    if (shown[id] !== undefined || placing.current.has(id)) return;
    const rects: TRect[] = [...elements.current].flatMap(([other, card]) => {
      const at = shown[other] ?? placing.current.get(other);
      return at === undefined
        ? []
        : [{ ...at, width: card.offsetWidth, height: card.offsetHeight }];
    });
    const place = freePlace(rects, element.offsetWidth);
    placing.current.set(id, place);
    setPlaced((current) => ({ ...current, [id]: place }));
  };

  /** Selecting a part also measures where its feedback panel goes, beside its card. */
  const select = useCallback((next: TSelection) => {
    setSelection(next);
    const root = world.current;
    const end =
      root === null || next?.kind !== SelectionKind.enum.ref
        ? null
        : endOnBoard(root, next.ref, viewNow.current.scale);
    setPanelOffset(
      end === null
        ? null
        : { x: end.card.width + 20, y: end.y - end.card.y - 22 },
    );
  }, []);

  const selectedRef =
    selection?.kind === SelectionKind.enum.ref ? selection.ref : null;

  const [selectedCard = ""] = (selectedRef ?? "").split("/");
  const cardAt = shown[selectedCard];
  const panelAt =
    cardAt === undefined || panelOffset === null
      ? null
      : { x: cardAt.x + panelOffset.x, y: cardAt.y + panelOffset.y };

  const size = () => {
    const box = viewport.current?.getBoundingClientRect();
    return { width: box?.width ?? 0, height: box?.height ?? 0 };
  };

  const zoom = (factor: number) => {
    const { width, height } = size();
    setView((current) =>
      zoomAt(current, factor, { x: width / 2, y: height / 2 }),
    );
  };

  const fit = () => {
    const root = world.current;
    if (root === null) return;
    const rects = [...root.querySelectorAll("article")].map((card) =>
      rectOnBoard(card, root, view.scale),
    );
    if (rects.length > 0) setView(fitAll(rects, size()));
  };

  const show = (ref: string) => {
    const root = world.current;
    const element = root?.querySelector(`[data-ref="${CSS.escape(ref)}"]`);
    if (root == null || element == null) return;
    select({ kind: SelectionKind.enum.ref, ref });
    setView((current) =>
      centreOn(current, rectOnBoard(element, root, current.scale), size()),
    );
  };

  const note = (at?: TPoint) => {
    const { width, height } = size();
    const centre = toBoard(view, { x: width / 2 - 128, y: height / 2 - 60 });
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
    if (typing(event.target) || event.metaKey || event.ctrlKey || event.altKey)
      return;
    const key = event.key.toLowerCase();
    const reaction = Reaction.options.find(
      (option) => reactionKeys[option] === key,
    );
    if (key === "escape") select(null);
    else if (key === "n") note();
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
          thread?.reaction === reaction
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
        void act({ kind: ActionKind.enum.remove, id: selectedRef });
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
    () => ({ board, act, selection, select, linking, beginLink }),
    [board, act, selection, select, linking, beginLink],
  );

  const empty =
    Object.keys(board.cards).length === 0 && Object.keys(drafts).length === 0;
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
        overlay={
          <>
            <div className="absolute top-4 left-4 flex items-center gap-2 rounded-full bg-white/90 px-3 py-1.5 text-sm font-semibold tracking-tight text-stone-800 shadow-sm ring-1 ring-stone-900/5">
              <span className="size-2 rounded-full bg-emerald-500 shadow-[0_0_0_3px_rgba(16,185,129,0.2)]" />
              agent-hud
            </div>
            {linking !== null && (
              <div className="absolute top-4 left-1/2 -translate-x-1/2 rounded-full bg-violet-600 px-4 py-1.5 text-sm text-white shadow-lg">
                Release on a part or a card · Esc cancels
              </div>
            )}
            {empty ? (
              <div className="absolute inset-0 grid place-items-center">
                <p className="max-w-xs text-center text-stone-400">
                  The agent&apos;s cards show here.
                  <br />
                  Double-click anywhere to write a note.
                </p>
              </div>
            ) : null}
            <p className="absolute bottom-6 left-4 hidden text-xs text-stone-400 lg:block">
              Double-click: note · drag a dot: arrow · Space+drag: pan ·
              ⌘+scroll: zoom
            </p>
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
              show={show}
            />
            <Chat />
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
            measure={measure(id)}
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
        {selectedRef !== null && panelAt !== null && linking === null && (
          <div className="absolute" style={{ left: panelAt.x, top: panelAt.y }}>
            <FeedbackPanel key={selectedRef} target={selectedRef} />
          </div>
        )}
      </Canvas>
    </ToolContext>
  );
};
