import { flushSync } from "react-dom";
import { createRoot } from "react-dom/client";

import { StagedCard } from "~/components/StagedCard";
import type { TMeasure, TSurface } from "~/data/boardModel";
import { homeView, toBoardRect } from "~/lib/geometry";
import { invariant } from "~/lib/invariant";

/**
 * The measure of a card on the stage: an element at the top of the document that takes no space, shows nothing and
 * takes no pointer, where the card renders with the page's styles for the one moment its size is read, then goes.
 * The stage joins the document on the first measure.
 */
export const createMeasure = (): TMeasure => {
  let stage: HTMLElement | null = null;
  const findStage = () => {
    if (stage !== null) return stage;
    stage = document.createElement("div");
    stage.dataset["stage"] = "";
    stage.setAttribute("aria-hidden", "true");
    Object.assign(stage.style, {
      position: "fixed",
      top: "0",
      left: "0",
      width: "0",
      height: "0",
      overflow: "hidden",
      visibility: "hidden",
      pointerEvents: "none",
      contain: "layout style",
    });
    document.body.append(stage);
    return stage;
  };
  return (card) => {
    const mount = document.createElement("div");
    findStage().append(mount);
    const root = createRoot(mount);
    try {
      flushSync(() => {
        root.render(<StagedCard {...card} />);
      });
      const frame = mount.firstElementChild;
      invariant(frame instanceof HTMLElement, "the stage renders the frame");
      return { width: frame.offsetWidth, height: frame.offsetHeight };
    } finally {
      root.unmount();
      mount.remove();
    }
  };
};

/** The page before the whiteboard shows: the window at the home view, with no card laid out. */
export const pageSurface: TSurface = {
  viewport: () =>
    toBoardRect(homeView, {
      x: 0,
      y: 0,
      width: window.innerWidth,
      height: window.innerHeight,
    }),
  sizes: () => new Map(),
};
