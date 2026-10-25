# Verdict log: general-election-2022

- Date: 2026-10-14 (second run, after Sam revised the draft; overwrites the first-run log)
- Draft `week_start_date`: 2022-08-06
- Models: workflow run by Claude Sonnet 5.5 (`claude-sonnet-5-5`); verdicts by the `evidence-reviewer` subagent (model as set in its agent definition)
- Outcome: no UNSUPPORTED, CORRECTED or EXTERNAL NO SOURCE rows. Finding written to `content/findings/general-election-2022.yaml`.
- Changes since the first run: the teaser now says the label "is computed only from ACLED offline events" and names the #KeepItOn coalition as the reporter; the suppression sentence now reads "or whose sub-type mentions arrests, detentions or crackdowns"; citations were added for the "computed only from ACLED" phrase and for the ACLED-input caveat sentence (first-run rows 5 and 26 had no source).

## Step 3 queries and results (week = 2022-08-06)

### Q1 regime row
```sql
SELECT week_start_date, primary_regime, confidence_level, transition_detected,
       protest_band, violence_band, suppression_band
FROM regime_weeks WHERE iso2 = 'KE' AND week_start_date = DATE '2022-08-06'
```
2022-08-06 | CRISIS | HIGH | transition_detected true | protest NORMAL | violence SEVERE | suppression SEVERE

### Q2 ACLED row with prior-12-week median
```sql
WITH prior AS (
  SELECT total_events, total_fatalities FROM acled_signal_context
  WHERE week_start_date < DATE '2022-08-06' ORDER BY week_start_date DESC LIMIT 12
)
SELECT a.week_start_date, a.total_events, a.total_fatalities, a.signal_valid,
       (SELECT count(*) FROM prior) AS prior_weeks,
       (SELECT percentile_cont(0.5) WITHIN GROUP (ORDER BY total_events) FROM prior) AS prior_12w_median_events,
       (SELECT percentile_cont(0.5) WITHIN GROUP (ORDER BY total_fatalities) FROM prior) AS prior_12w_median_fatalities
FROM acled_signal_context a WHERE a.week_start_date = DATE '2022-08-06'
```
total_events 90 | total_fatalities 13 | signal_valid true | prior_weeks 12 | prior_12w_median_events 38.5 | prior_12w_median_fatalities 7.0

### Q3 OONI rows, ranked by the contract's rule
```sql
SELECT test_name, anomalous_count, anomalous_total_scored, anomalous_rate,
       anomalous_baseline_rate_12w, anomalous_zscore_12w,
       blocked_count, blocked_total_observations, blocked_rate, blocked_zscore_12w
FROM ooni_weekly_signals WHERE week_start_date = DATE '2022-08-06'
ORDER BY anomalous_zscore_12w DESC NULLS LAST, test_name
```
No row (zero rows). Supporting query:
```sql
SELECT min(week_start_date) AS first_ooni_week, count(*) AS rows FROM ooni_weekly_signals
```
first_ooni_week 2023-05-27 | rows 550

### Q4 Google Transparency totals, half-year containing the week
```sql
SELECT time_period, sum(number_of_requests) AS requests,
       sum(items_requested_removal) AS items_requested_removal,
       sum(items_removed_legal) AS items_removed_legal,
       sum(items_removed_policy) AS items_removed_policy
FROM google_transparency_requests
WHERE period_date = make_date(EXTRACT(YEAR FROM DATE '2022-08-06')::int,
                              CASE WHEN EXTRACT(MONTH FROM DATE '2022-08-06') <= 6 THEN 6 ELSE 12 END, 1)
GROUP BY time_period
```
July - December 2022 | requests 5 | items_requested_removal 5 | items_removed_legal 0 | items_removed_policy 1

## Reviewer verdict table (verbatim)

