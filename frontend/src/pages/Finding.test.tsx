import { readFileSync, readdirSync } from "node:fs";
import { join } from "node:path";
import { afterEach, describe, expect, it, vi } from "vitest";
import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { createMemoryRouter, RouterProvider } from "react-router-dom";
import * as client from "../api/client";
import { routes } from "../routes";

type Finding = client.FindingRecord;
type Card = client.AcledEvidence;
type ListItem = client.FindingList["findings"][number];

const SNAP = "2026-10-10.1";

const baseFinding = (over: Partial<Finding> = {}): Finding => ({
  slug: "finance-bill-2024",
  title: "22–28 June 2024: protest and suppression both SEVERE",
  teaser: "CLIO's first CRISIS week of the 2024 Finance Bill protests, the week protesters entered Parliament.",
  position: 1,
  key_phrase: "CLIO's first CRISIS week",
  week_start_date: "2024-06-22",
  country_iso: "KE",
  regime_state: "CRISIS",
  confidence_level: "HIGH",
  classification: {
    protest_band: "SEVERE",
    violence_band: "ELEVATED",
    suppression_band: "SEVERE",
    previous_regime: "STABLE",
    pre_transition_target: null,
  },
  summary_md: "First paragraph of the summary.\n\nSecond paragraph of the summary.\n",
  caveats: [
    { severity: "limitation", caveat_md: "Limitation one." },
    { severity: "do_not_conclude", caveat_md: "Do not conclude that anything caused anything." },
    { severity: "limitation", caveat_md: "Limitation two." },
  ],
  sources: [
    { source: "acled", name: "ACLED source name", provenance_note: "ACLED provenance text.", url: "https://acled.example/" },
    { source: "ooni", name: "OONI source name", provenance_note: "OONI provenance text." },
  ],
  citations: [
    { claim: "Claim one", citation: "Cite A", url: "https://a.example/" },
    { claim: "Claim two", citation: "Cite B", url: "https://b.example/" },
    { claim: "Claim three", citation: "Cite A", url: "https://a.example/" },
  ],
  evidence_available: ["acled", "ooni", "google_transparency"],
  published_at: "2026-10-15T00:00:00Z",
  ...over,
});

const acledCard = (over: Partial<Card["evidence"]> = {}): Card => ({
  snapshot_version: SNAP,
  evidence: {
    slug: "finance-bill-2024",
    source: "acled",
    has_data: true,
    period_start: "2024-06-22",
    period_end: "2024-06-28",
    period_grain: "week",
    headline_metric: "Conflict events recorded in the week (all event types)",
    metric_value: 167,
    comparison: { label: "Median of the 12 weeks before", value: 55 },
    provenance_note: "ACLED note",
    snapshot_files: ["acled_signal_context.ndjson"],
    supporting: {
      kind: "acled",
      classifier_input: true,
      week: {
        week_start_date: "2024-06-22",
        total_events: 167,
        total_fatalities: 56,
        signal_valid: true,
        protest_pressure_z: 2.0057,
        violence_pressure_z: 1.4379,
        suppression_z: null,
        protest_active_baseline_weeks: 12,
        violence_active_baseline_weeks: 12,
        suppression_active_baseline_weeks: 10,
        sparse_protest_baseline_flag: false,
        sparse_violence_baseline_flag: false,
        sparse_suppression_baseline_flag: false,
        zero_variance_flag: false,
        low_event_density_flag: false,
        high_methodology_risk_flag: false,
      },
      prior_12_week_median_events: 55,
      prior_12_week_median_fatalities: 3,
      series: [],
    },
    ...over,
  },
});

