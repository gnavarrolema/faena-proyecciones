from fastapi.testclient import TestClient
import pytest

from backend.config import ADMIN_PASSWORD, ADMIN_USERNAME
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
    r = client.post(
        "/token",
        data={"username": ADMIN_USERNAME, "password": ADMIN_PASSWORD},
    )
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


def test_manager_mode_respects_continuous_calendar_flag(client, auth_headers):
    """Cuando planificacion_continua_gerente=True está persistido,
    el sistema lo respeta y genera un calendario continuo."""
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

    assert data["calendario_planificacion"] == "continuo_habil"
    assert data["dias_faena_reales"] >= 5


def test_manager_mode_defaults_to_weekly_calendar_when_continuous_flag_is_missing(client, auth_headers):
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
        "pollos_diarios_objetivo_max": 38000,
    })

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

    assert data["calendario_planificacion"] == "semanal"
    assert data["fecha_inicio_planificacion_real"] == "2026-04-20"
    assert data["dias_faena_reales"] == 5
    assert fechas == [
        "2026-04-20",
        "2026-04-21",
        "2026-04-22",
        "2026-04-23",
        "2026-04-24",
    ]


def test_manager_mode_starts_after_global_offer_date_when_it_precedes_selected_monday(client, auth_headers):
    storage.save_ofertas([
        {
            "fecha_peso": "2026-04-23",
            "fecha_oferta": "2026-04-23",
            "granja": "REMANSOS",
            "galpon": 5,
            "nucleo": 2,
            "cantidad": 4732,
            "sexo": "H",
            "edad_proyectada": 41,
            "peso_muestreo_proy": 2.85,
            "ganancia_diaria": 0.085,
            "dias_proyectados": 0,
            "edad_real": 41,
            "peso_muestreo_real": 2.85,
            "fecha_ingreso": "2026-03-12",
        },
        {
            "fecha_peso": "2026-04-21",
            "fecha_oferta": "2026-04-23",
            "granja": "MANANTIALES",
            "galpon": 4,
            "nucleo": 1,
            "cantidad": 11492,
            "sexo": "M",
            "edad_proyectada": 33,
            "peso_muestreo_proy": 2.51,
            "ganancia_diaria": 0.09,
            "dias_proyectados": 2,
            "edad_real": 31,
            "peso_muestreo_real": 2.29,
            "fecha_ingreso": "2026-03-20",
        },
    ])
    storage.save_parametros({
        "pollos_diarios_objetivo_max": 45000,
        "usar_feriados_nacionales": False,
    })

    r = client.post(
        "/proyeccion/generar",
        json={
            "fecha_inicio_semana": "2026-04-27",
            "dias_faena": 5,
            "pollos_por_dia": 45000,
            "criterio_gerente": True,
        },
        headers=auth_headers,
    )

    assert r.status_code == 200
    data = r.json()
    fechas = [dia["fecha"] for dia in data["dias"]]

    assert data["calendario_planificacion"] == "continuo_habil"
    assert data["fecha_inicio_planificacion_real"] == "2026-04-24"
    assert data["dias_faena_reales"] == 6
    assert fechas == [
        "2026-04-24",
        "2026-04-27",
        "2026-04-28",
        "2026-04-29",
        "2026-04-30",
        "2026-05-01",
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
    # Con planificacion_continua=True, los valores reales pueden diferir
    assert config["dias_faena_reales"] >= 5
    assert config["planificacion_continua_gerente"] is True


def test_feriados_endpoint_respects_national_holidays_toggle(client, auth_headers):
    storage.save_parametros({"usar_feriados_nacionales": False})

    r = client.get("/feriados?anio=2026", headers=auth_headers)

    assert r.status_code == 200
    assert all(item["tipo"] != "nacional" for item in r.json())
