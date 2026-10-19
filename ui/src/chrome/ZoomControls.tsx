import { useCallback } from "react";

import { fitView } from "~/canvas/fitView";
import { tidy } from "~/canvas/tidy";
import { zoomAt } from "~/canvas/viewport";
import { useWorld } from "~/canvas/world";
import { Icon } from "~/chrome/icons";
import { useStore } from "~/lib/store";
import { useSend } from "~/store/socket";
import { uiStore } from "~/store/ui";

export const ZoomControls = () => {
  const world = useWorld();
  const { containerRef } = world;
  const zoom = useStore(uiStore, (s) => s.viewport.zoom);
  const step = useCallback(
    (factor: number) => {
      const box = containerRef.current;
      const center =
        box === null
          ? { x: 0, y: 0 }
          : { x: box.clientWidth / 2, y: box.clientHeight / 2 };
      uiStore.set((s) => ({
        ...s,
        viewport: zoomAt(s.viewport, center, factor),
      }));
    },
    [containerRef],
  );
  const zoomOut = useCallback(() => {
    step(1 / 1.2);
  }, [step]);
  const zoomIn = useCallback(() => {
    step(1.2);
  }, [step]);
  const reset = useCallback(() => {
    step(1 / uiStore.get().viewport.zoom);
  }, [step]);
  const fitAll = useCallback(() => {
    fitView(world);
  }, [world]);
  const send = useSend();
  const tidyUp = useCallback(() => {
    tidy(world, send);
  }, [world, send]);
  return (
    <div className="chrome zoom">
      <button type="button" onClick={zoomOut} title="Zoom out (−)">
        <Icon name="minus" size={14} />
      </button>
      <button
        type="button"
        className="zoom-level"
        onClick={reset}
        title="Reset to 100% (Ctrl+0)"
      >
        {Math.round(zoom * 100)}%
      </button>
      <button type="button" onClick={zoomIn} title="Zoom in (+)">
        <Icon name="plus" size={14} />
      </button>
      <button type="button" onClick={fitAll} title="Fit all (Shift+1)">
        <Icon name="fit" size={14} />
      </button>
      <button
        type="button"
        onClick={tidyUp}
        title="Tidy: re-flow cards so none overlap (T)"
      >
        <Icon name="tidy" size={14} />
      </button>
    </div>
  );
};
