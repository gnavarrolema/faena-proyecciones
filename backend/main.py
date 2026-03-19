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
)
from .parser_excel import leer_oferta_excel
from .parser_produccion import (
    leer_produccion_excel, simular_mortalidad,
    SemanaProduccion, TASAS_MORTALIDAD_DEFAULT, DIAS_HASTA_FAENA,
)
from .feriados import obtener_feriados_nacionales, obtener_feriados_rango
from .config import CORS_ORIGINS, CORS_ALLOW_CREDENTIALS
from . import storage

logger = logging.getLogger(__name__)


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


def _get_proyeccion() -> Optional[SemanaFaena]:
    """Lee proyección desde storage. Devuelve None si no existe."""
    data = storage.load_proyeccion()
    if data:
        try:
            return SemanaFaena(**data)
        except Exception as e:
            logger.warning(f"Error leyendo proyección de storage: {e}")
    return None


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
    tasa_mortalidad: Optional[float] = None  # ej: 0.065 (6.5%)


class CompararEscenariosRequest(BaseModel):
    """Para comparar escenarios por IDs."""
    ids: List[str]


class FactibilidadProduccion(BaseModel):
    """Resultado de cruzar oferta vs producción propia."""
    encontrada: bool
    pollitos_cargados: Optional[int] = None
    disponibles_mejor: Optional[int] = None   # al 4.5% mortalidad
    disponibles_peor: Optional[int] = None     # al 6.5% mortalidad
    total_oferta: int = 0
    deficit_peor: Optional[int] = None          # oferta - disponibles_peor (si >0)
    cobertura_pct_peor: Optional[float] = None  # (oferta / disponibles_peor) * 100
    coberturas: Optional[list] = None           # [{tasa, disponibles, cobertura_pct}, ...]


class ReferenciaProduccionResponse(BaseModel):
    """Respuesta del endpoint de referencia de producción."""
    encontrada: bool
    semana_produccion: Optional[dict] = None
    total_oferta_actual: int = 0
    cobertura_pct: Optional[float] = None
    coberturas: Optional[list] = None  # [{tasa, disponibles, cobertura_pct}, ...]
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


# ─── Helpers: factibilidad producción ─────────────────────────────────────────

def _calcular_factibilidad(
    fecha_inicio_semana: date,
    total_oferta: int,
) -> Optional[FactibilidadProduccion]:
    """Cruza oferta con producción cargada para evaluar factibilidad."""
    data = storage.load_produccion()
    if not data:
        return None

    semanas = [SemanaProduccion(**s) for s in data]
    TOLERANCIA_DIAS = 3

    semana_encontrada = None
    for sem in semanas:
        fecha_faena_estimada = sem.fecha_desde + timedelta(days=DIAS_HASTA_FAENA)
        if abs((fecha_faena_estimada - fecha_inicio_semana).days) <= TOLERANCIA_DIAS:
            semana_encontrada = sem
            break

    if semana_encontrada is None:
        return FactibilidadProduccion(encontrada=False, total_oferta=total_oferta)

    simulacion = simular_mortalidad([semana_encontrada])
    sims = simulacion[0].simulaciones

    disponibles_mejor = sims[0].pollitos_disponibles   # 4.5%
    disponibles_peor = sims[-1].pollitos_disponibles    # 6.5%
    deficit = max(0, total_oferta - disponibles_peor)
    cobertura = round((total_oferta / disponibles_peor * 100), 1) if disponibles_peor > 0 else None

    coberturas = []
    for sim in sims:
        cob_pct = round((total_oferta / sim.pollitos_disponibles * 100), 1) if sim.pollitos_disponibles > 0 else None
        coberturas.append({
            "tasa": round(sim.tasa_mortalidad * 100, 1),
            "disponibles": sim.pollitos_disponibles,
            "cobertura_pct": cob_pct,
        })

    return FactibilidadProduccion(
        encontrada=True,
        pollitos_cargados=semana_encontrada.pollitos_cargados,
        disponibles_mejor=disponibles_mejor,
        disponibles_peor=disponibles_peor,
        total_oferta=total_oferta,
        deficit_peor=deficit if deficit > 0 else None,
        cobertura_pct_peor=cobertura,
        coberturas=coberturas,
    )


