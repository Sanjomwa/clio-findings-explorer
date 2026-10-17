// Pure week and date helpers. All date maths is in UTC: "YYYY-MM-DD" is parsed as UTC
// midnight, never local time.
import type { components } from "../api/schema";

export type RegimeState = components["schemas"]["RegimeState"];
export type ConfidenceLevel = components["schemas"]["ConfidenceLevel"];

export const DAY_MS = 86_400_000;
export const GRID_COLUMNS = 53;

const MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"];
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

/** One-letter state codes; they match the `--st-*` colour tokens. */
export const STATE_CODE: Record<RegimeState, string> = {
  STABLE: "S",
  MOBILISATION: "M",
  CONTESTATION: "T",
  REPRESSION: "R",
  CONFLICT: "F",
  ESCALATION: "E",
  CRISIS: "C",
};

/** Legend and colour order after "insufficient data". */
export const STATE_ORDER: RegimeState[] = [
  "STABLE",
  "MOBILISATION",
  "CONTESTATION",
  "REPRESSION",
  "CONFLICT",
  "ESCALATION",
  "CRISIS",
];

export function parseUtc(iso: string): Date {
  const [y, m, d] = iso.split("-").map(Number);
  return new Date(Date.UTC(y ?? 0, (m ?? 1) - 1, d ?? 1));
}

export function addDays(d: Date, n: number): Date {
  return new Date(d.getTime() + n * DAY_MS);
}

/** Days since 1 January of the date's own year (1 Jan is day 0). */
export function dayOfYear(d: Date): number {
  return Math.round((d.getTime() - Date.UTC(d.getUTCFullYear(), 0, 1)) / DAY_MS);
}

/** Grid column 0 to 52. */
export function gridColumn(iso: string): number {
  return Math.min(GRID_COLUMNS - 1, Math.floor(dayOfYear(parseUtc(iso)) / 7));
}

export function gridRow(iso: string, firstYear: number): number {
  return parseUtc(iso).getUTCFullYear() - firstYear;
}

/** "11 Jan 1997" (short) or "11 January 1997" (long). */
export function formatDate(d: Date, long = false): string {
  return `${d.getUTCDate()} ${(long ? MONTHS_LONG : MONTHS)[d.getUTCMonth()]} ${d.getUTCFullYear()}`;
}

/** Saturday-to-Friday range: "22–28 Jun 2024", or the long form across a month or year. */
export function range(iso: string): string {
  const a = parseUtc(iso);
  const b = addDays(a, 6);
  if (a.getUTCMonth() === b.getUTCMonth() && a.getUTCFullYear() === b.getUTCFullYear()) {
    return `${a.getUTCDate()}–${b.getUTCDate()} ${MONTHS[b.getUTCMonth()]} ${b.getUTCFullYear()}`;
  }
  return `${formatDate(a)} – ${formatDate(b)}`;
}

/** Record id, e.g. KE·2024·W25. */
export function recId(iso: string, country = "KE"): string {
  const d = parseUtc(iso);
  const n = Math.floor(dayOfYear(d) / 7) + 1;
  return `${country}·${d.getUTCFullYear()}·W${String(n).padStart(2, "0")}`;
}

/** "Jun 2024" from the week's start date. */
export function monthYear(iso: string): string {
  const d = parseUtc(iso);
  return `${MONTHS[d.getUTCMonth()]} ${d.getUTCFullYear()}`;
}

/** "22 June 2024". */
export function longDate(iso: string): string {
  return formatDate(parseUtc(iso), true);
}

/** A STABLE week with INSUFFICIENT_DATA confidence is unscored. Other states keep their colour. */
export function isInsufficient(week: { regime_state: RegimeState; confidence_level: ConfidenceLevel }): boolean {
  return week.regime_state === "STABLE" && week.confidence_level === "INSUFFICIENT_DATA";
}

/** Key into the legend and the colour tokens: "I" for insufficient data, else the state code. */
export function cellKey(week: { regime_state: RegimeState; confidence_level: ConfidenceLevel }): string {
  return isInsufficient(week) ? "I" : STATE_CODE[week.regime_state];
}

export function stateLabel(week: { regime_state: RegimeState; confidence_level: ConfidenceLevel }): string {
  return isInsufficient(week) ? "STABLE (insufficient data)" : week.regime_state;
}

/** The tooltip's confidence line, or null when the state line already says it. */
export function confidenceLine(week: { regime_state: RegimeState; confidence_level: ConfidenceLevel }): string | null {
  if (isInsufficient(week)) return null;
  switch (week.confidence_level) {
    case "HIGH":
      return "High confidence";
    case "MEDIUM":
      return "Medium confidence";
    case "LOW":
      return "Low confidence";
    default:
      return "Insufficient data";
  }
}

const WORDS = ["zero", "one", "two", "three", "four", "five", "six", "seven", "eight", "nine"];

/** Spell out 0 to 9; larger numbers stay as digits. */
export function numberWord(n: number): string {
  return Number.isInteger(n) && n >= 0 && n < WORDS.length ? (WORDS[n] as string) : String(n);
}

export function capitalise(s: string): string {
  return s.charAt(0).toUpperCase() + s.slice(1);
}

const DATE_PREFIX = /^\d[^:]*\d{4}:\s*/;

/** True when the title starts with a date prefix such as "22–28 June 2024: ". */
export function hasDatePrefix(title: string): boolean {
  return DATE_PREFIX.test(title);
}

export function titleNoDate(title: string): string {
  return hasDatePrefix(title) ? capitalise(title.replace(DATE_PREFIX, "")) : title;
}
