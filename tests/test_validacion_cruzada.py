"""Tests para la validación cruzada oferta ↔ producción al momento de la carga."""
from datetime import date, timedelta

import pytest
from backend.main import _validar_cruce_oferta, _validar_cruce_produccion
from backend.calculo import LoteOferta
from backend.parser_produccion import SemanaProduccion, DIAS_HASTA_FAENA
from backend import storage


@pytest.fixture(autouse=True)
def clean_storage(tmp_path, monkeypatch):
    """Usa un directorio temporal para storage en cada test."""
    monkeypatch.setenv("STORAGE_BACKEND", "local")
    monkeypatch.setenv("LOCAL_STORAGE_PATH", str(tmp_path))
    storage._storage_instance = storage.LocalStorage(str(tmp_path))
    yield
    storage._storage_instance = None


def _lote(
    granja="GRANJA_A",
    cantidad=5000,
    fecha_peso=date(2026, 3, 16),
    fecha_ingreso=date(2026, 2, 2),
    edad_real=42,
    edad_proyectada=42,
) -> LoteOferta:
    return LoteOferta(
        fecha_peso=fecha_peso,
        granja=granja,
        galpon=1,
        nucleo=1,
        cantidad=cantidad,
        sexo="M",
        edad_proyectada=edad_proyectada,
        peso_muestreo_proy=2.80,
        ganancia_diaria=0.09,
        dias_proyectados=0,
        edad_real=edad_real,
        peso_muestreo_real=2.80,
        fecha_ingreso=fecha_ingreso,
    )


def _guardar_produccion(fecha_desde: date, pollitos: int):
    sem = SemanaProduccion(
        fecha_desde=fecha_desde,
        fecha_hasta=fecha_desde + timedelta(days=6),
        pollitos_cargados=pollitos,
    )
    storage.save_produccion([sem.model_dump()])


# ─── _validar_cruce_oferta ──────────────────────────────────────────────────────

def test_cruce_oferta_sin_produccion_retorna_none():
    """Sin datos de producción, la validación retorna None."""
    ofertas = [_lote()]
    result = _validar_cruce_oferta(ofertas)
    assert result is None


def test_cruce_oferta_con_superavit():
    """Oferta menor a producción → factibilidad sin déficit."""
    fecha_prod = date(2026, 2, 2)
    fecha_faena = fecha_prod + timedelta(days=DIAS_HASTA_FAENA)
    _guardar_produccion(fecha_prod, 100000)

    ofertas = [_lote(cantidad=30000, fecha_peso=fecha_faena)]
    result = _validar_cruce_oferta(ofertas)

    assert result is not None
    assert "factibilidad" in result
    assert result["factibilidad"]["encontrada"] is True
    assert result["factibilidad"]["deficit_peor"] is None


def test_cruce_oferta_con_deficit():
    """Oferta mayor a producción → factibilidad con déficit."""
    fecha_prod = date(2026, 2, 2)
    fecha_faena = fecha_prod + timedelta(days=DIAS_HASTA_FAENA)
    _guardar_produccion(fecha_prod, 100000)

    ofertas = [_lote(cantidad=96000, fecha_peso=fecha_faena)]
    result = _validar_cruce_oferta(ofertas)

    assert result is not None
    assert result["factibilidad"]["encontrada"] is True
    assert result["factibilidad"]["deficit_peor"] is not None
    assert result["factibilidad"]["deficit_peor"] > 0


def test_cruce_oferta_mortalidad_cohortes():
    """Si hay producción, se calculan cohortes de mortalidad."""
    fecha_prod = date(2026, 2, 2)
    _guardar_produccion(fecha_prod, 100000)

    ofertas = [
        _lote(granja="G1", cantidad=45000, fecha_ingreso=fecha_prod),
        _lote(granja="G2", cantidad=45000, fecha_ingreso=fecha_prod + timedelta(days=1)),
    ]
    result = _validar_cruce_oferta(ofertas)

    assert result is not None
    assert "mortalidad_cohortes" in result
    assert result["mortalidad_cohortes"]["total_cohortes"] >= 1


def test_cruce_oferta_consistencia_edad_ok():
    """Lotes con edad consistente no generan alertas."""
    fecha_ing = date(2026, 2, 2)
    fecha_peso = fecha_ing + timedelta(days=42)
    _guardar_produccion(fecha_ing, 100000)

    ofertas = [_lote(fecha_ingreso=fecha_ing, fecha_peso=fecha_peso, edad_real=42)]
    result = _validar_cruce_oferta(ofertas)

    # No debe haber alertas de consistencia de edad
    assert result is None or "consistencia_edad" not in result


def test_cruce_oferta_consistencia_edad_inconsistente():
    """Lotes con edad real diferente a (fecha_peso - fecha_ingreso) generan alerta."""
    fecha_ing = date(2026, 2, 2)
    fecha_peso = fecha_ing + timedelta(days=42)
    _guardar_produccion(fecha_ing, 100000)

    # edad_real=35 pero debería ser 42
    ofertas = [_lote(fecha_ingreso=fecha_ing, fecha_peso=fecha_peso, edad_real=35)]
    result = _validar_cruce_oferta(ofertas)

    assert result is not None
    assert "consistencia_edad" in result
    assert result["consistencia_edad"]["total"] == 1
    alerta = result["consistencia_edad"]["alertas"][0]
    assert alerta["edad_real"] == 35
    assert alerta["dias_calculados"] == 42
    assert alerta["diferencia"] == 7


def test_cruce_oferta_lista_vacia():
    """Con lista vacía de ofertas, retorna None."""
    _guardar_produccion(date(2026, 2, 2), 100000)
    result = _validar_cruce_oferta([])
    assert result is None


# ─── _validar_cruce_produccion ───────────────────────────────────────────────────

def test_cruce_produccion_sin_oferta_retorna_none():
    """Sin ofertas cargadas, la validación retorna None."""
    _guardar_produccion(date(2026, 2, 2), 100000)
    result = _validar_cruce_produccion()
    assert result is None


def test_cruce_produccion_con_oferta():
    """Con oferta existente, calcula factibilidad y mortalidad."""
    fecha_prod = date(2026, 2, 2)
    fecha_faena = fecha_prod + timedelta(days=DIAS_HASTA_FAENA)
    _guardar_produccion(fecha_prod, 100000)

    # Guardar ofertas en storage
    ofertas = [_lote(cantidad=80000, fecha_peso=fecha_faena, fecha_ingreso=fecha_prod)]
    storage.save_ofertas([o.model_dump() for o in ofertas])

    result = _validar_cruce_produccion()

    assert result is not None
    assert "factibilidad" in result
    assert result["factibilidad"]["encontrada"] is True


def test_cruce_produccion_detecta_deficit():
    """Producción insuficiente para la oferta existente."""
    fecha_prod = date(2026, 2, 2)
    fecha_faena = fecha_prod + timedelta(days=DIAS_HASTA_FAENA)
    _guardar_produccion(fecha_prod, 50000)

    ofertas = [_lote(cantidad=50000, fecha_peso=fecha_faena, fecha_ingreso=fecha_prod)]
    storage.save_ofertas([o.model_dump() for o in ofertas])

    result = _validar_cruce_produccion()

    assert result is not None
    fact = result["factibilidad"]
    assert fact["encontrada"] is True
    # 50000 * (1 - 0.065) = 46750, oferta = 50000, deficit = 3250
    assert fact["deficit_peor"] == 3250
