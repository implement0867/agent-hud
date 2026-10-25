import { BoardMenu } from "~/components/BoardMenu";
import { useBoard } from "~/data/useBoard";
import { AgentState } from "~/domain/events";
import type { TAgentState } from "~/domain/events";
import { agentDots } from "~/theme";

const states: Record<TAgentState, string> = {
  away: "No agent connected",
  working: "Agent connected · working on your turn",
  waiting: "Agent connected · your turn",
};

/**
 * The board the page shows, with the menu of boards; the state of the agent's socket: whether an agent's monitor is
 * open, and whether it has the user's last turn; and the turns sent that no agent has taken.
 */
export const AgentPill = () => {
  const { agent, waiting } = useBoard().model;
  const turns = `${String(waiting)} ${waiting === 1 ? "turn" : "turns"} waiting for an agent`;
  const label =
    waiting === 0
      ? states[agent]
      : agent === AgentState.enum.away
        ? `${states[agent]} · ${turns}; run /agent-hud:open in Claude Code to deliver ${waiting === 1 ? "it" : "them"}`
        : `${states[agent]} · ${turns}`;
  return (
    <div
      role="status"
      aria-label="Agent"
      className="pointer-events-auto absolute top-4 left-4 flex max-w-xl items-center gap-2 rounded-full bg-surface/90 px-3 py-1.5 text-sm shadow-sm ring-1 ring-edge-faint"
    >
      <span
        className={`size-2 shrink-0 rounded-full ${agentDots[agent]} ${agent === AgentState.enum.working ? "animate-pulse" : ""}`}
      />
      <span className="font-semibold tracking-tight text-ink">agent-hud</span>
      <BoardMenu />
      <span className="truncate text-ink-muted">{label}</span>
    </div>
  );
};
