import { Check, CircleHelp, X } from "lucide-react";
import type { LucideIcon } from "lucide-react";

import type { TReaction } from "~/domain/actions";
import type { TAgentState } from "~/domain/events";

/** The icon of each reaction. */
export const reactionIcons: Record<TReaction, LucideIcon> = {
  approve: Check,
  reject: X,
  question: CircleHelp,
};

/** The colours of each reaction, wherever it shows. */
export const reactionTones: Record<TReaction, string> = {
  approve: "bg-success-soft text-success-strong",
  reject: "bg-danger-soft text-danger-strong",
  question: "bg-warning-soft text-warning-strong",
};

/** The colour of the dot that shows each state of the agent. */
export const agentDots: Record<TAgentState, string> = {
  away: "bg-ink-ghost",
  working: "bg-warning",
  waiting: "bg-success",
};
