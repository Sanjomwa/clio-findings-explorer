# Deployment

Two environments, **dev** and **production**, each with a backend and a frontend service on Google Cloud Run (`europe-west1`) and its own Neon Postgres branch (AWS `eu-central-1`). See `product-spec.md` §7.1.

| Thing | Dev | Production |
|---|---|---|
| Backend service | `cfe-backend-dev` | `cfe-backend-prod` |
| Frontend service | `cfe-frontend-dev` | `cfe-frontend-prod` |
| Migrate-and-seed job | `cfe-seed-dev` | `cfe-seed-prod` |
| Secret | `cfe-database-url-dev` | `cfe-database-url-prod` |
| Neon branch | `dev` | `production` |

Shared: Google project `clio-findings-explorer-1012`, Artifact Registry repository `cfe` (images `backend` and `frontend`, tagged with the commit SHA), service accounts `cfe-runtime` (what the services run as) and `cfe-deployer` (what GitHub Actions acts as), Workload Identity pool `github` with provider `clio-findings-explorer`.

How it fits together: one **backend image** (built from the repository root with `backend/Dockerfile`) holds the API, `content/` and `data/snapshot/`, so nothing needs a volume. The same image runs as the API and as the seed job (`alembic upgrade head && python -m app.seed`). The seed is safe to run on every deploy: it skips an already-loaded snapshot and upserts the findings. The **frontend image** is nginx serving the built site and proxying `/api` to its environment's backend over HTTPS (`BACKEND_URL`).

## One-time setup, in order

1. **Neon** (done). Project `clio-findings-explorer`, Postgres 16, branches `production` and `dev`, database `neondb`. Each branch has its own connection string (Neon console, Connect).
2. **Google Cloud project.** `clio-findings-explorer-1012` must exist with billing linked. Create it in the console if it does not.
3. **Cloud Shell script.** Open Cloud Shell in that project, get this repository (`git clone https://github.com/Sanjomwa/clio-findings-explorer`) and run:

   ```bash
   bash ops/deploy/gcp-setup.sh
   ```

   It enables the APIs, creates the registry (keeping the 10 most recent versions of each image), both service accounts with their minimum roles, the two secrets, and the Workload Identity pool and provider (restricted to the repository `Sanjomwa/clio-findings-explorer`). It asks for the two Neon URLs with hidden input, converts `postgresql://` or `postgres://` to `postgresql+psycopg://` (keeping the query string, such as `?sslmode=require`) and stores each as a secret version. It never prints or saves a URL. It is safe to run again; press Enter at a prompt to keep the stored value.
4. **GitHub repository variables.** The script ends by printing six `gh variable set …` lines (`GCP_PROJECT_ID`, `GCP_REGION`, `WIF_PROVIDER`, `DEPLOYER_SA`, `RUNTIME_SA`, `AR_REPO`). Run them yourself, where `gh` is logged in. They are not secrets.
5. **GitHub environments.** Settings, Environments: create `dev` (no rules) and `production` with **Required reviewers: Sam**. Optionally limit `production` to the `main` branch.
6. **Org policy check.** The services allow unauthenticated access (it is a public read-only site). If the project sits under an organisation with "Domain restricted sharing", the first deploy fails at the `allUsers` binding; relax that policy for this project.
7. **Budget alert.** Console, Billing, Budgets and alerts: create a budget on the project (for example 5 USD a month) with email alerts at 50%, 90% and 100%. Scale-to-zero services and Neon's free plan should cost nothing at this traffic, but the alert catches a mistake.

## How dev deploys

Pushing to `main` runs CI. When CI finishes with `success`, `.github/workflows/deploy.yml` runs on the same commit, with no manual step (a red CI deploys nothing):

1. build both images and push them tagged with the commit SHA;
2. deploy and run the `cfe-seed-dev` job (waits for it);
3. deploy `cfe-backend-dev`, read its URL, deploy `cfe-frontend-dev` with that `BACKEND_URL`;
4. smoke test: `/api/health` through the frontend URL must return the `snapshot_version` in `data/snapshot/MANIFEST.json` and `findings: 5` (`ops/deploy/smoke-test.sh`);
5. the run summary shows the SHA and both URLs.

Authentication is Workload Identity Federation: the job gets a short-lived token as `cfe-deployer`. There are no key files in the repository, the images or the logs. The database URLs are only in Secret Manager.

## How to promote to production

1. Open the dev deploy run and copy the SHA from its summary.
2. Actions, **Deploy**, Run workflow (branch `main`), paste the SHA in `sha`.
3. The run waits for approval on the `production` environment. Approve it.
4. The job checks that both images exist for that SHA (it fails with a clear message if not; **it never rebuilds**), runs `cfe-seed-prod`, deploys the production backend and frontend, and smoke-tests the frontend URL.

