import type { FindingRecord } from "../../api/client";
import { paragraphs } from "../../lib/finding";

const PREFIX = "Do not conclude";

export default function Limits({ caveats }: { caveats: FindingRecord["caveats"] }) {
  const limits = caveats.filter((c) => c.severity !== "do_not_conclude");
  const dnc = caveats.filter((c) => c.severity === "do_not_conclude");
  return (
    <aside className="limits" aria-label="What this does not establish">
      <h2>What this does not establish</h2>
      {limits.flatMap((c, i) => paragraphs(c.caveat_md).map((p, j) => <p key={`l${i}-${j}`}>{p}</p>))}
      {dnc.flatMap((c, i) =>
        paragraphs(c.caveat_md).map((p, j) => (
          <p className="dnc" key={`d${i}-${j}`}>
            {j === 0 && p.startsWith(PREFIX) ? (
              <>
                <b>{PREFIX}</b>
                {p.slice(PREFIX.length)}
              </>
            ) : (
              p
            )}
          </p>
        )),
      )}
    </aside>
  );
}
