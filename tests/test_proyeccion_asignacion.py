from datetime import date

from backend.calculo import (
    LoteOferta, Parametros, SemanaFaena,
    generar_proyeccion, aplicar_ajuste_martes,
    calcular_lote_proyectado,
)


def _lote(cantidad: int, galpon: int, edad_proyectada: int = 40, peso: float = 2.95,
           ganancia: float = 0.0, granja: str = "TEST", sexo: str = "M") -> LoteOferta:
    return LoteOferta(
        fecha_peso=date(2026, 2, 23),
        granja=granja,
        galpon=galpon,
        nucleo=1,
        cantidad=cantidad,
        sexo=sexo,
        edad_proyectada=edad_proyectada,
        peso_muestreo_proy=peso,
        ganancia_diaria=ganancia,
        dias_proyectados=0,
        edad_real=edad_proyectada,
        peso_muestreo_real=peso,
        fecha_ingreso=date(2026, 1, 10),
    )


def test_respeta_tope_diario_maximo_y_reporta_no_asignados():
    ofertas = [
        _lote(23000, 1),
        _lote(23000, 2),
        _lote(36000, 3),
    ]

    params = Parametros(
        pollos_diarios_objetivo_min=25000,
        pollos_diarios_objetivo_max=35000,
        edad_min_faena=38,
        edad_max_faena=43,
        peso_min_faena=2.8,
        peso_max_faena=3.2,
    )

    semana = generar_proyeccion(
        ofertas=ofertas,
        fecha_inicio_semana=date(2026, 2, 23),
        dias_faena=6,
        pollos_por_dia=30000,
        params=params,
    )

    assert all(d.total_pollos <= params.pollos_diarios_objetivo_max for d in semana.dias)
    assert len(semana.lotes_no_asignados) == 1
    assert semana.lotes_no_asignados[0].cantidad == 36000
    assert "tope diario máximo" in semana.lotes_no_asignados[0].motivo


def test_descuento_sofia_no_afecta_asignacion_diaria():
    ofertas = [
        _lote(23000, 1),
        _lote(23000, 2),
        _lote(23000, 3),
    ]

    params_a = Parametros(descuento_sofia=10000)
    params_b = Parametros(descuento_sofia=5000)

    semana_a = generar_proyeccion(
        ofertas=ofertas,
        fecha_inicio_semana=date(2026, 2, 23),
        dias_faena=6,
        pollos_por_dia=30000,
        params=params_a,
    )

    semana_b = generar_proyeccion(
        ofertas=ofertas,
        fecha_inicio_semana=date(2026, 2, 23),
        dias_faena=6,
        pollos_por_dia=30000,
        params=params_b,
    )

    assert [d.total_pollos for d in semana_a.dias] == [d.total_pollos for d in semana_b.dias]
    assert semana_a.sofia == semana_a.total_pollos_semana - 10000
    assert semana_b.sofia == semana_b.total_pollos_semana - 5000


def test_lote_proyectado_preserva_datos_originales():
    """Verifica que calcular_lote_proyectado almacena los datos originales de la oferta."""
    oferta = _lote(15000, 1, ganancia=0.085)
    params = Parametros()
    lote = calcular_lote_proyectado(oferta, date(2026, 2, 25), params)

    assert lote.fecha_peso_original == date(2026, 2, 23)
    assert lote.ganancia_diaria_original == 0.085
    assert lote.fecha_ingreso_original == date(2026, 1, 10)


def test_heavier_lots_assigned_to_earlier_days_on_equal_deficit():
    """Lotes más pesados deben ir a días más tempranos cuando los déficits son iguales."""
    ofertas = [
        _lote(10000, 1, peso=3.15),  # pesado
        _lote(10000, 2, peso=2.85),  # liviano
    ]
    params = Parametros(
        pollos_diarios_objetivo_min=25000,
        pollos_diarios_objetivo_max=35000,
        edad_min_faena=38,
        edad_max_faena=43,
        peso_min_faena=2.8,
        peso_max_faena=3.2,
    )
    semana = generar_proyeccion(
        ofertas=ofertas,
        fecha_inicio_semana=date(2026, 2, 23),
        dias_faena=6,
        pollos_por_dia=30000,
        params=params,
    )
    # El lote más pesado (galpon 1) debería estar en un día anterior al más liviano
    dia_pesado = None
    dia_liviano = None
    for d_idx, dia in enumerate(semana.dias):
        for lote in dia.lotes:
            if lote.galpon == 1:
                dia_pesado = d_idx
            elif lote.galpon == 2:
                dia_liviano = d_idx
    if dia_pesado is not None and dia_liviano is not None:
        assert dia_pesado <= dia_liviano, (
            f"Lote pesado en día {dia_pesado}, lote liviano en día {dia_liviano}"
        )


def test_ajuste_martes_detecta_fuera_de_rango_post_ajuste():
    """El ajuste del martes debe alertar si un lote queda fuera de rango tras actualización."""
    params = Parametros(
        pollos_diarios_objetivo_min=25000,
        pollos_diarios_objetivo_max=35000,
        edad_min_faena=38,
        edad_max_faena=43,
        peso_min_faena=2.80,
        peso_max_faena=3.20,
    )

    # Generar proyección con oferta del jueves
    ofertas_jueves = [_lote(15000, 1, peso=2.95)]
    semana = generar_proyeccion(
        ofertas=ofertas_jueves,
        fecha_inicio_semana=date(2026, 2, 23),
        dias_faena=6,
        pollos_por_dia=30000,
        params=params,
    )

    # Oferta del martes: el lote ahora tiene peso mucho menor (fuera de rango)
    ofertas_martes = [_lote(15000, 1, peso=2.30)]
    resultado, resumen = aplicar_ajuste_martes(ofertas_martes, semana, params)

    # Debe detectar que el lote está fuera de rango tras el ajuste
    assert resumen.lotes_fuera_rango_post_ajuste > 0
    assert len(resumen.detalle_fuera_rango_post_ajuste) > 0
    assert "Peso" in resumen.detalle_fuera_rango_post_ajuste[0]["alerta"]
