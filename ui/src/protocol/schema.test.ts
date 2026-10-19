import { readFileSync } from "node:fs";
import { describe, expect, it } from "vitest";

import { ClientMsg, ServerMsg } from "./schema";

const fixture = (name: string): unknown[] => {
  const url = new URL(`../../../protocol/fixtures/${name}`, import.meta.url);
  const parsed: unknown = JSON.parse(readFileSync(url, "utf8"));
  if (!Array.isArray(parsed)) throw new Error(`${name} must hold an array`);
  return parsed;
};

describe("protocol fixtures shared with the Python server", () => {
  it.each(fixture("server.json").map((msg, n) => [n, msg] as const))(
    "server message %i parses strictly",
    (_n, msg) => {
      expect(ServerMsg.safeParse(msg).error).toBeUndefined();
    },
  );

  it.each(fixture("client.json").map((msg, n) => [n, msg] as const))(
    "client message %i parses strictly",
    (_n, msg) => {
      expect(ClientMsg.safeParse(msg).error).toBeUndefined();
    },
  );

  it("rejects fields the server does not send", () => {
    const bad = { t: "gone", id: "plan", extra: 1 };
    expect(ServerMsg.safeParse(bad).success).toBe(false);
  });
});
