# Verdict log: june-july-2025

- Date: 2026-10-15 (consistency-pass run, from the revised draft that names the z-score; overwrites the earlier logs)
- Draft `week_start_date`: 2025-06-21
- Models: workflow run by Claude Sonnet 5.5 (`claude-sonnet-5-5`); verdicts by the `evidence-reviewer` subagent (model as set in its agent definition)
- Outcome: no UNSUPPORTED, CORRECTED or EXTERNAL NO SOURCE rows. Finding written to `content/findings/june-july-2025.yaml` (the draft minus its two comment lines).

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
2025-06-21 | total_events 115 | total_fatalities 43 | signal_valid true | prior_weeks 12 | median events 61.5 | median fatalities 18.5

### Q3 OONI rows, ranked by anomalous_zscore_12w
```sql
SELECT test_name, anomalous_count, anomalous_total_scored, anomalous_rate,
       anomalous_baseline_rate_12w, anomalous_zscore_12w,
       blocked_count, blocked_total_observations, blocked_rate, blocked_zscore_12w
FROM ooni_weekly_signals WHERE week_start_date = DATE '2025-06-21'
ORDER BY anomalous_zscore_12w DESC NULLS LAST, test_name
```
| test_name | anomalous_count | anomalous_total_scored | anomalous_rate | baseline_12w | z_12w | blocked_count | blocked_total | blocked_rate | blocked_z |
|---|---|---|---|---|---|---|---|---|---|
| telegram | 54 | 789 | 0.06844 | 0.008325 | 10.1747 | 19 | 22966 | 0.000827 | 1.5098 |
| psiphon | 0 | 784 | 0.0 | 0.0 | 0.0 | 0 | 2332 | 0.0 | 0.0 |
| whatsapp | 8 | 784 | 0.01020 | 0.012519 | -0.2243 | 0 | 63391 | 0.0 | -0.0700 |
| signal | 2 | 683 | 0.002928 | 0.008912 | -0.5261 | 1 | 18014 | 0.0000555 | -0.3769 |
| dnscheck | 24 | 12732 | 0.001885 | 0.009059 | -1.2559 | 48 | 36945 | 0.001299 | -1.3271 |

### Q4 Google Transparency, half-year containing the week
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

## Reviewer queries (labels used in the table)

- QR: `SELECT week_start_date, primary_regime, confidence_level, protest_band, violence_band, suppression_band, regime_held_by_exit_persistence, classification_reason FROM regime_weeks WHERE iso2='KE' AND week_start_date IN ('2025-06-07','2025-06-14','2025-06-21','2025-06-28','2025-07-05','2025-07-12') ORDER BY week_start_date`
  -> 06-07 ESCALATION/HIGH, protest SEVERE, `protest=SEVERE(z=2.03)`; 06-14 ESCALATION/HIGH, all NORMAL, held_by_exit_persistence=true, reason ends `exit_persistence`; 06-21 STABLE/HIGH, protest NORMAL, violence NORMAL, suppression ELEVATED, `protest=NORMAL(z=0.62),suppression=ELEVATED(z=1.21),violence=NORMAL(z=-0.07)|HIGH:HIGH|pre_transition:REPRESSION`; 06-28 STABLE/HIGH, all NORMAL, no pre_transition; 07-05 STABLE/HIGH, suppression SEVERE `(z=2.74)`, `pre_transition:REPRESSION`; 07-12 STABLE/HIGH, all NORMAL.
- QB: `SELECT * FROM acled_signal_context WHERE week_start_date='2025-06-21'` -> total_events 115, total_fatalities 43, signal_valid true, protest_pressure_z 0.6168, violence_pressure_z -0.0668, suppression_z 1.2091.
- QC: `SELECT COUNT(*) AS prior_weeks, MIN(week_start_date) AS first_wk, MAX(week_start_date) AS last_wk, percentile_cont(0.5) WITHIN GROUP (ORDER BY total_events) AS median_events FROM acled_signal_context WHERE week_start_date >= DATE '2025-06-21' - INTERVAL '84 days' AND week_start_date < DATE '2025-06-21'` -> 12, 2025-03-29, 2025-06-14, 61.5
- QD: `SELECT * FROM ooni_weekly_signals WHERE week_start_date='2025-06-21' ORDER BY anomalous_zscore_12w DESC NULLS LAST, test_name` -> matches Q3 above; no network/ASN or hour column.
- QE: `SELECT test_name, anomalous_zscore_12w, anomalous_count, anomalous_total_scored FROM ooni_weekly_signals WHERE week_start_date='2025-06-21' ORDER BY anomalous_zscore_12w DESC NULLS LAST LIMIT 1` -> telegram, 10.174743572270174, 54, 789
- QF: `SELECT time_period, SUM(number_of_requests) AS requests, SUM(items_requested_removal) AS items, SUM(items_removed_legal) AS legal, SUM(items_removed_policy) AS policy FROM google_transparency_requests WHERE time_period='January - June 2025' GROUP BY time_period` -> January - June 2025, 16, 42, 0, 5.