def _calcular_deficit_produccion(proyeccion: SemanaFaena) -> Optional[dict]:
    """Calcula déficit de producción propia vs oferta para la recomendación de terceros."""
    fact = _calcular_factibilidad(
        fecha_inicio_semana=proyeccion.fecha_inicio,
        total_oferta=proyeccion.total_pollos_semana,
    )
    if fact is None or not fact.encontrada:
        return None

    hay_deficit = fact.deficit_peor is not None and fact.deficit_peor > 0
    return {
        "encontrada": True,
        "pollitos_cargados": fact.pollitos_cargados,
        "disponibles_peor": fact.disponibles_peor,
        "disponibles_mejor": fact.disponibles_mejor,
        "total_oferta": fact.total_oferta,
        "deficit_peor": fact.deficit_peor,
        "cobertura_pct_peor": fact.cobertura_pct_peor,
        "hay_deficit": hay_deficit,
        "recomendacion_terceros": (
            f"La producción propia ({fact.disponibles_peor:,} al 6.5% mort.) "
            f"no cubre la oferta ({fact.total_oferta:,}). "
            f"Se recomienda adquirir ~{fact.deficit_peor:,} pollos a terceros."
        ) if hay_deficit else None,
    }


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
    """Actualizar parámetros de cálculo."""
    current = _get_parametros().model_dump()
    for key, value in update.model_dump(exclude_none=True).items():
        current[key] = value
    params = Parametros(**current)
    storage.save_parametros(params.model_dump())
    return params


@app.post("/oferta/upload")
async def upload_oferta(file: UploadFile = File(...), sheet_name: Optional[str] = None, current_user: TokenData = Depends(get_current_user)):
    """
    Subir archivo Excel de oferta de granjas.
    Acepta formato OFERTA JUEV o similar.
    """
    if not file.filename.endswith(('.xlsx', '.xls')):
        raise HTTPException(400, "El archivo debe ser .xlsx o .xls")

    content = await file.read()
    try:
        ofertas = leer_oferta_excel(content, sheet_name)
    except Exception as e:
        raise HTTPException(400, f"Error al leer el archivo: {str(e)}")

    # Persistir ofertas y archivo original
    storage.save_ofertas([o.model_dump() for o in ofertas])
    storage.save_upload(file.filename, content)

    # Resumen por granja
    resumen = {}
    for o in ofertas:
        if o.granja not in resumen:
            resumen[o.granja] = {"lotes": 0, "pollos": 0}
        resumen[o.granja]["lotes"] += 1
        resumen[o.granja]["pollos"] += o.cantidad

    return {
        "total_lotes": len(ofertas),
        "total_pollos": sum(o.cantidad for o in ofertas),
        "granjas": resumen,
        "ofertas": [o.model_dump() for o in ofertas],
    }


@app.get("/oferta")
def get_oferta(current_user: TokenData = Depends(get_current_user)):
    """Obtener oferta cargada."""
    ofertas = _get_ofertas()
    return {
        "total_lotes": len(ofertas),
        "total_pollos": sum(o.cantidad for o in ofertas),
        "ofertas": [o.model_dump() for o in ofertas],
    }


