import { AgentState } from "~/schemas/events";
import type { TAgentState } from "~/schemas/events";

const looks: Record<TAgentState, { dot: string; label: string }> = {
  away: { dot: "bg-stone-300", label: "No agent is listening" },
  working: { dot: "animate-pulse bg-amber-500", label: "The agent is working" },
  waiting: { dot: "bg-emerald-500", label: "Your turn" },
};

/** Whose turn it is: the agent's state, and, while the agent works, the status it set. */
export const AgentPill = ({
  agent,
  status,
}: {
  agent: TAgentState;
  status: string;
}) => {
  const { dot, label } = looks[agent];
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
      <span className="truncate text-stone-500">
        {status !== "" && agent === AgentState.enum.working
          ? `${label} · ${status}`
          : label}
      </span>
    </div>
  );
};
