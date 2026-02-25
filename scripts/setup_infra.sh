#!/bin/bash
# ═══════════════════════════════════════════════════════════════════════════════
# setup_infra.sh — Configuración inicial de infraestructura GCP + GitHub Secrets
# ═══════════════════════════════════════════════════════════════════════════════
#
# Este script se ejecuta UNA SOLA VEZ antes del primer deploy.
# Crea todos los recursos en GCP y configura los secrets en GitHub.
#
# Prerequisitos:
#   1. gcloud CLI instalado y autenticado (gcloud auth login)
#   2. gh CLI instalado y autenticado (gh auth login)
#   3. Un proyecto de GCP ya creado con billing habilitado
#   4. Un repositorio en GitHub ya creado
#
# Uso:
#   chmod +x scripts/setup_infra.sh
#   ./scripts/setup_infra.sh
# ═══════════════════════════════════════════════════════════════════════════════

set -euo pipefail

# ─── CONFIGURACIÓN (editar estos valores) ───────────────────────────────────
GCP_PROJECT_ID="faena-proyecciones"
GCP_REGION="us-central1"
GCS_BUCKET_NAME="proyeccion-faena-data"
GITHUB_REPO="gnavarrolema/faena-proyecciones"

# Service Account
SA_NAME="proyeccion-faena-sa"
SA_DISPLAY="Proyección Faena CI/CD"

# Artifact Registry
AR_REPO="proyeccion-faena"

# App secrets
APP_SECRET_KEY=""          # Generar con: openssl rand -hex 32
APP_ADMIN_USERNAME="admin"
APP_ADMIN_PASSWORD=""      # Cambiar en producción
APP_CORS_ORIGINS=""        # Se llena automáticamente con la URL del frontend
# ─────────────────────────────────────────────────────────────────────────────

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

log()  { echo -e "${GREEN}[✓]${NC} $1"; }
warn() { echo -e "${YELLOW}[!]${NC} $1"; }
err()  { echo -e "${RED}[✗]${NC} $1"; exit 1; }

# ─── Validaciones ───────────────────────────────────────────────────────────
echo ""
echo "═══════════════════════════════════════════════════════════════"
echo "  Setup de Infraestructura — Proyección de Faena"
echo "═══════════════════════════════════════════════════════════════"
echo ""

command -v gcloud >/dev/null 2>&1 || err "gcloud CLI no encontrado. Instálalo: https://cloud.google.com/sdk/docs/install"
command -v gh     >/dev/null 2>&1 || err "gh CLI no encontrado. Instálalo: https://cli.github.com"

[[ -z "$GCP_PROJECT_ID" ]]  && err "Configura GCP_PROJECT_ID en el script"
[[ -z "$GCS_BUCKET_NAME" ]] && err "Configura GCS_BUCKET_NAME en el script"
[[ -z "$GITHUB_REPO" ]]     && err "Configura GITHUB_REPO en el script (usuario/repo)"

# Generar secret key si no se definió
if [[ -z "$APP_SECRET_KEY" ]]; then
    APP_SECRET_KEY=$(openssl rand -hex 32)
    warn "SECRET_KEY generada automáticamente"
fi

# Password por defecto si no se definió
if [[ -z "$APP_ADMIN_PASSWORD" ]]; then
    APP_ADMIN_PASSWORD="admin123"
    warn "Usando ADMIN_PASSWORD por defecto (cambiar después)"
fi

# ─── 1. Configurar proyecto GCP ─────────────────────────────────────────────
log "Configurando proyecto GCP: $GCP_PROJECT_ID"
gcloud config set project "$GCP_PROJECT_ID"

# ─── 2. Habilitar APIs necesarias ───────────────────────────────────────────
log "Habilitando APIs de GCP..."
gcloud services enable \
    run.googleapis.com \
    artifactregistry.googleapis.com \
    storage.googleapis.com \
    iamcredentials.googleapis.com \
    iam.googleapis.com \
    cloudresourcemanager.googleapis.com

# ─── 3. Crear bucket GCS ────────────────────────────────────────────────────
if gcloud storage buckets describe "gs://$GCS_BUCKET_NAME" >/dev/null 2>&1; then
    warn "Bucket gs://$GCS_BUCKET_NAME ya existe"
else
    log "Creando bucket: gs://$GCS_BUCKET_NAME"
    gcloud storage buckets create "gs://$GCS_BUCKET_NAME" \
        --location="$GCP_REGION" \
        --uniform-bucket-level-access \
        --public-access-prevention
    log "Bucket creado"
fi

# ─── 4. Crear Artifact Registry ─────────────────────────────────────────────
if gcloud artifacts repositories describe "$AR_REPO" --location="$GCP_REGION" >/dev/null 2>&1; then
    warn "Artifact Registry '$AR_REPO' ya existe"
else
    log "Creando Artifact Registry: $AR_REPO"
    gcloud artifacts repositories create "$AR_REPO" \
        --repository-format=docker \
        --location="$GCP_REGION" \
        --description="Imágenes Docker de Proyección Faena"
    log "Artifact Registry creado"
fi

# ─── 5. Crear Service Account ───────────────────────────────────────────────
SA_EMAIL="${SA_NAME}@${GCP_PROJECT_ID}.iam.gserviceaccount.com"

if gcloud iam service-accounts describe "$SA_EMAIL" >/dev/null 2>&1; then
    warn "Service Account $SA_EMAIL ya existe"
else
    log "Creando Service Account: $SA_NAME"
    gcloud iam service-accounts create "$SA_NAME" \
        --display-name="$SA_DISPLAY"
    log "Service Account creado"
fi

