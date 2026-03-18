"""Tests para Fase 2: forecast de producción y déficit_produccion en análisis de terceros."""
from datetime import date, timedelta

import pytest
from fastapi.testclient import TestClient
from backend.main import app, _calcular_deficit_produccion
from backend.parser_produccion import (
    SemanaProduccion, DIAS_HASTA_FAENA, TASAS_MORTALIDAD_DEFAULT,
)
from backend.calculo import SemanaFaena
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


# ─── Tests: _calcular_deficit_produccion ─────────────────────────────────────────

def test_deficit_produccion_sin_datos():
    """Sin producción cargada retorna None."""
    proy = SemanaFaena(
        fecha_inicio=date(2026, 3, 16),
        fecha_fin=date(2026, 3, 21),
        total_pollos_semana=30000,
    )
    result = _calcular_deficit_produccion(proy)
    assert result is None


def test_deficit_produccion_con_superavit():
    """Producción suficiente → hay_deficit=False."""
    fecha_prod = date(2026, 2, 2)
    fecha_faena = fecha_prod + timedelta(days=DIAS_HASTA_FAENA)
    _guardar_produccion(fecha_prod, 100000)

    proy = SemanaFaena(
        fecha_inicio=fecha_faena,
        fecha_fin=fecha_faena + timedelta(days=5),
        total_pollos_semana=80000,
    )
    result = _calcular_deficit_produccion(proy)
    assert result is not None
    assert result["encontrada"] is True
    assert result["hay_deficit"] is False
    assert result["recomendacion_terceros"] is None


def test_deficit_produccion_con_deficit():
    """Oferta excede producción → hay_deficit=True con recomendación."""
    fecha_prod = date(2026, 2, 2)
    fecha_faena = fecha_prod + timedelta(days=DIAS_HASTA_FAENA)
    _guardar_produccion(fecha_prod, 100000)

    proy = SemanaFaena(
        fecha_inicio=fecha_faena,
        fecha_fin=fecha_faena + timedelta(days=5),
        total_pollos_semana=96000,
    )
    result = _calcular_deficit_produccion(proy)
    assert result is not None
    assert result["hay_deficit"] is True
    assert result["deficit_peor"] == 96000 - 93500  # 100000*(1-0.065)=93500
    assert "terceros" in result["recomendacion_terceros"].lower()


# ─── Tests: /produccion/forecast endpoint ────────────────────────────────────────

def test_forecast_sin_datos(client, auth_headers):
    """Sin datos de producción → 404."""
    r = client.get("/produccion/forecast", headers=auth_headers)
    assert r.status_code == 404


def test_forecast_con_datos(client, auth_headers):
    """Con datos cargados retorna semanas con mejor/peor caso."""
    # Cargar pollitos con fecha_desde tal que faena caiga esta semana
    hoy = date.today()
    fecha_prod = hoy - timedelta(days=DIAS_HASTA_FAENA)
    _guardar_produccion(fecha_prod, 50000)

    r = client.get("/produccion/forecast?semanas=2", headers=auth_headers)
    assert r.status_code == 200
    data = r.json()
    assert "semanas" in data
    assert len(data["semanas"]) == 2

    # La primera semana debería tener match
    sem0 = data["semanas"][0]
    assert sem0["semanas_incluidas"] >= 1
    assert sem0["mejor_caso"] is not None
    assert sem0["peor_caso"] is not None
    # Mejor caso: 50000 * (1 - 0.045) = 47750
    assert sem0["mejor_caso"]["pollitos_disponibles"] == 47750
    # Peor caso: 50000 * (1 - 0.065) = 46750
    assert sem0["peor_caso"]["pollitos_disponibles"] == 46750


def test_forecast_sin_match(client, auth_headers):
    """Datos lejanos → semanas sin match, mejor/peor caso null."""
    _guardar_produccion(date(2020, 1, 1), 50000)

    r = client.get("/produccion/forecast?semanas=1", headers=auth_headers)
    assert r.status_code == 200
    sem = r.json()["semanas"][0]
    assert sem["semanas_incluidas"] == 0
    assert sem["mejor_caso"] is None
    assert sem["peor_caso"] is None


def test_forecast_default_4_semanas(client, auth_headers):
    """Sin parámetro semanas, retorna 4 por defecto."""
    _guardar_produccion(date(2020, 1, 1), 10000)

    r = client.get("/produccion/forecast", headers=auth_headers)
    assert r.status_code == 200
    assert len(r.json()["semanas"]) == 4
