from datetime import date

from backend.calculo import LoteOferta, Parametros, generar_proyeccion


def _lote(cantidad: int, galpon: int, edad_proyectada: int = 40, peso: float = 2.95) -> LoteOferta:
    return LoteOferta(
        fecha_peso=date(2026, 2, 23),
        granja="TEST",
        galpon=galpon,
        nucleo=1,
        cantidad=cantidad,
        sexo="M",
        edad_proyectada=edad_proyectada,
        peso_muestreo_proy=peso,
        ganancia_diaria=0.0,
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
