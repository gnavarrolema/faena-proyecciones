# Pausa y Reactivación del Proyecto en Google Cloud

Guía para **detener todo el consumo** del proyecto en GCP cuando no se va a usar
(vacaciones, pausas del negocio, ahorro de costos) y **reactivarlo rápido y sin
fricción** cuando se necesite de nuevo.

---

## Resumen ejecutivo

| Acción | Comando | Tiempo | Costo después |
|---|---|---|---|
| **Pausar** | `bash scripts/pausar_gcp.sh` | ~1 min | ~$0.0002/mes |
| **Reactivar** | `bash scripts/reactivar_gcp.sh` | 5-8 min | normal |

Los scripts se ejecutan desde **WSL Ubuntu 22.04** (donde están instalados
`gcloud` y `gh`).

---

## ¿Qué hace cada script?

### `pausar_gcp.sh`

Borra los recursos que generan consumo activo:

1. **Servicios Cloud Run** (`proyeccion-faena-api`, `proyeccion-faena-web` y
   cualquier preview `*-pr-N` que haya quedado).
2. **Repositorio de Artifact Registry** (`proyeccion-faena`) con todas las
   imágenes Docker que tenía adentro.

Conserva intactos:

- **Bucket GCS** `proyeccion-faena-data` (los datos del usuario; cuesta centavos).
- **Service Account** `proyeccion-faena-sa` con sus roles.
- **Workload Identity Federation** (pool y provider).
- **GitHub Secrets** del repositorio.
- **APIs habilitadas** del proyecto.

Esto significa que al reactivar **no hay que volver a configurar nada de
autenticación ni secrets** — solo recrear el repo de imágenes y disparar el
deploy.

### `reactivar_gcp.sh`

1. **Recrea el Artifact Registry** `proyeccion-faena` (lo necesita el workflow CD).
2. **Hace un commit vacío en `main` y lo pushea**, lo que dispara el workflow
   `cd.yml` de GitHub Actions, que compila las imágenes desde cero y despliega
   ambos servicios Cloud Run.

---

## Uso

### Pausar

Desde la raíz del repo, en WSL Ubuntu 22.04:

```bash
chmod +x scripts/pausar_gcp.sh
./scripts/pausar_gcp.sh
```

Si querés ver primero qué haría sin borrar nada:

```bash
DRY_RUN=1 ./scripts/pausar_gcp.sh
```

### Reactivar

Desde la raíz del repo. El script intenta hacer el `git push` solo si `git` está
disponible en WSL. Si trabajás con git desde PowerShell (como es habitual en
este proyecto), conviene saltar esa parte y hacer el push aparte:

```bash
# Paso 1: en WSL Ubuntu 22.04 — recrea el AR (sin hacer push)
SKIP_PUSH=1 bash scripts/reactivar_gcp.sh
```

```powershell
# Paso 2: en PowerShell — dispara el deploy
git commit --allow-empty -m "chore: reactivar deploy GCP"
git push origin main
```

El workflow CD aparecerá corriendo en
<https://github.com/gnavarrolema/faena-proyecciones/actions>.

Una vez completado (5-8 min), obtenés las URLs:

```bash
gcloud run services list --region=us-central1
```

---

## ¿Por qué no deshabilitar la facturación del proyecto?

La opción de **deshabilitar billing** garantiza un costo de exactamente $0,
pero introduce dos problemas serios para este caso:

1. **Pérdida de datos**: tras ~30 días sin facturación, Google empieza a
   eliminar recursos del proyecto, incluido el bucket GCS con los datos del
   usuario.
2. **Reactivación frágil**: puede desactivar APIs y romper el binding entre la
   Service Account y Workload Identity Federation. Reactivar requiere
   verificar que CI/CD vuelva a funcionar.

El ahorro adicional es despreciable: después de correr `pausar_gcp.sh` el costo
pasivo es de ~$0.0002 USD/mes (medio centavo al año por los 7 MiB del bucket).
No vale la pena el riesgo.

**Recomendación alternativa**: configurar una **alerta de presupuesto** en
[Billing → Budgets & alerts](https://console.cloud.google.com/billing/budgets)
con monto de $1 USD/mes. Si por error queda algo corriendo, Google avisa por
email antes de que sea un problema.

---

## Costo detallado tras pausar

| Recurso | Estado | Costo aproximado |
|---|---|---|
| Cloud Run (api + web) | borrado | $0 |
| Artifact Registry `proyeccion-faena` | borrado | $0 |
| Artifact Registry `cloud-run-source-deploy` | vacío | $0 |
| Bucket `proyeccion-faena-data` (~7 MiB) | conservado | ~$0.0002/mes |
| Service Account, WIF, APIs | conservados | gratis |
| **Total** | | **~$0.0002/mes** |

---

## Notas operativas

- El cargo del **1 de cada mes** corresponde al **consumo del mes anterior**
  (facturación en arrears de GCP). Si pausás a mediados de mes, el cargo del
  mes siguiente todavía incluirá los días que el servicio estuvo activo.
- La **URL pública de Cloud Run** puede cambiar de hash al reactivar
  (`-qvhjcsv7ja-` puede ser otro). El workflow CD actualiza automáticamente la
  variable `CORS_ORIGINS` del backend con la nueva URL del frontend, así que no
  hay que tocar nada manualmente.
- Si en el futuro hace falta una pausa **más larga** (varios meses) y se quiere
  evitar incluso el costo simbólico del bucket, conviene:
  1. Descargar el contenido del bucket localmente.
  2. Borrar el bucket.
  3. Re-correr `scripts/setup_infra.sh` al reactivar (es idempotente y recrea
     lo que falte).
