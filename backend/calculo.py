"""
Motor de cálculo para la proyección de faena avícola.
Replica la lógica de la hoja PROYEC1 del Excel.
"""
from datetime import date, timedelta
from typing import List, Optional
from pydantic import BaseModel
import math


# ─── Modelos ────────────────────────────────────────────────────────────────────

class Parametros(BaseModel):
    """Parámetros globales de cálculo."""
    ganancia_diaria_macho: float = 0.090
    ganancia_diaria_hembra: float = 0.079
    medio_dia_ganancia: float = 0.5
    rendimiento_canal: float = 0.87
    kg_por_caja: float = 20.0
    edad_ideal_macho: int = 40
    edad_ideal_hembra: int = 44
    edad_ideal_sin_sexar: int = 42
    edad_min_faena: int = 38
    edad_max_faena: int = 43
    peso_min_faena: float = 2.80   # kg mínimo peso vivo aceptable
    peso_max_faena: float = 3.20   # kg máximo peso vivo aceptable
    descuento_sin_sexar: float = 0.04  # 4%
    pollos_diarios_objetivo_min: int = 25000
    pollos_diarios_objetivo_max: int = 35000
    descuento_sofia: int = 10000


class LoteOferta(BaseModel):
    """Un lote de la oferta de granjas (una fila de OFERTA JUEV)."""
    fecha_peso: date
    granja: str
    galpon: int
    nucleo: int
    cantidad: int
    sexo: str  # "M", "H", "MIX" (mixto), o "" (sin sexar)
    edad_proyectada: int
    peso_muestreo_proy: float
    ganancia_diaria: float
    dias_proyectados: int
    edad_real: int
    peso_muestreo_real: float
    fecha_ingreso: date


class LoteProyectado(BaseModel):
    """Un lote ya asignado a un día de faena (una fila de PROYEC1)."""
    granja: str
    galpon: int
    nucleo: int
    cantidad: int
    sexo: str
    edad_actual: int
    peso_actual: float
    fecha_fin_retiro: date
    edad_fin_retiro: int
    diferencia_edad_ideal: int
    peso_vivo_retiro: float
    diferencia_edad_promedio: Optional[float] = None
    peso_promedio_ponderado: Optional[float] = None
    peso_faenado: float = 0.0
    calibre_promedio: float = 0.0
    cajas: float = 0.0
    calibre_promedio_diario: Optional[float] = None
    pollos_dia: Optional[int] = None
    produccion_cajas_semanales: Optional[float] = None


class DiaFaena(BaseModel):
    """Agrupación de lotes para un día de faena."""
    fecha: date
    lotes: List[LoteProyectado] = []
    total_pollos: int = 0
    peso_promedio_ponderado: float = 0.0
    diferencia_edad_promedio: float = 0.0
    calibre_promedio_ponderado: float = 0.0
    cajas_totales: float = 0.0


class SemanaFaena(BaseModel):
    """Agrupación de días para una semana de faena."""
    fecha_inicio: date  # lunes
    fecha_fin: date     # sábado
    dias: List[DiaFaena] = []
    total_pollos_semana: int = 0
    promedio_edad_semana: float = 0.0
    produccion_cajas_semanales: float = 0.0
    sofia: int = 0


# ─── Funciones de cálculo ───────────────────────────────────────────────────────

def calcular_edad_fin_retiro(
    fecha_fin_retiro: date,
    fecha_ingreso: date,
    edad_actual: int
) -> int:
    """
    Edad al fin del retiro.
    edad_fin_retiro = (fecha_fin_retiro - fecha_ingreso).days + edad_actual
    """
    dias_transcurridos = (fecha_fin_retiro - fecha_ingreso).days
    return edad_actual + dias_transcurridos


def calcular_edad_fin_retiro_v2(
    fecha_fin_retiro: date,
    fecha_peso: date,
    edad_proyectada: int
) -> int:
    """
    Edad al fin del retiro calculada a partir de la fecha de peso y edad proyectada.
    """
    dias_extra = (fecha_fin_retiro - fecha_peso).days
    return edad_proyectada + dias_extra


