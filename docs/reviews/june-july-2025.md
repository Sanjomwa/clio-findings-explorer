# Verdict log: june-july-2025

- Date: 2026-10-14 (second run, after Sam revised the draft; overwrites the first-run log)
- Draft `week_start_date`: 2025-06-21
- Models: workflow run by Claude Sonnet 5.5 (`claude-sonnet-5-5`); verdicts by the `evidence-reviewer` subagent (model as set in its agent definition)
- Outcome: no UNSUPPORTED, CORRECTED or EXTERNAL NO SOURCE rows. Finding written to `content/findings/june-july-2025.yaml`.
- Changes since the first run: "With suppression alone raised" became "With suppression the only family raised"; a ninth citation was added for the definition of STABLE (first-run row 31 had no source).

## Step 3 queries and results (week = 2025-06-21)

### Q1 regime row
```sql
SELECT week_start_date, primary_regime, confidence_level, transition_detected,
       protest_band, violence_band, suppression_band
FROM regime_weeks WHERE iso2 = 'KE' AND week_start_date = DATE '2025-06-21'
```
2025-06-21 | STABLE | HIGH | transition_detected true | protest NORMAL | violence NORMAL | suppression ELEVATED

### Q2 ACLED row with prior-12-week median
```sql
WITH prior AS (
  SELECT total_events, total_fatalities FROM acled_signal_context
  WHERE week_start_date < DATE '2025-06-21' ORDER BY week_start_date DESC LIMIT 12
)
SELECT a.week_start_date, a.total_events, a.total_fatalities, a.signal_valid,
       (SELECT count(*) FROM prior) AS prior_weeks,
       (SELECT percentile_cont(0.5) WITHIN GROUP (ORDER BY total_events) FROM prior) AS prior_12w_median_events,
       (SELECT percentile_cont(0.5) WITHIN GROUP (ORDER BY total_fatalities) FROM prior) AS prior_12w_median_fatalities
FROM acled_signal_context a WHERE a.week_start_date = DATE '2025-06-21'
```
total_events 115 | total_fatalities 43 | signal_valid true | prior_weeks 12 | prior_12w_median_events 61.5 | prior_12w_median_fatalities 18.5

### Q3 OONI rows, ranked by the contract's rule
```sql
SELECT test_name, anomalous_count, anomalous_total_scored, anomalous_rate,
       anomalous_baseline_rate_12w, anomalous_zscore_12w,
       blocked_count, blocked_total_observations, blocked_rate, blocked_zscore_12w
FROM ooni_weekly_signals WHERE week_start_date = DATE '2025-06-21'
ORDER BY anomalous_zscore_12w DESC NULLS LAST, test_name
```
| test_name | anomalous_count | total_scored | anomalous_rate | baseline_12w | anomalous_z | blocked_count | blocked_total_obs | blocked_rate | blocked_z |
|---|---|---|---|---|---|---|---|---|---|
| telegram | 54 | 789 | 0.06844 | 0.00833 | 10.17474 | 19 | 22966 | 0.000827 | 1.5098 |
| psiphon | 0 | 784 | 0.0 | 0.0 | 0.0 | 0 | 2332 | 0.0 | 0.0 |
| whatsapp | 8 | 784 | 0.01020 | 0.01252 | -0.22427 | 0 | 63391 | 0.0 | -0.0700 |
| signal | 2 | 683 | 0.00293 | 0.00891 | -0.52611 | 1 | 18014 | 0.0000555 | -0.3769 |
| dnscheck | 24 | 12732 | 0.00189 | 0.00906 | -1.25588 | 48 | 36945 | 0.001299 | -1.3271 |

### Q4 Google Transparency totals, half-year containing the week
```sql
SELECT time_period, sum(number_of_requests) AS requests,
       sum(items_requested_removal) AS items_requested_removal,
       sum(items_removed_legal) AS items_removed_legal,
       sum(items_removed_policy) AS items_removed_policy
FROM google_transparency_requests
WHERE period_date = make_date(EXTRACT(YEAR FROM DATE '2025-06-21')::int,
                              CASE WHEN EXTRACT(MONTH FROM DATE '2025-06-21') <= 6 THEN 6 ELSE 12 END, 1)
GROUP BY time_period
```
January - June 2025 | requests 16 | items_requested_removal 42 | items_removed_legal 0 | items_removed_policy 5