const ooniCard = (): Card => ({
  snapshot_version: SNAP,
  evidence: {
    slug: "finance-bill-2024",
    source: "ooni",
    has_data: true,
    period_start: "2024-06-22",
    period_end: "2024-06-28",
    period_grain: "week",
    headline_metric: "Anomalous measurement rate, for the test furthest above its own 12-week baseline",
    metric_value: 0.03,
    comparison: { label: "signal: standard deviations from its own 12-week baseline", value: 1.2370736 },
    provenance_note: "OONI note",
    snapshot_files: ["ooni_weekly_signals.ndjson"],
    supporting: {
      kind: "ooni",
      top_test: "signal",
      note: "These OONI tests check whether specific apps and sites can be reached from testers' networks.",
      tests: [
        {
          week_start_date: "2024-06-22",
          test_name: "signal",
          anomalous_total_scored: 499,
          anomalous_count: 15,
          anomalous_rate: 0.03,
          anomalous_baseline_rate_12w: 0.02,
          anomalous_zscore_12w: 1.237,
          anomalous_low_sample_flag: false,
          anomalous_sparse_baseline_flag: false,
          blocked_total_observations: 1,
          blocked_count: 0,
          blocked_rate: 0,
          blocked_baseline_rate_12w: 0,
          blocked_zscore_12w: 0,
          blocked_low_sample_flag: false,
          blocked_sparse_baseline_flag: false,
          feature_version: "v1",
        },
      ],
    },
  },
});

const googleCard = (): Card => ({
  snapshot_version: SNAP,
  evidence: {
    slug: "finance-bill-2024",
    source: "google_transparency",
    has_data: true,
    period_start: "2024-01-01",
    period_end: "2024-06-30",
    period_grain: "half_year",
    headline_metric: "Removal requests in Google's government-requests report for Kenya, this half-year",
    metric_value: 9,
    comparison: null,
    provenance_note: "Google note",
    snapshot_files: ["google_transparency_requests.ndjson"],
    supporting: {
      kind: "google_transparency",
      time_period: "January - June 2024",
      totals: { number_of_requests: 9, items_requested_removal: 1, items_removed_legal: 0, items_removed_policy: 0 },
      rows: [],
    },
  },
});

const noData = (source: Card["evidence"]["source"], note: string): Card => ({
  snapshot_version: SNAP,
  evidence: {
    slug: "finance-bill-2024",
    source,
    has_data: false,
    period_start: null,
    period_end: null,
    period_grain: source === "google_transparency" ? "half_year" : "week",
    headline_metric: "Metric",
    metric_value: null,
    comparison: null,
    provenance_note: note,
    snapshot_files: [],
    supporting: null,
  },
});

const item = (slug: string, title: string): ListItem => ({
  slug,
  title,
  week_start_date: "2024-06-22",
  country_iso: "KE",
  regime_state: "CRISIS",
  confidence_level: "HIGH",
  teaser: "t",
});
const LIST: ListItem[] = [
  item("finance-bill-2024", "22–28 June 2024: first title"),
  item("june-july-2025", "21–27 June 2025: second title"),
  item("july-2023", "15–21 July 2023: third title"),
];

type Week = client.TimelineResponse["weeks"][number];
const TIMELINE: Week[] = [
  { week_start_date: "2024-06-15", country_iso: "KE", regime_state: "STABLE", confidence_level: "INSUFFICIENT_DATA", finding_slug: null },
  { week_start_date: "2024-06-22", country_iso: "KE", regime_state: "CRISIS", confidence_level: "HIGH", finding_slug: "finance-bill-2024" },
  { week_start_date: "2024-06-29", country_iso: "KE", regime_state: "ESCALATION", confidence_level: "LOW", finding_slug: "july-2023" },
];

interface Opts {
  finding?: Finding | Error;
  list?: ListItem[] | Error | "pending";
  timeline?: Error;
  acled?: Card | Error;
  ooni?: Card | Error;
  google?: Card | Error;
}
const settle = <T,>(v: T | Error) => (v instanceof Error ? Promise.reject(v) : Promise.resolve(v));

