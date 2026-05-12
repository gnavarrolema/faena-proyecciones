"""
Motor de cálculo para la proyección de faena avícola.
Replica la lógica de la hoja PROYEC1 del Excel.
"""
from datetime import date, timedelta

from typing import List, Optional
from pydantic import BaseModel
import math


DIAS_HASTA_FAENA_REFERENCIA = 42
MERMA_REFERENCIA_MIN = 0.045
MERMA_REFERENCIA_MAX = 0.075
MERMA_REFERENCIA_PASO = 0.005
TOLERANCIA_FECHA_CRUCE_DIAS = 3
EDAD_TOLERANCIA_GERENTE = 4
PESO_TOLERANCIA_GERENTE = 0.75
# Las ganancias diarias del criterio gerente se leen de Parametros
# (ganancia_diaria_macho=0.090, ganancia_diaria_hembra=0.079)
# para mantener consistencia con la planilla Excel del gerente.
PUENTE_VIERNES_TOLERANCIA_PESO_GERENTE = 0.10
# 0 = sin cap especifico para el viernes puente (se usa la capacidad regular del dia).
# Historico: 15177 era un cap operativo legado que limitaba el plan del gerente
# por debajo del objetivo real. Los usuarios pueden setear un valor positivo
# desde el panel de parametros si necesitan acotar el viernes puente.
PUENTE_VIERNES_CAPACIDAD_DEFAULT = 0


def _normalizar_objetivos_diarios(
    objetivos_diarios: Optional[List[int]],
    num_dias: int,
) -> Optional[List[int]]:
    """Valida y recorta objetivos diarios informados por el usuario."""
    if not objetivos_diarios:
        return None

    objetivos = []
    for valor in objetivos_diarios[:num_dias]:
        try:
            objetivo = int(valor)
        except (TypeError, ValueError):
            objetivo = 0
        objetivos.append(max(0, objetivo))

    if not any(objetivos):
        return None

    while len(objetivos) < num_dias:
        objetivos.append(objetivos[-1])

    return objetivos


def normalizar_granja_clave(granja: str) -> str:
    """Normaliza el nombre de granja para matching entre fuentes."""
    valor = " ".join((granja or "").strip().upper().split())
    for prefijo in ("LOS ", "LAS ", "EL ", "LA "):
        if valor.startswith(prefijo):
            return valor[len(prefijo):]
    return valor


# ─── Modelos ────────────────────────────────────────────────────────────────────

class Parametros(BaseModel):
    """Parámetros globales de cálculo."""
    ganancia_diaria_macho: float = 0.090
    ganancia_diaria_hembra: float = 0.079
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
    planificacion_continua_gerente: bool = False
    planificacion_continua_dias_habiles: int = 16
    planificacion_gerente_priorizar_peso_objetivo: bool = False
    pollos_viernes_puente: int = PUENTE_VIERNES_CAPACIDAD_DEFAULT  # Capacidad máxima para el viernes puente
    produccion_dias_hasta_faena: int = DIAS_HASTA_FAENA_REFERENCIA
    produccion_tolerancia_cruce_dias: int = TOLERANCIA_FECHA_CRUCE_DIAS
    produccion_mortalidad_min: float = MERMA_REFERENCIA_MIN
    produccion_mortalidad_max: float = MERMA_REFERENCIA_MAX
    produccion_mortalidad_paso: float = MERMA_REFERENCIA_PASO


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
    fecha_oferta: Optional[date] = None


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
    sobreedad: bool = False  # True si supera edad_max o peso_max (urgente)
    # Datos originales de la oferta para recálculo (mover lote, etc.)
    fecha_peso_original: Optional[date] = None
    ganancia_diaria_original: Optional[float] = None
    fecha_ingreso_original: Optional[date] = None
    dias_proyectados_original: int = 0
    # Compra a terceros
    es_compra_terceros: bool = False
    motivo_compra: Optional[str] = None
    # Exclusión manual (lote "tachado" por el usuario)
    excluido: bool = False
    motivo_exclusion: Optional[str] = None
    # Fraccionamiento automático para aproximar el criterio del gerente
    fragmentado: bool = False
    fragment_id: Optional[str] = None
    cantidad_original_lote: Optional[int] = None
    alerta_baja_edad: bool = False
    alerta_bajo_peso: bool = False


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
    lotes_reinsertados_no_asignados: int = 0
    lotes_nuevos_fuera_rango: int = 0
    lotes_faltantes: int = 0
    lotes_fuera_rango_post_ajuste: int = 0
    detalle_actualizados: List[dict] = []
    detalle_nuevos: List[dict] = []
    detalle_nuevos_asignados: List[dict] = []
    detalle_reinsertados_no_asignados: List[dict] = []
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
    fecha_base_override: Optional[date] = None,
) -> int:
    """
    Edad al fin del retiro calculada a partir de la fecha base de la oferta.

    La fecha base es fecha_peso + dias_proyectados (fecha en que se emitió la
    oferta).  edad_proyectada ya incluye esos días de proyección, por lo que
    la base correcta para contar "días extra" hasta el retiro es la fecha de
    la oferta, no la fecha de pesaje individual.
    """
    fecha_base = fecha_base_override or (fecha_peso + timedelta(days=dias_proyectados))
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


def diferencia_edad_ideal_criterio_gerente(sexo: str, edad_fin: int) -> int:
    """Diferencia de edad usada en la planilla del gerente."""
    if sexo.upper() == "M":
        return edad_fin - 40
    if sexo.upper() == "H":
        return edad_fin - 44
    return edad_fin - 42


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

    # medio_dia siempre usa ganancia macho * 0.5 (0.09*0.5=0.045), según la fórmula del Excel
    medio_dia = params.ganancia_diaria_macho * 0.5

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


def cajas_lote_por_peso(cantidad_pollos: int, peso_faen: float, kg_por_caja: float) -> float:
    """Cajas producidas usando el peso faenado exacto, equivalente a D/(20/O)."""
    if peso_faen <= 0 or kg_por_caja <= 0:
        return 0
    return round(cantidad_pollos * peso_faen / kg_por_caja, 0)


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
    cajas = cajas_lote_por_peso(oferta.cantidad, p_faenado, params.kg_por_caja)

    lote = LoteProyectado(
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
        dias_proyectados_original=oferta.dias_proyectados,
        cantidad_original_lote=oferta.cantidad,
    )
    lote.alerta_baja_edad = lote.edad_fin_retiro < params.edad_min_faena
    lote.alerta_bajo_peso = lote.peso_vivo_retiro < params.peso_min_faena
    return lote


def _ganancia_diaria_criterio_gerente(sexo: str, params: Parametros) -> float:
    """Ganancia diaria usada por la planilla del gerente.

    Excel del gerente: MACHO = 90 GR (0.090), HEMBRA = 79 GR (0.079).
    MIX y sin sexar usan la fórmula "SIN SEX" que aplica ganancia de macho.
    Los valores se leen de Parametros para mantener sincronización.
    """
    sexo_norm = (sexo or "").upper()
    if sexo_norm == "H":
        return params.ganancia_diaria_hembra
    # M, MIX y sin sexar usan ganancia de macho (fórmula SIN SEX del Excel)
    return params.ganancia_diaria_macho


def calcular_lote_proyectado_criterio_gerente(
    oferta: LoteOferta,
    fecha_fin_retiro: date,
    params: Parametros,
) -> LoteProyectado:
    """Replica la proyección que usa la planilla del gerente cuando existe fecha global de oferta."""

    fecha_base = oferta.fecha_oferta or (oferta.fecha_peso + timedelta(days=oferta.dias_proyectados))
    edad_fin = calcular_edad_fin_retiro_v2(
        fecha_fin_retiro,
        oferta.fecha_peso,
        oferta.edad_proyectada,
        dias_proyectados=oferta.dias_proyectados,
        fecha_base_override=fecha_base,
    )

    dif_edad = diferencia_edad_ideal_criterio_gerente(oferta.sexo, edad_fin)
    peso_vivo = peso_vivo_retiro(
        oferta.sexo,
        edad_fin,
        oferta.edad_proyectada,
        oferta.peso_muestreo_proy,
        params,
        ganancia_diaria_lote=_ganancia_diaria_criterio_gerente(oferta.sexo, params),
    )
    p_faenado = peso_faenado(peso_vivo, params.rendimiento_canal)
    calibre = calibre_promedio(p_faenado, params.kg_por_caja)
    cajas = cajas_lote_por_peso(oferta.cantidad, p_faenado, params.kg_por_caja)

    lote = LoteProyectado(
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
        fecha_peso_original=oferta.fecha_peso,
        ganancia_diaria_original=oferta.ganancia_diaria,
        fecha_ingreso_original=oferta.fecha_ingreso,
        dias_proyectados_original=oferta.dias_proyectados,
        cantidad_original_lote=oferta.cantidad,
    )
    lote.alerta_baja_edad = lote.edad_fin_retiro < params.edad_min_faena
    lote.alerta_bajo_peso = lote.peso_vivo_retiro < params.peso_min_faena
    return lote


def _crear_fragmento_proyectado(
    oferta: LoteOferta,
    fecha_fin_retiro: date,
    params: Parametros,
    cantidad_fragmento: int,
    fragmento_indice: int,
    total_fragmentos: int,
    cantidad_original_lote: Optional[int] = None,
    usar_formula_gerente: bool = False,
) -> LoteProyectado:
    lote = (
        calcular_lote_proyectado_criterio_gerente(oferta, fecha_fin_retiro, params)
        if usar_formula_gerente
        else calcular_lote_proyectado(oferta, fecha_fin_retiro, params)
    )
    lote.cantidad = cantidad_fragmento
    lote.cajas = cajas_lote_por_peso(cantidad_fragmento, lote.peso_faenado, params.kg_por_caja)
    lote.fragmentado = total_fragmentos > 1 or cantidad_fragmento != oferta.cantidad
    lote.cantidad_original_lote = cantidad_original_lote or oferta.cantidad
    if lote.fragmentado:
        fecha_ingreso = oferta.fecha_ingreso.isoformat() if oferta.fecha_ingreso else "sin-fecha"
        lote.fragment_id = (
            f"{normalizar_granja_clave(oferta.granja)}-"
            f"{oferta.galpon}-{oferta.nucleo}-{oferta.sexo}-{fecha_ingreso}-{fragmento_indice}"
        )
    return lote


def _generar_fechas_faena(
    fecha_inicio_semana: date,
    dias_faena: int,
    feriados: Optional[dict],
) -> tuple[list[date], bool, date]:
    incluir_sabado = dias_faena >= 6
    fecha_limite = fecha_inicio_semana + timedelta(days=5 if incluir_sabado else 4)
    if feriados:
        from .feriados import generar_dias_habiles

        fechas_dias = generar_dias_habiles(
            fecha_inicio_semana,
            dias_faena,
            feriados,
            incluir_sabado=incluir_sabado,
            fecha_limite=fecha_limite,
        )
    else:
        fechas_dias = [fecha_inicio_semana + timedelta(days=i) for i in range(dias_faena)]
    return fechas_dias, incluir_sabado, fecha_limite


def _generar_fechas_faena_continuas(
    fecha_inicio: date,
    dias_habiles: int,
    feriados: Optional[dict],
    incluir_sabado: bool,
) -> tuple[list[date], bool, date]:
    from .feriados import generar_dias_habiles

    fechas_dias = generar_dias_habiles(
        fecha_inicio,
        dias_habiles,
        feriados or {},
        incluir_sabado=incluir_sabado,
        fecha_limite=None,
    )
    fecha_limite = fechas_dias[-1] if fechas_dias else fecha_inicio
    return fechas_dias, incluir_sabado, fecha_limite


def _particionar_cantidad(cantidad_total: int, pesos: list[int]) -> list[int]:
    if not pesos:
        return []
    if sum(pesos) <= 0:
        base = cantidad_total // len(pesos)
        cantidades = [base for _ in pesos]
        for idx in range(cantidad_total - sum(cantidades)):
            cantidades[idx % len(cantidades)] += 1
        return cantidades

    cantidades = []
    restos = []
    total_asignado = 0
    total_pesos = sum(pesos)
    for idx, peso in enumerate(pesos):
        exacto = cantidad_total * peso / total_pesos
        base = int(exacto)
        cantidades.append(base)
        restos.append((exacto - base, idx))
        total_asignado += base

    for _, idx in sorted(restos, reverse=True)[:cantidad_total - total_asignado]:
        cantidades[idx] += 1
    return cantidades