# ─── 6. Asignar permisos al Service Account ─────────────────────────────────
log "Asignando roles al Service Account..."

ROLES=(
    "roles/run.admin"                    # Desplegar en Cloud Run
    "roles/storage.admin"                # Leer/escribir en GCS
    "roles/artifactregistry.writer"      # Push imágenes Docker
    "roles/iam.serviceAccountUser"       # Actuar como SA en Cloud Run
)

for ROLE in "${ROLES[@]}"; do
    gcloud projects add-iam-policy-binding "$GCP_PROJECT_ID" \
        --member="serviceAccount:$SA_EMAIL" \
        --role="$ROLE" \
        --condition=None \
        --quiet >/dev/null 2>&1
    log "  Rol asignado: $ROLE"
done

# ─── 7. Configurar Workload Identity Federation (WIF) ───────────────────────
WIF_POOL="github-pool"
WIF_PROVIDER="github-provider"

log "Configurando Workload Identity Federation..."

# Crear pool
if gcloud iam workload-identity-pools describe "$WIF_POOL" \
    --location="global" >/dev/null 2>&1; then
    warn "WIF Pool '$WIF_POOL' ya existe"
else
    gcloud iam workload-identity-pools create "$WIF_POOL" \
        --location="global" \
        --display-name="GitHub Actions Pool"
    log "WIF Pool creado"
fi

# Crear provider
if gcloud iam workload-identity-pools providers describe "$WIF_PROVIDER" \
    --workload-identity-pool="$WIF_POOL" \
    --location="global" >/dev/null 2>&1; then
    warn "WIF Provider '$WIF_PROVIDER' ya existe"
else
    gcloud iam workload-identity-pools providers create-oidc "$WIF_PROVIDER" \
        --workload-identity-pool="$WIF_POOL" \
        --location="global" \
        --issuer-uri="https://token.actions.githubusercontent.com" \
        --attribute-mapping="google.subject=assertion.sub,attribute.repository=assertion.repository" \
        --attribute-condition="assertion.repository=='$GITHUB_REPO'"
    log "WIF Provider creado"
fi

# Vincular SA con WIF
GCP_PROJECT_NUMBER=$(gcloud projects describe "$GCP_PROJECT_ID" --format="value(projectNumber)")
WIF_PROVIDER_FULL="projects/${GCP_PROJECT_NUMBER}/locations/global/workloadIdentityPools/${WIF_POOL}/providers/${WIF_PROVIDER}"

gcloud iam service-accounts add-iam-policy-binding "$SA_EMAIL" \
    --role="roles/iam.workloadIdentityUser" \
    --member="principalSet://iam.googleapis.com/projects/${GCP_PROJECT_NUMBER}/locations/global/workloadIdentityPools/${WIF_POOL}/attribute.repository/${GITHUB_REPO}" \
    --quiet >/dev/null 2>&1
log "Service Account vinculado a WIF"

# ─── 8. Configurar GitHub Secrets ────────────────────────────────────────────
log "Configurando GitHub Secrets en: $GITHUB_REPO"

gh secret set GCP_PROJECT_ID    --repo "$GITHUB_REPO" --body "$GCP_PROJECT_ID"
gh secret set GCS_BUCKET_NAME   --repo "$GITHUB_REPO" --body "$GCS_BUCKET_NAME"
gh secret set GCP_WIF_PROVIDER  --repo "$GITHUB_REPO" --body "$WIF_PROVIDER_FULL"
gh secret set GCP_SA_EMAIL      --repo "$GITHUB_REPO" --body "$SA_EMAIL"
gh secret set SECRET_KEY        --repo "$GITHUB_REPO" --body "$APP_SECRET_KEY"
gh secret set ADMIN_USERNAME    --repo "$GITHUB_REPO" --body "$APP_ADMIN_USERNAME"
gh secret set ADMIN_PASSWORD    --repo "$GITHUB_REPO" --body "$APP_ADMIN_PASSWORD"

# CORS_ORIGINS se dejará vacío por ahora — se llena después del primer deploy
if [[ -n "$APP_CORS_ORIGINS" ]]; then
    gh secret set CORS_ORIGINS --repo "$GITHUB_REPO" --body "$APP_CORS_ORIGINS"
    log "CORS_ORIGINS configurado"
else
    gh secret set CORS_ORIGINS --repo "$GITHUB_REPO" --body "*"
    warn "CORS_ORIGINS='*' (actualizar después del primer deploy con la URL real del frontend)"
fi

log "GitHub Secrets configurados"

# ─── 9. Resumen ─────────────────────────────────────────────────────────────
echo ""
echo "═══════════════════════════════════════════════════════════════"
echo "  Setup completado exitosamente"
echo "═══════════════════════════════════════════════════════════════"
echo ""
echo "  Proyecto GCP:      $GCP_PROJECT_ID"
echo "  Región:            $GCP_REGION"
echo "  Bucket GCS:        gs://$GCS_BUCKET_NAME"
echo "  Artifact Registry: $AR_REPO"
echo "  Service Account:   $SA_EMAIL"
echo "  WIF Provider:      $WIF_PROVIDER_FULL"
echo "  GitHub Repo:       $GITHUB_REPO"
echo ""
echo "  Siguiente paso:"
echo "    git push origin main"
echo "    → El workflow CD desplegará automáticamente a Cloud Run."
echo ""
echo "  Después del primer deploy, actualizar CORS_ORIGINS:"
echo "    FRONTEND_URL=\$(gcloud run services describe proyeccion-faena-web --region=$GCP_REGION --format='value(status.url)')"
echo "    gh secret set CORS_ORIGINS --repo $GITHUB_REPO --body \"\$FRONTEND_URL\""
echo ""
