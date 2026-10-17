import type { FindingRecord } from "../../api/client";
import { groupCitations } from "../../lib/finding";

export function Citations({ citations }: { citations: FindingRecord["citations"] }) {
  const groups = groupCitations(citations);
  if (groups.length === 0) return null;
  return (
    <section className="block">
      <h2>Sources for the events and rules named above</h2>
      <ol className="sources">
        {groups.map((g) => (
          <li key={g.url}>
            <a href={g.url} target="_blank" rel="noopener noreferrer">
              {g.citation}
            </a>
            <span className="c">Supports: {g.claims.map((c) => `“${c}”`).join("; ")}</span>
          </li>
        ))}
      </ol>
    </section>
  );
}

export function DataSources({ sources }: { sources: FindingRecord["sources"] }) {
  if (sources.length === 0) return null;
  return (
    <section className="block data-sources">
      <h2>Data</h2>
      <ul className="rec data-list">
        {sources.map((s) => (
          <li key={s.source}>
            <b>
              {s.url ? (
                <a href={s.url} target="_blank" rel="noopener noreferrer">
                  {s.name}
                </a>
              ) : (
                s.name
              )}
            </b>
            <span>{s.provenance_note}</span>
          </li>
        ))}
      </ul>
    </section>
  );
}