def calcular_dia_faena(
    fecha: date,
    lotes: List[LoteProyectado],
    params: Optional["Parametros"] = None,
    gallinas_cantidad: int = 0,
    gallinas_livianas: int = 0,
    gallinas_pesadas: int = 0,
) -> DiaFaena:
    """Calcula los agregados de un día de faena, incluyendo alertas de carga."""
    lotes_activos = [l for l in lotes if l.cantidad > 0 and not l.excluido]
    total = sum(l.cantidad for l in lotes_activos)

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

    if lotes_activos:
        dia.peso_promedio_ponderado = peso_promedio_ponderado_dia(lotes_activos)
        dia.diferencia_edad_promedio = dif_edad_promedio_ponderada(lotes_activos)
        dia.calibre_promedio_ponderado = calibre_promedio_ponderado(lotes_activos)
        dia.cajas_totales = sum(l.cajas for l in lotes_activos)

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
        todos_lotes.extend([l for l in d.lotes if not l.excluido])

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
    if peso_proy < params.peso_min_faena:
        razones.append(f"Peso {peso_proy:.2f} < mín {params.peso_min_faena:.2f}")
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
    """Construye un motivo resumido de por qué el lote está fuera de rango.

    Solo se llama para lotes que no cumplen los límites DUROS (edad_min,
    peso_min). Lotes que superan edad_max/peso_max son elegibles y urgentes,
    no llegan aquí.
    """
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

    if peso_ultimo < params.peso_min_faena:
        razones.append(f"Peso: {peso_primer:.2f}–{peso_ultimo:.2f} kg (mín. {params.peso_min_faena:.2f})")

    return "; ".join(razones) if razones else "Fuera de rango edad/peso en todos los días"


def evaluar_elegibilidad_lote(
    oferta: LoteOferta,
    fecha_dia: date,
    params: Parametros,
) -> Optional[tuple]:
    """
    Evalúa si un lote es elegible para un día de faena específico.
    Retorna (peso_proy, edad_fin, sobreedad) si es elegible, None si no.

    Límites duros (rechazan): edad_min, peso_min — no se puede faenar
    un pollo inmaduro o demasiado liviano.

    Límites blandos (elegible pero urgente): edad_max, peso_max — un
    lote que supera la edad o peso máximo DEBE faenarse, no puede
    ignorarse.
    """
    edad_fin = calcular_edad_fin_retiro_v2(
        fecha_dia, oferta.fecha_peso, oferta.edad_proyectada,
        dias_proyectados=oferta.dias_proyectados,
    )

    # Límite duro: edad mínima (no se puede faenar pollo inmaduro)
    if edad_fin < params.edad_min_faena:
        return None

    peso_proy = _peso_proyectado_en_fecha(oferta, fecha_dia, params)

    # Límite duro: peso mínimo (no se puede faenar pollo muy liviano)
    if peso_proy < params.peso_min_faena:
        return None

    # Límites blandos: edad/peso máximo → lote elegible pero urgente
    sobreedad = edad_fin > params.edad_max_faena or peso_proy > params.peso_max_faena

    return (peso_proy, edad_fin, sobreedad)


def _evaluar_elegibilidad_lote_criterio_gerente(
    oferta: LoteOferta,
    fecha_dia: date,
    params: Parametros,
    minimos_como_alerta: bool,
) -> Optional[LoteProyectado]:
    lote = calcular_lote_proyectado_criterio_gerente(oferta, fecha_dia, params)
    brecha_edad = params.edad_min_faena - lote.edad_fin_retiro
    brecha_peso = params.peso_min_faena - lote.peso_vivo_retiro

    if minimos_como_alerta:
        if brecha_edad > EDAD_TOLERANCIA_GERENTE or brecha_peso > PESO_TOLERANCIA_GERENTE:
            return None
    else:
        if brecha_edad > 0 or brecha_peso > 0:
            return None

    lote.sobreedad = (
        lote.edad_fin_retiro > params.edad_max_faena
        or lote.peso_vivo_retiro > params.peso_max_faena
    )
    return lote


def _generar_proyeccion_criterio_gerente(
    ofertas: List[LoteOferta],
    fecha_inicio_semana: date,
    dias_faena: int,
    pollos_por_dia: int,
    objetivos_diarios: Optional[List[int]],
    params: Parametros,
    feriados: Optional[dict],
    gallinas: Optional[dict],
    permitir_fraccionamiento_lotes: bool,
    excluir_backlog_semana_previa: bool,
    minimos_como_alerta: bool,
    planificacion_continua: bool,
    incluir_sabado_continuo: bool,
) -> SemanaFaena:
    gallinas = gallinas or {}
    objetivo_preferido = max(
        params.pollos_diarios_objetivo_min,
        min(pollos_por_dia, params.pollos_diarios_objetivo_max),
    )
    if planificacion_continua:
        fechas_dias, _, fecha_limite = _generar_fechas_faena_continuas(
            fecha_inicio_semana,
            dias_faena,
            feriados,
            incluir_sabado=incluir_sabado_continuo,
        )
    else:
        fechas_dias, _, fecha_limite = _generar_fechas_faena(
            fecha_inicio_semana,
            dias_faena,
            feriados,
        )
    usa_viernes_puente = bool(planificacion_continua and fechas_dias and fechas_dias[0].weekday() == 4)
    fechas_semana_previa = [fecha_dia - timedelta(days=7) for fecha_dia in fechas_dias]
    num_dias = len(fechas_dias)
    objetivos_plan = _normalizar_objetivos_diarios(objetivos_diarios, num_dias)

    def _gallinas_total(fecha_iso: str) -> int:
        val = gallinas.get(fecha_iso, 0)
        if isinstance(val, dict):
            return val.get("livianas", 0) + val.get("pesadas", 0)
        return val

    def _gallinas_desglose(fecha_iso: str) -> tuple[int, int]:
        val = gallinas.get(fecha_iso, 0)
        if isinstance(val, dict):
            return val.get("livianas", 0), val.get("pesadas", 0)
        return val, 0

    def _capacidad_dia(d_idx: int) -> int:
        fecha = fechas_dias[d_idx]
        es_sabado = fecha.weekday() == 5
        # Sabados: limite estricto. L-V: capacidad real con horas extras.
        # capacidad_maxima_planta es solo el umbral de alerta "HORAS EXTRAS".
        cap_base = params.limite_sabado if es_sabado else params.capacidad_con_horas_extras
        # Viernes puente: respetar capacidad configurada si es > 0
        if usa_viernes_puente and d_idx == 0 and params.pollos_viernes_puente > 0:
            cap_base = min(cap_base, params.pollos_viernes_puente)
        return max(0, cap_base - _gallinas_total(fecha.isoformat()))

    def _objetivo_dia(d_idx: int) -> int:
        fecha = fechas_dias[d_idx]
        es_sabado = fecha.weekday() == 5
        gall = _gallinas_total(fecha.isoformat())
        if objetivos_plan and d_idx < len(objetivos_plan):
            return max(0, min(objetivos_plan[d_idx], _capacidad_dia(d_idx)))
        if es_sabado:
            return max(0, params.limite_sabado - gall)
        return max(0, objetivo_preferido - gall)

    candidatos_por_lote: dict[int, list[dict]] = {}
    candidatos_por_dia: dict[int, dict[int, dict]] = {}
    fuera_rango_data: dict[int, list[dict]] = {}
    backlog_previo: set[int] = set()

    for i, oferta in enumerate(ofertas):
        candidatos = []
        detalle_rechazo = []
        for d_idx, fecha_dia in enumerate(fechas_dias):
            lote = _evaluar_elegibilidad_lote_criterio_gerente(
                oferta,
                fecha_dia,
                params,
                minimos_como_alerta=minimos_como_alerta,
            )
            if lote is None:
                detalle_rechazo.append(_detalle_rechazo_dia(oferta, fecha_dia, params))
                continue

            es_candidato_viernes_puente = usa_viernes_puente and d_idx == 0
            if (
                es_candidato_viernes_puente
                and (
                    lote.edad_fin_retiro < params.edad_min_faena
                    or lote.peso_vivo_retiro < params.peso_min_faena - PUENTE_VIERNES_TOLERANCIA_PESO_GERENTE
                )
            ):
                detalle_rechazo.append(_detalle_rechazo_dia(oferta, fecha_dia, params))
                continue

            brecha_edad = max(0, params.edad_min_faena - lote.edad_fin_retiro)
            brecha_peso = max(0.0, params.peso_min_faena - lote.peso_vivo_retiro)
            alertas = int(lote.alerta_baja_edad) + int(lote.alerta_bajo_peso)
            if es_candidato_viernes_puente:
                brecha_edad = 0
                brecha_peso = 0.0
                alertas = 0

            candidatos.append({
                "dia_idx": d_idx,
                "lote": lote,
                "alertas": alertas,
                "brecha_edad": brecha_edad,
                "brecha_peso": brecha_peso,
                "distancia_objetivo": abs(lote.peso_vivo_retiro - params.peso_objetivo_recepcion),
            })
            candidatos_por_dia.setdefault(i, {})[d_idx] = {
                "lote": lote,
                "alertas": alertas,
                "brecha_edad": brecha_edad,
                "brecha_peso": brecha_peso,
                "distancia_objetivo": abs(lote.peso_vivo_retiro - params.peso_objetivo_recepcion),
            }

        if candidatos:
            candidatos_por_lote[i] = candidatos
            if excluir_backlog_semana_previa and any(
                evaluar_elegibilidad_lote(oferta, fecha_previa, params) is not None
                for fecha_previa in fechas_semana_previa
            ):
                backlog_previo.add(i)
        else:
            fuera_rango_data[i] = detalle_rechazo

    pendientes: dict[int, int] = {i: ofertas[i].cantidad for i in candidatos_por_lote}
    asignaciones: dict[int, dict[int, int]] = {d_idx: {} for d_idx in range(num_dias)}
    pollos_dia: dict[int, int] = {d_idx: 0 for d_idx in range(num_dias)}

    def _registrar_asignacion(lote_idx: int, dia_idx: int, cantidad: int):
        if cantidad <= 0:
            return
        asignaciones[dia_idx][lote_idx] = asignaciones[dia_idx].get(lote_idx, 0) + cantidad
        pendientes[lote_idx] -= cantidad
        pollos_dia[dia_idx] += cantidad

    # ── Cascada de madurez: lógica del gerente ──────────────────────────
    # 1) Ordenar lotes por madurez (peso desc en primer día elegible)
    # 2) Llenar días secuencialmente (más temprano primero)
    # 3) Target dinámico: capacidad planta si total pendiente > lo que
    #    cabe al objetivo normal, sino pollos_diarios_objetivo_max

    def _peso_primer_dia(lote_idx: int) -> float:
        """Peso proyectado del lote en su primer día elegible."""
        candidatos = candidatos_por_lote[lote_idx]
        primer = min(candidatos, key=lambda c: c["dia_idx"])
        return primer["lote"].peso_vivo_retiro

    def _prioridad_madurez(lote_idx: int) -> tuple:
        """Prioridad cascada: sobreedad primero, luego más pesado, más viejo."""
        candidatos = candidatos_por_lote[lote_idx]
        if (
            usa_viernes_puente
            and normalizar_granja_clave(ofertas[lote_idx].granja) in granjas_viernes_puente
        ):
            candidatos_post_puente = [
                candidato
                for candidato in candidatos
                if candidato["dia_idx"] > 1
            ]
            candidatos = candidatos_post_puente or [
                candidato
                for candidato in candidatos
                if candidato["dia_idx"] > 0
            ] or candidatos
        if usa_viernes_puente:
            primer = min(candidatos, key=lambda c: c["dia_idx"])
            es_granja_puente = (
                normalizar_granja_clave(ofertas[lote_idx].granja) in granjas_viernes_puente
            )
            return (
                0 if es_granja_puente else 1,
                0 if primer["lote"].sobreedad else 1,
                primer["dia_idx"],
                -primer["lote"].peso_vivo_retiro,
                -primer["lote"].edad_fin_retiro,
                primer["alertas"],
                primer["brecha_peso"],
                primer["brecha_edad"],
                len(candidatos),
            )
        primer = min(candidatos, key=lambda c: c["dia_idx"])
        primer_limpio = min(
            (c for c in candidatos if c["alertas"] == 0),
            key=lambda c: c["dia_idx"],
            default=primer,
        )
        if primer["alertas"] > 0:
            dias_hasta_limpio = primer_limpio["dia_idx"] - primer["dia_idx"]
            primer_dia_limpio_idx = primer_limpio["dia_idx"]
        else:
            dias_hasta_limpio = math.inf
            primer_dia_limpio_idx = math.inf
        mejor_limpio_dist = min(
            (c["distancia_objetivo"] for c in candidatos if c["alertas"] == 0),
            default=math.inf,
        )
        return (
            0 if primer["lote"].sobreedad else 1,
            primer["alertas"],
            dias_hasta_limpio,
            primer_dia_limpio_idx,
            primer["brecha_peso"],
            primer["brecha_edad"],
            mejor_limpio_dist if params.planificacion_gerente_priorizar_peso_objetivo else math.inf,
            -primer["lote"].peso_vivo_retiro,
            -primer["lote"].edad_fin_retiro,
            len(candidatos),
        )

    granjas_viernes_puente: set[str] = set()

    def _preasignar_viernes_puente():
        """Reserva el viernes puente como día reducido antes de llenar la semana normal."""
        if not usa_viernes_puente or num_dias == 0:
            return

        capacidad_puente = _capacidad_dia(0)
        if capacidad_puente <= 0:
            return

        candidatos_puente = [
            lote_idx
            for lote_idx, candidatos in candidatos_por_lote.items()
            if any(c["dia_idx"] == 0 for c in candidatos)
        ]

        def _prioridad_viernes_puente(lote_idx: int) -> tuple:
            candidato = candidatos_por_dia[lote_idx][0]
            lote = candidato["lote"]
            return (
                candidato["alertas"],
                candidato["brecha_peso"],
                candidato["brecha_edad"],
                -lote.peso_vivo_retiro,
                -lote.edad_fin_retiro,
                lote_idx,
            )

        for lote_idx in sorted(candidatos_puente, key=_prioridad_viernes_puente):
            espacio = capacidad_puente - pollos_dia[0]
            if espacio <= 0:
                break
            cantidad_pendiente = pendientes[lote_idx]
            if cantidad_pendiente <= 0:
                continue

            if permitir_fraccionamiento_lotes:
                cantidad = min(cantidad_pendiente, espacio)
            elif cantidad_pendiente <= espacio:
                cantidad = cantidad_pendiente
            else:
                continue

            _registrar_asignacion(lote_idx, 0, cantidad)
            granjas_viernes_puente.add(normalizar_granja_clave(ofertas[lote_idx].granja))

    def _target_dia_dinamico(d_idx: int) -> int:
        """Target de asignacion en modo gerente.

        Si el usuario informa un plan comercial diario, ese plan es la meta
        de faena. Si no existe, se conserva el comportamiento anterior y se
        usa la capacidad real disponible para absorber semanas de alta carga.
        """
        if objetivos_plan and d_idx < len(objetivos_plan):
            return _objetivo_dia(d_idx)
        return _capacidad_dia(d_idx)

    def _llenar_cascada(indices: list[int]):
        """Llena días secuencialmente; con plan comercial respeta el orden de la oferta."""
        sorted_indices = indices if objetivos_plan else sorted(indices, key=_prioridad_madurez)

        for lote_idx in sorted_indices:
            while pendientes[lote_idx] > 0:
                restante = pendientes[lote_idx]
                # Buscar primer día elegible con espacio bajo target dinámico
                mejor_dia = None
                mejor_espacio = 0
                if objetivos_plan:
                    candidatos_ordenados = sorted(
                        candidatos_por_lote[lote_idx],
                        key=lambda c: c["dia_idx"],
                    )
                else:
                    candidatos_ordenados = sorted(
                        candidatos_por_lote[lote_idx],
                        key=(
                            lambda c: (
                                c["dia_idx"],
                                c["alertas"],
                                c["brecha_peso"],
                                c["brecha_edad"],
                            )
                            if usa_viernes_puente
                            else (
                                c["alertas"],
                                c["brecha_peso"],
                                c["brecha_edad"],
                                c["distancia_objetivo"] if (
                                    params.planificacion_gerente_priorizar_peso_objetivo
                                    and c["alertas"] == 0
                                ) else math.inf,
                                c["dia_idx"],
                            )
                        ),
                    )
                for candidato in candidatos_ordenados:
                    dia_idx = candidato["dia_idx"]
                    if (
                        usa_viernes_puente
                        and dia_idx == 1
                        and normalizar_granja_clave(ofertas[lote_idx].granja) in granjas_viernes_puente
                    ):
                        continue
                    target = _target_dia_dinamico(dia_idx)
                    espacio = target - pollos_dia[dia_idx]
                    if espacio > 0:
                        mejor_dia = dia_idx
                        mejor_espacio = espacio
                        break

                if mejor_dia is None:
                    break  # No cabe en ningún día bajo target dinámico → diferir

                if permitir_fraccionamiento_lotes:
                    cantidad = min(restante, mejor_espacio)
                    if cantidad <= 0:
                        break
                    _registrar_asignacion(lote_idx, mejor_dia, cantidad)
                else:
                    if restante <= mejor_espacio:
                        _registrar_asignacion(lote_idx, mejor_dia, restante)
                    else:
                        break  # No cabe entero

    lotes_primarios = [i for i in candidatos_por_lote if i not in backlog_previo]
    lotes_respaldo = [i for i in backlog_previo if i in candidatos_por_lote]

    # En modo cascada sin plan comercial, los lotes de backlog se incluyen
    # en el sort principal por madurez. Con plan comercial diario, la oferta
    # ya viene ordenada por el criterio operativo del gerente y se respeta.
    todos_los_lotes = (
        list(candidatos_por_lote.keys())
        if objetivos_plan
        else sorted(
            list(candidatos_por_lote.keys()),
            key=_prioridad_madurez,
        )
    )

    _preasignar_viernes_puente()
    _llenar_cascada(todos_los_lotes)

    dias_por_lote: dict[int, list[tuple[int, int]]] = {}
    for dia_idx, asignaciones_dia in asignaciones.items():
        for lote_idx, cantidad in asignaciones_dia.items():
            dias_por_lote.setdefault(lote_idx, []).append((dia_idx, cantidad))
    for fragmentos_lote in dias_por_lote.values():
        fragmentos_lote.sort(key=lambda item: item[0])

    dias_resultado: List[DiaFaena] = []
    for d_idx, fecha_dia in enumerate(fechas_dias):
        lotes_dia: List[LoteProyectado] = []
        lotes_ordenados = sorted(
            asignaciones[d_idx].items(),
            key=lambda item: -candidatos_por_dia[item[0]][d_idx]["lote"].peso_vivo_retiro,
        )
        for lote_idx, cantidad in lotes_ordenados:
            fragmentos_lote = dias_por_lote.get(lote_idx, [])
            fragmento_indice = next(
                idx + 1
                for idx, (dia_fragmento, _) in enumerate(fragmentos_lote)
                if dia_fragmento == d_idx
            )
            lote = _crear_fragmento_proyectado(
                ofertas[lote_idx],
                fecha_dia,
                params,
                cantidad_fragmento=cantidad,
                fragmento_indice=fragmento_indice,
                total_fragmentos=len(fragmentos_lote),
                cantidad_original_lote=ofertas[lote_idx].cantidad,
                usar_formula_gerente=True,
            )
            lote.sobreedad = candidatos_por_dia[lote_idx][d_idx]["lote"].sobreedad
            lotes_dia.append(lote)

        gall_total = _gallinas_total(fecha_dia.isoformat())
        gall_liv, gall_pes = _gallinas_desglose(fecha_dia.isoformat())
        dias_resultado.append(
            calcular_dia_faena(
                fecha_dia,
                lotes_dia,
                params=params,
                gallinas_cantidad=gall_total,
                gallinas_livianas=gall_liv,
                gallinas_pesadas=gall_pes,
            )
        )

    lotes_no_asignados_resultado: List[LoteNoAsignado] = []
    for lote_idx, cantidad_restante in pendientes.items():
        if cantidad_restante <= 0:
            continue
        oferta = ofertas[lote_idx]
        dias_elegibles = [fechas_dias[c["dia_idx"]] for c in candidatos_por_lote.get(lote_idx, [])]
        if lote_idx in backlog_previo and cantidad_restante == oferta.cantidad:
            motivo = "Ya era elegible en la semana previa; quedó como respaldo y no fue necesario"
        elif cantidad_restante < oferta.cantidad:
            motivo = "Saldo del lote fragmentado sin capacidad disponible"
        else:
            motivo = "Excede la capacidad disponible en los días elegibles"
        lotes_no_asignados_resultado.append(
            LoteNoAsignado(
                granja=oferta.granja,
                galpon=oferta.galpon,
                nucleo=oferta.nucleo,
                cantidad=cantidad_restante,
                sexo=oferta.sexo,
                fecha_ingreso=oferta.fecha_ingreso,
                dias_elegibles=dias_elegibles,
                motivo=motivo,
            )
        )

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

    feriados_aplicados_lista: List[FeriadoAplicado] = []
    if feriados:
        for f_fecha, f_nombre in sorted(feriados.items()):
            if fecha_inicio_semana <= f_fecha <= fecha_limite and f_fecha not in fechas_dias:
                feriados_aplicados_lista.append(FeriadoAplicado(fecha=f_fecha, nombre=f_nombre))

    semana = calcular_semana_faena(
        fecha_inicio_semana,
        dias_resultado,
        params,
        lotes_no_asignados=lotes_no_asignados_resultado,
        lotes_fuera_rango=lotes_fuera_rango_resultado,
    )
    semana.feriados_aplicados = feriados_aplicados_lista

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


