from fastapi.testclient import TestClient
import pytest

from backend.main import app
from backend import storage


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


def _guardar_ofertas_y_parametros():
    storage.save_ofertas([
        {
            "fecha_peso": "2026-04-16",
            "granja": "REMANSOS",
            "galpon": 2,
            "nucleo": 1,
            "cantidad": 19673,
            "sexo": "M",
            "edad_proyectada": 37,
            "peso_muestreo_proy": 2.90,
            "ganancia_diaria": 0.11,
            "dias_proyectados": 0,
            "edad_real": 37,
            "peso_muestreo_real": 2.90,
            "fecha_ingreso": "2026-03-09",
        },
        {
            "fecha_peso": "2026-04-16",
            "granja": "REMANSOS",
            "galpon": 4,
            "nucleo": 1,
            "cantidad": 8530,
            "sexo": "H",
            "edad_proyectada": 40,
            "peso_muestreo_proy": 2.80,
            "ganancia_diaria": 0.09,
            "dias_proyectados": 0,
            "edad_real": 40,
            "peso_muestreo_real": 2.80,
            "fecha_ingreso": "2026-03-06",
        },
    ])
    storage.save_parametros({
        "planificacion_continua_gerente": True,
        "planificacion_continua_dias_habiles": 7,
    })


def test_manager_mode_uses_continuous_business_day_calendar(client, auth_headers):
    _guardar_ofertas_y_parametros()

    r = client.post(
        "/proyeccion/generar",
        json={
            "fecha_inicio_semana": "2026-04-20",
            "dias_faena": 5,
            "pollos_por_dia": 35000,
            "criterio_gerente": True,
        },
        headers=auth_headers,
    )

    assert r.status_code == 200
    data = r.json()
    fechas = [dia["fecha"] for dia in data["dias"]]

    assert data["calendario_planificacion"] == "continuo_habil"
    assert data["fecha_inicio_planificacion_real"] == "2026-04-17"
    assert data["dias_faena_reales"] == 7
    assert fechas == [
        "2026-04-17",
        "2026-04-20",
        "2026-04-21",
        "2026-04-22",
        "2026-04-23",
        "2026-04-24",
        "2026-04-27",
    ]


def test_continuous_manager_keeps_weekly_config_for_followup_flows(client, auth_headers):
    _guardar_ofertas_y_parametros()

    r = client.post(
        "/proyeccion/generar",
        json={
            "fecha_inicio_semana": "2026-04-20",
            "dias_faena": 5,
            "pollos_por_dia": 35000,
            "criterio_gerente": True,
        },
        headers=auth_headers,
    )

    assert r.status_code == 200
    config = storage.load_proyeccion_config()
    assert config is not None
    assert config["fecha_inicio_semana"] == "2026-04-20"
    assert config["dias_faena"] == 5
    assert config["fecha_inicio_semana_real"] == "2026-04-17"
    assert config["dias_faena_reales"] == 7
    assert config["planificacion_continua_gerente"] is True