def diferencia_edad_ideal(sexo: str, edad_fin: int, params: Parametros) -> int:
    """
    Diferencia de edad respecto al ideal.
    M → edad_fin - 40, H → edad_fin - 44, sin sexar → edad_fin - 42
    """
    if sexo.upper() == "M":
        return edad_fin - params.edad_ideal_macho
    elif sexo.upper() == "H":
        return edad_fin - params.edad_ideal_hembra
    else:
        return edad_fin - params.edad_ideal_sin_sexar


def peso_vivo_retiro(
    sexo: str,
    edad_fin: int,
    edad_actual: int,
    peso_actual: float,
    params: Parametros,
    ganancia_diaria_lote: Optional[float] = None,
) -> float:
    """
    Peso vivo proyectado al momento del retiro.
    Excel: H → (dias_extra * 0.079) + peso + 0.045
           M/sin sexar → ((dias_extra * 0.09) + peso + 0.045) * 0.96
    medio_dia siempre usa ganancia_diaria_macho (0.09 * 0.5 = 0.045).
    El descuento 4% aplica a todo lo que NO sea H (tanto M como sin sexar).

    Si ganancia_diaria_lote viene del Excel (> 0), se usa esa en vez de la
    ganancia global por sexo.
    """
    dias_extra = edad_fin - edad_actual - 1

    # Usar ganancia del lote si está disponible; si no, la global por sexo
    if ganancia_diaria_lote and ganancia_diaria_lote > 0:
        ganancia = ganancia_diaria_lote
    else:
        ganancia = params.ganancia_diaria_hembra if sexo.upper() == "H" else params.ganancia_diaria_macho

    # medio_dia siempre usa ganancia macho (0.09*0.5=0.045), según la fórmula del Excel
    medio_dia = params.ganancia_diaria_macho * params.medio_dia_ganancia

    peso = (dias_extra * ganancia) + peso_actual + medio_dia

    # Descuento 4% aplica a M y sin sexar (todo lo que no sea H)
    if sexo.upper() != "H":
        peso = peso * (1 - params.descuento_sin_sexar)

    return round(peso, 5)


def peso_faenado(peso_vivo: float, rendimiento: float = 0.87) -> float:
    """Peso faenado (rendimiento canal)."""
    return round(peso_vivo * rendimiento, 5)


def calibre_promedio(peso_faen: float, kg_por_caja: float = 20.0) -> float:
    """Calibre promedio (pollos por caja)."""
    if peso_faen <= 0:
        return 0
    return round(kg_por_caja / peso_faen, 2)


def cajas_lote(cantidad_pollos: int, calibre: float) -> float:
    """Cajas producidas por lote."""
    if calibre <= 0:
        return 0
    return round(cantidad_pollos / calibre, 0)


def calibre_promedio_ponderado(lotes: List[LoteProyectado]) -> float:
    """
    Calibre promedio diario ponderado.
    SUMPRODUCT(cantidades * calibres) / SUM(cantidades)
    """
    lotes_reales = [l for l in lotes if l.cantidad > 0]
    if not lotes_reales:
        return 0
    numerador = sum(l.cantidad * l.calibre_promedio for l in lotes_reales)
    denominador = sum(l.cantidad for l in lotes_reales)
    return round(numerador / denominador, 2) if denominador > 0 else 0


def peso_promedio_ponderado_dia(lotes: List[LoteProyectado]) -> float:
    """
    Peso promedio diario ponderado.
    SUMPRODUCT(cantidades * pesos_vivos) / SUM(cantidades)
    """
    lotes_reales = [l for l in lotes if l.cantidad > 0]
    if not lotes_reales:
        return 0
    numerador = sum(l.cantidad * l.peso_vivo_retiro for l in lotes_reales)
    denominador = sum(l.cantidad for l in lotes_reales)
    return round(numerador / denominador, 5) if denominador > 0 else 0


def dif_edad_promedio_ponderada(lotes: List[LoteProyectado]) -> float:
    """
    Diferencia de edad promedio ponderada.
    SUMPRODUCT(cantidades * diferencias_edad) / SUM(cantidades)
    """
    lotes_reales = [l for l in lotes if l.cantidad > 0]
    if not lotes_reales:
        return 0
    numerador = sum(l.cantidad * l.diferencia_edad_ideal for l in lotes_reales)
    denominador = sum(l.cantidad for l in lotes_reales)
    return round(numerador / denominador, 2) if denominador > 0 else 0


