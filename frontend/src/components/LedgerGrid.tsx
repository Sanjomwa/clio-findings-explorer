import { memo, useEffect, useMemo, useRef, useState, type MouseEvent } from "react";
import { useNavigate } from "react-router-dom";
import type { FindingList, TimelineResponse } from "../api/client";
import {
  GRID_COLUMNS,
  cellKey,
  confidenceLine,
  gridColumn,
  gridRow,
  longDate,
  monthYear,
  numberWord,
  parseUtc,
  range,
  stateLabel,
  titleNoDate,
} from "../lib/weeks";
import { LABEL_GUTTER, cellX, cellY, computeLayout, gridHeight, hitCell, labelYs, type Layout } from "../lib/ledgerLayout";

export type Week = TimelineResponse["weeks"][number];
export type Finding = FindingList["findings"][number];

const FALLBACK_WIDTH = 1000;
const TIP_WIDTH = 260;

interface CellLayerProps {
  weeks: Week[];
  layout: Layout;
  firstYear: number;
}

// The 1,523 cells. Memoised on (weeks, layout): pointer movement never re-renders them, and
// fills are CSS variables, so a theme switch needs no redraw.
const CellLayer = memo(function CellLayer({ weeks, layout, firstYear }: CellLayerProps) {
  return (
    <g>
      {weeks.map((w) => (
        <rect
          key={w.week_start_date}
          data-week={w.week_start_date}
          x={cellX(layout, gridColumn(w.week_start_date))}
          y={cellY(layout, gridRow(w.week_start_date, firstYear))}
          width={layout.cw - 1}
          height={layout.ch}
          fill={`var(--st-${cellKey(w)})`}
        />
      ))}
    </g>
  );
});

const YearLabels = memo(function YearLabels({ layout, firstYear }: { layout: Layout; firstYear: number }) {
  const years = Array.from({ length: layout.rows }, (_, i) => firstYear + i);
  return (
    <g className="ledger-years" aria-hidden="true">
      {years.map((y, i) =>
        i === 0 || y % 5 === 0 ? (
          <text key={y} x={0} y={cellY(layout, i) + layout.ch / 2 + 1} dominantBaseline="middle">
            {y}
          </text>
        ) : null,
      )}
    </g>
  );
});

interface Tip {
  week: Week;
  x: number;
  y: number;
}

interface Placed {
  finding: Finding;
  week: Week;
  col: number;
  row: number;
  labelY: number;
}

function useWidth(ref: React.RefObject<HTMLElement | null>): number {
  const [width, setWidth] = useState(0);
  useEffect(() => {
    const el = ref.current;
    if (!el) return;
    setWidth(Math.round(el.getBoundingClientRect().width));
    if (typeof ResizeObserver === "undefined") return;
    const ro = new ResizeObserver((entries) => {
      const w = entries[0]?.contentRect.width;
      if (w !== undefined) setWidth(Math.round(w));
    });
    ro.observe(el);
    return () => ro.disconnect();
  }, [ref]);
  return width > 0 ? width : FALLBACK_WIDTH;
}

