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


def test_ganancia_necesaria_desde_hoy():
    """
    Cuando la oferta tiene días de antigüedad, ganancia_necesaria debe
    calcularse desde la fecha actual, no desde la fecha de la oferta.

    Caso: MARTINA galpón 8, núcleo 2, sexo M.
    - fecha_peso: 14/3, dias_proy: 5, fecha_base: 19/3
    - edad_proyectada: 26, peso_muestreo_proy: 1.56, gdp: 0.070
    - fecha_referencia: 26/3 (7 días después)
    - edad_actual: 33, dias_restantes a edad_ideal_macho(40): 7
    - peso_estimado_hoy: 1.56 + 7*0.070 = 2.05
    - dias_efectivos_restantes: 7 - 1 = 6
    - peso_target (M): 2.80/0.96 = 2.91667
    - gan_necesaria: (2.91667 - 2.05 - 0.045) / 6 ≈ 0.1369
    """
    params = Parametros()  # edad_ideal_macho=40, peso_min_faena=2.80
    lote = LoteOferta(
        fecha_peso=date(2026, 3, 14),
        granja="MARTINA",
        galpon=8,
        nucleo=2,
        cantidad=12751,
        sexo="M",
        edad_proyectada=26,
        peso_muestreo_proy=1.56,
        ganancia_diaria=0.070,
        dias_proyectados=5,
        edad_real=21,
        peso_muestreo_real=1.21,
        fecha_ingreso=date(2026, 2, 20),
    )
    fecha_ref = date(2026, 3, 26)  # 7 días después de la oferta
    result = calcular_alerta_temprana([lote], params, fecha_referencia=fecha_ref)

    r = result["lotes"][0]
    assert r["edad_actual"] == 33
    assert r["dias_restantes"] == 7  # 40 - 33

    # Ganancia necesaria debe ser ~0.1369 (desde HOY), no ~0.100 (desde oferta)
    assert r["ganancia_necesaria"] > 0.13, (
        f"ganancia_necesaria={r['ganancia_necesaria']:.4f} debería ser ~0.137 "
        f"(calculada desde hoy), no ~0.100 (promedio desde la oferta)"
    )
    assert round(r["ganancia_necesaria"], 2) == 0.14


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


def test_resumen_galpon_nucleo():
    """El resumen por granja/galpón/núcleo se agrega y ordena correctamente."""
    params = Parametros()
    lotes = [
        _lote(galpon=1, granja="A", peso=2.81),
        _lote(galpon=1, granja="A", peso=1.50, edad=30, ganancia=0.060),
        _lote(galpon=2, granja="A", peso=2.90),
    ]
    result = calcular_alerta_temprana(lotes, params, fecha_referencia=FECHA_REF)
    assert "galpones_nucleos" in result
    assert len(result["galpones_nucleos"]) == 2

    gn_1 = next(g for g in result["galpones_nucleos"] if g["granja"] == "A" and g["galpon"] == 1 and g["nucleo"] == 1)
    gn_2 = next(g for g in result["galpones_nucleos"] if g["granja"] == "A" and g["galpon"] == 2 and g["nucleo"] == 1)

    assert gn_1["total_lotes"] == 2
    assert gn_1["lotes_rojo"] == 1
    assert gn_1["lotes_verde"] == 1
    assert gn_1["pct_pollos_rojo"] == 50.0
    assert gn_2["nivel"] == "verde"


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
