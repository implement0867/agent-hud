import { z } from "zod";

import { boardSchema } from "~/schemas/board";

export const Turn = z.enum(["agent", "user"]);

export const viewSchema = z.strictObject({ board: boardSchema, turn: Turn });

export type TTurn = z.infer<typeof Turn>;
export type TView = z.infer<typeof viewSchema>;
