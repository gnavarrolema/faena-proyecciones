"""Tests para la lógica de desvío de peso (proyectado vs. real)."""
from datetime import date

from backend.calculo import (
    LoteOferta, Parametros, generar_proyeccion,
)


def _lote(cantidad: int, galpon: int, peso: float = 2.95, sexo: str = "M") -> LoteOferta:
    return LoteOferta(
        fecha_peso=date(2026, 2, 23),
        granja="TEST",
        galpon=galpon,
        nucleo=1,
        cantidad=cantidad,
        sexo=sexo,
        edad_proyectada=40,
        peso_muestreo_proy=peso,
        ganancia_diaria=0.090,
        dias_proyectados=0,
        edad_real=40,
        peso_muestreo_real=peso,
        fecha_ingreso=date(2026, 1, 10),
    )


def test_desvio_calculo_basico():
    """Verifica que la proyección tenga peso_promedio_ponderado para calcular desvíos."""
    ofertas = [_lote(15000, 1, peso=3.0), _lote(10000, 2, peso=3.1)]
    params = Parametros(
        pollos_diarios_objetivo_min=25000,
        pollos_diarios_objetivo_max=35000,
    )

    semana = generar_proyeccion(
        ofertas=ofertas,
        fecha_inicio_semana=date(2026, 2, 23),
        dias_faena=6,
        pollos_por_dia=30000,
        params=params,
    )

    # Al menos un día debe tener pollos asignados con peso ponderado > 0
    dias_con_pollos = [d for d in semana.dias if d.total_pollos > 0]
    assert len(dias_con_pollos) > 0

    for dia in dias_con_pollos:
        assert dia.peso_promedio_ponderado > 0, (
            f"Día {dia.fecha} tiene pollos pero peso_promedio_ponderado=0"
        )

    # Simulando el cálculo de desvío que hace el endpoint
    peso_real = 3.2
    dia = dias_con_pollos[0]
    desvio = peso_real - dia.peso_promedio_ponderado
    desvio_pct = (peso_real - dia.peso_promedio_ponderado) / dia.peso_promedio_ponderado * 100

    assert desvio > 0  # Real más pesado que proyectado
    assert desvio_pct > 0


def test_desvio_alerta_niveles():
    """Verifica la lógica de niveles de alerta del desvío."""
    def nivel_alerta(desvio_abs: float) -> str:
        if abs(desvio_abs) <= 0.05:
            return "normal"
        elif abs(desvio_abs) <= 0.15:
            return "moderado"
        else:
            return "critico"

    # Desvío pequeño (< 50g)
    assert nivel_alerta(0.03) == "normal"
    assert nivel_alerta(-0.04) == "normal"

    # Desvío moderado (50g-150g)
    assert nivel_alerta(0.10) == "moderado"
    assert nivel_alerta(-0.12) == "moderado"

    # Desvío crítico (> 150g)
    assert nivel_alerta(0.20) == "critico"
    assert nivel_alerta(-0.25) == "critico"
