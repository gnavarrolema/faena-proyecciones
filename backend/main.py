"""
API FastAPI para la planificación de faena avícola.
"""
import logging
import uuid

from fastapi import FastAPI, UploadFile, File, HTTPException, Depends
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import OAuth2PasswordRequestForm
from pydantic import BaseModel
from datetime import date, datetime, timedelta
from typing import List, Optional

from .auth import (
    Token,
    TokenData,
    verify_password,
    get_password_hash,
    create_access_token,
    get_current_user,
    ADMIN_USERNAME,
    ADMIN_PASSWORD_HASH,
    ACCESS_TOKEN_EXPIRE_MINUTES
)

from .calculo import (
    Parametros, LoteOferta, LoteProyectado, DiaFaena, SemanaFaena,
    AjusteMartesResumen, FeriadoAplicado, EventoGallinas, LoteNoAsignado,
    aplicar_ajuste_martes,
    calcular_lote_proyectado, calcular_dia_faena, calcular_semana_faena,
    generar_proyeccion, ordenar_oferta_por_prioridad,
    calcular_edad_fin_retiro_v2, diferencia_edad_ideal,
    peso_vivo_retiro, peso_faenado, calibre_promedio, cajas_lote,
    evaluar_elegibilidad_lote,
    calcular_alerta_temprana,
    generar_sugerencias_diferimiento,
    validar_mortalidad_oferta,
    normalizar_granja_clave,
)
from .parser_excel import leer_oferta_excel
from .parser_produccion import (
    leer_produccion_excel, simular_mortalidad,
    SemanaProduccion, TASAS_MORTALIDAD_DEFAULT, DIAS_HASTA_FAENA,
    construir_tasas_mortalidad, calcular_fecha_faena_estimada,
)
from .feriados import obtener_feriados_nacionales, obtener_feriados_rango
from .config import CORS_ORIGINS, CORS_ALLOW_CREDENTIALS
from . import storage

logger = logging.getLogger(__name__)


def _get_produccion_reference_config(params: Optional[Parametros] = None) -> dict:
    """Devuelve la configuración persistida para cruces con producción BB."""
    params = params or _get_parametros()
    tasas = construir_tasas_mortalidad(
        params.produccion_mortalidad_min,
        params.produccion_mortalidad_max,
        params.produccion_mortalidad_paso,
    )
    if not tasas:
        tasas = TASAS_MORTALIDAD_DEFAULT
    return {
        "dias_hasta_faena": params.produccion_dias_hasta_faena,
        "tolerancia_dias": params.produccion_tolerancia_cruce_dias,
        "tasas_mortalidad": tasas,
    }


def _serializar_semanas_referenciadas(
    semanas: list[SemanaProduccion],
    dias_hasta_faena: int,
) -> list[dict]:
    """Serializa las semanas BB usadas como referencia en un cruce."""
    return [
        {
            "fecha_desde": sem.fecha_desde.isoformat(),
            "fecha_hasta": sem.fecha_hasta.isoformat(),
            "pollitos_cargados": sem.pollitos_cargados,
            "fecha_faena_estimada": calcular_fecha_faena_estimada(
                sem.fecha_desde,
                dias_hasta_faena,
            ).isoformat(),
        }
        for sem in sorted(semanas, key=lambda item: item.fecha_desde)
    ]


# ─── Helpers: lectura directa de storage ────────────────────────────────────────

def _get_parametros() -> Parametros:
    """Lee parámetros desde storage. Devuelve defaults si no existen."""
    data = storage.load_parametros()
    if data:
        try:
            return Parametros(**data)
        except Exception as e:
            logger.warning(f"Error leyendo parámetros de storage: {e}")
    return Parametros()


def _get_ofertas() -> list[LoteOferta]:
    """Lee ofertas desde storage. Devuelve lista vacía si no existen."""
    data = storage.load_ofertas()
    if data:
        try:
            return [LoteOferta(**o) for o in data]
        except Exception as e:
            logger.warning(f"Error leyendo ofertas de storage: {e}")
    return []


def _get_ofertas_martes() -> list[LoteOferta]:
    """Lee la oferta del martes desde storage. Devuelve lista vacía si no existe."""
    data = storage.load_ofertas_martes()
    if data:
        try:
            return [LoteOferta(**o) for o in data]
        except Exception as e:
            logger.warning(f"Error leyendo ofertas del martes de storage: {e}")
    return []


def _build_oferta_summary(ofertas: list[LoteOferta]) -> dict:
    fechas_peso = [o.fecha_peso for o in ofertas if o.fecha_peso]
    fechas_ingreso = [o.fecha_ingreso for o in ofertas if o.fecha_ingreso]
    return {
        "total_lotes": len(ofertas),
        "total_pollos": sum(o.cantidad for o in ofertas),
        "fecha_peso_desde": min(fechas_peso).isoformat() if fechas_peso else None,
        "fecha_peso_hasta": max(fechas_peso).isoformat() if fechas_peso else None,
        "fecha_ingreso_desde": min(fechas_ingreso).isoformat() if fechas_ingreso else None,
        "fecha_ingreso_hasta": max(fechas_ingreso).isoformat() if fechas_ingreso else None,
    }


def _build_produccion_summary(semanas: list[SemanaProduccion]) -> dict:
    fechas_desde = [s.fecha_desde for s in semanas if s.fecha_desde]
    fechas_hasta = [s.fecha_hasta for s in semanas if s.fecha_hasta]
    return {
        "total_semanas": len(semanas),
        "total_pollitos": sum(s.pollitos_cargados for s in semanas),
        "fecha_desde": min(fechas_desde).isoformat() if fechas_desde else None,
        "fecha_hasta": max(fechas_hasta).isoformat() if fechas_hasta else None,
    }


def _same_summary_values(metadata: Optional[dict], persisted: dict, fields: tuple[str, ...]) -> Optional[bool]:
    if not metadata:
        return None
    comparable = [field for field in fields if metadata.get(field) is not None]
    if not comparable:
        return None
    return all(metadata.get(field) == persisted.get(field) for field in comparable)


def _build_fuentes_validacion(ofertas: list[LoteOferta], produccion_data: Optional[list[dict]]) -> dict:
    oferta_summary = _build_oferta_summary(ofertas)
    oferta_metadata = storage.load_oferta_metadata() or {}

    semanas_produccion = []
    for row in produccion_data or []:
        try:
            semanas_produccion.append(SemanaProduccion(**row))
        except Exception as e:
            logger.warning(f"Error reconstruyendo semana de producción para metadata: {e}")

    produccion_summary = _build_produccion_summary(semanas_produccion)
    produccion_metadata = storage.load_produccion_metadata() or {}

    return {
        "oferta": {
            "filename": oferta_metadata.get("filename"),
            "uploaded_at": oferta_metadata.get("uploaded_at"),
            "upload_key": oferta_metadata.get("upload_key"),
            "sheet_name": oferta_metadata.get("sheet_name"),
            "total_descartadas": oferta_metadata.get("total_descartadas"),
            "persisted": oferta_summary,
            "metadata_matches_persisted": _same_summary_values(
                oferta_metadata,
                oferta_summary,
                ("total_lotes", "total_pollos", "fecha_peso_desde", "fecha_peso_hasta", "fecha_ingreso_desde", "fecha_ingreso_hasta"),
            ),
        },
        "produccion": {
            "filename": produccion_metadata.get("filename"),
            "uploaded_at": produccion_metadata.get("uploaded_at"),
            "upload_key": produccion_metadata.get("upload_key"),
            "sheet_name": produccion_metadata.get("sheet_name"),
            "persisted": produccion_summary,
            "metadata_matches_persisted": _same_summary_values(
                produccion_metadata,
                produccion_summary,
                ("total_semanas", "total_pollitos", "fecha_desde", "fecha_hasta"),
            ),
        },
    }


def _get_proyeccion() -> Optional[SemanaFaena]:
    """Lee proyección desde storage. Devuelve None si no existe."""
    data = storage.load_proyeccion()
    if data:
        try:
            return SemanaFaena(**data)
        except Exception as e:
            logger.warning(f"Error leyendo proyección de storage: {e}")
    return None


def _get_modo_planificacion_actual() -> str:
    """Obtiene el modo persistido de la proyección actual o lo infiere desde la config guardada."""
    data = storage.load_proyeccion() or {}
    if data.get("modo_planificacion"):
        return data["modo_planificacion"]

    config = storage.load_proyeccion_config() or {}
    if config.get("criterio_gerente") is False:
        return "optimizacion_restricciones"
    return "cascada_madurez"


def _ganancia_default_por_sexo(sexo: str, params: Parametros) -> float:
    return params.ganancia_diaria_hembra if (sexo or "").upper() == "H" else params.ganancia_diaria_macho


def _reconstruir_oferta_desde_lote(
    lote: LoteProyectado,
    fecha_faena: date,
    params: Parametros,
) -> LoteOferta:
    fecha_peso = lote.fecha_peso_original or fecha_faena
    fecha_ingreso = lote.fecha_ingreso_original or fecha_peso
    ganancia = (
        lote.ganancia_diaria_original
        if lote.ganancia_diaria_original is not None
        else _ganancia_default_por_sexo(lote.sexo, params)
    )

    return LoteOferta(
        fecha_peso=fecha_peso,
        granja=lote.granja,
        galpon=lote.galpon,
        nucleo=lote.nucleo,
        cantidad=lote.cantidad,
        sexo=lote.sexo,
        edad_proyectada=lote.edad_actual,
        peso_muestreo_proy=lote.peso_actual,
        ganancia_diaria=ganancia,
        dias_proyectados=lote.dias_proyectados_original,
        edad_real=lote.edad_actual,
        peso_muestreo_real=lote.peso_actual,
        fecha_ingreso=fecha_ingreso,
    )


def _recalcular_lote_en_fecha(
    lote: LoteProyectado,
    fecha_faena: date,
    params: Parametros,
) -> LoteProyectado:
    oferta = _reconstruir_oferta_desde_lote(lote, fecha_faena, params)
    recalculado = calcular_lote_proyectado(oferta, fecha_faena, params)
    return _copiar_metadata_lote(lote, recalculado)


def _copiar_metadata_lote(origen: LoteProyectado, destino: LoteProyectado) -> LoteProyectado:
    destino.es_compra_terceros = origen.es_compra_terceros
    destino.motivo_compra = origen.motivo_compra
    destino.excluido = origen.excluido
    destino.motivo_exclusion = origen.motivo_exclusion
    destino.fragmentado = origen.fragmentado
    destino.fragment_id = origen.fragment_id
    destino.cantidad_original_lote = origen.cantidad_original_lote or origen.cantidad
    return destino


def _copiar_metadata_diferida(datos: dict, destino: LoteProyectado) -> LoteProyectado:
    destino.fragmentado = datos.get("fragmentado", False)
    destino.fragment_id = datos.get("fragment_id")
    destino.cantidad_original_lote = datos.get("cantidad_original_lote") or destino.cantidad
    return destino


def _recalcular_proyeccion_actual(semana: SemanaFaena, params: Parametros) -> SemanaFaena:
    dias_recalculados: list[DiaFaena] = []

    for dia in semana.dias:
        lotes_recalculados = [
            _recalcular_lote_en_fecha(lote, dia.fecha, params)
            for lote in dia.lotes
        ]
        dias_recalculados.append(
            calcular_dia_faena(
                dia.fecha,
                lotes_recalculados,
                params=params,
                gallinas_cantidad=dia.gallinas_cantidad,
                gallinas_livianas=dia.gallinas_livianas_cantidad,
                gallinas_pesadas=dia.gallinas_pesadas_cantidad,
            )
        )

    resultado = calcular_semana_faena(
        semana.fecha_inicio,
        dias_recalculados,
        params,
        lotes_no_asignados=semana.lotes_no_asignados,
        lotes_fuera_rango=semana.lotes_fuera_rango,
    )
    resultado.feriados_aplicados = semana.feriados_aplicados
    resultado.eventos_gallinas = semana.eventos_gallinas
    return resultado


def _oferta_key(granja: str, galpon: int, nucleo: int, sexo: str, fecha_ingreso: Optional[date]) -> tuple:
    return (
        normalizar_granja_clave(granja),
        galpon,
        nucleo,
        sexo,
        fecha_ingreso.isoformat() if fecha_ingreso else "",
    )


def _estado_ajuste_martes(oferta_jueves: LoteOferta, oferta_martes: Optional[LoteOferta]) -> str:
    if oferta_martes is None:
        return "sin_ajuste"

    campos = (
        "cantidad",
        "edad_proyectada",
        "peso_muestreo_proy",
        "ganancia_diaria",
        "edad_real",
        "peso_muestreo_real",
    )
    for campo in campos:
        if getattr(oferta_jueves, campo) != getattr(oferta_martes, campo):
            return "actualizado"
    return "confirmado"


def _build_oferta_trace() -> dict:
    ofertas_jueves = _get_ofertas()
    ofertas_martes = _get_ofertas_martes()
    planificacion = _get_proyeccion()

    martes_index = {
        _oferta_key(o.granja, o.galpon, o.nucleo, o.sexo, o.fecha_ingreso): o
        for o in ofertas_martes
    }

    planificados: dict[tuple, dict] = {}
    no_asignados: dict[tuple, dict] = {}
    fuera_rango: dict[tuple, dict] = {}

    if planificacion:
        dias_semana = ['Lunes', 'Martes', 'Miércoles', 'Jueves', 'Viernes', 'Sábado', 'Domingo']
        for dia in planificacion.dias:
            dia_nombre = dias_semana[dia.fecha.weekday()]
            for lote in dia.lotes:
                fecha_ingreso = lote.fecha_ingreso_original
                if isinstance(fecha_ingreso, str):
                    fecha_ingreso = date.fromisoformat(fecha_ingreso)
                key = _oferta_key(lote.granja, lote.galpon, lote.nucleo, lote.sexo, fecha_ingreso)
                detalle = planificados.setdefault(key, {
                    "dia": None,
                    "fecha": None,
                    "dias": [],
                    "fechas": [],
                    "cantidad_planificada": 0,
                    "es_compra_terceros": False,
                    "fragmentado": False,
                    "fragmentos": [],
                })
                if dia_nombre not in detalle["dias"]:
                    detalle["dias"].append(dia_nombre)
                fecha_iso = dia.fecha.isoformat()
                if detalle["dia"] is None:
                    detalle["dia"] = dia_nombre
                if detalle["fecha"] is None:
                    detalle["fecha"] = fecha_iso
                if fecha_iso not in detalle["fechas"]:
                    detalle["fechas"].append(fecha_iso)
                detalle["cantidad_planificada"] += lote.cantidad
                detalle["es_compra_terceros"] = detalle["es_compra_terceros"] or lote.es_compra_terceros
                detalle["fragmentado"] = detalle["fragmentado"] or lote.fragmentado
                detalle["fragmentos"].append({
                    "dia": dia_nombre,
                    "fecha": fecha_iso,
                    "cantidad": lote.cantidad,
                    "fragment_id": lote.fragment_id,
                })

        for lote in planificacion.lotes_no_asignados or []:
            key = _oferta_key(lote.granja, lote.galpon, lote.nucleo, lote.sexo, lote.fecha_ingreso)
            detalle = no_asignados.setdefault(key, {
                "motivo": None,
                "cantidad_no_asignada": 0,
                "motivos": [],
                "dias_elegibles": [],
            })
            detalle["cantidad_no_asignada"] += lote.cantidad
            if detalle["motivo"] is None:
                detalle["motivo"] = lote.motivo
            if lote.motivo not in detalle["motivos"]:
                detalle["motivos"].append(lote.motivo)
            for dia_elegible in lote.dias_elegibles:
                fecha_iso = dia_elegible.isoformat() if isinstance(dia_elegible, date) else dia_elegible
                if fecha_iso not in detalle["dias_elegibles"]:
                    detalle["dias_elegibles"].append(fecha_iso)

        for lote in planificacion.lotes_fuera_rango or []:
            key = _oferta_key(lote.granja, lote.galpon, lote.nucleo, lote.sexo, lote.fecha_ingreso)
            detalle = fuera_rango.setdefault(key, {
                "motivo": None,
                "cantidad_fuera_rango": 0,
                "motivos": [],
                "detalle_por_dia": [],
            })
            detalle["cantidad_fuera_rango"] += lote.cantidad
            if detalle["motivo"] is None:
                detalle["motivo"] = lote.motivo
            if lote.motivo not in detalle["motivos"]:
                detalle["motivos"].append(lote.motivo)
            detalle["detalle_por_dia"].extend(lote.detalle_por_dia)

    registros = []
    resumen = {
        "total_jueves": len(ofertas_jueves),
        "planificados": 0,
        "parciales": 0,
        "no_asignados": 0,
        "fuera_rango": 0,
        "pendientes": 0,
        "ajustados_martes": 0,
        "confirmados_martes": 0,
        "sin_ajuste_martes": 0,
    }

    for idx, oferta in enumerate(ofertas_jueves):
        key = _oferta_key(oferta.granja, oferta.galpon, oferta.nucleo, oferta.sexo, oferta.fecha_ingreso)
        oferta_martes = martes_index.get(key)
        ajuste_estado = _estado_ajuste_martes(oferta, oferta_martes)

        tiene_plan = key in planificados
        tiene_no_asignado = key in no_asignados
        tiene_fuera_rango = key in fuera_rango

        if tiene_plan and tiene_no_asignado:
            estado_planificacion = "parcial"
            detalle = {
                "planificado": planificados[key],
                "no_asignado": no_asignados[key],
            }
            resumen["parciales"] += 1
        elif tiene_plan:
            estado_planificacion = "planificado"
            detalle = planificados[key]
            resumen["planificados"] += 1
        elif tiene_no_asignado:
            estado_planificacion = "no_asignado"
            detalle = no_asignados[key]
            resumen["no_asignados"] += 1
        elif tiene_fuera_rango:
            estado_planificacion = "fuera_rango"
            detalle = fuera_rango[key]
            resumen["fuera_rango"] += 1
        else:
            estado_planificacion = "pendiente"
            detalle = None
            resumen["pendientes"] += 1

        if ajuste_estado == "actualizado":
            resumen["ajustados_martes"] += 1
        elif ajuste_estado == "confirmado":
            resumen["confirmados_martes"] += 1
        else:
            resumen["sin_ajuste_martes"] += 1

        registros.append({
            "id": idx + 1,
            "clave": {
                "granja": oferta.granja,
                "galpon": oferta.galpon,
                "nucleo": oferta.nucleo,
                "sexo": oferta.sexo,
                "fecha_ingreso": oferta.fecha_ingreso.isoformat() if oferta.fecha_ingreso else None,
            },
            "oferta_jueves": oferta.model_dump(),
            "estado_planificacion": estado_planificacion,
            "tomado_en_planificacion": estado_planificacion in {"planificado", "parcial"},
            "detalle_planificacion": detalle,
            "ajuste_martes": {
                "disponible": oferta_martes is not None,
                "estado": ajuste_estado,
                "oferta": oferta_martes.model_dump() if oferta_martes else None,
            },
        })

    claves_jueves = {
        _oferta_key(o.granja, o.galpon, o.nucleo, o.sexo, o.fecha_ingreso)
        for o in ofertas_jueves
    }
    nuevos_martes = []
    for oferta in ofertas_martes:
        key = _oferta_key(oferta.granja, oferta.galpon, oferta.nucleo, oferta.sexo, oferta.fecha_ingreso)
        if key not in claves_jueves:
            nuevos_martes.append(oferta.model_dump())

    return {
        "resumen": resumen,
        "registros": registros,
        "ajuste_martes_cargado": len(ofertas_martes) > 0,
        "nuevos_martes": nuevos_martes,
        "planificacion_disponible": planificacion is not None,
    }


