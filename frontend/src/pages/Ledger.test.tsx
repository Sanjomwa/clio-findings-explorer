import { afterEach, describe, expect, it, vi } from "vitest";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { createMemoryRouter, RouterProvider } from "react-router-dom";
import * as client from "../api/client";
import FindingRegister from "../components/FindingRegister";
import { computeLayout, cellX, cellY } from "../lib/ledgerLayout";
import { routes } from "../routes";

type Week = client.TimelineResponse["weeks"][number];
type Finding = client.FindingList["findings"][number];

const w = (d: string, s: Week["regime_state"], c: Week["confidence_level"], slug: string | null = null): Week => ({
  week_start_date: d,
  country_iso: "KE",
  regime_state: s,
  confidence_level: c,
  finding_slug: slug,
});

const WEEKS: Week[] = [
  w("2023-07-15", "CRISIS", "HIGH", "july-2023"),
  w("2024-06-15", "STABLE", "INSUFFICIENT_DATA"),
  w("2024-06-22", "CRISIS", "HIGH", "finance-bill-2024"),
  w("2024-06-29", "ESCALATION", "INSUFFICIENT_DATA"),
  w("2024-07-06", "STABLE", "MEDIUM"),
  w("2025-06-21", "STABLE", "HIGH", "june-july-2025"),
];

const f = (slug: string, title: string, d: string, s: Finding["regime_state"]): Finding => ({
  slug,
  title,
  week_start_date: d,
  country_iso: "KE",
  regime_state: s,
  confidence_level: "HIGH",
  teaser: `Teaser for ${slug}.`,
});

// API order (curated position), deliberately not date order.
const FINDINGS: Finding[] = [
  f("finance-bill-2024", "22–28 June 2024: protest and suppression both SEVERE", "2024-06-22", "CRISIS"),
  f("june-july-2025", "21–27 June 2025: STABLE, with Telegram far above its baseline", "2025-06-21", "STABLE"),
  f("july-2023", "15–21 July 2023: CRISIS, with OONI signals flat", "2023-07-15", "CRISIS"),
];

function mockApi(opts: { weeks?: Week[] | Error; findings?: Finding[] | Error } = {}) {
  vi.spyOn(client, "getHealth").mockResolvedValue({ snapshot_version: "2026-10-10.1" } as client.Health);
  const tl = opts.weeks ?? WEEKS;
  const fl = opts.findings ?? FINDINGS;
  const timeline = vi
    .spyOn(client, "getTimeline")
    .mockImplementation(() =>
      tl instanceof Error ? Promise.reject(tl) : Promise.resolve({ weeks: tl } as client.TimelineResponse),
    );
  vi.spyOn(client, "listFindings").mockImplementation(() =>
    fl instanceof Error ? Promise.reject(fl) : Promise.resolve({ findings: fl } as client.FindingList),
  );
  return { timeline };
}

function renderLedger() {
  return render(<RouterProvider router={createMemoryRouter(routes, { initialEntries: ["/"] })} />);
}

afterEach(() => {
  vi.restoreAllMocks();
  vi.unstubAllGlobals();
});

const fillOf = (c: HTMLElement, date: string) => c.querySelector(`rect[data-week="${date}"]`)?.getAttribute("fill");

