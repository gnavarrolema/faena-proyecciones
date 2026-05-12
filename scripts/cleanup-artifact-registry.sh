#!/usr/bin/env bash
# Limpieza manual de imagenes viejas en Artifact Registry.
#
# Uso (desde la raiz del repo):
#   bash scripts/cleanup-artifact-registry.sh                  # borra de verdad
#   DRY_RUN=1 bash scripts/cleanup-artifact-registry.sh        # solo lista
#   KEEP_LAST=20 bash scripts/cleanup-artifact-registry.sh     # cuantas mantener
#
# Mantiene las KEEP_LAST imagenes mas recientes de cada uno de los
# repositorios `backend` y `frontend`, ademas de la imagen actualmente
# desplegada en produccion (por seguridad, aunque no este en el top KEEP_LAST).
#
# Tambien existen cleanup policies declarativas en
# scripts/artifact-registry-cleanup-policies.json que se aplican
# periodicamente desde Artifact Registry sin intervencion manual. Este
# script sirve para limpiezas puntuales (por ejemplo, despues de bajar
# el KEEP_LAST configurado o despues de una avalancha de deploys).
set -euo pipefail

REGION="us-central1"
PROJECT="faena-proyecciones"
REPO="proyeccion-faena"
KEEP_LAST="${KEEP_LAST:-10}"
DRY_RUN="${DRY_RUN:-0}"

get_prod_digest() {
  local service="$1"
  local image
  image=$(gcloud run services describe "$service" --region "$REGION" \
    --format='value(spec.template.spec.containers[0].image)' 2>/dev/null || echo "")
  if [[ -z "$image" ]]; then return; fi
  if [[ "$image" == *"@sha256:"* ]]; then
    echo "${image##*@}"
  else
    local tag="${image##*:}"
    local repo_path="${image%:*}"
    gcloud artifacts docker images list "$repo_path" \
      --include-tags --filter="tags:${tag}" \
      --format='value(DIGEST)' 2>/dev/null | head -n 1
  fi
}

cleanup_image() {
  local image_name="$1"   # backend | frontend
  local service="$2"      # proyeccion-faena-api | proyeccion-faena-web
  local repo_path="${REGION}-docker.pkg.dev/${PROJECT}/${REPO}/${image_name}"

  echo "=== ${image_name} ==="
  local prod_digest
  prod_digest="$(get_prod_digest "$service" || echo "")"
  echo "  prod digest: ${prod_digest:-<no encontrado>}"

  mapfile -t all_digests < <(
    gcloud artifacts docker images list "$repo_path" \
      --format='value(DIGEST)' --sort-by=~CREATE_TIME 2>/dev/null
  )
  local total="${#all_digests[@]}"
  echo "  total imagenes: ${total}"

  declare -A keep
  local i
  for (( i=0; i<KEEP_LAST && i<total; i++ )); do
    keep["${all_digests[$i]}"]=1
  done
  if [[ -n "$prod_digest" ]]; then
    keep["$prod_digest"]=1
  fi

  local borrados=0
  for digest in "${all_digests[@]}"; do
    if [[ -n "${keep[$digest]:-}" ]]; then continue; fi
    if [[ "$DRY_RUN" == "1" ]]; then
      echo "  [DRY] borraria ${digest}"
    else
      gcloud artifacts docker images delete "${repo_path}@${digest}" --quiet --delete-tags 2>&1 | tail -n 1
    fi
    borrados=$((borrados + 1))
  done
  echo "  borradas: ${borrados} (mantenidas: $((total - borrados)))"
}

cleanup_image "backend" "proyeccion-faena-api"
cleanup_image "frontend" "proyeccion-faena-web"
echo "Listo."
