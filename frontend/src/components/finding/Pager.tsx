import { Link } from "react-router-dom";
import type { FindingList } from "../../api/client";
import { titleNoDate } from "../../lib/weeks";

export default function Pager({ findings, slug }: { findings: FindingList["findings"]; slug: string }) {
  const i = findings.findIndex((f) => f.slug === slug);
  if (i < 0) return null;
  const prev = findings[i - 1];
  const next = findings[i + 1];
  return (
    <nav className="pager" aria-label="Findings">
      {prev ? <Link to={`/findings/${prev.slug}`}>← {titleNoDate(prev.title)}</Link> : <span />}
      {next ? (
        <Link to={`/findings/${next.slug}`} className="next">
          {titleNoDate(next.title)} →
        </Link>
      ) : (
        <span />
      )}
    </nav>
  );
}
