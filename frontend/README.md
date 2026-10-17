# Frontend

React 18, TypeScript and Vite. Node 22 (`.nvmrc`). Built so far: the Vite scaffold, typed API client, design tokens and both themes, the page shell, the ledger (`/`) and the finding page (`/findings/:slug`). The register, methodology and about pages are still placeholders.

## Commands

Run from `frontend/`.

| Purpose | Command |
|---|---|
| Install (exact versions from `package-lock.json`) | `npm ci` |
| Dev server on `localhost:5173` (proxies `/api` to `127.0.0.1:8000`) | `npm run dev` |
| Type-check | `npm run typecheck` |
| Lint | `npm run lint` |
| Tests (Vitest, Testing Library, jsdom) | `npm test` |
| Production build to `dist/` | `npm run build` |
| Regenerate API types from `../openapi.yaml` | `npm run gen:api` |

The dev proxy needs the API running (`docker compose up -d --build` at the repo root).

## One client

Every backend call goes through `src/api/client.ts`, the only file that calls `fetch` (AGENTS.md rule 3). A test fails if any other file under `src/` contains `fetch(`. The base URL is `VITE_API_BASE`, default `""` (same origin). A non-2xx response throws `ApiError` with the `status`; `isNotFound` is true for 404.

## API types

`src/api/schema.d.ts` is generated from `openapi.yaml` by `npm run gen:api` and committed. Do not edit it by hand. CI regenerates it and fails if the committed file differs.

## Theme

Two states, light and dark. An inline script in `index.html` sets `data-theme` on `<html>` before first paint: the stored choice if there is one, otherwise `prefers-color-scheme`. The reader's choice is kept in `localStorage` under `cfe-theme`; every storage access is wrapped in try/catch, so the switch still works for the page view when storage is blocked.

## Fonts

Self-hosted through `@fontsource` packages (Schibsted Grotesk, Literata, Spline Sans Mono). No request goes to a third-party font host.

## Ledger (`/`)

The landing page draws every classified week as one SVG cell: one row per calendar year, one column per `floor(dayOfYear / 7)` (1 January is day 0, so 53 columns). All date maths is in UTC (`src/lib/weeks.ts`).

- **Data:** `getTimeline()` (country KE) for the weeks and `listFindings()` for the findings, both through the client. If only the findings list fails, the ledger is drawn without outlines; if the timeline fails, the page offers "Try again".
- **Insufficient data:** a week is "insufficient data" only when its state is STABLE and its confidence is INSUFFICIENT_DATA. It is drawn with `--st-I`. Every other week uses its own state colour, including ESCALATION weeks with INSUFFICIENT_DATA confidence. Fills are CSS variables, so a theme switch needs no redraw.
- **Hover:** one mouse handler on the SVG finds the cell from the pointer position; the memoised cell layer does not re-render. The tooltip shows the Saturday-to-Friday range, the state and the confidence, and for a finding week `Finding: open ↵`. It carries no family bands.
- **Keyboard:** ordinary cells are not focusable. Each finding is one focusable element (Tab to reach it, Enter to open `/findings/<slug>`); focus shows the tooltip and a focus ring. Below 600px of width the margin labels and leader lines are hidden and the outlines stay.
- **`FindingRegister`:** the list of findings in API (curated) order, reused by `/findings` later.

## Finding page (`/findings/:slug`)

`src/pages/Finding.tsx` with components in `src/components/finding/` and pure helpers in `src/lib/finding.ts`.

- **Data, all through the client:** `getFinding` (record header, state, headline, dek, summary, limits, citations, data sources), `listFindings` (the "Finding N of M" item and previous/next), `getTimeline` for 91 days either side of the week (the context strip; it starts once the finding's date is known), and the three evidence calls. The family band z-scores come from the ACLED card's `supporting.week`.
- **Independent loading:** the page renders as soon as the finding arrives. Each of the other five requests fills in or fails on its own: a failed evidence call shows `This exhibit could not be loaded.` in that card only, a failed list hides the pager and the "Finding N of M" item, a failed timeline hides the strip, and a failed ACLED card leaves the band names without bars. The page remounts per slug, so moving between findings starts every part again and scrolls to the top.
- **Errors:** a 404 for the finding shows `No finding with this name.` with links to the ledger and `/findings`; any other error shows `This finding could not be loaded.` and `Try again`.
- **No data:** a card with `has_data: false` is still shown, with `No data` and the API's `provenance_note` verbatim. The frontend writes no coverage dates.
- **OONI number:** the card leads with the top test's anomaly rate (`metric_value`, as a percentage to one decimal), as spec §4.2 says. The description gives the test's count, its 12-week baseline rate (both from the top test's row in `supporting.tests`) and the z-score (`comparison.value`); with no z-score, the sentence ends after the baseline.
- **Wording:** the STABLE and pre-transition sentences are the spec's §4.1 strings (`src/lib/finding.ts`). Summary and caveats are split on blank lines into plain paragraphs; nothing is rendered as HTML, and a test fails if `dangerouslySetInnerHTML` appears in the page or its components.
