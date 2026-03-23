"""Tests para Fase 3: mortalidad en escenarios y mortalidad observada."""
from datetime import date, timedelta

import pytest
from fastapi.testclient import TestClient
from backend.main import app
from backend.parser_produccion import SemanaProduccion, DIAS_HASTA_FAENA
from backend.calculo import (
    Parametros, LoteOferta, SemanaFaena, DiaFaena,
    generar_proyeccion, ordenar_oferta_por_prioridad,
)
from backend import storage


# ─── Fixtures ────────────────────────────────────────────────────────────────────

@pytest.fixture(autouse=True)
def clean_storage(tmp_path, monkeypatch):
    monkeypatch.setenv("STORAGE_BACKEND", "local")
    monkeypatch.setenv("LOCAL_STORAGE_PATH", str(tmp_path))
    storage._storage_instance = storage.LocalStorage(str(tmp_path))
    yield
    storage._storage_instance = None


@pytest.fixture()
def client():
    return TestClient(app)


@pytest.fixture()
def auth_headers(client):
    r = client.post("/token", data={"username": "admin", "password": "admin123"})
    assert r.status_code == 200
    token = r.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


def _guardar_produccion(fecha_desde: date, pollitos: int):
    sem = SemanaProduccion(
        fecha_desde=fecha_desde,
        fecha_hasta=fecha_desde + timedelta(days=6),
        pollitos_cargados=pollitos,
    )
    storage.save_produccion([sem.model_dump()])


def _crear_proyeccion_simple(fecha_inicio: date, pollos_dia: int = 30000):
    """Crea y guarda una proyección simple para tests."""
    dias = []
    for i in range(6):  # lun-sab
        dias.append(DiaFaena(
            fecha=fecha_inicio + timedelta(days=i),
            dia_nombre=["Lunes", "Martes", "Miércoles", "Jueves", "Viernes", "Sábado"][i],
            total_pollos=pollos_dia,
            peso_promedio_ponderado=3.0,
        ))
    semana = SemanaFaena(
        fecha_inicio=fecha_inicio,
        fecha_fin=fecha_inicio + timedelta(days=5),
        dias=dias,
        total_pollos_semana=pollos_dia * 6,
    )
    storage.save_proyeccion(semana.model_dump())
    return semana


def _crear_proyeccion_amplia(fecha_inicio: date, dias: int = 13, pollos_dia: int = 7500):
    """Crea una proyección que cubre un rango amplio (para tests de cobertura)."""
    nombres_dia = ["Lunes", "Martes", "Miércoles", "Jueves", "Viernes", "Sábado", "Domingo"]
    dias_list = []
    for i in range(dias):
        f = fecha_inicio + timedelta(days=i)
        dias_list.append(DiaFaena(
            fecha=f,
            dia_nombre=nombres_dia[f.weekday()],
            total_pollos=pollos_dia,
            peso_promedio_ponderado=3.0,
        ))
    semana = SemanaFaena(
        fecha_inicio=fecha_inicio,
        fecha_fin=fecha_inicio + timedelta(days=dias - 1),
        dias=dias_list,
        total_pollos_semana=pollos_dia * dias,
    )
    storage.save_proyeccion(semana.model_dump())
    return semana


# ─── Tests 3.1: Escenarios con tasa de mortalidad ───────────────────────────────

def test_guardar_escenario_sin_mortalidad(client, auth_headers):
    """Guardar escenario sin tasa_mortalidad funciona como antes."""
    _crear_proyeccion_simple(date(2026, 3, 16))
    storage.save_parametros(Parametros().model_dump())

    r = client.post("/escenarios/guardar", json={
        "nombre": "Test básico",
    }, headers=auth_headers)
    assert r.status_code == 200
    esc_id = r.json()["id"]

    # Verificar que se guardó sin mortalidad
    r2 = client.get(f"/escenarios/{esc_id}", headers=auth_headers)
    assert r2.status_code == 200
    data = r2.json()
    assert data["tasa_mortalidad"] is None
    assert data["produccion_analisis"] is None


def test_guardar_escenario_con_mortalidad(client, auth_headers):
    """Guardar escenario con tasa_mortalidad incluye produccion_analisis."""
    fecha_faena = date(2026, 3, 16)
    fecha_prod = fecha_faena - timedelta(days=DIAS_HASTA_FAENA)
    _guardar_produccion(fecha_prod, 200000)
    _crear_proyeccion_simple(fecha_faena, pollos_dia=30000)
    storage.save_parametros(Parametros().model_dump())

    r = client.post("/escenarios/guardar", json={
        "nombre": "Con mortalidad 7.5%",
        "tasa_mortalidad": 0.075,
    }, headers=auth_headers)
    assert r.status_code == 200
    esc_id = r.json()["id"]

    r2 = client.get(f"/escenarios/{esc_id}", headers=auth_headers)
    data = r2.json()
    assert data["tasa_mortalidad"] == 0.075
    assert data["produccion_analisis"] is not None
    assert data["produccion_analisis"]["tasa_mortalidad"] == 0.075
    assert data["produccion_analisis"]["pollitos_cargados"] == 200000
    # 200000 * (1 - 0.075) = 185000
    assert data["produccion_analisis"]["disponibles"] == 185000