def generar_proyeccion(
    ofertas: List[LoteOferta],
    fecha_inicio_semana: date,
    dias_faena: int = 5,
    pollos_por_dia: int = 35000,
    objetivos_diarios: Optional[List[int]] = None,
    params: Optional[Parametros] = None,
    feriados: Optional[dict] = None,
    gallinas: Optional[dict] = None,
    criterio_gerente: bool = False,
    permitir_fraccionamiento_lotes: Optional[bool] = None,
    excluir_backlog_semana_previa: Optional[bool] = None,
    minimos_como_alerta: Optional[bool] = None,
    planificacion_continua_gerente: bool = False,
    incluir_sabado_continuo_gerente: bool = False,
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

    if criterio_gerente:
        if permitir_fraccionamiento_lotes is None:
            permitir_fraccionamiento_lotes = True
        if excluir_backlog_semana_previa is None:
            excluir_backlog_semana_previa = True
        if minimos_como_alerta is None:
            minimos_como_alerta = True
        return _generar_proyeccion_criterio_gerente(
            ofertas=ofertas,
            fecha_inicio_semana=fecha_inicio_semana,
            dias_faena=dias_faena,
            pollos_por_dia=pollos_por_dia,
            objetivos_diarios=objetivos_diarios,
            params=params,
            feriados=feriados,
            gallinas=gallinas,
            permitir_fraccionamiento_lotes=permitir_fraccionamiento_lotes,
            excluir_backlog_semana_previa=excluir_backlog_semana_previa,
            minimos_como_alerta=minimos_como_alerta,
            planificacion_continua=planificacion_continua_gerente,
            incluir_sabado_continuo=incluir_sabado_continuo_gerente,
        )

    objetivo_preferido = max(
        params.pollos_diarios_objetivo_min,
        min(pollos_por_dia, params.pollos_diarios_objetivo_max),
    )

    # Generar días hábiles saltando feriados y domingos
    fechas_dias, _, fecha_limite = _generar_fechas_faena(
        fecha_inicio_semana,
        dias_faena,
        feriados,
    )

    num_dias = len(fechas_dias)
    objetivos_plan = _normalizar_objetivos_diarios(objetivos_diarios, num_dias)

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

    # Capacidad maxima por dia: sabados = limite_sabado, L-V = capacidad_con_horas_extras.
    # capacidad_maxima_planta es solo el umbral de alerta "HORAS EXTRAS".
    # Se descuenta la capacidad ocupada por gallinas
    def _capacidad_dia(d_idx: int) -> int:
        fecha = fechas_dias[d_idx]
        es_sabado = fecha.weekday() == 5
        cap_base = params.limite_sabado if es_sabado else params.capacidad_con_horas_extras
        gall = _gallinas_total(fecha.isoformat())
        capacidad = max(0, cap_base - gall)
        if objetivos_plan and d_idx < len(objetivos_plan):
            return min(capacidad, objetivos_plan[d_idx])
        return capacidad

    # Objetivo preferido por día (no puede superar la capacidad del día)
    def _objetivo_dia(d_idx: int) -> int:
        fecha = fechas_dias[d_idx]
        es_sabado = fecha.weekday() == 5
        gall = _gallinas_total(fecha.isoformat())
        if objetivos_plan and d_idx < len(objetivos_plan):
            return max(0, min(objetivos_plan[d_idx], _capacidad_dia(d_idx)))
        if es_sabado:
            # Sábado: objetivo = limite_sabado (estricto 20k)
            return max(0, params.limite_sabado - gall)
        return max(0, objetivo_preferido - gall)

    # ── Fase 1: Matriz de elegibilidad ──────────────────────────────────────
    elegibilidad: dict[int, list[tuple[int, float, int, bool]]] = {}
    fuera_rango_data: dict[int, list[dict]] = {}  # idx → detalle por día

    for i, oferta in enumerate(ofertas):
        dias_elegibles = []
        detalle_rechazo = []
        for d_idx, fecha_dia in enumerate(fechas_dias):
            resultado = evaluar_elegibilidad_lote(oferta, fecha_dia, params)
            if resultado:
                peso_proy, edad_fin, sobreedad = resultado
                dias_elegibles.append((d_idx, peso_proy, edad_fin, sobreedad))
            else:
                detalle_rechazo.append(
                    _detalle_rechazo_dia(oferta, fecha_dia, params)
                )
        if dias_elegibles:
            elegibilidad[i] = dias_elegibles
        else:
            fuera_rango_data[i] = detalle_rechazo

    # Estructuras de asignación
    asignaciones: dict[int, list[int]] = {d: [] for d in range(num_dias)}
    pollos_dia: dict[int, int] = {d: 0 for d in range(num_dias)}
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

    def _prioridad_dinamica_lote(lote_idx: int) -> tuple:
        """Prioridad consistente basada en la mejor foto recalculada del lote dentro de la semana.

        No parte lotes. Solo define qué lote se intenta ubicar primero cuando varios
        compiten por la misma capacidad semanal.
        """
        dias_eleg = elegibilidad[lote_idx]
        oferta = ofertas[lote_idx]
        todos_sobreedad = all(s for _, _, _, s in dias_eleg)
        mejor_dif_ideal = min(
            abs(diferencia_edad_ideal(oferta.sexo, edad_fin, params))
            for _, _, edad_fin, _ in dias_eleg
        )
        peso_max = max(peso for _, peso, _, _ in dias_eleg)
        edad_max = max(edad for _, _, edad, _ in dias_eleg)
        dia_temprano = min(d for d, _, _, _ in dias_eleg)

        return (
            len(dias_eleg),
            0 if todos_sobreedad else 1,
            mejor_dif_ideal,
            -peso_max,
            -edad_max,
            dia_temprano,
            -oferta.cantidad,
        )

    # ── Fase 2: Propagación de restricciones ────────────────────────────────
    cambio = True
    while cambio:
        cambio = False

        # 2a: Lotes elegibles en un solo día → asignación forzada
        for i in sorted(elegibilidad.keys(), key=_prioridad_dinamica_lote):
            if i in asignados or i in no_asignados:
                continue
            dias_eleg = [d for d, _, _, _ in elegibilidad[i]]
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
        for d_idx in range(num_dias):
            candidatos_dia = [
                i for i, dias_eleg in elegibilidad.items()
                if i not in asignados
                and i not in no_asignados
                and any(d == d_idx for d, _, _, _ in dias_eleg)
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

    # ── Fase 2.5: Asignación prioritaria de lotes sobreedad ─────────────
    # Solo lotes que son sobreedad en TODOS sus días elegibles (realmente
    # urgentes — no tienen ningún día dentro del rango normal). Lotes que
    # son sobreedad solo en algunos días se asignan en Fase 3, que los
    # ubicará en un día no-sobreedad con mejor edad ideal.
    sobreedad_restantes = [
        i for i in elegibilidad
        if i not in asignados and i not in no_asignados
        and all(s for _, _, _, s in elegibilidad[i])
    ]
    sobreedad_restantes.sort(key=_prioridad_dinamica_lote)
    for i in sobreedad_restantes:
        dias_eleg = elegibilidad[i]
        # Asignar al día elegible con mayor capacidad remanente
        mejor_dia = None
        mayor_margen = -1
        for d_idx, peso_proy, edad_fin, _ in dias_eleg:
            if _puede_asignarse(i, d_idx):
                margen = _capacidad_dia(d_idx) - pollos_dia[d_idx]
                if margen > mayor_margen:
                    mayor_margen = margen
                    mejor_dia = d_idx
        if mejor_dia is not None:
            _asignar(i, mejor_dia)
        else:
            no_asignados[i] = (
                "Lote sobreedad/sobrepeso urgente: excede tope diario máximo en todos los días"
            )

    # ── Fase 3: Asignación flexible (lotes restantes, bajo objetivo) ───────
    # Optimiza por edad ideal según sexo: machos (ideal 40) a días tempranos,
    # hembras (ideal 44) a días tardíos. Ordena lotes por restricción
    # (menos días elegibles primero) y luego por peso descendente.
    restantes = [
        i for i in elegibilidad if i not in asignados and i not in no_asignados
    ]
    restantes_ordenados = sorted(restantes, key=_prioridad_dinamica_lote)

    pendientes = []

    for i in restantes_ordenados:
        dias_eleg = elegibilidad[i]
        sexo = ofertas[i].sexo

        # Para cada día elegible con capacidad, calcular score combinado:
        #   1) Minimizar |diferencia_edad_ideal| (prioridad principal)
        #   2) Mayor déficit respecto al objetivo (desempate)
        #   3) Día más temprano (último desempate)
        mejor_dia = None
        mejor_score = None

        for d_idx, peso_proy, edad_fin, _ in dias_eleg:
            if not _puede_asignarse(i, d_idx):
                continue
            obj = _objetivo_dia(d_idx)
            deficit = obj - pollos_dia[d_idx]
            if deficit <= 0:
                continue

            dif_edad = abs(diferencia_edad_ideal(sexo, edad_fin, params))
            # Tupla de score: menor dif_edad es mejor (negamos),
            # mayor deficit es mejor, día más temprano es mejor (negamos)
            score = (-dif_edad, deficit, -d_idx)

            if mejor_score is None or score > mejor_score:
                mejor_score = score
                mejor_dia = d_idx

        if mejor_dia is not None:
            _asignar(i, mejor_dia)
        else:
            pendientes.append(i)

    # ── Fase 4: Excedentes → día menos cargado (con tope duro) ─────────────
    for i in sorted(pendientes, key=_prioridad_dinamica_lote):
        dias_eleg = elegibilidad[i]

        mejor_dia = None
        mejor_pollos = float("inf")

        for d_idx, peso_proy, edad_fin, _ in dias_eleg:
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

    # ── Fase 5: Horas extras — segunda oportunidad con capacidad extendida ─
    # Lotes que no cupieron bajo capacidad normal pueden asignarse con horas
    # extras (capacidad_con_horas_extras). Se prefiere el día menos cargado.
    def _capacidad_dia_extras(d_idx: int) -> int:
        fecha = fechas_dias[d_idx]
        es_sabado = fecha.weekday() == 5
        # Sábados no tienen horas extras: mantienen limite_sabado
        cap_base = params.limite_sabado if es_sabado else params.capacidad_con_horas_extras
        gall = _gallinas_total(fecha.isoformat())
        capacidad = max(0, cap_base - gall)
        if objetivos_plan and d_idx < len(objetivos_plan):
            return min(capacidad, objetivos_plan[d_idx])
        return capacidad

    def _puede_asignarse_extras(lote_idx: int, dia_idx: int) -> bool:
        return pollos_dia[dia_idx] + ofertas[lote_idx].cantidad <= _capacidad_dia_extras(dia_idx)

    lotes_aun_no_asignados = sorted(
        [i for i in no_asignados if i in elegibilidad],
        key=_prioridad_dinamica_lote,
    )
    for i in lotes_aun_no_asignados:
        dias_eleg = elegibilidad[i]
        mejor_dia = None
        mejor_pollos = float("inf")
        for d_idx, _, _, _ in dias_eleg:
            pollos_actuales = pollos_dia[d_idx]
            if _puede_asignarse_extras(i, d_idx) and pollos_actuales < mejor_pollos:
                mejor_pollos = pollos_actuales
                mejor_dia = d_idx
        if mejor_dia is not None:
            _asignar(i, mejor_dia)
            del no_asignados[i]

    # ── Fase 5.5: Rescate anti-diferimiento ─────────────────────────────────
    # Lotes que aún no se asignaron serían diferidos a S2.  Si en S2 estarían
    # AÚN MÁS fuera de rango (más sobreedad/sobrepeso) que en el mejor día
    # de S1, es preferible forzar la asignación en S1 aceptando sobreedad
    # leve, antes que empeorar el problema con una semana extra de ganancia.
    fecha_inicio_s2 = fecha_inicio_semana + timedelta(days=7)
    fecha_media_s2 = fecha_inicio_s2 + timedelta(days=2)  # miércoles S2

    def _desviacion_s2(lote_idx: int) -> float:
        """Desviación combinada (edad + peso) que tendría el lote en S2."""
        o = ofertas[lote_idx]
        edad = calcular_edad_fin_retiro_v2(
            fecha_media_s2, o.fecha_peso, o.edad_proyectada,
            dias_proyectados=o.dias_proyectados,
        )
        peso = _peso_proyectado_en_fecha(o, fecha_media_s2, params)
        return max(0, edad - params.edad_max_faena) + max(0.0, peso - params.peso_max_faena)

    def _desviacion_s1_en_dia(lote_idx: int, d_idx: int) -> float:
        """Desviación combinada del lote si se faena en el día d_idx de S1."""
        for d, peso_proy, edad_fin, _ in elegibilidad.get(lote_idx, []):
            if d == d_idx:
                return max(0, edad_fin - params.edad_max_faena) + max(0.0, peso_proy - params.peso_max_faena)
        return float("inf")  # no elegible ese día

    def _desasignar(lote_idx: int, dia_idx: int):
        """Quita un lote de su día asignado y actualiza estructuras."""
        asignaciones[dia_idx].remove(lote_idx)
        pollos_dia[dia_idx] -= ofertas[lote_idx].cantidad
        asignados.discard(lote_idx)

    # Paso A: intento directo (si cabe bajo cap extras)
    lotes_rescate = sorted(
        [i for i in no_asignados if i in elegibilidad],
        key=_prioridad_dinamica_lote,
    )
    for i in lotes_rescate:
        dias_eleg = elegibilidad[i]
        desv_s2_i = _desviacion_s2(i)
        if desv_s2_i == 0:
            continue

        mejor_dia = None
        menor_desv = None
        for d_idx, peso_proy, edad_fin, _ in dias_eleg:
            if not _puede_asignarse_extras(i, d_idx):
                continue
            desv_s1 = _desviacion_s1_en_dia(i, d_idx)
            if desv_s1 >= desv_s2_i:
                continue
            score = (desv_s1, pollos_dia[d_idx])
            if menor_desv is None or score < menor_desv:
                menor_desv = score
                mejor_dia = d_idx
        if mejor_dia is not None:
            _asignar(i, mejor_dia)
            del no_asignados[i]

    # Paso B: intercambio (swap) — si el lote no cabe directamente,
    # intentar reemplazar un lote asignado en S1 que sufriría MENOS en S2.
    lotes_swap = sorted(
        [i for i in no_asignados if i in elegibilidad],
        key=_prioridad_dinamica_lote,
    )
    for i in lotes_swap:
        dias_eleg_i = elegibilidad[i]
        desv_s2_i = _desviacion_s2(i)
        if desv_s2_i == 0:
            continue

        mejor_swap = None     # (d_idx, j, beneficio_neto)
        mejor_beneficio = 0.0

        for d_idx, _, _, _ in dias_eleg_i:
            # Para cada lote j ya asignado al día d_idx
            for j in list(asignaciones[d_idx]):
                oferta_j = ofertas[j]
                # ¿Al quitar j y poner i, cabe en el día?
                pollos_despues = pollos_dia[d_idx] - oferta_j.cantidad + ofertas[i].cantidad
                if pollos_despues > _capacidad_dia_extras(d_idx):
                    continue

                desv_s1_i = _desviacion_s1_en_dia(i, d_idx)
                desv_s1_j = _desviacion_s1_en_dia(j, d_idx)
                desv_s2_j = _desviacion_s2(j)

                # Situación actual:  i→S2, j→S1(d_idx)  → costo = desv_s2_i + desv_s1_j
                # Con swap:          i→S1(d_idx), j→S2   → costo = desv_s1_i + desv_s2_j
                # (si j se reubica en otro día S1, su costo S2 se evita)
                costo_actual = desv_s2_i + desv_s1_j
                costo_swap = desv_s1_i + desv_s2_j
                beneficio = costo_actual - costo_swap

                if beneficio <= 0:
                    continue

                # Verificar si j puede reubicarse en otro día S1
                j_reubicable = False
                for dd, _, _, _ in elegibilidad.get(j, []):
                    if dd == d_idx:
                        continue
                    pollos_dd = pollos_dia[dd] + oferta_j.cantidad
                    if pollos_dd <= _capacidad_dia_extras(dd):
                        j_reubicable = True
                        break

                # Ponderar: si j es reubicable en S1, beneficio total es mayor
                # porque j no va a S2 (no paga desv_s2_j).
                beneficio_real = beneficio
                if j_reubicable:
                    beneficio_real = desv_s2_i - desv_s1_i  # j no pierde nada

                if beneficio_real > mejor_beneficio:
                    mejor_beneficio = beneficio_real
                    mejor_swap = (d_idx, j, j_reubicable)

        if mejor_swap is not None:
            d_idx, j, j_reubicable = mejor_swap
            _desasignar(j, d_idx)
            _asignar(i, d_idx)
            del no_asignados[i]

            # Intentar reubicar j en otro día S1
            if j_reubicable:
                for dd, _, _, _ in elegibilidad.get(j, []):
                    if dd == d_idx:
                        continue
                    if pollos_dia[dd] + ofertas[j].cantidad <= _capacidad_dia_extras(dd):
                        _asignar(j, dd)
                        break
            # Si j no pudo reubicarse, pasa a no_asignados (irá a S2)
            if j not in asignados:
                no_asignados[j] = (
                    "Desplazado por lote con mayor urgencia S2"
                )

    # ── Construir DiaFaena con lotes proyectados ────────────────────────────
    dias_resultado: List[DiaFaena] = []

    for d_idx, fecha_dia in enumerate(fechas_dias):
        lotes_dia: List[LoteProyectado] = []

        lotes_indices = asignaciones[d_idx]
        lotes_con_peso = []
        for i in lotes_indices:
            peso_dia = 0.0
            sobreedad_en_dia = False
            for d, p, e, s in elegibilidad[i]:
                if d == d_idx:
                    peso_dia = p
                    sobreedad_en_dia = s
                    break
            lotes_con_peso.append((i, peso_dia, sobreedad_en_dia))

        lotes_con_peso.sort(key=lambda x: -x[1])

        for i, _, es_sobreedad in lotes_con_peso:
            lote = calcular_lote_proyectado(ofertas[i], fecha_dia, params)
            lote.sobreedad = es_sobreedad
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
        dias = [fechas_dias[d] for d, _, _, _ in elegibilidad.get(i, [])]
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

    # Construir lista de feriados aplicados (saltados) — solo dentro de la semana
    feriados_aplicados_lista: List[FeriadoAplicado] = []
    if feriados:
        for f_fecha, f_nombre in sorted(feriados.items()):
            if fecha_inicio_semana <= f_fecha <= fecha_limite and f_fecha not in fechas_dias:
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

    for oferta in nuevos:
        dias_elegibles, detalle_rechazo = _evaluar_dias_elegibles_para_asignacion(oferta, dias, params)

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

        mejor_dia = _elegir_mejor_dia_para_asignacion(oferta, dias, dias_elegibles, params)

        if mejor_dia is not None:
            _asignar_oferta_en_dia(oferta, mejor_dia, dias, params)
            dia_nombre = DIAS_SEMANA[mejor_dia] if mejor_dia < len(DIAS_SEMANA) else str(mejor_dia)
            detalle_asignados.append({
                "granja": oferta.granja,
                "galpon": oferta.galpon,
                "nucleo": oferta.nucleo,
                "cantidad": oferta.cantidad,
                "dia": dia_nombre,
            })
        else:
            dias_eleg_fechas = [dias[d].fecha for d, _, _s in dias_elegibles]
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


def _capacidad_disponible_dia(dia: DiaFaena, params: Parametros) -> int:
    es_sab = dia.fecha.weekday() == 5
    cap = params.limite_sabado if es_sab else params.capacidad_con_horas_extras
    return max(0, cap - dia.gallinas_cantidad)


def _evaluar_dias_elegibles_para_asignacion(
    oferta: LoteOferta,
    dias: List[DiaFaena],
    params: Parametros,
) -> tuple[list[tuple[int, float, int]], list[dict]]:
    dias_elegibles = []
    detalle_rechazo = []

    for d_idx, dia in enumerate(dias):
        resultado = evaluar_elegibilidad_lote(oferta, dia.fecha, params)
        if resultado:
            peso_proy, edad_fin, _sobreedad = resultado
            dias_elegibles.append((d_idx, peso_proy, edad_fin))
        else:
            detalle_rechazo.append(_detalle_rechazo_dia(oferta, dia.fecha, params))

    return dias_elegibles, detalle_rechazo


def _elegir_mejor_dia_para_asignacion(
    oferta: LoteOferta,
    dias: List[DiaFaena],
    dias_elegibles: list[tuple[int, float, int]],
    params: Parametros,
) -> Optional[int]:
    mejor_dia = None
    mayor_deficit = -1

    for d_idx, _peso_proy, _edad_fin in dias_elegibles:
        pollos_actuales = dias[d_idx].total_pollos
        cap = _capacidad_disponible_dia(dias[d_idx], params)
        if pollos_actuales + oferta.cantidad > cap:
            continue
        es_sab = dias[d_idx].fecha.weekday() == 5
        obj_pref = params.limite_sabado if es_sab else params.pollos_diarios_objetivo_min
        deficit = obj_pref - pollos_actuales
        if deficit > mayor_deficit:
            mayor_deficit = deficit
            mejor_dia = d_idx

    if mejor_dia is not None:
        return mejor_dia

    mejor_pollos = float("inf")
    for d_idx, _peso_proy, _edad_fin in dias_elegibles:
        pollos_actuales = dias[d_idx].total_pollos
        cap = _capacidad_disponible_dia(dias[d_idx], params)
        if pollos_actuales + oferta.cantidad <= cap and pollos_actuales < mejor_pollos:
            mejor_pollos = pollos_actuales
            mejor_dia = d_idx

    return mejor_dia


def _asignar_oferta_en_dia(
    oferta: LoteOferta,
    dia_idx: int,
    dias: List[DiaFaena],
    params: Parametros,
) -> None:
    lote = calcular_lote_proyectado(oferta, dias[dia_idx].fecha, params)
    dias[dia_idx].lotes.append(lote)
    dias[dia_idx] = calcular_dia_faena(
        dias[dia_idx].fecha,
        dias[dia_idx].lotes,
        params=params,
        gallinas_cantidad=dias[dia_idx].gallinas_cantidad,
        gallinas_livianas=dias[dia_idx].gallinas_livianas_cantidad,
        gallinas_pesadas=dias[dia_idx].gallinas_pesadas_cantidad,
    )


def _reinsertar_lotes_no_asignados_actualizados(
    candidatos: list[dict],
    dias: List[DiaFaena],
    params: Parametros,
) -> tuple[list[DiaFaena], set[int], list[dict]]:
    detalle_reinsertados = []
    indices_reinsertados: set[int] = set()

    DIAS_SEMANA = ['Lunes', 'Martes', 'Miércoles', 'Jueves', 'Viernes', 'Sábado']

    for candidato in candidatos:
        oferta = candidato["oferta"]
        dias_elegibles, _detalle_rechazo = _evaluar_dias_elegibles_para_asignacion(oferta, dias, params)
        if not dias_elegibles:
            continue

        mejor_dia = _elegir_mejor_dia_para_asignacion(oferta, dias, dias_elegibles, params)
        if mejor_dia is None:
            continue

        _asignar_oferta_en_dia(oferta, mejor_dia, dias, params)
        indices_reinsertados.add(candidato["index"])
        detalle_reinsertados.append({
            "granja": oferta.granja,
            "galpon": oferta.galpon,
            "nucleo": oferta.nucleo,
            "cantidad": oferta.cantidad,
            "dia": DIAS_SEMANA[mejor_dia] if mejor_dia < len(DIAS_SEMANA) else str(mejor_dia),
        })

    return dias, indices_reinsertados, detalle_reinsertados


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

    # Fecha de referencia: hoy, para reflejar la edad real actual de los lotes.
    # Antes usaba la fecha de la oferta, lo que congelaba las edades al momento
    # de la carga y no reflejaba el paso del tiempo.
    if fecha_referencia is None:
        fecha_referencia = date.today()

    lotes_resultado = []
    alertas_rojas = 0
    alertas_amarillas = 0
    lotes_ok = 0
    granjas_stats: dict[str, dict] = {}
    galpones_nucleos_stats: dict[tuple[str, int, int], dict] = {}

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
        # Usar peso_muestreo_real y edad_real como ancla (dato medido real)
        # para mayor transparencia y robustez frente a posibles diferencias
        # entre el peso proyectado y el real + días × gdp.
        fecha_faena_ideal = fecha_referencia + timedelta(days=max(dias_restantes, 0))
        edad_fin_ideal = calcular_edad_fin_retiro_v2(
            fecha_faena_ideal, oferta.fecha_peso, oferta.edad_proyectada,
            dias_proyectados=oferta.dias_proyectados,
        )
        peso_en_ideal = peso_vivo_retiro(
            oferta.sexo, edad_fin_ideal, oferta.edad_real,
            oferta.peso_muestreo_real, params,
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
            oferta.sexo, edad_fin_min, oferta.edad_real,
            oferta.peso_muestreo_real, params,
            ganancia_diaria_lote=oferta.ganancia_diaria,
        )

        fecha_faena_max = fecha_referencia + timedelta(days=max(dias_a_max, 0))
        edad_fin_max = calcular_edad_fin_retiro_v2(
            fecha_faena_max, oferta.fecha_peso, oferta.edad_proyectada,
            dias_proyectados=oferta.dias_proyectados,
        )
        peso_en_max = peso_vivo_retiro(
            oferta.sexo, edad_fin_max, oferta.edad_real,
            oferta.peso_muestreo_real, params,
            ganancia_diaria_lote=oferta.ganancia_diaria,
        )

        # --- Ganancia mínima necesaria DESDE HOY para alcanzar peso_min_faena a edad ideal ---
        medio_dia = params.ganancia_diaria_macho * 0.5
        if oferta.sexo.upper() != "H":
            factor_desc = 1 - params.descuento_sin_sexar
            peso_target = params.peso_min_faena / factor_desc
        else:
            peso_target = params.peso_min_faena

        # Peso estimado de crecimiento hoy (sin descuento de faena)
        # Anclar sobre peso_muestreo_real para usar dato medido
        dias_transcurridos = edad_actual - oferta.edad_real
        peso_estimado_hoy = oferta.peso_muestreo_real + dias_transcurridos * ganancia_lote

        # Días efectivos de crecimiento restantes (último día solo medio_dia)
        dias_efectivos_restantes = max(dias_restantes - 1, 0)
        if dias_efectivos_restantes > 0:
            ganancia_necesaria = (peso_target - peso_estimado_hoy - medio_dia) / dias_efectivos_restantes
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

        gn_key = (oferta.granja, oferta.galpon, oferta.nucleo)
        if gn_key not in galpones_nucleos_stats:
            galpones_nucleos_stats[gn_key] = {
                "total": 0,
                "verde": 0,
                "amarillo": 0,
                "rojo": 0,
                "pollos_total": 0,
                "pollos_alerta": 0,
                "pollos_rojo": 0,
                "suma_peso_ideal": 0.0,
            }
        gn = galpones_nucleos_stats[gn_key]
        gn["total"] += 1
        gn[nivel] += 1
        gn["pollos_total"] += oferta.cantidad
        gn["suma_peso_ideal"] += peso_en_ideal * oferta.cantidad
        if nivel in ("amarillo", "rojo"):
            gn["pollos_alerta"] += oferta.cantidad
        if nivel == "rojo":
            gn["pollos_rojo"] += oferta.cantidad

        lotes_resultado.append({
            "granja": oferta.granja,
            "galpon": oferta.galpon,
            "nucleo": oferta.nucleo,
            "cantidad": oferta.cantidad,
            "sexo": oferta.sexo,
            "edad_actual": edad_actual,
            "edad_ideal": edad_ideal,
            "dias_restantes": max(dias_restantes, 0),
            "peso_actual": oferta.peso_muestreo_real,
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

    galpones_nucleos_resumen = []
    for (granja, galpon, nucleo), stats in galpones_nucleos_stats.items():
        peso_prom = (
            stats["suma_peso_ideal"] / stats["pollos_total"]
            if stats["pollos_total"] > 0 else 0
        )
        if stats["rojo"] > 0:
            nivel_gn = "rojo"
        elif stats["amarillo"] > 0:
            nivel_gn = "amarillo"
        else:
            nivel_gn = "verde"

        pollos_total = stats["pollos_total"]
        pct_alerta = round(stats["pollos_alerta"] / pollos_total * 100, 1) if pollos_total > 0 else 0
        pct_rojo = round(stats["pollos_rojo"] / pollos_total * 100, 1) if pollos_total > 0 else 0

        galpones_nucleos_resumen.append({
            "granja": granja,
            "galpon": galpon,
            "nucleo": nucleo,
            "total_lotes": stats["total"],
            "lotes_verde": stats["verde"],
            "lotes_amarillo": stats["amarillo"],
            "lotes_rojo": stats["rojo"],
            "pollos_total": pollos_total,
            "pollos_alerta": stats["pollos_alerta"],
            "pollos_rojo": stats["pollos_rojo"],
            "pct_pollos_alerta": pct_alerta,
            "pct_pollos_rojo": pct_rojo,
            "peso_promedio_ideal": round(peso_prom, 3),
            "nivel": nivel_gn,
        })

    galpones_nucleos_resumen.sort(
        key=lambda item: (
            {"rojo": 0, "amarillo": 1, "verde": 2}.get(item["nivel"], 3),
            -item["pct_pollos_rojo"],
            -item["pct_pollos_alerta"],
            -item["pollos_total"],
            item["granja"],
            item["galpon"],
            item["nucleo"],
        )
    )

    total_lotes = len(lotes_resultado)

    # Metadata de antigüedad: fecha efectiva de la oferta y días desde entonces
    fecha_oferta = ofertas[0].fecha_peso + timedelta(days=ofertas[0].dias_proyectados)
    dias_antiguedad = (fecha_referencia - fecha_oferta).days

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
        "fecha_referencia": fecha_referencia.isoformat(),
        "fecha_oferta": fecha_oferta.isoformat(),
        "dias_antiguedad": dias_antiguedad,
        "lotes": lotes_resultado,
        "granjas": granjas_resumen,
        "galpones_nucleos": galpones_nucleos_resumen,
    }


# ─── Validación cruzada: oferta vs producción ─────────────────────────────────

def validar_mortalidad_oferta(
    ofertas: List[LoteOferta],
    semanas_produccion: list[dict],
    dias_hasta_faena: int = DIAS_HASTA_FAENA_REFERENCIA,
    tolerancia_dias: int = TOLERANCIA_FECHA_CRUCE_DIAS,
    merma_min: float = MERMA_REFERENCIA_MIN,
    merma_max: float = MERMA_REFERENCIA_MAX,
) -> dict:
    """
    Cruza la oferta detallada por granja contra las cargas semanales de
    pollitos BB para estimar cuántas aves se esperan recibir en faena por
    cohorte.

    El archivo de producción es agregado por semana y no detalla granjas,
    mientras que la oferta sí viene desagregada por lote. Por eso el cruce no
    debe inferir mortalidad observada a partir de la diferencia simple entre
    ambos reportes. En cambio, reporta:

    - ventana esperada de faena para la cohorte según la referencia configurada
    - rango esperado de aves en faena aplicando la merma de referencia vigente
    - aves presentes en la oferta actual
    - si la fecha objetivo de la oferta está alineada o desfasada respecto a
      la ventana esperada

    Args:
        ofertas: Lista de lotes de la oferta cargada.
        semanas_produccion: Lista de dicts con fecha_desde, fecha_hasta, pollitos_cargados.

    Returns:
        dict con cohortes analizadas y alertas.
    """
    if not ofertas or not semanas_produccion:
        return {"cohortes": [], "tiene_produccion": bool(semanas_produccion)}

    # Indexar semanas de producción por rango de fechas
    semanas = []
    for s in semanas_produccion:
        desde = s["fecha_desde"]
        hasta = s["fecha_hasta"]
        if isinstance(desde, str):
            desde = date.fromisoformat(desde)
        if isinstance(hasta, str):
            hasta = date.fromisoformat(hasta)
        semanas.append({
            "fecha_desde": desde,
            "fecha_hasta": hasta,
            "pollitos_cargados": s["pollitos_cargados"],
        })

    def buscar_semana(fecha_ingreso: date):
        """Busca la semana de producción que contiene la fecha de ingreso."""
        for sem in semanas:
            if sem["fecha_desde"] <= fecha_ingreso <= sem["fecha_hasta"]:
                return sem
        # Tolerancia configurable: buscar ±N días si no hay match exacto
        for sem in semanas:
            if abs((fecha_ingreso - sem["fecha_desde"]).days) <= tolerancia_dias:
                return sem
            if abs((fecha_ingreso - sem["fecha_hasta"]).days) <= tolerancia_dias:
                return sem
        return None

    # Agrupar lotes por semana de producción (cohorte)
    cohortes_map: dict[str, dict] = {}

    for oferta in ofertas:
        if not oferta.fecha_ingreso:
            continue

        sem = buscar_semana(oferta.fecha_ingreso)
        if sem is None:
            continue

        key = sem["fecha_desde"].isoformat()
        if key not in cohortes_map:
            cohortes_map[key] = {
                "fecha_desde": sem["fecha_desde"].isoformat(),
                "fecha_hasta": sem["fecha_hasta"].isoformat(),
                "pollitos_cargados": sem["pollitos_cargados"],
                "aves_en_oferta": 0,
                "lotes": 0,
                "granjas": set(),
                "fecha_oferta_desde": None,
                "fecha_oferta_hasta": None,
                "fecha_objetivo_desde": None,
                "fecha_objetivo_hasta": None,
            }
        c = cohortes_map[key]
        fecha_objetivo = oferta.fecha_peso + timedelta(days=max(oferta.dias_proyectados, 0))
        c["aves_en_oferta"] += oferta.cantidad
        c["lotes"] += 1
        c["granjas"].add(oferta.granja)
        c["fecha_oferta_desde"] = min(
            [d for d in (c["fecha_oferta_desde"], oferta.fecha_peso) if d is not None]
        )
        c["fecha_oferta_hasta"] = max(
            [d for d in (c["fecha_oferta_hasta"], oferta.fecha_peso) if d is not None]
        )
        c["fecha_objetivo_desde"] = min(
            [d for d in (c["fecha_objetivo_desde"], fecha_objetivo) if d is not None]
        )
        c["fecha_objetivo_hasta"] = max(
            [d for d in (c["fecha_objetivo_hasta"], fecha_objetivo) if d is not None]
        )

    # Calcular expectativa de recepción en faena por cohorte
    cohortes = []
    for key in sorted(cohortes_map.keys()):
        c = cohortes_map[key]
        cargados = c["pollitos_cargados"]
        en_oferta = c["aves_en_oferta"]

        fecha_desde = date.fromisoformat(c["fecha_desde"])
        fecha_hasta = date.fromisoformat(c["fecha_hasta"])
        faena_esperada_desde = fecha_desde + timedelta(days=dias_hasta_faena)
        # Si cae sábado o domingo, mover al lunes siguiente
        if faena_esperada_desde.weekday() == 5:
            faena_esperada_desde += timedelta(days=2)
        elif faena_esperada_desde.weekday() == 6:
            faena_esperada_desde += timedelta(days=1)
        faena_esperada_hasta = fecha_hasta + timedelta(days=dias_hasta_faena)
        if faena_esperada_hasta.weekday() == 5:
            faena_esperada_hasta += timedelta(days=2)
        elif faena_esperada_hasta.weekday() == 6:
            faena_esperada_hasta += timedelta(days=1)

        if cargados > 0:
            esperados_faena_max = int(cargados * (1 - merma_min))
            esperados_faena_min = int(cargados * (1 - merma_max))
            cobertura_pct_cargados = round(en_oferta / cargados * 100, 1)
            cobertura_pct_min = round(en_oferta / esperados_faena_min * 100, 1) if esperados_faena_min > 0 else None
            cobertura_pct_max = round(en_oferta / esperados_faena_max * 100, 1) if esperados_faena_max > 0 else None
        else:
            esperados_faena_max = 0
            esperados_faena_min = 0
            cobertura_pct_cargados = 0.0
            cobertura_pct_min = None
            cobertura_pct_max = None

        objetivo_desde = c["fecha_objetivo_desde"]
        objetivo_hasta = c["fecha_objetivo_hasta"]
        if objetivo_desde is None or objetivo_hasta is None:
            estado_fecha = "sin_dato"
            desfase_dias = None
        elif objetivo_hasta < faena_esperada_desde - timedelta(days=tolerancia_dias):
            estado_fecha = "anticipada"
            desfase_dias = (objetivo_hasta - faena_esperada_desde).days
        elif objetivo_desde > faena_esperada_hasta + timedelta(days=tolerancia_dias):
            estado_fecha = "atrasada"
            desfase_dias = (objetivo_desde - faena_esperada_hasta).days
        elif (
            objetivo_desde >= faena_esperada_desde - timedelta(days=tolerancia_dias)
            and objetivo_hasta <= faena_esperada_hasta + timedelta(days=tolerancia_dias)
        ):
            estado_fecha = "alineada"
            desfase_dias = 0
        else:
            estado_fecha = "mixta"
            desfase_dias = 0

        if esperados_faena_min <= 0:
            estado_cantidad = "sin_dato"
        elif en_oferta > (esperados_faena_max + max(500, int(esperados_faena_max * 0.03))):
            estado_cantidad = "por_encima"
        elif en_oferta < esperados_faena_min:
            estado_cantidad = "parcial"
        else:
            estado_cantidad = "en_rango"

        if estado_fecha in ("anticipada", "atrasada"):
            nivel = estado_fecha
        elif estado_cantidad == "por_encima":
            nivel = "excedida"
        elif estado_fecha == "mixta":
            nivel = "mixta"
        elif estado_cantidad == "parcial":
            nivel = "parcial"
        elif estado_fecha == "sin_dato":
            nivel = "sin_dato"
        else:
            nivel = "alineada"

        if nivel == "anticipada":
            motivo = "La fecha objetivo de la oferta cae antes de la ventana estimada de faena (+42 días) para esta cohorte."
        elif nivel == "atrasada":
            motivo = "La fecha objetivo de la oferta cae después de la ventana estimada de faena (+42 días) para esta cohorte."
        elif nivel == "excedida":
            motivo = "La oferta supera el rango esperado de aves en faena para esta cohorte. Conviene revisar fechas o duplicidades."
        elif nivel == "mixta":
            motivo = "La cohorte mezcla lotes con fechas objetivo dentro y fuera de la ventana esperada."
        elif nivel == "parcial":
            motivo = "La oferta actual cubre solo una parte de lo esperado para la cohorte. Esto puede ser normal porque producción es semanal y la oferta viene por granja/lote."
        elif nivel == "alineada":
            motivo = "La cantidad ofertada y la ventana temporal son coherentes con lo esperado para la cohorte."
        else:
            motivo = "No hay datos suficientes para evaluar la cohorte."

        cohortes.append({
            "fecha_desde": c["fecha_desde"],
            "fecha_hasta": c["fecha_hasta"],
            "fecha_faena_esperada_desde": faena_esperada_desde.isoformat(),
            "fecha_faena_esperada_hasta": faena_esperada_hasta.isoformat(),
            "fecha_oferta_desde": c["fecha_oferta_desde"].isoformat() if c["fecha_oferta_desde"] else None,
            "fecha_oferta_hasta": c["fecha_oferta_hasta"].isoformat() if c["fecha_oferta_hasta"] else None,
            "fecha_objetivo_desde": objetivo_desde.isoformat() if objetivo_desde else None,
            "fecha_objetivo_hasta": objetivo_hasta.isoformat() if objetivo_hasta else None,
            "pollitos_cargados": cargados,
            "esperados_faena_min": esperados_faena_min,
            "esperados_faena_max": esperados_faena_max,
            "aves_en_oferta": en_oferta,
            "diferencia": en_oferta - esperados_faena_min,
            "diferencia_vs_min": en_oferta - esperados_faena_min,
            "diferencia_vs_max": en_oferta - esperados_faena_max,
            "cobertura_pct": cobertura_pct_cargados,
            "cobertura_pct_min": cobertura_pct_min,
            "cobertura_pct_max": cobertura_pct_max,
            "estado_fecha": estado_fecha,
            "estado_cantidad": estado_cantidad,
            "desfase_dias": desfase_dias,
            "nivel": nivel,
            "motivo": motivo,
            "lotes": c["lotes"],
            "granjas": sorted(c["granjas"]),
        })

    return {
        "tiene_produccion": True,
        "cohortes": cohortes,
        "total_cohortes": len(cohortes),
        "alertas": sum(1 for c in cohortes if c["nivel"] in ("anticipada", "atrasada", "excedida", "mixta")),
    }


# ─── Sugerencias inteligentes de diferimiento ──────────────────────────────────

def generar_sugerencias_diferimiento(
    semana: SemanaFaena,
    ofertas: List[LoteOferta],
    params: Optional[Parametros] = None,
    feriados: Optional[dict] = None,
) -> dict:
    """
    Analiza la proyección actual y genera sugerencias de lotes candidatos
    a diferir a Semana 2, priorizadas por criterio.

    Criterios evaluados (en orden de prioridad):
    1. Sobrecarga de día: lotes en días que superan objetivo_max con más
       flexibilidad de días elegibles (pueden ir a otros días o a S2).
    2. Mejor calibre en S2: lotes cerca del peso mínimo que pesarían más
       en S2 (7 días extra de ganancia).
    3. Feriado cercano: días adyacentes a feriados que quedan sobrecargados.
    4. Edad temprana: lotes en edad mínima que estarían más cerca de la
       edad ideal si se faenaran en S2.

    Returns:
        dict con sugerencias priorizadas y resumen.
    """
    if params is None:
        params = Parametros()

    if not semana.dias:
        return {"total_sugerencias": 0, "sugerencias": []}

    sugerencias = []

    # Indexar ofertas por (granja, galpon, nucleo, sexo, fecha_ingreso)
    ofertas_index: dict[tuple, LoteOferta] = {}
    for o in ofertas:
        key = (o.granja, o.galpon, o.nucleo, o.sexo,
               o.fecha_ingreso.isoformat() if o.fecha_ingreso else "")
        ofertas_index[key] = o

    # Fecha inicio hipotética de S2
    fecha_inicio_s2 = semana.fecha_inicio + timedelta(days=7)

    # Pre-calcular elegibilidad de cada lote para cada día (para medir flexibilidad)
    lote_dias_elegibles: dict[str, int] = {}  # "diaIdx-loteIdx" → cantidad de días elegibles
    for dia_idx, dia in enumerate(semana.dias):
        for lote_idx, lote in enumerate(dia.lotes):
            key_oferta = (lote.granja, lote.galpon, lote.nucleo, lote.sexo,
                          lote.fecha_ingreso_original.isoformat() if lote.fecha_ingreso_original else "")
            oferta = ofertas_index.get(key_oferta)
            if not oferta:
                continue
            n_elegibles = 0
            for d in semana.dias:
                result = evaluar_elegibilidad_lote(oferta, d.fecha, params)
                if result:
                    n_elegibles += 1
            lote_dias_elegibles[f"{dia_idx}-{lote_idx}"] = n_elegibles

    # IDs ya sugeridos (evitar duplicados entre criterios)
    sugeridos_set: set[str] = set()

    def _lote_id(dia_idx: int, lote_idx: int, lote: LoteProyectado) -> str:
        return f"{dia_idx}-{lote_idx}-{lote.granja}-{lote.galpon}-{lote.nucleo}"

    def _peso_en_s2(lote: LoteProyectado) -> Optional[float]:
        """Calcula peso proyectado si se faenara al inicio de S2 (lunes S2)."""
        key_oferta = (lote.granja, lote.galpon, lote.nucleo, lote.sexo,
                      lote.fecha_ingreso_original.isoformat() if lote.fecha_ingreso_original else "")
        oferta = ofertas_index.get(key_oferta)
        if not oferta:
            return None
        # Evaluar para el miércoles de S2 (día típico medio)
        fecha_media_s2 = fecha_inicio_s2 + timedelta(days=2)
        result = evaluar_elegibilidad_lote(oferta, fecha_media_s2, params)
        if result:
            return result[0]  # peso_proy
        return None

    def _edad_en_s2(lote: LoteProyectado) -> Optional[int]:
        """Calcula edad si se faenara al inicio de S2."""
        key_oferta = (lote.granja, lote.galpon, lote.nucleo, lote.sexo,
                      lote.fecha_ingreso_original.isoformat() if lote.fecha_ingreso_original else "")
        oferta = ofertas_index.get(key_oferta)
        if not oferta:
            return None
        fecha_media_s2 = fecha_inicio_s2 + timedelta(days=2)
        return calcular_edad_fin_retiro_v2(
            fecha_media_s2, oferta.fecha_peso, oferta.edad_proyectada,
            dias_proyectados=oferta.dias_proyectados,
        )

    DIAS_SEMANA_NOMBRES = ['Lunes', 'Martes', 'Miércoles', 'Jueves', 'Viernes', 'Sábado']

    def _dia_nombre(dia_idx: int) -> str:
        if dia_idx < len(semana.dias):
            wd = semana.dias[dia_idx].fecha.weekday()
            return DIAS_SEMANA_NOMBRES[wd] if wd < len(DIAS_SEMANA_NOMBRES) else str(dia_idx)
        return str(dia_idx)

    # ── Criterio 1: Sobrecarga de día ───────────────────────────────────────
    for dia_idx, dia in enumerate(semana.dias):
        es_sabado = dia.fecha.weekday() == 5
        objetivo = params.limite_sabado if es_sabado else params.pollos_diarios_objetivo_max
        exceso = dia.total_pollos - objetivo
        if exceso <= 0:
            continue

        # Buscar lotes con más flexibilidad (más días elegibles) para mover
        candidatos = []
        for lote_idx, lote in enumerate(dia.lotes):
            if lote.es_compra_terceros:
                continue
            lid = _lote_id(dia_idx, lote_idx, lote)
            if lid in sugeridos_set:
                continue
            n_eleg = lote_dias_elegibles.get(f"{dia_idx}-{lote_idx}", 0)
            # Solo sugerir lotes con flexibilidad (>1 día elegible)
            if n_eleg > 1:
                candidatos.append((lote_idx, lote, n_eleg))

        # Ordenar: más flexibles primero, luego los más pequeños (menor impacto)
        candidatos.sort(key=lambda x: (-x[2], x[1].cantidad))

        # Sugerir los necesarios para bajar del objetivo
        pollos_a_mover = exceso
        for lote_idx, lote, n_eleg in candidatos:
            if pollos_a_mover <= 0:
                break
            lid = _lote_id(dia_idx, lote_idx, lote)
            peso_s2 = _peso_en_s2(lote)
            sugerencias.append({
                "dia_index": dia_idx,
                "lote_index": lote_idx,
                "granja": lote.granja,
                "galpon": lote.galpon,
                "nucleo": lote.nucleo,
                "cantidad": lote.cantidad,
                "sexo": lote.sexo,
                "criterio": "sobrecarga",
                "prioridad": 1,
                "dia_nombre": _dia_nombre(dia_idx),
                "motivo": (
                    f"{_dia_nombre(dia_idx)} tiene {dia.total_pollos:,} pollos "
                    f"(excede objetivo de {objetivo:,} en {exceso:,}). "
                    f"Este lote tiene {n_eleg} días elegibles → flexible para diferir."
                ),
                "impacto": {
                    "pollos_removidos": lote.cantidad,
                    "dia_post_diferir": dia.total_pollos - lote.cantidad,
                    "peso_actual": round(lote.peso_vivo_retiro, 3),
                    "peso_estimado_s2": round(peso_s2, 3) if peso_s2 else None,
                },
            })
            sugeridos_set.add(lid)
            pollos_a_mover -= lote.cantidad

    # ── Criterio 2: Mejor calibre en S2 ────────────────────────────────────
    MARGEN_PESO_MINIMO = 0.08  # kg - lotes a menos de 80g del mínimo
    for dia_idx, dia in enumerate(semana.dias):
        for lote_idx, lote in enumerate(dia.lotes):
            if lote.es_compra_terceros:
                continue
            lid = _lote_id(dia_idx, lote_idx, lote)
            if lid in sugeridos_set:
                continue
            # Lotes cerca del peso mínimo
            margen = lote.peso_vivo_retiro - params.peso_min_faena
            if margen > MARGEN_PESO_MINIMO or margen < 0:
                continue
            peso_s2 = _peso_en_s2(lote)
            if peso_s2 is None:
                continue
            mejora = peso_s2 - lote.peso_vivo_retiro
            # Solo sugerir si mejora significativamente (>50g)
            if mejora < 0.05:
                continue
            # Verificar que en S2 esté dentro del rango
            if peso_s2 > params.peso_max_faena:
                continue
            sugerencias.append({
                "dia_index": dia_idx,
                "lote_index": lote_idx,
                "granja": lote.granja,
                "galpon": lote.galpon,
                "nucleo": lote.nucleo,
                "cantidad": lote.cantidad,
                "sexo": lote.sexo,
                "criterio": "mejor_calibre",
                "prioridad": 2,
                "dia_nombre": _dia_nombre(dia_idx),
                "motivo": (
                    f"Peso actual {lote.peso_vivo_retiro:.3f} kg "
                    f"(solo {margen*1000:.0f}g sobre el mínimo de {params.peso_min_faena:.2f}). "
                    f"En S2 pesaría ~{peso_s2:.3f} kg (+{mejora*1000:.0f}g) → mejor calibre."
                ),
                "impacto": {
                    "pollos_removidos": lote.cantidad,
                    "dia_post_diferir": dia.total_pollos - lote.cantidad,
                    "peso_actual": round(lote.peso_vivo_retiro, 3),
                    "peso_estimado_s2": round(peso_s2, 3),
                    "mejora_peso_g": round(mejora * 1000),
                },
            })
            sugeridos_set.add(lid)

    # ── Criterio 3: Feriado cercano ─────────────────────────────────────────
    if feriados:
        for dia_idx, dia in enumerate(semana.dias):
            # Ver si este día está adyacente a un feriado
            fecha = dia.fecha
            adyacente_feriado = False
            feriado_nombre = ""
            for f_fecha, f_nombre in feriados.items():
                diff = abs((fecha - f_fecha).days)
                if diff <= 1 and f_fecha != fecha:
                    adyacente_feriado = True
                    feriado_nombre = f_nombre
                    break

            if not adyacente_feriado:
                continue

            es_sabado = dia.fecha.weekday() == 5
            objetivo = params.limite_sabado if es_sabado else params.pollos_diarios_objetivo_max
            # Solo sugerir si el día está al menos al 90% del objetivo
            if dia.total_pollos < objetivo * 0.9:
                continue

            for lote_idx, lote in enumerate(dia.lotes):
                if lote.es_compra_terceros:
                    continue
                lid = _lote_id(dia_idx, lote_idx, lote)
                if lid in sugeridos_set:
                    continue
                n_eleg = lote_dias_elegibles.get(f"{dia_idx}-{lote_idx}", 0)
                if n_eleg <= 1:
                    continue
                peso_s2 = _peso_en_s2(lote)
                sugerencias.append({
                    "dia_index": dia_idx,
                    "lote_index": lote_idx,
                    "granja": lote.granja,
                    "galpon": lote.galpon,
                    "nucleo": lote.nucleo,
                    "cantidad": lote.cantidad,
                    "sexo": lote.sexo,
                    "criterio": "feriado",
                    "prioridad": 3,
                    "dia_nombre": _dia_nombre(dia_idx),
                    "motivo": (
                        f"{_dia_nombre(dia_idx)} adyacente a feriado ({feriado_nombre}). "
                        f"Día con {dia.total_pollos:,} pollos ({dia.total_pollos*100//objetivo}% del objetivo). "
                        f"Diferir alivia carga del día."
                    ),
                    "impacto": {
                        "pollos_removidos": lote.cantidad,
                        "dia_post_diferir": dia.total_pollos - lote.cantidad,
                        "peso_actual": round(lote.peso_vivo_retiro, 3),
                        "peso_estimado_s2": round(peso_s2, 3) if peso_s2 else None,
                    },
                })
                sugeridos_set.add(lid)
                break  # Solo 1 sugerencia por día feriado

    # ── Criterio 4: Edad temprana ───────────────────────────────────────────
    for dia_idx, dia in enumerate(semana.dias):
        for lote_idx, lote in enumerate(dia.lotes):
            if lote.es_compra_terceros:
                continue
            lid = _lote_id(dia_idx, lote_idx, lote)
            if lid in sugeridos_set:
                continue
            # Solo lotes en edad mínima de faena
            if lote.edad_fin_retiro > params.edad_min_faena:
                continue
            # Calcular edad ideal según sexo
            if lote.sexo.upper() == "M":
                edad_ideal = params.edad_ideal_macho
            elif lote.sexo.upper() == "H":
                edad_ideal = params.edad_ideal_hembra
            else:
                edad_ideal = params.edad_ideal_sin_sexar
            dif_actual = abs(lote.edad_fin_retiro - edad_ideal)
            edad_s2 = _edad_en_s2(lote)
            if edad_s2 is None or edad_s2 > params.edad_max_faena:
                continue
            dif_s2 = abs(edad_s2 - edad_ideal)
            # Solo sugerir si S2 mejora la diferencia a la edad ideal
            if dif_s2 >= dif_actual:
                continue
            peso_s2 = _peso_en_s2(lote)
            if peso_s2 is not None and peso_s2 > params.peso_max_faena:
                continue
            sugerencias.append({
                "dia_index": dia_idx,
                "lote_index": lote_idx,
                "granja": lote.granja,
                "galpon": lote.galpon,
                "nucleo": lote.nucleo,
                "cantidad": lote.cantidad,
                "sexo": lote.sexo,
                "criterio": "edad_temprana",
                "prioridad": 4,
                "dia_nombre": _dia_nombre(dia_idx),
                "motivo": (
                    f"Edad actual {lote.edad_fin_retiro}d (mínima de faena). "
                    f"Ideal para {lote.sexo}: {edad_ideal}d. "
                    f"En S2 tendría ~{edad_s2}d → más cerca del ideal."
                ),
                "impacto": {
                    "pollos_removidos": lote.cantidad,
                    "dia_post_diferir": dia.total_pollos - lote.cantidad,
                    "peso_actual": round(lote.peso_vivo_retiro, 3),
                    "peso_estimado_s2": round(peso_s2, 3) if peso_s2 else None,
                    "edad_actual": lote.edad_fin_retiro,
                    "edad_estimada_s2": edad_s2,
                    "edad_ideal": edad_ideal,
                },
            })
            sugeridos_set.add(lid)

    # Ordenar por prioridad
    sugerencias.sort(key=lambda s: (s["prioridad"], -s["cantidad"]))

    # Contadores por criterio
    por_criterio = {}
    for s in sugerencias:
        c = s["criterio"]
        por_criterio[c] = por_criterio.get(c, 0) + 1

    return {
        "total_sugerencias": len(sugerencias),
        "sugerencias": sugerencias,
        "por_criterio": por_criterio,
        "total_pollos_sugeridos": sum(s["cantidad"] for s in sugerencias),
    }


# ─── Ajuste con oferta del martes ──────────────────────────────────────────────

def aplicar_ajuste_martes(
    ofertas_martes: List[LoteOferta],
    semana: SemanaFaena,
    params: Optional[Parametros] = None,
    ofertas_referencia: Optional[List[LoteOferta]] = None,
) -> tuple:
    """
    Aplica la oferta del martes a una proyección existente.

    Matchea lotes por (granja, galpon, nucleo, sexo, fecha_ingreso).
    La fecha_ingreso identifica de forma unívoca cada lote dentro de un
    mismo galpón/núcleo/sexo, ya que representa la fecha de ingreso de
    las aves a la granja (dato estático que no cambia entre ofertas).

    - Lotes matcheados: actualiza datos y recalcula en el MISMO día asignado.
    - Lotes nuevos (en martes pero no en proyección): van a lotes_no_asignados.
    - Si el ajuste libera capacidad, reintenta insertar backlog previo no asignado.
    - Lotes faltantes (en proyección pero no en martes): se marcan en el resumen.

    Retorna (SemanaFaena actualizada, AjusteMartesResumen).
    """
    if params is None:
        params = Parametros()

    def _clave_lote(granja: str, galpon: int, nucleo: int, sexo: str, fecha_ingreso: Optional[date]) -> tuple:
        return (
            normalizar_granja_clave(granja),
            galpon,
            nucleo,
            sexo,
            fecha_ingreso,
        )

    martes_index: dict[tuple, LoteOferta] = {}
    for oferta in ofertas_martes:
        key = _clave_lote(oferta.granja, oferta.galpon, oferta.nucleo, oferta.sexo, oferta.fecha_ingreso)
        existente = martes_index.get(key)
        if existente is None:
            martes_index[key] = oferta.model_copy(deep=True)
        else:
            existente.cantidad += oferta.cantidad

    martes_lookup = {
        key: oferta.model_copy(deep=True)
        for key, oferta in martes_index.items()
    }

    ofertas_referencia_index: dict[tuple, LoteOferta] = {}
    for oferta in ofertas_referencia or []:
        key = _clave_lote(oferta.granja, oferta.galpon, oferta.nucleo, oferta.sexo, oferta.fecha_ingreso)
        if key not in ofertas_referencia_index:
            ofertas_referencia_index[key] = oferta

    resumen = AjusteMartesResumen()

    DIAS_SEMANA = ['Lunes', 'Martes', 'Miércoles', 'Jueves', 'Viernes', 'Sábado']

    reemplazos_por_dia: dict[int, list[Optional[LoteProyectado]]] = {
        dia_idx: list(dia.lotes)
        for dia_idx, dia in enumerate(semana.dias)
    }

    lotes_planificados_por_clave: dict[tuple, list[dict]] = {}
    for dia_idx, dia in enumerate(semana.dias):
        for lote_idx, lote in enumerate(dia.lotes):
            key = _clave_lote(
                lote.granja,
                lote.galpon,
                lote.nucleo,
                lote.sexo,
                lote.fecha_ingreso_original,
            )
            lotes_planificados_por_clave.setdefault(key, []).append({
                "dia_idx": dia_idx,
                "lote_idx": lote_idx,
                "lote": lote,
            })

    lotes_no_asignados_originales = list(semana.lotes_no_asignados or [])
    lotes_no_asignados_actualizados: dict[int, Optional[LoteNoAsignado]] = {
        idx: lote.model_copy(deep=True)
        for idx, lote in enumerate(lotes_no_asignados_originales)
    }
    lotes_no_asignados_por_clave: dict[tuple, list[dict]] = {}
    for idx, lote in enumerate(lotes_no_asignados_originales):
        key = _clave_lote(lote.granja, lote.galpon, lote.nucleo, lote.sexo, lote.fecha_ingreso)
        lotes_no_asignados_por_clave.setdefault(key, []).append({
            "index": idx,
            "lote": lotes_no_asignados_actualizados[idx],
        })

    claves_existentes = set(lotes_planificados_por_clave) | set(lotes_no_asignados_por_clave)

    for key in claves_existentes:
        lotes_planificados = lotes_planificados_por_clave.get(key, [])
        lotes_no_asignados = lotes_no_asignados_por_clave.get(key, [])
        oferta_martes = martes_index.pop(key, None)

        if oferta_martes is None:
            if lotes_planificados:
                resumen.lotes_faltantes += 1
                primer_lote = lotes_planificados[0]["lote"]
                resumen.detalle_faltantes.append({
                    "granja": primer_lote.granja,
                    "galpon": primer_lote.galpon,
                    "nucleo": primer_lote.nucleo,
                    "cantidad": sum(item["lote"].cantidad for item in lotes_planificados),
                    "sexo": primer_lote.sexo,
                    "dia": DIAS_SEMANA[lotes_planificados[0]["dia_idx"]] if lotes_planificados else "",
                })
            continue

        cantidades_originales_planificadas = [item["lote"].cantidad for item in lotes_planificados]
        cantidades_originales_no_asignadas = [item["lote"].cantidad for item in lotes_no_asignados]
        total_planificado_original = sum(cantidades_originales_planificadas)
        total_no_asignado_original = sum(cantidades_originales_no_asignadas)
        total_original = total_planificado_original + total_no_asignado_original

        # El plan ya comprometido se ajusta por separado del backlog no asignado.
        # Si el martes baja la cantidad total, el remanente pendiente debe absorberse
        # primero sin recortar artificialmente lo que ya estaba calendarizado.
        cantidad_planificada_actualizada = 0
        if lotes_planificados:
            cantidad_planificada_actualizada = oferta_martes.cantidad
            if lotes_no_asignados:
                cantidad_planificada_actualizada = min(oferta_martes.cantidad, total_planificado_original)

        cantidad_no_asignada_actualizada = 0
        if lotes_no_asignados:
            if lotes_planificados:
                cantidad_no_asignada_actualizada = max(oferta_martes.cantidad - cantidad_planificada_actualizada, 0)
            else:
                cantidad_no_asignada_actualizada = oferta_martes.cantidad

        cantidades_planificadas = _particionar_cantidad(
            cantidad_planificada_actualizada,
            cantidades_originales_planificadas,
        )
        cantidades_no_asignadas = _particionar_cantidad(
            cantidad_no_asignada_actualizada,
            cantidades_originales_no_asignadas,
        )
        fragmentos_actualizados = [
            cantidad
            for cantidad in cantidades_planificadas + cantidades_no_asignadas
            if cantidad > 0
        ]
        hubo_cambios = oferta_martes.cantidad != total_original
        hubo_recalculo_datos = False
        detalle_cambios = []
        if total_original != oferta_martes.cantidad:
            detalle_cambios.append(f"Cantidad total {total_original} -> {oferta_martes.cantidad}")
        if total_no_asignado_original and cantidad_no_asignada_actualizada != total_no_asignado_original:
            if cantidad_no_asignada_actualizada == 0:
                detalle_cambios.append("Sin remanente pendiente en no asignados")
            else:
                detalle_cambios.append(
                    f"Remanente no asignado {total_no_asignado_original} -> {cantidad_no_asignada_actualizada}"
                )

        for idx_plan, item in enumerate(lotes_planificados):
            lote_actual = item["lote"]
            cantidad_fragmento = cantidades_planificadas[idx_plan]
            if cantidad_fragmento <= 0:
                reemplazos_por_dia[item["dia_idx"]][item["lote_idx"]] = None
                if lote_actual.cantidad != 0:
                    hubo_cambios = True
                continue

            oferta_fragmento = oferta_martes.model_copy(update={"cantidad": cantidad_fragmento})
            nuevo_lote = calcular_lote_proyectado(oferta_fragmento, lote_actual.fecha_fin_retiro, params)
            nuevo_lote.es_compra_terceros = lote_actual.es_compra_terceros
            nuevo_lote.motivo_compra = lote_actual.motivo_compra
            nuevo_lote.excluido = lote_actual.excluido
            nuevo_lote.motivo_exclusion = lote_actual.motivo_exclusion
            nuevo_lote.fragmentado = lote_actual.fragmentado or len(fragmentos_actualizados) > 1
            nuevo_lote.fragment_id = lote_actual.fragment_id
            nuevo_lote.cantidad_original_lote = oferta_martes.cantidad
            reemplazos_por_dia[item["dia_idx"]][item["lote_idx"]] = nuevo_lote

            if (
                abs(nuevo_lote.peso_actual - lote_actual.peso_actual) > 0.001
                or nuevo_lote.edad_actual != lote_actual.edad_actual
                or abs((nuevo_lote.ganancia_diaria_original or 0) - (lote_actual.ganancia_diaria_original or 0)) > 0.0001
            ):
                hubo_recalculo_datos = True

            if (
                abs(nuevo_lote.peso_vivo_retiro - lote_actual.peso_vivo_retiro) > 0.001
                or nuevo_lote.edad_fin_retiro != lote_actual.edad_fin_retiro
                or nuevo_lote.cantidad != lote_actual.cantidad
                or hubo_recalculo_datos
            ):
                hubo_cambios = True

            alertas_rango = []
            if nuevo_lote.edad_fin_retiro < params.edad_min_faena:
                alertas_rango.append(f"Edad {nuevo_lote.edad_fin_retiro} < mín {params.edad_min_faena}")
            if nuevo_lote.edad_fin_retiro > params.edad_max_faena:
                alertas_rango.append(f"Edad {nuevo_lote.edad_fin_retiro} > máx {params.edad_max_faena}")
            if nuevo_lote.peso_vivo_retiro < params.peso_min_faena:
                alertas_rango.append(f"Peso {nuevo_lote.peso_vivo_retiro:.2f} < mín {params.peso_min_faena:.2f}")
            if nuevo_lote.peso_vivo_retiro > params.peso_max_faena:
                alertas_rango.append(f"Peso {nuevo_lote.peso_vivo_retiro:.2f} > máx {params.peso_max_faena:.2f}")
            if alertas_rango:
                resumen.lotes_fuera_rango_post_ajuste += 1
                resumen.detalle_fuera_rango_post_ajuste.append({
                    "granja": lote_actual.granja,
                    "galpon": lote_actual.galpon,
                    "nucleo": lote_actual.nucleo,
                    "cantidad": nuevo_lote.cantidad,
                    "dia": DIAS_SEMANA[item["dia_idx"]] if item["dia_idx"] < len(DIAS_SEMANA) else str(item["dia_idx"]),
                    "alerta": "; ".join(alertas_rango),
                })

        offset_no_asignados = len(lotes_planificados)
        for idx_na, item in enumerate(lotes_no_asignados):
            cantidad_actualizada = cantidades_no_asignadas[idx_na]
            lote_na = item["lote"]
            if cantidad_actualizada <= 0:
                lotes_no_asignados_actualizados[item["index"]] = None
                if lote_na.cantidad != 0:
                    hubo_cambios = True
                continue

            if lote_na.cantidad != cantidad_actualizada:
                hubo_cambios = True
            lote_na.cantidad = cantidad_actualizada
            lote_na.sexo = oferta_martes.sexo
            sufijo_ajuste = " (datos actualizados con oferta martes)"
            if sufijo_ajuste not in lote_na.motivo:
                lote_na.motivo = f"{lote_na.motivo}{sufijo_ajuste}"
            lotes_no_asignados_actualizados[item["index"]] = lote_na

        if hubo_cambios:
            referencia = (lotes_planificados[0]["lote"] if lotes_planificados else lotes_no_asignados[0]["lote"])
            if hubo_recalculo_datos:
                detalle_cambios.append("Peso/edad/ganancia actualizados")
            resumen.lotes_actualizados += 1
            resumen.detalle_actualizados.append({
                "granja": referencia.granja,
                "galpon": referencia.galpon,
                "nucleo": referencia.nucleo,
                "dia": DIAS_SEMANA[lotes_planificados[0]["dia_idx"]] if lotes_planificados else "pool_no_asignados",
                "cambios": "; ".join(detalle_cambios) if detalle_cambios else f"Cantidad total reajustada a {oferta_martes.cantidad}",
            })

    for dia_idx, dia in enumerate(semana.dias):
        dia.lotes = [lote for lote in reemplazos_por_dia[dia_idx] if lote is not None]

    semana.dias = [
        calcular_dia_faena(
            dia.fecha,
            dia.lotes,
            params=params,
            gallinas_cantidad=dia.gallinas_cantidad,
            gallinas_livianas=dia.gallinas_livianas_cantidad,
            gallinas_pesadas=dia.gallinas_pesadas_cantidad,
        )
        for dia in semana.dias
    ]

    candidatos_reinsercion = []
    for idx, lote in lotes_no_asignados_actualizados.items():
        if lote is None or lote.cantidad <= 0:
            continue
        key = _clave_lote(lote.granja, lote.galpon, lote.nucleo, lote.sexo, lote.fecha_ingreso)
        oferta_base = martes_lookup.get(key) or ofertas_referencia_index.get(key)
        if oferta_base is None:
            continue
        candidatos_reinsercion.append({
            "index": idx,
            "oferta": oferta_base.model_copy(update={"cantidad": lote.cantidad}),
        })

    if candidatos_reinsercion:
        semana.dias, indices_reinsertados, detalle_reinsertados = _reinsertar_lotes_no_asignados_actualizados(
            candidatos_reinsercion,
            semana.dias,
            params,
        )
        for idx in indices_reinsertados:
            lotes_no_asignados_actualizados[idx] = None
        resumen.lotes_reinsertados_no_asignados = len(detalle_reinsertados)
        resumen.detalle_reinsertados_no_asignados = detalle_reinsertados

    lotes_nuevos_oferta: List[LoteOferta] = []
    for oferta in martes_index.values():
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

    todos_no_asignados = [
        lote
        for lote in lotes_no_asignados_actualizados.values()
        if lote is not None and lote.cantidad > 0
    ] + lotes_no_asignados_nuevos

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
