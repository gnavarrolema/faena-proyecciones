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
    pollos_diarios_objetivo_min: int = 33000   # rango práctico inferior
    pollos_diarios_objetivo_max: int = 38000   # rango práctico superior (objetivo)
    capacidad_maxima_planta: int = 42000       # capacidad planta (horas extras a partir de aquí)
    limite_sabado: int = 20000                 # máximo estricto para sábados
    descuento_sofia: int = 10000
    peso_objetivo_recepcion: float = 2.85   # kg peso vivo objetivo en recepción
    capacidad_con_horas_extras: int = 45000  # capacidad máxima real con horas extras


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
    # Datos originales de la oferta para recálculo (mover lote, etc.)
    fecha_peso_original: Optional[date] = None
    ganancia_diaria_original: Optional[float] = None
    fecha_ingreso_original: Optional[date] = None
    # Compra a terceros
    es_compra_terceros: bool = False
    motivo_compra: Optional[str] = None


class DiaFaena(BaseModel):
    """Agrupación de lotes para un día de faena."""
    fecha: date
    lotes: List[LoteProyectado] = []
    total_pollos: int = 0
    peso_promedio_ponderado: float = 0.0
    diferencia_edad_promedio: float = 0.0
    calibre_promedio_ponderado: float = 0.0
    cajas_totales: float = 0.0
    # Alertas de carga / horas extras
    nivel_carga: str = "normal"       # "normal" | "alto" | "horas_extras"
    alerta_horas_extras: bool = False
    es_sabado: bool = False
    # Gallinas (total y desglose por tipo)
    gallinas_cantidad: int = 0
    gallinas_habilitado: bool = False
    gallinas_livianas_cantidad: int = 0
    gallinas_pesadas_cantidad: int = 0


class LoteNoAsignado(BaseModel):
    """Eligible lot that could not be assigned due to capacity constraints."""
    granja: str
    galpon: int
    nucleo: int
    cantidad: int
    sexo: str
    fecha_ingreso: Optional[date] = None
    dias_elegibles: List[date] = []
    motivo: str


class LoteFueraRango(BaseModel):
    """Lote que no pasó el filtro de elegibilidad (edad/peso) para ningún día."""
    granja: str
    galpon: int
    nucleo: int
    cantidad: int
    sexo: str
    fecha_ingreso: Optional[date] = None
    motivo: str
    detalle_por_dia: List[dict] = []


class FeriadoAplicado(BaseModel):
    """Feriado que fue saltado al generar la proyección."""
    fecha: date
    nombre: str


class EventoGallinas(BaseModel):
    """Evento de faena de gallinas en un día."""
    fecha: date
    cantidad: int
    tipo: str = "liviana"  # "liviana" | "pesada"
    descripcion: str = "Faena de gallinas"


class SemanaFaena(BaseModel):
    """Agrupación de días para una semana de faena."""
    fecha_inicio: date  # lunes
    fecha_fin: date     # sábado
    dias: List[DiaFaena] = []
    total_pollos_semana: int = 0
    promedio_edad_semana: float = 0.0
    produccion_cajas_semanales: float = 0.0
    sofia: int = 0
    lotes_no_asignados: List[LoteNoAsignado] = []
    total_pollos_no_asignados: int = 0
    lotes_fuera_rango: List[LoteFueraRango] = []
    total_pollos_fuera_rango: int = 0
    feriados_aplicados: List[FeriadoAplicado] = []
    eventos_gallinas: List[EventoGallinas] = []


class AjusteMartesResumen(BaseModel):
    """Resumen de cambios al aplicar la oferta del martes."""
    lotes_actualizados: int = 0
    lotes_nuevos: int = 0
    lotes_nuevos_asignados: int = 0
    lotes_nuevos_fuera_rango: int = 0
    lotes_faltantes: int = 0
    lotes_fuera_rango_post_ajuste: int = 0
    detalle_actualizados: List[dict] = []
    detalle_nuevos: List[dict] = []
    detalle_nuevos_asignados: List[dict] = []
    detalle_faltantes: List[dict] = []
    detalle_fuera_rango_post_ajuste: List[dict] = []


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
    edad_proyectada: int,
    dias_proyectados: int = 0,
) -> int:
    """
    Edad al fin del retiro calculada a partir de la fecha base de la oferta.

    La fecha base es fecha_peso + dias_proyectados (fecha en que se emitió la
    oferta).  edad_proyectada ya incluye esos días de proyección, por lo que
    la base correcta para contar "días extra" hasta el retiro es la fecha de
    la oferta, no la fecha de pesaje individual.
    """
    fecha_base = fecha_peso + timedelta(days=dias_proyectados)
    dias_extra = (fecha_fin_retiro - fecha_base).days
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
        fecha_fin_retiro, oferta.fecha_peso, oferta.edad_proyectada,
        dias_proyectados=oferta.dias_proyectados,
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
        # Preservar datos originales de la oferta para recálculo
        fecha_peso_original=oferta.fecha_peso,
        ganancia_diaria_original=oferta.ganancia_diaria,
        fecha_ingreso_original=oferta.fecha_ingreso,
    )


