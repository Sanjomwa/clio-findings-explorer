# Verdict log: finance-bill-2024

- Date: 2026-10-14 (third run, after Sam unquoted `week_start_date` and `published_at`; overwrites the earlier logs)
- Draft `week_start_date`: 2024-06-22
- Models: workflow run by Claude Sonnet 5.5 (`claude-sonnet-5-5`); verdicts by the `evidence-reviewer` subagent (model as set in its agent definition)
- Outcome: no UNSUPPORTED, CORRECTED or EXTERNAL NO SOURCE rows. Finding written to `content/findings/finance-bill-2024.yaml`.
- History: run 1 stopped on two unsourced OONI caveat sentences; run 2 passed review but the seed rejected the quoted `week_start_date` and `published_at` (the loader needs native YAML date and datetime values), so that finding file was deleted; this run uses the fixed draft. The wording is unchanged since run 2.

## Step 3 queries and results (week = 2024-06-22)

### Q1 regime row
```sql
SELECT week_start_date, primary_regime, confidence_level, transition_detected,
       protest_band, violence_band, suppression_band
FROM regime_weeks WHERE iso2 = 'KE' AND week_start_date = DATE '2024-06-22'
```
2024-06-22 | CRISIS | HIGH | transition_detected true | protest SEVERE | violence ELEVATED | suppression SEVERE

### Q2 ACLED row with prior-12-week median
```sql
WITH prior AS (
  SELECT total_events, total_fatalities FROM acled_signal_context
  WHERE week_start_date < DATE '2024-06-22' ORDER BY week_start_date DESC LIMIT 12
)
SELECT a.week_start_date, a.total_events, a.total_fatalities, a.signal_valid,
       (SELECT count(*) FROM prior) AS prior_weeks,
       (SELECT percentile_cont(0.5) WITHIN GROUP (ORDER BY total_events) FROM prior) AS prior_12w_median_events,
       (SELECT percentile_cont(0.5) WITHIN GROUP (ORDER BY total_fatalities) FROM prior) AS prior_12w_median_fatalities
FROM acled_signal_context a WHERE a.week_start_date = DATE '2024-06-22'
```
total_events 167 | total_fatalities 56 | signal_valid true | prior_weeks 12 | prior_12w_median_events 55.0 | prior_12w_median_fatalities 11.5

### Q3 OONI rows, ranked by the contract's rule
```sql
SELECT test_name, anomalous_count, anomalous_total_scored, anomalous_rate,
       anomalous_baseline_rate_12w, anomalous_zscore_12w,
       blocked_count, blocked_total_observations, blocked_rate, blocked_zscore_12w
FROM ooni_weekly_signals WHERE week_start_date = DATE '2024-06-22'
ORDER BY anomalous_zscore_12w DESC NULLS LAST, test_name
```
| test_name | anomalous_count | total_scored | anomalous_rate | baseline_12w | anomalous_z | blocked_count | blocked_total_obs | blocked_rate | blocked_z |
|---|---|---|---|---|---|---|---|---|---|
| signal | 30 | 998 | 0.03006 | 0.01342 | 1.23707 | 12 | 26039 | 0.000461 | 0.1795 |
| whatsapp | 48 | 1217 | 0.03944 | 0.02097 | 0.93366 | 0 | 101123 | 0.0 | -0.1557 |
| telegram | 36 | 1139 | 0.03161 | 0.01843 | 0.76907 | 14 | 33268 | 0.000421 | 0.6004 |
| psiphon | 0 | 1103 | 0.0 | 0.0 | 0.0 | 0 | 3232 | 0.0 | 0.0 |
| dnscheck | 0 | 40755 | 0.0 | 0.00994 | -0.41490 | 0 | 111208 | 0.0 | -0.4122 |

### Q4 Google Transparency totals, half-year containing the week
```sql
SELECT time_period, sum(number_of_requests) AS requests,
       sum(items_requested_removal) AS items_requested_removal,
       sum(items_removed_legal) AS items_removed_legal,
       sum(items_removed_policy) AS items_removed_policy
FROM google_transparency_requests
WHERE period_date = make_date(EXTRACT(YEAR FROM DATE '2024-06-22')::int,
                              CASE WHEN EXTRACT(MONTH FROM DATE '2024-06-22') <= 6 THEN 6 ELSE 12 END, 1)
GROUP BY time_period
```
January - June 2024 | requests 9 | items_requested_removal 12 | items_removed_legal 0 | items_removed_policy 2

## Reviewer queries and verdict table (verbatim)

