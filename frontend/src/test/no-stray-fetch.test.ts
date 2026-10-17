import { readdirSync, readFileSync, statSync } from "node:fs";
import { join, relative, sep } from "node:path";
import { describe, expect, it } from "vitest";

const SRC = join(__dirname, "..");
const ALLOWED = ["api", "client.ts"].join(sep);

function files(dir: string): string[] {
  return readdirSync(dir).flatMap((name) => {
    const p = join(dir, name);
    return statSync(p).isDirectory() ? files(p) : [p];
  });
}

describe("one place for HTTP", () => {
  it("no file under src/ except api/client.ts calls fetch(", () => {
    const offenders = files(SRC)
      .filter((p) => /\.(ts|tsx)$/.test(p))
      .filter((p) => relative(SRC, p) !== ALLOWED)
      .filter((p) => !p.endsWith("no-stray-fetch.test.ts"))
      .filter((p) => readFileSync(p, "utf8").includes("fetch("));
    expect(offenders.map((p) => relative(SRC, p))).toEqual([]);
  });
});
