import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { render, screen, within } from "@testing-library/react";
import { createMemoryRouter, RouterProvider } from "react-router-dom";
import * as client from "../api/client";
import { routes } from "../routes";

beforeEach(() => {
  vi.spyOn(client, "getTimeline").mockResolvedValue({ weeks: [] } as unknown as client.TimelineResponse);
  vi.spyOn(client, "listFindings").mockResolvedValue({ findings: [] } as unknown as client.FindingList);
});
afterEach(() => vi.restoreAllMocks());

function renderAt(path: string) {
  return render(<RouterProvider router={createMemoryRouter(routes, { initialEntries: [path] })} />);
}

const health = { snapshot_version: "2026-10-10.1" } as client.Health;

describe("Shell", () => {
  it("shows the snapshot version from the client", async () => {
    vi.spyOn(client, "getHealth").mockResolvedValue(health);
    renderAt("/");
    expect(screen.getByText(/Snapshot/)).toHaveTextContent("Snapshot …");
    expect(await screen.findByText("2026-10-10.1")).toBeInTheDocument();
  });

  it("shows 'Snapshot unavailable' on failure and keeps the page working", async () => {
    vi.spyOn(client, "getHealth").mockRejectedValue(new client.ApiError(503, "/api/health"));
    vi.spyOn(client, "getMethodology").mockRejectedValue(new client.ApiError(503, "/api/methodology"));
    renderAt("/methodology");
    expect(await screen.findByText("Snapshot unavailable")).toBeInTheDocument();
    expect(screen.getByRole("heading", { level: 1, name: "How CLIO classifies a week" })).toBeInTheDocument();
  });

  it("has a skip link, the archive strip and the footer", () => {
    vi.spyOn(client, "getHealth").mockResolvedValue(health);
    renderAt("/");
    expect(screen.getByRole("link", { name: "Skip to main content" })).toHaveAttribute("href", "#main");
    expect(screen.getByText("not a live monitor")).toBeInTheDocument();
    expect(screen.getByText("Saturday to Friday")).toBeInTheDocument();
    expect(screen.getByRole("contentinfo")).toHaveTextContent("CLIO");
  });

  it("marks the active route in the nav", () => {
    vi.spyOn(client, "getHealth").mockResolvedValue(health);
    renderAt("/findings/some-slug");
    const nav = screen.getByRole("navigation", { name: "Main" });
    expect(within(nav).getByRole("link", { name: "Findings" })).toHaveAttribute("aria-current", "page");
    expect(within(nav).getByRole("link", { name: "Ledger" })).not.toHaveAttribute("aria-current");
    expect(within(nav).getByRole("link", { name: "About" })).not.toHaveAttribute("aria-current");
  });

  it("shows Not found with a link to the ledger on an unknown path", () => {
    vi.spyOn(client, "getHealth").mockResolvedValue(health);
    renderAt("/nope");
    expect(screen.getByRole("heading", { name: "Not found" })).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Back to the ledger" })).toHaveAttribute("href", "/");
  });
});