function mockApi(o: Opts = {}) {
  vi.spyOn(client, "getHealth").mockResolvedValue({ snapshot_version: SNAP } as client.Health);
  vi.spyOn(client, "getFinding").mockImplementation(() => {
    const f = o.finding ?? baseFinding();
    return f instanceof Error ? Promise.reject(f) : Promise.resolve({ snapshot_version: SNAP, finding: f });
  });
  vi.spyOn(client, "listFindings").mockImplementation(() => {
    if (o.list === "pending") return new Promise(() => {});
    const l = o.list ?? LIST;
    return l instanceof Error ? Promise.reject(l) : Promise.resolve({ snapshot_version: SNAP, findings: l });
  });
  const timeline = vi
    .spyOn(client, "getTimeline")
    .mockImplementation(() => settle(o.timeline ?? ({ weeks: TIMELINE } as client.TimelineResponse)));
  vi.spyOn(client, "getAcledEvidence").mockImplementation(() => settle(o.acled ?? acledCard()));
  vi.spyOn(client, "getOoniEvidence").mockImplementation(() => settle(o.ooni ?? ooniCard()));
  vi.spyOn(client, "getGoogleTransparencyEvidence").mockImplementation(() => settle(o.google ?? googleCard()));
  return { timeline };
}

function renderAt(slug = "finance-bill-2024") {
  const router = createMemoryRouter(routes, { initialEntries: [`/findings/${slug}`] });
  return { router, ...render(<RouterProvider router={router} />) };
}

afterEach(() => {
  vi.restoreAllMocks();
});

const exhibit = (source: string) => document.querySelector(`.ex[data-source="${source}"]`) as HTMLElement;

describe("record header and state line", () => {
  it("shows the record, week and snapshot, and adds Finding N of M only once the list loads", async () => {
    mockApi({ list: "pending" });
    const { container } = renderAt();
    await screen.findByRole("heading", { level: 1 });
    const meta = container.querySelector(".meta") as HTMLElement;
    expect(meta).toHaveTextContent("Record KE·2024·W25");
    expect(meta).toHaveTextContent("Week 22–28 Jun 2024");
    expect(meta).toHaveTextContent(`Snapshot ${SNAP}`);
    expect(meta).not.toHaveTextContent("Finding 1 of 3");
  });

  it("shows Finding N of M when the list has loaded", async () => {
    mockApi();
    const { container } = renderAt();
    await waitFor(() => expect(container.querySelector(".meta")).toHaveTextContent("Finding 1 of 3"));
  });

  it("shows the STABLE sentence for STABLE+HIGH, and the pre-transition sentence when set", async () => {
    mockApi({
      finding: baseFinding({
        regime_state: "STABLE",
        confidence_level: "HIGH",
        classification: { ...baseFinding().classification, pre_transition_target: "REPRESSION" },
      }),
    });
    renderAt();
    expect(await screen.findByText(/STABLE: no regime rule was met this week\./)).toHaveTextContent(
      "STABLE: no regime rule was met this week. Bands can still be raised; a first raised week is held at STABLE until a second consecutive one follows. Raised: would have entered REPRESSION if the next week also qualified.",
    );
    expect(screen.getByText("High confidence")).toBeInTheDocument();
  });

  it("shows no STABLE sentence for CRISIS", async () => {
    mockApi();
    renderAt();
    await screen.findByRole("heading", { level: 1 });
    expect(screen.queryByText(/no regime rule was met/)).toBeNull();
    expect(screen.queryByText(/Raised: would have entered/)).toBeNull();
  });

  it("labels STABLE+INSUFFICIENT_DATA as STABLE (insufficient data) with no confidence text", async () => {
    mockApi({ finding: baseFinding({ regime_state: "STABLE", confidence_level: "INSUFFICIENT_DATA" }) });
    const { container } = renderAt();
    await screen.findByRole("heading", { level: 1 });
    expect(container.querySelector(".lbl")).toHaveTextContent("STABLE (insufficient data)");
    expect(container.querySelector(".conf")).toBeNull();
    expect(screen.queryByText(/no regime rule was met/)).toBeNull();
  });
});

