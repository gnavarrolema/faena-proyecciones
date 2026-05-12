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
    assert data["dias_faena_reales"] == 5
    assert fechas == [
        "2026-04-24",
        "2026-04-27",
        "2026-04-28",
        "2026-04-29",
        "2026-04-30",
    ]


def test_puente_friday_respects_user_objetivo_diario(client, auth_headers):
    """
    Regresion: antes _preasignar_viernes_puente llenaba el dia con
    _capacidad_dia(0) ignorando el objetivo del usuario, asi que con cap=0
    (sin tope legacy) terminaba en 45k aunque el usuario pidiese 38k.
    """
    storage.save_ofertas([
        {
            "fecha_peso": "2026-05-07",
            "fecha_oferta": "2026-05-07",
            "granja": "MANANTIALES",
            "galpon": g,
            "nucleo": 1,
            "cantidad": 15000,
            "sexo": "M",
            "edad_proyectada": 40,
            "peso_muestreo_proy": 2.85,
            "ganancia_diaria": 0.09,
            "dias_proyectados": 0,
            "edad_real": 40,
            "peso_muestreo_real": 2.85,
            "fecha_ingreso": "2026-03-28",
        }
        for g in (1, 2, 3, 4, 5)
    ])
    # Sin cap legacy del puente (el flujo actual deja default = 0).
    storage.save_parametros({
        "pollos_diarios_objetivo_max": 42000,
        "capacidad_con_horas_extras": 45000,
        "pollos_viernes_puente": 0,
        "edad_min_faena": 37,
        "edad_max_faena": 45,
        "peso_min_faena": 2.70,
        "peso_max_faena": 3.20,
    })

    r = client.post(
        "/proyeccion/generar",
        json={
            "fecha_inicio_semana": "2026-05-11",
            "dias_faena": 6,  # 1 puente + 5 Lun-Vie
            "pollos_por_dia": 42000,
            "criterio_gerente": True,
            "objetivos_diarios": [38000, 40000, 40000, 40021, 35000, 35000],
        },
        headers=auth_headers,
    )

    assert r.status_code == 200
    data = r.json()
    fechas = [dia["fecha"] for dia in data["dias"]]
    assert fechas[0] == "2026-05-08", f"Primer dia deberia ser el viernes puente, no {fechas[0]}"
    total_puente = data["dias"][0]["total_pollos"]
    assert total_puente <= 38000, (
        f"El viernes puente excedio el objetivo del usuario (38000): {total_puente}"
    )


def test_puente_no_bloquea_lunes_para_misma_granja_con_objetivos(client, auth_headers):
    """
    Regresion: la heuristica "no repetir granja consecutiva tras el puente"
    bloqueaba MANANTIALES en el lunes cuando ya estaba en el puente. Si la
    oferta es toda de una sola granja eso dejaba el lunes vacio aunque el
    usuario hubiera pedido 40k para ese dia.
    """
    storage.save_ofertas([
        # Lotes mas chicos / mas livianos -> caen al puente.
        {
            "fecha_peso": "2026-05-07", "fecha_oferta": "2026-05-07",
            "granja": "MANANTIALES", "galpon": g, "nucleo": 2,
            "cantidad": 8000, "sexo": "H", "edad_proyectada": 38,
            "peso_muestreo_proy": 2.85, "ganancia_diaria": 0.079,
            "dias_proyectados": 0, "edad_real": 38, "peso_muestreo_real": 2.85,
            "fecha_ingreso": "2026-03-30",
        }
        for g in (1, 2, 3, 4, 5)
    ] + [
        # Lotes mas grandes / mas pesados -> deberian llenar lunes en adelante.
        {
            "fecha_peso": "2026-05-07", "fecha_oferta": "2026-05-07",
            "granja": "MANANTIALES", "galpon": g, "nucleo": 3,
            "cantidad": 14000, "sexo": "H", "edad_proyectada": 37,
            "peso_muestreo_proy": 2.75, "ganancia_diaria": 0.079,
            "dias_proyectados": 0, "edad_real": 37, "peso_muestreo_real": 2.75,
            "fecha_ingreso": "2026-03-31",
        }
        for g in (1, 2, 3, 4, 5)
    ])
    storage.save_parametros({
        "pollos_diarios_objetivo_max": 42000,
        "capacidad_con_horas_extras": 45000,
        "pollos_viernes_puente": 0,
        "edad_min_faena": 37,
        "edad_max_faena": 45,
        "peso_min_faena": 2.70,
        "peso_max_faena": 3.20,
    })

    r = client.post(
        "/proyeccion/generar",
        json={
            "fecha_inicio_semana": "2026-05-11",
            "dias_faena": 6,
            "pollos_por_dia": 42000,
            "criterio_gerente": True,
            "objetivos_diarios": [38000, 40000, 40000, 40000, 35000, 35000],
        },
        headers=auth_headers,
    )

    assert r.status_code == 200
    data = r.json()
    dias_por_fecha = {dia["fecha"]: dia for dia in data["dias"]}

    puente = dias_por_fecha["2026-05-08"]
    lunes = dias_por_fecha["2026-05-11"]

    assert puente["total_pollos"] > 0, "Puente debe recibir asignaciones"
    assert lunes["total_pollos"] > 0, (
        f"Lunes quedo vacio cuando hay objetivo 40k: {lunes['total_pollos']}"
    )
    granjas_lunes = {lote["granja"] for lote in lunes["lotes"]}
    assert "MANANTIALES" in granjas_lunes, (
        f"Lunes no recibio MANANTIALES pese a ser la unica granja: {granjas_lunes}"
    )


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
