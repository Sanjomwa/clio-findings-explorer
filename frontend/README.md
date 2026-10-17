# Frontend

React 18, TypeScript and Vite. Node 22 (`.nvmrc`). This is the Phase 3a shell: Vite scaffold, typed API client, design tokens and both themes, the page shell and placeholder pages. Real page content arrives in later steps.

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
