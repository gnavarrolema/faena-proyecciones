#!/usr/bin/env bash
# ═══════════════════════════════════════════════════════════════════════════════
# reactivar_gcp.sh — Reactiva el proyecto en Google Cloud después de pausar
# ═══════════════════════════════════════════════════════════════════════════════
#
# Pasos que ejecuta:
#   1. Recrea el repositorio de Artifact Registry (si fue borrado)
#   2. Dispara el workflow CD de GitHub Actions para redeplegar Cloud Run
#      (commit vacío + push a main)
#
# Tiempo total estimado: 5-8 min (rebuild completo de imágenes + deploy).
#
# Uso (desde la raíz del repo, en WSL Ubuntu 22.04):
#   chmod +x scripts/reactivar_gcp.sh
#   ./scripts/reactivar_gcp.sh
#
#   SKIP_PUSH=1 ./scripts/reactivar_gcp.sh   # solo recrea AR, no hace push
# ═══════════════════════════════════════════════════════════════════════════════

set -euo pipefail

PROJECT="faena-proyecciones"
REGION="us-central1"
AR_REPO="proyeccion-faena"
SKIP_PUSH="${SKIP_PUSH:-0}"

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

log()  { echo -e "${GREEN}[✓]${NC} $1"; }
warn() { echo -e "${YELLOW}[!]${NC} $1"; }
err()  { echo -e "${RED}[✗]${NC} $1"; exit 1; }

command -v gcloud >/dev/null 2>&1 || err "gcloud CLI no encontrado"

echo ""
echo "═══════════════════════════════════════════════════════════════"
echo "  Reactivación de Infraestructura GCP — Proyección de Faena"
echo "═══════════════════════════════════════════════════════════════"
echo ""

gcloud config set project "$PROJECT" >/dev/null

# ─── 1. Recrear Artifact Registry si no existe ──────────────────────────────
if gcloud artifacts repositories describe "$AR_REPO" --location="$REGION" >/dev/null 2>&1; then
  warn "Artifact Registry '$AR_REPO' ya existe — no se recrea"
else
  log "Creando Artifact Registry: $AR_REPO"
  gcloud artifacts repositories create "$AR_REPO" \
    --repository-format=docker \
    --location="$REGION" \
    --description="Imágenes Docker de Proyección Faena"
  log "Artifact Registry creado"
fi

# ─── 2. Disparar deploy via push a main ─────────────────────────────────────
if [[ "$SKIP_PUSH" == "1" ]]; then
  warn "SKIP_PUSH=1 — no se dispara el deploy"
  echo ""
  echo "  Para disparar el deploy manualmente, en PowerShell:"
  echo "    git commit --allow-empty -m \"chore: reactivar deploy\""
  echo "    git push origin main"
  exit 0
fi

if ! command -v git >/dev/null 2>&1; then
  warn "git no está disponible en WSL — hacé el push desde PowerShell:"
  echo "    git commit --allow-empty -m \"chore: reactivar deploy\""
  echo "    git push origin main"
  exit 0
fi

log "Disparando deploy con commit vacío en main..."
git commit --allow-empty -m "chore: reactivar deploy GCP"
git push origin main

# ─── 3. Resumen ─────────────────────────────────────────────────────────────
echo ""
echo "═══════════════════════════════════════════════════════════════"
echo "  Reactivación iniciada"
echo "═══════════════════════════════════════════════════════════════"
echo ""
echo "  El workflow CD está corriendo en GitHub Actions."
echo "  Tiempo estimado: 5-8 min"
echo ""
echo "  Seguí el progreso en:"
echo "    https://github.com/gnavarrolema/faena-proyecciones/actions"
echo ""
echo "  Una vez completado, obtené las URLs con:"
echo "    gcloud run services list --region=$REGION"
echo ""
