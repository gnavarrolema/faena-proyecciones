"""
Configuración centralizada usando variables de entorno.
Compatible con Cloud Run (env vars inyectadas) y desarrollo local (.env).
"""
import os
from pathlib import Path

# Intentar cargar .env si existe (solo en desarrollo local)
try:
    from dotenv import load_dotenv
    env_path = Path(__file__).resolve().parent.parent / ".env"
    if env_path.exists():
        load_dotenv(env_path)
except ImportError:
    pass  # python-dotenv no instalado → producción, usa env vars directas


# ─── Storage ────────────────────────────────────────────────────────────────────
# "gcs" para Google Cloud Storage, "local" para filesystem local
STORAGE_BACKEND = os.getenv("STORAGE_BACKEND", "local")

# Google Cloud Storage
GCS_BUCKET_NAME = os.getenv("GCS_BUCKET_NAME", "")
GCS_PREFIX = os.getenv("GCS_PREFIX", "data/")  # prefijo dentro del bucket

# Almacenamiento local (desarrollo)
LOCAL_STORAGE_PATH = os.getenv(
    "LOCAL_STORAGE_PATH",
    str(Path(__file__).resolve().parent.parent / "local_storage")
)

# ─── Auth ───────────────────────────────────────────────────────────────────────
SECRET_KEY = os.getenv("SECRET_KEY", "vibe_coding_secret_key")
ADMIN_USERNAME = os.getenv("ADMIN_USERNAME", "admin")
ADMIN_PASSWORD = os.getenv("ADMIN_PASSWORD", "admin123")

# ─── Server ─────────────────────────────────────────────────────────────────────
PORT = int(os.getenv("PORT", "5000"))
HOST = os.getenv("HOST", "0.0.0.0")
CORS_ORIGINS = [o.strip() for o in os.getenv("CORS_ORIGINS", "*").split(",") if o.strip()]

# allow_credentials=True es inválido cuando origins contiene "*" (estándar CORS).
# En dev/Docker se usa proxy (Vite/Nginx), por lo que no se necesitan credenciales
# vía CORS. En producción se debe configurar el origin exacto del frontend.
CORS_ALLOW_CREDENTIALS = "*" not in CORS_ORIGINS

# ─── Validación de seguridad ────────────────────────────────────────────────────
# K_SERVICE es una variable que Cloud Run inyecta automáticamente.
# Si estamos en Cloud Run pero con storage local, los datos se perderán.
if os.getenv("K_SERVICE") and STORAGE_BACKEND == "local":
    import warnings
    warnings.warn(
        "⚠️ STORAGE_BACKEND='local' detectado en Cloud Run. "
        "Los datos NO persistirán entre reinicios del contenedor. "
        "Configure STORAGE_BACKEND='gcs' y GCS_BUCKET_NAME para producción.",
        RuntimeWarning,
        stacklevel=1,
    )
