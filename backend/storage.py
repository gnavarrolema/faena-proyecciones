"""
Capa de persistencia de datos.

Provee una interfaz abstracta con dos implementaciones:
- LocalStorage: guarda archivos JSON en disco (desarrollo local)
- GCSStorage: guarda archivos JSON en Google Cloud Storage (producción)

Ambas comparten la misma API: save/load/delete/list, lo que permite
cambiar de backend con solo una variable de entorno (STORAGE_BACKEND).
"""
from __future__ import annotations

import json
import os
import logging
from abc import ABC, abstractmethod
from datetime import date, datetime
from pathlib import Path
from typing import Any, Optional

logger = logging.getLogger(__name__)


# ─── JSON serializer personalizado ──────────────────────────────────────────────

class DateEncoder(json.JSONEncoder):
    """Serializa date/datetime a ISO 8601."""
    def default(self, obj):
        if isinstance(obj, (date, datetime)):
            return obj.isoformat()
        return super().default(obj)


def _serialize(data: Any) -> str:
    return json.dumps(data, cls=DateEncoder, ensure_ascii=False, indent=2)


def _deserialize(raw: str) -> Any:
    return json.loads(raw)


# ─── Interfaz abstracta ─────────────────────────────────────────────────────────

class StorageBackend(ABC):
    """Interfaz que deben cumplir todos los backends de almacenamiento."""

    @abstractmethod
    def save(self, key: str, data: Any) -> None:
        """Guarda data (dict/list) bajo la clave `key` (e.g. 'ofertas')."""
        ...

    @abstractmethod
    def load(self, key: str) -> Optional[Any]:
        """Carga data bajo la clave `key`. Retorna None si no existe."""
        ...

    @abstractmethod
    def delete(self, key: str) -> None:
        """Elimina la clave `key`."""
        ...

    @abstractmethod
    def exists(self, key: str) -> bool:
        """Verifica si existe la clave `key`."""
        ...

    @abstractmethod
    def list_keys(self, prefix: str = "") -> list[str]:
        """Lista las claves que empiezan con `prefix`."""
        ...

    @abstractmethod
    def save_bytes(self, key: str, data: bytes, content_type: str = "application/octet-stream") -> None:
        """Guarda datos binarios (e.g. archivos Excel originales)."""
        ...

    @abstractmethod
    def load_bytes(self, key: str) -> Optional[bytes]:
        """Carga datos binarios. Retorna None si no existe."""
        ...


# ─── Implementación: Filesystem local ───────────────────────────────────────────

class LocalStorage(StorageBackend):
    """Almacena JSON en archivos locales. Ideal para desarrollo."""

    def __init__(self, base_path: str):
        self.base_path = Path(base_path)
        self.base_path.mkdir(parents=True, exist_ok=True)
        logger.info(f"LocalStorage inicializado en: {self.base_path}")

    def _key_path(self, key: str) -> Path:
        path = self.base_path / f"{key}.json"
        path.parent.mkdir(parents=True, exist_ok=True)
        return path

    def _bin_path(self, key: str) -> Path:
        path = self.base_path / key
        path.parent.mkdir(parents=True, exist_ok=True)
        return path

    def save(self, key: str, data: Any) -> None:
        path = self._key_path(key)
        path.write_text(_serialize(data), encoding="utf-8")
        logger.debug(f"LocalStorage: guardado {key}")

    def load(self, key: str) -> Optional[Any]:
        path = self._key_path(key)
        if not path.exists():
            return None
        raw = path.read_text(encoding="utf-8")
        return _deserialize(raw)

    def delete(self, key: str) -> None:
        path = self._key_path(key)
        if path.exists():
            path.unlink()
            logger.debug(f"LocalStorage: eliminado {key}")

    def exists(self, key: str) -> bool:
        return self._key_path(key).exists()

    def list_keys(self, prefix: str = "") -> list[str]:
        keys = []
        for p in self.base_path.rglob("*.json"):
            rel = p.relative_to(self.base_path).with_suffix("").as_posix()
            if rel.startswith(prefix):
                keys.append(rel)
        return keys

    def save_bytes(self, key: str, data: bytes, content_type: str = "application/octet-stream") -> None:
        path = self._bin_path(key)
        path.write_bytes(data)
        logger.debug(f"LocalStorage: guardado binario {key}")

    def load_bytes(self, key: str) -> Optional[bytes]:
        path = self._bin_path(key)
        if not path.exists():
            return None
        return path.read_bytes()


# ─── Implementación: Google Cloud Storage ────────────────────────────────────────

