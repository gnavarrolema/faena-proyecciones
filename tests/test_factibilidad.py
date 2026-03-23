"""Tests para la integración de factibilidad producción ↔ proyección."""
from datetime import date, timedelta

import pytest
from backend.main import _calcular_factibilidad
from backend.parser_produccion import (
    SemanaProduccion, simular_mortalidad, DIAS_HASTA_FAENA,
)
from backend import storage


@pytest.fixture(autouse=True)
def clean_storage(tmp_path, monkeypatch):
    """Usa un directorio temporal para storage en cada test."""
    monkeypatch.setenv("STORAGE_BACKEND", "local")
    monkeypatch.setenv("LOCAL_STORAGE_PATH", str(tmp_path))
    storage._storage_instance = storage.LocalStorage(str(tmp_path))
    yield
    storage._storage_instance = None


def _guardar_produccion(fecha_desde: date, pollitos: int):
    """Helper: guarda una semana de producción en storage."""
    sem = SemanaProduccion(
        fecha_desde=fecha_desde,
        fecha_hasta=fecha_desde + timedelta(days=6),
        pollitos_cargados=pollitos,
    )
    storage.save_produccion([sem.model_dump()])


# ─── Tests ───────────────────────────────────────────────────────────────────────

def test_sin_produccion_retorna_none():
    """Sin datos de producción cargados, retorna None."""
    result = _calcular_factibilidad(
        fecha_inicio_semana=date(2026, 3, 16),
        total_oferta=30000,
    )
    assert result is None


def test_sin_match_retorna_no_encontrada():
    """Si producción existe pero no matchea con la fecha, encontrada=False."""
    _guardar_produccion(date(2026, 1, 1), 100000)
    result = _calcular_factibilidad(
        fecha_inicio_semana=date(2026, 6, 1),  # muy lejos
        total_oferta=30000,
    )
    assert result is not None
    assert result.encontrada is False


def test_match_exacto_con_superavit():
    """Oferta menor a producción disponible → sin déficit."""
    fecha_prod = date(2026, 2, 2)
    fecha_faena = fecha_prod + timedelta(days=DIAS_HASTA_FAENA)
    _guardar_produccion(fecha_prod, 100000)

    result = _calcular_factibilidad(
        fecha_inicio_semana=fecha_faena,
        total_oferta=80000,
    )
    assert result.encontrada is True
    assert result.pollitos_cargados == 100000
    assert result.disponibles_mejor == 95500   # 100000 * (1 - 0.045)
    assert result.disponibles_peor == 92500    # 100000 * (1 - 0.075)
    assert result.deficit_peor is None
    assert result.cobertura_pct_peor == round(80000 / 92500 * 100, 1)


def test_match_con_deficit():
    """Oferta mayor a producción disponible → tiene déficit."""
    fecha_prod = date(2026, 2, 2)
    fecha_faena = fecha_prod + timedelta(days=DIAS_HASTA_FAENA)
    _guardar_produccion(fecha_prod, 100000)

    result = _calcular_factibilidad(
        fecha_inicio_semana=fecha_faena,
        total_oferta=96000,
    )
    assert result.encontrada is True
    assert result.deficit_peor == 96000 - 92500  # 3500
    assert result.cobertura_pct_peor == round(96000 / 92500 * 100, 1)


def test_tolerancia_3_dias():
    """Match funciona con hasta ±3 días de diferencia."""
    fecha_prod = date(2026, 2, 2)
    fecha_faena_exacta = fecha_prod + timedelta(days=DIAS_HASTA_FAENA)
    _guardar_produccion(fecha_prod, 50000)

    # +3 días → debe matchear
    result = _calcular_factibilidad(
        fecha_inicio_semana=fecha_faena_exacta + timedelta(days=3),
        total_oferta=40000,
    )
    assert result.encontrada is True

    # +4 días → no debe matchear
    result = _calcular_factibilidad(
        fecha_inicio_semana=fecha_faena_exacta + timedelta(days=4),
        total_oferta=40000,
    )
    assert result.encontrada is False


def test_coberturas_contiene_7_escenarios():
    """El campo coberturas tiene 7 entradas, una por tasa de mortalidad."""
    fecha_prod = date(2026, 2, 2)
    fecha_faena = fecha_prod + timedelta(days=DIAS_HASTA_FAENA)
    _guardar_produccion(fecha_prod, 100000)

    result = _calcular_factibilidad(
        fecha_inicio_semana=fecha_faena,
        total_oferta=90000,
    )
    assert result.coberturas is not None
    assert len(result.coberturas) == 7
    tasas = [c["tasa"] for c in result.coberturas]
    assert tasas == [4.5, 5.0, 5.5, 6.0, 6.5, 7.0, 7.5]

    # Cada cobertura es diferente
    coberturas = [c["cobertura_pct"] for c in result.coberturas]
    assert coberturas == sorted(coberturas)  # mayor mortalidad → mayor % cobertura


def test_coberturas_valores_correctos():
    """Los valores de cada escenario son consistentes."""
    fecha_prod = date(2026, 2, 2)
    fecha_faena = fecha_prod + timedelta(days=DIAS_HASTA_FAENA)
    _guardar_produccion(fecha_prod, 100000)

    result = _calcular_factibilidad(
        fecha_inicio_semana=fecha_faena,
        total_oferta=90000,
    )
    for c in result.coberturas:
        expected_disp = int(100000 * (1 - c["tasa"] / 100))
        assert c["disponibles"] == expected_disp
        expected_cob = round(90000 / expected_disp * 100, 1)
        assert c["cobertura_pct"] == expected_cob
