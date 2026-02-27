"""
API FastAPI para la planificación de faena avícola.
"""
import logging

from fastapi import FastAPI, UploadFile, File, HTTPException, Depends
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import OAuth2PasswordRequestForm
from pydantic import BaseModel
from datetime import date, timedelta
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
    AjusteMartesResumen, aplicar_ajuste_martes,
    calcular_lote_proyectado, calcular_dia_faena, calcular_semana_faena,
    generar_proyeccion, ordenar_oferta_por_prioridad,
    calcular_edad_fin_retiro_v2, diferencia_edad_ideal,
    peso_vivo_retiro, peso_faenado, calibre_promedio, cajas_lote,
)
from .parser_excel import leer_oferta_excel
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
    dias_faena: int = 6
    pollos_por_dia: int = 30000
    parametros: Optional[Parametros] = None


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
    descuento_sofia: Optional[int] = None


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
    """
    ofertas = _get_ofertas()
    if not ofertas:
        raise HTTPException(400, "No hay oferta cargada. Suba un archivo primero.")

    params = req.parametros or _get_parametros()

    semana = generar_proyeccion(
        ofertas=ofertas,
        fecha_inicio_semana=req.fecha_inicio_semana,
        dias_faena=req.dias_faena,
        pollos_por_dia=req.pollos_por_dia,
        params=params,
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
    semana.dias[asignacion.dia_origen] = calcular_dia_faena(dia_origen.fecha, dia_origen.lotes)
    semana.dias[asignacion.dia_destino] = calcular_dia_faena(dia_destino.fecha, dia_destino.lotes)

    # Recalcular semana (preservar lotes no asignados y fuera de rango)
    resultado = calcular_semana_faena(
        semana.fecha_inicio, semana.dias, params,
        lotes_no_asignados=semana.lotes_no_asignados,
        lotes_fuera_rango=semana.lotes_fuera_rango,
    )
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
    semana.dias[lote_req.dia_faena].lotes.append(lote)

    # Recalcular el día
    dia = semana.dias[lote_req.dia_faena]
    semana.dias[lote_req.dia_faena] = calcular_dia_faena(dia.fecha, dia.lotes)

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
    semana.dias[dia_index] = calcular_dia_faena(dia.fecha, dia.lotes)
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
