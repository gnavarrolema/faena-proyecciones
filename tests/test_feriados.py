"""Tests para el módulo de feriados."""
from datetime import date

from backend.feriados import (
    obtener_feriados_nacionales,
    obtener_feriados_rango,
    generar_dias_habiles,
    _calcular_pascua,
)
from backend.calculo import (
    LoteOferta, Parametros, generar_proyeccion,
)


# ─── Tests unitarios del módulo feriados ──────────────────────────────────────

def test_feriados_nacionales_contiene_fechas_clave_2026():
    """Verifica que los feriados de 2026 incluyen las fechas inamovibles conocidas."""
    feriados = obtener_feriados_nacionales(2026)

    assert date(2026, 1, 1) in feriados, "Falta Año Nuevo"
    assert date(2026, 3, 24) in feriados, "Falta Día de la Memoria"
    assert date(2026, 4, 2) in feriados, "Falta Día de Malvinas"
    assert date(2026, 5, 1) in feriados, "Falta Día del Trabajador"
    assert date(2026, 5, 25) in feriados, "Falta Revolución de Mayo"
    assert date(2026, 6, 20) in feriados, "Falta Belgrano"
    assert date(2026, 7, 9) in feriados, "Falta Día de la Independencia"
    assert date(2026, 12, 25) in feriados, "Falta Navidad"
    assert date(2026, 12, 8) in feriados, "Falta Inmaculada Concepción"


def test_feriados_nacionales_incluye_carnaval_2026():
    """Carnaval 2026: lunes 16 y martes 17 de febrero."""
    feriados = obtener_feriados_nacionales(2026)
    assert date(2026, 2, 16) in feriados, "Falta Carnaval lunes"
    assert date(2026, 2, 17) in feriados, "Falta Carnaval martes"


def test_feriados_nacionales_incluye_viernes_santo_2026():
    """Viernes Santo 2026: 3 de abril."""
    feriados = obtener_feriados_nacionales(2026)
    assert date(2026, 4, 3) in feriados, "Falta Viernes Santo"


def test_pascua_2025():
    """Pascua 2025 es el 20 de abril."""
    assert _calcular_pascua(2025) == date(2025, 4, 20)


def test_pascua_2026():
    """Pascua 2026 es el 5 de abril."""
    assert _calcular_pascua(2026) == date(2026, 4, 5)


def test_feriados_rango_filtra_correctamente():
    """Solo debe retornar feriados dentro del rango."""
    feriados = obtener_feriados_rango(
        date(2026, 3, 23),  # lunes
        date(2026, 3, 28),  # sábado
    )
    # 24 de marzo es feriado nacional (Día de la Memoria)
    assert date(2026, 3, 24) in feriados
    # 25 de mayo NO está en este rango
    assert date(2026, 5, 25) not in feriados


def test_feriados_rango_con_custom():
    """Los feriados custom se combinan con los nacionales."""
    custom = [{"fecha": "2026-03-25", "descripcion": "Feriado puente"}]
    feriados = obtener_feriados_rango(
        date(2026, 3, 23),
        date(2026, 3, 28),
        feriados_custom=custom,
    )
    assert date(2026, 3, 24) in feriados  # nacional
    assert date(2026, 3, 25) in feriados  # custom
    assert feriados[date(2026, 3, 25)] == "Feriado puente"


def test_generar_dias_habiles_sin_feriados():
    """Sin feriados, genera 6 días consecutivos (lun-sáb)."""
    dias = generar_dias_habiles(date(2026, 3, 23), 6)
    assert len(dias) == 6
    assert dias[0] == date(2026, 3, 23)  # lunes
    assert dias[5] == date(2026, 3, 28)  # sábado


def test_generar_dias_habiles_salta_feriado():
    """Si el martes es feriado, genera lun, mié, jue, vie, sáb, lun."""
    feriados = {date(2026, 3, 24): "Día de la Memoria"}
    dias = generar_dias_habiles(date(2026, 3, 23), 6, feriados)
    assert len(dias) == 6
    assert date(2026, 3, 24) not in dias
    assert dias[0] == date(2026, 3, 23)  # lunes
    assert dias[1] == date(2026, 3, 25)  # miércoles (saltó martes)


def test_generar_dias_habiles_salta_domingo():
    """Los domingos se saltan automáticamente."""
    dias = generar_dias_habiles(date(2026, 3, 23), 7)
    # Lun-Sab + Lun siguiente (domingo se salta)
    assert len(dias) == 7
    assert date(2026, 3, 29) not in dias  # domingo


