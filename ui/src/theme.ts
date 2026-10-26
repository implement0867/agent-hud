import type { TAgentState } from "~/domain/events";

/** The colour of the dot that shows each state of the agent. */
export const agentDots: Record<TAgentState, string> = {
  away: "bg-ink-ghost",
  working: "bg-warning",
  waiting: "bg-success",
};
