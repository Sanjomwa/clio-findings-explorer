# Verdict log: post-election-violence-2008

- Date: 2026-10-15 (re-run after Sam revised the draft; overwrites the earlier log)
- Draft `week_start_date`: 2008-01-19
- Models: workflow run by Claude Sonnet 5.5 (`claude-sonnet-5-5`); verdicts by the `evidence-reviewer` subagent (model as set in its agent definition)
- Outcome: no UNSUPPORTED, CORRECTED or EXTERNAL NO SOURCE rows. Finding written to `content/findings/post-election-violence-2008.yaml`.

## Step 3 queries and results (week = 2008-01-19)

### Q1 regime row
```sql
SELECT week_start_date, primary_regime, confidence_level, transition_detected,
       protest_band, violence_band, suppression_band
FROM regime_weeks WHERE iso2 = 'KE' AND week_start_date = DATE '2008-01-19'
```
2008-01-19 | ESCALATION | MEDIUM | transition_detected true | protest NORMAL | violence SEVERE | suppression ELEVATED

### Q2 ACLED row with prior-12-week median
```sql
WITH prior AS (
  SELECT total_events, total_fatalities FROM acled_signal_context
  WHERE week_start_date < DATE '2008-01-19' ORDER BY week_start_date DESC LIMIT 12
)
SELECT a.week_start_date, a.total_events, a.total_fatalities, a.signal_valid,
       (SELECT count(*) FROM prior) AS prior_weeks,
       (SELECT percentile_cont(0.5) WITHIN GROUP (ORDER BY total_events) FROM prior) AS prior_12w_median_events,
       (SELECT percentile_cont(0.5) WITHIN GROUP (ORDER BY total_fatalities) FROM prior) AS prior_12w_median_fatalities
FROM acled_signal_context a WHERE a.week_start_date = DATE '2008-01-19'
```
2008-01-19 | total_events 66 | total_fatalities 261 | signal_valid true | prior_weeks 12 | prior_12w_median_events 16.5 | prior_12w_median_fatalities 10.0

### Q3 OONI rows for the week
```sql
SELECT test_name, anomalous_count, anomalous_total_scored, anomalous_rate,
       anomalous_baseline_rate_12w, anomalous_zscore_12w,
       blocked_count, blocked_total_observations, blocked_rate, blocked_zscore_12w
FROM ooni_weekly_signals WHERE week_start_date = DATE '2008-01-19'
ORDER BY anomalous_zscore_12w DESC NULLS LAST, test_name
```
No row.

### Q4 Google Transparency totals for the half-year containing the week (period_date 2008-06-01)
```sql
SELECT time_period, sum(number_of_requests) AS requests,
       sum(items_requested_removal) AS items_requested_removal,
       sum(items_removed_legal) AS items_removed_legal,
       sum(items_removed_policy) AS items_removed_policy
FROM google_transparency_requests
WHERE period_date = make_date(EXTRACT(YEAR FROM DATE '2008-01-19')::int,
                              CASE WHEN EXTRACT(MONTH FROM DATE '2008-01-19') <= 6 THEN 6 ELSE 12 END, 1)
GROUP BY time_period
```
No row.

## Reviewer's verdict table

