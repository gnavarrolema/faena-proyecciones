"""
Tests para la capa de persistencia (storage).
"""
import json
import os
import tempfile
import pytest
from datetime import date

from backend.storage import LocalStorage, DateEncoder, _serialize, _deserialize


@pytest.fixture
def temp_storage():
    """Crea un LocalStorage en directorio temporal."""
    with tempfile.TemporaryDirectory() as tmpdir:
        yield LocalStorage(base_path=tmpdir)


class TestDateEncoder:
    def test_date_serialization(self):
        data = {"fecha": date(2026, 2, 23)}
        result = json.dumps(data, cls=DateEncoder)
        assert '"2026-02-23"' in result

    def test_nested_dates(self):
        data = {"items": [{"fecha": date(2026, 1, 1)}, {"fecha": date(2026, 12, 31)}]}
        result = json.dumps(data, cls=DateEncoder)
        parsed = json.loads(result)
        assert parsed["items"][0]["fecha"] == "2026-01-01"
        assert parsed["items"][1]["fecha"] == "2026-12-31"


class TestLocalStorage:
    def test_save_and_load(self, temp_storage):
        data = {"key": "value", "number": 42}
        temp_storage.save("test", data)
        loaded = temp_storage.load("test")
        assert loaded == data

    def test_load_nonexistent(self, temp_storage):
        assert temp_storage.load("nonexistent") is None

    def test_exists(self, temp_storage):
        assert not temp_storage.exists("test")
        temp_storage.save("test", {"a": 1})
        assert temp_storage.exists("test")

    def test_delete(self, temp_storage):
        temp_storage.save("test", {"a": 1})
        assert temp_storage.exists("test")
        temp_storage.delete("test")
        assert not temp_storage.exists("test")

    def test_delete_nonexistent(self, temp_storage):
        # No debería lanzar error
        temp_storage.delete("nonexistent")

    def test_list_keys(self, temp_storage):
        temp_storage.save("ofertas", [])
        temp_storage.save("parametros", {})
        temp_storage.save("proyeccion", {})
        keys = temp_storage.list_keys()
        assert set(keys) == {"ofertas", "parametros", "proyeccion"}

    def test_list_keys_with_prefix(self, temp_storage):
        temp_storage.save("ofertas", [])
        temp_storage.save("parametros", {})
        keys = temp_storage.list_keys("ofert")
        assert keys == ["ofertas"]

    def test_save_and_load_bytes(self, temp_storage):
        data = b"binary content here"
        temp_storage.save_bytes("uploads/test.xlsx", data)
        loaded = temp_storage.load_bytes("uploads/test.xlsx")
        assert loaded == data

    def test_load_bytes_nonexistent(self, temp_storage):
        assert temp_storage.load_bytes("nonexistent") is None

    def test_complex_data_roundtrip(self, temp_storage):
        """Simula guardar y cargar datos de oferta con fechas."""
        ofertas = [
            {
                "fecha_peso": "2026-02-20",
                "granja": "Santa Rosa",
                "galpon": 1,
                "nucleo": 1,
                "cantidad": 15000,
                "sexo": "M",
                "edad_proyectada": 38,
                "peso_muestreo_proy": 2.5,
                "ganancia_diaria": 0.09,
                "dias_proyectados": 3,
                "edad_real": 35,
                "peso_muestreo_real": 2.23,
                "fecha_ingreso": "2026-01-15",
            }
        ]
        temp_storage.save("ofertas", ofertas)
        loaded = temp_storage.load("ofertas")
        assert len(loaded) == 1
        assert loaded[0]["granja"] == "Santa Rosa"
        assert loaded[0]["cantidad"] == 15000

    def test_overwrite(self, temp_storage):
        temp_storage.save("test", {"version": 1})
        temp_storage.save("test", {"version": 2})
        loaded = temp_storage.load("test")
        assert loaded["version"] == 2

    def test_subdirectory_keys(self, temp_storage):
        """Verifica que claves con / crean subdirectorios."""
        temp_storage.save("uploads/2026/file1", {"name": "f1"})
        loaded = temp_storage.load("uploads/2026/file1")
        assert loaded["name"] == "f1"
