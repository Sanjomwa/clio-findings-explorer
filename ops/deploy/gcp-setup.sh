#!/usr/bin/env bash
# One-time Google Cloud setup for CLIO Findings Explorer. Sam runs this in Cloud Shell.
#
#   bash ops/deploy/gcp-setup.sh
#
# Safe to run again: every create checks first. It asks for the two Neon connection strings
# without echoing them, stores them in Secret Manager, and never writes them to disk.
# Needs permission to administer the project (Owner is enough).
set -euo pipefail

PROJECT_ID="${PROJECT_ID:-clio-findings-explorer-1012}"
REGION="${REGION:-europe-west1}"
REPO_SLUG="${REPO_SLUG:-Sanjomwa/clio-findings-explorer}"
AR_REPO="cfe"
RUNTIME_SA_NAME="cfe-runtime"
DEPLOYER_SA_NAME="cfe-deployer"
WIF_POOL="github"
WIF_PROVIDER_NAME="clio-findings-explorer"
SECRETS=(cfe-database-url-dev cfe-database-url-prod)

RUNTIME_SA="${RUNTIME_SA_NAME}@${PROJECT_ID}.iam.gserviceaccount.com"
DEPLOYER_SA="${DEPLOYER_SA_NAME}@${PROJECT_ID}.iam.gserviceaccount.com"

say() { printf '\n== %s\n' "$*"; }

gcloud config set project "$PROJECT_ID" >/dev/null
if ! gcloud projects describe "$PROJECT_ID" >/dev/null 2>&1; then
  echo "Project $PROJECT_ID not found or not accessible. Create it, link billing, then re-run." >&2
  exit 1
fi
PROJECT_NUMBER="$(gcloud projects describe "$PROJECT_ID" --format='value(projectNumber)')"

say "Enabling APIs"
gcloud services enable \
  run.googleapis.com \
  artifactregistry.googleapis.com \
  secretmanager.googleapis.com \
  iam.googleapis.com \
  iamcredentials.googleapis.com \
  sts.googleapis.com \
  cloudresourcemanager.googleapis.com

say "Artifact Registry repository ${AR_REPO}"
if ! gcloud artifacts repositories describe "$AR_REPO" --location "$REGION" >/dev/null 2>&1; then
  gcloud artifacts repositories create "$AR_REPO" \
    --repository-format docker --location "$REGION" \
    --description "CLIO Findings Explorer images"
fi
# Keep the 10 most recent versions of each image; delete the rest. (A Delete policy is needed:
# a Keep policy alone deletes nothing.)
POLICY_FILE="$(mktemp)"
trap 'rm -f "$POLICY_FILE"' EXIT
cat >"$POLICY_FILE" <<'JSON'
[
  {"name": "keep-10-recent", "action": {"type": "Keep"}, "mostRecentVersions": {"keepCount": 10}},
  {"name": "delete-older", "action": {"type": "Delete"}, "condition": {"tagState": "any"}}
]
JSON
gcloud artifacts repositories set-cleanup-policies "$AR_REPO" \
  --location "$REGION" --policy "$POLICY_FILE" --no-dry-run

say "Service accounts"
for name in "$RUNTIME_SA_NAME" "$DEPLOYER_SA_NAME"; do
  email="${name}@${PROJECT_ID}.iam.gserviceaccount.com"
  if ! gcloud iam service-accounts describe "$email" >/dev/null 2>&1; then
    gcloud iam service-accounts create "$name" --display-name "$name"
  fi
done

say "Secrets (empty containers first, so access can be granted per secret)"
for secret in "${SECRETS[@]}"; do
  if ! gcloud secrets describe "$secret" >/dev/null 2>&1; then
    gcloud secrets create "$secret" --replication-policy user-managed --locations "$REGION"
  fi
  gcloud secrets add-iam-policy-binding "$secret" \
    --member "serviceAccount:${RUNTIME_SA}" --role roles/secretmanager.secretAccessor \
    --condition=None >/dev/null
done

say "Deployer roles (minimum needed)"
gcloud projects add-iam-policy-binding "$PROJECT_ID" \
  --member "serviceAccount:${DEPLOYER_SA}" --role roles/run.admin --condition=None >/dev/null
