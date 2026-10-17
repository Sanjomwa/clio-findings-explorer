import { useNavigate } from "react-router-dom";
import type { TimelineResponse } from "../../api/client";
import { monthLabels } from "../../lib/finding";
import { addDays, cellKey, formatDate, parseUtc, stateLabel } from "../../lib/weeks";

interface Props {
  weeks: TimelineResponse["weeks"];
  anchor: string;
  slug: string;
}

const W = 600;

export default function ContextStrip({ weeks, anchor, slug }: Props) {
  const navigate = useNavigate();
  if (weeks.length === 0) return null;
  const cw = W / weeks.length;
  const first = weeks[0]!;
  const last = weeks[weeks.length - 1]!;
  const anchorWeek = weeks.find((w) => w.week_start_date === anchor);
  const label =
    `Weeks from ${formatDate(parseUtc(first.week_start_date))} to ${formatDate(addDays(parseUtc(last.week_start_date), 6))}, coloured by state` +
    (anchorWeek ? `; the finding's week is ${stateLabel(anchorWeek)}` : "");

  const months = monthLabels(
    weeks.map((w) => w.week_start_date),
    cw,
  );
  return (
    <svg viewBox="0 0 600 56" role="img" aria-label={label}>
      {weeks.map((w, k) => {
        const x = k * cw;
        const target = w.finding_slug && w.finding_slug !== slug ? w.finding_slug : null;
        const month = months.get(k);
        return (
          <g key={w.week_start_date}>
            <rect
              x={x + 0.5}
              y="8"
              width={cw - 1.5}
              height="26"
              fill={`var(--st-${cellKey(w)})`}
              data-week={w.week_start_date}
              style={target ? { cursor: "pointer" } : undefined}
              onClick={target ? () => navigate(`/findings/${target}`) : undefined}
            />
            {w.week_start_date === anchor && (
              <rect
                x={x - 1}
                y="5"
                width={cw + 1}
                height="32"
                fill="none"
                stroke="var(--ink)"
                strokeWidth="2"
                pointerEvents="none"
              />
            )}
            {month && (
              <text x={x + 1} y="50" fontSize="10" fontFamily="Spline Sans Mono, monospace" fill="var(--soft)">
                {month}
              </text>
            )}
          </g>
        );
      })}
    </svg>
  );
}