describe("Ledger cells and legend", () => {
  it("colours insufficient-data weeks --st-I and ESCALATION+INSUFFICIENT_DATA weeks --st-E", async () => {
    mockApi();
    const { container } = renderLedger();
    await screen.findByRole("img");
    expect(fillOf(container, "2024-06-15")).toBe("var(--st-I)");
    expect(fillOf(container, "2024-06-29")).toBe("var(--st-E)");
    expect(fillOf(container, "2024-06-22")).toBe("var(--st-C)");
  });

  it("shows legend counts computed from the data, in order", async () => {
    mockApi();
    renderLedger();
    await screen.findByRole("img");
    const legend = document.querySelector(".legend") as HTMLElement;
    const texts = Array.from(legend.querySelectorAll("span")).map((s) => s.textContent);
    expect(texts).toEqual([
      "Insufficient data · 1",
      "STABLE · 2",
      "ESCALATION · 1",
      "CRISIS · 2",
      "Published finding",
    ]);
  });

  it("prints the record line with the last Friday, the h1, the dek and the head row", async () => {
    mockApi();
    renderLedger();
    expect(await screen.findByText("Register of classified weeks · 15 Jul 2023 to 27 Jun 2025")).toBeInTheDocument();
    expect(screen.getByRole("heading", { level: 1 })).toHaveTextContent(
      "Nearly thirty years of Kenya, one week at a time",
    );
    expect(screen.getByText("Pale cells are weeks with too little data to judge").tagName).toBe("MARK");
    expect(screen.getByText(/Three weeks are published findings/)).toBeInTheDocument();
    expect(screen.getByText("One row per year · one cell per week · 6 weeks")).toBeInTheDocument();
    expect(screen.getByRole("heading", { level: 2, name: "The three findings" })).toBeInTheDocument();
  });

  it("labels each finding in the margin as 'Mon YYYY · STATE'", async () => {
    mockApi();
    const { container } = renderLedger();
    await screen.findByRole("img");
    const labels = Array.from(container.querySelectorAll(".ledger-label")).map((n) => n.textContent);
    expect(labels).toEqual(["Jul 2023 · CRISIS", "Jun 2024 · CRISIS", "Jun 2025 · STABLE"]);
  });

  it("describes the SVG for assistive technology", async () => {
    mockApi();
    renderLedger();
    expect(await screen.findByRole("img")).toHaveAttribute(
      "aria-label",
      "Ledger of 6 classified weeks from 2023 to 2025. The three findings are listed below.",
    );
  });

  it("ends the SVG description with a failure note when the findings list failed", async () => {
    mockApi({ findings: new client.ApiError(500, "/api/findings") });
    renderLedger();
    expect(await screen.findByRole("img")).toHaveAttribute(
      "aria-label",
      "Ledger of 6 classified weeks from 2023 to 2025. The findings could not be loaded.",
    );
  });

  it("does not change any cell fill when the theme switches", async () => {
    mockApi();
    const { container } = renderLedger();
    await screen.findByRole("img");
    const fills = () => Array.from(container.querySelectorAll("rect[data-week]")).map((r) => r.getAttribute("fill"));
    const before = fills();
    expect(before.every((x) => x?.startsWith("var(--st-"))).toBe(true);
    await userEvent.click(screen.getByRole("button", { name: "Dark" }));
    expect(fills()).toEqual(before);
  });
});

describe("Ledger tooltip", () => {
  const layout = computeLayout(1000, 3);
  const over = (container: HTMLElement, row: number, col: number) => {
    const svg = container.querySelector("svg.ledger-svg") as SVGSVGElement;
    fireEvent.mouseMove(svg, { clientX: cellX(layout, col) + 1, clientY: cellY(layout, row) + 1 });
  };

  it("shows date range, state, confidence and the finding line, and no band text", async () => {
    mockApi();
    const { container } = renderLedger();
    await screen.findByRole("img");
    over(container, 1, 24); // 2024-06-22
    const tip = screen.getByRole("tooltip");
    expect(tip).toHaveTextContent("22–28 Jun 2024");
    expect(tip).toHaveTextContent("CRISIS");
    expect(tip).toHaveTextContent("High confidence");
    expect(tip).toHaveTextContent("Finding: open ↵");
    expect(tip.textContent).not.toMatch(/protest|violence|suppression|SEVERE|ELEVATED|NORMAL/i);
  });

  it("reads 'STABLE (insufficient data)' with no confidence line for an unscored week", async () => {
    mockApi();
    const { container } = renderLedger();
    await screen.findByRole("img");
    over(container, 1, 23); // 2024-06-15
    const tip = screen.getByRole("tooltip");
    expect(tip).toHaveTextContent("15–21 Jun 2024");
    expect(tip).toHaveTextContent("STABLE (insufficient data)");
    expect(tip.textContent).not.toMatch(/confidence|Finding:/);
  });

  it("shows 'Insufficient data' as the confidence of an ESCALATION week, with the long range", async () => {
    mockApi();
    const { container } = renderLedger();
    await screen.findByRole("img");
    over(container, 1, 25); // 2024-06-29
    const tip = screen.getByRole("tooltip");
    expect(tip).toHaveTextContent("29 Jun 2024 – 5 Jul 2024");
    expect(tip).toHaveTextContent("ESCALATION");
    expect(tip).toHaveTextContent("Insufficient data");
  });

  it("hides the tooltip when the pointer leaves", async () => {
    mockApi();
    const { container } = renderLedger();
    await screen.findByRole("img");
    over(container, 1, 24);
    fireEvent.mouseLeave(container.querySelector("svg.ledger-svg") as SVGSVGElement);
    expect(screen.queryByRole("tooltip")).toBeNull();
  });
});

