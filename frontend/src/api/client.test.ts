import { afterEach, describe, expect, it, vi } from "vitest";
import * as client from "./client";

function mockFetch(status: number, body: unknown = {}) {
  const fn = vi.fn().mockResolvedValue({ ok: status >= 200 && status < 300, status, json: async () => body });
  vi.stubGlobal("fetch", fn);
  return fn;
}

const urlOf = (fn: ReturnType<typeof vi.fn>) => fn.mock.calls[0]?.[0] as string;

afterEach(() => vi.unstubAllGlobals());

describe("api client URLs", () => {
  it("builds the path for each endpoint", async () => {
    const cases: Array<[() => Promise<unknown>, string]> = [
      [() => client.getHealth(), "/api/health"],
      [() => client.listFindings(), "/api/findings"],
      [() => client.getFinding("june-july-2025"), "/api/findings/june-july-2025"],
      [() => client.getAcledEvidence("a"), "/api/findings/a/evidence/acled"],
      [() => client.getOoniEvidence("a"), "/api/findings/a/evidence/ooni"],
      [() => client.getGoogleTransparencyEvidence("a"), "/api/findings/a/evidence/google-transparency"],
      [() => client.getMethodology(), "/api/methodology"],
      [() => client.getTimeline(), "/api/timeline"],
    ];
    for (const [call, path] of cases) {
      const fn = mockFetch(200);
      await call();
      expect(urlOf(fn)).toBe(path);
    }
  });

  it("adds timeline query parameters and skips undefined ones", async () => {
    const fn = mockFetch(200);
    await client.getTimeline({ country: "KE", from: "2024-06-01", state: undefined });
    expect(urlOf(fn)).toBe("/api/timeline?country=KE&from=2024-06-01");
  });

  it("encodes the slug", async () => {
    const fn = mockFetch(200);
    await client.getFinding("a/b c");
    expect(urlOf(fn)).toBe("/api/findings/a%2Fb%20c");
  });
});

describe("api client errors", () => {
  it("throws an ApiError carrying the status, and a 404 is distinguishable", async () => {
    mockFetch(404);
    const err = await client.getFinding("missing").catch((e: unknown) => e);
    expect(err).toBeInstanceOf(client.ApiError);
    const apiErr = err as client.ApiError;
    expect(apiErr.status).toBe(404);
    expect(apiErr.isNotFound).toBe(true);
  });

  it("does not flag other statuses as not found", async () => {
    mockFetch(503);
    const err = (await client.getHealth().catch((e: unknown) => e)) as client.ApiError;
    expect(err.status).toBe(503);
    expect(err.isNotFound).toBe(false);
  });
});
