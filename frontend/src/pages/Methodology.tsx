import { useEffect, type ReactNode } from "react";
import { Link } from "react-router-dom";
import { getMethodology, type Methodology as MethodologyData } from "../api/client";
import { useLoad } from "../lib/useLoad";
import { capitalise } from "../lib/weeks";

const CLIO_CODE = "https://github.com/Sanjomwa/Civil-Liberties-Intelligence-Observatory";

const confidenceLabel = (level: string) =>
  level === "INSUFFICIENT_DATA" ? "Insufficient data" : capitalise(level.toLowerCase());

function Section({ title, rows }: { title: string; rows: Array<{ key: string; term: ReactNode; definition: string }> }) {
  if (rows.length === 0) return null;
  return (
    <section className="block">
      <h2>{title}</h2>
      <dl className="defs">
        {rows.map((r) => (
          <div key={r.key}>
            <dt>{r.term}</dt>
            <dd>{r.definition}</dd>
          </div>
        ))}
      </dl>
    </section>
  );
}

export default function Methodology() {
  const [state, retry] = useLoad<MethodologyData>(getMethodology);
  useEffect(() => {
    document.title = "How CLIO classifies a week · CLIO Findings Explorer";
  }, []);

  const m = state.kind === "ready" ? state.data : null;

  return (
    <div>
      <div className="rec">Methodology</div>
      <h1 className="page-h1">How CLIO classifies a week</h1>
      <p className="dek">
        CLIO, the Civil Liberties Intelligence Observatory, scores three pressure families from ACLED conflict events
        each week, compares each with its own previous 12 weeks, and assigns one of seven states. The definitions below
        were written from{" "}
        <a href={CLIO_CODE} target="_blank" rel="noopener">
          CLIO's production code
        </a>{" "}
        and are kept in this repository as content/methodology.yaml. For the sources themselves, see{" "}
        <Link to="/about">About</Link>.
      </p>
      {state.kind === "loading" && <div className="register-placeholder" aria-busy="true" />}
      {state.kind === "error" && (
        <>
          <p role="alert">The methodology could not be loaded.</p>
          <button type="button" className="btn" onClick={retry}>
            Try again
          </button>
        </>
      )}
      {m && (
        <>
          <Section
            title="What each family counts"
            rows={m.families.map((x) => ({ key: x.family, term: capitalise(x.family), definition: x.definition }))}
          />
          <Section
            title="Regime states"
            rows={m.regime_states.map((x) => ({
              key: x.state,
              term: <span className="lbl sm">{x.state}</span>,
              definition: x.definition,
            }))}
          />
          <Section
            title="Confidence levels"
            rows={m.confidence_levels.map((x) => ({
              key: x.level,
              term: confidenceLabel(x.level),
              definition: x.definition,
            }))}
          />
          <Section
            title="Family bands"
            rows={m.family_bands.map((x) => ({ key: x.band, term: x.band, definition: x.definition }))}
          />
          <p className="rec snapshot-line">Snapshot {m.snapshot_version}.</p>
        </>
      )}
    </div>
  );
}