| # | assertion (verbatim) | verdict | evidence (query + result, or correction, or source) |
|---|---|---|---|
| 1 | "6–12 August 2022" (title) | VERIFIED | Q-A: `SELECT week_start_date, iso2, primary_regime, confidence_level, previous_regime, transition_detected, transition_type, regime_held_by_exit_persistence, protest_band, violence_band, suppression_band, classification_reason FROM regime_weeks WHERE week_start_date BETWEEN '2022-07-23' AND '2022-09-03' ORDER BY week_start_date` -> row `2022-08-06, KE, CRISIS, HIGH ...` (week starts 6 Aug; the end date 12 Aug is start + 6 days) |
| 2 | "suppression and violence SEVERE" (title) | VERIFIED | Q-A -> 2022-08-06: `violence_band SEVERE, suppression_band SEVERE` |
| 3 | "in the election week" (title) | EXTERNAL | source attached: citation "Kenya's 2022 general election week" -> Al Jazeera, 10 Aug 2022, https URL |
| 4 | "CLIO's CRISIS label for Kenya" (teaser) | VERIFIED | Q-A -> `2022-08-06, KE, CRISIS`; `SELECT DISTINCT iso2, country FROM regime_weeks` -> `KE, Kenya` |
| 5 | "Kenya's 2022 general election week" (teaser) | EXTERNAL | source attached: Al Jazeera, https URL |
| 6 | "is computed only from ACLED offline events" (teaser) | EXTERNAL | source attached: content/methodology.yaml, https URL. Checked against the local file: all three families (lines 8-24) are defined from ACLED events, and CRISIS (lines 56-62) is defined from those families only, so "only from ACLED" is supported. The word "offline" is stated only for suppression (line 23, "recorded offline events only"); protest and violence are not described as "offline". A human should accept or reword. |
| 7 | "suppression and violence were both SEVERE" (teaser) | VERIFIED | Q-A -> `violence_band SEVERE, suppression_band SEVERE` |
| 8 | "the #KeepItOn coalition reported no internet shutdown" (teaser) | EXTERNAL | source attached: Access Now, "#KeepItOn elections watch 2022", https URL |
| 9 | "In the week of 6–12 August 2022, CLIO classified Kenya as CRISIS with HIGH confidence." | VERIFIED | Q-A -> `2022-08-06, KE, CRISIS, HIGH` |
| 10 | "Suppression (z = 3.06) ... SEVERE" | VERIFIED | Q-B: `SELECT week_start_date, total_events, total_fatalities, signal_valid, round(protest_pressure_z::numeric,2) pz, round(violence_pressure_z::numeric,2) vz, round(suppression_z::numeric,2) sz FROM acled_signal_context WHERE week_start_date = '2022-08-06'` -> `sz 3.06`; Q-A -> `suppression_band SEVERE` |
| 11 | "violence (z = 3.41) were both SEVERE" | VERIFIED | Q-B -> `vz 3.41`; Q-A -> `violence_band SEVERE` |
| 12 | "against their own previous 12 weeks" | VERIFIED | Q-C: `SELECT count(*) AS prior_weeks, percentile_cont(0.5) WITHIN GROUP (ORDER BY total_events) AS median_events FROM acled_signal_context WHERE week_start_date >= DATE '2022-08-06' - 84 AND week_start_date < DATE '2022-08-06'` -> `prior_weeks 12`. The 12-week baseline itself is defined in methodology.yaml (family_bands) |
| 13 | "protest was NORMAL (z = 0.37)" | VERIFIED | Q-B -> `pz 0.37`; Q-A -> `protest_band NORMAL` |
| 14 | "ACLED recorded 90 events that week" | VERIFIED | Q-B -> `total_events 90` |
| 15 | "against a median of 38.5 in the 12 weeks before" | VERIFIED | Q-C -> `prior_weeks 12, median_events 38.5` |
| 16 | "In CLIO, suppression counts ACLED events whose sub-type is "Excessive force against protesters" or "Protest with intervention", or whose sub-type mentions arrests, detentions or crackdowns." | EXTERNAL | source attached (two entries: methodology.yaml and production int.acled_event_classification.sql, both https). Matches methodology.yaml lines 20-21 word for word; the draft leaves out "whatever their main event type", which does not change the meaning |
| 17 | "It counts recorded offline events only; it does not measure internet restrictions or online censorship." | EXTERNAL | source attached: methodology.yaml, https. Matches lines 23-24 word for word |
| 18 | "The week before was held at STABLE" | VERIFIED | Q-A -> `2022-07-30, STABLE, HIGH, transition_detected false` |
| 19 | "as a first qualifying week toward CONFLICT" | EXTERNAL | source attached (methodology.yaml STABLE/CONFLICT, and production acled_pressure_regimes.sql, both https). The wording matches methodology.yaml lines 29-30 and 38-39. The snapshot agrees: Q-A 2022-07-30 classification_reason ends `pre_transition:CONFLICT`, with protest and suppression NORMAL and only violence raised |
| 20 | "with violence SEVERE" | VERIFIED | Q-A -> 2022-07-30 `violence_band SEVERE` (z=3.2) |
| 21 | "CRISIS was held for the two weeks after this one" | VERIFIED | Q-A -> 2022-08-13 and 2022-08-20: `CRISIS, regime_held_by_exit_persistence true`, all three bands NORMAL |
| 22 | "because leaving CRISIS takes three consecutive lower weeks" | EXTERNAL | source attached: production acled_pressure_regimes.sql (CTE-11), https. This is a statement of a rule, not a claim about events. It matches methodology.yaml line 61 ("ends only after three consecutive weeks that qualify for a lower state"), but methodology.yaml is not cited for this phrase. Adding it as a second source would be consistent with the other rule claims |
| 23 | "the week of 27 August 2022 was STABLE" | VERIFIED | Q-A -> `2022-08-27, STABLE, previous_regime CRISIS, transition_type DE_ESCALATION` |
| 24 | "Kenya held its general election on 9 August 2022." | EXTERNAL | source attached: Al Jazeera, 10 Aug 2022, https |
| 25 | "The #KeepItOn coalition received no reports of internet shutdowns during the election." | EXTERNAL | source attached: Access Now, https |
| 26 | "The snapshot has no OONI data for this week" | VERIFIED | Q-D: `SELECT (SELECT count(*) FROM ooni_weekly_signals WHERE week_start_date = '2022-08-06') AS rows_this_week, (SELECT min(week_start_date) FROM ooni_weekly_signals) AS first_week, (SELECT count(*) FROM ooni_weekly_signals) AS total_rows` -> `0, 2023-05-27, 550` |
| 27 | "its OONI weekly signals begin in May 2023" | VERIFIED | Q-D -> `first_week 2023-05-27` |
| 28 | "Google's government-requests report lists 5 removal requests from Kenya for July to December 2022." | VERIFIED | Q-E: `SELECT time_period, sum(number_of_requests) requests, sum(items_requested_removal) items, count(*) rows FROM google_transparency_requests WHERE time_period ILIKE '%2022%' GROUP BY time_period` -> `July - December 2022, 5, 5, 5`. Note: the table has no country column, so "from Kenya" depends on the snapshot covering Kenya only (regime_weeks holds only KE). Requestors are "Information and Communications Authority", "Police" and "Other" (Q-F: `SELECT requestor, product, reason, number_of_requests, items_requested_removal, items_removed_legal, items_removed_policy FROM google_transparency_requests WHERE time_period = 'July - December 2022'`) |
| 29 | "ACLED data are the classification's own input" (caveat 1) | EXTERNAL | source attached: methodology.yaml, https. Supported: every family and every regime state in methodology.yaml is defined from ACLED events |
| 30 | "so the ACLED card is not independent confirmation of the CRISIS label." (caveat 1) | VERIFIED | limitation statement; no data claim |
| 31 | "With no OONI data for this week, this finding says nothing about app or website blocking." (caveat 2) | VERIFIED | Q-D -> `rows_this_week 0`; the rest is a limitation statement |
| 32 | "The absence of a reported shutdown comes from the #KeepItOn coalition, not from a CLIO measurement." (caveat 2) | EXTERNAL | source attached: Access Now, https. Consistent with the snapshot: no shutdown field in any of the 4 tables (information_schema column listing) |
| 33 | "Google's figure covers the whole half-year, not this week." (caveat 3) | VERIFIED | Q-E -> `time_period 'July - December 2022'` (no weekly granularity) |
| 34 | "Do not conclude that the election and the CRISIS label are connected beyond falling in the same week, or that the SEVERE suppression band refers to anything online." (caveat 4) | VERIFIED | limitation statement; no data claim |
| 35 | "This finding records only that these coincide in time." (caveat 4) | VERIFIED | limitation statement. The co-occurrence depends on row 24 (EXTERNAL election date of 9 Aug) falling inside week 2022-08-06 to 08-12 (Q-A) |

