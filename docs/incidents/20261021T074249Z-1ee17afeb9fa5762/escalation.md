# Escalation: 20261021T074249Z-1ee17afeb9fa5762

The on-call agent could not fix this incident and hands it to a person.

**Why:** the model-call budget is spent (1 in the last hour of 0, 1 in the last 24 h of 10); no model call was made

**State left behind:** the service action, if any (None. The agent acts only on a valid diagnosis.) was not reverted. For a start or a
restart, undoing it would recreate the outage. Check `docker compose ps` and the gates in `gates.json`.

**Issue:** GitHub issue opened: https://github.com/Sanjomwa/clio-findings-explorer/issues/15

**Next:** read `summary.md`, `diagnosis.json` and `evidence/`, then check the rule at the Grafana alert list.