class GCSStorage(StorageBackend):
    """Almacena JSON y binarios en Google Cloud Storage. Para producción."""

    def __init__(self, bucket_name: str, prefix: str = "data/"):
        from google.cloud import storage as gcs_lib
        self.client = gcs_lib.Client()
        self.bucket = self.client.bucket(bucket_name)
        self.prefix = prefix.rstrip("/") + "/" if prefix else ""
        logger.info(f"GCSStorage inicializado: bucket={bucket_name}, prefix={self.prefix}")

    def _blob_name(self, key: str, ext: str = ".json") -> str:
        return f"{self.prefix}{key}{ext}"

    def save(self, key: str, data: Any) -> None:
        blob = self.bucket.blob(self._blob_name(key))
        blob.upload_from_string(
            _serialize(data),
            content_type="application/json"
        )
        logger.debug(f"GCSStorage: guardado {key}")

    def load(self, key: str) -> Optional[Any]:
        blob = self.bucket.blob(self._blob_name(key))
        if not blob.exists():
            return None
        raw = blob.download_as_text(encoding="utf-8")
        return _deserialize(raw)

    def delete(self, key: str) -> None:
        blob = self.bucket.blob(self._blob_name(key))
        if blob.exists():
            blob.delete()
            logger.debug(f"GCSStorage: eliminado {key}")

    def exists(self, key: str) -> bool:
        blob = self.bucket.blob(self._blob_name(key))
        return blob.exists()

    def list_keys(self, prefix: str = "") -> list[str]:
        full_prefix = f"{self.prefix}{prefix}"
        blobs = self.client.list_blobs(self.bucket, prefix=full_prefix)
        keys = []
        for blob in blobs:
            # Remover prefijo global y extensión .json
            rel = blob.name
            if rel.startswith(self.prefix):
                rel = rel[len(self.prefix):]
            if rel.endswith(".json"):
                rel = rel[:-5]
            keys.append(rel)
        return keys

    def save_bytes(self, key: str, data: bytes, content_type: str = "application/octet-stream") -> None:
        blob = self.bucket.blob(self._blob_name(key, ext=""))
        blob.upload_from_string(data, content_type=content_type)
        logger.debug(f"GCSStorage: guardado binario {key}")

    def load_bytes(self, key: str) -> Optional[bytes]:
        blob = self.bucket.blob(self._blob_name(key, ext=""))
        if not blob.exists():
            return None
        return blob.download_as_bytes()


# ─── Factory ────────────────────────────────────────────────────────────────────

_storage_instance: Optional[StorageBackend] = None


def get_storage() -> StorageBackend:
    """
    Retorna la instancia singleton del storage según la configuración.
    Lazy initialization — se crea en la primera llamada.
    """
    global _storage_instance
    if _storage_instance is not None:
        return _storage_instance

    from .config import STORAGE_BACKEND, GCS_BUCKET_NAME, GCS_PREFIX, LOCAL_STORAGE_PATH

    if STORAGE_BACKEND == "gcs":
        if not GCS_BUCKET_NAME:
            raise ValueError(
                "STORAGE_BACKEND='gcs' pero GCS_BUCKET_NAME no está configurado. "
                "Defina la variable de entorno GCS_BUCKET_NAME."
            )
        _storage_instance = GCSStorage(
            bucket_name=GCS_BUCKET_NAME,
            prefix=GCS_PREFIX,
        )
    else:
        _storage_instance = LocalStorage(base_path=LOCAL_STORAGE_PATH)

    return _storage_instance


# ─── Data Access Layer (capa de acceso a datos específica) ───────────────────────

OFERTAS_KEY = "ofertas"
PARAMETROS_KEY = "parametros"
PROYECCION_KEY = "proyeccion"
UPLOADS_PREFIX = "uploads/"


def save_ofertas(ofertas_data: list[dict]) -> None:
    get_storage().save(OFERTAS_KEY, ofertas_data)


def load_ofertas() -> Optional[list[dict]]:
    return get_storage().load(OFERTAS_KEY)


def save_parametros(parametros_data: dict) -> None:
    get_storage().save(PARAMETROS_KEY, parametros_data)


def load_parametros() -> Optional[dict]:
    return get_storage().load(PARAMETROS_KEY)


def save_proyeccion(proyeccion_data: dict) -> None:
    get_storage().save(PROYECCION_KEY, proyeccion_data)


def load_proyeccion() -> Optional[dict]:
    return get_storage().load(PROYECCION_KEY)


def delete_proyeccion() -> None:
    get_storage().delete(PROYECCION_KEY)


def delete_ofertas() -> None:
    get_storage().delete(OFERTAS_KEY)


def save_upload(filename: str, content: bytes) -> str:
    """Guarda un archivo Excel subido. Retorna la key usada."""
    from datetime import datetime
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    key = f"{UPLOADS_PREFIX}{ts}_{filename}"
    get_storage().save_bytes(
        key, content,
        content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )
    return key