describe("Ledger keyboard and navigation", () => {
  it("Tab reaches each finding in date order, ordinary cells are not focusable, Enter opens it", async () => {
    mockApi();
    const { container } = renderLedger();
    await screen.findByRole("img");
    expect(container.querySelectorAll("rect[tabindex]").length).toBe(0);
    const seen: string[] = [];
    for (let i = 0; i < 30 && seen.length < 3; i++) {
      await userEvent.tab();
      const slug = document.activeElement?.getAttribute("data-slug");
      if (slug) seen.push(slug);
    }
    expect(seen).toEqual(["july-2023", "finance-bill-2024", "june-july-2025"]);
    expect(screen.getByRole("tooltip")).toHaveTextContent("21–27 Jun 2025");
    await userEvent.keyboard("{Enter}");
    expect(await screen.findByRole("heading", { name: "Finding: june-july-2025" })).toBeInTheDocument();
  });

  it("names each finding with title, week and state", async () => {
    mockApi();
    renderLedger();
    await screen.findByRole("img");
    expect(
      screen.getByRole("link", {
        name: "Finding: Protest and suppression both SEVERE, week of 22 June 2024, CRISIS",
      }),
    ).toBeInTheDocument();
  });

  it("opens a finding when its outline is clicked", async () => {
    mockApi();
    renderLedger();
    await screen.findByRole("img");
    await userEvent.click(screen.getByRole("link", { name: /week of 15 July 2023/ }));
    expect(await screen.findByRole("heading", { name: "Finding: july-2023" })).toBeInTheDocument();
  });

  it("hides margin labels and leader lines below 600px but keeps the outlines", async () => {
    class RO {
      constructor(private cb: ResizeObserverCallback) {}
      observe() {
        this.cb([{ contentRect: { width: 400 } } as ResizeObserverEntry], this as unknown as ResizeObserver);
      }
      unobserve() {}
      disconnect() {}
    }
    vi.stubGlobal("ResizeObserver", RO);
    mockApi();
    const { container } = renderLedger();
    await screen.findByRole("img");
    await waitFor(() => expect(container.querySelector("svg.ledger-svg")).toHaveAttribute("width", "400"));
    expect(container.querySelectorAll(".ledger-label").length).toBe(0);
    expect(container.querySelectorAll(".ledger-leader").length).toBe(0);
    expect(container.querySelectorAll(".ledger-outline").length).toBe(3);
  });
});

describe("Ledger states", () => {
  it("shows a placeholder while loading", () => {
    vi.spyOn(client, "getHealth").mockResolvedValue({ snapshot_version: "x" } as client.Health);
    vi.spyOn(client, "getTimeline").mockReturnValue(new Promise(() => {}));
    vi.spyOn(client, "listFindings").mockReturnValue(new Promise(() => {}));
    const { container } = renderLedger();
    expect(container.querySelector(".ledger-placeholder")).not.toBeNull();
  });

  it("shows an error with Try again when the timeline fails, and retries", async () => {
    const { timeline } = mockApi({ weeks: new client.ApiError(500, "/api/timeline") });
    renderLedger();
    expect(await screen.findByText("The ledger could not be loaded.")).toBeInTheDocument();
    expect(screen.getByRole("navigation", { name: "Main" })).toBeInTheDocument();
    timeline.mockResolvedValue({ weeks: WEEKS } as client.TimelineResponse);
    await userEvent.click(screen.getByRole("button", { name: "Try again" }));
    expect(await screen.findByRole("img")).toBeInTheDocument();
  });

  it("draws the ledger without outlines when only the findings list fails", async () => {
    mockApi({ findings: new client.ApiError(500, "/api/findings") });
    const { container } = renderLedger();
    expect(await screen.findByText("The findings list could not be loaded.")).toBeInTheDocument();
    expect(await screen.findByRole("img")).toBeInTheDocument();
    expect(container.querySelectorAll(".ledger-outline").length).toBe(0);
    expect(container.querySelectorAll("rect[data-week]").length).toBe(WEEKS.length);
  });

  it("shows a message for an empty weeks array", async () => {
    mockApi({ weeks: [] });
    renderLedger();
    expect(await screen.findByText("No classified weeks in this snapshot.")).toBeInTheDocument();
  });
});

describe("FindingRegister", () => {
  const renderRegister = () =>
    render(
      <RouterProvider
        router={createMemoryRouter([{ path: "/", element: <FindingRegister findings={FINDINGS} /> }])}
      />,
    );

  it("keeps API order, not week-date order", () => {
    renderRegister();
    const hrefs = screen.getAllByRole("link").map((a) => a.getAttribute("href"));
    expect(hrefs).toEqual(["/findings/finance-bill-2024", "/findings/june-july-2025", "/findings/july-2023"]);
  });

  it("shows record id, range, stripped title, teaser and state", () => {
    renderRegister();
    const first = screen.getAllByRole("listitem")[0] as HTMLElement;
    expect(first).toHaveTextContent("KE·2024·W25");
    expect(first).toHaveTextContent("22–28 Jun 2024");
    expect(first).toHaveTextContent("Protest and suppression both SEVERE");
    expect(first).not.toHaveTextContent("22–28 June 2024:");
    expect(first).toHaveTextContent("Teaser for finance-bill-2024.");
    expect(first.querySelector(".lbl.sm")).toHaveTextContent("CRISIS");
  });
});