gcloud artifacts repositories add-iam-policy-binding "$AR_REPO" --location "$REGION" \
  --member "serviceAccount:${DEPLOYER_SA}" --role roles/artifactregistry.writer >/dev/null
gcloud iam service-accounts add-iam-policy-binding "$RUNTIME_SA" \
  --member "serviceAccount:${DEPLOYER_SA}" --role roles/iam.serviceAccountUser >/dev/null

say "Workload Identity Federation (GitHub Actions, no keys)"
if ! gcloud iam workload-identity-pools describe "$WIF_POOL" --location global >/dev/null 2>&1; then
  gcloud iam workload-identity-pools create "$WIF_POOL" --location global \
    --display-name "GitHub Actions"
fi
if ! gcloud iam workload-identity-pools providers describe "$WIF_PROVIDER_NAME" \
  --workload-identity-pool "$WIF_POOL" --location global >/dev/null 2>&1; then
  gcloud iam workload-identity-pools providers create-oidc "$WIF_PROVIDER_NAME" \
    --workload-identity-pool "$WIF_POOL" --location global \
    --issuer-uri "https://token.actions.githubusercontent.com" \
    --attribute-mapping "google.subject=assertion.sub,attribute.repository=assertion.repository,attribute.ref=assertion.ref" \
    --attribute-condition "assertion.repository == '${REPO_SLUG}'"
fi
POOL_NAME="projects/${PROJECT_NUMBER}/locations/global/workloadIdentityPools/${WIF_POOL}"
gcloud iam service-accounts add-iam-policy-binding "$DEPLOYER_SA" \
  --member "principalSet://iam.googleapis.com/${POOL_NAME}/attribute.repository/${REPO_SLUG}" \
  --role roles/iam.workloadIdentityUser >/dev/null

# Reads a Neon URL silently, converts it for SQLAlchemy + psycopg 3 and stores it as a new
# secret version. The URL lives only in a shell variable and a pipe; it is never printed.
store_database_url() {
  local secret="$1" label="$2" url
  if gcloud secrets versions list "$secret" --filter 'state=enabled' --limit 1 \
    --format 'value(name)' | grep -q .; then
    printf '%s already has a value. Paste a new Neon URL to replace it, or press Enter to keep it: ' "$label"
  else
    printf 'Paste the Neon connection string for %s: ' "$label"
  fi
  read -rs url
  printf '\n'
  if [ -z "$url" ]; then
    if gcloud secrets versions list "$secret" --filter 'state=enabled' --limit 1 \
      --format 'value(name)' | grep -q .; then
      echo "Kept the existing value for $label."
      return 0
    fi
    echo "No value given for $label." >&2
    return 1
  fi
  case "$url" in
    postgresql://*) url="postgresql+psycopg://${url#postgresql://}" ;;
    postgres://*) url="postgresql+psycopg://${url#postgres://}" ;;
    *)
      echo "Rejected: the URL must start with postgresql:// or postgres://" >&2
      return 1
      ;;
  esac
  case "$url" in
    *[[:space:]]*)
      echo "Rejected: the URL contains whitespace" >&2
      return 1
      ;;
  esac
  printf '%s' "$url" | gcloud secrets versions add "$secret" --data-file=- >/dev/null
  echo "Stored a new version of $secret."
}

say "Neon connection strings (input is hidden)"
echo "Use the pooled or direct string of the matching Neon branch; the query string is kept."
store_database_url cfe-database-url-dev "dev (Neon branch 'dev')"
store_database_url cfe-database-url-prod "production (Neon branch 'production')"

say "Done. Run these in a terminal where 'gh' is logged in to the repository:"
cat <<OUT

gh variable set GCP_PROJECT_ID --repo ${REPO_SLUG} --body '${PROJECT_ID}'
gh variable set GCP_REGION --repo ${REPO_SLUG} --body '${REGION}'
gh variable set WIF_PROVIDER --repo ${REPO_SLUG} --body '${POOL_NAME}/providers/${WIF_PROVIDER_NAME}'
gh variable set DEPLOYER_SA --repo ${REPO_SLUG} --body '${DEPLOYER_SA}'
gh variable set RUNTIME_SA --repo ${REPO_SLUG} --body '${RUNTIME_SA}'
gh variable set AR_REPO --repo ${REPO_SLUG} --body '${AR_REPO}'

OUT
