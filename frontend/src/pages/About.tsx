import { useEffect } from "react";
import { getMethodology, type Methodology as MethodologyData } from "../api/client";
import { useLoad } from "../lib/useLoad";
import { formatDate } from "../lib/weeks";

const REVIEWS = "https://github.com/Sanjomwa/clio-findings-explorer/tree/main/docs/reviews";

const exportTime = (iso: string) => `${formatDate(new Date(iso))} ${iso.slice(11, 16)} UTC`;

function Snapshot({ manifest }: { manifest: MethodologyData["manifest"] }) {
  return (
    <section className="block">
      <h2>The snapshot</h2>
      <p className="prose">
        Version {manifest.version}, exported {formatDate(new Date(manifest.exported_at))}. Each file below was produced
        by the SQL shown.
      </p>
      <ul className="snapshot-files">
        {manifest.tables.map((t) => (
          <li key={t.file}>
            <div className="snapshot-row">
              <span className="snapshot-file">{t.file}</span>
              <span className="rec">{t.source_table}</span>
              <span className="rec">{t.row_count.toLocaleString("en")} rows</span>
              <span className="rec">Exported {exportTime(t.exported_at)}</span>
            </div>
            <details>
              <summary>SQL</summary>
              <pre>{t.sql}</pre>
            </details>
          </li>
        ))}
      </ul>
    </section>
  );
}

export default function About() {
  const [state] = useLoad<MethodologyData>(getMethodology);
  useEffect(() => {
    document.title = "About · CLIO Findings Explorer";
  }, []);

  return (
    <div>
      <div className="rec">About</div>
      <h1 className="page-h1">An archive of checked findings</h1>
      <p className="dek">
        CLIO Findings Explorer presents a small set of curated findings about civil-liberties pressure in Kenya. Each
        finding is one week that CLIO classified, shown with its evidence and with what that evidence does not
        establish.
      </p>
      <section className="block prose">
        <h2>Why it exists</h2>
        <p>
          When a government restricts civil liberties, the evidence arrives in pieces that don't line up. Conflict-event
          records describe what happened on the street, network measurements describe what happened to internet access,
          and transparency reports describe what content governments asked to have removed. Each has a different grain,
          collection method and reliability.
        </p>
        <p>
          Someone asking whether a week saw coordinated pressure, and how sure we can be, usually has two poor options:
          correlate raw datasets by hand, or read a summary with no traceable evidence under it. This site puts the
          classification, the evidence and its limits on one page, and every number traces back to the query that
          produced it.
        </p>
      </section>
      <section className="block prose">
        <h2>How a finding is made</h2>
        <ol className="steps">
          <li>
            <b>A fixed snapshot.</b> CLIO's output for Kenya was exported once, by a person, to the repository. A
            manifest records the source table, the exact SQL, the row count, a checksum and the export time for every
            file. Synthetic data is refused at export. The site never queries CLIO at runtime.
          </li>
          <li>
            <b>A drafted week.</b> A person picks a week and drafts its title, summary and caveats from the snapshot,
            citing a public source for every real-world event and every statement about CLIO's rules.
          </li>
          <li>
            <b>A claim-by-claim review.</b> An AI evidence reviewer checks every factual assertion against the snapshot.
            Figures must match the data, events and rules must carry a cited source, and causal wording is rejected. Any
            failure stops publication. The{" "}
            <a href={REVIEWS} target="_blank" rel="noopener">
              verdict logs
            </a>{" "}
            are public.
          </li>
          <li>
            <b>Published with its limits.</b> A finding cannot be published without at least one caveat: the database refuses
            it, and the loader checks it when content is loaded.
          </li>
        </ol>
      </section>
      <section className="block">
        <h2>The three sources</h2>
        <dl className="defs">
          <div>
            <dt>ACLED</dt>
            <dd>
              Armed Conflict Location &amp; Event Data. Conflict and protest events, aggregated by CLIO into weeks
              running Saturday to Friday. It is the classifier's own input, so it never independently confirms a label.
              Used under ACLED's terms for non-commercial use, with attribution.
            </dd>
          </div>
          <div>
            <dt>OONI</dt>
            <dd>
              Open Observatory of Network Interference. Volunteer network measurements of whether specific apps and
              sites can be reached. The snapshot's weekly signals cover 27 May 2023 to 28 June 2025. Licensed CC BY-NC-SA
              4.0.
            </dd>
          </div>
          <div>
            <dt>Google Transparency Report</dt>
            <dd>
              Government requests to remove content, reported per half-year, never per week. The snapshot's data begins
              with July to December 2012. Reuse terms not determined.
            </dd>
          </div>
        </dl>
      </section>
      {state.kind === "ready" && <Snapshot manifest={state.data.manifest} />}
      <section className="block prose">
        <h2>What it is not</h2>
        <p>
          It is not a live monitor: the snapshot is fixed, and every page shows its version. It does not say why
          anything happened. Two things in the same week are reported as falling in the same week, and nothing more.
        </p>
      </section>
    </div>
  );
}
