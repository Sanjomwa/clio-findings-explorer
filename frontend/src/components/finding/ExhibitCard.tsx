import type { AcledEvidence } from "../../api/client";
import { ooniTestName, periodLabel } from "../../lib/finding";
import { range } from "../../lib/weeks";

// The three evidence operations share one response schema.
type Card = AcledEvidence;

const NAMES = { acled: "ACLED", ooni: "OONI", google_transparency: "Google Transparency Report" } as const;
const SHORT = { acled: "A · ACLED", ooni: "B · OONI", google_transparency: "C · Google" } as const;

export type ExhibitSource = keyof typeof NAMES;

export const ACLED_NOTE = "ACLED is the classifier's own input, so this is not independent corroboration of the label.";
export const GOOGLE_NOTE = "A half-year total with no comparison figure. It does not show what happened in this week.";

function CompareBar({ value, baseline }: { value: number; baseline: number }) {
  const max = Math.max(value, baseline) * 1.08 || 1;
  const X = (v: number) => (v / max) * 300;
  return (
    <svg viewBox="0 0 300 30" preserveAspectRatio="none" aria-hidden="true">
      <rect x="0" y="9" width={X(value)} height="12" fill="var(--ink)" />
      <line x1={X(baseline)} y1="2" x2={X(baseline)} y2="28" stroke="var(--hl)" strokeWidth="3" />
      <line x1={X(baseline)} y1="2" x2={X(baseline)} y2="28" stroke="var(--soft)" strokeWidth="1" />
    </svg>
  );
}

function Shell({
  source,
  period,
  children,
  prov,
}: {
  source: ExhibitSource;
  period: string;
  children: React.ReactNode;
  prov: string;
}) {
  return (
    <div className="ex" data-source={source}>
      <div className="h">
        <span className="rec">Exhibit {SHORT[source]}</span>
        <span className="rec">{period}</span>
      </div>
      {children}
      <div className="prov rec">{prov}</div>
    </div>
  );
}

export function ExhibitError({ source }: { source: ExhibitSource }) {
  return (
    <Shell source={source} period="" prov={`${NAMES[source]}`}>
      <div className="d" role="alert">
        This exhibit could not be loaded.
      </div>
    </Shell>
  );
}

export function ExhibitLoading({ source }: { source: ExhibitSource }) {
  return (
    <Shell source={source} period="" prov={`${NAMES[source]}`}>
      <div className="ex-placeholder" aria-busy="true" aria-label="Loading this exhibit" />
    </Shell>
  );
}

function describe(card: Card["evidence"], value: string | null): string {
  const cmp = card.comparison;
  return cmp ? `${card.headline_metric}. ${cmp.label}: ${value ?? cmp.value}` : card.headline_metric;
}

const pct = (v: number) => `${(v * 100).toFixed(1)}%`;

export default function ExhibitCard({ response, weekStart }: { response: Card; weekStart: string }) {
  const card = response.evidence;
  const source = card.source;
  const period = periodLabel(card);
  const provPeriod = card.period_grain === "week" ? `week ${range(weekStart)}` : period;
  const prov = `${NAMES[source]} · ${provPeriod} · snapshot ${response.snapshot_version}`;

  if (!card.has_data) {
    return (
      <Shell source={source} period={period} prov={`${NAMES[source]} · snapshot ${response.snapshot_version}`}>
        <div className="num none">No data</div>
        <div className="d">{card.provenance_note}</div>
      </Shell>
    );
  }

  const s = card.supporting;

  if (s?.kind === "acled") {
    const events = Number(card.metric_value);
    return (
      <Shell source={source} period={period} prov={prov}>
        <div className="num">{card.metric_value}</div>
        <div className="d">{describe(card, null)}</div>
        {card.comparison && <CompareBar value={events} baseline={card.comparison.value} />}
        {s.classifier_input && <div className="note">{ACLED_NOTE}</div>}
      </Shell>
    );
  }

  if (s?.kind === "ooni") {
    const row = s.tests.find((t) => t.test_name === s.top_test);
    const top =
      row && row.anomalous_rate !== null && row.anomalous_baseline_rate_12w !== null
        ? { ...row, rate: row.anomalous_rate, baseline: row.anomalous_baseline_rate_12w }
        : null;
    const z = card.comparison?.value;
    const rate = typeof card.metric_value === "number" ? card.metric_value : top?.rate;
    const counts =
      top && top.anomalous_count !== null && top.anomalous_total_scored !== null
        ? ` (${top.anomalous_count} of ${top.anomalous_total_scored} measurements)`
        : "";
    const text = top
      ? `${ooniTestName(top.test_name)}'s anomaly rate this week${counts}, against ${pct(top.baseline)} over its own 12-week baseline.${z === undefined ? "" : ` z-score ${z.toFixed(2)}.`}`
      : card.headline_metric;
    return (
      <Shell source={source} period={period} prov={prov}>
        {rate === undefined ? <div className="num none">No number</div> : <div className="num">{pct(rate)}</div>}
        <div className="d">{text}</div>
        {top && <CompareBar value={top.rate} baseline={top.baseline} />}
        <div className="note">{s.note}</div>
      </Shell>
    );
  }

  return (
    <Shell source={source} period={period} prov={prov}>
      <div className="num">{card.metric_value}</div>
      <div className="d">{describe(card, null)}</div>
      <div className="note">{GOOGLE_NOTE}</div>
    </Shell>
  );
}
