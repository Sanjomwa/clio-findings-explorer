import { GRID_COLUMNS } from "./weeks";

export const LABEL_GUTTER = 36;
export const ROW_GAP = 1.5;
export const LABEL_SPACING = 15;
export const NARROW_BELOW = 600;

export interface Layout {
  width: number;
  rows: number;
  showLabels: boolean;
  cw: number;
  ch: number;
  right: number;
}

export function computeLayout(width: number, rows: number): Layout {
  const showLabels = width >= NARROW_BELOW;
  const right = showLabels ? Math.min(200, Math.max(104, width * 0.22)) : 0;
  const cw = Math.max(3, (width - LABEL_GUTTER - right) / GRID_COLUMNS);
  const ch = Math.max(5, Math.min(9, cw * 0.9));
  return { width, rows, showLabels, cw, ch, right };
}

export const cellX = (l: Layout, col: number) => LABEL_GUTTER + col * l.cw;
export const cellY = (l: Layout, row: number) => row * (l.ch + ROW_GAP);

/** Label y positions: each at its cell's row, pushed down so labels are at least 15px apart. */
export function labelYs(l: Layout, rows: number[]): number[] {
  let prev = -99;
  return rows.map((row) => {
    const y = Math.max(cellY(l, row) + l.ch / 2, prev + LABEL_SPACING);
    prev = y;
    return y;
  });
}

export function gridHeight(l: Layout, lastLabelY: number | null): number {
  const base = l.rows * (l.ch + ROW_GAP) + 6;
  return l.showLabels && lastLabelY !== null ? Math.max(base, lastLabelY + 12) : base;
}

/** Map pointer coordinates (relative to the SVG) to a row and column, or null outside the grid. */
export function hitCell(l: Layout, x: number, y: number): { row: number; col: number } | null {
  const col = Math.floor((x - LABEL_GUTTER) / l.cw);
  const row = Math.floor(y / (l.ch + ROW_GAP));
  if (col < 0 || col >= GRID_COLUMNS || row < 0 || row >= l.rows) return null;
  return { row, col };
}
