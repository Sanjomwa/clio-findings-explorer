// Pure helpers for the finding page. No React, no network.
import type { components } from "../api/schema";
import { addDays, capitalise, parseUtc, type RegimeState } from "./weeks";

type FamilyBand = components["schemas"]["FamilyBand"];
type Citation = components["schemas"]["Citation"];

const MONTHS_LONG = [
  "January",
  "February",
  "March",
  "April",
  "May",
  "June",
  "July",
  "August",
  "September",
  "October",
  "November",
  "December",
];

/** Split plain text into paragraphs on blank lines. Empty paragraphs are dropped. */
export function paragraphs(text: string): string[] {
  return text
    .split(/\n\s*\n/)
    .map((p) => p.trim())
    .filter((p) => p.length > 0);
}

/** Split the teaser around the key phrase. Null when there is no phrase or it is not an exact substring. */
export function splitKeyPhrase(
  teaser: string,
  keyPhrase: string | null | undefined,
): { before: string; mark: string; after: string } | null {
  if (!keyPhrase) return null;
  const i = teaser.indexOf(keyPhrase);
  if (i < 0) return null;
  return { before: teaser.slice(0, i), mark: keyPhrase, after: teaser.slice(i + keyPhrase.length) };
}

export interface CitationGroup {
  url: string;
  citation: string;
  claims: string[];
}

/** Group citations by URL in first-appearance order. Repeated claims are listed once. */
export function groupCitations(citations: Citation[]): CitationGroup[] {
  const groups = new Map<string, CitationGroup>();
  for (const c of citations) {
    let g = groups.get(c.url);
    if (!g) {
      g = { url: c.url, citation: c.citation, claims: [] };
      groups.set(c.url, g);
    }
    if (!g.claims.includes(c.claim)) g.claims.push(c.claim);
  }
  return [...groups.values()];
}

/** "January – June 2024" from a half-year's start and end dates (same year), else "Jan 2024 – Jun 2025" style long months. */
export function halfYearLabel(startIso: string, endIso: string): string {
  const a = parseUtc(startIso);
  const b = parseUtc(endIso);
  const am = MONTHS_LONG[a.getUTCMonth()];
  const bm = MONTHS_LONG[b.getUTCMonth()];
  if (a.getUTCFullYear() === b.getUTCFullYear()) return `${am} – ${bm} ${b.getUTCFullYear()}`;
  return `${am} ${a.getUTCFullYear()} – ${bm} ${b.getUTCFullYear()}`;
}

/** The context strip's request range: 91 days (13 weeks) either side of the anchor week. */
export function contextRange(weekStartIso: string): { from: string; to: string } {
  const d = parseUtc(weekStartIso);
  return { from: isoDate(addDays(d, -13 * 7)), to: isoDate(addDays(d, 13 * 7)) };
}

export function isoDate(d: Date): string {
  return d.toISOString().slice(0, 10);
}

/** One-letter band code; it matches the `--b-*` colour tokens. */
export function bandCode(band: FamilyBand): "n" | "e" | "s" | "u" {
  switch (band) {
    case "NORMAL":
      return "n";
    case "ELEVATED":
      return "e";
    case "SEVERE":
      return "s";
    default:
      return "u";
  }
}

export const STABLE_SENTENCE =
  "STABLE: no regime rule was met this week. Bands can still be raised; a first raised week is held at STABLE until a second consecutive one follows.";

/** The spec's §4.1 sentence for a STABLE week with usable data, else null. */
export function stableSentence(week: { regime_state: RegimeState; confidence_level: string }): string | null {
  return week.regime_state === "STABLE" && week.confidence_level !== "INSUFFICIENT_DATA" ? STABLE_SENTENCE : null;
}

/** The spec's §4.1 pre-transition sentence, or null when the flag is not set. */
export function preTransitionSentence(target: RegimeState | null | undefined): string | null {
  return target ? `Raised: would have entered ${target} if the next week also qualified.` : null;
}

/** "High confidence", or null for an unscored week (the state label already says it). */
export function confidenceText(week: { regime_state: RegimeState; confidence_level: string }): string | null {
  switch (week.confidence_level) {
    case "HIGH":
      return "High confidence";
    case "MEDIUM":
      return "Medium confidence";
    case "LOW":
      return "Low confidence";
    default:
      return null;
  }
}

export interface PeriodInput {
  period_grain: "week" | "month" | "half_year" | "other";
  period_start: string | null;
  period_end: string | null;
}

/** "This week" for weekly cards, a half-year label for half-year cards, else the date span. */
export function periodLabel(card: PeriodInput): string {
  if (card.period_grain === "week") return "This week";
  if (card.period_start && card.period_end) return halfYearLabel(card.period_start, card.period_end);
  return "";
}

const MONTHS_SHORT = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"];

/**
 * Month labels for the context strip, keyed by week index. A label is placed at the first week of a new
 * month, and only if it is at least `minGap` pixels after the previous label. The year is added at the
 * first label and in January.
 */
export function monthLabels(weekStarts: string[], cellWidth: number, minGap = 44): Map<number, string> {
  const labels = new Map<number, string>();
  let lastMonth = -1;
  let lastX = -99;
  weekStarts.forEach((iso, k) => {
    const d = parseUtc(iso);
    const x = k * cellWidth;
    if (d.getUTCMonth() !== lastMonth && (k === 0 || x - lastX >= minGap)) {
      lastMonth = d.getUTCMonth();
      lastX = x;
      labels.set(k, `${MONTHS_SHORT[lastMonth]}${lastMonth === 0 || k === 0 ? ` ${d.getUTCFullYear()}` : ""}`);
    }
  });
  return labels;
}

const TEST_NAMES: Record<string, string> = {
  whatsapp: "WhatsApp",
  signal: "Signal",
  telegram: "Telegram",
  facebook_messenger: "Facebook Messenger",
  web_connectivity: "Web Connectivity",
};

/** Display name for an OONI test; unknown names are capitalised as they are. */
export function ooniTestName(name: string): string {
  return TEST_NAMES[name] ?? capitalise(name);
}
