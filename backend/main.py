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
    descripcion: str = "Faena de gallinas livianas"


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


class CompararEscenariosRequest(BaseModel):
    """Para comparar escenarios por IDs."""
    ids: List[str]


class ReferenciaProduccionResponse(BaseModel):
    """Respuesta del endpoint de referencia de producción."""
    encontrada: bool
    semana_produccion: Optional[dict] = None
    total_oferta_actual: int = 0
    cobertura_pct: Optional[float] = None
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
    return semana.model_dump()


@app.get("/proyeccion")
def get_proyeccion(current_user: TokenData = Depends(get_current_user)):
    """Obtener la proyección actual."""
    proyeccion = _get_proyeccion()
    if proyeccion is None:
        raise HTTPException(404, "No hay proyección generada aún.")
    return proyeccion.model_dump()


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
    )
    semana.dias[asignacion.dia_destino] = calcular_dia_faena(
        dia_destino.fecha, dia_destino.lotes, params=params,
        gallinas_cantidad=dia_destino.gallinas_cantidad,
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


# ─── Gallinas Livianas ─────────────────────────────────────────────────────────

@app.post("/proyeccion/gallinas")
def configurar_gallinas(
    req: GallinasRequest,
    current_user: TokenData = Depends(get_current_user),
):
    """
    Marca un día de la proyección para faena de gallinas livianas.
    Reduce la capacidad disponible para pollos en ese día.
    """
    semana = _get_proyeccion()
    if semana is None:
        raise HTTPException(404, "No hay proyección generada aún.")

    if req.dia_index < 0 or req.dia_index >= len(semana.dias):
        raise HTTPException(400, "Índice de día inválido")

    dia = semana.dias[req.dia_index]
    params = _get_parametros()

    # Actualizar gallinas en el día
    semana.dias[req.dia_index] = calcular_dia_faena(
        dia.fecha, dia.lotes, params=params,
        gallinas_cantidad=req.cantidad,
    )

    # Registrar evento de gallinas en la semana
    semana.eventos_gallinas = [
        e for e in semana.eventos_gallinas
        if e.fecha != dia.fecha
    ]
    if req.cantidad > 0:
        semana.eventos_gallinas.append(
            EventoGallinas(
                fecha=dia.fecha,
                cantidad=req.cantidad,
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
    current_user: TokenData = Depends(get_current_user),
):
    """Quita las gallinas de un día de faena."""
    semana = _get_proyeccion()
    if semana is None:
        raise HTTPException(404, "No hay proyección generada aún.")

    if dia_index < 0 or dia_index >= len(semana.dias):
        raise HTTPException(400, "Índice de día inválido")

    dia = semana.dias[dia_index]
    params = _get_parametros()

    semana.dias[dia_index] = calcular_dia_faena(
        dia.fecha, dia.lotes, params=params, gallinas_cantidad=0,
    )

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

    return ReferenciaProduccionResponse(
        encontrada=True,
        semana_produccion=sim_data,
        total_oferta_actual=total_oferta,
        cobertura_pct=cobertura,
        mensaje="Referencia encontrada.",
    )


@app.delete("/produccion")
def clear_produccion(current_user: TokenData = Depends(get_current_user)):
    """Limpiar datos de producción."""
    storage.delete_produccion()
    return {"message": "Datos de producción eliminados."}


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

    escenario_data = {
        "id": escenario_id,
        "nombre": req.nombre,
        "descripcion": req.descripcion or "",
        "fecha_creacion": datetime.now().isoformat(),
        "parametros": params.model_dump(),
        "proyeccion": proyeccion.model_dump(),
        "resumen": {
            "total_pollos": proyeccion.total_pollos_semana,
            "dias": len(proyeccion.dias),
            "cajas": proyeccion.produccion_cajas_semanales,
            "sofia": proyeccion.sofia,
            "promedio_edad": proyeccion.promedio_edad_semana,
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
    para la semana siguiente. Aparecerá como aviso al cargar la próxima oferta.
    """
    semana = _get_proyeccion()
    if semana is None:
        raise HTTPException(404, "No hay proyección generada.")

    if not semana.lotes_no_asignados:
        raise HTTPException(400, "No hay lotes no asignados en la proyección actual.")

    deficit_data = {
        "lotes": [l.model_dump() for l in semana.lotes_no_asignados],
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