def promedio_edades_semana(lotes_semana: List[LoteProyectado]) -> float:
    """
    Promedio de edades semanal.
    Solo incluye lotes reales (cantidad > 0).
    """
    lotes_reales = [l for l in lotes_semana if l.cantidad > 0]
    if not lotes_reales:
        return 0
    return round(sum(l.edad_fin_retiro for l in lotes_reales) / len(lotes_reales), 1)


def cajas_semanales(total_pollos_semana: int, calibre_ponderado: float) -> float:
    """Producción de cajas semanales."""
    if calibre_ponderado <= 0:
        return 0
    return round(total_pollos_semana / calibre_ponderado, 0)


def calcular_totales_semana(
    total_pollos: int,
    descuento_sofia: int = 10000,
    peso_promedio_recibido: float = 0
) -> dict:
    """Totales semanales por granja/destino."""
    sofia = total_pollos - descuento_sofia
    calibre_real = (20 / peso_promedio_recibido) if peso_promedio_recibido > 0 else 0
    cajas_reales = (total_pollos / calibre_real) if calibre_real > 0 else 0
    return {
        "total_pollos": total_pollos,
        "sofia": sofia,
        "calibre_real": round(calibre_real, 2),
        "cajas_reales": round(cajas_reales, 0),
    }


# ─── Proyección completa ────────────────────────────────────────────────────────

def calcular_lote_proyectado(
    oferta: LoteOferta,
    fecha_fin_retiro: date,
    params: Parametros
) -> LoteProyectado:
    """Calcula todos los campos de un lote proyectado a partir de la oferta."""

    edad_fin = calcular_edad_fin_retiro_v2(
        fecha_fin_retiro, oferta.fecha_peso, oferta.edad_proyectada
    )

    dif_edad = diferencia_edad_ideal(oferta.sexo, edad_fin, params)

    peso_vivo = peso_vivo_retiro(
        oferta.sexo, edad_fin, oferta.edad_proyectada,
        oferta.peso_muestreo_proy, params,
        ganancia_diaria_lote=oferta.ganancia_diaria,
    )

    p_faenado = peso_faenado(peso_vivo, params.rendimiento_canal)
    calibre = calibre_promedio(p_faenado, params.kg_por_caja)
    cajas = cajas_lote(oferta.cantidad, calibre)

    return LoteProyectado(
        granja=oferta.granja,
        galpon=oferta.galpon,
        nucleo=oferta.nucleo,
        cantidad=oferta.cantidad,
        sexo=oferta.sexo,
        edad_actual=oferta.edad_proyectada,
        peso_actual=oferta.peso_muestreo_proy,
        fecha_fin_retiro=fecha_fin_retiro,
        edad_fin_retiro=edad_fin,
        diferencia_edad_ideal=dif_edad,
        peso_vivo_retiro=peso_vivo,
        peso_faenado=p_faenado,
        calibre_promedio=calibre,
        cajas=cajas,
    )


def calcular_dia_faena(fecha: date, lotes: List[LoteProyectado]) -> DiaFaena:
    """Calcula los agregados de un día de faena."""
    lotes_reales = [l for l in lotes if l.cantidad > 0]
    total = sum(l.cantidad for l in lotes_reales)

    dia = DiaFaena(
        fecha=fecha,
        lotes=lotes,
        total_pollos=total,
    )

    if lotes_reales:
        dia.peso_promedio_ponderado = peso_promedio_ponderado_dia(lotes)
        dia.diferencia_edad_promedio = dif_edad_promedio_ponderada(lotes)
        dia.calibre_promedio_ponderado = calibre_promedio_ponderado(lotes)
        dia.cajas_totales = sum(l.cajas for l in lotes_reales)

    return dia


def calcular_semana_faena(
    fecha_inicio: date,
    dias: List[DiaFaena],
    params: Parametros
) -> SemanaFaena:
    """Calcula los agregados de una semana de faena."""
    fecha_fin = fecha_inicio + timedelta(days=5)  # lunes a sábado

    todos_lotes = []
    for d in dias:
        todos_lotes.extend(d.lotes)

    total = sum(d.total_pollos for d in dias)
    prom_edad = promedio_edades_semana(todos_lotes)

    # Calibre ponderado semanal
    cal_pond = calibre_promedio_ponderado(todos_lotes)
    cajas_sem = cajas_semanales(total, cal_pond)

    sofia = total - params.descuento_sofia

    return SemanaFaena(
        fecha_inicio=fecha_inicio,
        fecha_fin=fecha_fin,
        dias=dias,
        total_pollos_semana=total,
        promedio_edad_semana=prom_edad,
        produccion_cajas_semanales=cajas_sem,
        sofia=sofia,
    )


