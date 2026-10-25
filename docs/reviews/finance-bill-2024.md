# Verdict log: finance-bill-2024

- Date: 2026-10-15 (consistency-pass run, from the revised draft that names the z-score; overwrites the earlier logs)
- Draft `week_start_date`: 2024-06-22
- Models: workflow run by Claude Sonnet 5.5 (`claude-sonnet-5-5`); verdicts by the `evidence-reviewer` subagent (model as set in its agent definition)
- Outcome: no UNSUPPORTED, CORRECTED or EXTERNAL NO SOURCE rows. Finding written to `content/findings/finance-bill-2024.yaml` (the draft minus its two comment lines).
- Note on the summary line: the reviewer's summary says 15 VERIFIED and 11 EXTERNAL; the 26-row table below has 17 VERIFIED and 9 EXTERNAL (rows 3, 6, 13, 15, 16, 17, 20, 21, 22). The table is unedited; the totals and the 0 CORRECTED, 0 UNSUPPORTED and 0 NO SOURCE are not affected.

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
2024-06-22 | total_events 167 | total_fatalities 56 | signal_valid true | prior_weeks 12 | median events 55.0 | median fatalities 11.5

### Q3 OONI rows, ranked by anomalous_zscore_12w
```sql
SELECT test_name, anomalous_count, anomalous_total_scored, anomalous_rate,
       anomalous_baseline_rate_12w, anomalous_zscore_12w,
       blocked_count, blocked_total_observations, blocked_rate, blocked_zscore_12w
FROM ooni_weekly_signals WHERE week_start_date = DATE '2024-06-22'
ORDER BY anomalous_zscore_12w DESC NULLS LAST, test_name
```
| test_name | anomalous_count | anomalous_total_scored | anomalous_rate | baseline_12w | z_12w | blocked_count | blocked_total | blocked_rate | blocked_z |
|---|---|---|---|---|---|---|---|---|---|
| signal | 30 | 998 | 0.03006 | 0.013421 | 1.2371 | 12 | 26039 | 0.000461 | 0.1795 |
| whatsapp | 48 | 1217 | 0.03944 | 0.020973 | 0.9337 | 0 | 101123 | 0.0 | -0.1557 |
| telegram | 36 | 1139 | 0.03161 | 0.018433 | 0.7691 | 14 | 33268 | 0.000421 | 0.6004 |
| psiphon | 0 | 1103 | 0.0 | 0.0 | 0.0 | 0 | 3232 | 0.0 | 0.0 |
| dnscheck | 0 | 40755 | 0.0 | 0.009936 | -0.4149 | 0 | 111208 | 0.0 | -0.4122 |

### Q4 Google Transparency, half-year containing the week
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

## Reviewer verdict table (verbatim)

