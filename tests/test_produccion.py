"""Tests para el parser de producción y la simulación de mortalidad."""
from datetime import date, timedelta

from backend.parser_produccion import (
    SemanaProduccion,
    SimulacionMortalidadFila,
    SemanaSimulacion,
    simular_mortalidad,
    TASAS_MORTALIDAD_DEFAULT,
    DIAS_HASTA_FAENA,
)


def _semana(desde: date, hasta: date, pollitos: int) -> SemanaProduccion:
    return SemanaProduccion(
        fecha_desde=desde,
        fecha_hasta=hasta,
        pollitos_cargados=pollitos,
    )


def test_simulacion_mortalidad_calcula_correctamente():
    """10,000 pollitos con 6.5% mortalidad = 9,350."""
    semanas = [_semana(date(2026, 1, 1), date(2026, 1, 7), 10000)]
    resultado = simular_mortalidad(semanas, tasas=[0.065])

    assert len(resultado) == 1
    sim = resultado[0]
    assert sim.pollitos_cargados == 10000
    assert len(sim.simulaciones) == 1
    assert sim.simulaciones[0].tasa_mortalidad == 0.065
    assert sim.simulaciones[0].pollitos_disponibles == 9350


def test_fecha_faena_estimada_42_dias():
    """La fecha de faena estimada debe ser fecha_desde + 42 días."""
    desde = date(2026, 2, 1)
    semanas = [_semana(desde, date(2026, 2, 7), 5000)]
    resultado = simular_mortalidad(semanas)

    assert resultado[0].fecha_faena_estimada == desde + timedelta(days=DIAS_HASTA_FAENA)


def test_multiples_tasas_mortalidad():
    """Las 5 tasas por defecto deben generar 5 resultados distintos."""
    semanas = [_semana(date(2026, 1, 1), date(2026, 1, 7), 100000)]
    resultado = simular_mortalidad(semanas)

    assert len(resultado[0].simulaciones) == 5
    disponibles = [s.pollitos_disponibles for s in resultado[0].simulaciones]
    # Cada tasa mayor produce menos pollos
    assert disponibles == sorted(disponibles, reverse=True)
    # Con 100,000 y tasas 4.5%, 5%, 5.5%, 6%, 6.5%:
    assert disponibles[0] == 95500  # 4.5%
    assert disponibles[1] == 95000  # 5%
    assert disponibles[2] == 94500  # 5.5%
    assert disponibles[3] == 94000  # 6%
    assert disponibles[4] == 93500  # 6.5%


def test_multiples_semanas():
    """Varias semanas deben procesarse independientemente."""
    semanas = [
        _semana(date(2026, 1, 1), date(2026, 1, 7), 10000),
        _semana(date(2026, 1, 8), date(2026, 1, 14), 20000),
        _semana(date(2026, 1, 15), date(2026, 1, 21), 15000),
    ]
    resultado = simular_mortalidad(semanas, tasas=[0.065])

    assert len(resultado) == 3
    assert resultado[0].simulaciones[0].pollitos_disponibles == 9350
    assert resultado[1].simulaciones[0].pollitos_disponibles == 18700
    assert resultado[2].simulaciones[0].pollitos_disponibles == 14025


def test_mortalidad_cero():
    """Con mortalidad 0% se obtiene la totalidad de los pollitos."""
    semanas = [_semana(date(2026, 1, 1), date(2026, 1, 7), 50000)]
    resultado = simular_mortalidad(semanas, tasas=[0.0])

    assert resultado[0].simulaciones[0].pollitos_disponibles == 50000