def ordenar_oferta_por_prioridad(
    ofertas: List[LoteOferta],
    params: Parametros
) -> List[LoteOferta]:
    """
    Ordena la oferta por prioridad de faena:
    1. Los pollos más pesados primero (peso descendente)
    2. A igual peso, los de mayor edad primero
    """
    return sorted(
        ofertas,
        key=lambda o: (-o.peso_muestreo_proy, -o.edad_proyectada)
    )


def _peso_proyectado_en_fecha(
    oferta: LoteOferta,
    fecha_dia: date,
    params: Parametros,
) -> float:
    """
    Calcula el peso vivo que tendría un lote si se faenara en `fecha_dia`,
    usando la ganancia diaria individual del lote (si está disponible).
    """
    edad_fin = calcular_edad_fin_retiro_v2(
        fecha_dia, oferta.fecha_peso, oferta.edad_proyectada
    )
    return peso_vivo_retiro(
        oferta.sexo, edad_fin, oferta.edad_proyectada,
        oferta.peso_muestreo_proy, params,
        ganancia_diaria_lote=oferta.ganancia_diaria,
    )


def _evaluar_elegibilidad_lote(
    oferta: LoteOferta,
    fecha_dia: date,
    params: Parametros,
) -> Optional[tuple]:
    """
    Evalúa si un lote es elegible para un día de faena específico.
    Retorna (peso_proy, edad_fin) si es elegible, None si no.
    """
    edad_fin = calcular_edad_fin_retiro_v2(
        fecha_dia, oferta.fecha_peso, oferta.edad_proyectada
    )

    if edad_fin < params.edad_min_faena or edad_fin > params.edad_max_faena:
        return None

    peso_proy = _peso_proyectado_en_fecha(oferta, fecha_dia, params)

    if peso_proy < params.peso_min_faena or peso_proy > params.peso_max_faena:
        return None

    return (peso_proy, edad_fin)