app = FastAPI(
    title="Proyección de Faena Avícola",
    description="API para planificación y proyección de faena avícola",
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=CORS_ORIGINS,
    allow_credentials=CORS_ALLOW_CREDENTIALS,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ─── Request/Response Models ────────────────────────────────────────────────────

class ProyeccionRequest(BaseModel):
    fecha_inicio_semana: date
    dias_faena: int = 5
    pollos_por_dia: int = 35000
    parametros: Optional[Parametros] = None
    feriados_custom: Optional[List[date]] = None
    habilitar_sabado: bool = False
    gallinas: Optional[dict] = None  # {fecha_iso: cantidad}
    incluir_deficit: bool = False  # incluir lotes del déficit de semana anterior
    criterio_gerente: bool = True
    permitir_fraccionamiento_lotes: Optional[bool] = None
    excluir_backlog_semana_previa: Optional[bool] = None
    minimos_como_alerta: Optional[bool] = None


class FeriadoCustomRequest(BaseModel):
    """Para agregar un feriado personalizado."""
    fecha: date
    descripcion: str = "Feriado personalizado"


class AsignacionManual(BaseModel):
    """Para mover un lote de un día a otro."""
    lote_index: int
    dia_origen: int     # índice 0-5
    dia_destino: int    # índice 0-5


class LoteManualRequest(BaseModel):
    """Para agregar/editar un lote manualmente."""
    granja: str
    galpon: int
    nucleo: int
    cantidad: int
    sexo: str
    edad_proyectada: int
    peso_muestreo_proy: float
    ganancia_diaria: float = 0.09
    fecha_peso: date
    fecha_ingreso: date
    dia_faena: int  # índice 0-5, día de la semana al que asignar
    es_compra_terceros: bool = False
    motivo_compra: Optional[str] = None


class ParametrosUpdate(BaseModel):
    ganancia_diaria_macho: Optional[float] = None
    ganancia_diaria_hembra: Optional[float] = None
    rendimiento_canal: Optional[float] = None
    kg_por_caja: Optional[float] = None
    edad_ideal_macho: Optional[int] = None
    edad_ideal_hembra: Optional[int] = None
    edad_ideal_sin_sexar: Optional[int] = None
    edad_min_faena: Optional[int] = None
    edad_max_faena: Optional[int] = None
    peso_min_faena: Optional[float] = None
    peso_max_faena: Optional[float] = None
    pollos_diarios_objetivo_min: Optional[int] = None
    pollos_diarios_objetivo_max: Optional[int] = None
    capacidad_maxima_planta: Optional[int] = None
    limite_sabado: Optional[int] = None
    descuento_sofia: Optional[int] = None
    capacidad_con_horas_extras: Optional[int] = None
    peso_objetivo_recepcion: Optional[float] = None
    produccion_dias_hasta_faena: Optional[int] = None
    produccion_tolerancia_cruce_dias: Optional[int] = None
    produccion_mortalidad_min: Optional[float] = None
    produccion_mortalidad_max: Optional[float] = None
    produccion_mortalidad_paso: Optional[float] = None


class GallinasRequest(BaseModel):
    """Para marcar un día con faena de gallinas."""
    dia_index: int         # índice del día en la proyección
    cantidad: int          # cantidad de gallinas
    tipo: str = "liviana"  # "liviana" | "pesada"
    descripcion: str = "Faena de gallinas"


class PesoRealRequest(BaseModel):
    """Para cargar el peso real recibido de un día."""
    fecha: date
    peso_promedio_real: float  # kg promedio real


class PesosRealesBatchRequest(BaseModel):
    """Para cargar pesos reales de múltiples días a la vez."""
    pesos: List[PesoRealRequest]


class GuardarEscenarioRequest(BaseModel):
    """Para guardar la proyección actual como escenario."""
    nombre: str
    descripcion: Optional[str] = None
    tasa_mortalidad: Optional[float] = None  # ej: 0.075 (7.5%)


class CompararEscenariosRequest(BaseModel):
    """Para comparar escenarios por IDs."""
    ids: List[str]


class FactibilidadProduccion(BaseModel):
    """Resultado de cruzar oferta vs producción propia."""
    encontrada: bool
    pollitos_cargados: Optional[int] = None
    disponibles_mejor: Optional[int] = None   # al 4.5% mortalidad
    disponibles_peor: Optional[int] = None     # al peor escenario configurado
    total_oferta: int = 0
    deficit_peor: Optional[int] = None          # oferta - disponibles_peor (si >0)
    cobertura_pct_peor: Optional[float] = None  # (oferta / disponibles_peor) * 100
    coberturas: Optional[list] = None           # [{tasa, disponibles, cobertura_pct}, ...]
    total_compra_terceros: int = 0
    total_semanas_referenciadas: int = 0
    metodo_cruce: str = "macro_faena"
    contexto: str = "oferta_actual"
    dias_hasta_faena_referencia: int = DIAS_HASTA_FAENA
    tolerancia_cruce_dias: int = 3
    semanas_referenciadas: Optional[list] = None


class ReferenciaProduccionResponse(BaseModel):
    """Respuesta del endpoint de referencia de producción."""
    encontrada: bool
    semana_produccion: Optional[dict] = None
    total_oferta_actual: int = 0
    cobertura_pct: Optional[float] = None
    coberturas: Optional[list] = None  # [{tasa, disponibles, cobertura_pct}, ...]
    total_compra_terceros: int = 0
    total_semanas_referenciadas: int = 0
    metodo_cruce: str = "macro_faena"
    dias_hasta_faena_referencia: int = DIAS_HASTA_FAENA
    tolerancia_cruce_dias: int = 3
    mensaje: str = ""


class RedistribuirDiaRequest(BaseModel):
    """Para redistribuir los lotes de un día a los días restantes."""
    dia_index: int


class DeficitResponse(BaseModel):
    """Lotes no asignados de la proyección actual."""
    lotes_no_asignados: list
    total_pollos: int
    total_lotes: int


class CargarDeficitResponse(BaseModel):
    """Respuesta al guardar el déficit para la semana siguiente."""
    lotes_trasladados: int
    pollos_trasladados: int
    mensaje: str


class DiferirLoteRequest(BaseModel):
    """Para diferir un lote de semana 1 a semana 2."""
    dia_index: int
    lote_index: int
    motivo: str = ""


class RestaurarLoteRequest(BaseModel):
    """Para restaurar un lote diferido de vuelta a semana 1."""
    diferido_index: int
    dia_destino: Optional[int] = None  # si None, auto-asigna al día con más déficit


class MoverLoteS2Request(BaseModel):
    """Para mover un lote entre días dentro de semana 2."""
    lote_index: int
    dia_origen: int
    dia_destino: int


class EnviarS1Request(BaseModel):
    """Para enviar un lote de semana 2 a semana 1."""
    dia_index_s2: int
    lote_index_s2: int
    dia_destino_s1: Optional[int] = None  # si None, auto-asigna al día con más déficit en S1


# ─── Helpers: factibilidad producción ─────────────────────────────────────────

def _buscar_semanas_produccion_referenciadas(
    semanas: list[SemanaProduccion],
    fecha_inicio_semana: Optional[date] = None,
    ofertas: Optional[list[LoteOferta]] = None,
    fechas_ingreso: Optional[list[date]] = None,
    dias_hasta_faena: int = DIAS_HASTA_FAENA,
    tolerancia_dias: int = 3,
) -> list[SemanaProduccion]:
    """Encuentra las semanas de producción relevantes para un cruce."""
    semanas_encontradas: list[SemanaProduccion] = []
    fechas_referencia = [f for f in (fechas_ingreso or []) if f is not None]
    if not fechas_referencia and ofertas:
        fechas_referencia = [
            oferta.fecha_ingreso for oferta in ofertas if oferta.fecha_ingreso
        ]

    if fechas_referencia:
        seen: set[str] = set()
        for fecha_ingreso in fechas_referencia:
            for sem in semanas:
                key = sem.fecha_desde.isoformat()
                if key in seen:
                    continue
                if sem.fecha_desde <= fecha_ingreso <= sem.fecha_hasta:
                    seen.add(key)
                    semanas_encontradas.append(sem)
                    break
            else:
                for sem in semanas:
                    key = sem.fecha_desde.isoformat()
                    if key in seen:
                        continue
                    if abs((fecha_ingreso - sem.fecha_desde).days) <= tolerancia_dias:
                        seen.add(key)
                        semanas_encontradas.append(sem)
                        break
                    if abs((fecha_ingreso - sem.fecha_hasta).days) <= tolerancia_dias:
                        seen.add(key)
                        semanas_encontradas.append(sem)
                        break
        return semanas_encontradas

    if fecha_inicio_semana is None:
        return []

    for sem in semanas:
        fecha_faena_estimada = calcular_fecha_faena_estimada(
            sem.fecha_desde,
            dias_hasta_faena,
        )
        if abs((fecha_faena_estimada - fecha_inicio_semana).days) <= tolerancia_dias:
            semanas_encontradas.append(sem)
            break

    return semanas_encontradas


def _extraer_contexto_planificado_propio(proyeccion: SemanaFaena) -> dict:
    """Resume el plan propio asignado en la proyección activa."""
    fechas_ingreso: list[date] = []
    total_propio = 0
    total_compra_terceros = 0

    for dia in proyeccion.dias or []:
        for lote in dia.lotes or []:
            if lote.es_compra_terceros:
                total_compra_terceros += lote.cantidad
                continue
            total_propio += lote.cantidad
            if lote.fecha_ingreso_original:
                fechas_ingreso.append(lote.fecha_ingreso_original)

    return {
        "fechas_ingreso": fechas_ingreso,
        "total_propio": total_propio,
        "total_compra_terceros": total_compra_terceros,
    }


def _agrupar_simulacion_produccion(
    semanas: list[SemanaProduccion],
    dias_hasta_faena: int,
    tasas_mortalidad: list[float],
) -> dict:
    """Consolida varias semanas de producción en una referencia única."""
    simulacion = simular_mortalidad(
        semanas,
        tasas=tasas_mortalidad,
        dias_hasta_faena=dias_hasta_faena,
    )
    if not simulacion:
        return {}

    tasas = [fila.tasa_mortalidad for fila in simulacion[0].simulaciones]
    simulaciones = []
    for tasa in tasas:
        disponibles = sum(
            next(
                fila.pollitos_disponibles
                for fila in sem.simulaciones
                if abs(fila.tasa_mortalidad - tasa) < 1e-9
            )
            for sem in simulacion
        )
        simulaciones.append({
            "tasa_mortalidad": tasa,
            "pollitos_disponibles": disponibles,
        })

    fecha_faena_desde = min(sem.fecha_faena_estimada for sem in simulacion)
    fecha_faena_hasta = max(sem.fecha_faena_estimada for sem in simulacion)

    return {
        "fecha_desde": min(sem.fecha_desde for sem in semanas).isoformat(),
        "fecha_hasta": max(sem.fecha_hasta for sem in semanas).isoformat(),
        "pollitos_cargados": sum(sem.pollitos_cargados for sem in semanas),
        "fecha_faena_estimada": (
            fecha_faena_desde.isoformat() if len(simulacion) == 1 else None
        ),
        "fecha_faena_estimada_desde": fecha_faena_desde.isoformat(),
        "fecha_faena_estimada_hasta": fecha_faena_hasta.isoformat(),
        "total_semanas": len(semanas),
        "semanas_referenciadas": _serializar_semanas_referenciadas(
            semanas,
            dias_hasta_faena,
        ),
        "simulaciones": simulaciones,
    }

def _calcular_factibilidad(
    fecha_inicio_semana: date,
    total_oferta: int,
    ofertas: Optional[list[LoteOferta]] = None,
    fechas_ingreso: Optional[list[date]] = None,
    total_compra_terceros: int = 0,
    metodo_cruce: str = "macro_faena",
    contexto: str = "oferta_actual",
) -> Optional[FactibilidadProduccion]:
    """Cruza oferta con producción cargada para evaluar factibilidad.

    Si se pasan ofertas, agrega TODAS las semanas de producción que
    corresponden a los fecha_ingreso de los lotes (más preciso para el
    cruce validación cruzada).  Sin ofertas, busca una sola semana por
    fecha_faena_estimada (compatibilidad con proyección).
    """
    data = storage.load_produccion()
    if not data:
        return None

    config = _get_produccion_reference_config()
    semanas = [SemanaProduccion(**s) for s in data]
    semanas_encontradas = _buscar_semanas_produccion_referenciadas(
        semanas,
        fecha_inicio_semana=fecha_inicio_semana,
        ofertas=ofertas,
        fechas_ingreso=fechas_ingreso,
        dias_hasta_faena=config["dias_hasta_faena"],
        tolerancia_dias=config["tolerancia_dias"],
    )

    if not semanas_encontradas:
        return FactibilidadProduccion(
            encontrada=False,
            total_oferta=total_oferta,
            total_compra_terceros=total_compra_terceros,
            metodo_cruce=metodo_cruce,
            contexto=contexto,
            dias_hasta_faena_referencia=config["dias_hasta_faena"],
            tolerancia_cruce_dias=config["tolerancia_dias"],
        )

    total_pollitos = sum(s.pollitos_cargados for s in semanas_encontradas)
    tasas_mortalidad = config["tasas_mortalidad"]
    semanas_referenciadas = _serializar_semanas_referenciadas(
        semanas_encontradas,
        config["dias_hasta_faena"],
    )

    coberturas = []
    for tasa in tasas_mortalidad:
        disponibles = int(total_pollitos * (1 - tasa))
        cob_pct = round((total_oferta / disponibles * 100), 1) if disponibles > 0 else None
        coberturas.append({
            "tasa": round(tasa * 100, 1),
            "disponibles": disponibles,
            "cobertura_pct": cob_pct,
        })

    disponibles_mejor = coberturas[0]["disponibles"]   # 4.5%
    disponibles_peor = coberturas[-1]["disponibles"]    # peor escenario configurado
    deficit = max(0, total_oferta - disponibles_peor)
    cobertura = round((total_oferta / disponibles_peor * 100), 1) if disponibles_peor > 0 else None

    return FactibilidadProduccion(
        encontrada=True,
        pollitos_cargados=total_pollitos,
        disponibles_mejor=disponibles_mejor,
        disponibles_peor=disponibles_peor,
        total_oferta=total_oferta,
        deficit_peor=deficit if deficit > 0 else None,
        cobertura_pct_peor=cobertura,
        coberturas=coberturas,
        total_compra_terceros=total_compra_terceros,
        total_semanas_referenciadas=len(semanas_encontradas),
        metodo_cruce=metodo_cruce,
        contexto=contexto,
        dias_hasta_faena_referencia=config["dias_hasta_faena"],
        tolerancia_cruce_dias=config["tolerancia_dias"],
        semanas_referenciadas=semanas_referenciadas,
    )


def _calcular_factibilidad_proyeccion(proyeccion: SemanaFaena) -> Optional[FactibilidadProduccion]:
    """Calcula factibilidad usando las cohortes realmente planificadas."""
    contexto = _extraer_contexto_planificado_propio(proyeccion)
    total_propio = contexto["total_propio"]
    if total_propio <= 0:
        if not proyeccion.total_pollos_semana or proyeccion.total_pollos_semana <= 0:
            return None
        return _calcular_factibilidad(
            fecha_inicio_semana=proyeccion.fecha_inicio,
            total_oferta=proyeccion.total_pollos_semana,
            metodo_cruce="macro_faena",
            contexto="plan_propio",
        )

    fechas_ingreso = contexto["fechas_ingreso"]
    return _calcular_factibilidad(
        fecha_inicio_semana=proyeccion.fecha_inicio,
        total_oferta=total_propio,
        fechas_ingreso=fechas_ingreso or None,
        total_compra_terceros=contexto["total_compra_terceros"],
        metodo_cruce="cohortes_planificadas" if fechas_ingreso else "macro_faena",
        contexto="plan_propio",
    )


def _calcular_deficit_produccion(proyeccion: SemanaFaena) -> Optional[dict]:
    """Calcula déficit de producción propia vs oferta para la recomendación de terceros."""
    fact = _calcular_factibilidad_proyeccion(proyeccion)
    if fact is None or not fact.encontrada:
        return None

    hay_deficit = fact.deficit_peor is not None and fact.deficit_peor > 0
    sujeto = "el plan propio" if fact.contexto == "plan_propio" else "la oferta"
    return {
        "encontrada": True,
        "pollitos_cargados": fact.pollitos_cargados,
        "disponibles_peor": fact.disponibles_peor,
        "disponibles_mejor": fact.disponibles_mejor,
        "total_oferta": fact.total_oferta,
        "deficit_peor": fact.deficit_peor,
        "cobertura_pct_peor": fact.cobertura_pct_peor,
        "total_compra_terceros": fact.total_compra_terceros,
        "total_semanas_referenciadas": fact.total_semanas_referenciadas,
        "metodo_cruce": fact.metodo_cruce,
        "contexto": fact.contexto,
        "hay_deficit": hay_deficit,
        "recomendacion_terceros": (
            f"La producción propia ({fact.disponibles_peor:,} en el escenario conservador) "
            f"no cubre {sujeto} ({fact.total_oferta:,}). "
            f"Se recomienda adquirir ~{fact.deficit_peor:,} pollos a terceros."
        ) if hay_deficit else None,
    }


# ─── Helpers: validación cruzada en carga ─────────────────────────────────────

def _validar_cruce_oferta(ofertas: list[LoteOferta]) -> Optional[dict]:
    """Valida oferta contra producción existente al momento de la carga."""
    produccion_data = storage.load_produccion()
    if not produccion_data or not ofertas:
        return None

    params = _get_parametros()
    config = _get_produccion_reference_config(params)
    result: dict = {}

    # 1. Factibilidad: cobertura oferta vs producción (agregando todas las semanas)
    from collections import Counter
    fechas_peso = [o.fecha_peso for o in ofertas if o.fecha_peso]
    if fechas_peso:
        fecha_mas_comun = Counter(fechas_peso).most_common(1)[0][0]
        lunes = fecha_mas_comun - timedelta(days=fecha_mas_comun.weekday())
        total_oferta = sum(o.cantidad for o in ofertas)
        fact = _calcular_factibilidad(lunes, total_oferta, ofertas=ofertas)
        if fact:
            result["factibilidad"] = fact.model_dump()

    # 2. Concordancia producción-oferta por cohorte
    mortalidad = validar_mortalidad_oferta(
        ofertas,
        produccion_data,
        dias_hasta_faena=config["dias_hasta_faena"],
        tolerancia_dias=config["tolerancia_dias"],
        merma_min=params.produccion_mortalidad_min,
        merma_max=params.produccion_mortalidad_max,
    )
    if mortalidad and mortalidad.get("cohortes"):
        result["mortalidad_cohortes"] = mortalidad

    # 3. Consistencia de edad: edad_real vs (fecha_peso − fecha_ingreso)
    alertas_edad: list[dict] = []
    for i, o in enumerate(ofertas):
        if o.fecha_peso and o.fecha_ingreso and o.edad_real:
            dias_calculados = (o.fecha_peso - o.fecha_ingreso).days
            diferencia_abs = abs(dias_calculados - o.edad_real)
            if diferencia_abs > 3:
                alertas_edad.append({
                    "lote": i + 1,
                    "granja": o.granja,
                    "galpon": o.galpon,
                    "edad_real": o.edad_real,
                    "dias_calculados": dias_calculados,
                    "diferencia": dias_calculados - o.edad_real,
                })
    if alertas_edad:
        result["consistencia_edad"] = {
            "alertas": alertas_edad,
            "total": len(alertas_edad),
        }

    # 4. Concentración por granja
    from collections import defaultdict
    granjas_map: dict[str, dict] = defaultdict(lambda: {
        "aves": 0, "lotes": 0, "sum_edad": 0, "sum_peso": 0, "n_edad": 0, "n_peso": 0,
        "sexos": defaultdict(int), "nucleos": set(), "fechas_ingreso": set(),
    })
    total_aves = sum(o.cantidad for o in ofertas)
    for o in ofertas:
        g = granjas_map[o.granja]
        g["aves"] += o.cantidad
        g["lotes"] += 1
        if o.edad_real and o.edad_real > 0:
            g["sum_edad"] += o.edad_real * o.cantidad
            g["n_edad"] += o.cantidad
        if o.peso_muestreo_real and o.peso_muestreo_real > 0:
            g["sum_peso"] += o.peso_muestreo_real * o.cantidad
            g["n_peso"] += o.cantidad
        if o.sexo:
            g["sexos"][o.sexo] += o.cantidad
        if o.nucleo:
            g["nucleos"].add(o.nucleo)
        if o.fecha_ingreso:
            g["fechas_ingreso"].add(o.fecha_ingreso.isoformat())

    # Vincular granjas con cohortes de producción si existen
    cohortes_list = mortalidad.get("cohortes", []) if mortalidad else []
    granja_cohorte: dict[str, list[str]] = defaultdict(list)
    for coh in cohortes_list:
        for gname in (coh.get("granjas") or []):
            label = f"{coh.get('fecha_desde', '')} → {coh.get('fecha_hasta', '')}"
            if label not in granja_cohorte[gname]:
                granja_cohorte[gname].append(label)

    concentracion = []
    for nombre, g in sorted(granjas_map.items(), key=lambda x: x[1]["aves"], reverse=True):
        concentracion.append({
            "granja": nombre,
            "aves": g["aves"],
            "pct": round(g["aves"] / total_aves * 100, 1) if total_aves > 0 else 0,
            "lotes": g["lotes"],
            "edad_prom": round(g["sum_edad"] / g["n_edad"], 1) if g["n_edad"] > 0 else None,
            "peso_prom": round(g["sum_peso"] / g["n_peso"], 2) if g["n_peso"] > 0 else None,
            "sexo_predominante": max(g["sexos"], key=g["sexos"].get) if g["sexos"] else None,
            "nucleos": len(g["nucleos"]),
            "cohortes": granja_cohorte.get(nombre, []),
        })
    if concentracion:
        result["concentracion_granjas"] = {
            "granjas": concentracion,
            "total_granjas": len(concentracion),
            "total_aves": total_aves,
            "max_pct": concentracion[0]["pct"] if concentracion else 0,
        }

    return result if result else None


def _validar_cruce_produccion() -> Optional[dict]:
    """Valida producción recién cargada contra oferta existente."""
    ofertas = _get_ofertas()
    if not ofertas:
        return None
    produccion_data = storage.load_produccion()
    if not produccion_data:
        return None

    params = _get_parametros()
    config = _get_produccion_reference_config(params)
    result: dict = {}

    # 1. Factibilidad (agregando todas las semanas referenciadas)
    from collections import Counter
    fechas_peso = [o.fecha_peso for o in ofertas if o.fecha_peso]
    if fechas_peso:
        fecha_mas_comun = Counter(fechas_peso).most_common(1)[0][0]
        lunes = fecha_mas_comun - timedelta(days=fecha_mas_comun.weekday())
        total_oferta = sum(o.cantidad for o in ofertas)
        fact = _calcular_factibilidad(lunes, total_oferta, ofertas=ofertas)
        if fact:
            result["factibilidad"] = fact.model_dump()

    # 2. Concordancia producción-oferta por cohorte
    mortalidad = validar_mortalidad_oferta(
        ofertas,
        produccion_data,
        dias_hasta_faena=config["dias_hasta_faena"],
        tolerancia_dias=config["tolerancia_dias"],
        merma_min=params.produccion_mortalidad_min,
        merma_max=params.produccion_mortalidad_max,
    )
    if mortalidad and mortalidad.get("cohortes"):
        result["mortalidad_cohortes"] = mortalidad

    return result if result else None


# ─── Endpoints ──────────────────────────────────────────────────────────────────

@app.get("/")
def root():
    return {"message": "API Proyección de Faena Avícola", "version": "1.0.0"}


@app.post("/token", response_model=Token)
async def login_for_access_token(form_data: OAuth2PasswordRequestForm = Depends()):
    # Simple hardcoded check
    if form_data.username != ADMIN_USERNAME or not verify_password(form_data.password, ADMIN_PASSWORD_HASH):
        raise HTTPException(
            status_code=401,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    access_token_expires = timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = create_access_token(
        data={"sub": form_data.username}, expires_delta=access_token_expires
    )
    return {"access_token": access_token, "token_type": "bearer"}


@app.get("/parametros")
def get_parametros(current_user: TokenData = Depends(get_current_user)):
    """Obtener parámetros actuales."""
    return _get_parametros()


@app.put("/parametros")
def update_parametros(update: ParametrosUpdate, current_user: TokenData = Depends(get_current_user)):
    """Actualizar parámetros de cálculo y recalcular proyección si existe."""
    current = _get_parametros().model_dump()
    for key, value in update.model_dump(exclude_none=True).items():
        current[key] = value
    params = Parametros(**current)
    storage.save_parametros(params.model_dump())

    # Recalcular proyección existente con los nuevos parámetros
    proyeccion_recalculada = False
    proyeccion = _get_proyeccion()
    if proyeccion is not None:
        try:
            semana = _recalcular_proyeccion_actual(proyeccion, params)
            storage.save_proyeccion(semana.model_dump())
            proyeccion_recalculada = True
        except Exception as e:
            logger.warning(f"Error recalculando proyección tras cambio de parámetros: {e}")

    result = params.model_dump()
    result["proyeccion_recalculada"] = proyeccion_recalculada
    return result


@app.post("/oferta/upload")
async def upload_oferta(file: UploadFile = File(...), sheet_name: Optional[str] = None, current_user: TokenData = Depends(get_current_user)):
    """
    Subir archivo Excel de oferta de granjas.
    Acepta formato OFERTA JUEV o similar.
    """
    if not file.filename or not file.filename.endswith(('.xlsx', '.xls')):
        raise HTTPException(400, "El archivo debe ser .xlsx o .xls")

    content = await file.read()
    try:
        ofertas, filas_descartadas, resumen_filas = leer_oferta_excel(content, sheet_name)
    except Exception as e:
        raise HTTPException(400, f"Error al leer el archivo: {str(e)}")

    # Backup automático antes de sobrescribir
    backup_key = storage.backup_ofertas()

    # Persistir ofertas y archivo original
    storage.save_ofertas([o.model_dump() for o in ofertas])
    upload_key = storage.save_upload(file.filename, content)
    storage.save_oferta_metadata({
        "filename": file.filename,
        "uploaded_at": datetime.now().isoformat(),
        "upload_key": upload_key,
        "backup_key": backup_key,
        "sheet_name": sheet_name,
        "total_lotes": len(ofertas),
        "total_pollos": sum(o.cantidad for o in ofertas),
        "fecha_peso_desde": min((o.fecha_peso for o in ofertas if o.fecha_peso), default=None),
        "fecha_peso_hasta": max((o.fecha_peso for o in ofertas if o.fecha_peso), default=None),
        "fecha_ingreso_desde": min((o.fecha_ingreso for o in ofertas if o.fecha_ingreso), default=None),
        "fecha_ingreso_hasta": max((o.fecha_ingreso for o in ofertas if o.fecha_ingreso), default=None),
        "total_descartadas": len(filas_descartadas),
    })

    # Guardar auditoría persistente de la carga
    pollos_descartados = sum(d.get("cantidad", 0) for d in filas_descartadas)
    storage.save_oferta_audit({
        "timestamp": datetime.now().isoformat(),
        "archivo": file.filename,
        "tipo": "jueves",
        "backup_key": backup_key,
        "resumen_filas": resumen_filas,
        "total_lotes_parseados": len(ofertas),
        "total_pollos_parseados": sum(o.cantidad for o in ofertas),
        "total_descartadas": len(filas_descartadas),
        "pollos_descartados": pollos_descartados,
        "filas_descartadas": filas_descartadas,
    })

    # Resumen por granja
    resumen = {}
    for o in ofertas:
        if o.granja not in resumen:
            resumen[o.granja] = {"lotes": 0, "pollos": 0}
        resumen[o.granja]["lotes"] += 1
        resumen[o.granja]["pollos"] += o.cantidad

    resultado = {
        "total_lotes": len(ofertas),
        "total_pollos": sum(o.cantidad for o in ofertas),
        "granjas": resumen,
        "ofertas": [o.model_dump() for o in ofertas],
        "resumen_filas": resumen_filas,
    }
    if backup_key:
        resultado["backup_key"] = backup_key
    if filas_descartadas:
        resultado["filas_descartadas"] = filas_descartadas
        resultado["total_descartadas"] = len(filas_descartadas)
        resultado["pollos_descartados"] = pollos_descartados

    # Validación cruzada contra producción (si existe)
    try:
        validacion = _validar_cruce_oferta(ofertas)
        if validacion:
            resultado["validacion_cruzada"] = validacion
    except Exception as e:
        logger.warning(f"Error en validación cruzada oferta: {e}")

    return resultado


@app.get("/oferta/audit")
def get_oferta_audit(current_user: TokenData = Depends(get_current_user)):
    """Retorna el registro de auditoría de la última carga de oferta,
    incluyendo filas descartadas, resumen de filas y backup."""
    audit = storage.load_oferta_audit()
    if not audit:
        raise HTTPException(404, "No hay registro de auditoría. Cargue una oferta primero.")
    return audit


@app.get("/oferta")
def get_oferta(current_user: TokenData = Depends(get_current_user)):
    """Obtener oferta cargada."""
    ofertas = _get_ofertas()
    # Agrupar por granja para el resumen del frontend
    granjas: dict[str, dict] = {}
    for o in ofertas:
        if o.granja not in granjas:
            granjas[o.granja] = {"lotes": 0, "pollos": 0}
        granjas[o.granja]["lotes"] += 1
        granjas[o.granja]["pollos"] += o.cantidad
    return {
        "total_lotes": len(ofertas),
        "total_pollos": sum(o.cantidad for o in ofertas),
        "granjas": granjas,
        "ofertas": [o.model_dump() for o in ofertas],
    }


@app.get("/oferta/trazabilidad")
def get_oferta_trazabilidad(current_user: TokenData = Depends(get_current_user)):
    """Retorna la oferta del jueves anotada con su estado dentro de la planificación actual."""
    ofertas = _get_ofertas()
    if not ofertas:
        raise HTTPException(404, "No hay oferta cargada.")
    return _build_oferta_trace()


@app.delete("/oferta")
def clear_oferta(current_user: TokenData = Depends(get_current_user)):
    """Limpiar la oferta cargada."""
    storage.delete_ofertas()
    storage.delete_oferta_metadata()
    storage.delete_ofertas_martes()
    storage.delete_proyeccion()
    storage.delete_oferta_audit()
    return {"message": "Oferta limpiada"}


@app.post("/oferta/ajuste-martes")
async def upload_ajuste_martes(
    file: UploadFile = File(...),
    sheet_name: Optional[str] = None,
    current_user: TokenData = Depends(get_current_user),
):
    """
    Subir oferta del martes para ajustar la proyección existente.
    Matchea lotes por (granja, galpon, nucleo, sexo, fecha_ingreso),
    actualiza datos y recalcula preservando las asignaciones de día.
    """
    if not file.filename or not file.filename.endswith(('.xlsx', '.xls')):
        raise HTTPException(400, "El archivo debe ser .xlsx o .xls")

    # Verificar que existe una proyección para ajustar
    semana = _get_proyeccion()
    if semana is None:
        raise HTTPException(400, "No hay proyección existente para ajustar. Genere una primero desde la pestaña Oferta.")

    content = await file.read()
    try:
        ofertas_martes, filas_descartadas_martes, resumen_filas_martes = leer_oferta_excel(content, sheet_name)
    except Exception as e:
        raise HTTPException(400, f"Error al leer el archivo: {str(e)}")

    if not ofertas_martes:
        raise HTTPException(400, "El archivo no contiene lotes válidos.")

    # Log de descartadas del martes
    if filas_descartadas_martes:
        pollos_desc = sum(d.get("cantidad", 0) for d in filas_descartadas_martes)
        logger.warning(
            f"Ajuste martes: {len(filas_descartadas_martes)} lotes descartados "
            f"({pollos_desc} aves) del archivo {file.filename}"
        )

    # Guardar oferta martes y archivo original
    storage.save_ofertas_martes([o.model_dump() for o in ofertas_martes])
    storage.save_upload(file.filename, content)

    # Aplicar ajuste
    params = _get_parametros()
    resultado, resumen = aplicar_ajuste_martes(
        ofertas_martes,
        semana,
        params,
        ofertas_referencia=_get_ofertas(),
    )

    # Guardar proyección actualizada
    storage.save_proyeccion(resultado.model_dump())

    resp = {
        "proyeccion": resultado.model_dump(),
        "resumen_ajuste": resumen.model_dump(),
        "resumen_filas": resumen_filas_martes,
    }
    if filas_descartadas_martes:
        resp["filas_descartadas"] = filas_descartadas_martes
        resp["total_descartadas"] = len(filas_descartadas_martes)
        resp["pollos_descartados"] = sum(d.get("cantidad", 0) for d in filas_descartadas_martes)
    return resp


@app.post("/proyeccion/generar")
def generar_proyeccion_endpoint(req: ProyeccionRequest, current_user: TokenData = Depends(get_current_user)):
    """
    Genera la proyección de faena automática.
    Toma la oferta cargada y la distribuye en los días de la semana.
    Si hay feriados (nacionales o custom), salta esos días.
    """
    ofertas = _get_ofertas()
    if not ofertas:
        raise HTTPException(400, "No hay oferta cargada. Suba un archivo primero.")

    # Inyectar lotes del déficit de la semana anterior si corresponde
    if req.incluir_deficit:
        deficit_data = storage.load_deficit()
        if deficit_data and deficit_data.get("ofertas_originales"):
            ofertas_deficit = []
            for od in deficit_data["ofertas_originales"]:
                try:
                    ofertas_deficit.append(LoteOferta(**od))
                except Exception as e:
                    logger.warning(f"Error reconstruyendo oferta de déficit: {e}")
            if ofertas_deficit:
                logger.info(
                    f"Incluyendo {len(ofertas_deficit)} lotes del déficit "
                    f"de semana {deficit_data.get('semana_origen', '?')}"
                )
                ofertas = ofertas + ofertas_deficit

    params = req.parametros or _get_parametros()

    # Construir lista de feriados custom (de request + guardados)
    feriados_custom_list = []
    saved_custom = storage.load_feriados_custom() or []
    feriados_custom_list.extend(saved_custom)
    if req.feriados_custom:
        for fc in req.feriados_custom:
            feriados_custom_list.append({"fecha": fc.isoformat(), "descripcion": "Feriado personalizado"})

    # Obtener feriados del rango de la semana (L-S inclusive)
    fecha_fin = req.fecha_inicio_semana + timedelta(days=5)  # lunes a sábado
    feriados = obtener_feriados_rango(
        req.fecha_inicio_semana, fecha_fin,
        feriados_custom=feriados_custom_list if feriados_custom_list else None,
    )

    # Determinar días de faena: si habilitó sábado, forzar 6 días
    dias_faena = req.dias_faena
    if req.habilitar_sabado and dias_faena < 6:
        dias_faena = 6

    semana = generar_proyeccion(
        ofertas=ofertas,
        fecha_inicio_semana=req.fecha_inicio_semana,
        dias_faena=dias_faena,
        pollos_por_dia=req.pollos_por_dia,
        params=params,
        feriados=feriados if feriados else None,
        gallinas=req.gallinas,
        criterio_gerente=req.criterio_gerente,
        permitir_fraccionamiento_lotes=req.permitir_fraccionamiento_lotes,
        excluir_backlog_semana_previa=req.excluir_backlog_semana_previa,
        minimos_como_alerta=req.minimos_como_alerta,
    )

    # Generar planificación alternativa con el otro modo
    try:
        semana_alt = generar_proyeccion(
            ofertas=ofertas,
            fecha_inicio_semana=req.fecha_inicio_semana,
            dias_faena=dias_faena,
            pollos_por_dia=req.pollos_por_dia,
            params=params,
            feriados=feriados if feriados else None,
            gallinas=req.gallinas,
            criterio_gerente=not req.criterio_gerente,
            permitir_fraccionamiento_lotes=req.permitir_fraccionamiento_lotes if not req.criterio_gerente else None,
            excluir_backlog_semana_previa=req.excluir_backlog_semana_previa if not req.criterio_gerente else None,
            minimos_como_alerta=req.minimos_como_alerta if not req.criterio_gerente else None,
        )
        alternativa_dict = semana_alt.model_dump()
    except Exception as e:
        logger.warning(f"No se pudo generar planificación alternativa: {e}")
        alternativa_dict = None

    # Etiquetas profesionales para los modos de planificación
    modo_principal = "cascada_madurez" if req.criterio_gerente else "optimizacion_restricciones"
    modo_alternativo = "optimizacion_restricciones" if req.criterio_gerente else "cascada_madurez"

    # Persistir proyección y parámetros usados
    proyeccion_principal = semana.model_dump()
    proyeccion_principal["modo_planificacion"] = modo_principal
    storage.save_proyeccion(proyeccion_principal)
    if alternativa_dict:
        alternativa_dict["modo_planificacion"] = modo_alternativo
        storage.save_proyeccion_alternativa(alternativa_dict)
    else:
        storage.delete_proyeccion_alternativa()
    storage.save_parametros(params.model_dump())

    # Guardar configuración de generación para poder recalcular al cambiar parámetros
    storage.save_proyeccion_config({
        "fecha_inicio_semana": req.fecha_inicio_semana.isoformat(),
        "dias_faena": dias_faena,
        "pollos_por_dia": req.pollos_por_dia,
        "habilitar_sabado": req.habilitar_sabado,
        "incluir_deficit": req.incluir_deficit,
        "criterio_gerente": req.criterio_gerente,
        "permitir_fraccionamiento_lotes": req.permitir_fraccionamiento_lotes,
        "excluir_backlog_semana_previa": req.excluir_backlog_semana_previa,
        "minimos_como_alerta": req.minimos_como_alerta,
        "gallinas": req.gallinas,
        "feriados_custom": [f.isoformat() for f in req.feriados_custom] if req.feriados_custom else None,
    })

    # ── Factibilidad: cruzar plan propio vs producción propia ──
    factibilidad = _calcular_factibilidad_proyeccion(semana)

    result = semana.model_dump()
    result["factibilidad_produccion"] = factibilidad.model_dump() if factibilidad else None
    result["modo_planificacion"] = modo_principal
    if alternativa_dict:
        result["planificacion_alternativa"] = alternativa_dict
    return result


@app.get("/proyeccion")
def get_proyeccion(current_user: TokenData = Depends(get_current_user)):
    """Obtener la proyección actual."""
    proyeccion = _get_proyeccion()
    if proyeccion is None:
        raise HTTPException(404, "No hay proyección generada aún.")
    result = proyeccion.model_dump()
    factibilidad = _calcular_factibilidad_proyeccion(proyeccion)
    result["factibilidad_produccion"] = factibilidad.model_dump() if factibilidad else None
    result["modo_planificacion"] = result.get("modo_planificacion") or _get_modo_planificacion_actual()
    alternativa = storage.load_proyeccion_alternativa()
    if alternativa:
        result["planificacion_alternativa"] = alternativa
    return result


@app.post("/proyeccion/activar")
def activar_proyeccion(data: dict, current_user: TokenData = Depends(get_current_user)):
    """Reemplaza la proyección activa con los datos proporcionados (swap de modo)."""
    payload = dict(data or {})
    proyeccion_data = payload.get("proyeccion") or payload
    if not isinstance(proyeccion_data, dict):
        raise HTTPException(400, "Datos de proyección inválidos")

    proyeccion_data = dict(proyeccion_data)
    alternativa = payload.get("planificacion_alternativa")
    if alternativa is None and "planificacion_alternativa" in proyeccion_data:
        alternativa = proyeccion_data.pop("planificacion_alternativa")

    if "dias" not in proyeccion_data:
        raise HTTPException(400, "Datos de proyección inválidos")

    storage.save_proyeccion(proyeccion_data)
    if alternativa and isinstance(alternativa, dict) and alternativa.get("dias"):
        storage.save_proyeccion_alternativa(alternativa)
    elif "planificacion_alternativa" in payload:
        storage.delete_proyeccion_alternativa()
    return {"ok": True}


@app.post("/proyeccion/mover-lote")
def mover_lote(asignacion: AsignacionManual, current_user: TokenData = Depends(get_current_user)):
    """Mover un lote de un día a otro manualmente."""
    semana = _get_proyeccion()
    if semana is None:
        raise HTTPException(404, "No hay proyección generada aún.")

    if asignacion.dia_origen < 0 or asignacion.dia_origen >= len(semana.dias) \
       or asignacion.dia_destino < 0 or asignacion.dia_destino >= len(semana.dias):
        raise HTTPException(400, "Índice de día inválido")

    dia_origen = semana.dias[asignacion.dia_origen]
    dia_destino = semana.dias[asignacion.dia_destino]

    if asignacion.lote_index < 0 or asignacion.lote_index >= len(dia_origen.lotes):
        raise HTTPException(400, "Índice de lote inválido")

    # Extraer el lote
    lote = dia_origen.lotes.pop(asignacion.lote_index)

    # Recalcular con la nueva fecha
    params = _get_parametros()
    nueva_fecha = dia_destino.fecha

    # Usar datos originales de la oferta si están disponibles (preservados
    # desde calcular_lote_proyectado). Si no existen (proyecciones antiguas),
    # caemos al fallback anterior para compatibilidad.
    fecha_peso = lote.fecha_peso_original or lote.fecha_fin_retiro
    ganancia = lote.ganancia_diaria_original if lote.ganancia_diaria_original is not None else params.ganancia_diaria_macho
    fecha_ingreso = lote.fecha_ingreso_original or fecha_peso

    oferta_equiv = LoteOferta(
        fecha_peso=fecha_peso,
        granja=lote.granja,
        galpon=lote.galpon,
        nucleo=lote.nucleo,
        cantidad=lote.cantidad,
        sexo=lote.sexo,
        edad_proyectada=lote.edad_actual,
        peso_muestreo_proy=lote.peso_actual,
        ganancia_diaria=ganancia,
        dias_proyectados=0,
        edad_real=lote.edad_actual,
        peso_muestreo_real=lote.peso_actual,
        fecha_ingreso=fecha_ingreso,
    )

    nuevo_lote = _copiar_metadata_lote(
        lote,
        calcular_lote_proyectado(oferta_equiv, nueva_fecha, params),
    )
    dia_destino.lotes.append(nuevo_lote)

    # Recalcular agregados de ambos días
    semana.dias[asignacion.dia_origen] = calcular_dia_faena(
        dia_origen.fecha, dia_origen.lotes, params=params,
        gallinas_cantidad=dia_origen.gallinas_cantidad,
        gallinas_livianas=dia_origen.gallinas_livianas_cantidad,
        gallinas_pesadas=dia_origen.gallinas_pesadas_cantidad,
    )
    semana.dias[asignacion.dia_destino] = calcular_dia_faena(
        dia_destino.fecha, dia_destino.lotes, params=params,
        gallinas_cantidad=dia_destino.gallinas_cantidad,
        gallinas_livianas=dia_destino.gallinas_livianas_cantidad,
        gallinas_pesadas=dia_destino.gallinas_pesadas_cantidad,
    )

    # Recalcular semana (preservar lotes no asignados y fuera de rango)
    resultado = calcular_semana_faena(
        semana.fecha_inicio, semana.dias, params,
        lotes_no_asignados=semana.lotes_no_asignados,
        lotes_fuera_rango=semana.lotes_fuera_rango,
    )
    storage.save_proyeccion(resultado.model_dump())

    return resultado.model_dump()


@app.post("/proyeccion/redistribuir-dia")
def redistribuir_dia(
    req: RedistribuirDiaRequest,
    current_user: TokenData = Depends(get_current_user),
):
    """
    Redistribuye todos los lotes de un día hacia los días restantes.
    Usa la misma lógica de asignación por déficit que generar_proyeccion.
    El día de origen queda con 0 lotes asignados.
    Los lotes que no puedan redistribuirse se agregan a lotes_no_asignados.
    """
    semana = _get_proyeccion()
    if semana is None:
        raise HTTPException(404, "No hay proyección generada.")

    if req.dia_index < 0 or req.dia_index >= len(semana.dias):
        raise HTTPException(400, "Índice de día inválido.")

    params = _get_parametros()
    dia_origen = semana.dias[req.dia_index]

    if not dia_origen.lotes:
        raise HTTPException(400, "El día no tiene lotes para redistribuir.")

    # Extraer todos los lotes del día origen
    lotes_a_redistribuir = dia_origen.lotes[:]

    # Vaciar el día origen (preservar gallinas y fecha)
    semana.dias[req.dia_index] = calcular_dia_faena(
        dia_origen.fecha, [], params=params,
        gallinas_cantidad=dia_origen.gallinas_cantidad,
        gallinas_livianas=dia_origen.gallinas_livianas_cantidad,
        gallinas_pesadas=dia_origen.gallinas_pesadas_cantidad,
    )

    # Rastrear pollos actuales por día (excluyendo el día origen)
    pollos_dia: dict[int, int] = {
        d_idx: semana.dias[d_idx].total_pollos
        for d_idx in range(len(semana.dias))
    }

    lotes_na_nuevos: list[LoteNoAsignado] = []

    for lote in lotes_a_redistribuir:
        # Reconstruir LoteOferta desde los campos _original (patrón de mover-lote)
        fecha_peso = lote.fecha_peso_original or lote.fecha_fin_retiro
        ganancia = (
            lote.ganancia_diaria_original
            if lote.ganancia_diaria_original is not None
            else params.ganancia_diaria_macho
        )
        fecha_ingreso = lote.fecha_ingreso_original or fecha_peso

        oferta_equiv = LoteOferta(
            fecha_peso=fecha_peso,
            granja=lote.granja,
            galpon=lote.galpon,
            nucleo=lote.nucleo,
            cantidad=lote.cantidad,
            sexo=lote.sexo,
            edad_proyectada=lote.edad_actual,
            peso_muestreo_proy=lote.peso_actual,
            ganancia_diaria=ganancia,
            dias_proyectados=0,
            edad_real=lote.edad_actual,
            peso_muestreo_real=lote.peso_actual,
            fecha_ingreso=fecha_ingreso,
        )

        # Evaluar días elegibles (todos menos el origen)
        candidatos: list[tuple[int, int, int]] = []  # (dia_idx, deficit, weekday)
        for d_idx, dia in enumerate(semana.dias):
            if d_idx == req.dia_index:
                continue
            if evaluar_elegibilidad_lote(oferta_equiv, dia.fecha, params) is None:
                continue
            es_sabado = dia.fecha.weekday() == 5
            cap_max = params.limite_sabado if es_sabado else params.capacidad_maxima_planta
            if cap_max - pollos_dia[d_idx] < lote.cantidad:
                continue
            objetivo = params.limite_sabado if es_sabado else params.pollos_diarios_objetivo_max
            deficit = objetivo - pollos_dia[d_idx]
            candidatos.append((d_idx, deficit, dia.fecha.weekday()))

        if not candidatos:
            lotes_na_nuevos.append(LoteNoAsignado(
                granja=lote.granja,
                galpon=lote.galpon,
                nucleo=lote.nucleo,
                cantidad=lote.cantidad,
                sexo=lote.sexo,
                fecha_ingreso=fecha_ingreso,
                dias_elegibles=[],
                motivo="No redistribuible: sin capacidad en días restantes",
            ))
            continue

        # Mejor día: mayor déficit, desempate por día más temprano
        candidatos.sort(key=lambda x: (-x[1], x[2]))
        mejor_idx = candidatos[0][0]

        nuevo_lote = _copiar_metadata_lote(
            lote,
            calcular_lote_proyectado(oferta_equiv, semana.dias[mejor_idx].fecha, params),
        )
        semana.dias[mejor_idx].lotes.append(nuevo_lote)

        dia_dest = semana.dias[mejor_idx]
        semana.dias[mejor_idx] = calcular_dia_faena(
            dia_dest.fecha, dia_dest.lotes, params=params,
            gallinas_cantidad=dia_dest.gallinas_cantidad,
            gallinas_livianas=dia_dest.gallinas_livianas_cantidad,
            gallinas_pesadas=dia_dest.gallinas_pesadas_cantidad,
        )
        pollos_dia[mejor_idx] = semana.dias[mejor_idx].total_pollos

    # Combinar lotes_no_asignados existentes con los nuevos
    lotes_na_combinados = list(semana.lotes_no_asignados) + lotes_na_nuevos

    resultado = calcular_semana_faena(
        semana.fecha_inicio, semana.dias, params,
        lotes_no_asignados=lotes_na_combinados,
        lotes_fuera_rango=semana.lotes_fuera_rango,
    )
    resultado.feriados_aplicados = semana.feriados_aplicados
    resultado.eventos_gallinas = semana.eventos_gallinas
    storage.save_proyeccion(resultado.model_dump())
    return resultado.model_dump()


@app.post("/proyeccion/agregar-lote")
def agregar_lote(lote_req: LoteManualRequest, current_user: TokenData = Depends(get_current_user)):
    """Agregar un lote manualmente a un día de faena."""
    semana = _get_proyeccion()
    if semana is None:
        raise HTTPException(404, "No hay proyección generada aún.")

    if lote_req.dia_faena < 0 or lote_req.dia_faena >= len(semana.dias):
        raise HTTPException(400, "Índice de día inválido")

    params = _get_parametros()
    fecha_dia = semana.dias[lote_req.dia_faena].fecha

    oferta = LoteOferta(
        fecha_peso=lote_req.fecha_peso,
        granja=lote_req.granja,
        galpon=lote_req.galpon,
        nucleo=lote_req.nucleo,
        cantidad=lote_req.cantidad,
        sexo=lote_req.sexo,
        edad_proyectada=lote_req.edad_proyectada,
        peso_muestreo_proy=lote_req.peso_muestreo_proy,
        ganancia_diaria=lote_req.ganancia_diaria,
        dias_proyectados=0,
        edad_real=lote_req.edad_proyectada,
        peso_muestreo_real=lote_req.peso_muestreo_proy,
        fecha_ingreso=lote_req.fecha_ingreso,
    )

    lote = calcular_lote_proyectado(oferta, fecha_dia, params)

    # Marcar como compra a terceros si aplica
    if lote_req.es_compra_terceros:
        lote.es_compra_terceros = True
        lote.motivo_compra = lote_req.motivo_compra

    semana.dias[lote_req.dia_faena].lotes.append(lote)

    # Recalcular el día
    dia = semana.dias[lote_req.dia_faena]
    semana.dias[lote_req.dia_faena] = calcular_dia_faena(
        dia.fecha, dia.lotes, params=params,
        gallinas_cantidad=dia.gallinas_cantidad,
        gallinas_livianas=dia.gallinas_livianas_cantidad,
        gallinas_pesadas=dia.gallinas_pesadas_cantidad,
    )

    # Recalcular semana (preservar lotes no asignados y fuera de rango)
    resultado = calcular_semana_faena(
        semana.fecha_inicio, semana.dias, params,
        lotes_no_asignados=semana.lotes_no_asignados,
        lotes_fuera_rango=semana.lotes_fuera_rango,
    )
    storage.save_proyeccion(resultado.model_dump())

    return resultado.model_dump()


@app.delete("/proyeccion/lote/{dia_index}/{lote_index}")
def eliminar_lote(dia_index: int, lote_index: int, current_user: TokenData = Depends(get_current_user)):
    """Eliminar un lote de un día de faena."""
    semana = _get_proyeccion()
    if semana is None:
        raise HTTPException(404, "No hay proyección generada aún.")

    if dia_index < 0 or dia_index >= len(semana.dias):
        raise HTTPException(400, "Índice de día inválido")

    dia = semana.dias[dia_index]
    if lote_index < 0 or lote_index >= len(dia.lotes):
        raise HTTPException(400, "Índice de lote inválido")

    dia.lotes.pop(lote_index)

    # Recalcular (preservar lotes no asignados y fuera de rango)
    params = _get_parametros()
    semana.dias[dia_index] = calcular_dia_faena(
        dia.fecha, dia.lotes, params=params,
        gallinas_cantidad=dia.gallinas_cantidad,
        gallinas_livianas=dia.gallinas_livianas_cantidad,
        gallinas_pesadas=dia.gallinas_pesadas_cantidad,
    )
    resultado = calcular_semana_faena(
        semana.fecha_inicio, semana.dias, params,
        lotes_no_asignados=semana.lotes_no_asignados,
        lotes_fuera_rango=semana.lotes_fuera_rango,
    )
    storage.save_proyeccion(resultado.model_dump())

    return resultado.model_dump()


# ─── Exclusión / inclusión de lotes ─────────────────────────────────────────────

class ExcluirLoteRequest(BaseModel):
    motivo: str = ""


@app.patch("/proyeccion/lote/{dia_index}/{lote_index}/excluir")
def excluir_lote(dia_index: int, lote_index: int, req: ExcluirLoteRequest, current_user: TokenData = Depends(get_current_user)):
    """Marcar o desmarcar un lote como excluido (tachado)."""
    semana = _get_proyeccion()
    if semana is None:
        raise HTTPException(404, "No hay proyección generada aún.")

    if dia_index < 0 or dia_index >= len(semana.dias):
        raise HTTPException(400, "Índice de día inválido")

    dia = semana.dias[dia_index]
    if lote_index < 0 or lote_index >= len(dia.lotes):
        raise HTTPException(400, "Índice de lote inválido")

    lote = dia.lotes[lote_index]
    # Toggle: si ya estaba excluido, lo restaura
    lote.excluido = not lote.excluido
    lote.motivo_exclusion = req.motivo if lote.excluido else None

    # Recalcular día y semana (los excluidos no computan)
    params = _get_parametros()
    semana.dias[dia_index] = calcular_dia_faena(
        dia.fecha, dia.lotes, params=params,
        gallinas_cantidad=dia.gallinas_cantidad,
        gallinas_livianas=dia.gallinas_livianas_cantidad,
        gallinas_pesadas=dia.gallinas_pesadas_cantidad,
    )
    resultado = calcular_semana_faena(
        semana.fecha_inicio, semana.dias, params,
        lotes_no_asignados=semana.lotes_no_asignados,
        lotes_fuera_rango=semana.lotes_fuera_rango,
    )
    storage.save_proyeccion(resultado.model_dump())

    return resultado.model_dump()


@app.get("/proyeccion/lotes-disponibles")
def lotes_disponibles(current_user: TokenData = Depends(get_current_user)):
    """Pool de lotes disponibles para incluir: no asignados + excluidos."""
    semana = _get_proyeccion()
    if semana is None:
        raise HTTPException(404, "No hay proyección generada aún.")

    disponibles = []

    # Lotes excluidos (tachados) — incluir día de origen
    for dia_idx, dia in enumerate(semana.dias):
        for lote_idx, lote in enumerate(dia.lotes):
            if lote.excluido:
                disponibles.append({
                    "origen": "excluido",
                    "dia_index": dia_idx,
                    "lote_index": lote_idx,
                    "fecha_dia": dia.fecha.isoformat(),
                    "granja": lote.granja,
                    "galpon": lote.galpon,
                    "nucleo": lote.nucleo,
                    "cantidad": lote.cantidad,
                    "sexo": lote.sexo,
                    "edad_fin_retiro": lote.edad_fin_retiro,
                    "peso_vivo_retiro": lote.peso_vivo_retiro,
                    "motivo_exclusion": lote.motivo_exclusion,
                })

    # Lotes no asignados por capacidad
    for idx, lote in enumerate(semana.lotes_no_asignados or []):
        disponibles.append({
            "origen": "no_asignado",
            "pool_index": idx,
            "granja": lote.granja,
            "galpon": lote.galpon,
            "nucleo": lote.nucleo,
            "cantidad": lote.cantidad,
            "sexo": lote.sexo,
            "dias_elegibles": [d.isoformat() for d in lote.dias_elegibles],
            "motivo": lote.motivo,
        })

    return {"disponibles": disponibles, "total": len(disponibles)}


class IncluirLoteDisponibleRequest(BaseModel):
    origen: str  # "excluido" | "no_asignado"
    dia_index: Optional[int] = None     # para excluidos: día donde está
    lote_index: Optional[int] = None    # para excluidos: índice del lote
    pool_index: Optional[int] = None    # para no_asignados: índice en el pool
    dia_destino: int                     # día al que se quiere incorporar


@app.post("/proyeccion/incluir-lote-disponible")
def incluir_lote_disponible(req: IncluirLoteDisponibleRequest, current_user: TokenData = Depends(get_current_user)):
    """Incluir un lote del pool de disponibles en un día de faena."""
    semana = _get_proyeccion()
    if semana is None:
        raise HTTPException(404, "No hay proyección generada aún.")

    if req.dia_destino < 0 or req.dia_destino >= len(semana.dias):
        raise HTTPException(400, "Índice de día destino inválido")

    params = _get_parametros()

    if req.origen == "excluido":
        if req.dia_index is None or req.lote_index is None:
            raise HTTPException(400, "Se requiere dia_index y lote_index para lotes excluidos")
        if req.dia_index < 0 or req.dia_index >= len(semana.dias):
            raise HTTPException(400, "Índice de día origen inválido")
        dia_origen = semana.dias[req.dia_index]
        if req.lote_index < 0 or req.lote_index >= len(dia_origen.lotes):
            raise HTTPException(400, "Índice de lote inválido")

        lote = dia_origen.lotes[req.lote_index]
        if not lote.excluido:
            raise HTTPException(400, "El lote no está excluido")

        # Si se mueve a otro día, quitarlo del día origen y recalcular en el destino
        if req.dia_index == req.dia_destino:
            lote.excluido = False
            lote.motivo_exclusion = None
        else:
            # Sacar del día origen
            dia_origen.lotes.pop(req.lote_index)
            # Recalcular en el día destino con la nueva fecha
            fecha_destino = semana.dias[req.dia_destino].fecha
            oferta = LoteOferta(
                fecha_peso=lote.fecha_peso_original or fecha_destino,
                granja=lote.granja,
                galpon=lote.galpon,
                nucleo=lote.nucleo,
                cantidad=lote.cantidad,
                sexo=lote.sexo,
                edad_proyectada=lote.edad_actual,
                peso_muestreo_proy=lote.peso_actual,
                ganancia_diaria=lote.ganancia_diaria_original or 0.09,
                dias_proyectados=lote.dias_proyectados_original,
                edad_real=lote.edad_actual,
                peso_muestreo_real=lote.peso_actual,
                fecha_ingreso=lote.fecha_ingreso_original or fecha_destino,
            )
            nuevo_lote = _copiar_metadata_lote(
                lote,
                calcular_lote_proyectado(oferta, fecha_destino, params),
            )
            semana.dias[req.dia_destino].lotes.append(nuevo_lote)

            # Recalcular el día origen
            semana.dias[req.dia_index] = calcular_dia_faena(
                dia_origen.fecha, dia_origen.lotes, params=params,
                gallinas_cantidad=dia_origen.gallinas_cantidad,
                gallinas_livianas=dia_origen.gallinas_livianas_cantidad,
                gallinas_pesadas=dia_origen.gallinas_pesadas_cantidad,
            )

    elif req.origen == "no_asignado":
        if req.pool_index is None:
            raise HTTPException(400, "Se requiere pool_index para lotes no asignados")
        no_asignados = semana.lotes_no_asignados or []
        if req.pool_index < 0 or req.pool_index >= len(no_asignados):
            raise HTTPException(400, "Índice de lote no asignado inválido")

        lote_na = no_asignados[req.pool_index]
        fecha_destino = semana.dias[req.dia_destino].fecha

        # Buscar en la oferta original o reconstruir desde datos disponibles
        oferta = LoteOferta(
            fecha_peso=lote_na.fecha_ingreso or fecha_destino,
            granja=lote_na.granja,
            galpon=lote_na.galpon,
            nucleo=lote_na.nucleo,
            cantidad=lote_na.cantidad,
            sexo=lote_na.sexo,
            edad_proyectada=0,
            peso_muestreo_proy=0.0,
            ganancia_diaria=params.ganancia_diaria_macho if lote_na.sexo == 'M' else params.ganancia_diaria_hembra,
            dias_proyectados=0,
            edad_real=0,
            peso_muestreo_real=0.0,
            fecha_ingreso=lote_na.fecha_ingreso or fecha_destino,
        )

        # Intentar recuperar datos completos de la oferta guardada
        ofertas_cargadas = storage.load_ofertas()
        for of in ofertas_cargadas:
            if of.get("granja") == lote_na.granja and of.get("galpon") == lote_na.galpon and of.get("nucleo") == lote_na.nucleo:
                oferta = LoteOferta(**of)
                break

        nuevo_lote = calcular_lote_proyectado(oferta, fecha_destino, params)
        semana.dias[req.dia_destino].lotes.append(nuevo_lote)

        # Quitar del pool de no asignados
        no_asignados.pop(req.pool_index)
        semana.lotes_no_asignados = no_asignados
        semana.total_pollos_no_asignados = sum(l.cantidad for l in no_asignados)

    else:
        raise HTTPException(400, f"Origen inválido: {req.origen}")

    # Recalcular día destino
    dia_dest = semana.dias[req.dia_destino]
    semana.dias[req.dia_destino] = calcular_dia_faena(
        dia_dest.fecha, dia_dest.lotes, params=params,
        gallinas_cantidad=dia_dest.gallinas_cantidad,
        gallinas_livianas=dia_dest.gallinas_livianas_cantidad,
        gallinas_pesadas=dia_dest.gallinas_pesadas_cantidad,
    )

    # Recalcular semana
    resultado = calcular_semana_faena(
        semana.fecha_inicio, semana.dias, params,
        lotes_no_asignados=semana.lotes_no_asignados,
        lotes_fuera_rango=semana.lotes_fuera_rango,
    )
    storage.save_proyeccion(resultado.model_dump())

    return resultado.model_dump()


@app.post("/calcular/lote-individual")
def calcular_lote_individual(
    granja: str,
    galpon: int,
    nucleo: int,
    cantidad: int,
    sexo: str,
    edad: int,
    peso: float,
    fecha_faena: date,
    fecha_peso: date,
    current_user: TokenData = Depends(get_current_user)
):
    """Calcular valores de un lote individual (para preview)."""
    params = _get_parametros()
    oferta = LoteOferta(
        fecha_peso=fecha_peso,
        granja=granja,
        galpon=galpon,
        nucleo=nucleo,
        cantidad=cantidad,
        sexo=sexo,
        edad_proyectada=edad,
        peso_muestreo_proy=peso,
        ganancia_diaria=params.ganancia_diaria_macho,
        dias_proyectados=0,
        edad_real=edad,
        peso_muestreo_real=peso,
        fecha_ingreso=fecha_peso,
    )
    lote = calcular_lote_proyectado(oferta, fecha_faena, params)
    return lote.model_dump()


# ─── Gallinas ───────────────────────────────────────────────────────────────────────────

@app.post("/proyeccion/gallinas")
def configurar_gallinas(
    req: GallinasRequest,
    current_user: TokenData = Depends(get_current_user),
):
    """
    Marca un día de la proyección para faena de gallinas.
    Reduce la capacidad disponible para pollos en ese día.
    Soporta tipo "liviana" o "pesada" (se acumulan si se agregan ambos tipos).
    """
    semana = _get_proyeccion()
    if semana is None:
        raise HTTPException(404, "No hay proyección generada aún.")

    if req.dia_index < 0 or req.dia_index >= len(semana.dias):
        raise HTTPException(400, "Índice de día inválido")

    dia = semana.dias[req.dia_index]
    params = _get_parametros()

    # Calcular desglose: preservar la cantidad del otro tipo que ya esté en el día
    if req.tipo == "pesada":
        gallinas_pesadas = req.cantidad
        gallinas_livianas = dia.gallinas_livianas_cantidad
    else:
        gallinas_livianas = req.cantidad
        gallinas_pesadas = dia.gallinas_pesadas_cantidad

    total_gallinas = gallinas_livianas + gallinas_pesadas

    # Actualizar gallinas en el día
    semana.dias[req.dia_index] = calcular_dia_faena(
        dia.fecha, dia.lotes, params=params,
        gallinas_cantidad=total_gallinas,
        gallinas_livianas=gallinas_livianas,
        gallinas_pesadas=gallinas_pesadas,
    )

    # Registrar evento de gallinas: reemplazar solo el del mismo tipo en esa fecha
    semana.eventos_gallinas = [
        e for e in semana.eventos_gallinas
        if not (e.fecha == dia.fecha and e.tipo == req.tipo)
    ]
    if req.cantidad > 0:
        semana.eventos_gallinas.append(
            EventoGallinas(
                fecha=dia.fecha,
                cantidad=req.cantidad,
                tipo=req.tipo,
                descripcion=req.descripcion,
            )
        )

    # Recalcular semana
    resultado = calcular_semana_faena(
        semana.fecha_inicio, semana.dias, params,
        lotes_no_asignados=semana.lotes_no_asignados,
        lotes_fuera_rango=semana.lotes_fuera_rango,
    )
    resultado.feriados_aplicados = semana.feriados_aplicados
    resultado.eventos_gallinas = semana.eventos_gallinas
    storage.save_proyeccion(resultado.model_dump())
    return resultado.model_dump()


@app.delete("/proyeccion/gallinas/{dia_index}")
def quitar_gallinas(
    dia_index: int,
    tipo: Optional[str] = None,
    current_user: TokenData = Depends(get_current_user),
):
    """
    Quita las gallinas de un día de faena.
    Si tipo es "liviana" o "pesada", solo quita ese tipo.
    Si tipo es None, quita todas las gallinas del día.
    """
    semana = _get_proyeccion()
    if semana is None:
        raise HTTPException(404, "No hay proyección generada aún.")

    if dia_index < 0 or dia_index >= len(semana.dias):
        raise HTTPException(400, "Índice de día inválido")

    dia = semana.dias[dia_index]
    params = _get_parametros()

    if tipo == "pesada":
        gallinas_livianas = dia.gallinas_livianas_cantidad
        gallinas_pesadas = 0
    elif tipo == "liviana":
        gallinas_livianas = 0
        gallinas_pesadas = dia.gallinas_pesadas_cantidad
    else:
        gallinas_livianas = 0
        gallinas_pesadas = 0

    total_gallinas = gallinas_livianas + gallinas_pesadas

    semana.dias[dia_index] = calcular_dia_faena(
        dia.fecha, dia.lotes, params=params,
        gallinas_cantidad=total_gallinas,
        gallinas_livianas=gallinas_livianas,
        gallinas_pesadas=gallinas_pesadas,
    )

    if tipo:
        semana.eventos_gallinas = [
            e for e in semana.eventos_gallinas
            if not (e.fecha == dia.fecha and e.tipo == tipo)
        ]
    else:
        semana.eventos_gallinas = [
            e for e in semana.eventos_gallinas
            if e.fecha != dia.fecha
        ]

    resultado = calcular_semana_faena(
        semana.fecha_inicio, semana.dias, params,
        lotes_no_asignados=semana.lotes_no_asignados,
        lotes_fuera_rango=semana.lotes_fuera_rango,
    )
    resultado.feriados_aplicados = semana.feriados_aplicados
    resultado.eventos_gallinas = semana.eventos_gallinas
    storage.save_proyeccion(resultado.model_dump())
    return resultado.model_dump()


# ─── Feriados ───────────────────────────────────────────────────────────────────

@app.get("/feriados")
def get_feriados(anio: int, current_user: TokenData = Depends(get_current_user)):
    """
    Obtener feriados nacionales para un año dado,
    combinados con los feriados custom guardados.
    """
    nacionales = obtener_feriados_nacionales(anio)
    resultado = [
        {"fecha": f.isoformat(), "nombre": n, "tipo": "nacional"}
        for f, n in sorted(nacionales.items())
    ]

    # Agregar custom del mismo año
    custom = storage.load_feriados_custom() or []
    for fc in custom:
        fecha_str = fc.get("fecha", "")
        if fecha_str.startswith(str(anio)):
            resultado.append({
                "fecha": fecha_str,
                "nombre": fc.get("descripcion", "Feriado personalizado"),
                "tipo": "custom",
            })

    return resultado


@app.get("/feriados/custom")
def get_feriados_custom(current_user: TokenData = Depends(get_current_user)):
    """Obtener feriados personalizados guardados."""
    return storage.load_feriados_custom() or []


@app.post("/feriados/custom")
def add_feriado_custom(req: FeriadoCustomRequest, current_user: TokenData = Depends(get_current_user)):
    """Agregar un feriado personalizado."""
    custom = storage.load_feriados_custom() or []

    # Verificar que no exista ya
    fecha_str = req.fecha.isoformat()
    for fc in custom:
        if fc.get("fecha") == fecha_str:
            raise HTTPException(400, f"Ya existe un feriado custom para {fecha_str}")

    custom.append({"fecha": fecha_str, "descripcion": req.descripcion})
    storage.save_feriados_custom(custom)
    return {"message": f"Feriado agregado: {fecha_str}", "feriados": custom}


@app.delete("/feriados/custom/{fecha}")
def delete_feriado_custom(fecha: date, current_user: TokenData = Depends(get_current_user)):
    """Eliminar un feriado personalizado."""
    custom = storage.load_feriados_custom() or []
    fecha_str = fecha.isoformat()

    nueva_lista = [fc for fc in custom if fc.get("fecha") != fecha_str]
    if len(nueva_lista) == len(custom):
        raise HTTPException(404, f"No existe feriado custom para {fecha_str}")

    storage.save_feriados_custom(nueva_lista)
    return {"message": f"Feriado eliminado: {fecha_str}", "feriados": nueva_lista}


# ─── Producción Semanal ─────────────────────────────────────────────────────────

@app.post("/produccion/upload")
async def upload_produccion(
    file: UploadFile = File(...),
    sheet_name: Optional[str] = None,
    current_user: TokenData = Depends(get_current_user),
):
    """
    Subir archivo Excel de producción semanal (13.Datos Produccion por Semana).
    Lee la columna I (Pollitos Cargados en Granjas Propias).
    """
    if not file.filename or not file.filename.endswith(('.xlsx', '.xls')):
        raise HTTPException(400, "El archivo debe ser .xlsx o .xls")

    content = await file.read()
    try:
        semanas = leer_produccion_excel(content, sheet_name)
    except Exception as e:
        raise HTTPException(400, f"Error al leer el archivo: {str(e)}")

    if not semanas:
        raise HTTPException(400, "No se encontraron datos de producción válidos en el archivo.")

    # Persistir
    storage.save_produccion([s.model_dump() for s in semanas])
    upload_key = storage.save_upload(file.filename, content)
    storage.save_produccion_metadata({
        "filename": file.filename,
        "uploaded_at": datetime.now().isoformat(),
        "upload_key": upload_key,
        "sheet_name": sheet_name,
        "total_semanas": len(semanas),
        "total_pollitos": sum(s.pollitos_cargados for s in semanas),
        "fecha_desde": min((s.fecha_desde for s in semanas if s.fecha_desde), default=None),
        "fecha_hasta": max((s.fecha_hasta for s in semanas if s.fecha_hasta), default=None),
    })

    resultado = {
        "total_semanas": len(semanas),
        "total_pollitos": sum(s.pollitos_cargados for s in semanas),
        "semanas": [s.model_dump() for s in semanas],
    }

    # Validación cruzada contra oferta (si existe)
    try:
        validacion = _validar_cruce_produccion()
        if validacion:
            resultado["validacion_cruzada"] = validacion
    except Exception as e:
        logger.warning(f"Error en validación cruzada producción: {e}")

    return resultado


@app.get("/produccion")
def get_produccion(current_user: TokenData = Depends(get_current_user)):
    """Obtener datos de producción cargados."""
    data = storage.load_produccion()
    if not data:
        raise HTTPException(404, "No hay datos de producción cargados.")
    return {
        "total_semanas": len(data),
        "total_pollitos": sum(s.get("pollitos_cargados", 0) for s in data),
        "semanas": data,
    }


@app.get("/produccion/simulacion")
def get_simulacion_mortalidad(current_user: TokenData = Depends(get_current_user)):
    """
    Retorna simulación de mortalidad según la configuración vigente.
    para cada semana de producción cargada.
    """
    data = storage.load_produccion()
    if not data:
        raise HTTPException(404, "No hay datos de producción cargados.")

    config = _get_produccion_reference_config()
    semanas = [SemanaProduccion(**s) for s in data]
    resultado = simular_mortalidad(
        semanas,
        tasas=config["tasas_mortalidad"],
        dias_hasta_faena=config["dias_hasta_faena"],
    )
    return {
        "tasas": [round(t * 100, 1) for t in config["tasas_mortalidad"]],
        "configuracion": {
            "dias_hasta_faena": config["dias_hasta_faena"],
            "tolerancia_dias": config["tolerancia_dias"],
            "mortalidad_min": round(config["tasas_mortalidad"][0] * 100, 1),
            "mortalidad_max": round(config["tasas_mortalidad"][-1] * 100, 1),
        },
        "simulacion": [r.model_dump() for r in resultado],
    }


@app.get("/produccion/referencia")
def get_referencia_produccion(
    fecha_faena: date,
    current_user: TokenData = Depends(get_current_user),
) -> ReferenciaProduccionResponse:
    """
    Busca la referencia de producción más útil para la semana analizada.

    Si existe una proyección activa para esa semana, consolida las cohortes
    realmente planificadas a partir de los fecha_ingreso originales de los
    lotes asignados. Si no, cae al modo macro legacy (una sola semana por +42 días).
    """
    data = storage.load_produccion()
    if not data:
        return ReferenciaProduccionResponse(
            encontrada=False,
            mensaje="No hay datos de producción cargados.",
        )

    semanas = [SemanaProduccion(**s) for s in data]
    config = _get_produccion_reference_config()
    proyeccion = _get_proyeccion()
    total_oferta = proyeccion.total_pollos_semana if proyeccion else 0
    total_compra_terceros = 0
    metodo_cruce = "macro_faena"

    semanas_referenciadas: list[SemanaProduccion] = []
    if proyeccion and proyeccion.fecha_inicio == fecha_faena:
        contexto = _extraer_contexto_planificado_propio(proyeccion)
        if contexto["total_propio"] > 0:
            total_oferta = contexto["total_propio"]
            total_compra_terceros = contexto["total_compra_terceros"]
        if contexto["fechas_ingreso"]:
            semanas_referenciadas = _buscar_semanas_produccion_referenciadas(
                semanas,
                fechas_ingreso=contexto["fechas_ingreso"],
                dias_hasta_faena=config["dias_hasta_faena"],
                tolerancia_dias=config["tolerancia_dias"],
            )
            metodo_cruce = "cohortes_planificadas"

    if not semanas_referenciadas:
        semanas_referenciadas = _buscar_semanas_produccion_referenciadas(
            semanas,
            fecha_inicio_semana=fecha_faena,
            dias_hasta_faena=config["dias_hasta_faena"],
            tolerancia_dias=config["tolerancia_dias"],
        )
        metodo_cruce = "macro_faena"

    if not semanas_referenciadas:
        return ReferenciaProduccionResponse(
            encontrada=False,
            dias_hasta_faena_referencia=config["dias_hasta_faena"],
            tolerancia_cruce_dias=config["tolerancia_dias"],
            mensaje=f"No se encontró semana de producción para fecha de faena {fecha_faena.isoformat()}.",
        )

    sim_data = _agrupar_simulacion_produccion(
        semanas_referenciadas,
        dias_hasta_faena=config["dias_hasta_faena"],
        tasas_mortalidad=config["tasas_mortalidad"],
    )

    # Cobertura: plan propio actual vs disponible al peor escenario configurado
    peor_tasa = max(config["tasas_mortalidad"])
    total_pollitos = sum(sem.pollitos_cargados for sem in semanas_referenciadas)
    disponible_peor = int(total_pollitos * (1 - peor_tasa))
    cobertura = round((total_oferta / disponible_peor * 100), 1) if disponible_peor > 0 else None

    # Coberturas multi-escenario
    coberturas = []
    for sim_fila in sim_data["simulaciones"]:
        cob_pct = round((total_oferta / sim_fila["pollitos_disponibles"] * 100), 1) if sim_fila["pollitos_disponibles"] > 0 else None
        coberturas.append({
            "tasa": round(sim_fila["tasa_mortalidad"] * 100, 1),
            "disponibles": sim_fila["pollitos_disponibles"],
            "cobertura_pct": cob_pct,
        })

    return ReferenciaProduccionResponse(
        encontrada=True,
        semana_produccion=sim_data,
        total_oferta_actual=total_oferta,
        cobertura_pct=cobertura,
        coberturas=coberturas,
        total_compra_terceros=total_compra_terceros,
        total_semanas_referenciadas=len(semanas_referenciadas),
        metodo_cruce=metodo_cruce,
        dias_hasta_faena_referencia=config["dias_hasta_faena"],
        tolerancia_cruce_dias=config["tolerancia_dias"],
        mensaje=(
            f"Referencia consolidada sobre {len(semanas_referenciadas)} semana(s) de producción."
            if len(semanas_referenciadas) > 1
            else "Referencia encontrada."
        ),
    )


def _generar_insights_validacion(validacion: dict) -> list[dict]:
    """Genera insights accionables a partir de los datos de validación cruzada."""
    insights = []

    # ── Insights de factibilidad ──
    fact = validacion.get("factibilidad")
    if fact and fact.get("encontrada"):
        total_oferta = fact.get("total_oferta", 0)
        disponibles_peor = fact.get("disponibles_peor", 0)
        disponibles_mejor = fact.get("disponibles_mejor", 0)
        deficit = fact.get("deficit_peor")
        cobertura = fact.get("cobertura_pct_peor")

        if deficit and deficit > 0:
            pct_exceso = round(deficit / disponibles_peor * 100, 1) if disponibles_peor else 0
            insights.append({
                "tipo": "critico",
                "categoria": "factibilidad",
                "titulo": "Déficit de producción propia",
                "detalle": (
                    f"La oferta actual ({total_oferta:,} aves) supera en {deficit:,} aves "
                    f"({pct_exceso}%) la producción disponible en el escenario conservador "
                    f"({disponibles_peor:,} aves)."
                ),
                "accion": (
                    f"Considerar la compra de ~{deficit:,} pollos a terceros "
                    f"o reducir la oferta de la semana."
                ),
            })
        elif cobertura and cobertura > 85:
            insights.append({
                "tipo": "advertencia",
                "categoria": "factibilidad",
                "titulo": "Cobertura ajustada",
                "detalle": (
                    f"La producción cubre la oferta pero con margen bajo "
                    f"(la oferta consume {cobertura}% de la producción en el escenario conservador)."
                ),
                "accion": "Monitorear merma real; si sube, podría generarse déficit.",
            })
        else:
            margen = disponibles_peor - total_oferta if disponibles_peor else 0
            insights.append({
                "tipo": "positivo",
                "categoria": "factibilidad",
                "titulo": "Producción suficiente",
                "detalle": (
                    f"La producción propia ({disponibles_peor:,} en el escenario conservador) "
                    f"cubre la oferta ({total_oferta:,}) con un superávit de {margen:,} aves."
                ),
                "accion": "",
            })

        # Sensibilidad: diferencia entre mejor y peor caso
        if disponibles_mejor and disponibles_peor:
            rango = disponibles_mejor - disponibles_peor
            if rango > 0:
                coberturas = fact.get("coberturas") or []
                tasa_mejor = coberturas[0].get("tasa") if coberturas else None
                tasa_peor = coberturas[-1].get("tasa") if coberturas else None
                if tasa_mejor is not None and tasa_peor is not None:
                    detalle_sensibilidad = (
                        f"Entre el mejor ({tasa_mejor:.1f}% merma → {disponibles_mejor:,}) "
                        f"y peor escenario ({tasa_peor:.1f}% merma → {disponibles_peor:,}) "
                        f"hay una variación de {rango:,} aves."
                    )
                else:
                    detalle_sensibilidad = (
                        f"Entre el mejor ({disponibles_mejor:,}) y peor escenario "
                        f"({disponibles_peor:,}) hay una variación de {rango:,} aves."
                    )
                insights.append({
                    "tipo": "info",
                    "categoria": "sensibilidad",
                    "titulo": "Rango de sensibilidad por merma estimada",
                    "detalle": detalle_sensibilidad,
                    "accion": "",
                })

    # ── Insights de concordancia producción-oferta por cohortes ──
    mort = validacion.get("mortalidad_cohortes")
    if mort and mort.get("cohortes"):
        cohortes = mort["cohortes"]
        total_cohortes = len(cohortes)
        anticipadas = [c for c in cohortes if c.get("nivel") == "anticipada"]
        atrasadas = [c for c in cohortes if c.get("nivel") == "atrasada"]
        excedidas = [c for c in cohortes if c.get("nivel") == "excedida"]
        parciales = [c for c in cohortes if c.get("nivel") == "parcial"]
        alineadas = [c for c in cohortes if c.get("nivel") == "alineada"]

        if anticipadas:
            insights.append({
                "tipo": "advertencia",
                "categoria": "fechas",
                "titulo": f"{len(anticipadas)} cohorte(s) con oferta anticipada respecto a la carga BB",
                "detalle": (
                    "Las fechas objetivo de la oferta quedan antes de la ventana esperada de faena "
                    "según la configuración actual de referencia para esas cohortes."
                ),
                "accion": "Revisar si la fecha de ingreso o la fecha objetivo de la oferta corresponden a la misma cohorte.",
            })

        if atrasadas:
            insights.append({
                "tipo": "advertencia",
                "categoria": "fechas",
                "titulo": f"{len(atrasadas)} cohorte(s) con oferta tardía respecto a la carga BB",
                "detalle": (
                    "Las fechas objetivo de la oferta caen después de la ventana esperada de faena "
                    "para esas cargas de pollitos BB."
                ),
                "accion": "Validar si la cohorte fue diferida o si hay un desfase de fechas en los reportes.",
            })

        if excedidas:
            insights.append({
                "tipo": "critico",
                "categoria": "datos",
                "titulo": f"{len(excedidas)} cohorte(s) por encima de lo esperado",
                "detalle": (
                    "La oferta supera el rango esperado de aves en faena para al menos una cohorte. "
                    "Esto suele indicar duplicidades, fechas cruzadas o un matcheo incorrecto entre reportes."
                ),
                "accion": "Verificar fechas de ingreso, fechas objetivo de oferta y cantidades duplicadas.",
            })

        if parciales:
            insights.append({
                "tipo": "info",
                "categoria": "cobertura",
                "titulo": f"{len(parciales)} cohorte(s) con cobertura parcial en la oferta",
                "detalle": (
                    "La producción está informada por semana y la oferta por granja/lote, por lo que una cobertura baja "
                    "puede reflejar una cohorte parcial y no necesariamente un problema real."
                ),
                "accion": "Usar este cruce como referencia agregada, no como mortalidad observada por granja.",
            })

        if alineadas and not anticipadas and not atrasadas and not excedidas:
            insights.append({
                "tipo": "positivo",
                "categoria": "cohortes",
                "titulo": "Cohortes temporalmente alineadas",
                "detalle": (
                    f"{len(alineadas)} de {total_cohortes} cohortes muestran fechas objetivo coherentes con la ventana esperada de faena."
                ),
                "accion": "",
            })

    # ── Insights de consistencia de edad ──
    consist = validacion.get("consistencia_edad")
    if consist and consist.get("total", 0) > 0:
        total = consist["total"]
        insights.append({
            "tipo": "info",
            "categoria": "consistencia",
            "titulo": f"{total} lote(s) con inconsistencia de edad",
            "detalle": (
                f"La edad declarada difiere en más de 3 días de la edad calculada "
                f"(fecha_peso − fecha_ingreso) en {total} lotes."
            ),
            "accion": "Verificar fechas de ingreso y edades declaradas en la oferta.",
        })

    return insights


@app.delete("/produccion")
def clear_produccion(current_user: TokenData = Depends(get_current_user)):
    """Limpiar datos de producción."""
    storage.delete_produccion()
    storage.delete_produccion_metadata()
    return {"message": "Datos de producción eliminados."}


@app.get("/produccion/forecast")
def forecast_produccion(
    semanas: int = 4,
    current_user: TokenData = Depends(get_current_user),
):
    """
    Forecast de producción: para las próximas N semanas, muestra cuántos
    pollitos estarán disponibles para faena según las cargas registradas.
    """
    raw = storage.load_produccion()
    if not raw:
        raise HTTPException(404, "No hay datos de producción cargados.")

    config = _get_produccion_reference_config()
    semanas_prod = [SemanaProduccion(**r) for r in raw]
    hoy = date.today()
    tolerancia = config["tolerancia_dias"]

    # Pre-calcular rangos de cada semana de forecast (lunes a domingo)
    # Buscar el lunes de la semana actual (weekday(): 0=lunes, 6=domingo)
    lunes_actual = hoy - timedelta(days=hoy.weekday())
    rangos = []
    for i in range(semanas):
        inicio_sem = lunes_actual + timedelta(weeks=i)
        fin_sem = inicio_sem + timedelta(days=6)  # domingo
        centro = inicio_sem + timedelta(days=3)
        rangos.append((inicio_sem, fin_sem, centro))

    # Asignar cada carga a UNA sola semana (la más cercana) para evitar duplicados
    asignaciones: dict[int, list] = {i: [] for i in range(semanas)}
    for sp in semanas_prod:
        faena_est = calcular_fecha_faena_estimada(sp.fecha_desde, config["dias_hasta_faena"])
        mejor_idx = None
        mejor_dist = None
        for i, (inicio_sem, fin_sem, centro) in enumerate(rangos):
            if inicio_sem - timedelta(days=tolerancia) <= faena_est <= fin_sem + timedelta(days=tolerancia):
                dist = abs((faena_est - centro).days)
                if mejor_dist is None or dist < mejor_dist:
                    mejor_dist = dist
                    mejor_idx = i
        if mejor_idx is not None:
            asignaciones[mejor_idx].append(sp)

    result_semanas = []
    for i in range(semanas):
        inicio_sem, fin_sem, _ = rangos[i]
        matched = asignaciones[i]

        total_cargados = sum(s.pollitos_cargados for s in matched)
        mejor_tasa = min(config["tasas_mortalidad"])
        peor_tasa = max(config["tasas_mortalidad"])

        result_semanas.append({
            "inicio": inicio_sem.isoformat(),
            "fin": fin_sem.isoformat(),
            "semanas_incluidas": len(matched),
            "pollitos_cargados": total_cargados,
            "mejor_caso": {
                "tasa_mortalidad": mejor_tasa,
                "pollitos_disponibles": int(total_cargados * (1 - mejor_tasa)),
            } if total_cargados > 0 else None,
            "peor_caso": {
                "tasa_mortalidad": peor_tasa,
                "pollitos_disponibles": int(total_cargados * (1 - peor_tasa)),
            } if total_cargados > 0 else None,
        })

    return {"semanas": result_semanas}


# ─── Desvío de Peso (Proyectado vs. Real) ──────────────────────────────────────

@app.post("/desvio/pesos-reales")
def cargar_pesos_reales(
    req: PesosRealesBatchRequest,
    current_user: TokenData = Depends(get_current_user),
):
    """
    Cargar los pesos reales recibidos para comparar con la proyección.
    Recibe una lista de {fecha, peso_promedio_real}.
    """
    if not req.pesos:
        raise HTTPException(400, "Debe enviar al menos un peso real.")

    data = [p.model_dump() for p in req.pesos]
    storage.save_pesos_reales(data)
    return {"message": f"{len(data)} pesos reales guardados.", "pesos": data}


@app.get("/desvio")
def get_desvio(current_user: TokenData = Depends(get_current_user)):
    """
    Calcula el desvío entre peso proyectado y peso real para cada día.
    Requiere que exista una proyección y pesos reales cargados.
    """
    proyeccion = _get_proyeccion()
    if proyeccion is None:
        raise HTTPException(404, "No hay proyección generada.")

    pesos_data = storage.load_pesos_reales()
    if not pesos_data:
        raise HTTPException(404, "No hay pesos reales cargados.")

    # Indexar pesos reales por fecha
    pesos_por_fecha = {}
    for p in pesos_data:
        fecha_str = p["fecha"] if isinstance(p["fecha"], str) else p["fecha"].isoformat()
        pesos_por_fecha[fecha_str] = p["peso_promedio_real"]

    dias_desvio = []
    for dia in proyeccion.dias:
        fecha_str = dia.fecha.isoformat()
        peso_real = pesos_por_fecha.get(fecha_str)

        if peso_real is not None and dia.peso_promedio_ponderado > 0:
            desvio_abs = round(peso_real - dia.peso_promedio_ponderado, 3)
            desvio_pct = round(
                (peso_real - dia.peso_promedio_ponderado) / dia.peso_promedio_ponderado * 100, 2
            )

            # Nivel de alerta basado en desvío absoluto
            abs_desvio = abs(desvio_abs)
            if abs_desvio <= 0.05:
                nivel = "normal"
            elif abs_desvio <= 0.15:
                nivel = "moderado"
            else:
                nivel = "critico"

            dias_desvio.append({
                "fecha": fecha_str,
                "peso_proyectado": round(dia.peso_promedio_ponderado, 3),
                "peso_real": peso_real,
                "desvio_absoluto": desvio_abs,
                "desvio_porcentual": desvio_pct,
                "nivel": nivel,
                "total_pollos": dia.total_pollos,
            })
        else:
            dias_desvio.append({
                "fecha": fecha_str,
                "peso_proyectado": round(dia.peso_promedio_ponderado, 3),
                "peso_real": peso_real,
                "desvio_absoluto": None,
                "desvio_porcentual": None,
                "nivel": "sin_datos" if peso_real is None else "sin_proyeccion",
                "total_pollos": dia.total_pollos,
            })

    # Calcular promedio de desvío semanal (solo días con datos)
    dias_con_datos = [d for d in dias_desvio if d["desvio_absoluto"] is not None]
    if dias_con_datos:
        desvio_promedio = round(
            sum(d["desvio_absoluto"] for d in dias_con_datos) / len(dias_con_datos), 3
        )
        abs_promedio = abs(desvio_promedio)
        if abs_promedio <= 0.05:
            alerta_semana = "normal"
        elif abs_promedio <= 0.15:
            alerta_semana = "moderado"
        else:
            alerta_semana = "critico"
    else:
        desvio_promedio = None
        alerta_semana = "sin_datos"

    # Generar mensaje de alerta para Comercial
    mensaje = None
    if desvio_promedio is not None and abs(desvio_promedio) > 0.05:
        if desvio_promedio > 0:
            mensaje = (
                f"⚠ Los pollos vienen ~{int(abs(desvio_promedio) * 1000)}g más pesados "
                f"que lo proyectado. Avisar a Comercial: calibres más grandes de lo esperado."
            )
        else:
            mensaje = (
                f"⚠ Los pollos vienen ~{int(abs(desvio_promedio) * 1000)}g más livianos "
                f"que lo proyectado. Avisar a Comercial: calibres más chicos de lo esperado."
            )

    return {
        "dias": dias_desvio,
        "desvio_promedio_semana": desvio_promedio,
        "alerta_semana": alerta_semana,
        "mensaje_alerta": mensaje,
    }


@app.delete("/desvio")
def clear_pesos_reales(current_user: TokenData = Depends(get_current_user)):
    """Limpiar pesos reales cargados."""
    storage.delete_pesos_reales()
    return {"message": "Pesos reales eliminados."}


@app.get("/desvio/recomendacion")
def get_recomendacion_peso(current_user: TokenData = Depends(get_current_user)):
    """
    Analiza desvío de peso vs. objetivo de recepción y genera recomendación
    óptima para compensar kg perdidos, indicando si se necesitan más pollos
    o compra a terceros.
    """
    proyeccion = _get_proyeccion()
    if proyeccion is None:
        raise HTTPException(404, "No hay proyección generada.")

    params = _get_parametros()
    peso_objetivo = params.peso_objetivo_recepcion

    pesos_data = storage.load_pesos_reales()

    # Indexar pesos reales por fecha
    pesos_por_fecha = {}
    if pesos_data:
        for p in pesos_data:
            fecha_str = p["fecha"] if isinstance(p["fecha"], str) else p["fecha"].isoformat()
            pesos_por_fecha[fecha_str] = p["peso_promedio_real"]

    dias_afectados = []
    total_kg_deficit = 0.0
    total_pollos_compensacion = 0

    for dia in proyeccion.dias:
        fecha_str = dia.fecha.isoformat()
        peso_real = pesos_por_fecha.get(fecha_str)

        # Usar peso real si existe, si no usar proyectado
        peso_referencia = peso_real if peso_real is not None else dia.peso_promedio_ponderado

        if peso_referencia <= 0 or dia.total_pollos <= 0:
            continue

        if peso_referencia < peso_objetivo:
            diff_peso = round(peso_objetivo - peso_referencia, 3)
            kg_perdidos = round(diff_peso * dia.total_pollos * params.rendimiento_canal, 1)
            # Pollos adicionales necesarios para compensar kg perdidos
            peso_faenado_ref = peso_referencia * params.rendimiento_canal
            pollos_comp = int(kg_perdidos / peso_faenado_ref) if peso_faenado_ref > 0 else 0

            # Capacidad disponible
            es_sabado = dia.fecha.weekday() == 5
            cap_normal = params.limite_sabado if es_sabado else params.capacidad_maxima_planta
            cap_extras = params.limite_sabado if es_sabado else params.capacidad_con_horas_extras
            margen_normal = max(0, cap_normal - dia.total_pollos - dia.gallinas_cantidad)
            margen_extras = max(0, cap_extras - dia.total_pollos - dia.gallinas_cantidad)

            puede_sin_extras = pollos_comp <= margen_normal
            puede_con_extras = pollos_comp <= margen_extras

            dia_nombre = ["Lunes", "Martes", "Miércoles", "Jueves", "Viernes", "Sábado", "Domingo"][dia.fecha.weekday()]

            dias_afectados.append({
                "fecha": fecha_str,
                "dia_nombre": dia_nombre,
                "peso_referencia": round(peso_referencia, 3),
                "peso_objetivo": peso_objetivo,
                "diferencia_peso": diff_peso,
                "kg_deficit": kg_perdidos,
                "pollos_compensacion": pollos_comp,
                "pollos_actuales": dia.total_pollos,
                "margen_sin_extras": margen_normal,
                "margen_con_extras": margen_extras,
                "puede_sin_extras": puede_sin_extras,
                "puede_con_extras": puede_con_extras,
                "requiere_terceros": not puede_con_extras,
                "fuente_peso": "real" if peso_real is not None else "proyectado",
            })

            total_kg_deficit += kg_perdidos
            total_pollos_compensacion += pollos_comp

    # Determinar estado general
    peso_por_debajo = len(dias_afectados) > 0
    todos_absorben_sin_extras = all(d["puede_sin_extras"] for d in dias_afectados) if dias_afectados else True
    todos_absorben_con_extras = all(d["puede_con_extras"] for d in dias_afectados) if dias_afectados else True
    alguno_requiere_terceros = any(d["requiere_terceros"] for d in dias_afectados)

    # Generar recomendación textual
    recomendacion = ""
    alerta_comercial = ""
    if not peso_por_debajo:
        recomendacion = "✅ Los pesos están dentro o por encima del objetivo de recepción. No se requiere acción."
    else:
        if todos_absorben_sin_extras:
            recomendacion = (
                f"⚠ Peso por debajo del objetivo ({peso_objetivo:.2f} kg) en {len(dias_afectados)} día(s). "
                f"Se necesitan ~{total_pollos_compensacion:,} pollos adicionales para compensar "
                f"~{total_kg_deficit:,.0f} kg de déficit. "
                f"La planta puede absorber estos pollos SIN horas extras."
            )
        elif todos_absorben_con_extras:
            recomendacion = (
                f"⚠ Peso por debajo del objetivo ({peso_objetivo:.2f} kg) en {len(dias_afectados)} día(s). "
                f"Se necesitan ~{total_pollos_compensacion:,} pollos adicionales para compensar "
                f"~{total_kg_deficit:,.0f} kg de déficit. "
                f"Se requieren HORAS EXTRAS para absorber la carga adicional."
            )
        else:
            dias_terceros = [d for d in dias_afectados if d["requiere_terceros"]]
            recomendacion = (
                f"🔴 Peso por debajo del objetivo ({peso_objetivo:.2f} kg) en {len(dias_afectados)} día(s). "
                f"Se necesitan ~{total_pollos_compensacion:,} pollos adicionales. "
                f"En {len(dias_terceros)} día(s) la capacidad (incluso con horas extras) no alcanza. "
                f"Considerar COMPRA A TERCEROS."
            )

        alerta_comercial = (
            f"Alerta: peso promedio recibido por debajo del objetivo de {peso_objetivo:.2f} kg. "
            f"Déficit estimado de ~{total_kg_deficit:,.0f} kg faenados en la semana. "
            f"Calibres más chicos de lo esperado."
        )

    return {
        "peso_objetivo": peso_objetivo,
        "peso_por_debajo": peso_por_debajo,
        "dias_afectados": dias_afectados,
        "total_kg_deficit": round(total_kg_deficit, 1),
        "total_pollos_compensacion": total_pollos_compensacion,
        "puede_absorber_sin_extras": todos_absorben_sin_extras if peso_por_debajo else True,
        "puede_absorber_con_extras": todos_absorben_con_extras if peso_por_debajo else True,
        "requiere_terceros": alguno_requiere_terceros,
        "recomendacion": recomendacion,
        "alerta_comercial": alerta_comercial,
        "tiene_pesos_reales": len(pesos_por_fecha) > 0,
    }


@app.get("/desvio/mortalidad-observada")
def mortalidad_observada(current_user: TokenData = Depends(get_current_user)):
    """
    Back-calcula la mortalidad observada comparando producción (pollitos cargados)
    con los pollos realmente recibidos en faena (de la proyección).

    Ajustes respecto a la versión original:
    - Descuenta pollos fuera de rango (edad/peso) y no asignados (capacidad)
      del total de pollitos cargados, ya que están vivos pero no entran en faena.
    - Solo evalúa semanas cuyo rango de faena esté completamente cubierto por
      los días de la proyección (evita mortalidades ficticias por datos parciales).
    """
    prod_data = storage.load_produccion()
    if not prod_data:
        raise HTTPException(404, "No hay datos de producción cargados.")

    proyeccion = _get_proyeccion()
    if proyeccion is None:
        raise HTTPException(404, "No hay proyección generada.")

    config = _get_produccion_reference_config()
    semanas_prod = [SemanaProduccion(**s) for s in prod_data]
    tolerancia = config["tolerancia_dias"]

    # Rango de fechas cubierto por la proyección
    fechas_proyeccion = {dia.fecha for dia in proyeccion.dias if dia.total_pollos > 0}
    if not fechas_proyeccion:
        return {
            "puntos": [],
            "resumen": None,
            "mensaje": "La proyección no tiene días con pollos asignados.",
        }
    proy_fecha_min = min(fechas_proyeccion)
    proy_fecha_max = max(fechas_proyeccion)

    # Indexar pollos fuera de rango y no asignados por fecha_ingreso
    # para vincularlos a su semana de producción.
    pollos_excluidos_por_ingreso: dict[date, int] = {}
    for lote in (proyeccion.lotes_fuera_rango or []):
        if lote.fecha_ingreso:
            pollos_excluidos_por_ingreso[lote.fecha_ingreso] = (
                pollos_excluidos_por_ingreso.get(lote.fecha_ingreso, 0) + lote.cantidad
            )
    for lote in (proyeccion.lotes_no_asignados or []):
        if lote.fecha_ingreso:
            pollos_excluidos_por_ingreso[lote.fecha_ingreso] = (
                pollos_excluidos_por_ingreso.get(lote.fecha_ingreso, 0) + lote.cantidad
            )

    puntos = []
    for sp in semanas_prod:
        # Los pollitos cargados durante TODA la semana (fecha_desde→fecha_hasta)
        # estarán listos para faena alrededor de la ventana de referencia configurada.
        faena_rango_ini = sp.fecha_desde + timedelta(days=config["dias_hasta_faena"]) - timedelta(days=tolerancia)
        faena_rango_fin = sp.fecha_hasta + timedelta(days=config["dias_hasta_faena"]) + timedelta(days=tolerancia)

        # Verificar cobertura: el rango de faena debe estar completamente
        # dentro de las fechas de la proyección.
        if faena_rango_ini < proy_fecha_min or faena_rango_fin > proy_fecha_max:
            continue

        # Contar días hábiles esperados (lun-vie) en el rango de faena
        dias_habiles_esperados = 0
        d = faena_rango_ini
        while d <= faena_rango_fin:
            if d.weekday() < 5:  # lun=0 … vie=4
                dias_habiles_esperados += 1
            d += timedelta(days=1)

        # Buscar todos los días de faena dentro de ese rango
        pollos_recibidos = 0
        dias_match = 0
        for dia in proyeccion.dias:
            if faena_rango_ini <= dia.fecha <= faena_rango_fin:
                pollos_recibidos += dia.total_pollos
                dias_match += 1

        # Exigir al menos 80% de los días hábiles cubiertos
        if dias_habiles_esperados == 0 or sp.pollitos_cargados == 0:
            continue
        cobertura = dias_match / dias_habiles_esperados
        if cobertura < 0.8:
            continue

        # Sumar pollos excluidos (fuera de rango + no asignados) que pertenecen
        # a esta semana de producción (fecha_ingreso dentro de fecha_desde..fecha_hasta).
        pollos_excluidos = 0
        for fi, cant in pollos_excluidos_por_ingreso.items():
            if sp.fecha_desde <= fi <= sp.fecha_hasta:
                pollos_excluidos += cant

        # Mortalidad = 1 - (pollos_recibidos + pollos_excluidos) / pollitos_cargados
        pollos_contabilizados = pollos_recibidos + pollos_excluidos
        mortalidad_obs = 1 - (pollos_contabilizados / sp.pollitos_cargados)
        mortalidad_obs = max(0, min(1, mortalidad_obs))  # clamp 0-100%
        mortalidad_pct = round(mortalidad_obs * 100, 2)

        # Comparar con tasas estándar
        mejor_tasa = min(config["tasas_mortalidad"]) * 100
        peor_tasa = max(config["tasas_mortalidad"]) * 100

        if mortalidad_pct <= mejor_tasa:
            evaluacion = "excelente"
        elif mortalidad_pct <= peor_tasa:
            evaluacion = "dentro_rango"
        else:
            evaluacion = "por_encima"

        fecha_faena_est = calcular_fecha_faena_estimada(sp.fecha_desde, config["dias_hasta_faena"])
        puntos.append({
            "fecha_carga": sp.fecha_desde.isoformat(),
            "fecha_faena_estimada": fecha_faena_est.isoformat(),
            "pollitos_cargados": sp.pollitos_cargados,
            "pollos_recibidos": pollos_recibidos,
            "pollos_excluidos": pollos_excluidos,
            "mortalidad_observada_pct": mortalidad_pct,
            "evaluacion": evaluacion,
            "cobertura_dias_pct": round(cobertura * 100, 1),
        })

    if not puntos:
        return {
            "puntos": [],
            "resumen": None,
            "mensaje": (
                "No se encontraron semanas de producción cuyo rango de faena "
                "esté completamente cubierto por la proyección actual."
            ),
        }

    # Resumen
    mortalidades = [p["mortalidad_observada_pct"] for p in puntos]
    promedio = round(sum(mortalidades) / len(mortalidades), 2)
    mejor_tasa_pct = min(config["tasas_mortalidad"]) * 100
    peor_tasa_pct = max(config["tasas_mortalidad"]) * 100

    if promedio <= mejor_tasa_pct:
        tendencia = "favorable"
        mensaje = (
            f"✅ Mortalidad promedio observada: {promedio}%. "
            f"Por debajo del mejor escenario ({mejor_tasa_pct}%). Excelente desempeño."
        )
    elif promedio <= peor_tasa_pct:
        tendencia = "normal"
        mensaje = (
            f"📊 Mortalidad promedio observada: {promedio}%. "
            f"Dentro del rango esperado ({mejor_tasa_pct}%–{peor_tasa_pct}%)."
        )
    else:
        tendencia = "desfavorable"
        mensaje = (
            f"⚠ Mortalidad promedio observada: {promedio}%. "
            f"Por encima del peor escenario ({peor_tasa_pct}%). Revisar condiciones sanitarias."
        )

    return {
        "puntos": puntos,
        "resumen": {
            "promedio_mortalidad_pct": promedio,
            "min_mortalidad_pct": min(mortalidades),
            "max_mortalidad_pct": max(mortalidades),
            "semanas_analizadas": len(puntos),
            "tendencia": tendencia,
            "rango_esperado": {"min": mejor_tasa_pct, "max": peor_tasa_pct},
        },
        "mensaje": mensaje,
    }


@app.get("/proyeccion/analisis-terceros")
def analisis_necesidad_terceros(current_user: TokenData = Depends(get_current_user)):
    """
    Analiza la proyección actual y determina si hay déficit de pollos
    respecto al objetivo diario, sugiriendo compra a terceros.
    """
    proyeccion = _get_proyeccion()
    if proyeccion is None:
        raise HTTPException(404, "No hay proyección generada.")

    params = _get_parametros()
    objetivo_min = params.pollos_diarios_objetivo_min

    dias_con_deficit = []
    deficit_total = 0

    for dia in proyeccion.dias:
        es_sabado = dia.fecha.weekday() == 5
        if es_sabado:
            continue  # Sábados tienen su propio límite, no aplica déficit

        total_efectivo = dia.total_pollos + dia.gallinas_cantidad
        if total_efectivo < objetivo_min:
            faltante = objetivo_min - total_efectivo
            dia_nombre = ["Lunes", "Martes", "Miércoles", "Jueves", "Viernes", "Sábado", "Domingo"][dia.fecha.weekday()]

            # Margen disponible
            cap_normal = params.capacidad_maxima_planta
            cap_extras = params.capacidad_con_horas_extras
            margen = max(0, cap_normal - total_efectivo)

            dias_con_deficit.append({
                "fecha": dia.fecha.isoformat(),
                "dia_nombre": dia_nombre,
                "pollos_actuales": dia.total_pollos,
                "gallinas": dia.gallinas_cantidad,
                "objetivo_min": objetivo_min,
                "faltante": faltante,
                "margen_capacidad": margen,
                "dia_index": proyeccion.dias.index(dia),
            })
            deficit_total += faltante

    requiere_compra = deficit_total > 0

    # Generar recomendación
    recomendacion = ""
    if not requiere_compra:
        recomendacion = "✅ Todos los días cumplen con el objetivo mínimo diario."
    else:
        detalle = ", ".join(
            f"{d['dia_nombre']} ({d['faltante']:,})"
            for d in dias_con_deficit
        )
        recomendacion = (
            f"⚠ Faltan ~{deficit_total:,} pollos para cubrir el objetivo mínimo semanal. "
            f"Días con déficit: {detalle}. "
            f"Considerar compra a terceros para completar la carga."
        )

    return {
        "deficit_total": deficit_total,
        "dias_con_deficit": dias_con_deficit,
        "requiere_compra": requiere_compra,
        "recomendacion": recomendacion,
        "objetivo_min_diario": objetivo_min,
        "deficit_produccion": _calcular_deficit_produccion(proyeccion),
    }


# ─── Generación de Variantes (múltiples escenarios) ────────────────────────────

@app.post("/proyeccion/generar-escenarios")
def generar_escenarios_endpoint(
    req: ProyeccionRequest,
    current_user: TokenData = Depends(get_current_user),
):
    """
    Genera 1 a 3 variantes de proyección con diferentes estrategias.
    Para semanas complejas (feriados, gallinas, alta carga), genera 3 variantes.
    Para semanas normales, genera solo la variante Equilibrado.
    """
    ofertas = _get_ofertas()
    if not ofertas:
        raise HTTPException(400, "No hay oferta cargada. Suba un archivo primero.")

    params = req.parametros or _get_parametros()

    # Construir feriados
    feriados_custom_list = []
    saved_custom = storage.load_feriados_custom() or []
    feriados_custom_list.extend(saved_custom)
    if req.feriados_custom:
        for fc in req.feriados_custom:
            feriados_custom_list.append({"fecha": fc.isoformat(), "descripcion": "Feriado personalizado"})

    fecha_fin = req.fecha_inicio_semana + timedelta(days=13)
    feriados = obtener_feriados_rango(
        req.fecha_inicio_semana, fecha_fin,
        feriados_custom=feriados_custom_list if feriados_custom_list else None,
    )

    # Inyectar déficit si corresponde
    ofertas_base = ofertas
    if req.incluir_deficit:
        deficit_data = storage.load_deficit()
        if deficit_data and deficit_data.get("ofertas_originales"):
            for od in deficit_data["ofertas_originales"]:
                try:
                    ofertas_base = ofertas_base + [LoteOferta(**od)]
                except Exception:
                    pass

    # Detectar si la semana es compleja
    tiene_feriados = bool(feriados)
    tiene_gallinas = bool(req.gallinas and len(req.gallinas) > 0)
    total_aves_oferta = sum(o.cantidad for o in ofertas_base)
    dias_base = req.dias_faena
    carga_excedida = total_aves_oferta > req.pollos_por_dia * dias_base * 1.1
    es_compleja = tiene_feriados or tiene_gallinas or carga_excedida

    def _generar_variante(etiqueta, descripcion, pollos_dia, dias, habilitar_sab, params_override=None):
        dias_eff = max(dias, 6) if habilitar_sab else dias
        variante_params = params.model_copy()
        if params_override:
            for k, v in params_override.items():
                setattr(variante_params, k, v)
        semana = generar_proyeccion(
            ofertas=ofertas_base,
            fecha_inicio_semana=req.fecha_inicio_semana,
            dias_faena=dias_eff,
            pollos_por_dia=pollos_dia,
            params=variante_params,
            feriados=feriados if feriados else None,
            gallinas=req.gallinas,
            criterio_gerente=req.criterio_gerente,
            permitir_fraccionamiento_lotes=req.permitir_fraccionamiento_lotes,
            excluir_backlog_semana_previa=req.excluir_backlog_semana_previa,
            minimos_como_alerta=req.minimos_como_alerta,
        )
        proy_dict = semana.model_dump()
        usa_horas_extras = any(d.get("nivel_carga") == "horas_extras" for d in proy_dict.get("dias", []))
        usa_sabado = any(d.get("es_sabado") for d in proy_dict.get("dias", []))
        max_carga = max((d.get("total_pollos", 0) for d in proy_dict.get("dias", [])), default=0)
        return {
            "etiqueta": etiqueta,
            "descripcion": descripcion,
            "parametros_usados": {
                "pollos_por_dia": pollos_dia,
                "dias_faena": dias_eff,
                "habilitar_sabado": habilitar_sab,
            },
            "proyeccion": proy_dict,
            "resumen": {
                "total_pollos": proy_dict.get("total_pollos_semana", 0),
                "dias_efectivos": len(proy_dict.get("dias", [])),
                "pollos_no_asignados": proy_dict.get("total_pollos_no_asignados", 0),
                "pollos_fuera_rango": proy_dict.get("total_pollos_fuera_rango", 0),
                "max_carga_dia": max_carga,
                "usa_sabado": usa_sabado,
                "usa_horas_extras": usa_horas_extras,
                "cajas_semanales": proy_dict.get("produccion_cajas_semanales", 0),
            },
        }

    variantes = []

    if es_compleja:
        # Conservador: objetivo bajo, capacidad limitada al objetivo, sábado habilitado
        variantes.append(_generar_variante(
            "Conservador",
            "Carga diaria baja, sábado habilitado. Prioriza evitar horas extras.",
            params.pollos_diarios_objetivo_min,
            dias_base,
            True,
            params_override={
                "capacidad_maxima_planta": params.pollos_diarios_objetivo_min,
                "pollos_diarios_objetivo_max": params.pollos_diarios_objetivo_min,
            },
        ))

        # Equilibrado: objetivo del usuario, capacidad estándar, sábado solo si hay feriados
        variantes.append(_generar_variante(
            "Equilibrado",
            "Carga moderada. Sábado solo si hay feriados o gallinas.",
            req.pollos_por_dia,
            dias_base,
            tiene_feriados or tiene_gallinas,
        ))

        # Intensivo: objetivo alto, permite horas extras, sin sábado
        variantes.append(_generar_variante(
            "Intensivo",
            "Carga máxima Lun-Vie. Sin sábado, acepta posibles horas extras.",
            params.capacidad_con_horas_extras,
            dias_base,
            False,
            params_override={
                "capacidad_maxima_planta": params.capacidad_con_horas_extras,
                "pollos_diarios_objetivo_max": params.capacidad_con_horas_extras,
            },
        ))
    else:
        # Semana normal: solo Equilibrado
        variantes.append(_generar_variante(
            "Equilibrado",
            "Distribución estándar sin complejidades especiales.",
            req.pollos_por_dia,
            dias_base,
            req.habilitar_sabado,
        ))

    return {
        "es_compleja": es_compleja,
        "motivos_complejidad": {
            "feriados": tiene_feriados,
            "gallinas": tiene_gallinas,
            "carga_excedida": carga_excedida,
        },
        "variantes": variantes,
    }


@app.post("/proyeccion/aplicar-variante")
def aplicar_variante_endpoint(
    proyeccion_data: dict,
    current_user: TokenData = Depends(get_current_user),
):
    """
    Persiste una variante de proyección seleccionada por el usuario.
    Recibe la proyección completa (SemanaFaena) y la guarda como activa.
    """
    storage.save_proyeccion(proyeccion_data)
    params = _get_parametros()
    storage.save_parametros(params.model_dump())
    return proyeccion_data


# ─── Escenarios ─────────────────────────────────────────────────────────────────

@app.post("/escenarios/guardar")
def guardar_escenario(
    req: GuardarEscenarioRequest,
    current_user: TokenData = Depends(get_current_user),
):
    """
    Guarda la proyección actual como un escenario con nombre.
    """
    proyeccion = _get_proyeccion()
    if proyeccion is None:
        raise HTTPException(404, "No hay proyección generada para guardar.")

    params = _get_parametros()
    escenario_id = str(uuid.uuid4())[:8]

    # Calcular análisis de producción con la tasa elegida (o peor caso por defecto)
    tasa = req.tasa_mortalidad
    produccion_analisis = None
    if tasa is not None:
        fact = _calcular_factibilidad_proyeccion(proyeccion)
        if fact and fact.encontrada and fact.pollitos_cargados is not None:
            disponibles = int(fact.pollitos_cargados * (1 - tasa))
            deficit = max(0, fact.total_oferta - disponibles)
            cobertura = round(fact.total_oferta / disponibles * 100, 1) if disponibles > 0 else None
            produccion_analisis = {
                "tasa_mortalidad": tasa,
                "pollitos_cargados": fact.pollitos_cargados,
                "disponibles": disponibles,
                "deficit": deficit if deficit > 0 else None,
                "cobertura_pct": cobertura,
                "total_oferta": fact.total_oferta,
                "total_compra_terceros": fact.total_compra_terceros,
                "total_semanas_referenciadas": fact.total_semanas_referenciadas,
                "metodo_cruce": fact.metodo_cruce,
                "contexto": fact.contexto,
            }

    escenario_data = {
        "id": escenario_id,
        "nombre": req.nombre,
        "descripcion": req.descripcion or "",
        "fecha_creacion": datetime.now().isoformat(),
        "tasa_mortalidad": tasa,
        "parametros": params.model_dump(),
        "proyeccion": proyeccion.model_dump(),
        "produccion_analisis": produccion_analisis,
        "resumen": {
            "total_pollos": proyeccion.total_pollos_semana,
            "dias": len(proyeccion.dias),
            "cajas": proyeccion.produccion_cajas_semanales,
            "sofia": proyeccion.sofia,
            "promedio_edad": proyeccion.promedio_edad_semana,
            "tasa_mortalidad": tasa,
            "pollos_por_dia": [
                {"fecha": d.fecha.isoformat(), "total": d.total_pollos}
                for d in proyeccion.dias
            ],
        },
    }

    storage.save_escenario(escenario_id, escenario_data)
    return {"message": f"Escenario '{req.nombre}' guardado.", "id": escenario_id}


@app.get("/escenarios")
def listar_escenarios(current_user: TokenData = Depends(get_current_user)):
    """Lista todos los escenarios guardados (resumen, sin la proyección completa)."""
    ids = storage.list_escenarios()
    escenarios = []
    for eid in ids:
        data = storage.load_escenario(eid)
        if data:
            escenarios.append({
                "id": data.get("id", eid),
                "nombre": data.get("nombre", "Sin nombre"),
                "descripcion": data.get("descripcion", ""),
                "fecha_creacion": data.get("fecha_creacion"),
                "tasa_mortalidad": data.get("tasa_mortalidad"),
                "produccion_analisis": data.get("produccion_analisis"),
                "resumen": data.get("resumen", {}),
            })
    # Ordenar por fecha de creación descendente
    escenarios.sort(key=lambda x: x.get("fecha_creacion", ""), reverse=True)
    return escenarios


@app.get("/escenarios/{escenario_id}")
def get_escenario(escenario_id: str, current_user: TokenData = Depends(get_current_user)):
    """Obtiene un escenario completo (con proyección)."""
    data = storage.load_escenario(escenario_id)
    if not data:
        raise HTTPException(404, f"Escenario '{escenario_id}' no encontrado.")
    return data


@app.delete("/escenarios/{escenario_id}")
def eliminar_escenario(escenario_id: str, current_user: TokenData = Depends(get_current_user)):
    """Elimina un escenario guardado."""
    data = storage.load_escenario(escenario_id)
    if not data:
        raise HTTPException(404, f"Escenario '{escenario_id}' no encontrado.")
    storage.delete_escenario(escenario_id)
    nombre = data.get("nombre", escenario_id)
    return {"message": f"Escenario '{nombre}' eliminado."}


@app.post("/escenarios/comparar")
def comparar_escenarios(
    req: CompararEscenariosRequest,
    current_user: TokenData = Depends(get_current_user),
):
    """
    Compara 2-3 escenarios lado a lado.
    Retorna los datos de cada escenario para renderizar la comparación.
    """
    if len(req.ids) < 2 or len(req.ids) > 3:
        raise HTTPException(400, "Debe seleccionar 2 o 3 escenarios para comparar.")

    escenarios = []
    for eid in req.ids:
        data = storage.load_escenario(eid)
        if not data:
            raise HTTPException(404, f"Escenario '{eid}' no encontrado.")
        escenarios.append(data)

    return {"escenarios": escenarios}


@app.post("/escenarios/{escenario_id}/cargar")
def cargar_escenario(
    escenario_id: str,
    current_user: TokenData = Depends(get_current_user),
):
    """
    Restaura un escenario como la proyección activa.
    Carga la proyección y los parámetros del escenario.
    """
    data = storage.load_escenario(escenario_id)
    if not data:
        raise HTTPException(404, f"Escenario '{escenario_id}' no encontrado.")

    # Restaurar proyección y parámetros
    if "proyeccion" in data:
        storage.save_proyeccion(data["proyeccion"])
    if "parametros" in data:
        storage.save_parametros(data["parametros"])

    return {
        "message": f"Escenario '{data.get('nombre', escenario_id)}' cargado como proyección activa.",
        "proyeccion": data.get("proyeccion"),
    }


# ─── Déficit entre semanas ───────────────────────────────────────────────────────

@app.get("/proyeccion/deficit")
def get_deficit(current_user: TokenData = Depends(get_current_user)):
    """Retorna los lotes no asignados de la proyección actual (déficit de la semana)."""
    semana = _get_proyeccion()
    if semana is None:
        raise HTTPException(404, "No hay proyección generada.")
    return DeficitResponse(
        lotes_no_asignados=[l.model_dump() for l in semana.lotes_no_asignados],
        total_pollos=semana.total_pollos_no_asignados,
        total_lotes=len(semana.lotes_no_asignados),
    )


@app.post("/proyeccion/cargar-deficit")
def cargar_deficit_semana(current_user: TokenData = Depends(get_current_user)):
    """
    Persiste los lotes no asignados de la proyección actual como déficit
    para la semana siguiente.  Guarda también los datos originales de oferta
    para poder re-inyectarlos en la generación de la semana siguiente.
    """
    semana = _get_proyeccion()
    if semana is None:
        raise HTTPException(404, "No hay proyección generada.")

    if not semana.lotes_no_asignados:
        raise HTTPException(400, "No hay lotes no asignados en la proyección actual.")

    # Buscar ofertas originales para preservar datos de cálculo
    ofertas_originales = _get_ofertas()
    ofertas_index: dict[tuple, dict] = {}
    for o in ofertas_originales:
        key = (o.granja, o.galpon, o.nucleo, o.sexo,
               o.fecha_ingreso.isoformat() if o.fecha_ingreso else "")
        ofertas_index[key] = o.model_dump()

    ofertas_deficit = []
    for lote_na in semana.lotes_no_asignados:
        key = (lote_na.granja, lote_na.galpon, lote_na.nucleo, lote_na.sexo,
               lote_na.fecha_ingreso.isoformat() if lote_na.fecha_ingreso else "")
        oferta_orig = ofertas_index.get(key)
        if oferta_orig:
            ofertas_deficit.append(oferta_orig)

    deficit_data = {
        "lotes": [l.model_dump() for l in semana.lotes_no_asignados],
        "ofertas_originales": ofertas_deficit,
        "total_pollos": semana.total_pollos_no_asignados,
        "total_lotes": len(semana.lotes_no_asignados),
        "semana_origen": semana.fecha_inicio.isoformat(),
        "fecha_guardado": datetime.now().isoformat(),
    }
    storage.save_deficit(deficit_data)

    return CargarDeficitResponse(
        lotes_trasladados=len(semana.lotes_no_asignados),
        pollos_trasladados=semana.total_pollos_no_asignados,
        mensaje=(
            f"{len(semana.lotes_no_asignados)} lotes "
            f"({semana.total_pollos_no_asignados:,} pollos) guardados como déficit "
            f"para la semana siguiente."
        ),
    )


@app.get("/proyeccion/deficit-guardado")
def get_deficit_guardado(current_user: TokenData = Depends(get_current_user)):
    """Retorna el déficit guardado de la semana anterior (si existe)."""
    data = storage.load_deficit()
    if not data:
        return {
            "existe": False,
            "total_pollos": 0,
            "total_lotes": 0,
            "lotes": [],
            "semana_origen": None,
        }
    return {"existe": True, **data}


@app.delete("/proyeccion/deficit-guardado")
def clear_deficit_guardado(current_user: TokenData = Depends(get_current_user)):
    """Elimina el déficit guardado de la semana anterior."""
    storage.delete_deficit()
    return {"message": "Déficit limpiado."}


# ─── Semana 2: Diferir lotes y proyección tentativa ─────────────────────────────

@app.post("/proyeccion/diferir-lote")
def diferir_lote_semana2(req: DiferirLoteRequest, current_user: TokenData = Depends(get_current_user)):
    """
    Difiere un lote de semana 1 a semana 2.
    Lo remueve de la proyección actual y lo guarda como lote diferido.
    """
    semana = _get_proyeccion()
    if semana is None:
        raise HTTPException(404, "No hay proyección generada aún.")

    if req.dia_index < 0 or req.dia_index >= len(semana.dias):
        raise HTTPException(400, "Índice de día inválido")

    dia = semana.dias[req.dia_index]
    if req.lote_index < 0 or req.lote_index >= len(dia.lotes):
        raise HTTPException(400, "Índice de lote inválido")

    lote = dia.lotes.pop(req.lote_index)

    # Guardar como lote diferido (preservar datos originales para recálculo)
    diferido = {
        "granja": lote.granja,
        "galpon": lote.galpon,
        "nucleo": lote.nucleo,
        "cantidad": lote.cantidad,
        "sexo": lote.sexo,
        "edad_actual": lote.edad_actual,
        "peso_actual": lote.peso_actual,
        "fecha_peso_original": lote.fecha_peso_original.isoformat() if lote.fecha_peso_original else None,
        "ganancia_diaria_original": lote.ganancia_diaria_original,
        "fecha_ingreso_original": lote.fecha_ingreso_original.isoformat() if lote.fecha_ingreso_original else None,
        "dias_proyectados_original": lote.dias_proyectados_original,
        "fragmentado": lote.fragmentado,
        "fragment_id": lote.fragment_id,
        "cantidad_original_lote": lote.cantidad_original_lote,
        "dia_origen_fecha": dia.fecha.isoformat(),
        "dia_origen_index": req.dia_index,
        "motivo": req.motivo,
    }

    diferidos = storage.load_lotes_diferidos() or []
    diferidos.append(diferido)
    storage.save_lotes_diferidos(diferidos)

    # Recalcular semana 1
    params = _get_parametros()
    semana.dias[req.dia_index] = calcular_dia_faena(
        dia.fecha, dia.lotes, params=params,
        gallinas_cantidad=dia.gallinas_cantidad,
        gallinas_livianas=dia.gallinas_livianas_cantidad,
        gallinas_pesadas=dia.gallinas_pesadas_cantidad,
    )
    resultado = calcular_semana_faena(
        semana.fecha_inicio, semana.dias, params,
        lotes_no_asignados=semana.lotes_no_asignados,
        lotes_fuera_rango=semana.lotes_fuera_rango,
    )
    resultado.feriados_aplicados = semana.feriados_aplicados
    resultado.eventos_gallinas = semana.eventos_gallinas
    storage.save_proyeccion(resultado.model_dump())

    return {
        "proyeccion": resultado.model_dump(),
        "lote_diferido": diferido,
        "total_diferidos": len(diferidos),
    }


@app.post("/proyeccion/restaurar-lote-semana1")
def restaurar_lote_semana1(req: RestaurarLoteRequest, current_user: TokenData = Depends(get_current_user)):
    """
    Restaura un lote diferido de vuelta a semana 1.
    Lo remueve de lotes diferidos y lo agrega al día indicado (o al de mayor déficit).
    """
    semana = _get_proyeccion()
    if semana is None:
        raise HTTPException(404, "No hay proyección generada aún.")

    diferidos = storage.load_lotes_diferidos() or []
    if req.diferido_index < 0 or req.diferido_index >= len(diferidos):
        raise HTTPException(400, "Índice de lote diferido inválido")

    diferido = diferidos.pop(req.diferido_index)
    storage.save_lotes_diferidos(diferidos)

    params = _get_parametros()

    # Reconstruir LoteOferta desde datos diferidos
    fecha_peso = date.fromisoformat(diferido["fecha_peso_original"]) if diferido.get("fecha_peso_original") else semana.fecha_inicio
    ganancia = diferido.get("ganancia_diaria_original") or params.ganancia_diaria_macho
    fecha_ingreso = date.fromisoformat(diferido["fecha_ingreso_original"]) if diferido.get("fecha_ingreso_original") else fecha_peso

    oferta_equiv = LoteOferta(
        fecha_peso=fecha_peso,
        granja=diferido["granja"],
        galpon=diferido["galpon"],
        nucleo=diferido["nucleo"],
        cantidad=diferido["cantidad"],
        sexo=diferido["sexo"],
        edad_proyectada=diferido["edad_actual"],
        peso_muestreo_proy=diferido["peso_actual"],
        ganancia_diaria=ganancia,
        dias_proyectados=diferido.get("dias_proyectados_original", 0),
        edad_real=diferido["edad_actual"],
        peso_muestreo_real=diferido["peso_actual"],
        fecha_ingreso=fecha_ingreso,
    )

    # Determinar día destino
    if req.dia_destino is not None:
        if req.dia_destino < 0 or req.dia_destino >= len(semana.dias):
            raise HTTPException(400, "Índice de día destino inválido")
        dia_destino_idx = req.dia_destino
    else:
        # Auto-asignar al día con mayor déficit vs objetivo
        objetivo = params.pollos_diarios_objetivo_max
        mejor_idx = 0
        mayor_deficit = -1
        for idx, d in enumerate(semana.dias):
            deficit = objetivo - d.total_pollos
            if deficit > mayor_deficit:
                mayor_deficit = deficit
                mejor_idx = idx
        dia_destino_idx = mejor_idx

    dia_destino = semana.dias[dia_destino_idx]
    nuevo_lote = _copiar_metadata_diferida(
        diferido,
        calcular_lote_proyectado(oferta_equiv, dia_destino.fecha, params),
    )
    dia_destino.lotes.append(nuevo_lote)

    # Recalcular
    semana.dias[dia_destino_idx] = calcular_dia_faena(
        dia_destino.fecha, dia_destino.lotes, params=params,
        gallinas_cantidad=dia_destino.gallinas_cantidad,
        gallinas_livianas=dia_destino.gallinas_livianas_cantidad,
        gallinas_pesadas=dia_destino.gallinas_pesadas_cantidad,
    )
    resultado = calcular_semana_faena(
        semana.fecha_inicio, semana.dias, params,
        lotes_no_asignados=semana.lotes_no_asignados,
        lotes_fuera_rango=semana.lotes_fuera_rango,
    )
    resultado.feriados_aplicados = semana.feriados_aplicados
    resultado.eventos_gallinas = semana.eventos_gallinas
    storage.save_proyeccion(resultado.model_dump())

    return {
        "proyeccion": resultado.model_dump(),
        "dia_destino": dia_destino_idx,
        "total_diferidos": len(diferidos),
    }


@app.get("/proyeccion/semana2")
def get_semana2(current_user: TokenData = Depends(get_current_user)):
    """
    Genera la proyección tentativa de semana 2 usando:
    - Lotes diferidos por el usuario
    - Lotes no asignados de semana 1 (si son elegibles en semana 2)
    - Lotes fuera de rango de semana 1 que sí podrían entrar en semana 2

    Retorna la proyección como solo lectura (tentativa).
    """
    semana = _get_proyeccion()
    if semana is None:
        raise HTTPException(404, "No hay proyección generada aún.")

    diferidos = storage.load_lotes_diferidos() or []

    # Reunir lotes para semana 2 como LoteOferta
    ofertas_s2: list[LoteOferta] = []
    params = _get_parametros()
    config_s1 = storage.load_proyeccion_config() or {}
    dias_faena_s2 = config_s1.get("dias_faena", 5)
    pollos_por_dia_s2 = config_s1.get("pollos_por_dia", params.pollos_diarios_objetivo_max)
    if config_s1.get("habilitar_sabado") and dias_faena_s2 < 6:
        dias_faena_s2 = 6

    def _lote_key(granja: str, galpon: int, nucleo: int, sexo: str, fecha_ingreso: Optional[date]) -> tuple:
        return (
            normalizar_granja_clave(granja),
            galpon,
            nucleo,
            sexo,
            fecha_ingreso.isoformat() if fecha_ingreso else "",
        )

    ofertas_s2_index: dict[tuple, LoteOferta] = {}

    def _agregar_oferta_si_no_existe(oferta: LoteOferta) -> bool:
        key = _lote_key(oferta.granja, oferta.galpon, oferta.nucleo, oferta.sexo, oferta.fecha_ingreso)
        existente = ofertas_s2_index.get(key)
        if existente is None:
            ofertas_s2.append(oferta)
            ofertas_s2_index[key] = oferta
            return True
        existente.cantidad += oferta.cantidad
        return False

    # 1) Lotes diferidos → LoteOferta
    for d in diferidos:
        fecha_peso = date.fromisoformat(d["fecha_peso_original"]) if d.get("fecha_peso_original") else semana.fecha_inicio
        ganancia = d.get("ganancia_diaria_original") or params.ganancia_diaria_macho
        fecha_ingreso = date.fromisoformat(d["fecha_ingreso_original"]) if d.get("fecha_ingreso_original") else fecha_peso
        _agregar_oferta_si_no_existe(LoteOferta(
            fecha_peso=fecha_peso,
            granja=d["granja"],
            galpon=d["galpon"],
            nucleo=d["nucleo"],
            cantidad=d["cantidad"],
            sexo=d["sexo"],
            edad_proyectada=d["edad_actual"],
            peso_muestreo_proy=d["peso_actual"],
            ganancia_diaria=ganancia,
            dias_proyectados=d.get("dias_proyectados_original", 0),
            edad_real=d["edad_actual"],
            peso_muestreo_real=d["peso_actual"],
            fecha_ingreso=fecha_ingreso,
        ))

    ofertas_originales = _get_ofertas()
    ofertas_index: dict[tuple, LoteOferta] = {}
    if ofertas_originales:
        for o in ofertas_originales:
            key = _lote_key(o.granja, o.galpon, o.nucleo, o.sexo, o.fecha_ingreso)
            if key not in ofertas_index:
                ofertas_index[key] = o

    # 2) Lotes no asignados de semana 1 → buscar en ofertas originales
    if semana.lotes_no_asignados and ofertas_index:
        for lote_na in semana.lotes_no_asignados:
            key = _lote_key(lote_na.granja, lote_na.galpon, lote_na.nucleo, lote_na.sexo, lote_na.fecha_ingreso)
            oferta_orig = ofertas_index.get(key)
            if oferta_orig:
                _agregar_oferta_si_no_existe(oferta_orig)

    # 3) Lotes fuera de rango de semana 1 → reintentar en semana 2 usando la oferta original.
    # Esto permite continuar la planificación con lotes jóvenes que aún no estaban listos en S1.
    lotes_recuperados_fuera_rango_s1 = 0
    pollos_recuperados_fuera_rango_s1 = 0
    if semana.lotes_fuera_rango and ofertas_index:
        for lote_fr in semana.lotes_fuera_rango:
            key = _lote_key(lote_fr.granja, lote_fr.galpon, lote_fr.nucleo, lote_fr.sexo, lote_fr.fecha_ingreso)
            oferta_orig = ofertas_index.get(key)
            if oferta_orig and _agregar_oferta_si_no_existe(oferta_orig):
                lotes_recuperados_fuera_rango_s1 += 1
                pollos_recuperados_fuera_rango_s1 += oferta_orig.cantidad

    if not ofertas_s2:
        return {
            "tiene_datos": False,
            "proyeccion": None,
            "lotes_diferidos": diferidos,
            "total_diferidos": len(diferidos),
            "lotes_no_asignados_s1": len(semana.lotes_no_asignados),
            "lotes_fuera_rango_s1": len(semana.lotes_fuera_rango),
            "lotes_recuperados_fuera_rango_s1": lotes_recuperados_fuera_rango_s1,
            "pollos_recuperados_fuera_rango_s1": pollos_recuperados_fuera_rango_s1,
            "mensaje": "No hay lotes diferidos, no asignados ni fuera de rango recuperables para proyectar en semana 2.",
        }

    # Fecha inicio semana 2: siguiente lunes después de semana 1
    fecha_inicio_s2 = semana.fecha_inicio + timedelta(days=7)

    # Obtener feriados para el rango de semana 2 (L-S)
    fecha_fin_s2 = fecha_inicio_s2 + timedelta(days=5)
    feriados_custom = storage.load_feriados_custom() or []
    feriados = obtener_feriados_rango(
        fecha_inicio_s2, fecha_fin_s2,
        feriados_custom=feriados_custom if feriados_custom else None,
    )

    semana2 = generar_proyeccion(
        ofertas=ofertas_s2,
        fecha_inicio_semana=fecha_inicio_s2,
        dias_faena=dias_faena_s2,
        pollos_por_dia=pollos_por_dia_s2,
        params=params,
        feriados=feriados if feriados else None,
        criterio_gerente=config_s1.get("criterio_gerente", True),
        permitir_fraccionamiento_lotes=config_s1.get("permitir_fraccionamiento_lotes"),
        excluir_backlog_semana_previa=config_s1.get("excluir_backlog_semana_previa"),
        minimos_como_alerta=config_s1.get("minimos_como_alerta"),
    )

    # Persistir la proyección S2 para edición interactiva
    storage.save_proyeccion_s2(semana2.model_dump())

    return {
        "tiene_datos": True,
        "proyeccion": semana2.model_dump(),
        "lotes_diferidos": diferidos,
        "total_diferidos": len(diferidos),
        "lotes_no_asignados_s1": len(semana.lotes_no_asignados),
        "lotes_fuera_rango_s1": len(semana.lotes_fuera_rango),
        "lotes_recuperados_fuera_rango_s1": lotes_recuperados_fuera_rango_s1,
        "pollos_recuperados_fuera_rango_s1": pollos_recuperados_fuera_rango_s1,
    }


@app.get("/proyeccion/lotes-diferidos")
def get_lotes_diferidos(current_user: TokenData = Depends(get_current_user)):
    """Retorna la lista de lotes diferidos a semana 2."""
    diferidos = storage.load_lotes_diferidos() or []
    return {
        "lotes_diferidos": diferidos,
        "total_diferidos": len(diferidos),
        "total_pollos": sum(d.get("cantidad", 0) for d in diferidos),
    }


@app.delete("/proyeccion/lotes-diferidos")
def clear_lotes_diferidos(current_user: TokenData = Depends(get_current_user)):
    """Limpia todos los lotes diferidos."""
    storage.delete_lotes_diferidos()
    return {"message": "Lotes diferidos limpiados."}


# ─── Semana 2: Edición interactiva (mover, eliminar, enviar a S1) ───────────────

def _get_proyeccion_s2() -> Optional[SemanaFaena]:
    """Lee la proyección S2 persistida."""
    data = storage.load_proyeccion_s2()
    if data:
        try:
            return SemanaFaena(**data)
        except Exception:
            return None
    return None


@app.post("/proyeccion/semana2/mover-lote")
def mover_lote_s2(req: MoverLoteS2Request, current_user: TokenData = Depends(get_current_user)):
    """Mover un lote de un día a otro dentro de semana 2."""
    semana2 = _get_proyeccion_s2()
    if semana2 is None:
        raise HTTPException(404, "No hay proyección de semana 2 generada. Genere primero la proyección.")

    if req.dia_origen < 0 or req.dia_origen >= len(semana2.dias) \
       or req.dia_destino < 0 or req.dia_destino >= len(semana2.dias):
        raise HTTPException(400, "Índice de día inválido")

    dia_origen = semana2.dias[req.dia_origen]
    dia_destino = semana2.dias[req.dia_destino]

    if req.lote_index < 0 or req.lote_index >= len(dia_origen.lotes):
        raise HTTPException(400, "Índice de lote inválido")

    lote = dia_origen.lotes.pop(req.lote_index)
    params = _get_parametros()
    nueva_fecha = dia_destino.fecha

    fecha_peso = lote.fecha_peso_original or lote.fecha_fin_retiro
    ganancia = lote.ganancia_diaria_original if lote.ganancia_diaria_original is not None else params.ganancia_diaria_macho
    fecha_ingreso = lote.fecha_ingreso_original or fecha_peso

    oferta_equiv = LoteOferta(
        fecha_peso=fecha_peso,
        granja=lote.granja,
        galpon=lote.galpon,
        nucleo=lote.nucleo,
        cantidad=lote.cantidad,
        sexo=lote.sexo,
        edad_proyectada=lote.edad_actual,
        peso_muestreo_proy=lote.peso_actual,
        ganancia_diaria=ganancia,
        dias_proyectados=0,
        edad_real=lote.edad_actual,
        peso_muestreo_real=lote.peso_actual,
        fecha_ingreso=fecha_ingreso,
    )

    nuevo_lote = _copiar_metadata_lote(
        lote,
        calcular_lote_proyectado(oferta_equiv, nueva_fecha, params),
    )
    dia_destino.lotes.append(nuevo_lote)

    semana2.dias[req.dia_origen] = calcular_dia_faena(
        dia_origen.fecha, dia_origen.lotes, params=params,
        gallinas_cantidad=dia_origen.gallinas_cantidad,
        gallinas_livianas=dia_origen.gallinas_livianas_cantidad,
        gallinas_pesadas=dia_origen.gallinas_pesadas_cantidad,
    )
    semana2.dias[req.dia_destino] = calcular_dia_faena(
        dia_destino.fecha, dia_destino.lotes, params=params,
        gallinas_cantidad=dia_destino.gallinas_cantidad,
        gallinas_livianas=dia_destino.gallinas_livianas_cantidad,
        gallinas_pesadas=dia_destino.gallinas_pesadas_cantidad,
    )

    resultado = calcular_semana_faena(
        semana2.fecha_inicio, semana2.dias, params,
        lotes_no_asignados=semana2.lotes_no_asignados,
        lotes_fuera_rango=semana2.lotes_fuera_rango,
    )
    resultado.feriados_aplicados = semana2.feriados_aplicados
    resultado.eventos_gallinas = semana2.eventos_gallinas
    storage.save_proyeccion_s2(resultado.model_dump())

    return {"proyeccion": resultado.model_dump()}


@app.delete("/proyeccion/semana2/lote/{dia_index}/{lote_index}")
def eliminar_lote_s2(dia_index: int, lote_index: int, current_user: TokenData = Depends(get_current_user)):
    """Eliminar un lote de la proyección de semana 2."""
    semana2 = _get_proyeccion_s2()
    if semana2 is None:
        raise HTTPException(404, "No hay proyección de semana 2 generada.")

    if dia_index < 0 or dia_index >= len(semana2.dias):
        raise HTTPException(400, "Índice de día inválido")

    dia = semana2.dias[dia_index]
    if lote_index < 0 or lote_index >= len(dia.lotes):
        raise HTTPException(400, "Índice de lote inválido")

    dia.lotes.pop(lote_index)
    params = _get_parametros()

    semana2.dias[dia_index] = calcular_dia_faena(
        dia.fecha, dia.lotes, params=params,
        gallinas_cantidad=dia.gallinas_cantidad,
        gallinas_livianas=dia.gallinas_livianas_cantidad,
        gallinas_pesadas=dia.gallinas_pesadas_cantidad,
    )
    resultado = calcular_semana_faena(
        semana2.fecha_inicio, semana2.dias, params,
        lotes_no_asignados=semana2.lotes_no_asignados,
        lotes_fuera_rango=semana2.lotes_fuera_rango,
    )
    resultado.feriados_aplicados = semana2.feriados_aplicados
    resultado.eventos_gallinas = semana2.eventos_gallinas
    storage.save_proyeccion_s2(resultado.model_dump())

    return resultado.model_dump()


@app.post("/proyeccion/semana2/enviar-semana1")
def enviar_lote_s2_a_s1(req: EnviarS1Request, current_user: TokenData = Depends(get_current_user)):
    """
    Envía un lote desde semana 2 de vuelta a semana 1.
    Lo remueve de la proyección S2 y lo agrega al día indicado de S1
    (o al de mayor déficit si no se indica).
    """
    semana2 = _get_proyeccion_s2()
    if semana2 is None:
        raise HTTPException(404, "No hay proyección de semana 2 generada.")

    semana1 = _get_proyeccion()
    if semana1 is None:
        raise HTTPException(404, "No hay proyección de semana 1 generada.")

    if req.dia_index_s2 < 0 or req.dia_index_s2 >= len(semana2.dias):
        raise HTTPException(400, "Índice de día S2 inválido")

    dia_s2 = semana2.dias[req.dia_index_s2]
    if req.lote_index_s2 < 0 or req.lote_index_s2 >= len(dia_s2.lotes):
        raise HTTPException(400, "Índice de lote S2 inválido")

    lote = dia_s2.lotes.pop(req.lote_index_s2)
    params = _get_parametros()

    # Reconstruir LoteOferta desde datos originales
    fecha_peso = lote.fecha_peso_original or lote.fecha_fin_retiro
    ganancia = lote.ganancia_diaria_original if lote.ganancia_diaria_original is not None else params.ganancia_diaria_macho
    fecha_ingreso = lote.fecha_ingreso_original or fecha_peso

    oferta_equiv = LoteOferta(
        fecha_peso=fecha_peso,
        granja=lote.granja,
        galpon=lote.galpon,
        nucleo=lote.nucleo,
        cantidad=lote.cantidad,
        sexo=lote.sexo,
        edad_proyectada=lote.edad_actual,
        peso_muestreo_proy=lote.peso_actual,
        ganancia_diaria=ganancia,
        dias_proyectados=0,
        edad_real=lote.edad_actual,
        peso_muestreo_real=lote.peso_actual,
        fecha_ingreso=fecha_ingreso,
    )

    # Determinar día destino en S1
    if req.dia_destino_s1 is not None:
        if req.dia_destino_s1 < 0 or req.dia_destino_s1 >= len(semana1.dias):
            raise HTTPException(400, "Índice de día destino S1 inválido")
        dia_destino_idx = req.dia_destino_s1
    else:
        objetivo = params.pollos_diarios_objetivo_max
        mejor_idx = 0
        mayor_deficit = -1
        for idx, d in enumerate(semana1.dias):
            deficit = objetivo - d.total_pollos
            if deficit > mayor_deficit:
                mayor_deficit = deficit
                mejor_idx = idx
        dia_destino_idx = mejor_idx

    dia_destino_s1 = semana1.dias[dia_destino_idx]
    nuevo_lote = _copiar_metadata_lote(
        lote,
        calcular_lote_proyectado(oferta_equiv, dia_destino_s1.fecha, params),
    )
    dia_destino_s1.lotes.append(nuevo_lote)

    # Recalcular S1
    semana1.dias[dia_destino_idx] = calcular_dia_faena(
        dia_destino_s1.fecha, dia_destino_s1.lotes, params=params,
        gallinas_cantidad=dia_destino_s1.gallinas_cantidad,
        gallinas_livianas=dia_destino_s1.gallinas_livianas_cantidad,
        gallinas_pesadas=dia_destino_s1.gallinas_pesadas_cantidad,
    )
    resultado_s1 = calcular_semana_faena(
        semana1.fecha_inicio, semana1.dias, params,
        lotes_no_asignados=semana1.lotes_no_asignados,
        lotes_fuera_rango=semana1.lotes_fuera_rango,
    )
    resultado_s1.feriados_aplicados = semana1.feriados_aplicados
    resultado_s1.eventos_gallinas = semana1.eventos_gallinas
    storage.save_proyeccion(resultado_s1.model_dump())

    # Recalcular S2
    semana2.dias[req.dia_index_s2] = calcular_dia_faena(
        dia_s2.fecha, dia_s2.lotes, params=params,
        gallinas_cantidad=dia_s2.gallinas_cantidad,
        gallinas_livianas=dia_s2.gallinas_livianas_cantidad,
        gallinas_pesadas=dia_s2.gallinas_pesadas_cantidad,
    )
    resultado_s2 = calcular_semana_faena(
        semana2.fecha_inicio, semana2.dias, params,
        lotes_no_asignados=semana2.lotes_no_asignados,
        lotes_fuera_rango=semana2.lotes_fuera_rango,
    )
    resultado_s2.feriados_aplicados = semana2.feriados_aplicados
    resultado_s2.eventos_gallinas = semana2.eventos_gallinas
    storage.save_proyeccion_s2(resultado_s2.model_dump())

    # Limpiar el lote de diferidos si corresponde
    diferidos = storage.load_lotes_diferidos() or []
    diferidos_actualizados = [
        d for d in diferidos
        if not (d["granja"] == lote.granja and d["galpon"] == lote.galpon
                and d["nucleo"] == lote.nucleo and d["cantidad"] == lote.cantidad)
    ]
    if len(diferidos_actualizados) != len(diferidos):
        storage.save_lotes_diferidos(diferidos_actualizados)

    return {
        "proyeccion_s1": resultado_s1.model_dump(),
        "proyeccion_s2": resultado_s2.model_dump(),
        "dia_destino_s1": dia_destino_idx,
        "total_diferidos": len(diferidos_actualizados),
    }


# ─── Sugerencias inteligentes de diferimiento ───────────────────────────────────

@app.get("/proyeccion/sugerencias-diferimiento")
def get_sugerencias_diferimiento(current_user: TokenData = Depends(get_current_user)):
    """
    Analiza la proyección actual y sugiere lotes candidatos a diferir a S2.
    Criterios: sobrecarga, mejor calibre en S2, feriado cercano, edad temprana.
    Las sugerencias son orientativas — el planificador decide.
    """
    semana = _get_proyeccion()
    if semana is None:
        raise HTTPException(404, "No hay proyección generada aún.")

    ofertas = _get_ofertas()
    if not ofertas:
        return {"total_sugerencias": 0, "sugerencias": [], "por_criterio": {}, "total_pollos_sugeridos": 0}

    params = _get_parametros()

    # Obtener feriados del rango de la semana actual
    feriados = None
    try:
        feriados_custom = storage.load_feriados_custom() or []
        fecha_fin_rango = semana.fecha_inicio + timedelta(days=13)
        feriados = obtener_feriados_rango(
            semana.fecha_inicio, fecha_fin_rango,
            feriados_custom=feriados_custom if feriados_custom else None,
        )
    except Exception:
        pass

    return generar_sugerencias_diferimiento(
        semana=semana,
        ofertas=ofertas,
        params=params,
        feriados=feriados,
    )


# ─── Pronóstico de Pesos ────────────────────────────────────────────────────────

@app.get("/pronostico/pesos")
def get_pronostico_pesos(current_user: TokenData = Depends(get_current_user)):
    """
    Analiza cada lote de la oferta/proyección y pronostica si llegará
    al peso ideal para faena. Genera alertas por lote, por día y por granja.
    """
    params = _get_parametros()
    proyeccion = _get_proyeccion()
    ofertas = _get_ofertas()

    if proyeccion is None:
        raise HTTPException(404, "No hay proyección generada.")
    if not ofertas:
        raise HTTPException(404, "No hay ofertas cargadas.")

    # Indexar ofertas por (granja, galpon, nucleo) para cruzar con lotes proyectados
    oferta_map = {}
    for o in ofertas:
        key = (o.granja, o.galpon, o.nucleo)
        oferta_map[key] = o

    lotes_pronostico = []
    alertas_criticas = 0
    alertas_moderadas = 0
    lotes_ok = 0
    granjas_stats = {}  # granja -> {total, ok, moderado, critico}

    for dia_idx, dia in enumerate(proyeccion.dias):
        for lote in dia.lotes:
            if lote.es_compra_terceros:
                continue

            peso_proyectado = lote.peso_vivo_retiro
            peso_faen = lote.peso_faenado

            # Determinar ganancia diaria esperada vs la que necesitaría
            oferta_orig = oferta_map.get((lote.granja, lote.galpon, lote.nucleo))
            ganancia_usada = None
            peso_muestreo = None
            edad_muestreo = None
            ganancia_esperada = None

            if oferta_orig:
                ganancia_usada = oferta_orig.ganancia_diaria
                peso_muestreo = oferta_orig.peso_muestreo_proy
                edad_muestreo = oferta_orig.edad_proyectada
                if oferta_orig.sexo.upper() == "H":
                    ganancia_esperada = params.ganancia_diaria_hembra
                else:
                    ganancia_esperada = params.ganancia_diaria_macho

            # Clasificar estado del peso
            if peso_proyectado < params.peso_min_faena:
                deficit = params.peso_min_faena - peso_proyectado
                if deficit > 0.15:
                    nivel = "critico"
                    alertas_criticas += 1
                else:
                    nivel = "moderado"
                    alertas_moderadas += 1
                mensaje = f"Bajo peso: {peso_proyectado:.3f} kg (mín {params.peso_min_faena:.2f})"
            elif peso_proyectado > params.peso_max_faena:
                exceso = peso_proyectado - params.peso_max_faena
                if exceso > 0.15:
                    nivel = "critico"
                    alertas_criticas += 1
                else:
                    nivel = "moderado"
                    alertas_moderadas += 1
                mensaje = f"Sobrepeso: {peso_proyectado:.3f} kg (máx {params.peso_max_faena:.2f})"
            else:
                nivel = "normal"
                lotes_ok += 1
                # Sub-alertar si está en el borde (dentro de 50g del límite)
                margen_inf = peso_proyectado - params.peso_min_faena
                margen_sup = params.peso_max_faena - peso_proyectado
                if margen_inf < 0.05:
                    mensaje = f"En rango pero cerca del mínimo ({margen_inf*1000:.0f}g de margen)"
                elif margen_sup < 0.05:
                    mensaje = f"En rango pero cerca del máximo ({margen_sup*1000:.0f}g de margen)"
                else:
                    mensaje = "Peso dentro del rango ideal"

            # Diferencia respecto al peso objetivo de recepción
            dif_vs_objetivo = round(peso_proyectado - params.peso_objetivo_recepcion, 3)

            # Tracking por granja
            if lote.granja not in granjas_stats:
                granjas_stats[lote.granja] = {
                    "total": 0, "ok": 0, "moderado": 0, "critico": 0,
                    "pollos_total": 0, "suma_peso": 0.0,
                }
            gs = granjas_stats[lote.granja]
            gs["total"] += 1
            gs["ok" if nivel == "normal" else nivel] += 1
            gs["pollos_total"] += lote.cantidad
            gs["suma_peso"] += peso_proyectado * lote.cantidad

            lotes_pronostico.append({
                "dia_index": dia_idx,
                "fecha": dia.fecha.isoformat(),
                "granja": lote.granja,
                "galpon": lote.galpon,
                "nucleo": lote.nucleo,
                "cantidad": lote.cantidad,
                "sexo": lote.sexo,
                "edad_fin_retiro": lote.edad_fin_retiro,
                "peso_muestreo": peso_muestreo,
                "peso_proyectado": round(peso_proyectado, 3),
                "peso_faenado": round(peso_faen, 3),
                "peso_min": params.peso_min_faena,
                "peso_max": params.peso_max_faena,
                "peso_objetivo": params.peso_objetivo_recepcion,
                "dif_vs_objetivo": dif_vs_objetivo,
                "ganancia_diaria_lote": ganancia_usada,
                "ganancia_esperada": ganancia_esperada,
                "ganancia_deficiente": (
                    ganancia_usada is not None
                    and ganancia_esperada is not None
                    and ganancia_usada < ganancia_esperada * 0.9
                ),
                "nivel": nivel,
                "mensaje": mensaje,
                "calibre": lote.calibre_promedio,
            })

    # Resumen por día
    dias_resumen = []
    for dia_idx, dia in enumerate(proyeccion.dias):
        lotes_dia = [l for l in lotes_pronostico if l["dia_index"] == dia_idx]
        if not lotes_dia:
            continue
        total_pollos = sum(l["cantidad"] for l in lotes_dia)
        peso_prom = (
            sum(l["peso_proyectado"] * l["cantidad"] for l in lotes_dia) / total_pollos
            if total_pollos > 0 else 0
        )
        criticos = sum(1 for l in lotes_dia if l["nivel"] == "critico")
        moderados = sum(1 for l in lotes_dia if l["nivel"] == "moderado")
        if criticos > 0:
            nivel_dia = "critico"
        elif moderados > 0:
            nivel_dia = "moderado"
        else:
            nivel_dia = "normal"

        dias_resumen.append({
            "dia_index": dia_idx,
            "fecha": dia.fecha.isoformat(),
            "total_pollos": total_pollos,
            "peso_promedio": round(peso_prom, 3),
            "lotes_total": len(lotes_dia),
            "lotes_criticos": criticos,
            "lotes_moderados": moderados,
            "lotes_ok": len(lotes_dia) - criticos - moderados,
            "nivel": nivel_dia,
        })

    # Resumen por granja
    granjas_resumen = []
    for granja, stats in sorted(granjas_stats.items()):
        peso_prom = (
            stats["suma_peso"] / stats["pollos_total"]
            if stats["pollos_total"] > 0 else 0
        )
        if stats["critico"] > 0:
            nivel_granja = "critico"
        elif stats["moderado"] > 0:
            nivel_granja = "moderado"
        else:
            nivel_granja = "normal"
        granjas_resumen.append({
            "granja": granja,
            "total_lotes": stats["total"],
            "lotes_ok": stats["ok"],
            "lotes_moderados": stats["moderado"],
            "lotes_criticos": stats["critico"],
            "pollos_total": stats["pollos_total"],
            "peso_promedio": round(peso_prom, 3),
            "nivel": nivel_granja,
        })

    total_lotes = len(lotes_pronostico)
    return {
        "total_lotes": total_lotes,
        "lotes_ok": lotes_ok,
        "alertas_moderadas": alertas_moderadas,
        "alertas_criticas": alertas_criticas,
        "pct_ok": round(lotes_ok / total_lotes * 100, 1) if total_lotes > 0 else 0,
        "peso_min_faena": params.peso_min_faena,
        "peso_max_faena": params.peso_max_faena,
        "peso_objetivo": params.peso_objetivo_recepcion,
        "lotes": lotes_pronostico,
        "dias": dias_resumen,
        "granjas": granjas_resumen,
    }


# ─── Sinc. Operativa / Validación Cruzada ──────────────────────────────────────

@app.get("/validacion-cruzada")
def get_validacion_cruzada(current_user: TokenData = Depends(get_current_user)):
    """
    Retorna el estado completo de sincronización operativa entre oferta y producción.

    Combina:
    - Factibilidad: cobertura oferta vs producción propia (tasas de mortalidad)
    - Cohortes: oferta vs expectativa de aves en faena por semana de producción
    - Consistencia de edad: detecta lotes con edad_real inconsistente
    - Fuentes: metadata de los archivos cargados
    - Insights: lista de observaciones priorizadas sobre los datos

    Retorna 404 si no hay ni oferta ni producción cargadas.
    """
    ofertas = _get_ofertas()
    produccion_data = storage.load_produccion()

    tiene_oferta = bool(ofertas)
    tiene_produccion = bool(produccion_data)

    if not tiene_oferta and not tiene_produccion:
        raise HTTPException(404, "No hay oferta ni producción cargadas.")

    validacion: dict = {}
    if tiene_oferta and tiene_produccion:
        validacion = _validar_cruce_oferta(ofertas) or {}

    insights = _generar_insights_validacion(validacion)

    fuentes = _build_fuentes_validacion(ofertas, produccion_data)

    return {
        "tiene_oferta": tiene_oferta,
        "tiene_produccion": tiene_produccion,
        "validacion": validacion,
        "insights": insights,
        "fuentes": fuentes,
    }


# ─── Alerta Temprana ────────────────────────────────────────────────────────────

@app.get("/pronostico/alerta-temprana")
def get_alerta_temprana(current_user: TokenData = Depends(get_current_user)):
    """
    Analiza todos los lotes de la oferta y proyecta anticipadamente
    cuáles llegarán al rango de peso ideal para faena y cuáles no.
    Permite detectar problemas de peso días antes de la semana de faena.
    Incluye validación cruzada entre oferta y cargas de pollitos BB.
    """
    params = _get_parametros()
    config = _get_produccion_reference_config(params)
    ofertas = _get_ofertas()

    if not ofertas:
        raise HTTPException(404, "No hay ofertas cargadas.")

    resultado = calcular_alerta_temprana(ofertas, params)

    # Cruce oferta vs producción: expectativa por cohorte
    prod_data = storage.load_produccion()
    resultado["validacion_mortalidad"] = validar_mortalidad_oferta(
        ofertas,
        prod_data or [],
        dias_hasta_faena=config["dias_hasta_faena"],
        tolerancia_dias=config["tolerancia_dias"],
        merma_min=params.produccion_mortalidad_min,
        merma_max=params.produccion_mortalidad_max,
    )

    return resultado
