import { fit, union } from "~/canvas/viewport";
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
