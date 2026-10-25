import { useCallback, useRef, useState } from "react";

import { freeArea } from "~/lib/geometry";
import type { TRect, TSize } from "~/lib/geometry";

/** What the board places around and keeps clear of, as laid out, before the view scales the cards. */
export type TLayout = {
  /** The part of the viewport that the chat leaves free, which the view fits and centres in. */
  area: TRect;
  panel: TSize | null;
  /** The toolbar's height, which the chat sits above on a narrow screen. */
  toolbar: number;
  cards: Record<string, TSize>;
};

type TChrome = "viewport" | "chat" | "panel" | "toolbar" | "history";

const sizeOf = (element: HTMLElement): TSize => ({
  width: element.offsetWidth,
  height: element.offsetHeight,
});

const sameRect = (a: TRect, b: TRect) =>
  a.x === b.x && a.y === b.y && a.width === b.width && a.height === b.height;

/**
 * The layout of the viewport, the chat, the feedback panel, the toolbar and each card, kept current by one ResizeObserver, and the
 * functions that track an element for it until the element goes.
 */
export const useLayout = () => {
  const chrome = useRef(new Map<TChrome, HTMLElement>());
  const cards = useRef(new Map<string, HTMLElement>());
  const observer = useRef<ResizeObserver | null>(null);
  const [layout, setLayout] = useState<TLayout>({
    area: { x: 0, y: 0, width: 0, height: 0 },
    panel: null,
    toolbar: 44,
    cards: {},
  });

  /** Measures every tracked element; the area stays the same object while its rect does, for the callbacks that use it. */
  const measure = useCallback(() => {
    const viewport = chrome.current.get("viewport");
    const chat = chrome.current.get("chat");
    const panel = chrome.current.get("panel");
    const toolbar = chrome.current.get("toolbar");
    const history = chrome.current.get("history");
    const rectOf = (element: HTMLElement | undefined) =>
      element === undefined
        ? null
        : { x: element.offsetLeft, y: element.offsetTop, ...sizeOf(element) };
    const area = freeArea(
      viewport === undefined ? { width: 0, height: 0 } : sizeOf(viewport),
      rectOf(chat),
      rectOf(history),
    );
    const next = {
      panel: panel === undefined ? null : sizeOf(panel),
      toolbar: toolbar === undefined ? 44 : toolbar.offsetHeight,
      cards: Object.fromEntries(
        [...cards.current].map(([id, card]) => [id, sizeOf(card)]),
      ),
    };
    setLayout((current) => ({
      ...next,
      area: sameRect(current.area, area) ? current.area : area,
    }));
  }, []);

  const observe = useCallback(
    <TKey>(
      elements: Map<TKey, HTMLElement>,
      key: TKey,
      element: HTMLElement,
    ) => {
      observer.current ??= new ResizeObserver(measure);
      const tracking = observer.current;
      elements.set(key, element);
      tracking.observe(element);
      return () => {
        tracking.unobserve(element);
        elements.delete(key);
        measure();
      };
    },
    [measure],
  );

  /** Tracks the viewport, the chat, the panel, the toolbar or the history; returns the cleanup. */
  const trackChrome = useCallback(
    (key: TChrome, element: HTMLElement) =>
      observe(chrome.current, key, element),
    [observe],
  );

  /** Tracks the card; returns the cleanup. */
  const trackCard = useCallback(
    (id: string, element: HTMLElement) => observe(cards.current, id, element),
    [observe],
  );

  /** The size of each card on the page as laid out now, for a place that must not wait for the observer. */
  const cardSizes = useCallback(
    () => new Map([...cards.current].map(([id, card]) => [id, sizeOf(card)])),
    [],
  );

  return { layout, trackChrome, trackCard, cardSizes };
};
