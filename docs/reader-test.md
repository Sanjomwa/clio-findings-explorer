# Reader test (spec §9.3)

## Purpose

[product-spec.md](../product-spec.md) §9.3 sets this criterion: "Someone unfamiliar with CLIO, landing on a finding page, can within two minutes state the classification, the confidence, one thing the evidence does not show, and how to cite the finding."

## Status

Not run before submission (25 October 2026). Readers, including course peer reviewers, are invited to take it.

## Protocol (about 2 minutes)

1. Open the live production finding page: <https://cfe-frontend-prod-qf6bvfuxjq-ew.a.run.app/findings/finance-bill-2024>. (The README's production link plus the app's route `/findings/:slug`.)
2. Answer these four questions without help:
   1. Which state did CLIO give this week?
   2. With what confidence?
   3. Name one thing this evidence does NOT show.
   4. How would you cite this finding?

## Expected answers (for whoever scores it)

| Question | Expected answer | Source |
|---|---|---|
| 1. State | CRISIS | `data/snapshot/regime_weeks.ndjson`, week 2024-06-22 (`primary_regime`); the finding's summary in `content/findings/finance-bill-2024.yaml` says the same |
| 2. Confidence | HIGH | same row (`confidence_level`) |
| 3. One thing it does not show | Any one of: the ACLED card is not independent confirmation of the CRISIS label, because ACLED data are the classification's own input; OONI data are evidence neither for nor against the 25 June 2024 internet disruption; Google's figure covers the whole half-year, not this week; the protests, the disruption and the OONI measurements are not shown to be connected, only to fall in the same week | the four caveats in `content/findings/finance-bill-2024.yaml` |
| 4. How to cite | See below | `frontend/src` |

### On question 4

The page has no "how to cite" text or citation helper. A search of `frontend/src` found only: the snapshot version shown in the record header (`components/finding/RecordHeader.tsx`) and on each evidence card (`components/finding/ExhibitCard.tsx`), and a "Citations" list (`components/finding/Sources.tsx`) that gives the public sources for the finding's real-world statements, not a way to cite the finding itself. A reasonable answer is therefore the page URL plus the snapshot version (2026-10-10.1, `data/snapshot/MANIFEST.json`). That the page gives no citation guidance is a finding of the test design itself, not a reader error.

## How to record

Open a GitHub issue with the "Reader test" template ([.github/ISSUE_TEMPLATE/reader-test.md](../.github/ISSUE_TEMPLATE/reader-test.md)) in <https://github.com/Sanjomwa/clio-findings-explorer/issues>. No names, emails or other personal details are needed or wanted. Results are copied into the table below later.

## Results

| Date | Reader (anonymous, e.g. "R1") | Time | Q1–Q4 right? | Notes |
|---|---|---|---|---|

No results yet.