@app.delete("/oferta")
def clear_oferta(current_user: TokenData = Depends(get_current_user)):
    """Limpiar la oferta cargada."""
    storage.delete_ofertas()
    storage.delete_ofertas_martes()
    storage.delete_proyeccion()
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
    if not file.filename.endswith(('.xlsx', '.xls')):
        raise HTTPException(400, "El archivo debe ser .xlsx o .xls")

    # Verificar que existe una proyección para ajustar
    semana = _get_proyeccion()
    if semana is None:
        raise HTTPException(400, "No hay proyección existente para ajustar. Genere una primero desde la pestaña Oferta.")

    content = await file.read()
    try:
        ofertas_martes = leer_oferta_excel(content, sheet_name)
    except Exception as e:
        raise HTTPException(400, f"Error al leer el archivo: {str(e)}")

    if not ofertas_martes:
        raise HTTPException(400, "El archivo no contiene lotes válidos.")

    # Guardar oferta martes y archivo original
    storage.save_ofertas_martes([o.model_dump() for o in ofertas_martes])
    storage.save_upload(file.filename, content)

    # Aplicar ajuste
    params = _get_parametros()
    resultado, resumen = aplicar_ajuste_martes(ofertas_martes, semana, params)

    # Guardar proyección actualizada
    storage.save_proyeccion(resultado.model_dump())

    return {
        "proyeccion": resultado.model_dump(),
        "resumen_ajuste": resumen.model_dump(),
    }


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

    # Obtener feriados del rango de la semana
    fecha_fin = req.fecha_inicio_semana + timedelta(days=13)  # rango amplio
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
    )

    # Persistir proyección y parámetros usados
    storage.save_proyeccion(semana.model_dump())
    storage.save_parametros(params.model_dump())

    # ── Factibilidad: cruzar oferta vs producción propia ──
    factibilidad = _calcular_factibilidad(
        fecha_inicio_semana=req.fecha_inicio_semana,
        total_oferta=semana.total_pollos_semana,
    )

    result = semana.model_dump()
    result["factibilidad_produccion"] = factibilidad.model_dump() if factibilidad else None
    return result