Queries the reviewer ran (rows below cite them by label):
- Q-A: `SELECT week_start_date, primary_regime, confidence_level, previous_regime, transition_detected, transition_type, regime_held_by_exit_persistence, protest_band, violence_band, suppression_band, classification_reason FROM regime_weeks WHERE iso2='KE' AND week_start_date BETWEEN '2024-06-01' AND '2024-07-20' ORDER BY week_start_date`
- Q-B: `SELECT week_start_date, total_events, total_fatalities, signal_valid, protest_pressure_z, violence_pressure_z, suppression_z, protest_active_baseline_weeks, violence_active_baseline_weeks, suppression_active_baseline_weeks FROM acled_signal_context WHERE week_start_date IN (DATE '2024-06-15', DATE '2024-06-22') ORDER BY week_start_date` -> 2024-06-15: `75, 11, true, 1.3896, 0.29, 3.0562, 12, 12, 9`; 2024-06-22: `167, 56, true, 2.0057, 1.4379, 2.3126, 12, 12, 10`
- Q-C: `SELECT count(*) AS prior_weeks, percentile_cont(0.5) WITHIN GROUP (ORDER BY total_events) AS median_events FROM acled_signal_context WHERE week_start_date >= DATE '2024-06-22' - 84 AND week_start_date < DATE '2024-06-22'` -> `12, 55.0`
- Q-D: `SELECT test_name, anomalous_zscore_12w, anomalous_count, anomalous_total_scored FROM ooni_weekly_signals WHERE week_start_date='2024-06-22' ORDER BY anomalous_zscore_12w DESC NULLS LAST, test_name` -> signal `1.2370736643659876` (30/998), whatsapp `0.9336640117915688`, telegram `0.7690714655285`, psiphon `0.0`, dnscheck `-0.4149030443616443`
- Q-E: `SELECT time_period, period_date, count(*) AS rows, sum(number_of_requests) AS requests, sum(items_requested_removal) AS items FROM google_transparency_requests WHERE time_period = 'January - June 2024' GROUP BY time_period, period_date` -> `January - June 2024, 2024-06-01, 8, 9, 12`
- Q-F: `SELECT max(week_start_date) FILTER (WHERE primary_regime='CRISIS' AND week_start_date < DATE '2024-06-22') AS last_crisis_before, count(*) FILTER (WHERE primary_regime='CRISIS' AND week_start_date >= DATE '2024-01-01' AND week_start_date < DATE '2024-06-22') AS crisis_2024_before, (SELECT string_agg(DISTINCT iso2 || ':' || country, ',') FROM regime_weeks) AS countries FROM regime_weeks WHERE iso2='KE'` -> `2023-07-29, 0, KE:Kenya`

Q-A results:
- 2024-06-08: STABLE, no pre_transition tag
- 2024-06-15: STABLE / HIGH / STABLE / false / PERSISTENCE / false / ELEVATED-NORMAL-SEVERE / `protest=ELEVATED(z=1.39),suppression=SEVERE(z=3.06)...|pre_transition:CONTESTATION`
- 2024-06-22: CRISIS / HIGH / STABLE / true / ESCALATION / false / SEVERE-ELEVATED-SEVERE / `protest=SEVERE(z=2.01),suppression=SEVERE(z=2.31),violence=ELEVATED(z=1.44)`
- 2024-06-29: CRISIS / HIGH / CRISIS / false / PERSISTENCE / true / `exit_persistence`
- 2024-07-06: CRISIS / HIGH / CRISIS / false / PERSISTENCE / true / `exit_persistence`
- 2024-07-13: STABLE / HIGH / CRISIS / true / DE_ESCALATION / false

