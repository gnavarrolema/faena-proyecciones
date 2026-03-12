"""Tests para el sistema de escenarios."""
import json
import tempfile
import os
from pathlib import Path

from backend.storage import LocalStorage


def test_guardar_y_cargar_escenario():
    """Verificar el round-trip de guardar y cargar un escenario."""
    with tempfile.TemporaryDirectory() as tmpdir:
        st = LocalStorage(tmpdir)

        escenario_data = {
            "id": "test-001",
            "nombre": "Escenario de prueba",
            "descripcion": "Descripción",
            "fecha_creacion": "2026-03-11T12:00:00",
            "parametros": {"pollos_diarios_objetivo_min": 30000},
            "proyeccion": {"total_pollos_semana": 150000, "dias": []},
            "resumen": {"total_pollos": 150000, "cajas": 1200},
        }

        st.save("escenarios/test-001", escenario_data)
        loaded = st.load("escenarios/test-001")

        assert loaded is not None
        assert loaded["id"] == "test-001"
        assert loaded["nombre"] == "Escenario de prueba"
        assert loaded["resumen"]["total_pollos"] == 150000


def test_listar_escenarios():
    """Verificar que list_keys retorna los escenarios guardados."""
    with tempfile.TemporaryDirectory() as tmpdir:
        st = LocalStorage(tmpdir)

        st.save("escenarios/esc-001", {"id": "esc-001", "nombre": "A"})
        st.save("escenarios/esc-002", {"id": "esc-002", "nombre": "B"})
        st.save("escenarios/esc-003", {"id": "esc-003", "nombre": "C"})

        keys = st.list_keys("escenarios/")
        assert len(keys) == 3
        ids = [k.replace("escenarios/", "") for k in keys]
        assert set(ids) == {"esc-001", "esc-002", "esc-003"}


def test_eliminar_escenario():
    """Verificar que se puede eliminar un escenario."""
    with tempfile.TemporaryDirectory() as tmpdir:
        st = LocalStorage(tmpdir)

        st.save("escenarios/temp-001", {"id": "temp-001", "nombre": "Temporal"})
        assert st.exists("escenarios/temp-001")

        st.delete("escenarios/temp-001")
        assert not st.exists("escenarios/temp-001")
        assert st.load("escenarios/temp-001") is None