## Reviewer verdict table (verbatim)

| # | assertion (verbatim) | verdict | evidence (query + result, or correction, or source) |
|---|---|---|---|
| 1 | "21–27 June 2025: STABLE" | VERIFIED | QR -> 2025-06-21 primary_regime `STABLE` |
| 2 | "with Telegram far above its baseline" | VERIFIED | QE -> telegram anomalous_zscore_12w `10.1747` (rate 0.06844 vs baseline 0.008325, QD) |
| 3 | "The anniversary week of the 2024 protests" | EXTERNAL | source attached: Anadolu Agency, 25 June 2025, https://aa.com.tr/en/africa/kenyan-human-rights-watchdog-reports-8-dead-in-ongoing-protests/3613451 |
| 4 | "read STABLE with HIGH confidence" | VERIFIED | QR -> 2025-06-21 `STABLE`, confidence_level `HIGH` |
| 5 | "OONI's Telegram test was 10.17 standard deviations above its baseline" | VERIFIED | QE -> telegram anomalous_zscore_12w `10.174743572270174` (this is the z-score of the anomaly rate) |
| 6 | "CLIO classified Kenya as STABLE with HIGH confidence" | VERIFIED | QR -> 2025-06-21 `STABLE`, `HIGH` |
| 7 | "Suppression was ELEVATED (z = 1.21)" | VERIFIED | QR -> suppression_band `ELEVATED`, reason `suppression=ELEVATED(z=1.21)`; QB suppression_z `1.2091` |
| 8 | "protest (z = 0.62) and violence (z = −0.07) were NORMAL" | VERIFIED | QR -> protest_band `NORMAL`, violence_band `NORMAL`, reason `protest=NORMAL(z=0.62)`, `violence=NORMAL(z=-0.07)`; QB 0.6168 / -0.0668 |
| 9 | "ACLED recorded 115 events that week" | VERIFIED | QB -> total_events `115` |
| 10 | "against a median of 61.5 in the 12 weeks before" | VERIFIED | QC -> prior_weeks `12` (2025-03-29 to 2025-06-14), median_events `61.5` |
| 11 | "With suppression the only family raised" | VERIFIED | QR -> 2025-06-21 protest `NORMAL`, violence `NORMAL`, suppression `ELEVATED` |
| 12 | "the week was a first qualifying week toward REPRESSION" | VERIFIED | QR -> 2025-06-21 reason ends `pre_transition:REPRESSION`; the prior week, 2025-06-14, has suppression `NORMAL` and no pre_transition tag. Rule citations also attached (methodology.yaml and acled_pressure_regimes.sql) |
| 13 | "The next week was not raised" | VERIFIED | QR -> 2025-06-28 protest/violence/suppression all `NORMAL` |
| 14 | "so REPRESSION was not assigned" | VERIFIED | QR -> 2025-06-28 primary_regime `STABLE` |
| 15 | "The same happened in the week of 5 July 2025" | VERIFIED | QR -> 2025-07-05 `STABLE`, reason `pre_transition:REPRESSION`; 2025-07-12 all bands `NORMAL`, `STABLE` |
| 16 | "when suppression was SEVERE (z = 2.74)" | VERIFIED | QR -> 2025-07-05 suppression_band `SEVERE`, reason `suppression=SEVERE(z=2.74)` |
| 17 | "Entering REPRESSION needs two consecutive qualifying weeks." | EXTERNAL | source attached (CLIO rule): CLIO acled_pressure_regimes.sql, REPRESSION persistence rule, https://github.com/Sanjomwa/Civil-Liberties-Intelligence-Observatory/blob/main/Bruin/assets/intelligence/acled_pressure_regimes.sql |
| 18 | "The two weeks before were ESCALATION" | VERIFIED | QR -> 2025-06-07 `ESCALATION`, 2025-06-14 `ESCALATION` |
| 19 | "protest was SEVERE (z = 2.03) in the week of 7 June 2025" | VERIFIED | QR -> 2025-06-07 protest_band `SEVERE`, reason `protest=SEVERE(z=2.03)` |
| 20 | "the week of 14 June 2025 was held at ESCALATION" | VERIFIED | QR -> 2025-06-14 `ESCALATION`, all bands `NORMAL`, regime_held_by_exit_persistence `true`, reason ends `exit_persistence` |
| 21 | "as leaving it takes two consecutive lower weeks" | EXTERNAL | source attached (CLIO rule): acled_pressure_regimes.sql, exit persistence rules (CTE-11), https://github.com/Sanjomwa/Civil-Liberties-Intelligence-Observatory/blob/main/Bruin/assets/intelligence/acled_pressure_regimes.sql |
| 22 | "Both weeks are in this week's 12-week baseline." | VERIFIED | QC -> the 12 prior weeks run from `2025-03-29` to `2025-06-14`, which includes 2025-06-07 and 2025-06-14. QB active_baseline_weeks are protest 12, violence 12, suppression 11. The snapshot does not store the z-score window itself; I verified it as the 12 calendar weeks before this one. |
| 23 | "On 25 June 2025, protests took place across Kenya marking one year since the 25 June 2024 protests." | EXTERNAL | source attached: Anadolu Agency, https://aa.com.tr/en/africa/kenyan-human-rights-watchdog-reports-8-dead-in-ongoing-protests/3613451 |
| 24 | "The same day, OONI found Telegram's web service blocked on at least three Kenyan networks, two of them Safaricom's" | EXTERNAL | source attached: OONI Explorer finding, Yachmeneva and Xynou, https://explorer.ooni.org/findings/2025-kenya-blocks-access-to-telegram-amid-anti-government-protes |
| 25 | "the block was lifted the same day" | EXTERNAL | source attached: same OONI Explorer citation (its claim covers this clause) |
| 26 | "The Communications Authority ordered television and radio stations to stop live coverage of the protests" | EXTERNAL | source attached: Kenyans.co.ke, Walter Ngano, https://www.kenyans.co.ke/news/113506-telegram-restricted-kenya-amid-charged-demos-nairobi (the article title is about Telegram; a human should confirm it covers the CA order) |
| 27 | "the High Court suspended that order the same day" | EXTERNAL | source attached: The Star (Kenya), https://www.the-star.co.ke/news/2025-06-25-court-suspends-cas-ban-on-live-protest-coverage |
| 28 | "Telegram's anomaly rate had the highest z-score against its own 12-week baseline, at 10.17" | VERIFIED | QE -> top row `telegram`, `10.1747`; QD -> next highest is psiphon `0.0` |
| 29 | "54 of 789 Telegram measurements were anomalous" | VERIFIED | QE -> anomalous_count `54`, anomalous_total_scored `789` |
| 30 | "Google's government-requests report lists 16 removal requests from Kenya for January to June 2025." | VERIFIED | QF -> requests `16`. Note: `google_transparency_requests` has no country column, so "from Kenya" depends on the table being Kenya-only. |
| 31 | "ACLED data are the classification's own input" | EXTERNAL | source attached (CLIO rule): content/methodology.yaml, https://github.com/Sanjomwa/clio-findings-explorer/blob/main/content/methodology.yaml (this URL matches this repo's origin in .git/config; the file exists locally) |
| 32 | "so the ACLED card is not independent confirmation of the STABLE label" | VERIFIED | limitation statement; no data claim |
| 33 | "A STABLE label means no regime rule was met this week; it does not mean nothing happened." | EXTERNAL | source attached (CLIO rule): content/methodology.yaml, https://github.com/Sanjomwa/clio-findings-explorer/blob/main/content/methodology.yaml. For the human checker: this week also has transition_detected=true / DE_ESCALATION from ESCALATION, and reason `STABLE:ALL_NORMAL` |
| 34 | "Bands can still be raised, and this week's suppression band was." | VERIFIED | QR -> 2025-06-21 suppression_band `ELEVATED` |
| 35 | "OONI reported the block on Telegram's web service, not the Telegram mobile app." | EXTERNAL | source attached: OONI Explorer finding, https://explorer.ooni.org/findings/2025-kenya-blocks-access-to-telegram-amid-anti-government-protes |
| 36 | "The snapshot's weekly OONI figure does not show which networks or hours were affected." | VERIFIED | QD -> ooni_weekly_signals columns are week_start_date, test_name, anomalous_*/blocked_* metrics and feature_version only; there is no network/ASN or hour column |
| 37 | "Google's figure covers the whole half-year, not this week." | VERIFIED | QF -> time_period `January - June 2025` (period_date 2025-06-01 for all rows) |
| 38 | "Do not conclude that the protests, the Telegram block, the broadcast order and the OONI figure are connected, or that a STABLE label means the week was calm." | VERIFIED | limitation statement; no data claim |
| 39 | "This finding records only what fell in the same week and how CLIO's rules classified it." | VERIFIED | limitation statement; no data claim |

Summary: 28 VERIFIED, 0 CORRECTED, 0 UNSUPPORTED, 11 EXTERNAL (0 without source).
Counted: 28 VERIFIED, 0 CORRECTED, 0 UNSUPPORTED, 11 EXTERNAL (0 without source).
(Counted line added on 25 October 2026 by the script in agent-capabilities/new-finding.md step 5. The review above is unchanged, including the reviewer's own summary line.)
