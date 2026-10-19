import { useCallback } from "react";
import type { MouseEvent } from "react";

import { Icon } from "~/chrome/icons";
import type { IconName } from "~/chrome/icons";
import { cx } from "~/lib/cx";
import { useStore } from "~/lib/store";
import type { Connection } from "~/store/board";
import { boardStore } from "~/store/board";
import type { Tool } from "~/store/ui";
import { setTool, uiStore } from "~/store/ui";

const tools: readonly {
  tool: Tool;
  icon: IconName;
  label: string;
  key: string;
}[] = [
  { tool: "select", icon: "pointer", label: "Select and move", key: "V" },
  { tool: "hand", icon: "hand", label: "Pan", key: "H" },
  { tool: "note", icon: "note", label: "Note for the agent", key: "N" },
  { tool: "link", icon: "arrow", label: "Arrow between parts", key: "L" },
];

const connectionText: Readonly<Record<Connection, string>> = {
  connecting: "Connecting…",
  open: "Connected",
  closed: "Disconnected, retrying…",
};

const isTool = (value: string | undefined): value is Tool =>
  tools.some((t) => t.tool === value);

export const TopBar = () => {
  const current = useStore(uiStore, (s) => s.tool);
  const project = useStore(boardStore, (s) => s.project);
  const connection = useStore(boardStore, (s) => s.connection);
  const choose = useCallback((e: MouseEvent<HTMLButtonElement>) => {
    const { tool } = e.currentTarget.dataset;
    if (isTool(tool)) setTool(tool);
  }, []);
  return (
    <header className="chrome topbar">
      <div className="brand">
        <span className="brand-mark">◩</span>
        <span className="brand-name">agent-hud</span>
        {project === "" ? null : (
          <span className="brand-project">{project}</span>
        )}
        <span
          className={`conn conn-${connection}`}
          title={connectionText[connection]}
        />
      </div>
      <nav className="toolbar" aria-label="Tools">
        {tools.map((t) => (
          <button
            key={t.tool}
            type="button"
            className={cx("tool", current === t.tool && "tool-on")}
            data-tool={t.tool}
            onClick={choose}
            title={`${t.label} (${t.key})`}
            aria-pressed={current === t.tool}
          >
            <Icon name={t.icon} size={18} />
            <span className="tool-key">{t.key}</span>
          </button>
        ))}
      </nav>
      <div className="topbar-end" />
    </header>
  );
};
