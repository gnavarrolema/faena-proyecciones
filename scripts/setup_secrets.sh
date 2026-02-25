#!/bin/bash
# Obtener project number y vincular SA con WIF, luego configurar GitHub Secrets

PROJECT_ID="faena-proyecciones"
SA_EMAIL="proyeccion-faena-sa@faena-proyecciones.iam.gserviceaccount.com"
GITHUB_REPO="gnavarrolema/faena-proyecciones"

# Obtener project number
PROJECT_NUMBER=$(gcloud projects describe "$PROJECT_ID" --format='value(projectNumber)')
echo "Project Number: $PROJECT_NUMBER"

WIF_PROVIDER="projects/${PROJECT_NUMBER}/locations/global/workloadIdentityPools/github-pool/providers/github-provider"
echo "WIF Provider: $WIF_PROVIDER"

# Vincular SA con WIF
echo "--- Vinculando SA con WIF ---"
gcloud iam service-accounts add-iam-policy-binding "$SA_EMAIL" \
  --role="roles/iam.workloadIdentityUser" \
  --member="principalSet://iam.googleapis.com/projects/${PROJECT_NUMBER}/locations/global/workloadIdentityPools/github-pool/attribute.repository/${GITHUB_REPO}" \
  --quiet
echo "SA vinculada"

# Generar SECRET_KEY
SECRET_KEY=$(openssl rand -hex 32)
echo "SECRET_KEY generada"

# Configurar GitHub Secrets
echo "--- Configurando GitHub Secrets ---"
gh secret set GCP_PROJECT_ID    --repo "$GITHUB_REPO" --body "$PROJECT_ID"
echo "  GCP_PROJECT_ID OK"
gh secret set GCS_BUCKET_NAME   --repo "$GITHUB_REPO" --body "proyeccion-faena-data"
echo "  GCS_BUCKET_NAME OK"
gh secret set GCP_WIF_PROVIDER  --repo "$GITHUB_REPO" --body "$WIF_PROVIDER"
echo "  GCP_WIF_PROVIDER OK"
gh secret set GCP_SA_EMAIL      --repo "$GITHUB_REPO" --body "$SA_EMAIL"
echo "  GCP_SA_EMAIL OK"
gh secret set SECRET_KEY        --repo "$GITHUB_REPO" --body "$SECRET_KEY"
echo "  SECRET_KEY OK"
gh secret set ADMIN_USERNAME    --repo "$GITHUB_REPO" --body "admin"
echo "  ADMIN_USERNAME OK"
gh secret set ADMIN_PASSWORD    --repo "$GITHUB_REPO" --body "admin123"
echo "  ADMIN_PASSWORD OK"
gh secret set CORS_ORIGINS      --repo "$GITHUB_REPO" --body "*"
echo "  CORS_ORIGINS OK"

echo ""
echo "=== SETUP COMPLETADO ==="
echo "WIF Provider: $WIF_PROVIDER"
echo "Secrets configurados en $GITHUB_REPO"