def generar_proyeccion(
    ofertas: List[LoteOferta],
    fecha_inicio_semana: date,
    dias_faena: int = 6,
    pollos_por_dia: int = 30000,
    params: Optional[Parametros] = None,
) -> SemanaFaena:
    """
    Genera la proyección completa de faena para una semana.

    Algoritmo de asignación con propagación de restricciones:

    Fase 1 – Elegibilidad:
        Construye la matriz de qué lotes son elegibles en qué días.

    Fase 2 – Propagación de restricciones (estilo Sudoku):
        Iterativamente detecta y resuelve asignaciones forzadas:
        a) Lote elegible en un solo día → se asigna a ese día.
        b) Día con un solo lote elegible no asignado → ese lote se
           reserva para ese día.
        Se repite hasta que no haya más restricciones forzadas.

    Fase 3 – Asignación flexible:
        Los lotes restantes se asignan al día elegible que tenga mayor
        déficit respecto al objetivo, sin superar el objetivo_max.

    Fase 4 – Excedentes:
        Lotes que no pudieron asignarse se distribuyen al día elegible
        menos cargado si está dentro del máximo tolerable.
    """
    if params is None:
        params = Parametros()

    objetivo_preferido = max(
        params.pollos_diarios_objetivo_min,
        min(pollos_por_dia, params.pollos_diarios_objetivo_max),
    )

    fechas_dias = [
        fecha_inicio_semana + timedelta(days=i) for i in range(dias_faena)
    ]

    # ── Fase 1: Matriz de elegibilidad ──────────────────────────────────────
    elegibilidad: dict[int, list[tuple[int, float, int]]] = {}

    for i, oferta in enumerate(ofertas):
        dias_elegibles = []
        for d_idx, fecha_dia in enumerate(fechas_dias):
            resultado = _evaluar_elegibilidad_lote(oferta, fecha_dia, params)
            if resultado:
                peso_proy, edad_fin = resultado
                dias_elegibles.append((d_idx, peso_proy, edad_fin))
        if dias_elegibles:
            elegibilidad[i] = dias_elegibles

    # Estructuras de asignación
    asignaciones: dict[int, list[int]] = {d: [] for d in range(dias_faena)}
    pollos_dia: dict[int, int] = {d: 0 for d in range(dias_faena)}
    asignados: set[int] = set()

    def _asignar(lote_idx: int, dia_idx: int):
        """Asigna un lote a un día y actualiza estructuras."""
        asignaciones[dia_idx].append(lote_idx)
        pollos_dia[dia_idx] += ofertas[lote_idx].cantidad
        asignados.add(lote_idx)

    # ── Fase 2: Propagación de restricciones ────────────────────────────────
    cambio = True
    while cambio:
        cambio = False

        # 2a: Lotes elegibles en un solo día → asignación forzada
        for i in list(elegibilidad.keys()):
            if i in asignados:
                continue
            dias_eleg = [d for d, _, _ in elegibilidad[i]]
            if len(dias_eleg) == 1:
                _asignar(i, dias_eleg[0])
                cambio = True

        # 2b: Días con un solo lote elegible no asignado → reservar
        for d_idx in range(dias_faena):
            candidatos_dia = [
                i for i, dias_eleg in elegibilidad.items()
                if i not in asignados
                and any(d == d_idx for d, _, _ in dias_eleg)
            ]
            if len(candidatos_dia) == 1:
                _asignar(candidatos_dia[0], d_idx)
                cambio = True

    # ── Fase 3: Asignación flexible (lotes restantes, bajo objetivo) ───────
    restantes = [
        i for i in elegibilidad if i not in asignados
    ]
    # Ordenar por peso descendente (faenar los más pesados primero)
    restantes_con_peso = []
    for i in restantes:
        peso_max = max(p for _, p, _ in elegibilidad[i])
        restantes_con_peso.append((i, peso_max))
    restantes_con_peso.sort(key=lambda x: (-x[1], -ofertas[x[0]].cantidad))

    pendientes = []

    for i, _ in restantes_con_peso:
        dias_eleg = elegibilidad[i]

        # Buscar día elegible con mayor déficit respecto al objetivo
        mejor_dia = None
        mayor_deficit = -1

        for d_idx, peso_proy, edad_fin in dias_eleg:
            deficit = objetivo_preferido - pollos_dia[d_idx]
            if deficit > 0 and deficit > mayor_deficit:
                mayor_deficit = deficit
                mejor_dia = d_idx

        if mejor_dia is not None:
            _asignar(i, mejor_dia)
        else:
            pendientes.append(i)

    # ── Fase 4: Excedentes → día menos cargado (sin tope) ─────────────────
    # No aplicar tope: es preferible faenar un lote elegible en un día con
    # algo de exceso que perder la producción.  El usuario puede ajustar
    # manualmente después si lo necesita.
    for i in pendientes:
        dias_eleg = elegibilidad[i]

        mejor_dia = None
        mejor_pollos = float("inf")

        for d_idx, peso_proy, edad_fin in dias_eleg:
            pollos_actuales = pollos_dia[d_idx]
            if pollos_actuales < mejor_pollos:
                mejor_pollos = pollos_actuales
                mejor_dia = d_idx

        if mejor_dia is not None:
            _asignar(i, mejor_dia)

    # ── Construir DiaFaena con lotes proyectados ────────────────────────────
    dias_resultado: List[DiaFaena] = []

    for d_idx, fecha_dia in enumerate(fechas_dias):
        lotes_dia: List[LoteProyectado] = []

        lotes_indices = asignaciones[d_idx]
        lotes_con_peso = []
        for i in lotes_indices:
            peso_dia = 0.0
            for d, p, e in elegibilidad[i]:
                if d == d_idx:
                    peso_dia = p
                    break
            lotes_con_peso.append((i, peso_dia))

        lotes_con_peso.sort(key=lambda x: -x[1])

        for i, _ in lotes_con_peso:
            lote = calcular_lote_proyectado(ofertas[i], fecha_dia, params)
            lotes_dia.append(lote)

        dia_faena_obj = calcular_dia_faena(fecha_dia, lotes_dia)
        dias_resultado.append(dia_faena_obj)

    semana = calcular_semana_faena(fecha_inicio_semana, dias_resultado, params)
    return semana