| # | assertion (verbatim) | verdict | evidence (query + result, or correction, or source) |
|---|---|---|---|
| 1 | "19–25 January 2008: the first week CLIO could score after the disputed election" | VERIFIED | `SELECT DATE '2008-01-19' + 6 AS week_end, ...` -> `2008-01-25`. `SELECT min(week_start_date) FROM regime_weeks WHERE iso2='KE' AND week_start_date >= '2007-12-22' AND confidence_level <> 'INSUFFICIENT_DATA'` -> `2008-01-19`. The word "disputed" is covered by the citation in row 3. |
| 2 | "CLIO labelled Kenya's busiest ACLED week around the disputed 2007 election \"STABLE (insufficient data)\"" | VERIFIED | `SELECT week_start_date, total_events FROM acled_signal_context WHERE week_start_date BETWEEN '2007-10-20' AND '2008-02-16' ORDER BY total_events DESC LIMIT 2` -> `2007-12-29: 139; 2008-01-26: 74`. `SELECT string_agg(week_start_date \|\| ':' \|\| primary_regime \|\| '/' \|\| confidence_level, ', ' ORDER BY week_start_date) FROM regime_weeks WHERE iso2='KE' AND week_start_date BETWEEN '2007-12-22' AND '2008-01-12'` -> `2007-12-29:STABLE/INSUFFICIENT_DATA` (and the same for the other three weeks) |
| 3 | "the disputed 2007 election" | EXTERNAL | source attached: Al Jazeera, "Rival Kenyan leaders hold talks", 24 Jan 2008, https://www.aljazeera.com/news/2008/1/24/rival-kenyan-leaders-hold-talks |
| 4 | "one family's baseline was too thin" | VERIFIED | `SELECT string_agg(week_start_date \|\| ':' \|\| sparse_protest_baseline_flag \|\| '/' \|\| sparse_violence_baseline_flag \|\| '/' \|\| sparse_suppression_baseline_flag \|\| '/' \|\| zero_variance_flag, ', ') FROM acled_signal_context WHERE week_start_date='2007-12-29'` -> `2007-12-29:false/false/true/false` (only the suppression flag is set) |
| 5 | "which in CLIO's current code withholds all three scores" | EXTERNAL | CLIO rule statement. Source attached: content/methodology.yaml (https://github.com/Sanjomwa/clio-findings-explorer/blob/main/content/methodology.yaml; matches the repo's git remote; the file exists in the repo) and production acled_pressure_signals.sql (https://github.com/Sanjomwa/Civil-Liberties-Intelligence-Observatory/...). Data consistent with it: all three bands are UNKNOWN that week (see row 23). |
| 6 | "The week of 19 January 2008 was the first it could score, as ESCALATION." | VERIFIED | `SELECT min(week_start_date) FROM regime_weeks WHERE iso2='KE' AND week_start_date >= '2007-12-22' AND confidence_level <> 'INSUFFICIENT_DATA'` -> `2008-01-19`. `SELECT primary_regime \|\| ' / ' \|\| confidence_level FROM regime_weeks WHERE iso2='KE' AND week_start_date='2008-01-19'` -> `ESCALATION / MEDIUM` |
| 7 | "In the week of 19–25 January 2008, CLIO classified Kenya as ESCALATION with MEDIUM confidence." | VERIFIED | `SELECT primary_regime \|\| ' / ' \|\| confidence_level AS v FROM regime_weeks WHERE iso2='KE' AND week_start_date='2008-01-19'` -> `ESCALATION / MEDIUM`. `SELECT DATE '2008-01-19' + 6` -> `2008-01-25` |
| 8 | "Violence was SEVERE (z = 2.21)" | VERIFIED | `SELECT r.violence_band, a.violence_pressure_z FROM regime_weeks r JOIN acled_signal_context a USING (week_start_date) WHERE r.iso2='KE' AND week_start_date='2008-01-19'` -> `SEVERE, 2.206` |
| 9 | "suppression ELEVATED (z = 1.11)" | VERIFIED | `SELECT r.suppression_band, a.suppression_z FROM regime_weeks r JOIN acled_signal_context a USING (week_start_date) WHERE r.iso2='KE' AND week_start_date='2008-01-19'` -> `ELEVATED, 1.1078` |
| 10 | "against their own previous 12 weeks" | EXTERNAL | CLIO rule statement. Source attached: content/methodology.yaml (repo URL) and production acled_pressure_signals.sql (CLIO repo URL). |
| 11 | "while protest was NORMAL (z = 0.19)" | VERIFIED | `SELECT r.protest_band, a.protest_pressure_z FROM regime_weeks r JOIN acled_signal_context a USING (week_start_date) WHERE r.iso2='KE' AND week_start_date='2008-01-19'` -> `NORMAL, 0.1866` |
| 12 | "Of the conditions that set MEDIUM confidence, the only one met this week was suppression's score sitting within 0.15 of the ELEVATED threshold." | EXTERNAL | CLIO rule statement; the thresholds and conditions are not in the snapshot. Source attached: content/methodology.yaml (repo URL) and production acled_pressure_regimes.sql (CLIO repo URL). Data side: suppression z = 1.1078 (row 9), and all sparse, zero-variance and fallback flags are false that week. A human must check the threshold value and the list of conditions. |
| 13 | "ACLED recorded 66 events that week" | VERIFIED | `SELECT total_events FROM acled_signal_context WHERE week_start_date='2008-01-19'` -> `66` |
| 14 | "against a median of 16.5 in the 12 weeks before" | VERIFIED | `SELECT percentile_cont(0.5) WITHIN GROUP (ORDER BY total_events) AS median_events, percentile_cont(0.5) WITHIN GROUP (ORDER BY total_fatalities) AS median_fat, count(*) AS n FROM acled_signal_context WHERE week_start_date BETWEEN DATE '2008-01-19' - 84 AND DATE '2008-01-19' - 7` -> `16.5, 10.0, 12` |
| 15 | "This was the first week since the election that CLIO could score." | VERIFIED | `SELECT min(week_start_date) FROM regime_weeks WHERE iso2='KE' AND week_start_date >= '2007-12-22' AND confidence_level <> 'INSUFFICIENT_DATA'` -> `2008-01-19` |
| 16 | "The election week and the three weeks after it, starting 22 December 2007, 29 December 2007, 5 January 2008 and 12 January 2008, all read \"STABLE (insufficient data)\"." | VERIFIED | `SELECT string_agg(week_start_date \|\| ':' \|\| primary_regime \|\| '/' \|\| confidence_level, ', ' ORDER BY week_start_date) FROM regime_weeks WHERE iso2='KE' AND week_start_date BETWEEN '2007-12-22' AND '2008-01-12'` -> `2007-12-22:STABLE/INSUFFICIENT_DATA, 2007-12-29:STABLE/INSUFFICIENT_DATA, 2008-01-05:STABLE/INSUFFICIENT_DATA, 2008-01-12:STABLE/INSUFFICIENT_DATA`. Week bounds: `SELECT ..., DATE '2007-12-27' BETWEEN DATE '2007-12-22' AND DATE '2007-12-28' AS election_in_wk` -> `true` (the election date itself is EXTERNAL, row 36) |
| 17 | "ACLED recorded 139 events in the week of 29 December" | VERIFIED | `SELECT week_start_date, total_events FROM acled_signal_context WHERE week_start_date BETWEEN '2007-10-20' AND '2008-02-16' ORDER BY total_events DESC LIMIT 2` -> `2007-12-29: 139` |
| 18 | "more than in any other week from late October 2007 to mid-February 2008" | VERIFIED | same query as row 17 -> top `2007-12-29: 139`, next `2008-01-26: 74` |
| 19 | "The label reflects what CLIO could score, not how much happened." | VERIFIED | limitation statement; no data claim |
| 20 | "In each of those four weeks, suppression had activity in at most 3 of its previous 12 weeks" | VERIFIED | `SELECT max(suppression_active_baseline_weeks) FROM acled_signal_context WHERE week_start_date BETWEEN '2007-12-22' AND '2008-01-12'` -> `3` |
| 21 | "below the 4 needed for a usable score" | EXTERNAL | CLIO rule statement. Source attached: content/methodology.yaml, UNKNOWN band (repo URL). |
| 22 | "In CLIO's current code, a thin or nearly flat baseline in any one family leaves all three families without a usable score" | EXTERNAL | CLIO rule statement. Source attached: content/methodology.yaml (repo URL) and production acled_pressure_signals.sql (CLIO repo URL). |
| 23 | "so violence was not scored either" | VERIFIED | Data half only; the link to the rule is row 22 (EXTERNAL). `SELECT string_agg(DISTINCT violence_band, ',') FROM regime_weeks WHERE iso2='KE' AND week_start_date BETWEEN '2007-12-22' AND '2008-01-12'` -> `UNKNOWN` |
| 24 | "although from 29 December it had activity in 11 of its previous 12 weeks" | VERIFIED | `SELECT string_agg(week_start_date \|\| ':' \|\| violence_active_baseline_weeks, ', ' ORDER BY week_start_date) FROM acled_signal_context WHERE week_start_date BETWEEN '2007-12-29' AND '2008-01-12'` -> `2007-12-29:11, 2008-01-05:11, 2008-01-12:11` |
| 25 | "The index fallback did not apply." | VERIFIED | `SELECT bool_or(fallback_used) FROM regime_weeks WHERE iso2='KE' AND week_start_date BETWEEN '2007-12-22' AND '2008-01-12'` -> `false` |
| 26 | "It needs a family's weekly index to exceed three times its 12-week average" | EXTERNAL | CLIO rule statement. Source attached: content/methodology.yaml (repo URL; lines 62 and 87-88 contain this wording) and production acled_pressure_regimes.sql CTE-07 (CLIO repo URL). |
| 27 | "in the week of 29 December, violence's weekly index was 6.02" | VERIFIED | `SELECT substring(classification_reason from 'violence=[A-Z]+\(idx=([0-9.]+)\)') FROM regime_weeks WHERE iso2='KE' AND week_start_date='2007-12-29'` -> `6.02` (parsed from classification_reason, which stores it to 2 decimals) |
| 28 | "three times its 12-week average was about 6.7" | VERIFIED | `WITH v AS (SELECT week_start_date, CAST(substring(classification_reason from 'violence=[A-Z]+\(idx=([0-9.]+)\)') AS numeric) AS vidx FROM regime_weeks WHERE iso2='KE') SELECT count(vidx) AS n_parsed, round(3*avg(vidx),2) AS three_x_avg FROM v WHERE week_start_date BETWEEN '2007-10-06' AND '2007-12-22'` -> `12, 6.68`. Uses the index values parsed from classification_reason (2 dp) for the 12 weeks before 29 Dec, excluding that week; methodology.yaml line 97 describes the baseline as "its own previous 12 weeks". If the code's window included the current week, the value would be higher, and 6.02 would still not exceed it. |
| 29 | "Under CLIO's rules such a week is STABLE with insufficient data." | EXTERNAL | CLIO rule statement. Source attached: content/methodology.yaml, INSUFFICIENT_DATA (repo URL) and production acled_pressure_regimes.sql CTE-10/CTE-14 (CLIO repo URL). |
| 30 | "By the week of 19 January, suppression had 4 active weeks and all three families were scored." | VERIFIED | `SELECT a.suppression_active_baseline_weeks, r.protest_band \|\| '/' \|\| r.violence_band \|\| '/' \|\| r.suppression_band AS bands FROM acled_signal_context a JOIN regime_weeks r USING (week_start_date) WHERE r.iso2='KE' AND week_start_date='2008-01-19'` -> `4, NORMAL/SEVERE/ELEVATED` |
| 31 | "ESCALATION was held for the next three weeks" | VERIFIED | `SELECT string_agg(week_start_date \|\| ':' \|\| primary_regime, ', ' ORDER BY week_start_date) FROM regime_weeks WHERE iso2='KE' AND week_start_date BETWEEN '2008-01-26' AND '2008-02-16'` -> `2008-01-26:ESCALATION, 2008-02-02:ESCALATION, 2008-02-09:ESCALATION, 2008-02-16:STABLE` |
| 32 | "as leaving it takes two consecutive lower weeks and the state is held through up to two weeks of unusable data" | EXTERNAL | CLIO rule statement. Source attached: content/methodology.yaml (repo URL) and production acled_pressure_regimes.sql CTE-11 (CLIO repo URL). |
| 33 | "ACLED recorded 74, 2 and 0 events in those weeks." | VERIFIED | `SELECT string_agg(week_start_date \|\| ':' \|\| total_events, ', ' ORDER BY week_start_date) FROM acled_signal_context WHERE week_start_date BETWEEN '2008-01-26' AND '2008-02-09'` -> `2008-01-26:74, 2008-02-02:2, 2008-02-09:0` |
| 34 | "The week of 16 February 2008 was STABLE." | VERIFIED | same query as row 31 -> `2008-02-16:STABLE` |
| 35 | "No week in 2007 or 2008 was classified as CRISIS." | VERIFIED | `SELECT count(*) FILTER (WHERE primary_regime='CRISIS') AS crisis, count(*) AS weeks FROM regime_weeks WHERE iso2='KE' AND week_start_date BETWEEN '2007-01-01' AND '2008-12-31'` -> `0, 104` |
| 36 | "Kenya held a general election on 27 December 2007." | EXTERNAL | source attached: CRS RL34378 (Dagne, updated 4 Mar 2008), https://www.everycrsreport.com/files/20080304_RL34378_92ad7c619a24875edaf80496fd58dfd573398c4a.html |
| 37 | "On 24 January 2008, Kibaki and Odinga met for the first time since the disputed vote, in talks brokered by Kofi Annan." | EXTERNAL | source attached: Al Jazeera, 24 Jan 2008, https://www.aljazeera.com/news/2008/1/24/rival-kenyan-leaders-hold-talks |
| 38 | "The same day, violence reached Nakuru town" | EXTERNAL | source attached: IRIN / The New Humanitarian, 26 Jan 2008, https://www.thenewhumanitarian.org/report/76431/kenya-nakuru-residents-join-displaced-camp-their-own-town-violence-erupts |
| 39 | "which until then had escaped the post-election violence" | EXTERNAL | source attached: the same IRIN citation; its claim text includes this clause. |
| 40 | "Some 1,880 displaced people arrived at the town's displacement camp that day" | EXTERNAL | source attached: the same IRIN citation (https URL). |
| 41 | "the largest number it had received in a single day" | EXTERNAL | source attached: the same IRIN citation (https URL). |
| 42 | "The snapshot has no OONI or Google data for this week" | VERIFIED | `SELECT (SELECT count(*) FROM ooni_weekly_signals WHERE week_start_date='2008-01-19') AS ooni_rows, (SELECT count(*) FROM google_transparency_requests WHERE period_date='2008-06-01') AS google_rows` -> `0, 0` |
| 43 | "its OONI weekly signals begin in May 2023" | VERIFIED | `SELECT min(week_start_date) FROM ooni_weekly_signals` -> `2023-05-27` |
| 44 | "and its Google figures in the second half of 2012" | VERIFIED | `SELECT time_period FROM google_transparency_requests ORDER BY period_date LIMIT 1` -> `July - December 2012` |
| 45 | "ACLED data are the classification's own input" | EXTERNAL | CLIO rule statement. Source attached: content/methodology.yaml, the three ACLED-based families (repo URL). |
| 46 | "so the ACLED card is not independent confirmation of the ESCALATION label." | VERIFIED | limitation statement; no data claim |
| 47 | "The \"STABLE (insufficient data)\" label on the election week and the three weeks after it describes what CLIO could score, not how much happened." | VERIFIED | limitation statement; no data claim (the labels on those weeks are checked in row 16) |
| 48 | "CLIO's own design notes intend each family to be judged separately." | EXTERNAL | CLIO rule/design statement. Source attached: content/methodology.yaml (repo URL) and production acled_pressure_signals.sql header (CLIO repo URL). |
| 49 | "This finding does not say what label those weeks would have received under that design." | VERIFIED | limitation statement; no data claim |
| 50 | "With no OONI or Google data for this period, this finding says nothing about internet restrictions or content removal." | VERIFIED | The data fact checks out: `SELECT (SELECT count(*) FROM ooni_weekly_signals WHERE week_start_date='2008-01-19') AS ooni_rows, (SELECT count(*) FROM google_transparency_requests WHERE period_date='2008-06-01') AS google_rows` -> `0, 0`. The rest is a limitation. |
| 51 | "Do not conclude that the talks or the violence in Nakuru are connected to the ESCALATION label beyond falling in the same week, or that a week labelled \"STABLE (insufficient data)\" was calm." | VERIFIED | limitation statement; no data claim |
| 52 | "This finding records only that these coincide in time." | VERIFIED | Week bounds only (the events are EXTERNAL, rows 37-38): `SELECT DATE '2008-01-19' + 6 AS week_end, DATE '2007-12-27' BETWEEN DATE '2007-12-22' AND DATE '2007-12-28' AS election_in_wk, DATE '2008-01-24' BETWEEN DATE '2008-01-19' AND DATE '2008-01-25' AS jan24_in_wk` -> `2008-01-25, true, true` |

Summary (reviewer's line): 35 VERIFIED, 0 CORRECTED, 0 UNSUPPORTED, 17 EXTERNAL (0 without source).
Counted: 35 VERIFIED, 0 CORRECTED, 0 UNSUPPORTED, 17 EXTERNAL (0 without source).
(Counted line added on 25 October 2026 by the script in agent-capabilities/new-finding.md step 5. The review above is unchanged, including the reviewer's own summary line.)