export default function LedgerGrid({ weeks, findings }: { weeks: Week[]; findings: Finding[] | null }) {
  const navigate = useNavigate();
  const wrapRef = useRef<HTMLDivElement>(null);
  const width = useWidth(wrapRef);
  const [tip, setTip] = useState<Tip | null>(null);

  const firstYear = parseUtc(weeks[0]?.week_start_date ?? "1970-01-01").getUTCFullYear();
  const lastYear = parseUtc(weeks[weeks.length - 1]?.week_start_date ?? "1970-01-01").getUTCFullYear();
  const rows = lastYear - firstYear + 1;
  const layout = useMemo(() => computeLayout(width, rows), [width, rows]);

  const byCell = useMemo(() => {
    const m = new Map<number, Week>();
    for (const w of weeks) {
      m.set(gridRow(w.week_start_date, firstYear) * GRID_COLUMNS + gridColumn(w.week_start_date), w);
    }
    return m;
  }, [weeks, firstYear]);

  const placed = useMemo<Placed[]>(() => {
    if (!findings) return [];
    const byDate = new Map(weeks.map((w) => [w.week_start_date, w]));
    const found = findings
      .map((f) => ({ finding: f, week: byDate.get(f.week_start_date) }))
      .filter((p): p is { finding: Finding; week: Week } => p.week !== undefined)
      .sort((a, b) => a.week.week_start_date.localeCompare(b.week.week_start_date));
    const rowsOf = found.map((p) => gridRow(p.week.week_start_date, firstYear));
    const ys = labelYs(layout, rowsOf);
    return found.map((p, i) => ({
      ...p,
      col: gridColumn(p.week.week_start_date),
      row: rowsOf[i] as number,
      labelY: ys[i] as number,
    }));
  }, [findings, weeks, firstYear, layout]);

  const slugs = useMemo(() => new Set(placed.map((p) => p.finding.slug)), [placed]);
  const labelX = LABEL_GUTTER + GRID_COLUMNS * layout.cw + 16;
  const height = gridHeight(layout, placed.length ? (placed[placed.length - 1] as Placed).labelY : null);

  function place(x: number): number {
    return Math.max(0, x + 14 + TIP_WIDTH > layout.width ? x - TIP_WIDTH - 10 : x + 14);
  }

  function onMove(e: MouseEvent<SVGSVGElement>) {
    const r = e.currentTarget.getBoundingClientRect();
    const x = e.clientX - r.left;
    const y = e.clientY - r.top;
    let week: Week | undefined;
    if (layout.showLabels) {
      const hit = placed.find((p) => x >= labelX - 4 && Math.abs(y - p.labelY) <= 8);
      if (hit) week = hit.week;
    }
    if (!week) {
      const c = hitCell(layout, x, y);
      if (c) week = byCell.get(c.row * GRID_COLUMNS + c.col);
    }
    if (!week) {
      setTip(null);
      return;
    }
    setTip({ week, x: place(x), y: y + 14 });
  }

  const open = (slug: string) => navigate(`/findings/${slug}`);
  const tipConf = tip ? confidenceLine(tip.week) : null;

  return (
    <div className="ledger-svg-wrap" ref={wrapRef}>
      <svg
        className="ledger-svg"
        role="img"
        aria-label={`Ledger of ${weeks.length.toLocaleString("en")} classified weeks from ${firstYear} to ${lastYear}. ${
          findings ? `The ${numberWord(findings.length)} findings are listed below.` : "The findings could not be loaded."
        }`}
        width={layout.width}
        height={height}
        viewBox={`0 0 ${layout.width} ${height}`}
        onMouseMove={onMove}
        onMouseLeave={() => setTip(null)}
      >
        <YearLabels layout={layout} firstYear={firstYear} />
        <CellLayer weeks={weeks} layout={layout} firstYear={firstYear} />
        {placed.map((p) => {
          const x = cellX(layout, p.col);
          const y = cellY(layout, p.row);
          const title = titleNoDate(p.finding.title);
          // A title that opens with the state already says it; don't repeat it.
          const state = title.startsWith(p.week.regime_state) ? "" : `, ${p.week.regime_state}`;
          const name = `Finding: ${title}, week of ${longDate(p.week.week_start_date)}${state}`;
          const leaderEnd = labelX - 11;
          return (
            <g
              key={p.finding.slug}
              className="ledger-finding"
              tabIndex={0}
              role="link"
              aria-label={name}
              data-slug={p.finding.slug}
              onClick={() => open(p.finding.slug)}
              onKeyDown={(e) => {
                if (e.key === "Enter") open(p.finding.slug);
              }}
              onFocus={() => setTip({ week: p.week, x: place(x), y: y + layout.ch + 8 })}
              onBlur={() => setTip(null)}
            >
              <rect
                className="ledger-outline"
                x={x - 1.5}
                y={y - 1.5}
                width={layout.cw + 2}
                height={layout.ch + 3}
                fill="transparent"
              />
              {layout.showLabels && (
                <>
                  <polyline
                    className="ledger-leader"
                    fill="none"
                    points={`${LABEL_GUTTER + GRID_COLUMNS * layout.cw + 2},${y + layout.ch / 2} ${leaderEnd},${y + layout.ch / 2} ${labelX - 4},${p.labelY}`}
                  />
                  <text className="ledger-label" x={labelX} y={p.labelY + 1} dominantBaseline="middle">
                    {`${monthYear(p.week.week_start_date)} · ${p.week.regime_state}`}
                  </text>
                </>
              )}
            </g>
          );
        })}
      </svg>
      {tip && (
        <div className="tip" role="tooltip" style={{ left: tip.x, top: tip.y }}>
          <b>{range(tip.week.week_start_date)}</b>
          <br />
          {stateLabel(tip.week)}
          {tipConf && (
            <>
              <br />
              {tipConf}
            </>
          )}
          {slugs.has(tip.week.finding_slug ?? "") && (
            <>
              <br />
              <b>Finding: open ↵</b>
            </>
          )}
        </div>
      )}
    </div>
  );
}
