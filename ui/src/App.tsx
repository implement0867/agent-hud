import { useCallback, useEffect, useMemo, useRef } from "react";

import { Canvas } from "~/canvas/Canvas";
import { LinkDraft } from "~/canvas/Drafts";
import { fitView, zoomBy } from "~/canvas/view";
import { tidy } from "~/canvas/tidy";
import { WorldContext } from "~/canvas/world";
import type { World } from "~/canvas/world";
import { EmptyState, Toast, ToolHint } from "~/chrome/Overlays";
import { SendPanel } from "~/chrome/SendPanel";
import { TopBar } from "~/chrome/Toolbar";
import { ZoomControls } from "~/chrome/ZoomControls";
import { isTyping } from "~/lib/dom";
import { boardStore } from "~/store/board";
import { connect, socketUrl } from "~/store/connection";
import type { Socket } from "~/store/connection";
import { SocketContext } from "~/store/socket";
import type { Send } from "~/store/socket";
import { select, setTool, uiStore } from "~/store/ui";

const useShortcuts = (world: World, send: Send) => {
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (isTyping(e.target)) return;
      const { selected, linkFrom, linkDraft, noteDraft } = uiStore.get();
      if ((e.ctrlKey || e.metaKey) && e.key === "0") {
        e.preventDefault();
        zoomBy(world, 0);
        return;
      }
      if (e.ctrlKey || e.metaKey || e.altKey) return;
      switch (e.key) {
        case "v":
        case "V":
          setTool("select");
          break;
        case "h":
        case "H":
          setTool("hand");
          break;
        case "n":
        case "N":
          setTool("note");
          break;
        case "l":
        case "L":
          setTool("link");
          break;
        case "!":
          fitView(world);
          break;
        case "t":
        case "T":
          tidy(world, send);
          break;
        case "+":
        case "=":
          zoomBy(world, 1.2);
          break;
        case "-":
          zoomBy(world, 1 / 1.2);
          break;
        case "Escape":
          if (linkFrom !== null || linkDraft !== null || noteDraft !== null)
            setTool(uiStore.get().tool);
          else {
            setTool("select");
            select(null);
          }
          break;
        case "Delete":
        case "Backspace": {
          const el =
            selected === null ? undefined : boardStore.get().elements[selected];
          if (el?.author === "user") {
            send({ t: "delete", id: el.id });
            select(null);
          }
          break;
        }
        default:
          break;
      }
    };
    window.addEventListener("keydown", onKey);
    return () => {
      window.removeEventListener("keydown", onKey);
    };
  }, [world, send]);
};

export const App = () => {
  const containerRef = useRef<HTMLDivElement>(null);
  const layerRef = useRef<HTMLDivElement>(null);
  const world = useMemo<World>(() => ({ containerRef, layerRef }), []);
  const socketRef = useRef<Socket | null>(null);
  const send = useCallback<Send>((msg) => {
    socketRef.current?.send(msg);
  }, []);

  useEffect(() => {
    const socket = connect(socketUrl());
    socketRef.current = socket;
    return () => {
      socket.close();
      socketRef.current = null;
    };
  }, []);
  useShortcuts(world, send);

  return (
    <SocketContext value={send}>
      <WorldContext value={world}>
        <Canvas />
        <EmptyState />
        <TopBar />
        <ToolHint />
        <ZoomControls />
        <SendPanel />
        <LinkDraft />
        <Toast />
      </WorldContext>
    </SocketContext>
  );
};