## Reviewer verdict table (verbatim)

| # | assertion (verbatim) | verdict | evidence (query + result, or correction, or source) |
|---|---|---|---|
| 1 | "21–27 June 2025: STABLE" | VERIFIED | `SELECT week_start_date, primary_regime, confidence_level, previous_regime, transition_detected, transition_type, regime_held_by_exit_persistence, protest_band, violence_band, suppression_band, velocity_band, conversion_band, classification_reason FROM regime_weeks WHERE iso2='KE' AND week_start_date BETWEEN '2025-05-31' AND '2025-07-19' ORDER BY week_start_date` (Q-R) -> 2025-06-21: STABLE, HIGH. 21–27 June is the 7-day week starting 2025-06-21. |
| 2 | "with Telegram far above its baseline" | VERIFIED | `SELECT test_name, anomalous_count, anomalous_total_scored, anomalous_zscore_12w FROM ooni_weekly_signals WHERE week_start_date='2025-06-21' ORDER BY anomalous_zscore_12w DESC NULLS LAST, test_name` (Q-O) -> telegram 54/789, z=10.174743572270174 |
| 3 | "The anniversary week of the 2024 protests" | EXTERNAL | source attached: citation 1, Anadolu Agency, 25 June 2025, https URL. The week 2025-06-21 to 06-27 contains 25 June. A human should check that the article describes the 25 June 2025 protests as the anniversary of 2024. |
| 4 | "read STABLE with HIGH confidence" | VERIFIED | Q-R -> 2025-06-21: primary_regime STABLE, confidence_level HIGH |
| 5 | "OONI's Telegram test was 10.17 standard deviations above its baseline" | VERIFIED | Q-O -> telegram anomalous_zscore_12w 10.174743572270174 (rounds to 10.17) |
| 6 | "In the week of 21–27 June 2025, CLIO classified Kenya as STABLE with HIGH confidence." | VERIFIED | Q-R -> 2025-06-21 STABLE, HIGH. `SELECT (SELECT array_agg(DISTINCT iso2) FROM regime_weeks) AS iso2s, (SELECT count(*) FROM acled_signal_context WHERE week_start_date='2025-06-21') AS acled_rows, (SELECT week_start_date FROM regime_weeks WHERE iso2='KE' AND week_start_date > '2025-07-05' ORDER BY 1 LIMIT 1)` (Q-K) -> iso2s {KE}, acled_rows 1, so the snapshot holds Kenya only |
| 7 | "Suppression was ELEVATED (z = 1.21)" | VERIFIED | Q-R -> suppression_band ELEVATED, reason `suppression=ELEVATED(z=1.21)`. `SELECT week_start_date, total_events, total_fatalities, signal_valid, protest_pressure_z, violence_pressure_z, suppression_z FROM acled_signal_context WHERE week_start_date IN ('2025-06-07','2025-06-21','2025-07-05') ORDER BY 1` (Q-A) -> suppression_z 1.2091 |
| 8 | "while protest (z = 0.62) ... were NORMAL" | VERIFIED | Q-R -> protest_band NORMAL, `protest=NORMAL(z=0.62)`. Q-A -> protest_pressure_z 0.6168 |
| 9 | "violence (z = −0.07) were NORMAL" | VERIFIED | Q-R -> violence_band NORMAL, `violence=NORMAL(z=-0.07)`. Q-A -> violence_pressure_z -0.0668 |
| 10 | "ACLED recorded 115 events that week" | VERIFIED | Q-A -> 2025-06-21 total_events 115 (signal_valid true) |
| 11 | "against a median of 61.5 in the 12 weeks before" | VERIFIED | `SELECT count(*) AS prior_weeks, min(week_start_date), max(week_start_date), percentile_cont(0.5) WITHIN GROUP (ORDER BY total_events) AS median_events, bool_or(week_start_date='2025-06-07') AS has_0607, bool_or(week_start_date='2025-06-14') AS has_0614 FROM acled_signal_context WHERE week_start_date >= DATE '2025-06-21' - 84 AND week_start_date < DATE '2025-06-21'` (Q-B) -> 12 weeks, 2025-03-29 to 2025-06-14, median 61.5 |
| 12 | "With suppression the only family raised" | VERIFIED | Q-R -> 2025-06-21 protest_band NORMAL, violence_band NORMAL, suppression_band ELEVATED. I treated as families only protest_band, violence_band and suppression_band, following content/methodology.yaml (the families list, and line 5: "Raised" means a family band of ELEVATED or SEVERE). velocity_band is NORMAL. Flag for a human: conversion_band is HIGH this week. It is not a family and uses a NORMAL/HIGH scale. `SELECT velocity_band, conversion_band, count(*) FROM regime_weeks GROUP BY 1,2 ORDER BY 1,2` -> conversion HIGH in 837 of 1523 rows, so it is common. The wording is accurate only if "family" keeps this meaning. |
| 13 | "the week was a first qualifying week toward REPRESSION" | VERIFIED | Q-R -> 2025-06-21 classification_reason ends `pre_transition:REPRESSION`. The previous week (2025-06-14) had suppression NORMAL, so this is the first such week. |
| 14 | "The next week was not raised" | VERIFIED | Q-R -> 2025-06-28: protest, violence and suppression all NORMAL, and no pre_transition tag |
| 15 | "so REPRESSION was not assigned" | VERIFIED | Q-R -> 2025-06-21 STABLE and 2025-06-28 STABLE. No week in the range is REPRESSION. The "so" describes a classification rule, not a real-world cause. The rule's source is row 18. |
| 16 | "The same happened in the week of 5 July 2025" | VERIFIED | Q-R -> 2025-07-05 STABLE with `pre_transition:REPRESSION`. Q-K -> the next week is 2025-07-12, and Q-R shows 2025-07-12 STABLE with all three families NORMAL |
| 17 | "when suppression was SEVERE (z = 2.74)" | VERIFIED | Q-R -> 2025-07-05 suppression_band SEVERE, `suppression=SEVERE(z=2.74)`. Q-A -> suppression_z 2.74 |
| 18 | "Entering REPRESSION needs two consecutive qualifying weeks." | EXTERNAL | source attached: citation 6, CLIO acled_pressure_regimes.sql, https GitHub URL |
| 19 | "The two weeks before were ESCALATION" | VERIFIED | Q-R -> 2025-06-07 ESCALATION and 2025-06-14 ESCALATION |
| 20 | "protest was SEVERE (z = 2.03) in the week of 7 June 2025" | VERIFIED | Q-R -> 2025-06-07 protest_band SEVERE, `protest=SEVERE(z=2.03)`, transition_type ESCALATION. Q-A -> protest_pressure_z 2.0322 |
| 21 | "the week of 14 June 2025 was held at ESCALATION" | VERIFIED | Q-R -> 2025-06-14 ESCALATION, regime_held_by_exit_persistence true, reason ends `exit_persistence`, all three families NORMAL |
| 22 | "because leaving it takes two consecutive lower weeks" | EXTERNAL | source attached: citation 7, CLIO acled_pressure_regimes.sql exit persistence rules, https URL. This "because" refers to a classification rule, not to real-world causation. |
| 23 | "Both weeks are in this week's 12-week baseline." | VERIFIED | Q-B -> window 2025-03-29 to 2025-06-14, has_0607 true, has_0614 true |
| 24 | "On 25 June 2025, protests took place across Kenya marking one year since the 25 June 2024 protests." | EXTERNAL | source attached: citation 2, Anadolu Agency, https URL |
| 25 | "The same day, OONI found Telegram's web service blocked on at least three Kenyan networks, two of them Safaricom's" | EXTERNAL | source attached: citation 3, OONI Explorer, https URL |
| 26 | "the block was lifted the same day" | EXTERNAL | source attached: citation 3 (its claim covers the whole sentence), https URL |
| 27 | "The Communications Authority ordered television and radio stations to stop live coverage of the protests" | EXTERNAL | source attached: citation 4, Kenyans.co.ke, https URL. A human should check that this article, whose title is about the Telegram restriction, actually reports the CA broadcast order. |
| 28 | "and the High Court suspended that order the same day" | EXTERNAL | source attached: citation 5, The Star (Kenya), https URL |
| 29 | "the test furthest above its own 12-week baseline was Telegram, at 10.17 standard deviations" | VERIFIED | Q-O -> telegram 10.1747 is first. The rest: psiphon 0.0, whatsapp -0.2243, signal -0.5261, dnscheck -1.2559 |
| 30 | "54 of 789 Telegram measurements were anomalous" | VERIFIED | Q-O -> telegram anomalous_count 54, anomalous_total_scored 789 |
| 31 | "Google's government-requests report lists 16 removal requests from Kenya for January to June 2025." | VERIFIED | `SELECT sum(number_of_requests) AS requests, sum(items_requested_removal) AS items FROM google_transparency_requests WHERE time_period='January - June 2025'` -> 16, 42. The table has no country column. "From Kenya" rests on the snapshot being Kenya-only (Q-K). |
| 32 | "ACLED data are the classification's own input, so the ACLED card is not independent confirmation of the STABLE label." | VERIFIED | limitation statement; no data claim |
| 33 | "A STABLE label means no regime rule was met this week; it does not mean nothing happened." | EXTERNAL | source attached: citation 9, content/methodology.yaml, https URL. The citation's claim matches the sentence word for word. The local file (/home/sanjomwa/Projects/CLIO-Findings-Explorer-course-project/content/methodology.yaml, lines 27-31) says "No regime rule was met this week. Bands can still be raised; ...", which supports the first clause directly. "Does not mean nothing happened" is a reasonable gloss of "Bands can still be raised", but the file does not say it. A human should confirm that the URL github.com/Sanjomwa/clio-findings-explorer/blob/main/content/methodology.yaml resolves publicly (the repo name differs from the local folder name). |
| 34 | "Bands can still be raised" | VERIFIED | `SELECT count(*) FROM regime_weeks WHERE iso2='KE' AND primary_regime='STABLE' AND (protest_band IN ('ELEVATED','SEVERE') OR violence_band IN ('ELEVATED','SEVERE') OR suppression_band IN ('ELEVATED','SEVERE'))` -> 95 STABLE weeks have a raised family band. The citation 9 claim does not cover this clause, but the data does. |
| 35 | "and this week's suppression band was." | VERIFIED | Q-R -> 2025-06-21 suppression_band ELEVATED. Flag for a human: classification_reason begins `STABLE:ALL_NORMAL` even though suppression is ELEVATED. That is CLIO's internal label, and the draft does not quote it. |
| 36 | "OONI reported the block on Telegram's web service, not the Telegram mobile app." | EXTERNAL | source attached: citation 8, OONI Explorer, https URL |
| 37 | "The snapshot's weekly OONI figure does not show which networks or hours were affected." | VERIFIED | `SELECT table_name, column_name FROM information_schema.columns WHERE table_name IN ('acled_signal_context','ooni_weekly_signals','google_transparency_requests') ORDER BY table_name, ordinal_position` -> ooni_weekly_signals has week_start_date, test_name, and anomalous_/blocked_ counts, rates, z-scores and flags, plus feature_version. It has no network, ASN or hour column. |
| 38 | "Google's figure covers the whole half-year, not this week." | VERIFIED | Google query in row 31 plus `SELECT time_period, period_date, ... FROM google_transparency_requests WHERE time_period ILIKE '%2025%'` -> time_period 'January - June 2025', period_date 2025-06-01. No weekly field. |
| 39 | "Do not conclude that the protests, the Telegram block, the broadcast order and the OONI figure are connected, or that a STABLE label means the week was calm. This finding records only what fell in the same week and how CLIO's rules classified it." | VERIFIED | limitation statement; no data claim. It asserts no causal link. |

Summary (reviewer's line): 29 VERIFIED, 0 CORRECTED, 0 UNSUPPORTED, 10 EXTERNAL (0 without source).

The table's own count matches this line (29 + 10 = 39 rows).

## Workflow result

Step 6 reached "otherwise": `content/findings/june-july-2025.yaml` written from the draft's ten keys, wording unchanged.
