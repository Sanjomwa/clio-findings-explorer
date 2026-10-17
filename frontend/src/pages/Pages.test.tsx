import { afterEach, describe, expect, it, vi } from "vitest";
import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { createMemoryRouter, RouterProvider } from "react-router-dom";
import * as client from "../api/client";
import { routes } from "../routes";

type Finding = client.FindingList["findings"][number];

const f = (slug: string, title: string): Finding => ({
  slug,
  title,
  week_start_date: "2024-06-22",
  country_iso: "KE",
  regime_state: "CRISIS",
  confidence_level: "HIGH",
  teaser: `Teaser for ${slug}.`,
});

// API order, deliberately not alphabetical.
const FINDINGS = [f("zeta", "22–28 June 2024: Zeta"), f("alpha", "22–28 June 2024: Alpha")];

const METHODOLOGY = {
  snapshot_version: "2026-10-10.1",
  families: [{ family: "protest", definition: "Protest def." }],
  regime_states: [{ state: "STABLE", definition: "Stable def." }],
  confidence_levels: [
    { level: "HIGH", definition: "High def." },
    { level: "INSUFFICIENT_DATA", definition: "Insufficient def." },
  ],
  family_bands: [{ band: "NORMAL", definition: "Normal def." }],
  sources: [],
  manifest: {
    version: "2026-10-10.1",
    exported_at: "2026-10-10T07:32:54Z",
    tables: [
      {
        file: "regime_weeks.ndjson",
        source_table: "intelligence.acled_pressure_regimes",
        sql: "SELECT 1 FROM regimes",
        row_count: 1523,
        exported_at: "2026-10-10T07:32:45Z",
      },
      {
        file: "ooni_weekly_signals.ndjson",
        source_table: "features.ooni_weekly_signals",
        sql: "SELECT 2 FROM ooni",
        row_count: 550,
        exported_at: "2026-10-10T07:32:51Z",
      },
    ],
  },
} as unknown as client.Methodology;

function renderAt(path: string) {
  vi.spyOn(client, "getHealth").mockResolvedValue({ snapshot_version: "2026-10-10.1" } as client.Health);
  render(<RouterProvider router={createMemoryRouter(routes, { initialEntries: [path] })} />);
}

afterEach(() => vi.restoreAllMocks());

describe("/findings", () => {
  it("shows the count and the list in API order", async () => {
    vi.spyOn(client, "listFindings").mockResolvedValue({ findings: FINDINGS } as client.FindingList);
    renderAt("/findings");
    expect(await screen.findByText("Register · 2 findings")).toBeInTheDocument();
    expect(screen.getByRole("heading", { level: 1, name: "Published findings" })).toBeInTheDocument();
    const titles = screen.getAllByText(/Zeta|Alpha/).map((n) => n.textContent);
    expect(titles).toEqual(["Zeta", "Alpha"]);
    expect(document.title).toBe("Published findings · CLIO Findings Explorer");
  });

  it("shows an error with a working retry", async () => {
    const spy = vi.spyOn(client, "listFindings").mockRejectedValueOnce(new Error("boom"));
    spy.mockResolvedValue({ findings: FINDINGS } as client.FindingList);
    renderAt("/findings");
    expect(await screen.findByText("The findings list could not be loaded.")).toBeInTheDocument();
    await userEvent.click(screen.getByRole("button", { name: "Try again" }));
    expect(await screen.findByText("Register · 2 findings")).toBeInTheDocument();
  });
});

describe("/methodology", () => {
  it("renders the four sections, links and snapshot line", async () => {
    vi.spyOn(client, "getMethodology").mockResolvedValue(METHODOLOGY);
    renderAt("/methodology");
    for (const h of ["What each family counts", "Regime states", "Confidence levels", "Family bands"]) {
      expect(await screen.findByRole("heading", { level: 2, name: h })).toBeInTheDocument();
    }
    expect(screen.getByText("Protest")).toBeInTheDocument();
    expect(screen.getByText("Insufficient data")).toBeInTheDocument();
    expect(screen.getByText("High")).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "CLIO's production code" })).toHaveAttribute(
      "href",
      "https://github.com/Sanjomwa/Civil-Liberties-Intelligence-Observatory",
    );
    expect(within(screen.getByRole("main")).getByRole("link", { name: "About" })).toHaveAttribute("href", "/about");
    expect(screen.getByText("Snapshot 2026-10-10.1.")).toBeInTheDocument();
    expect(screen.queryByText(/provisional/i)).toBeNull();
    expect(document.title).toBe("How CLIO classifies a week · CLIO Findings Explorer");
  });

  it("hides a section whose array is empty", async () => {
    vi.spyOn(client, "getMethodology").mockResolvedValue({ ...METHODOLOGY, families: [] } as client.Methodology);
    renderAt("/methodology");
    await screen.findByRole("heading", { level: 2, name: "Regime states" });
    expect(screen.queryByRole("heading", { name: "What each family counts" })).toBeNull();
  });
});

describe("/about", () => {
  it("has the sections, no Built with, and the snapshot rows with SQL", async () => {
    vi.spyOn(client, "getMethodology").mockResolvedValue(METHODOLOGY);
    renderAt("/about");
    for (const h of ["Why it exists", "How a finding is made", "The three sources", "The snapshot", "What it is not"]) {
      expect(await screen.findByRole("heading", { level: 2, name: h })).toBeInTheDocument();
    }
    expect(screen.queryByText(/built with/i)).toBeNull();
    expect(
      screen.getByText(
        /A finding cannot be published without at least one caveat: the database refuses it, and the loader checks it when content is loaded\./,
      ),
    ).toBeInTheDocument();
    expect(screen.getAllByRole("listitem").filter((li) => li.closest("ol.steps"))).toHaveLength(4);
    expect(screen.getByText(/Version 2026-10-10.1, exported 10 Oct 2026\./)).toBeInTheDocument();
    expect(screen.getByText("regime_weeks.ndjson")).toBeInTheDocument();
    expect(screen.getByText("intelligence.acled_pressure_regimes")).toBeInTheDocument();
    expect(screen.getByText("1,523 rows")).toBeInTheDocument();
    expect(screen.getByText("550 rows")).toBeInTheDocument();
    const details = document.querySelectorAll("ul.snapshot-files details");
    expect(details).toHaveLength(2);
    expect(details[0]?.querySelector("summary")?.textContent).toBe("SQL");
    expect(details[0]?.querySelector("pre")?.textContent).toBe("SELECT 1 FROM regimes");
    expect(screen.getByRole("link", { name: "verdict logs" })).toHaveAttribute(
      "href",
      "https://github.com/Sanjomwa/clio-findings-explorer/tree/main/docs/reviews",
    );
    await waitFor(() => expect(document.title).toBe("About · CLIO Findings Explorer"));
  });
});
