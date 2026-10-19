import { nextPlacement } from "~/canvas/placement";
import type { Rect } from "~/canvas/viewport";
import { cardNode } from "~/canvas/world";
import type { World } from "~/canvas/world";
import { boardStore } from "~/store/board";
import type { Send } from "~/store/socket";

/** Re-flow every card in creation order with its current size, so grown cards stop overlapping. */
export const tidy = ({ layerRef }: World, send: Send) => {
  const root = layerRef.current;
  if (root === null) return;
  const { order, elements } = boardStore.get();
  const rects: Rect[] = [];
  for (const id of order) {
    const node = elements[id]?.kind === "link" ? null : cardNode(root, id);
    if (node === null) continue;
    const size = { w: node.offsetWidth, h: node.offsetHeight };
    const at = nextPlacement(rects, size);
    rects.push({ ...at, ...size });
    if (at.x !== node.offsetLeft || at.y !== node.offsetTop)
      send({ t: "move", id, ...at });
  }
};