def calcular_dia_faena(
    fecha: date,
    lotes: List[LoteProyectado],
    params: Optional["Parametros"] = None,
    gallinas_cantidad: int = 0,
    gallinas_livianas: int = 0,
    gallinas_pesadas: int = 0,
) -> DiaFaena:
    """Calcula los agregados de un día de faena, incluyendo alertas de carga."""
    lotes_reales = [l for l in lotes if l.cantidad > 0]
    total = sum(l.cantidad for l in lotes_reales)

    es_sabado = fecha.weekday() == 5  # 5 = sábado

    # Determinar nivel de carga
    nivel_carga = "normal"
    alerta_horas_extras = False
    if params:
        capacidad = params.limite_sabado if es_sabado else params.capacidad_maxima_planta
        total_con_gallinas = total + gallinas_cantidad
        if total_con_gallinas > capacidad:
            nivel_carga = "horas_extras"
            alerta_horas_extras = True
        elif total_con_gallinas > params.pollos_diarios_objetivo_max:
            nivel_carga = "alto"
    else:
        if total > 42000:
            nivel_carga = "horas_extras"
            alerta_horas_extras = True
        elif total > 38000:
            nivel_carga = "alto"

    dia = DiaFaena(
        fecha=fecha,
        lotes=lotes,
        total_pollos=total,
        nivel_carga=nivel_carga,
        alerta_horas_extras=alerta_horas_extras,
        es_sabado=es_sabado,
        gallinas_cantidad=gallinas_cantidad,
        gallinas_habilitado=gallinas_cantidad > 0,
        gallinas_livianas_cantidad=gallinas_livianas,
        gallinas_pesadas_cantidad=gallinas_pesadas,
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
    params: Parametros,
    lotes_no_asignados: Optional[List[LoteNoAsignado]] = None,
    lotes_fuera_rango: Optional[List[LoteFueraRango]] = None,
) -> SemanaFaena:
    """Calcula los agregados de una semana de faena."""
    fecha_fin = fecha_inicio + timedelta(days=5)  # lunes a sábado

    todos_lotes = []
    for d in dias:
        todos_lotes.extend(d.lotes)

    total = sum(d.total_pollos for d in dias)
    prom_edad = promedio_edades_semana(todos_lotes)

    # Cajas semanales: suma de cajas diarias (como en Excel)
    cajas_sem = sum(d.cajas_totales for d in dias)

    # descuento_sofia is applied only in the final weekly summary (not in assignment)
    sofia = total - params.descuento_sofia

    no_asignados = lotes_no_asignados or []
    total_no_asignados = sum(l.cantidad for l in no_asignados)

    fuera_rango = lotes_fuera_rango or []
    total_fuera_rango = sum(l.cantidad for l in fuera_rango)

    return SemanaFaena(
        fecha_inicio=fecha_inicio,
        fecha_fin=fecha_fin,
        dias=dias,
        total_pollos_semana=total,
        promedio_edad_semana=prom_edad,
        produccion_cajas_semanales=cajas_sem,
        sofia=sofia,
        lotes_no_asignados=no_asignados,
        total_pollos_no_asignados=total_no_asignados,
        lotes_fuera_rango=fuera_rango,
        total_pollos_fuera_rango=total_fuera_rango,
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
        fecha_dia, oferta.fecha_peso, oferta.edad_proyectada,
        dias_proyectados=oferta.dias_proyectados,
    )
    return peso_vivo_retiro(
        oferta.sexo, edad_fin, oferta.edad_proyectada,
        oferta.peso_muestreo_proy, params,
        ganancia_diaria_lote=oferta.ganancia_diaria,
    )


def _detalle_rechazo_dia(
    oferta: LoteOferta,
    fecha_dia: date,
    params: Parametros,
) -> dict:
    """Construye el detalle de por qué un lote no es elegible para un día."""
    edad_fin = calcular_edad_fin_retiro_v2(
        fecha_dia, oferta.fecha_peso, oferta.edad_proyectada,
        dias_proyectados=oferta.dias_proyectados,
    )
    peso_proy = _peso_proyectado_en_fecha(oferta, fecha_dia, params)
    razones = []
    if edad_fin < params.edad_min_faena:
        razones.append(f"Edad {edad_fin} < mín {params.edad_min_faena}")
    if edad_fin > params.edad_max_faena:
        razones.append(f"Edad {edad_fin} > máx {params.edad_max_faena}")
    if peso_proy < params.peso_min_faena:
        razones.append(f"Peso {peso_proy:.2f} < mín {params.peso_min_faena:.2f}")
    if peso_proy > params.peso_max_faena:
        razones.append(f"Peso {peso_proy:.2f} > máx {params.peso_max_faena:.2f}")
    return {
        "fecha": fecha_dia.isoformat(),
        "edad_proyectada": edad_fin,
        "peso_proyectado": round(peso_proy, 2),
        "razon": "; ".join(razones) if razones else "OK",
    }


def _construir_motivo_fuera_rango(
    oferta: LoteOferta,
    fechas_dias: List[date],
    params: Parametros,
) -> str:
    """Construye un motivo resumido de por qué el lote está fuera de rango."""
    edad_primer = calcular_edad_fin_retiro_v2(
        fechas_dias[0], oferta.fecha_peso, oferta.edad_proyectada,
        dias_proyectados=oferta.dias_proyectados,
    )
    edad_ultimo = calcular_edad_fin_retiro_v2(
        fechas_dias[-1], oferta.fecha_peso, oferta.edad_proyectada,
        dias_proyectados=oferta.dias_proyectados,
    )
    peso_primer = _peso_proyectado_en_fecha(oferta, fechas_dias[0], params)
    peso_ultimo = _peso_proyectado_en_fecha(oferta, fechas_dias[-1], params)

    razones = []
    if edad_ultimo < params.edad_min_faena:
        razones.append(f"Edad: {edad_primer}–{edad_ultimo} días (mín. {params.edad_min_faena})")
    elif edad_primer > params.edad_max_faena:
        razones.append(f"Edad: {edad_primer}–{edad_ultimo} días (máx. {params.edad_max_faena})")

    if peso_ultimo < params.peso_min_faena:
        razones.append(f"Peso: {peso_primer:.2f}–{peso_ultimo:.2f} kg (mín. {params.peso_min_faena:.2f})")
    elif peso_primer > params.peso_max_faena:
        razones.append(f"Peso: {peso_primer:.2f}–{peso_ultimo:.2f} kg (máx. {params.peso_max_faena:.2f})")

    return "; ".join(razones) if razones else "Fuera de rango edad/peso en todos los días"