def test_generar_dias_habiles_sin_sabado():
    """Con incluir_sabado=False, genera solo lun-vie."""
    dias = generar_dias_habiles(date(2026, 3, 23), 5, incluir_sabado=False)
    assert len(dias) == 5
    assert all(d.weekday() < 5 for d in dias)  # todo lun-vie


# ─── Tests de integración con generar_proyeccion ────────────────────────────

def _lote(cantidad: int, galpon: int, edad_proyectada: int = 40,
          peso: float = 2.95, sexo: str = "M") -> LoteOferta:
    return LoteOferta(
        fecha_peso=date(2026, 3, 19),
        granja="TEST",
        galpon=galpon,
        nucleo=1,
        cantidad=cantidad,
        sexo=sexo,
        edad_proyectada=edad_proyectada,
        peso_muestreo_proy=peso,
        ganancia_diaria=0.0,
        dias_proyectados=0,
        edad_real=edad_proyectada,
        peso_muestreo_real=peso,
        fecha_ingreso=date(2026, 2, 10),
    )


def test_generar_proyeccion_salta_feriado():
    """
    Si el martes 24/03 es feriado, la proyección debe generar 6 días
    pero ninguno debe ser el 24 de marzo.
    """
    params = Parametros(
        pollos_diarios_objetivo_min=5000,
        pollos_diarios_objetivo_max=60000,
        edad_min_faena=35,
        edad_max_faena=50,
        peso_min_faena=2.50,
        peso_max_faena=3.50,
    )
    ofertas = [_lote(10000, 1)]

    # Feriado: martes 24 de marzo
    feriados = {date(2026, 3, 24): "Día de la Memoria"}

    semana = generar_proyeccion(
        ofertas=ofertas,
        fecha_inicio_semana=date(2026, 3, 23),  # lunes
        dias_faena=6,
        pollos_por_dia=30000,
        params=params,
        feriados=feriados,
    )

    fechas_generadas = [d.fecha for d in semana.dias]
    assert len(fechas_generadas) == 6
    assert date(2026, 3, 24) not in fechas_generadas, "El feriado no debería estar en los días de faena"
    assert semana.feriados_aplicados is not None
    assert len(semana.feriados_aplicados) == 1
    assert semana.feriados_aplicados[0].nombre == "Día de la Memoria"


def test_generar_proyeccion_multiples_feriados():
    """
    Semana con 2 feriados: debe generar solo 4 días hábiles
    cuando se piden 6 días de faena.
    """
    params = Parametros(
        pollos_diarios_objetivo_min=5000,
        pollos_diarios_objetivo_max=60000,
        edad_min_faena=35,
        edad_max_faena=50,
        peso_min_faena=2.50,
        peso_max_faena=3.50,
    )
    ofertas = [_lote(10000, 1)]

    # Dos feriados en la semana
    feriados = {
        date(2026, 3, 24): "Feriado 1",
        date(2026, 3, 26): "Feriado 2",
    }

    semana = generar_proyeccion(
        ofertas=ofertas,
        fecha_inicio_semana=date(2026, 3, 23),
        dias_faena=6,
        pollos_por_dia=30000,
        params=params,
        feriados=feriados,
    )

    fechas_generadas = [d.fecha for d in semana.dias]
    assert len(fechas_generadas) == 6
    assert date(2026, 3, 24) not in fechas_generadas
    assert date(2026, 3, 26) not in fechas_generadas


def test_generar_proyeccion_sin_feriados_backward_compatible():
    """
    Sin pasar feriados, la proyección debe funcionar como antes
    (6 días consecutivos lun-sáb).
    """
    params = Parametros(
        pollos_diarios_objetivo_min=5000,
        pollos_diarios_objetivo_max=60000,
        edad_min_faena=35,
        edad_max_faena=50,
        peso_min_faena=2.50,
        peso_max_faena=3.50,
    )
    ofertas = [_lote(10000, 1)]

    semana = generar_proyeccion(
        ofertas=ofertas,
        fecha_inicio_semana=date(2026, 3, 23),
        dias_faena=6,
        pollos_por_dia=30000,
        params=params,
        # Sin feriados → comportamiento legacy
    )

    fechas_generadas = [d.fecha for d in semana.dias]
    assert len(fechas_generadas) == 6
    # Consecutivos: lun 23, mar 24, mié 25, jue 26, vie 27, sáb 28
    assert fechas_generadas == [
        date(2026, 3, 23), date(2026, 3, 24), date(2026, 3, 25),
        date(2026, 3, 26), date(2026, 3, 27), date(2026, 3, 28),
    ]
    assert semana.feriados_aplicados == []