describe("headline, dek, summary and limits", () => {
  it("sets the title without the date prefix, and the document title", async () => {
    mockApi();
    renderAt();
    expect(await screen.findByRole("heading", { level: 1 })).toHaveTextContent(
      "Protest and suppression both SEVERE",
    );
    expect(document.title).toBe("Protest and suppression both SEVERE · CLIO Findings Explorer");
  });

  it("marks exactly the key phrase in the dek", async () => {
    mockApi();
    const { container } = renderAt();
    await screen.findByRole("heading", { level: 1 });
    expect(container.querySelector(".dek mark")?.textContent).toBe("CLIO's first CRISIS week");
  });

  it("renders the teaser plain when the key phrase is null or not found", async () => {
    mockApi({ finding: baseFinding({ key_phrase: "not in the teaser" }) });
    const { container } = renderAt();
    await screen.findByRole("heading", { level: 1 });
    expect(container.querySelector(".dek mark")).toBeNull();
    expect(container.querySelector(".dek")?.textContent).toBe(baseFinding().teaser);
  });

  it("splits the summary into paragraphs", async () => {
    mockApi();
    const { container } = renderAt();
    await screen.findByRole("heading", { level: 1 });
    const ps = [...container.querySelectorAll(".read p")].map((p) => p.textContent);
    expect(ps).toEqual(["First paragraph of the summary.", "Second paragraph of the summary."]);
  });

  it("puts do_not_conclude caveats after the limitations, with a bold prefix", async () => {
    mockApi();
    renderAt();
    const aside = await screen.findByRole("complementary", { name: "What this does not establish" });
    const ps = [...aside.querySelectorAll("p")].map((p) => p.textContent);
    expect(ps).toEqual([
      "Limitation one.",
      "Limitation two.",
      "Do not conclude that anything caused anything.",
    ]);
    expect(aside.querySelector("p.dnc b")?.textContent).toBe("Do not conclude");
  });
});

describe("family bands", () => {
  it("shows BAND · z to two decimals, and a dash for a null z", async () => {
    mockApi();
    const { container } = renderAt();
    await waitFor(() => expect(container.querySelector('[data-family="protest"] .v')).toHaveTextContent("SEVERE · 2.01"));
    expect(container.querySelector('[data-family="violence"] .v')).toHaveTextContent("ELEVATED · 1.44");
    expect(container.querySelector('[data-family="suppression"] .v')).toHaveTextContent("SEVERE · –");
    expect(container.querySelectorAll(".band svg")).toHaveLength(3);
    expect(screen.getByText(/dashed lines at 1\.0 \(ELEVATED\) and 2\.0 \(SEVERE\)/)).toBeInTheDocument();
  });

  it("shows band names without bars when the ACLED card fails", async () => {
    mockApi({ acled: new Error("boom") });
    const { container } = renderAt();
    await waitFor(() => expect(exhibit("acled")).toHaveTextContent("This exhibit could not be loaded."));
    expect(container.querySelector('[data-family="protest"] .v')?.textContent).toBe("SEVERE");
    expect(container.querySelectorAll(".band svg")).toHaveLength(0);
  });
});