def test_listar_escenarios_incluye_mortalidad(client, auth_headers):
    """La lista de escenarios incluye tasa_mortalidad y produccion_analisis."""
    _crear_proyeccion_simple(date(2026, 3, 16))
    storage.save_parametros(Parametros().model_dump())

    client.post("/escenarios/guardar", json={
        "nombre": "Escenario A",
        "tasa_mortalidad": 0.05,
    }, headers=auth_headers)

    r = client.get("/escenarios", headers=auth_headers)
    assert r.status_code == 200
    escenarios = r.json()
    assert len(escenarios) >= 1
    esc = escenarios[0]
    assert "tasa_mortalidad" in esc
    assert "produccion_analisis" in esc


def test_comparar_escenarios_incluye_mortalidad(client, auth_headers):
    """La comparación incluye campos de mortalidad."""
    fecha_faena = date(2026, 3, 16)
    fecha_prod = fecha_faena - timedelta(days=DIAS_HASTA_FAENA)
    _guardar_produccion(fecha_prod, 200000)
    _crear_proyeccion_simple(fecha_faena, pollos_dia=30000)
    storage.save_parametros(Parametros().model_dump())

    r1 = client.post("/escenarios/guardar", json={
        "nombre": "Mejor caso",
        "tasa_mortalidad": 0.045,
    }, headers=auth_headers)
    id1 = r1.json()["id"]

    r2 = client.post("/escenarios/guardar", json={
        "nombre": "Peor caso",
        "tasa_mortalidad": 0.075,
    }, headers=auth_headers)
    id2 = r2.json()["id"]

    r = client.post("/escenarios/comparar", json={"ids": [id1, id2]}, headers=auth_headers)
    assert r.status_code == 200
    escs = r.json()["escenarios"]
    assert len(escs) == 2
    # Both should have distinct produccion_analisis
    disp1 = escs[0]["produccion_analisis"]["disponibles"]
    disp2 = escs[1]["produccion_analisis"]["disponibles"]
    # 200000*(1-0.045)=191000 vs 200000*(1-0.075)=185000
    assert disp1 != disp2


# ─── Tests 3.2: Mortalidad observada ─────────────────────────────────────────────

def test_mortalidad_observada_sin_produccion(client, auth_headers):
    """Sin datos de producción → 404."""
    _crear_proyeccion_simple(date(2026, 3, 16))
    r = client.get("/desvio/mortalidad-observada", headers=auth_headers)
    assert r.status_code == 404


def test_mortalidad_observada_sin_proyeccion(client, auth_headers):
    """Sin proyección → 404."""
    _guardar_produccion(date(2026, 1, 1), 50000)
    r = client.get("/desvio/mortalidad-observada", headers=auth_headers)
    assert r.status_code == 404


def test_mortalidad_observada_sin_match(client, auth_headers):
    """Producción lejana de la proyección → sin puntos, con mensaje."""
    _guardar_produccion(date(2020, 1, 1), 50000)
    _crear_proyeccion_simple(date(2026, 3, 16))

    r = client.get("/desvio/mortalidad-observada", headers=auth_headers)
    assert r.status_code == 200
    data = r.json()
    assert len(data["puntos"]) == 0
    assert data["resumen"] is None


def test_mortalidad_observada_con_match(client, auth_headers):
    """Producción + proyección coinciden → calcula mortalidad."""
    fecha_faena = date(2026, 3, 16)
    fecha_prod = fecha_faena - timedelta(days=DIAS_HASTA_FAENA)
    _guardar_produccion(fecha_prod, 100000)
    # Crear proyección que cubra todo el rango de faena (tolerancia ±3 días)
    # rango: fecha_prod+42-3 .. fecha_prod+6+42+3 = 13 días antes de fecha_faena-3
    rango_ini = fecha_prod + timedelta(days=DIAS_HASTA_FAENA) - timedelta(days=3)
    _crear_proyeccion_amplia(rango_ini, dias=13, pollos_dia=7200)  # ~93600 total ~ 6.4% mort

    r = client.get("/desvio/mortalidad-observada", headers=auth_headers)
    assert r.status_code == 200
    data = r.json()
    assert len(data["puntos"]) >= 1
    assert data["resumen"] is not None

    punto = data["puntos"][0]
    assert punto["pollitos_cargados"] == 100000
    assert punto["pollos_recibidos"] > 0
    assert 0 <= punto["mortalidad_observada_pct"] <= 100
    assert punto["evaluacion"] in ("excelente", "dentro_rango", "por_encima")

    # Tendencia
    assert data["resumen"]["tendencia"] in ("favorable", "normal", "desfavorable")
    assert data["resumen"]["semanas_analizadas"] >= 1


def test_mortalidad_observada_evaluacion_excelente(client, auth_headers):
    """Mortalidad baja → evaluación excelente."""
    fecha_faena = date(2026, 3, 16)
    fecha_prod = fecha_faena - timedelta(days=DIAS_HASTA_FAENA)
    _guardar_produccion(fecha_prod, 100000)
    # Crear proyección amplia que cubra todo el rango de faena
    rango_ini = fecha_prod + timedelta(days=DIAS_HASTA_FAENA) - timedelta(days=3)
    # Necesitamos ~98000 pollos recibidos de 100000 → 2% mortalidad (bajo 4.5%)
    # Con 13 días × 10000 = 130000 total, pero solo ~9 días hábiles cuentan
    # 9 × 10800 ≈ 97200 → ~2.8% mort → excelente
    _crear_proyeccion_amplia(rango_ini, dias=13, pollos_dia=10800)

    r = client.get("/desvio/mortalidad-observada", headers=auth_headers)
    data = r.json()
    punto = data["puntos"][0]
    assert punto["evaluacion"] == "excelente"
    assert data["resumen"]["tendencia"] == "favorable"