def evaluar_elegibilidad_lote(
    oferta: LoteOferta,
    fecha_dia: date,
    params: Parametros,
) -> Optional[tuple]:
    """
    Evalúa si un lote es elegible para un día de faena específico.
    Retorna (peso_proy, edad_fin) si es elegible, None si no.
    """
    edad_fin = calcular_edad_fin_retiro_v2(
        fecha_dia, oferta.fecha_peso, oferta.edad_proyectada,
        dias_proyectados=oferta.dias_proyectados,
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
    dias_faena: int = 5,
    pollos_por_dia: int = 35000,
    params: Optional[Parametros] = None,
    feriados: Optional[dict] = None,
    gallinas: Optional[dict] = None,
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

    Args:
        feriados: dict[date, str] con fechas de feriados a saltar.
                  Si es None, se generan días consecutivos como antes.
        gallinas: dict[date_str, int] con cantidades de gallinas por día.
                  Reduce la capacidad disponible para pollos en ese día.
    """
    if params is None:
        params = Parametros()

    if gallinas is None:
        gallinas = {}

    objetivo_preferido = max(
        params.pollos_diarios_objetivo_min,
        min(pollos_por_dia, params.pollos_diarios_objetivo_max),
    )

    # Generar días hábiles saltando feriados y domingos
    if feriados:
        from .feriados import generar_dias_habiles
        incluir_sabado = dias_faena >= 6
        fechas_dias = generar_dias_habiles(
            fecha_inicio_semana, dias_faena, feriados,
            incluir_sabado=incluir_sabado,
        )
    else:
        fechas_dias = [
            fecha_inicio_semana + timedelta(days=i) for i in range(dias_faena)
        ]

    # Normalizar gallinas: acepta {fecha: int} o {fecha: {livianas: int, pesadas: int}}
    def _gallinas_total(fecha_iso: str) -> int:
        val = gallinas.get(fecha_iso, 0)
        if isinstance(val, dict):
            return val.get("livianas", 0) + val.get("pesadas", 0)
        return val

    def _gallinas_desglose(fecha_iso: str) -> tuple:
        val = gallinas.get(fecha_iso, 0)
        if isinstance(val, dict):
            return val.get("livianas", 0), val.get("pesadas", 0)
        return val, 0  # backward-compat: todo como livianas

    # Capacidad máxima por día: sábados = limite_sabado, L-V = capacidad_maxima_planta
    # Se descuenta la capacidad ocupada por gallinas
    def _capacidad_dia(d_idx: int) -> int:
        fecha = fechas_dias[d_idx]
        es_sabado = fecha.weekday() == 5
        cap_base = params.limite_sabado if es_sabado else params.capacidad_maxima_planta
        gall = _gallinas_total(fecha.isoformat())
        return max(0, cap_base - gall)

    # Objetivo preferido por día (no puede superar la capacidad del día)
    def _objetivo_dia(d_idx: int) -> int:
        fecha = fechas_dias[d_idx]
        es_sabado = fecha.weekday() == 5
        gall = _gallinas_total(fecha.isoformat())
        if es_sabado:
            # Sábado: objetivo = limite_sabado (estricto 20k)
            return max(0, params.limite_sabado - gall)
        return max(0, objetivo_preferido - gall)

    # ── Fase 1: Matriz de elegibilidad ──────────────────────────────────────
    elegibilidad: dict[int, list[tuple[int, float, int]]] = {}
    fuera_rango_data: dict[int, list[dict]] = {}  # idx → detalle por día

    for i, oferta in enumerate(ofertas):
        dias_elegibles = []
        detalle_rechazo = []
        for d_idx, fecha_dia in enumerate(fechas_dias):
            resultado = evaluar_elegibilidad_lote(oferta, fecha_dia, params)
            if resultado:
                peso_proy, edad_fin = resultado
                dias_elegibles.append((d_idx, peso_proy, edad_fin))
            else:
                detalle_rechazo.append(
                    _detalle_rechazo_dia(oferta, fecha_dia, params)
                )
        if dias_elegibles:
            elegibilidad[i] = dias_elegibles
        else:
            fuera_rango_data[i] = detalle_rechazo

    # Estructuras de asignación
    asignaciones: dict[int, list[int]] = {d: [] for d in range(dias_faena)}
    pollos_dia: dict[int, int] = {d: 0 for d in range(dias_faena)}
    asignados: set[int] = set()
    no_asignados: dict[int, str] = {}

    def _asignar(lote_idx: int, dia_idx: int):
        """Asigna un lote a un día y actualiza estructuras."""
        asignaciones[dia_idx].append(lote_idx)
        pollos_dia[dia_idx] += ofertas[lote_idx].cantidad
        asignados.add(lote_idx)

    def _puede_asignarse(lote_idx: int, dia_idx: int) -> bool:
        """Checks hard daily maximum capacity (respeta límite sábado y gallinas)."""
        return pollos_dia[dia_idx] + ofertas[lote_idx].cantidad <= _capacidad_dia(dia_idx)

    # ── Fase 2: Propagación de restricciones ────────────────────────────────
    cambio = True
    while cambio:
        cambio = False

        # 2a: Lotes elegibles en un solo día → asignación forzada
        for i in list(elegibilidad.keys()):
            if i in asignados or i in no_asignados:
                continue
            dias_eleg = [d for d, _, _ in elegibilidad[i]]
            if len(dias_eleg) == 1:
                dia_unico = dias_eleg[0]
                if _puede_asignarse(i, dia_unico):
                    _asignar(i, dia_unico)
                    cambio = True
                else:
                    cap = _capacidad_dia(dia_unico)
                    no_asignados[i] = (
                        f"Lote con único día elegible ({fechas_dias[dia_unico].isoformat()}) "
                        f"excede tope diario máximo de {cap}"
                    )
                    cambio = True

        # 2b: Días con un solo lote elegible no asignado → reservar
        for d_idx in range(dias_faena):
            candidatos_dia = [
                i for i, dias_eleg in elegibilidad.items()
                if i not in asignados
                and i not in no_asignados
                and any(d == d_idx for d, _, _ in dias_eleg)
            ]
            if len(candidatos_dia) == 1:
                lote_idx = candidatos_dia[0]
                if _puede_asignarse(lote_idx, d_idx):
                    _asignar(lote_idx, d_idx)
                else:
                    cap = _capacidad_dia(d_idx)
                    no_asignados[lote_idx] = (
                        f"Único candidato para {fechas_dias[d_idx].isoformat()} "
                        f"excede tope diario máximo de {cap}"
                    )
                cambio = True

    # ── Fase 3: Asignación flexible (lotes restantes, bajo objetivo) ───────
    restantes = [
        i for i in elegibilidad if i not in asignados and i not in no_asignados
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

        # Buscar día elegible con mayor déficit respecto al objetivo.
        # A igual déficit, preferir el día más temprano (los pollos pesados
        # deben faenarse cuanto antes para evitar exceder peso máximo).
        mejor_dia = None
        mayor_deficit = -1

        for d_idx, peso_proy, edad_fin in dias_eleg:
            if not _puede_asignarse(i, d_idx):
                continue
            obj = _objetivo_dia(d_idx)
            deficit = obj - pollos_dia[d_idx]
            if deficit > 0 and (deficit > mayor_deficit or
                                (deficit == mayor_deficit and
                                 (mejor_dia is None or d_idx < mejor_dia))):
                mayor_deficit = deficit
                mejor_dia = d_idx

        if mejor_dia is not None:
            _asignar(i, mejor_dia)
        else:
            pendientes.append(i)

    # ── Fase 4: Excedentes → día menos cargado (con tope duro) ─────────────
    for i in pendientes:
        dias_eleg = elegibilidad[i]

        mejor_dia = None
        mejor_pollos = float("inf")

        for d_idx, peso_proy, edad_fin in dias_eleg:
            pollos_actuales = pollos_dia[d_idx]
            if _puede_asignarse(i, d_idx) and pollos_actuales < mejor_pollos:
                mejor_pollos = pollos_actuales
                mejor_dia = d_idx

        if mejor_dia is not None:
            _asignar(i, mejor_dia)
        else:
            no_asignados[i] = (
                "Excede tope diario máximo en todos los días elegibles"
            )

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

        gall_total = _gallinas_total(fecha_dia.isoformat())
        gall_liv, gall_pes = _gallinas_desglose(fecha_dia.isoformat())
        dia_faena_obj = calcular_dia_faena(
            fecha_dia, lotes_dia, params=params, gallinas_cantidad=gall_total,
            gallinas_livianas=gall_liv, gallinas_pesadas=gall_pes,
        )
        dias_resultado.append(dia_faena_obj)

    lotes_no_asignados_resultado: List[LoteNoAsignado] = []
    for i, motivo in no_asignados.items():
        oferta = ofertas[i]
        dias = [fechas_dias[d] for d, _, _ in elegibilidad.get(i, [])]
        lotes_no_asignados_resultado.append(
            LoteNoAsignado(
                granja=oferta.granja,
                galpon=oferta.galpon,
                nucleo=oferta.nucleo,
                cantidad=oferta.cantidad,
                sexo=oferta.sexo,
                fecha_ingreso=oferta.fecha_ingreso,
                dias_elegibles=dias,
                motivo=motivo,
            )
        )

    # ── Lotes fuera de rango (no elegibles para ningún día) ───────────────
    lotes_fuera_rango_resultado: List[LoteFueraRango] = []
    for i, detalle in fuera_rango_data.items():
        oferta = ofertas[i]
        motivo = _construir_motivo_fuera_rango(oferta, fechas_dias, params)
        lotes_fuera_rango_resultado.append(
            LoteFueraRango(
                granja=oferta.granja,
                galpon=oferta.galpon,
                nucleo=oferta.nucleo,
                cantidad=oferta.cantidad,
                sexo=oferta.sexo,
                fecha_ingreso=oferta.fecha_ingreso,
                motivo=motivo,
                detalle_por_dia=detalle,
            )
        )

    # Construir lista de feriados aplicados (saltados)
    feriados_aplicados_lista: List[FeriadoAplicado] = []
    if feriados:
        fecha_fin_rango = fecha_inicio_semana + timedelta(days=13)
        for f_fecha, f_nombre in sorted(feriados.items()):
            if fecha_inicio_semana <= f_fecha <= fecha_fin_rango and f_fecha not in fechas_dias:
                feriados_aplicados_lista.append(
                    FeriadoAplicado(fecha=f_fecha, nombre=f_nombre)
                )

    semana = calcular_semana_faena(
        fecha_inicio_semana,
        dias_resultado,
        params,
        lotes_no_asignados=lotes_no_asignados_resultado,
        lotes_fuera_rango=lotes_fuera_rango_resultado,
    )
    semana.feriados_aplicados = feriados_aplicados_lista

    # Registrar eventos de gallinas
    for fecha_str in gallinas:
        from datetime import date as date_type
        fecha_gall = date_type.fromisoformat(fecha_str)
        gall_liv, gall_pes = _gallinas_desglose(fecha_str)
        if gall_liv > 0:
            semana.eventos_gallinas.append(
                EventoGallinas(fecha=fecha_gall, cantidad=gall_liv, tipo="liviana")
            )
        if gall_pes > 0:
            semana.eventos_gallinas.append(
                EventoGallinas(fecha=fecha_gall, cantidad=gall_pes, tipo="pesada")
            )

    return semana


def _intentar_asignar_lotes_nuevos(
    nuevos: List[LoteOferta],
    dias: List[DiaFaena],
    params: Parametros,
) -> tuple:
    """
    Intenta asignar lotes nuevos del martes a días existentes.

    Retorna:
        (dias_actualizados, no_asignados, fuera_rango, detalle_asignados)
    """
    no_asignados_resultado: List[LoteNoAsignado] = []
    fuera_rango_resultado: List[LoteFueraRango] = []
    detalle_asignados: List[dict] = []

    DIAS_SEMANA = ['Lunes', 'Martes', 'Miércoles', 'Jueves', 'Viernes', 'Sábado']

    def _cap_dia(d_idx: int) -> int:
        fecha = dias[d_idx].fecha
        es_sab = fecha.weekday() == 5
        cap = params.limite_sabado if es_sab else params.capacidad_maxima_planta
        return max(0, cap - dias[d_idx].gallinas_cantidad)

    for oferta in nuevos:
        dias_elegibles = []
        detalle_rechazo = []

        for d_idx, dia in enumerate(dias):
            resultado = evaluar_elegibilidad_lote(oferta, dia.fecha, params)
            if resultado:
                peso_proy, edad_fin = resultado
                dias_elegibles.append((d_idx, peso_proy, edad_fin))
            else:
                detalle_rechazo.append(
                    _detalle_rechazo_dia(oferta, dia.fecha, params)
                )

        if not dias_elegibles:
            fechas = [d.fecha for d in dias]
            motivo = _construir_motivo_fuera_rango(oferta, fechas, params)
            fuera_rango_resultado.append(
                LoteFueraRango(
                    granja=oferta.granja,
                    galpon=oferta.galpon,
                    nucleo=oferta.nucleo,
                    cantidad=oferta.cantidad,
                    sexo=oferta.sexo,
                    fecha_ingreso=oferta.fecha_ingreso,
                    motivo=motivo,
                    detalle_por_dia=detalle_rechazo,
                )
            )
            continue

        mejor_dia = None
        mayor_deficit = -1

        for d_idx, peso_proy, edad_fin in dias_elegibles:
            pollos_actuales = dias[d_idx].total_pollos
            cap = _cap_dia(d_idx)
            if pollos_actuales + oferta.cantidad > cap:
                continue
            fecha = dias[d_idx].fecha
            es_sab = fecha.weekday() == 5
            obj_pref = params.limite_sabado if es_sab else params.pollos_diarios_objetivo_min
            deficit = obj_pref - pollos_actuales
            if deficit > mayor_deficit:
                mayor_deficit = deficit
                mejor_dia = d_idx

        if mejor_dia is None:
            mejor_pollos = float("inf")
            for d_idx, peso_proy, edad_fin in dias_elegibles:
                pollos_actuales = dias[d_idx].total_pollos
                cap = _cap_dia(d_idx)
                if pollos_actuales + oferta.cantidad <= cap and pollos_actuales < mejor_pollos:
                    mejor_pollos = pollos_actuales
                    mejor_dia = d_idx

        if mejor_dia is not None:
            lote = calcular_lote_proyectado(oferta, dias[mejor_dia].fecha, params)
            dias[mejor_dia].lotes.append(lote)
            dias[mejor_dia] = calcular_dia_faena(
                dias[mejor_dia].fecha, dias[mejor_dia].lotes, params=params,
                gallinas_cantidad=dias[mejor_dia].gallinas_cantidad,
                gallinas_livianas=dias[mejor_dia].gallinas_livianas_cantidad,
                gallinas_pesadas=dias[mejor_dia].gallinas_pesadas_cantidad,
            )
            dia_nombre = DIAS_SEMANA[mejor_dia] if mejor_dia < len(DIAS_SEMANA) else str(mejor_dia)
            detalle_asignados.append({
                "granja": oferta.granja,
                "galpon": oferta.galpon,
                "nucleo": oferta.nucleo,
                "cantidad": oferta.cantidad,
                "dia": dia_nombre,
            })
        else:
            dias_eleg_fechas = [dias[d].fecha for d, _, _ in dias_elegibles]
            no_asignados_resultado.append(
                LoteNoAsignado(
                    granja=oferta.granja,
                    galpon=oferta.galpon,
                    nucleo=oferta.nucleo,
                    cantidad=oferta.cantidad,
                    sexo=oferta.sexo,
                    fecha_ingreso=oferta.fecha_ingreso,
                    dias_elegibles=dias_eleg_fechas,
                    motivo="Lote nuevo del martes: excede tope diario máximo",
                )
            )

    return dias, no_asignados_resultado, fuera_rango_resultado, detalle_asignados


# ─── Alerta Temprana ────────────────────────────────────────────────────────────

def calcular_alerta_temprana(
    ofertas: List[LoteOferta],
    params: Parametros,
    fecha_referencia: Optional[date] = None,
) -> dict:
    """
    Analiza TODOS los lotes de la oferta y proyecta su peso al momento
    de faena ideal según su sexo, identificando tempranamente aquellos
    que no llegarán al rango aceptable de peso.

    Para cada lote calcula:
    - Peso proyectado a la edad ideal de faena (según sexo)
    - Ganancia mínima diaria necesaria para alcanzar el peso mínimo
    - Días restantes hasta la edad ideal
    - Clasificación semáforo: verde/amarillo/rojo

    Args:
        ofertas: Lista de lotes de la oferta cargada.
        params: Parámetros globales de cálculo.
        fecha_referencia: Fecha de referencia (hoy). Si None, se infiere.

    Returns:
        dict con lotes analizados, contadores y resúmenes.
    """
    if not ofertas:
        return {
            "total_lotes": 0, "lotes_ok": 0,
            "alertas_amarillas": 0, "alertas_rojas": 0,
            "lotes": [], "granjas": [],
        }

    # Fecha de referencia: fecha base de la oferta (fecha_peso + dias_proyectados)
    if fecha_referencia is None:
        fecha_referencia = ofertas[0].fecha_peso + timedelta(days=ofertas[0].dias_proyectados)

    lotes_resultado = []
    alertas_rojas = 0
    alertas_amarillas = 0
    lotes_ok = 0
    granjas_stats: dict[str, dict] = {}

    for oferta in ofertas:
        # Edad actual real del lote en la fecha de referencia
        fecha_base = oferta.fecha_peso + timedelta(days=oferta.dias_proyectados)
        edad_actual = oferta.edad_proyectada + (fecha_referencia - fecha_base).days

        # Edad ideal de faena según sexo
        if oferta.sexo.upper() == "H":
            edad_ideal = params.edad_ideal_hembra
            ganancia_esperada = params.ganancia_diaria_hembra
        elif oferta.sexo.upper() == "M":
            edad_ideal = params.edad_ideal_macho
            ganancia_esperada = params.ganancia_diaria_macho
        else:
            edad_ideal = params.edad_ideal_sin_sexar
            ganancia_esperada = params.ganancia_diaria_macho

        # Días restantes hasta la edad ideal
        dias_restantes = edad_ideal - edad_actual

        # Si el lote ya superó la edad máxima, no es candidato para alerta temprana
        if edad_actual >= params.edad_max_faena:
            continue

        # Ganancia diaria del lote (real reportada o default por sexo)
        ganancia_lote = oferta.ganancia_diaria if oferta.ganancia_diaria > 0 else ganancia_esperada

        # --- Proyección a la edad ideal ---
        # Usar la misma lógica de peso_vivo_retiro para consistencia
        fecha_faena_ideal = fecha_referencia + timedelta(days=max(dias_restantes, 0))
        edad_fin_ideal = calcular_edad_fin_retiro_v2(
            fecha_faena_ideal, oferta.fecha_peso, oferta.edad_proyectada,
            dias_proyectados=oferta.dias_proyectados,
        )
        peso_en_ideal = peso_vivo_retiro(
            oferta.sexo, edad_fin_ideal, oferta.edad_proyectada,
            oferta.peso_muestreo_proy, params,
            ganancia_diaria_lote=oferta.ganancia_diaria,
        )

        # --- Proyección a edad mínima y máxima de faena ---
        dias_a_min = params.edad_min_faena - edad_actual
        dias_a_max = params.edad_max_faena - edad_actual

        fecha_faena_min = fecha_referencia + timedelta(days=max(dias_a_min, 0))
        edad_fin_min = calcular_edad_fin_retiro_v2(
            fecha_faena_min, oferta.fecha_peso, oferta.edad_proyectada,
            dias_proyectados=oferta.dias_proyectados,
        )
        peso_en_min = peso_vivo_retiro(
            oferta.sexo, edad_fin_min, oferta.edad_proyectada,
            oferta.peso_muestreo_proy, params,
            ganancia_diaria_lote=oferta.ganancia_diaria,
        )

        fecha_faena_max = fecha_referencia + timedelta(days=max(dias_a_max, 0))
        edad_fin_max = calcular_edad_fin_retiro_v2(
            fecha_faena_max, oferta.fecha_peso, oferta.edad_proyectada,
            dias_proyectados=oferta.dias_proyectados,
        )
        peso_en_max = peso_vivo_retiro(
            oferta.sexo, edad_fin_max, oferta.edad_proyectada,
            oferta.peso_muestreo_proy, params,
            ganancia_diaria_lote=oferta.ganancia_diaria,
        )

        # --- Ganancia mínima necesaria para alcanzar peso_min_faena a edad ideal ---
        # Inversa de la fórmula peso_vivo_retiro
        dias_extra_ideal = max(edad_fin_ideal - oferta.edad_proyectada - 1, 0)
        medio_dia = params.ganancia_diaria_macho * params.medio_dia_ganancia
        if oferta.sexo.upper() != "H":
            # peso_min = ((dias_extra * gan) + peso_actual + medio_dia) * (1 - desc)
            # gan_necesaria = (peso_min / (1 - desc) - peso_actual - medio_dia) / dias_extra
            factor_desc = 1 - params.descuento_sin_sexar
            peso_target = params.peso_min_faena / factor_desc
        else:
            peso_target = params.peso_min_faena

        if dias_extra_ideal > 0:
            ganancia_necesaria = (peso_target - oferta.peso_muestreo_proy - medio_dia) / dias_extra_ideal
        else:
            ganancia_necesaria = 0.0

        ganancia_necesaria = max(ganancia_necesaria, 0.0)

        # --- Clasificación semáforo ---
        # Rojo: incluso a edad máxima no llega al peso mínimo
        # Amarillo: llega pero necesita mejorar ganancia (>10% sobre la actual)
        #           o peso en ideal está muy cerca del mínimo (<100g margen)
        # Verde: proyección cómoda dentro del rango

        mejor_peso_posible = peso_en_max  # peso máximo que puede alcanzar

        if mejor_peso_posible < params.peso_min_faena:
            nivel = "rojo"
            alertas_rojas += 1
            mensaje = (
                f"No alcanza peso mínimo ({params.peso_min_faena:.2f} kg) "
                f"ni a edad máxima ({params.edad_max_faena}d): "
                f"proyecta {mejor_peso_posible:.3f} kg"
            )
        elif peso_en_ideal < params.peso_min_faena:
            nivel = "amarillo"
            alertas_amarillas += 1
            deficit = params.peso_min_faena - peso_en_ideal
            mensaje = (
                f"Bajo peso a edad ideal ({edad_ideal}d): {peso_en_ideal:.3f} kg, "
                f"déficit {deficit*1000:.0f}g. "
                f"Necesita mejorar a {ganancia_necesaria:.3f} kg/día"
            )
        elif peso_en_ideal > params.peso_max_faena:
            if peso_en_min > params.peso_max_faena:
                nivel = "rojo"
                alertas_rojas += 1
                mensaje = (
                    f"Sobrepeso incluso a edad mínima ({params.edad_min_faena}d): "
                    f"{peso_en_min:.3f} kg (máx {params.peso_max_faena:.2f})"
                )
            else:
                nivel = "amarillo"
                alertas_amarillas += 1
                mensaje = (
                    f"Sobrepeso a edad ideal ({edad_ideal}d): {peso_en_ideal:.3f} kg. "
                    f"Requiere faena anticipada"
                )
        elif (peso_en_ideal - params.peso_min_faena) < 0.10:
            nivel = "amarillo"
            alertas_amarillas += 1
            margen = (peso_en_ideal - params.peso_min_faena) * 1000
            mensaje = (
                f"En rango pero ajustado: {peso_en_ideal:.3f} kg "
                f"(solo {margen:.0f}g sobre el mínimo)"
            )
        elif ganancia_necesaria > ganancia_lote * 1.1:
            nivel = "amarillo"
            alertas_amarillas += 1
            mensaje = (
                f"Ganancia actual ({ganancia_lote:.3f}) insuficiente. "
                f"Necesita {ganancia_necesaria:.3f} kg/día para alcanzar mínimo"
            )
        else:
            nivel = "verde"
            lotes_ok += 1
            mensaje = (
                f"Proyecta {peso_en_ideal:.3f} kg a edad ideal ({edad_ideal}d). "
                f"Dentro de rango"
            )

        # Ganancia deficiente flag
        ganancia_deficiente = (
            ganancia_lote > 0 and ganancia_esperada > 0
            and ganancia_lote < ganancia_esperada * 0.9
        )

        # Stats por granja
        if oferta.granja not in granjas_stats:
            granjas_stats[oferta.granja] = {
                "total": 0, "verde": 0, "amarillo": 0, "rojo": 0,
                "pollos_total": 0, "suma_peso_ideal": 0.0,
            }
        gs = granjas_stats[oferta.granja]
        gs["total"] += 1
        gs[nivel] += 1
        gs["pollos_total"] += oferta.cantidad
        gs["suma_peso_ideal"] += peso_en_ideal * oferta.cantidad

        lotes_resultado.append({
            "granja": oferta.granja,
            "galpon": oferta.galpon,
            "nucleo": oferta.nucleo,
            "cantidad": oferta.cantidad,
            "sexo": oferta.sexo,
            "edad_actual": edad_actual,
            "edad_ideal": edad_ideal,
            "dias_restantes": max(dias_restantes, 0),
            "peso_actual": oferta.peso_muestreo_proy,
            "peso_en_edad_ideal": round(peso_en_ideal, 3),
            "peso_en_edad_min": round(peso_en_min, 3),
            "peso_en_edad_max": round(peso_en_max, 3),
            "peso_min_faena": params.peso_min_faena,
            "peso_max_faena": params.peso_max_faena,
            "ganancia_diaria_lote": ganancia_lote,
            "ganancia_esperada": ganancia_esperada,
            "ganancia_necesaria": round(ganancia_necesaria, 4),
            "ganancia_deficiente": ganancia_deficiente,
            "nivel": nivel,
            "mensaje": mensaje,
        })

    # Resumen por granja
    granjas_resumen = []
    for granja, stats in sorted(granjas_stats.items()):
        peso_prom = (
            stats["suma_peso_ideal"] / stats["pollos_total"]
            if stats["pollos_total"] > 0 else 0
        )
        if stats["rojo"] > 0:
            nivel_granja = "rojo"
        elif stats["amarillo"] > 0:
            nivel_granja = "amarillo"
        else:
            nivel_granja = "verde"
        granjas_resumen.append({
            "granja": granja,
            "total_lotes": stats["total"],
            "lotes_verde": stats["verde"],
            "lotes_amarillo": stats["amarillo"],
            "lotes_rojo": stats["rojo"],
            "pollos_total": stats["pollos_total"],
            "peso_promedio_ideal": round(peso_prom, 3),
            "nivel": nivel_granja,
        })

    total_lotes = len(lotes_resultado)
    return {
        "total_lotes": total_lotes,
        "lotes_ok": lotes_ok,
        "alertas_amarillas": alertas_amarillas,
        "alertas_rojas": alertas_rojas,
        "pct_ok": round(lotes_ok / total_lotes * 100, 1) if total_lotes > 0 else 0,
        "peso_min_faena": params.peso_min_faena,
        "peso_max_faena": params.peso_max_faena,
        "edad_min_faena": params.edad_min_faena,
        "edad_max_faena": params.edad_max_faena,
        "lotes": lotes_resultado,
        "granjas": granjas_resumen,
    }


# ─── Ajuste con oferta del martes ──────────────────────────────────────────────

def aplicar_ajuste_martes(
    ofertas_martes: List[LoteOferta],
    semana: SemanaFaena,
    params: Optional[Parametros] = None,
) -> tuple:
    """
    Aplica la oferta del martes a una proyección existente.

    Matchea lotes por (granja, galpon, nucleo, sexo, fecha_ingreso).
    La fecha_ingreso identifica de forma unívoca cada lote dentro de un
    mismo galpón/núcleo/sexo, ya que representa la fecha de ingreso de
    las aves a la granja (dato estático que no cambia entre ofertas).

    - Lotes matcheados: actualiza datos y recalcula en el MISMO día asignado.
    - Lotes nuevos (en martes pero no en proyección): van a lotes_no_asignados.
    - Lotes faltantes (en proyección pero no en martes): se marcan en el resumen.

    Retorna (SemanaFaena actualizada, AjusteMartesResumen).
    """
    if params is None:
        params = Parametros()

    # 1. Indexar oferta martes por clave 5-tupla.
    #    fecha_ingreso distingue lotes del mismo galpón/núcleo/sexo que
    #    ingresaron en fechas distintas (común en datos reales).
    martes_index: dict[tuple, list[LoteOferta]] = {}
    for o in ofertas_martes:
        key = (o.granja, o.galpon, o.nucleo, o.sexo, o.fecha_ingreso)
        martes_index.setdefault(key, []).append(o)

    # Conjunto de claves que ya fueron totalmente consumidas.
    matched_keys: set[tuple] = set()
    resumen = AjusteMartesResumen()

    DIAS_SEMANA = ['Lunes', 'Martes', 'Miércoles', 'Jueves', 'Viernes', 'Sábado']

    # 2. Recorrer cada día y cada lote de la proyección
    for dia_idx, dia in enumerate(semana.dias):
        nuevos_lotes: List[LoteProyectado] = []

        for lote in dia.lotes:
            key = (lote.granja, lote.galpon, lote.nucleo, lote.sexo,
                   lote.fecha_ingreso_original)

            if key in martes_index and martes_index[key]:
                oferta_martes = martes_index[key].pop(0)  # FIFO
                # Marcar como consumida si la lista quedó vacía
                if not martes_index[key]:
                    matched_keys.add(key)

                # Guardar valores previos para el diff
                peso_antes = lote.peso_vivo_retiro
                edad_antes = lote.edad_fin_retiro
                cantidad_antes = lote.cantidad

                # Recalcular con datos del martes en el MISMO día
                nuevo_lote = calcular_lote_proyectado(
                    oferta_martes, lote.fecha_fin_retiro, params
                )
                nuevos_lotes.append(nuevo_lote)

                # Verificar si el lote sigue dentro del rango de elegibilidad
                # después de la actualización con datos del martes
                alertas_rango = []
                if nuevo_lote.edad_fin_retiro < params.edad_min_faena:
                    alertas_rango.append(
                        f"Edad {nuevo_lote.edad_fin_retiro} < mín {params.edad_min_faena}"
                    )
                if nuevo_lote.edad_fin_retiro > params.edad_max_faena:
                    alertas_rango.append(
                        f"Edad {nuevo_lote.edad_fin_retiro} > máx {params.edad_max_faena}"
                    )
                if nuevo_lote.peso_vivo_retiro < params.peso_min_faena:
                    alertas_rango.append(
                        f"Peso {nuevo_lote.peso_vivo_retiro:.2f} < mín {params.peso_min_faena:.2f}"
                    )
                if nuevo_lote.peso_vivo_retiro > params.peso_max_faena:
                    alertas_rango.append(
                        f"Peso {nuevo_lote.peso_vivo_retiro:.2f} > máx {params.peso_max_faena:.2f}"
                    )

                if alertas_rango:
                    dia_nombre = DIAS_SEMANA[dia_idx] if dia_idx < len(DIAS_SEMANA) else str(dia_idx)
                    resumen.lotes_fuera_rango_post_ajuste += 1
                    resumen.detalle_fuera_rango_post_ajuste.append({
                        "granja": lote.granja,
                        "galpon": lote.galpon,
                        "nucleo": lote.nucleo,
                        "cantidad": nuevo_lote.cantidad,
                        "dia": dia_nombre,
                        "alerta": "; ".join(alertas_rango),
                    })

                # Registrar cambios
                cambios = []
                if abs(nuevo_lote.peso_vivo_retiro - peso_antes) > 0.001:
                    cambios.append(f"Peso: {peso_antes:.2f} → {nuevo_lote.peso_vivo_retiro:.2f}")
                if nuevo_lote.edad_fin_retiro != edad_antes:
                    cambios.append(f"Edad: {edad_antes} → {nuevo_lote.edad_fin_retiro}")
                if nuevo_lote.cantidad != cantidad_antes:
                    cambios.append(f"Cantidad: {cantidad_antes} → {nuevo_lote.cantidad}")

                if cambios:
                    resumen.lotes_actualizados += 1
                    resumen.detalle_actualizados.append({
                        "granja": lote.granja,
                        "galpon": lote.galpon,
                        "nucleo": lote.nucleo,
                        "dia": DIAS_SEMANA[dia_idx] if dia_idx < len(DIAS_SEMANA) else str(dia_idx),
                        "cambios": ", ".join(cambios),
                    })
                # Si no hay cambios, el lote ya fue agregado arriba
            else:
                # Lote en proyección no está en oferta martes → faltante
                resumen.lotes_faltantes += 1
                resumen.detalle_faltantes.append({
                    "granja": lote.granja,
                    "galpon": lote.galpon,
                    "nucleo": lote.nucleo,
                    "cantidad": lote.cantidad,
                    "sexo": lote.sexo,
                    "dia": DIAS_SEMANA[dia_idx] if dia_idx < len(DIAS_SEMANA) else str(dia_idx),
                })
                # Mantener el lote como está (no se elimina automáticamente)
                nuevos_lotes.append(lote)

        dia.lotes = nuevos_lotes

    # 3. Lotes nuevos del martes: los que quedaron sin consumir en el index
    lotes_nuevos_oferta: List[LoteOferta] = []
    for key, ofertas_restantes in martes_index.items():
        for oferta in ofertas_restantes:
            resumen.lotes_nuevos += 1
            resumen.detalle_nuevos.append({
                "granja": oferta.granja,
                "galpon": oferta.galpon,
                "nucleo": oferta.nucleo,
                "cantidad": oferta.cantidad,
                "sexo": oferta.sexo,
            })
            lotes_nuevos_oferta.append(oferta)

    # Intentar asignar lotes nuevos a días con capacidad
    lotes_no_asignados_nuevos: List[LoteNoAsignado] = []
    lotes_fuera_rango_nuevos: List[LoteFueraRango] = []
    detalle_asignados_nuevos: List[dict] = []

    if lotes_nuevos_oferta:
        _, lotes_no_asignados_nuevos, lotes_fuera_rango_nuevos, detalle_asignados_nuevos = (
            _intentar_asignar_lotes_nuevos(lotes_nuevos_oferta, semana.dias, params)
        )

    resumen.lotes_nuevos_asignados = len(detalle_asignados_nuevos)
    resumen.detalle_nuevos_asignados = detalle_asignados_nuevos
    resumen.lotes_nuevos_fuera_rango = len(lotes_fuera_rango_nuevos)

    # 4. Combinar lotes no asignados previos + nuevos
    # Construir conjunto de claves de lotes nuevos que SÍ fueron asignados a un
    # día en el paso 3, para no duplicarlos en la lista de no-asignados.
    claves_asignados_nuevos: set[tuple] = set()
    for d in detalle_asignados_nuevos:
        for o in lotes_nuevos_oferta:
            if (o.granja == d["granja"] and o.galpon == d["galpon"]
                    and o.nucleo == d["nucleo"]):
                claves_asignados_nuevos.add(
                    (o.granja, o.galpon, o.nucleo, o.sexo, o.fecha_ingreso)
                )

    # Actualizar también los lotes_no_asignados previos si hay match en martes
    martes_lookup: dict[tuple, list[LoteOferta]] = {}
    for o in ofertas_martes:
        k = (o.granja, o.galpon, o.nucleo, o.sexo, o.fecha_ingreso)
        martes_lookup.setdefault(k, []).append(o)

    lotes_no_asignados_previos: List[LoteNoAsignado] = []
    for lna in semana.lotes_no_asignados:
        key = (lna.granja, lna.galpon, lna.nucleo, lna.sexo, lna.fecha_ingreso)
        # Si este lote fue asignado como "nuevo" en el paso 3, no duplicar
        if key in claves_asignados_nuevos:
            continue
        if key in martes_lookup and martes_lookup[key]:
            oferta_martes = martes_lookup[key][0]  # usa el primero disponible
            # Actualizar datos del lote no asignado
            lna.cantidad = oferta_martes.cantidad
            lna.sexo = oferta_martes.sexo
            lna.motivo = f"{lna.motivo} (datos actualizados con oferta martes)"
            lotes_no_asignados_previos.append(lna)
        else:
            lotes_no_asignados_previos.append(lna)

    todos_no_asignados = lotes_no_asignados_previos + lotes_no_asignados_nuevos

    # Combinar fuera de rango previos + nuevos del martes
    fuera_rango_previos = list(semana.lotes_fuera_rango) if semana.lotes_fuera_rango else []
    todos_fuera_rango = fuera_rango_previos + lotes_fuera_rango_nuevos

    # 5. Recalcular agregados de cada día y de la semana
    dias_recalculados: List[DiaFaena] = []
    for dia in semana.dias:
        dia_recalc = calcular_dia_faena(
            dia.fecha, dia.lotes, params=params,
            gallinas_cantidad=dia.gallinas_cantidad,
            gallinas_livianas=dia.gallinas_livianas_cantidad,
            gallinas_pesadas=dia.gallinas_pesadas_cantidad,
        )
        dias_recalculados.append(dia_recalc)

    resultado = calcular_semana_faena(
        semana.fecha_inicio,
        dias_recalculados,
        params,
        lotes_no_asignados=todos_no_asignados,
        lotes_fuera_rango=todos_fuera_rango,
    )

    return resultado, resumen