describe("context strip", () => {
  it("requests 91 days either side, draws the weeks, and navigates from a finding week", async () => {
    const { timeline } = mockApi();
    const user = userEvent.setup();
    const { container, router } = renderAt();
    const strip = await screen.findByRole("img", { name: /the finding's week is CRISIS/ });
    expect(timeline).toHaveBeenCalledWith({ from: "2024-03-23", to: "2024-09-21" });
    expect(strip.querySelectorAll("rect[data-week]")).toHaveLength(3);
    expect(container.querySelector('rect[data-week="2024-06-15"]')?.getAttribute("fill")).toBe("var(--st-I)");
    await user.click(container.querySelector('rect[data-week="2024-06-15"]') as Element);
    expect(router.state.location.pathname).toBe("/findings/finance-bill-2024");
    await user.click(container.querySelector('rect[data-week="2024-06-29"]') as Element);
    await waitFor(() => expect(router.state.location.pathname).toBe("/findings/july-2023"));
  });

  it("hides only the strip when the timeline fails", async () => {
    mockApi({ timeline: new Error("down") });
    renderAt();
    await screen.findByRole("heading", { level: 1 });
    await waitFor(() => expect(client.getTimeline).toHaveBeenCalled());
    expect(screen.queryByText("The 13 weeks either side")).toBeNull();
    expect(screen.getByRole("navigation", { name: "Findings" })).toBeInTheDocument();
  });
});

describe("exhibits", () => {
  it("shows the three cards with periods, numbers, notes and provenance", async () => {
    mockApi();
    renderAt();
    await waitFor(() => expect(exhibit("google_transparency")).toHaveTextContent("9"));
    const a = exhibit("acled");
    expect(a).toHaveTextContent("Exhibit A · ACLED");
    expect(a).toHaveTextContent("This week");
    expect(a).toHaveTextContent("167");
    expect(a).toHaveTextContent("Median of the 12 weeks before: 55");
    expect(a).toHaveTextContent(
      "ACLED is the classifier's own input, so this is not independent corroboration of the label.",
    );
    expect(a).toHaveTextContent(`ACLED · week 22–28 Jun 2024 · snapshot ${SNAP}`);
    const g = exhibit("google_transparency");
    expect(g).toHaveTextContent("Exhibit C · Google");
    expect(g).toHaveTextContent("January – June 2024");
    expect(g).toHaveTextContent("A half-year total with no comparison figure. It does not show what happened in this week.");
    expect(g.querySelector("svg")).toBeNull();
    expect(g).toHaveTextContent(`Google Transparency Report · January – June 2024 · snapshot ${SNAP}`);
  });

  it("leads OONI with the top test's anomaly rate, puts the z-score in the description, and shows the API's note verbatim", async () => {
    mockApi();
    renderAt();
    await waitFor(() => expect(exhibit("ooni")).toHaveTextContent("3.0%"));
    const o = exhibit("ooni");
    expect(o.querySelector(".num")?.textContent).toBe("3.0%");
    expect(o.querySelector(".d")?.textContent).toBe(
      "Signal's anomaly rate this week (15 of 499 measurements), against 2.0% over its own 12-week baseline. z-score 1.24.",
    );
    expect(o.querySelector(".note")?.textContent).toBe(
      "These OONI tests check whether specific apps and sites can be reached from testers' networks.",
    );
    expect(o.querySelector("svg")).not.toBeNull();
  });

  it("ends the OONI description after the baseline when the z-score is null", async () => {
    const card = ooniCard();
    card.evidence.comparison = null;
    mockApi({ ooni: card });
    renderAt();
    await waitFor(() => expect(exhibit("ooni")).toHaveTextContent("3.0%"));
    const d = exhibit("ooni").querySelector(".d")?.textContent ?? "";
    expect(d.endsWith("over its own 12-week baseline.")).toBe(true);
    expect(d).not.toMatch(/z-score/);
  });

  it("shows No data and the API's provenance note verbatim when has_data is false", async () => {
    const note = "The snapshot has no OONI rows for the week starting 2022-08-06.";
    mockApi({ ooni: noData("ooni", note) });
    renderAt();
    await waitFor(() => expect(exhibit("ooni")).toHaveTextContent("No data"));
    expect(exhibit("ooni").querySelector(".d")?.textContent).toBe(note);
    expect(exhibit("ooni").querySelector("svg")).toBeNull();
  });

  it("leaves the other two cards and the page working when one request fails", async () => {
    mockApi({ ooni: new Error("boom") });
    renderAt();
    await waitFor(() => expect(exhibit("ooni")).toHaveTextContent("This exhibit could not be loaded."));
    await waitFor(() => expect(exhibit("acled")).toHaveTextContent("167"));
    expect(exhibit("google_transparency")).toHaveTextContent("9");
    expect(screen.getByRole("heading", { level: 1 })).toBeInTheDocument();
    expect(screen.getAllByText("This exhibit could not be loaded.")).toHaveLength(1);
  });
});

describe("sources, data and pager", () => {
  it("groups citations by URL in first-appearance order, as safe links", async () => {
    mockApi();
    const { container } = renderAt();
    await screen.findByRole("heading", { level: 1 });
    const items = [...container.querySelectorAll("ol.sources li")];
    expect(items).toHaveLength(2);
    expect(items[0]).toHaveTextContent("Cite A");
    expect(items[0]).toHaveTextContent("Supports: “Claim one”; “Claim three”");
    const a = items[0]?.querySelector("a");
    expect(a?.getAttribute("href")).toBe("https://a.example/");
    expect(a?.getAttribute("target")).toBe("_blank");
    expect(a?.getAttribute("rel")).toBe("noopener noreferrer");
    expect(items[1]).toHaveTextContent("Cite B");
  });

  it("omits the citations section when there are none", async () => {
    mockApi({ finding: baseFinding({ citations: [] }) });
    renderAt();
    await screen.findByRole("heading", { level: 1 });
    expect(screen.queryByText("Sources for the events and rules named above")).toBeNull();
  });

  it("lists the data sources with a link only where there is a URL", async () => {
    mockApi();
    renderAt();
    const h = await screen.findByRole("heading", { level: 2, name: "Data" });
    const section = h.closest("section") as HTMLElement;
    expect(within(section).getByRole("link", { name: "ACLED source name" })).toHaveAttribute("href", "https://acled.example/");
    expect(within(section).getByText("OONI source name").closest("a")).toBeNull();
    expect(section).toHaveTextContent("ACLED provenance text.");
    expect(section).toHaveTextContent("OONI provenance text.");
  });

  it("links to the next finding on position 1, with no previous link", async () => {
    mockApi();
    renderAt("finance-bill-2024");
    const nav = await screen.findByRole("navigation", { name: "Findings" });
    expect(within(nav).queryByText(/←/)).toBeNull();
    expect(within(nav).getByRole("link", { name: "Second title →" })).toHaveAttribute("href", "/findings/june-july-2025");
  });

  it("links both ways in the middle and has no next on the last", async () => {
    mockApi({ finding: baseFinding({ slug: "june-july-2025", position: 2 }) });
    const { unmount } = renderAt("june-july-2025");
    let nav = await screen.findByRole("navigation", { name: "Findings" });
    expect(within(nav).getByRole("link", { name: "← First title" })).toHaveAttribute("href", "/findings/finance-bill-2024");
    expect(within(nav).getByRole("link", { name: "Third title →" })).toHaveAttribute("href", "/findings/july-2023");
    unmount();
    vi.restoreAllMocks();
    mockApi({ finding: baseFinding({ slug: "july-2023", position: 3 }) });
    renderAt("july-2023");
    nav = await screen.findByRole("navigation", { name: "Findings" });
    expect(within(nav).getByRole("link", { name: "← Second title" })).toBeInTheDocument();
    expect(within(nav).queryByText(/→/)).toBeNull();
  });

  it("hides only the pager when the list fails", async () => {
    mockApi({ list: new Error("down") });
    renderAt();
    await screen.findByRole("heading", { level: 1 });
    expect(screen.queryByRole("navigation", { name: "Findings" })).toBeNull();
    expect(screen.getAllByRole("heading", { level: 1 })).toHaveLength(1);
  });
});

describe("errors", () => {
  it("shows the not-found message with links on a 404", async () => {
    mockApi({ finding: new client.ApiError(404, "/api/findings/nope") });
    renderAt("nope");
    expect(await screen.findByText("No finding with this name.")).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Back to the ledger" })).toHaveAttribute("href", "/");
    expect(screen.getByRole("link", { name: "All findings" })).toHaveAttribute("href", "/findings");
  });

  it("shows a retry for any other error, and loads on retry", async () => {
    mockApi({ finding: new client.ApiError(500, "/api/findings/x") });
    const user = userEvent.setup();
    renderAt();
    expect(await screen.findByText("This finding could not be loaded.")).toBeInTheDocument();
    vi.restoreAllMocks();
    mockApi();
    await user.click(screen.getByRole("button", { name: "Try again" }));
    expect(await screen.findByText("Protest and suppression both SEVERE")).toBeInTheDocument();
  });
});

describe("source scan", () => {
  it("has no dangerouslySetInnerHTML in the finding page or its components", () => {
    const dir = join(__dirname, "..", "components", "finding");
    const paths = [join(__dirname, "Finding.tsx"), ...readdirSync(dir).map((n) => join(dir, n))];
    const offenders = paths.filter((p) => !p.endsWith(".test.tsx") && readFileSync(p, "utf8").includes("dangerouslySetInnerHTML"));
    expect(offenders).toEqual([]);
  });
});