| # | assertion (verbatim) | verdict | evidence (query + result, or correction, or source) |
|---|---|---|---|
| 1 | "22–28 June 2024" (title) | VERIFIED | Q-A -> a row exists with week_start_date `2024-06-22`. Its 7-day week ends 28 June. |
| 2 | "protest and suppression both SEVERE" (title) | VERIFIED | Q-A -> 2024-06-22 protest_band `SEVERE`, suppression_band `SEVERE` |
| 3 | "CLIO's first CRISIS week of the 2024 Finance Bill protests" (teaser) | VERIFIED | Q-F -> `0` CRISIS weeks from 2024-01-01 to before 2024-06-22. The last earlier CRISIS week is `2023-07-29`. Q-A -> 2024-06-22 is `CRISIS`, previous_regime `STABLE`, transition_type `ESCALATION`. The snapshot does not store the "Finance Bill protests" label; that is real-world framing, sourced at row 4. |
| 4 | "the week protesters entered Kenya's Parliament buildings" (teaser) | EXTERNAL | source attached (AP News, 25 June 2024, https) |
| 5 | "In the week of 22–28 June 2024, CLIO classified Kenya as CRISIS with HIGH confidence." | VERIFIED | Q-A -> 2024-06-22 `CRISIS`, `HIGH`. Q-F -> iso2/country is `KE:Kenya` only. |
| 6 | "Protest (z = 2.01) ... SEVERE" | VERIFIED | Q-B -> protest_pressure_z `2.0057`. Q-A -> `protest=SEVERE(z=2.01)` |
| 7 | "suppression (z = 2.31) were both SEVERE" | VERIFIED | Q-B -> suppression_z `2.3126`. Q-A -> `suppression=SEVERE(z=2.31)` |
| 8 | "against their own previous 12 weeks" | VERIFIED | Q-B -> 2024-06-22 active baseline weeks: protest `12`, violence `12`, suppression `10`. Note: suppression had 10 active weeks in the window. No column stores the 12-week window length; that is a methodology fact. |
| 9 | "violence was ELEVATED (z = 1.44)" | VERIFIED | Q-B -> violence_pressure_z `1.4379`. Q-A -> violence_band `ELEVATED`, `violence=ELEVATED(z=1.44)` |
| 10 | "ACLED recorded 167 events that week" | VERIFIED | Q-B -> total_events `167` |
| 11 | "against a median of 55 in the 12 weeks before" | VERIFIED | Q-C -> `12, 55.0`. Note: acled_signal_context has no country column, so this assumes the table holds Kenya only. |
| 12 | "The week before was held at STABLE" | VERIFIED | Q-A -> 2024-06-15 `STABLE`, previous_regime `STABLE`, transition_detected `false` |
| 13 | "as a first qualifying week toward CONTESTATION" | VERIFIED | Q-A -> 2024-06-15 reason ends `pre_transition:CONTESTATION`. 2024-06-08 has no pre_transition tag. Note: reading a tagged week as a "qualifying week" comes from the CLIO methodology, not from a snapshot column. |
| 14 | "with protest ELEVATED and suppression SEVERE" | VERIFIED | Q-A -> 2024-06-15 protest `ELEVATED` (z=1.39), suppression `SEVERE` (z=3.06). Q-B -> `1.3896`, `3.0562` |
| 15 | "CRISIS was held for the two weeks after this one" | VERIFIED | Q-A -> 2024-06-29 and 2024-07-06 both `CRISIS`, regime_held_by_exit_persistence `true`, reason `exit_persistence` |
| 16 | "because leaving CRISIS takes three consecutive lower weeks" | EXTERNAL | source attached (CLIO acled_pressure_regimes.sql on GitHub, https). The snapshot does not store this rule but is consistent with it: per Q-A, the weeks after the CRISIS week are 06-29, 07-06 and 07-13, and 07-13 is STABLE. This "because" describes a classification rule, not a real-world cause. |
| 17 | "the week of 13 July 2024 was STABLE" | VERIFIED | Q-A -> 2024-07-13 `STABLE`, transition_type `DE_ESCALATION` |
| 18 | "On 25 June 2024, protesters opposing the Finance Bill 2024 entered Kenya's Parliament buildings in Nairobi, and part of the building was on fire." | EXTERNAL | source attached (AP News, https) |
| 19 | "The same day, an internet disruption was recorded in Kenya; its cause is disputed." | EXTERNAL | source attached (The Star, 25 June 2024; IODA report, 14 May 2025; both https) |
| 20 | "On 26 June 2024, President Ruto said he would not sign the bill." | EXTERNAL | source attached (Al Jazeera, https). For the human checker: the URL slug ("activists-call-for-new-protests...") does not match the cited headline. |
| 21 | "In OONI's measurements for the week, the test furthest above its own 12-week baseline was Signal, at 1.24 standard deviations." | VERIFIED | Q-D -> signal `1.2370736643659876` (30/998) ranks first. Next are whatsapp `0.9337` and telegram `0.7691`. |
| 22 | "Google's government-requests report lists 9 removal requests from Kenya for January to June 2024." | VERIFIED | Q-E -> requests `9` (items `12`). Note: the table has no country column, so "from Kenya" assumes the table holds Kenya only. |
| 23 | Caveat 1: "ACLED data are the classification's own input, so the ACLED card is not independent confirmation of the CRISIS label." | VERIFIED | The classification_reason z-values in Q-A (2.01 / 2.31 / 1.44) are the acled_signal_context z-values in Q-B (2.0057 / 2.3126 / 1.4379), rounded. The rest is a limitation statement. |
| 24 | Caveat 2: "OONI's app tests, including the Signal test, check whether an app's servers can be reached from the tester's network." | EXTERNAL | source attached (ooni.org/nettest/signal, https) |
| 25 | Caveat 2: "They are not a measure of general internet disruptions; OONI's own resources point to IODA and similar tools for monitoring shutdowns." | EXTERNAL | source attached (OONI Resources PDF, https). The citation's claim matches the sentence verbatim. |
| 26 | Caveat 2: "OONI data are therefore not evidence about the 25 June disruption either way." | VERIFIED | limitation statement; no data claim. The disruption it refers to is sourced at row 19. |
| 27 | Caveat 3: "Google's figure covers the whole half-year, not this week." | VERIFIED | Q-E -> a single period `January - June 2024` (period_date `2024-06-01`, 8 rows). There is no weekly field. |
| 28 | Caveat 4: "Do not conclude that the protests, the internet disruption and the OONI measurements are connected." | VERIFIED | limitation statement; no data claim |
| 29 | Caveat 4: "This finding records only that they fall in the same week." | VERIFIED | The Q-D rows are for week 2024-06-22. The 25 June events (rows 18–19, EXTERNAL) fall within 22–28 June. The sentence claims only that they share a week. |

Summary (reviewer's line): 22 VERIFIED, 0 CORRECTED, 0 UNSUPPORTED, 7 EXTERNAL (0 without source).

The table's own count matches this line (22 + 7 = 29 rows).

## Workflow result

Step 6 reached "otherwise": `content/findings/finance-bill-2024.yaml` written from the draft's ten keys, wording unchanged.
