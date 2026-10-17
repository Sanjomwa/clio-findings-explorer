import { listFindings, getTimeline, type FindingList, type TimelineResponse } from "../api/client";
import FindingRegister from "../components/FindingRegister";
import LedgerGrid from "../components/LedgerGrid";
import { useLoad } from "../lib/useLoad";
import { STATE_ORDER, addDays, cellKey, STATE_CODE, capitalise, formatDate, numberWord, parseUtc } from "../lib/weeks";

const timelineFn = () => getTimeline();

function Legend({ weeks }: { weeks: TimelineResponse["weeks"] }) {
  const counts = new Map<string, number>();
  for (const w of weeks) counts.set(cellKey(w), (counts.get(cellKey(w)) ?? 0) + 1);
  const items: Array<{ key: string; label: string }> = [
    { key: "I", label: "Insufficient data" },
    ...STATE_ORDER.map((s) => ({ key: STATE_CODE[s], label: s })),
  ].filter((i) => counts.has(i.key));
  return (
    <div className="legend">
      {items.map((i) => (
        <span key={i.key}>
          <i style={{ background: `var(--st-${i.key})` }} aria-hidden="true" />
          {i.label} · {counts.get(i.key)}
        </span>
      ))}
      <span>
        <i className="legend-finding" aria-hidden="true" />
        Published finding
      </span>
    </div>
  );
}

export default function Ledger() {
  const [timeline, retryTimeline] = useLoad(timelineFn);
  const [findings] = useLoad<FindingList>(listFindings);

  const list = findings.kind === "ready" ? findings.data.findings : null;
  const count = list ? numberWord(list.length) : null;

  if (timeline.kind === "error") {
    return (
      <div>
        <h1>Kenya, one week at a time</h1>
        <p role="alert">The ledger could not be loaded.</p>
        <button type="button" className="btn" onClick={retryTimeline}>
          Try again
        </button>
      </div>
    );
  }

  const weeks = timeline.kind === "ready" ? timeline.data.weeks : null;
  const first = weeks?.[0];
  const last = weeks?.[weeks.length - 1];
  const record =
    first && last
      ? `Register of classified weeks · ${formatDate(parseUtc(first.week_start_date))} to ${formatDate(addDays(parseUtc(last.week_start_date), 6))}`
      : "Register of classified weeks";

  return (
    <div>
      <div className="rec">{record}</div>
      <h1 className="ledger-h1">Nearly thirty years of Kenya, one week at a time</h1>
      <p className="dek">
        Each cell is one week that CLIO classified from ACLED conflict events.{" "}
        <mark>Pale cells are weeks with too little data to judge</mark>: almost every week before 2008, and many after
        it.{count ? ` ${capitalise(count)} weeks are published findings, each checked claim by claim against the data.` : ""}
      </p>
      <div className="ledger-wrap">
        {weeks === null && <div className="ledger-placeholder" aria-busy="true" aria-label="Loading the ledger" />}
        {weeks !== null && weeks.length === 0 && <p>No classified weeks in this snapshot.</p>}
        {weeks !== null && weeks.length > 0 && (
          <>
            <div className="ledger-head">
              <span className="rec">
                One row per year · one cell per week · {weeks.length.toLocaleString("en")} weeks
              </span>
              <span className="rec">Hover a week · select a named week to open it</span>
            </div>
            <LedgerGrid weeks={weeks} findings={list} />
            <Legend weeks={weeks} />
          </>
        )}
      </div>
      <section className="block">
        <h2>{count ? `The ${count} findings` : "The findings"}</h2>
        {findings.kind === "loading" && <div className="register-placeholder" aria-busy="true" />}
        {findings.kind === "error" && <p role="alert">The findings list could not be loaded.</p>}
        {list && <FindingRegister findings={list} />}
      </section>
    </div>
  );
}
