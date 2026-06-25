#!/usr/bin/env bash
# ═══════════════════════════════════════════════════════════════════════════════
# pausar_gcp.sh — Pausa el proyecto en Google Cloud para detener gastos
# ═══════════════════════════════════════════════════════════════════════════════
#
# Borra los recursos de GCP que generan consumo:
#   1. Servicios Cloud Run (api + web + previews *-pr-N si hubiera)
#   2. TODOS los repos de Artifact Registry (proyeccion-faena, gcr.io legacy,
#      cloud-run-source-deploy auto-generado)
#   3. Buckets auto-generados por Cloud Build y Cloud Run sources
#
# Conserva (no cobran o cuestan centavos):
#   • Bucket GCS de datos del usuario (proyeccion-faena-data)
#   • Service Account, WIF, APIs habilitadas, GitHub Secrets
#
# Costo esperado después de pausar: ~$0.0002 USD/mes (storage del bucket).
#
# Para reactivar: bash scripts/reactivar_gcp.sh
#
# Uso (desde la raíz del repo, en WSL Ubuntu 22.04):
#   chmod +x scripts/pausar_gcp.sh
#   ./scripts/pausar_gcp.sh
#
#   DRY_RUN=1 ./scripts/pausar_gcp.sh   # solo muestra qué haría
# ═══════════════════════════════════════════════════════════════════════════════

set -euo pipefail

PROJECT="faena-proyecciones"
REGION="us-central1"
DATA_BUCKET="proyeccion-faena-data"   # NUNCA borrar — datos del usuario
DRY_RUN="${DRY_RUN:-0}"

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

log()  { echo -e "${GREEN}[✓]${NC} $1"; }
warn() { echo -e "${YELLOW}[!]${NC} $1"; }
err()  { echo -e "${RED}[✗]${NC} $1"; exit 1; }

run() {
  if [[ "$DRY_RUN" == "1" ]]; then
    echo "  [DRY] $*"
  else
    eval "$@"
  fi
}

command -v gcloud >/dev/null 2>&1 || err "gcloud CLI no encontrado"

echo ""
echo "═══════════════════════════════════════════════════════════════"
echo "  Pausa de Infraestructura GCP — Proyección de Faena"
echo "═══════════════════════════════════════════════════════════════"
echo "  Proyecto:  $PROJECT"
echo "  Región:    $REGION"
[[ "$DRY_RUN" == "1" ]] && warn "Modo DRY_RUN — no se borra nada"
echo ""

gcloud config set project "$PROJECT" >/dev/null

# ─── 1. Borrar todos los servicios Cloud Run ────────────────────────────────
log "Buscando servicios Cloud Run en $REGION..."
mapfile -t SERVICES < <(
  gcloud run services list --region="$REGION" --format='value(metadata.name)' 2>/dev/null
)

if [[ "${#SERVICES[@]}" -eq 0 ]]; then
  warn "No hay servicios Cloud Run para borrar"
else
  for svc in "${SERVICES[@]}"; do
    log "Borrando Cloud Run: $svc"
    run "gcloud run services delete '$svc' --region='$REGION' --quiet"
  done
fi

# ─── 2. Borrar TODOS los repos de Artifact Registry ─────────────────────────
# Nota: en algunas versiones de gcloud el campo 'location' del formato value()
# viene vacío, por eso extraemos repo y location del path completo del 'name':
#   projects/<proj>/locations/<location>/repositories/<repo>
log "Buscando repositorios de Artifact Registry en todas las regiones..."
mapfile -t AR_PATHS < <(
  gcloud artifacts repositories list --format='value(name)' 2>/dev/null
)

if [[ "${#AR_PATHS[@]}" -eq 0 ]]; then
  warn "No hay repositorios de Artifact Registry para borrar"
else
  for path in "${AR_PATHS[@]}"; do
    repo_name="${path##*/repositories/}"        # último segmento
    location="${path##*/locations/}"            # quita prefijo hasta locations/
    location="${location%%/*}"                  # se queda con el primer segmento
    if [[ -z "$repo_name" || -z "$location" ]]; then
      warn "No se pudo parsear el repo de: $path (se omite)"
      continue
    fi
    log "Borrando AR repo: $repo_name (en $location)"
    run "gcloud artifacts repositories delete '$repo_name' --location='$location' --quiet"
  done
fi

# ─── 3. Borrar buckets auto-generados por Cloud Build / Cloud Run ───────────
log "Buscando buckets auto-generados..."
mapfile -t BUCKETS < <(
  gcloud storage buckets list --format='value(name)' 2>/dev/null
)

for bucket in "${BUCKETS[@]}"; do
  # Conservar el bucket de datos del usuario
  if [[ "$bucket" == "$DATA_BUCKET" ]]; then
    warn "Conservando bucket de datos: gs://$bucket"
    continue
  fi
  # Solo borrar buckets auto-generados conocidos (no cualquier bucket)
  if [[ "$bucket" == *"_cloudbuild" ]] || [[ "$bucket" == "run-sources-"* ]] || [[ "$bucket" == "gcf-sources-"* ]]; then
    log "Borrando bucket auto-generado: gs://$bucket"
    run "gcloud storage rm --recursive 'gs://$bucket' --quiet"
  else
    warn "Bucket no reconocido como auto-generado, se conserva: gs://$bucket"
  fi
done

# ─── 4. Resumen ─────────────────────────────────────────────────────────────
echo ""
echo "═══════════════════════════════════════════════════════════════"
echo "  Pausa completada"
echo "═══════════════════════════════════════════════════════════════"
echo ""
echo "  Costo esperado próximo mes: ~\$0.0002 USD (solo bucket GCS)"
echo ""
echo "  Para reactivar:"
echo "    bash scripts/reactivar_gcp.sh"
echo ""
