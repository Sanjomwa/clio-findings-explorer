import { Link } from "react-router-dom";
import type { FindingList } from "../api/client";
import { range, recId, titleNoDate } from "../lib/weeks";

export default function FindingRegister({ findings }: { findings: FindingList["findings"] }) {
  return (
    <ol className="register">
      {findings.map((f) => (
        <li key={f.slug}>
          <Link to={`/findings/${f.slug}`}>
            <div>
              <div className="rec">{recId(f.week_start_date, f.country_iso)}</div>
              <div className="rec rec-second">{range(f.week_start_date)}</div>
            </div>
            <div className="reg-main">
              <div className="t">{titleNoDate(f.title)}</div>
              <div className="s">{f.teaser}</div>
            </div>
            <div className="side">
              <span className="lbl sm">{f.regime_state}</span>
            </div>
          </Link>
        </li>
      ))}
    </ol>
  );
}
