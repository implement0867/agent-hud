import { tidy } from "~/canvas/tidy";
import { fitView, zoomBy } from "~/canvas/view";
import { useWorld } from "~/canvas/world";
import { Icon } from "~/chrome/icons";
import { useStore } from "~/lib/store";
import { useSend } from "~/store/socket";
import { uiStore } from "~/store/ui";

export const ZoomControls = () => {
  const world = useWorld();
  const send = useSend();
  const zoom = useStore(uiStore, (s) => s.viewport.zoom);
  return (
    <div className="chrome zoom">
      <button
        type="button"
        title="Zoom out (−)"
        onClick={() => {
          zoomBy(world, 1 / 1.2);
        }}
      >
        <Icon name="minus" size={14} />
      </button>
      <button
        type="button"
        className="zoom-level"
        title="Reset to 100% (Ctrl+0)"
        onClick={() => {
          zoomBy(world, 0);
        }}
      >
        {Math.round(zoom * 100)}%
      </button>
      <button
        type="button"
        title="Zoom in (+)"
        onClick={() => {
          zoomBy(world, 1.2);
        }}
      >
        <Icon name="plus" size={14} />
      </button>
      <button
        type="button"
        title="Fit all (Shift+1)"
        onClick={() => {
          fitView(world);
        }}
      >
        <Icon name="fit" size={14} />
      </button>
      <button
        type="button"
        title="Tidy: re-flow cards so none overlap (T)"
        onClick={() => {
          tidy(world, send);
        }}
      >
        <Icon name="tidy" size={14} />
      </button>
    </div>
  );
};
