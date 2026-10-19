import { fit, union, zoomAtCenter } from "~/canvas/viewport";
import { allCardRects } from "~/canvas/world";
import type { World } from "~/canvas/world";
import { uiStore } from "~/store/ui";

/** Zoom and pan so every placed card is visible. */
export const fitView = ({ containerRef, layerRef }: World) => {
  const box = containerRef.current;
  const root = layerRef.current;
  if (box === null || root === null) return;
  const bounds = union(allCardRects(root));
  if (bounds === null) return;
  const viewport = fit(bounds, { w: box.clientWidth, h: box.clientHeight });
  uiStore.set((s) => ({ ...s, viewport }));
};

/** Zoom around the middle of the canvas; a factor of 0 resets to 100%. */
export const zoomBy = ({ containerRef }: World, factor: number) => {
  const box = containerRef.current;
  const size = { w: box?.clientWidth ?? 0, h: box?.clientHeight ?? 0 };
  uiStore.set((s) => ({
    ...s,
    viewport: zoomAtCenter(
      s.viewport,
      size,
      factor === 0 ? 1 / s.viewport.zoom : factor,
    ),
  }));
};
