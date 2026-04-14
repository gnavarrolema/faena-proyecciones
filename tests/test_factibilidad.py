"""Tests para la integración de factibilidad producción ↔ proyección."""
from datetime import date, timedelta

import pytest
from backend.main import _calcular_factibilidad, _calcular_factibilidad_proyeccion
from backend.calculo import SemanaFaena, DiaFaena, LoteProyectado, Parametros
from backend.parser_produccion import (
    SemanaProduccion, simular_mortalidad, DIAS_HASTA_FAENA, calcular_fecha_faena_estimada,
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


def _lote_planificado(cantidad: int, fecha_faena: date, fecha_ingreso: date, compra_terceros: bool = False) -> LoteProyectado:
    return LoteProyectado(
        granja="GRANJA_A" if not compra_terceros else "TERCEROS",
        galpon=1,
        nucleo=1,
        cantidad=cantidad,
        sexo="M",
        edad_actual=42,
        peso_actual=2.8,
        fecha_fin_retiro=fecha_faena,
        edad_fin_retiro=42,
        diferencia_edad_ideal=0,
        peso_vivo_retiro=2.8,
        fecha_peso_original=fecha_faena,
        ganancia_diaria_original=0.09,
        fecha_ingreso_original=fecha_ingreso,
        es_compra_terceros=compra_terceros,
    )


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


def test_factibilidad_proyeccion_agrega_cohortes_planificadas():
    """La proyección activa debe sumar todas las cohortes realmente planificadas."""
    sem1 = date(2026, 2, 2)
    sem2 = date(2026, 2, 9)
    storage.save_produccion([
        SemanaProduccion(fecha_desde=sem1, fecha_hasta=sem1 + timedelta(days=6), pollitos_cargados=50000).model_dump(),
        SemanaProduccion(fecha_desde=sem2, fecha_hasta=sem2 + timedelta(days=6), pollitos_cargados=50000).model_dump(),
    ])

    fecha_faena = sem1 + timedelta(days=DIAS_HASTA_FAENA)
    semana = SemanaFaena(
        fecha_inicio=fecha_faena,
        fecha_fin=fecha_faena + timedelta(days=5),
        dias=[
            DiaFaena(
                fecha=fecha_faena,
                lotes=[
                    _lote_planificado(50000, fecha_faena, sem1),
                    _lote_planificado(50000, fecha_faena, sem2),
                ],
                total_pollos=100000,
            )
        ],
        total_pollos_semana=100000,
    )

    result = _calcular_factibilidad_proyeccion(semana)

    assert result is not None
    assert result.encontrada is True
    assert result.pollitos_cargados == 100000
    assert result.disponibles_peor == 92500
    assert result.deficit_peor == 7500
    assert result.total_semanas_referenciadas == 2
    assert result.metodo_cruce == "cohortes_planificadas"
    assert result.contexto == "plan_propio"


def test_factibilidad_proyeccion_excluye_compra_terceros():
    """Las compras a terceros no deben inflar la base comparada con producción propia."""
    fecha_prod = date(2026, 2, 2)
    fecha_faena = fecha_prod + timedelta(days=DIAS_HASTA_FAENA)
    _guardar_produccion(fecha_prod, 50000)

    semana = SemanaFaena(
        fecha_inicio=fecha_faena,
        fecha_fin=fecha_faena + timedelta(days=5),
        dias=[
            DiaFaena(
                fecha=fecha_faena,
                lotes=[
                    _lote_planificado(50000, fecha_faena, fecha_prod),
                    _lote_planificado(8000, fecha_faena, fecha_prod, compra_terceros=True),
                ],
                total_pollos=58000,
            )
        ],
        total_pollos_semana=58000,
    )

    result = _calcular_factibilidad_proyeccion(semana)

    assert result is not None
    assert result.total_oferta == 50000
    assert result.total_compra_terceros == 8000
    assert result.disponibles_peor == 46250
    assert result.deficit_peor == 3750


def test_factibilidad_respeta_parametros_produccion_configurables():
    """La factibilidad debe usar días y tasas configuradas en parámetros."""
    storage.save_parametros(Parametros(
        produccion_dias_hasta_faena=40,
        produccion_tolerancia_cruce_dias=1,
        produccion_mortalidad_min=0.02,
        produccion_mortalidad_max=0.04,
        produccion_mortalidad_paso=0.01,
    ).model_dump())

    fecha_prod = date(2026, 2, 2)
    _guardar_produccion(fecha_prod, 100000)
    fecha_referencia = calcular_fecha_faena_estimada(fecha_prod, 40)

    result = _calcular_factibilidad(
        fecha_inicio_semana=fecha_referencia,
        total_oferta=95000,
    )

    assert result is not None
    assert result.encontrada is True
    assert result.dias_hasta_faena_referencia == 40
    assert result.tolerancia_cruce_dias == 1
    assert [c["tasa"] for c in result.coberturas] == [2.0, 3.0, 4.0]
    assert result.disponibles_mejor == 98000
    assert result.disponibles_peor == 96000
    assert result.deficit_peor is None
