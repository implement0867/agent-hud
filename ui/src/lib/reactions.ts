import { Check, CircleHelp, X } from "lucide-react";
import type { LucideIcon } from "lucide-react";

import type { TReaction } from "~/schemas/actions";

export const reactionIcons: Record<TReaction, LucideIcon> = {
  approve: Check,
  reject: X,
  question: CircleHelp,
};

export const reactionKeys: Record<TReaction, string> = {
  approve: "a",
  reject: "r",
  question: "q",
};

export const reactionTones: Record<TReaction, string> = {
  approve: "bg-emerald-100 text-emerald-700",
  reject: "bg-rose-100 text-rose-700",
  question: "bg-amber-100 text-amber-700",
};