@app.get("/proyeccion")
def get_proyeccion(current_user: TokenData = Depends(get_current_user)):
    """Obtener la proyección actual."""
    proyeccion = _get_proyeccion()
    if proyeccion is None:
        raise HTTPException(404, "No hay proyección generada aún.")
    result = proyeccion.model_dump()
    factibilidad = _calcular_factibilidad(
        fecha_inicio_semana=proyeccion.fecha_inicio,
        total_oferta=proyeccion.total_pollos_semana,
    )
    result["factibilidad_produccion"] = factibilidad.model_dump() if factibilidad else None
    return result


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

    nuevo_lote = calcular_lote_proyectado(oferta_equiv, nueva_fecha, params)
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

        nuevo_lote = calcular_lote_proyectado(oferta_equiv, semana.dias[mejor_idx].fecha, params)
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
    semana.dias[dia_index] = calcular_dia_faena(
        dia.fecha, dia.lotes, params=params,
        gallinas_cantidad=dia.gallinas_cantidad,
        gallinas_livianas=dia.gallinas_livianas_cantidad,
        gallinas_pesadas=dia.gallinas_pesadas_cantidad,
    )
    params = _get_parametros()
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
    if not file.filename.endswith(('.xlsx', '.xls')):
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
    storage.save_upload(file.filename, content)

    return {
        "total_semanas": len(semanas),
        "total_pollitos": sum(s.pollitos_cargados for s in semanas),
        "semanas": [s.model_dump() for s in semanas],
    }


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
    Retorna simulación de mortalidad a 5 tasas (4.5%–6.5%)
    para cada semana de producción cargada.
    """
    data = storage.load_produccion()
    if not data:
        raise HTTPException(404, "No hay datos de producción cargados.")

    semanas = [SemanaProduccion(**s) for s in data]
    resultado = simular_mortalidad(semanas)
    return {
        "tasas": [t * 100 for t in TASAS_MORTALIDAD_DEFAULT],
        "simulacion": [r.model_dump() for r in resultado],
    }


@app.get("/produccion/referencia")
def get_referencia_produccion(
    fecha_faena: date,
    current_user: TokenData = Depends(get_current_user),
) -> ReferenciaProduccionResponse:
    """
    Busca la semana de producción cuya fecha_desde + 42 días
    cae dentro de la semana de faena indicada (±3 días de tolerancia).
    Sirve como referencia macro para validar que la oferta cubra todos los lotes.
    """
    data = storage.load_produccion()
    if not data:
        return ReferenciaProduccionResponse(
            encontrada=False,
            mensaje="No hay datos de producción cargados.",
        )

    semanas = [SemanaProduccion(**s) for s in data]
    TOLERANCIA_DIAS = 3

    semana_encontrada = None
    for sem in semanas:
        fecha_faena_estimada = sem.fecha_desde + timedelta(days=DIAS_HASTA_FAENA)
        if abs((fecha_faena_estimada - fecha_faena).days) <= TOLERANCIA_DIAS:
            semana_encontrada = sem
            break

    if semana_encontrada is None:
        return ReferenciaProduccionResponse(
            encontrada=False,
            mensaje=f"No se encontró semana de producción para fecha de faena {fecha_faena.isoformat()}.",
        )

    simulacion = simular_mortalidad([semana_encontrada])
    sim_data = simulacion[0].model_dump()

    # Cobertura: oferta actual vs disponible al 6.5%
    proyeccion = _get_proyeccion()
    total_oferta = proyeccion.total_pollos_semana if proyeccion else 0

    disponible_65 = int(semana_encontrada.pollitos_cargados * (1 - 0.065))
    cobertura = round((total_oferta / disponible_65 * 100), 1) if disponible_65 > 0 else None

    # Coberturas multi-escenario (5 tasas)
    coberturas = []
    for sim_fila in simulacion[0].simulaciones:
        cob_pct = round((total_oferta / sim_fila.pollitos_disponibles * 100), 1) if sim_fila.pollitos_disponibles > 0 else None
        coberturas.append({
            "tasa": round(sim_fila.tasa_mortalidad * 100, 1),
            "disponibles": sim_fila.pollitos_disponibles,
            "cobertura_pct": cob_pct,
        })

    return ReferenciaProduccionResponse(
        encontrada=True,
        semana_produccion=sim_data,
        total_oferta_actual=total_oferta,
        cobertura_pct=cobertura,
        coberturas=coberturas,
        mensaje="Referencia encontrada.",
    )


@app.delete("/produccion")
def clear_produccion(current_user: TokenData = Depends(get_current_user)):
    """Limpiar datos de producción."""
    storage.delete_produccion()
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

    from backend.parser_produccion import (
        SemanaProduccion, DIAS_HASTA_FAENA, TASAS_MORTALIDAD_DEFAULT,
    )

    semanas_prod = [SemanaProduccion(**r) for r in raw]
    hoy = date.today()
    tolerancia = 3

    result_semanas = []
    for i in range(semanas):
        inicio_sem = hoy + timedelta(weeks=i)
        fin_sem = inicio_sem + timedelta(days=6)

        # Buscar semanas de producción cuya faena caiga en este rango
        matched = []
        for sp in semanas_prod:
            faena_est = sp.fecha_desde + timedelta(days=DIAS_HASTA_FAENA)
            if inicio_sem - timedelta(days=tolerancia) <= faena_est <= fin_sem + timedelta(days=tolerancia):
                matched.append(sp)

        total_cargados = sum(s.pollitos_cargados for s in matched)
        mejor_tasa = min(TASAS_MORTALIDAD_DEFAULT)
        peor_tasa = max(TASAS_MORTALIDAD_DEFAULT)

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
    con los pollos realmente recibidos en faena (de la proyección + pesos reales).
    Muestra la tendencia: ¿la mortalidad real es mayor o menor a lo estimado?
    """
    prod_data = storage.load_produccion()
    if not prod_data:
        raise HTTPException(404, "No hay datos de producción cargados.")

    proyeccion = _get_proyeccion()
    if proyeccion is None:
        raise HTTPException(404, "No hay proyección generada.")

    semanas_prod = [SemanaProduccion(**s) for s in prod_data]
    tolerancia = 3

    puntos = []
    for sp in semanas_prod:
        fecha_faena_est = sp.fecha_desde + timedelta(days=DIAS_HASTA_FAENA)

        # Buscar el día de faena que coincida con esta semana de producción
        pollos_recibidos = 0
        dias_match = 0
        for dia in proyeccion.dias:
            if abs((dia.fecha - fecha_faena_est).days) <= tolerancia:
                pollos_recibidos += dia.total_pollos
                dias_match += 1

        if dias_match == 0 or sp.pollitos_cargados == 0:
            continue

        # Mortalidad observada = 1 - (pollos_recibidos / pollitos_cargados)
        mortalidad_obs = 1 - (pollos_recibidos / sp.pollitos_cargados)
        mortalidad_obs = max(0, min(1, mortalidad_obs))  # clamp 0-100%
        mortalidad_pct = round(mortalidad_obs * 100, 2)

        # Comparar con tasas estándar
        mejor_tasa = min(TASAS_MORTALIDAD_DEFAULT) * 100  # 4.5
        peor_tasa = max(TASAS_MORTALIDAD_DEFAULT) * 100   # 6.5

        if mortalidad_pct <= mejor_tasa:
            evaluacion = "excelente"
        elif mortalidad_pct <= peor_tasa:
            evaluacion = "dentro_rango"
        else:
            evaluacion = "por_encima"

        puntos.append({
            "fecha_carga": sp.fecha_desde.isoformat(),
            "fecha_faena_estimada": fecha_faena_est.isoformat(),
            "pollitos_cargados": sp.pollitos_cargados,
            "pollos_recibidos": pollos_recibidos,
            "mortalidad_observada_pct": mortalidad_pct,
            "evaluacion": evaluacion,
        })

    if not puntos:
        return {
            "puntos": [],
            "resumen": None,
            "mensaje": "No se encontraron coincidencias entre producción y proyección para calcular mortalidad observada.",
        }

    # Resumen
    mortalidades = [p["mortalidad_observada_pct"] for p in puntos]
    promedio = round(sum(mortalidades) / len(mortalidades), 2)
    mejor_tasa_pct = min(TASAS_MORTALIDAD_DEFAULT) * 100
    peor_tasa_pct = max(TASAS_MORTALIDAD_DEFAULT) * 100

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

    def _generar_variante(etiqueta, descripcion, pollos_dia, dias, habilitar_sab):
        dias_eff = max(dias, 6) if habilitar_sab else dias
        semana = generar_proyeccion(
            ofertas=ofertas_base,
            fecha_inicio_semana=req.fecha_inicio_semana,
            dias_faena=dias_eff,
            pollos_por_dia=pollos_dia,
            params=params,
            feriados=feriados if feriados else None,
            gallinas=req.gallinas,
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
        # Conservador: objetivo bajo, sábado habilitado
        variantes.append(_generar_variante(
            "Conservador",
            "Carga diaria baja, sábado habilitado. Prioriza evitar horas extras.",
            params.pollos_diarios_objetivo_min,
            dias_base,
            True,
        ))

        # Equilibrado: objetivo del usuario, sábado solo si hay feriados
        variantes.append(_generar_variante(
            "Equilibrado",
            "Carga moderada. Sábado solo si hay feriados o gallinas.",
            req.pollos_por_dia,
            dias_base,
            tiene_feriados or tiene_gallinas,
        ))

        # Intensivo: objetivo alto, sin sábado
        variantes.append(_generar_variante(
            "Intensivo",
            "Carga máxima Lun-Vie. Sin sábado, acepta posibles horas extras.",
            params.pollos_diarios_objetivo_max,
            dias_base,
            False,
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
        fact = _calcular_factibilidad(
            fecha_inicio_semana=proyeccion.fecha_inicio,
            total_oferta=proyeccion.total_pollos_semana,
        )
        if fact and fact.encontrada:
            disponibles = int(fact.pollitos_cargados * (1 - tasa))
            deficit = max(0, proyeccion.total_pollos_semana - disponibles)
            cobertura = round(proyeccion.total_pollos_semana / disponibles * 100, 1) if disponibles > 0 else None
            produccion_analisis = {
                "tasa_mortalidad": tasa,
                "pollitos_cargados": fact.pollitos_cargados,
                "disponibles": disponibles,
                "deficit": deficit if deficit > 0 else None,
                "cobertura_pct": cobertura,
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
        dias_proyectados=0,
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
    nuevo_lote = calcular_lote_proyectado(oferta_equiv, dia_destino.fecha, params)
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

    Retorna la proyección como solo lectura (tentativa).
    """
    semana = _get_proyeccion()
    if semana is None:
        raise HTTPException(404, "No hay proyección generada aún.")

    diferidos = storage.load_lotes_diferidos() or []

    # Reunir lotes para semana 2 como LoteOferta
    ofertas_s2: list[LoteOferta] = []
    params = _get_parametros()

    # 1) Lotes diferidos → LoteOferta
    for d in diferidos:
        fecha_peso = date.fromisoformat(d["fecha_peso_original"]) if d.get("fecha_peso_original") else semana.fecha_inicio
        ganancia = d.get("ganancia_diaria_original") or params.ganancia_diaria_macho
        fecha_ingreso = date.fromisoformat(d["fecha_ingreso_original"]) if d.get("fecha_ingreso_original") else fecha_peso
        ofertas_s2.append(LoteOferta(
            fecha_peso=fecha_peso,
            granja=d["granja"],
            galpon=d["galpon"],
            nucleo=d["nucleo"],
            cantidad=d["cantidad"],
            sexo=d["sexo"],
            edad_proyectada=d["edad_actual"],
            peso_muestreo_proy=d["peso_actual"],
            ganancia_diaria=ganancia,
            dias_proyectados=0,
            edad_real=d["edad_actual"],
            peso_muestreo_real=d["peso_actual"],
            fecha_ingreso=fecha_ingreso,
        ))

    # 2) Lotes no asignados de semana 1 → buscar en ofertas originales
    ofertas_originales = _get_ofertas()
    if semana.lotes_no_asignados and ofertas_originales:
        ofertas_index: dict[tuple, LoteOferta] = {}
        for o in ofertas_originales:
            key = (o.granja, o.galpon, o.nucleo, o.sexo,
                   o.fecha_ingreso.isoformat() if o.fecha_ingreso else "")
            ofertas_index[key] = o
        for lote_na in semana.lotes_no_asignados:
            key = (lote_na.granja, lote_na.galpon, lote_na.nucleo, lote_na.sexo,
                   lote_na.fecha_ingreso.isoformat() if lote_na.fecha_ingreso else "")
            oferta_orig = ofertas_index.get(key)
            if oferta_orig:
                ofertas_s2.append(oferta_orig)

    if not ofertas_s2:
        return {
            "tiene_datos": False,
            "proyeccion": None,
            "lotes_diferidos": diferidos,
            "total_diferidos": len(diferidos),
            "mensaje": "No hay lotes diferidos ni no asignados para proyectar en semana 2.",
        }

    # Fecha inicio semana 2: siguiente lunes después de semana 1
    fecha_inicio_s2 = semana.fecha_inicio + timedelta(days=7)

    # Obtener feriados para el rango de semana 2
    fecha_fin_s2 = fecha_inicio_s2 + timedelta(days=13)
    feriados_custom = storage.load_feriados_custom() or []
    feriados = obtener_feriados_rango(
        fecha_inicio_s2, fecha_fin_s2,
        feriados_custom=feriados_custom if feriados_custom else None,
    )

    semana2 = generar_proyeccion(
        ofertas=ofertas_s2,
        fecha_inicio_semana=fecha_inicio_s2,
        dias_faena=5,
        pollos_por_dia=params.pollos_diarios_objetivo_max,
        params=params,
        feriados=feriados if feriados else None,
    )

    return {
        "tiene_datos": True,
        "proyeccion": semana2.model_dump(),
        "lotes_diferidos": diferidos,
        "total_diferidos": len(diferidos),
        "lotes_no_asignados_s1": len(semana.lotes_no_asignados),
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


# ─── Alerta Temprana ────────────────────────────────────────────────────────────

@app.get("/pronostico/alerta-temprana")
def get_alerta_temprana(current_user: TokenData = Depends(get_current_user)):
    """
    Analiza todos los lotes de la oferta y proyecta anticipadamente
    cuáles llegarán al rango de peso ideal para faena y cuáles no.
    Permite detectar problemas de peso días antes de la semana de faena.
    """
    params = _get_parametros()
    ofertas = _get_ofertas()

    if not ofertas:
        raise HTTPException(404, "No hay ofertas cargadas.")

    return calcular_alerta_temprana(ofertas, params)
