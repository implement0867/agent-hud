import type { TAgentState } from "~/schemas/events";

const looks: Record<TAgentState, { dot: string; label: string }> = {
  away: { dot: "bg-stone-300", label: "No agent connected" },
  working: {
    dot: "animate-pulse bg-amber-500",
    label: "Agent connected · working on your turn",
  },
  waiting: { dot: "bg-emerald-500", label: "Agent connected · your turn" },
};

/** The state of the agent's socket: whether an agent's monitor is open, and whether it has the user's last turn; and the turns sent that no agent has taken. */
export const AgentPill = ({
  agent,
  waiting,
}: {
  agent: TAgentState;
  waiting: number;
}) => {
  const { dot, label: state } = looks[agent];
  const turns = `${String(waiting)} ${waiting === 1 ? "turn" : "turns"} waiting for an agent`;
  const label =
    waiting === 0
      ? state
      : agent === "away"
        ? `${state} · ${turns}; run /agent-hud:board in Claude Code to deliver ${waiting === 1 ? "it" : "them"}`
        : `${state} · ${turns}`;
  return (
    <div
      role="status"
      aria-label="Agent"
      className="absolute top-4 left-4 flex max-w-md items-center gap-2 rounded-full bg-white/90 px-3 py-1.5 text-sm shadow-sm ring-1 ring-stone-900/5"
    >
      <span className={`size-2 shrink-0 rounded-full ${dot}`} />
      <span className="font-semibold tracking-tight text-stone-800">
        agent-hud
      </span>
      <span className="truncate text-stone-500">{label}</span>
    </div>
  );
};