| # | assertion (verbatim) | verdict | evidence (query + result, or correction, or source) |
|---|---|---|---|
| 1 | "22–28 June 2024: protest and suppression both SEVERE" | VERIFIED | `SELECT week_start_date, primary_regime, confidence_level, previous_regime, transition_detected, transition_type, regime_held_by_exit_persistence, weeks_in_current_regime, protest_band, violence_band, suppression_band, classification_reason FROM regime_weeks WHERE iso2='KE' AND week_start_date BETWEEN '2024-06-08' AND '2024-07-20' ORDER BY week_start_date` (Q-A) -> row 2024-06-22: protest_band `SEVERE`, suppression_band `SEVERE`. The week starts 2024-06-22, so it runs 22–28 June. |
| 2 | "CLIO's first CRISIS week of the 2024 Finance Bill protests" | VERIFIED | `SELECT week_start_date, primary_regime FROM regime_weeks WHERE iso2='KE' AND primary_regime='CRISIS' AND week_start_date BETWEEN '2023-06-01' AND '2024-12-31' ORDER BY week_start_date` -> CRISIS weeks: 2023-07-15, 2023-07-22, 2023-07-29, then 2024-06-22, 2024-06-29, 2024-07-06. 2024-06-22 is the first CRISIS week in 2024 and the first since 2023-07-29. Q-A also shows previous_regime `STABLE` and transition_type `ESCALATION`. The snapshot cannot date the protests. The "Finance Bill 2024" framing rests only on the AP citation (row 15). |
| 3 | "the week protesters entered Kenya's Parliament buildings" | EXTERNAL | source attached: AP News, "Kenya: Anti-tax protesters storm parliament, drawing police fire", 25 June 2024, https://apnews.com/article/kenya-protests-finance-bill-33a20092285f1d663264f7b0d513e1da |
| 4 | "In the week of 22–28 June 2024, CLIO classified Kenya as CRISIS with HIGH confidence." | VERIFIED | Q-A -> 2024-06-22: primary_regime `CRISIS`, confidence_level `HIGH`. `SELECT DISTINCT iso2, country FROM regime_weeks` -> `KE, Kenya` |
| 5 | "Protest (z = 2.01) and suppression (z = 2.31) were both SEVERE" | VERIFIED | `SELECT week_start_date, total_events, total_fatalities, signal_valid, protest_pressure_z, violence_pressure_z, suppression_z FROM acled_signal_context WHERE week_start_date = '2024-06-22'` (Q-B) -> protest_pressure_z `2.0057`, suppression_z `2.3126`. Q-A -> protest_band `SEVERE`, suppression_band `SEVERE`, classification_reason `protest=SEVERE(z=2.01),suppression=SEVERE(z=2.31)` |
| 6 | "against their own previous 12 weeks" | EXTERNAL | source attached (rule): content/methodology.yaml, https://github.com/Sanjomwa/clio-findings-explorer/blob/main/content/methodology.yaml, and CLIO production code, https://github.com/Sanjomwa/Civil-Liberties-Intelligence-Observatory/blob/main/Bruin/assets/features/acled_pressure_signals.sql. Both URLs point to allowed locations. |
| 7 | "and violence was ELEVATED (z = 1.44)" | VERIFIED | Q-B -> violence_pressure_z `1.4379`. Q-A -> violence_band `ELEVATED`, reason `violence=ELEVATED(z=1.44)` |
| 8 | "ACLED recorded 167 events that week" | VERIFIED | Q-B -> total_events `167` (signal_valid `true`) |
| 9 | "against a median of 55 in the 12 weeks before" | VERIFIED | `SELECT count(*) AS prior_weeks, percentile_cont(0.5) WITHIN GROUP (ORDER BY total_events) AS median_events FROM acled_signal_context WHERE week_start_date >= DATE '2024-06-22' - 84 AND week_start_date < DATE '2024-06-22'` -> prior_weeks `12`, median_events `55.0` |
| 10 | "The week before was held at STABLE as a first qualifying week toward CONTESTATION" | VERIFIED | Q-A -> 2024-06-15: primary_regime `STABLE`, classification_reason ends `pre_transition:CONTESTATION`. The meaning of that rule is cited to content/methodology.yaml and to CLIO acled_pressure_regimes.sql. Both URLs are allowed. |
| 11 | "with protest ELEVATED and suppression SEVERE" | VERIFIED | Q-A -> 2024-06-15: protest_band `ELEVATED` (z=1.39), suppression_band `SEVERE` (z=3.06) |
| 12 | "CRISIS was held for the two weeks after this one" | VERIFIED | Q-A -> 2024-06-29 and 2024-07-06: primary_regime `CRISIS`, regime_held_by_exit_persistence `true`, reason `exit_persistence`. All three family bands were `NORMAL` on 2024-06-29. On 2024-07-06 violence was `ELEVATED` and the other two were `NORMAL`. |
| 13 | "as leaving CRISIS takes three consecutive lower weeks" | EXTERNAL | source attached (rule): https://github.com/Sanjomwa/Civil-Liberties-Intelligence-Observatory/blob/main/Bruin/assets/intelligence/acled_pressure_regimes.sql (CTE-11), an allowed URL. The data fit this rule: the third lower week, 2024-07-13, is STABLE (row 14). |
| 14 | "the week of 13 July 2024 was STABLE" | VERIFIED | Q-A -> 2024-07-13: primary_regime `STABLE`, previous_regime `CRISIS`, transition_type `DE_ESCALATION` |
| 15 | "On 25 June 2024, protesters opposing the Finance Bill 2024 entered Kenya's Parliament buildings in Nairobi, and part of the building was on fire." | EXTERNAL | source attached: AP News, 25 June 2024, https://apnews.com/article/kenya-protests-finance-bill-33a20092285f1d663264f7b0d513e1da |
| 16 | "The same day, an internet disruption was recorded in Kenya; its cause is disputed." | EXTERNAL | source attached (2): The Star (Kenya), 25 June 2024, https://www.the-star.co.ke/news/2024-06-25-safaricom-explains-slow-internet-speed, and IODA (Georgia Tech), 14 May 2025, https://ioda.inetintel.cc.gatech.edu/reports/the-kenya-june-25-2024-internet-disruption-subsea-cable-cut-or-shutdown/ |
| 17 | "On 26 June 2024, President Ruto said he would not sign the bill." | EXTERNAL | source attached: Al Jazeera, 26 June 2024, https://www.aljazeera.com/news/2024/6/26/activists-call-for-new-protests-in-kenya-following-deadly-police-crackdown. Note for the human checker: the URL slug ("activists-call-for-new-protests...") does not match the cited headline ("Ruto says finance bill to be withdrawn..."). Confirm that the URL is the intended article. |
| 18 | "In OONI's measurements for the week, Signal's anomaly rate had the highest z-score against its own 12-week baseline, at 1.24." | VERIFIED | `SELECT test_name, anomalous_zscore_12w, anomalous_rate, anomalous_baseline_rate_12w, anomalous_count, anomalous_total_scored, anomalous_low_sample_flag, anomalous_sparse_baseline_flag FROM ooni_weekly_signals WHERE week_start_date = '2024-06-22' ORDER BY anomalous_zscore_12w DESC NULLS LAST, test_name` -> signal `1.2371` (rate 0.03006, baseline 0.013421, 30/998, no low-sample or sparse flag); whatsapp 0.9337; telegram 0.7691; psiphon 0.0; dnscheck -0.4149 |
| 19 | "Google's government-requests report lists 9 removal requests from Kenya for January to June 2024." | VERIFIED | `SELECT sum(number_of_requests) AS requests, sum(items_requested_removal) AS items FROM google_transparency_requests WHERE time_period = 'January - June 2024'` -> requests `9`, items `12`. google_transparency_requests has no country column. "From Kenya" depends on the snapshot covering only Kenya (regime_weeks holds only `KE, Kenya`). |
| 20 | "ACLED data are the classification's own input, so the ACLED card is not independent confirmation of the CRISIS label." | EXTERNAL | source attached (rule): content/methodology.yaml, https://github.com/Sanjomwa/clio-findings-explorer/blob/main/content/methodology.yaml, an allowed URL. The rest of the sentence is a limitation statement with no data claim. |
| 21 | "OONI's Signal test checks whether Signal's servers can be reached from the tester's network." | EXTERNAL | source attached: OONI, "Signal test", https://ooni.org/nettest/signal/ |
| 22 | "OONI's own resources point to IODA and similar tools for monitoring internet connectivity shutdowns." | EXTERNAL | source attached: OONI Resources (2021), https://ooni.org/documents/2021-ooni-partner-training-resources/ooni-resources.pdf |
| 23 | "This finding treats OONI data as evidence neither for nor against the 25 June disruption." | VERIFIED | limitation statement; no data claim |
| 24 | "Google's figure covers the whole half-year, not this week." | VERIFIED | `SELECT period_date, requestor, product, reason, time_period, number_of_requests, items_requested_removal FROM google_transparency_requests WHERE time_period ILIKE '%2024%' ORDER BY period_date` -> the 8 rows behind the figure all have time_period `January - June 2024` and period_date `2024-06-01`. The table has no weekly granularity. |
| 25 | "Do not conclude that the protests, the internet disruption and the OONI measurements are connected." | VERIFIED | limitation statement; no data claim |
| 26 | "This finding records only that they fall in the same week." | VERIFIED | The OONI rows exist for week_start_date `2024-06-22` (query in row 18 returns 5 rows). That week runs 22–28 June, so it includes 25 June. The dates of the protests and the disruption themselves are EXTERNAL (rows 15–16). The sentence states co-occurrence only and makes no causal claim. |

Summary: 15 VERIFIED, 0 CORRECTED, 0 UNSUPPORTED, 11 EXTERNAL (0 without source).
Counted: 17 VERIFIED, 0 CORRECTED, 0 UNSUPPORTED, 9 EXTERNAL (0 without source).
(Counted line added on 25 October 2026 by the script in agent-capabilities/new-finding.md step 5. The review above is unchanged, including the reviewer's own summary line.)
