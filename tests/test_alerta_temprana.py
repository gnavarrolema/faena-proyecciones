"""Tests para la funcionalidad de Alerta Temprana."""
from datetime import date
from backend.calculo import Parametros, LoteOferta, calcular_alerta_temprana

# Fecha de referencia fija: igual a fecha_base de los lotes (fecha_peso + dias_proyectados)
# para que edad_actual == edad_proyectada y los tests sean determinísticos.
FECHA_REF = date(2026, 3, 19)


def _lote(galpon=1, sexo="M", edad=36, peso=2.81, ganancia=0.09, granja="TEST"):
    return LoteOferta(
        fecha_peso=date(2026, 3, 18),
        granja=granja,
        galpon=galpon,
        nucleo=1,
        cantidad=10000,
        sexo=sexo,
        edad_proyectada=edad,
        peso_muestreo_proy=peso,
        ganancia_diaria=ganancia,
        dias_proyectados=1,
        edad_real=edad - 1,
        peso_muestreo_real=peso - 0.09,
        fecha_ingreso=date(2026, 2, 10),
    )


def test_lote_normal_macho():
    """Macho con buen peso y ganancia => verde."""
    params = Parametros()
    result = calcular_alerta_temprana([_lote(peso=2.81, ganancia=0.09)], params, fecha_referencia=FECHA_REF)
    assert result["total_lotes"] == 1
    assert result["lotes"][0]["nivel"] == "verde"
    assert result["lotes_ok"] == 1


def test_lote_peso_muy_bajo_macho():
    """Macho joven con peso muy bajo => rojo (no llega ni a edad max)."""
    params = Parametros()
    lote = _lote(galpon=1, edad=30, peso=1.50, ganancia=0.060)
    result = calcular_alerta_temprana([lote], params, fecha_referencia=FECHA_REF)
    assert result["lotes"][0]["nivel"] == "rojo"
    assert result["alertas_rojas"] == 1


def test_lote_peso_ajustado_hembra():
    """Hembra con peso bajo pero no imposible => amarillo."""
    params = Parametros()
    lote = _lote(galpon=1, sexo="H", edad=35, peso=2.20, ganancia=0.065)
    result = calcular_alerta_temprana([lote], params, fecha_referencia=FECHA_REF)
    nivel = result["lotes"][0]["nivel"]
    assert nivel in ("rojo", "amarillo"), f"Expected rojo or amarillo, got {nivel}"


def test_lote_sobrepeso():
    """Lote con peso alto que excederá el máximo => amarillo o rojo."""
    params = Parametros()
    lote = _lote(galpon=1, sexo="M", edad=36, peso=3.10, ganancia=0.11)
    result = calcular_alerta_temprana([lote], params, fecha_referencia=FECHA_REF)
    nivel = result["lotes"][0]["nivel"]
    assert nivel in ("rojo", "amarillo"), f"Expected alert for overweight, got {nivel}"


def test_ganancia_necesaria_positiva():
    """La ganancia necesaria debe ser >= 0."""
    params = Parametros()
    lote = _lote(galpon=1, edad=33, peso=2.0, ganancia=0.075)
    result = calcular_alerta_temprana([lote], params, fecha_referencia=FECHA_REF)
    assert result["lotes"][0]["ganancia_necesaria"] >= 0


def test_lista_vacia():
    """Con lista vacía, devuelve resultado vacío."""
    result = calcular_alerta_temprana([], Parametros())
    assert result["total_lotes"] == 0
    assert result["lotes"] == []


def test_resumen_granjas():
    """El resumen por granja agrupa correctamente."""
    params = Parametros()
    lotes = [
        _lote(galpon=1, granja="A", peso=2.81),
        _lote(galpon=2, granja="A", peso=2.90),
        _lote(galpon=1, granja="B", peso=1.50, edad=30, ganancia=0.060),
    ]
    result = calcular_alerta_temprana(lotes, params, fecha_referencia=FECHA_REF)
    assert len(result["granjas"]) == 2
    granja_a = next(g for g in result["granjas"] if g["granja"] == "A")
    granja_b = next(g for g in result["granjas"] if g["granja"] == "B")
    assert granja_a["total_lotes"] == 2
    assert granja_b["total_lotes"] == 1
    assert granja_b["lotes_rojo"] > 0


def test_lotes_ya_en_edad_max_excluidos():
    """Lotes que ya pasaron la edad máxima no se analizan."""
    params = Parametros()
    lote = _lote(galpon=1, edad=44, peso=3.10, ganancia=0.09)
    result = calcular_alerta_temprana([lote], params, fecha_referencia=FECHA_REF)
    assert result["total_lotes"] == 0


def test_porcentaje_ok():
    """El porcentaje OK se calcula correctamente."""
    params = Parametros()
    lotes = [
        _lote(galpon=1, peso=2.81),  # ok
        _lote(galpon=2, peso=2.90),  # ok
    ]
    result = calcular_alerta_temprana(lotes, params, fecha_referencia=FECHA_REF)
    assert result["pct_ok"] == 100.0