Summary (reviewer's line): 23 VERIFIED, 0 CORRECTED, 0 UNSUPPORTED, 12 EXTERNAL (0 without source).
Counted: 23 VERIFIED, 0 CORRECTED, 0 UNSUPPORTED, 12 EXTERNAL (0 without source).
(Counted line added on 25 October 2026 by the script in agent-capabilities/new-finding.md step 5. The review above is unchanged, including the reviewer's own summary line.)

The table's own count matches this line (23 + 12 = 35 rows).

Reviewer's notes for a human (not verdicts):
- Teaser "offline": methodology.yaml says "offline" only for suppression (line 23). The "only from ACLED" part is supported; decide whether "offline events" is right for protest and violence too.
- The teaser and the summary use different #KeepItOn wording: "reported no internet shutdown" (teaser) and "received no reports of internet shutdowns during the election" (summary). Check that the Access Now page (https://www.accessnow.org/elections-internet-shutdowns-watch-2022/) actually covers Kenya's August 2022 election and supports both wordings, and that it supports caveat 2's sentence too.
- Al Jazeera (https://www.aljazeera.com/news/2022/8/10/tallying-underway-in-kenyan-election): check that it supports the polling date of 9 August 2022. The same entry covers both "election week" phrases (rows 3 and 5).
- How the two sources map to each claim: rows 16 and 19 cite both methodology.yaml and the production SQL. Row 22 cites only the production SQL; methodology.yaml line 61 also covers it. The production SQL files (int.acled_event_classification.sql read 2026-10-12, acled_pressure_regimes.sql read 2026-10-14) are not available to the reviewer. Confirm they say what is claimed.
- A snapshot oddity outside the draft's claims: the 2022-08-06 classification_reason reads `CRISIS:THREE_FAMILY_SEVERE` although only two families are SEVERE (protest NORMAL), and 08-13 and 08-20 repeat that tag. The draft correctly says "both" (two), but the reason-code label should be checked upstream.
- Queries were combined where one row returned several figures (Q-A for bands and regimes, Q-B for z-scores, events and fatalities). Each table row above names the query and the field it relies on.

## Workflow result

Step 6 reached "otherwise": `content/findings/general-election-2022.yaml` written from the draft's ten keys, wording unchanged.
