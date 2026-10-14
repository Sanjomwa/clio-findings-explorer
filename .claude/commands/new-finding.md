---
description: Review a human-written draft finding against the snapshot and, only if every assertion passes, write it to content/findings/. The only sanctioned way to add a finding.
argument-hint: <slug>
---

# /new-finding

Slug: `$ARGUMENTS` (call it `<slug>`). If no slug was given, or it does not match `^[a-z0-9]+(-[a-z0-9]+)*$`, say so and STOP.

You add a finding only by following these steps in order. Never write to `content/findings/` any other way. Never edit the draft. Never write causal or targeting wording yourself (AGENTS.md rule 6). Every number comes from `query_snapshot` and the query is recorded (rule 5).

## 1. Read the draft

Read `content/drafts/<slug>.yaml`. If it does not exist, STOP. If `content/findings/<slug>.yaml` already exists, STOP and say the finding exists (changing a published finding is a human edit, not this workflow).

## 2. Validate the shape

The draft is the finding format (`slug`, `week_start_date`, `iso2`, `position`, `title`, `teaser`, `summary_md`, `published_at`, `caveats`) with a required `citations` list. Check, and STOP on the first failure:

- exactly those ten keys, no others (a `sources` key is the old name of `citations`: STOP and say to rename it);
- `slug` equals `<slug>`; `week_start_date` is `YYYY-MM-DD`; `published_at` is an ISO 8601 timestamp with a timezone; `position` is an integer >= 1 not used by another file in `content/findings/`; `iso2` is `KE`;
- `title`, `teaser`, `summary_md` are non-blank strings;
- `caveats` has at least one item, each exactly `{severity, caveat_md}` with severity `limitation` or `do_not_conclude`;
- `citations` must be present and be a list (it may be empty). Each item, if any, is exactly `{claim, citation, url}` with all three non-blank and `url` starting with `https://`. Whether every real-world event statement and every statement of CLIO's rules has a source is not a shape check; the reviewer's EXTERNAL rule enforces it and the workflow stops on EXTERNAL NO SOURCE.

## 3. Gather the week's numbers

Run these with `query_snapshot`, substituting the draft's `week_start_date` for `:week`. Keep each query text and its result for the log.

```sql
-- Q1 regime row
SELECT week_start_date, primary_regime, confidence_level, transition_detected,
       protest_band, violence_band, suppression_band
FROM regime_weeks WHERE iso2 = 'KE' AND week_start_date = DATE ':week';

-- Q2 ACLED row for the week, with the median of the 12 weeks before it
WITH prior AS (
  SELECT total_events, total_fatalities FROM acled_signal_context
  WHERE week_start_date < DATE ':week' ORDER BY week_start_date DESC LIMIT 12
)
SELECT a.week_start_date, a.total_events, a.total_fatalities, a.signal_valid,
       (SELECT count(*) FROM prior) AS prior_weeks,
       (SELECT percentile_cont(0.5) WITHIN GROUP (ORDER BY total_events) FROM prior) AS prior_12w_median_events,
       (SELECT percentile_cont(0.5) WITHIN GROUP (ORDER BY total_fatalities) FROM prior) AS prior_12w_median_fatalities
FROM acled_signal_context a WHERE a.week_start_date = DATE ':week';

-- Q3 OONI rows for the week, ranked by the contract's rule (see below)
SELECT test_name, anomalous_count, anomalous_total_scored, anomalous_rate,
       anomalous_baseline_rate_12w, anomalous_zscore_12w,
       blocked_count, blocked_total_observations, blocked_rate, blocked_zscore_12w
FROM ooni_weekly_signals WHERE week_start_date = DATE ':week'
ORDER BY anomalous_zscore_12w DESC NULLS LAST, test_name;

-- Q4 Google Transparency totals for the half-year containing the week
-- (period_date is 1 June for January-June, 1 December for July-December)
SELECT time_period, sum(number_of_requests) AS requests,
       sum(items_requested_removal) AS items_requested_removal,
       sum(items_removed_legal) AS items_removed_legal,
       sum(items_removed_policy) AS items_removed_policy
FROM google_transparency_requests
WHERE period_date = make_date(EXTRACT(YEAR FROM DATE ':week')::int,
                              CASE WHEN EXTRACT(MONTH FROM DATE ':week') <= 6 THEN 6 ELSE 12 END, 1)
GROUP BY time_period;
```

The top OONI test is defined by the contract's rule (`getOoniEvidence` in `openapi.yaml`): the highest non-null `anomalous_zscore_12w`, ties broken by `test_name`; it is not the highest raw rate or count, so cite Q3's first row only when its z-score is non-null.

A query that returns zero rows is a result ("no row"), not an error. An `error` result means the database is unavailable: STOP.

## 4. Invoke `evidence-reviewer`

Call the `evidence-reviewer` subagent with the full draft text (including `citations`) and the queries and results from step 3 as claims to re-check. It returns a verdict table (`| # | assertion (verbatim) | verdict | evidence |`) and a summary line. Do not edit its table.

## 5. Write the verdict log

Write `docs/reviews/<slug>.md`: a heading, the date, the models used, the draft's `week_start_date`, the step-3 queries with results, the reviewer's table verbatim, and its summary line. Resolution marker for the later steps: a human who has fixed a `CORRECTED` row or added a source for an `EXTERNAL` row appends `RESOLVED` (uppercase) to the end of that table row, in the evidence cell, after the draft has been fixed and the workflow re-run. This workflow never adds `RESOLVED` itself.

## 6. Branch on the verdicts (first match wins)

- Any `UNSUPPORTED`: STOP. Do not write the finding. List the assertions. The human rewrites or removes them in the draft.
- Any `CORRECTED`: STOP. Show each correction and its query for the human to apply to the draft. Never apply it yourself.
- Any `EXTERNAL` with `NO SOURCE`: STOP. Say which sentence needs a cited public source in `citations`.
- Otherwise: write `content/findings/<slug>.yaml` with the draft's ten finding keys, same values, `citations` included. Do not alter any wording.

Re-running after the human edits the draft starts again at step 1 and overwrites `docs/reviews/<slug>.md`.

## 7. Load it and check it (only after a finding file was written)

1. `docker compose run --rm seed`: the output must report the finding loaded and no error.
2. `curl -s localhost:8000/api/findings/<slug>` and the three evidence endpoints `/api/findings/<slug>/evidence/acled`, `/ooni`, `/google-transparency`: each must return 200. Quote the status codes. The finding's JSON must contain the same number of `citations` as the draft; quote both counts.
3. `uv run --directory backend pytest tests/unit/test_content_language.py tests/unit/test_content_reviewed.py -v`: both must pass.

Then report: the verdict summary, the file written, the curl status codes and the test result. Do not run any git write command; Sam commits.