## Roll back

Cloud Run keeps old revisions. Route traffic back to the previous one (use `-dev` or `-prod`):

```bash
gcloud run revisions list --service cfe-frontend-prod --region europe-west1   # newest first
gcloud run services update-traffic cfe-frontend-prod --region europe-west1 \
  --to-revisions <previous-revision-name>=100
```

Do the same for `cfe-backend-<env>` if the backend was the change. The previous revision is the second one in the list. To go forward again: `--to-latest`. Rolling back a service does not undo a database seed: the seed only reloads the snapshot and content, and a backend from the previous commit reads the same tables. If a migration changed the schema, roll back with a new commit instead.

### Rollback tried on dev

Rehearsed by Sam in Cloud Shell on 17 October 2026, region `europe-west1`. Before it, dev had two revisions per service after Deploy #3 (commit `fa43623`).

| Service | Previous revision (rolled back to) | Latest revision (rolled forward to) |
|---|---|---|
| `cfe-backend-dev` | `cfe-backend-dev-00001-b9b` (created 2026-10-17T18:54:26Z) | `cfe-backend-dev-00002-z4b` (2026-10-17T19:41:07Z) |
| `cfe-frontend-dev` | `cfe-frontend-dev-00001-jmz` (2026-10-17T18:54:39Z) | `cfe-frontend-dev-00002-n86` (2026-10-17T19:41:21Z) |

1. `gcloud run services update-traffic <service> --region europe-west1 --to-revisions <previous>=100` for both services. Result: "Traffic: 100% <previous revision>".
2. `curl https://cfe-frontend-dev-qf6bvfuxjq-ew.a.run.app/api/health`. Result: status ok, database reachable, snapshot 2026-10-10.1, migration 0004, findings 5, finding_caveats 21.
3. `gcloud run services update-traffic <service> --region europe-west1 --to-latest` for both. Result: "100% LATEST (currently ...-00002-...)".
4. Health check again. Result: the same healthy response.

While traffic is pinned to a named revision, a new deploy creates a revision that receives no traffic. That is why step 3 (`--to-latest`) is part of the procedure: run it when the rollback is over, or the next deploy will not go live.

## Costs

Services scale to zero (`--min-instances 0 --max-instances 1`, 1 CPU, 512 MiB), so idle cost is nothing on Cloud Run's free tier; Artifact Registry and Secret Manager are cents; Neon's free plan covers two small branches. The budget alert (step 7) is the guard. A cold start takes a few seconds for the first visitor.

## Privacy note

The nginx access log has no client IP and no query string (see `frontend/nginx/default.conf.template`), and nginx does not forward `X-Forwarded-For`. Cloud Run's own platform request logs record the caller's IP address; we cannot switch that off. Spec §7.2 ("no client IPs in telemetry") therefore applies to the telemetry the application emits, not to Cloud Run's platform logs.

## Known limit

nginx re-resolves the backend's hostname at most every 10 seconds (`resolver ... valid=10s` and a variable in `proxy_pass`, in `frontend/nginx/default.conf.template`). Without that, nginx looks the name up once at start-up and keeps the address: after `docker compose restart backend` (new container address) the frontend answered 502 until it was restarted too, and a long-lived Cloud Run frontend instance could keep an old backend address in the same way. The resolver address comes from `/etc/resolv.conf` (`NGINX_ENTRYPOINT_LOCAL_RESOLVERS=1` in `frontend/Dockerfile`), so it works in compose and on Cloud Run. The remaining limit: a backend that is down answers 502 until it is back, then recovers within about 10 seconds.

## Tear everything down

```bash
P=clio-findings-explorer-1012; R=europe-west1
for e in dev prod; do
  gcloud run services delete cfe-frontend-$e cfe-backend-$e --region $R --project $P --quiet
  gcloud run jobs delete cfe-seed-$e --region $R --project $P --quiet
  gcloud secrets delete cfe-database-url-$e --project $P --quiet
done
gcloud artifacts repositories delete cfe --location $R --project $P --quiet
gcloud iam workload-identity-pools delete github --location global --project $P
gcloud iam service-accounts delete cfe-deployer@$P.iam.gserviceaccount.com --project $P --quiet
gcloud iam service-accounts delete cfe-runtime@$P.iam.gserviceaccount.com --project $P --quiet
```

Then delete the Neon project in the Neon console, the GitHub variables and the two GitHub environments. To remove everything at once, delete the Google project (`gcloud projects delete clio-findings-explorer-1012`; it is recoverable for 30 days).
