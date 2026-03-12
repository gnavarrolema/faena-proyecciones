"""
Feriados nacionales de Argentina.

Provee la lista de feriados nacionales (inamovibles y trasladables)
y utilidades para consultar si una fecha es feriado.

Fuente oficial: https://www.argentina.gob.ar/interior/feriados-nacionales
"""
from datetime import date, timedelta
from typing import Optional


# ─── Feriados inamovibles (misma fecha todos los años) ───────────────────────

FERIADOS_INAMOVIBLES = {
    (1, 1): "Año Nuevo",
    (3, 24): "Día Nacional de la Memoria por la Verdad y la Justicia",
    (4, 2): "Día del Veterano y de los Caídos en la Guerra de Malvinas",
    (5, 1): "Día del Trabajador",
    (5, 25): "Día de la Revolución de Mayo",
    (6, 20): "Paso a la Inmortalidad del Gral. Manuel Belgrano",
    (7, 9): "Día de la Independencia",
    (12, 8): "Inmaculada Concepción de María",
    (12, 25): "Navidad",
}


# ─── Feriados trasladables ───────────────────────────────────────────────────

def _trasladar_a_lunes(fecha: date) -> date:
    """
    Regla de traslado: si cae martes o miércoles → lunes anterior;
    si cae jueves, viernes, sábado o domingo → lunes siguiente.
    Si ya es lunes, no se mueve.
    """
    dow = fecha.weekday()  # 0=lunes
    if dow == 0:
        return fecha
    elif dow in (1, 2):  # martes, miércoles → lunes anterior
        return fecha - timedelta(days=dow)
    else:  # jueves(3), viernes(4), sábado(5), domingo(6) → lunes siguiente
        return fecha + timedelta(days=(7 - dow))


def _calcular_pascua(anio: int) -> date:
    """Algoritmo de Butcher para calcular la fecha de Pascua."""
    a = anio % 19
    b = anio // 100
    c = anio % 100
    d = b // 4
    e = b % 4
    f = (b + 8) // 25
    g = (b - f + 1) // 3
    h = (19 * a + b - d - g + 15) % 30
    i = c // 4
    k = c % 4
    l = (32 + 2 * e + 2 * i - h - k) % 7
    m = (a + 11 * h + 22 * l) // 451
    mes = (h + l - 7 * m + 114) // 31
    dia = ((h + l - 7 * m + 114) % 31) + 1
    return date(anio, mes, dia)


def obtener_feriados_nacionales(anio: int) -> dict[date, str]:
    """
    Retorna todos los feriados nacionales para un año dado.
    Incluye: inamovibles, trasladables, Carnaval y Viernes Santo.

    Returns:
        dict[date, str]: mapea fecha → nombre del feriado
    """
    feriados: dict[date, str] = {}

    # 1. Feriados inamovibles
    for (mes, dia), nombre in FERIADOS_INAMOVIBLES.items():
        feriados[date(anio, mes, dia)] = nombre

    # 2. Carnaval: lunes y martes, 48 y 47 días antes de Pascua
    pascua = _calcular_pascua(anio)
    carnaval_lunes = pascua - timedelta(days=48)
    carnaval_martes = pascua - timedelta(days=47)
    feriados[carnaval_lunes] = "Carnaval"
    feriados[carnaval_martes] = "Carnaval"

    # 3. Viernes Santo: 2 días antes de Pascua
    viernes_santo = pascua - timedelta(days=2)
    feriados[viernes_santo] = "Viernes Santo"

    # 4. Feriados trasladables
    # Güemes: 17 de junio (trasladable)
    guemes = date(anio, 6, 17)
    feriados[_trasladar_a_lunes(guemes)] = (
        "Paso a la Inmortalidad del Gral. Martín Miguel de Güemes"
    )

    # San Martín: 17 de agosto (trasladable)
    san_martin = date(anio, 8, 17)
    feriados[_trasladar_a_lunes(san_martin)] = (
        "Paso a la Inmortalidad del Gral. José de San Martín"
    )

    # Diversidad Cultural: 12 de octubre (trasladable)
    diversidad = date(anio, 10, 12)
    feriados[_trasladar_a_lunes(diversidad)] = (
        "Día del Respeto a la Diversidad Cultural"
    )

    # Soberanía Nacional: 20 de noviembre (trasladable)
    soberania = date(anio, 11, 20)
    feriados[_trasladar_a_lunes(soberania)] = "Día de la Soberanía Nacional"

    return feriados


def obtener_feriados_rango(
    fecha_inicio: date,
    fecha_fin: date,
    feriados_custom: Optional[list[dict]] = None,
) -> dict[date, str]:
    """
    Retorna los feriados (nacionales + custom) que caen en un rango de fechas.

    Args:
        fecha_inicio: primer día del rango (inclusive)
        fecha_fin: último día del rango (inclusive)
        feriados_custom: lista de dicts con {fecha: str, descripcion: str}

    Returns:
        dict[date, str]: mapea fecha → nombre/descripción
    """
    # Obtener feriados nacionales de los años que cubre el rango
    anios = set()
    anios.add(fecha_inicio.year)
    anios.add(fecha_fin.year)

    todos_feriados: dict[date, str] = {}
    for anio in anios:
        nacionales = obtener_feriados_nacionales(anio)
        for fecha, nombre in nacionales.items():
            if fecha_inicio <= fecha <= fecha_fin:
                todos_feriados[fecha] = nombre

    # Agregar feriados custom
    if feriados_custom:
        for fc in feriados_custom:
            fecha = fc["fecha"] if isinstance(fc["fecha"], date) else date.fromisoformat(fc["fecha"])
            if fecha_inicio <= fecha <= fecha_fin:
                todos_feriados[fecha] = fc.get("descripcion", "Feriado personalizado")

    return todos_feriados


def generar_dias_habiles(
    fecha_inicio: date,
    cantidad_dias: int,
    feriados: Optional[dict[date, str]] = None,
    incluir_sabado: bool = True,
) -> list[date]:
    """
    Genera una lista de días hábiles consecutivos a partir de fecha_inicio,
    saltando domingos y feriados.

    Args:
        fecha_inicio: primer día candidato (típicamente un lunes)
        cantidad_dias: cuántos días hábiles generar
        feriados: dict de feriados a saltar (fecha → nombre)
        incluir_sabado: si True, el sábado cuenta como día hábil

    Returns:
        Lista de fechas hábiles
    """
    if feriados is None:
        feriados = {}

    dias_habiles: list[date] = []
    dia_actual = fecha_inicio

    # Limitar iteraciones para evitar loops infinitos
    max_iteraciones = cantidad_dias + 30

    for _ in range(max_iteraciones):
        if len(dias_habiles) >= cantidad_dias:
            break

        dow = dia_actual.weekday()  # 0=lun, 6=dom

        # Saltar domingos siempre
        if dow == 6:
            dia_actual += timedelta(days=1)
            continue

        # Saltar sábados si no se incluyen
        if dow == 5 and not incluir_sabado:
            dia_actual += timedelta(days=1)
            continue

        # Saltar feriados
        if dia_actual in feriados:
            dia_actual += timedelta(days=1)
            continue

        dias_habiles.append(dia_actual)
        dia_actual += timedelta(days=1)

    return dias_habiles
