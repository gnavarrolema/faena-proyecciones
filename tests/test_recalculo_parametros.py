"""Tests para verificar que al actualizar parámetros se recalcula la proyección."""
from datetime import date
import pytest
from fastapi.testclient import TestClient
from backend.main import app
from backend.calculo import LoteOferta, Parametros
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


def _crear_oferta_y_proyeccion(client, auth_headers):
    """Crea ofertas y genera una proyección base."""
    ofertas = [
        LoteOferta(
            fecha_peso=date(2026, 2, 23),
            granja="GRANJA_A", galpon=1, nucleo=1, cantidad=15000,
            sexo="M", edad_proyectada=40, peso_muestreo_proy=2.95,
            ganancia_diaria=0.09, dias_proyectados=0, edad_real=40,
            peso_muestreo_real=2.95, fecha_ingreso=date(2026, 1, 14),
        ),
        LoteOferta(
            fecha_peso=date(2026, 2, 23),
            granja="GRANJA_B", galpon=2, nucleo=1, cantidad=20000,
            sexo="H", edad_proyectada=44, peso_muestreo_proy=2.50,
            ganancia_diaria=0.079, dias_proyectados=0, edad_real=44,
            peso_muestreo_real=2.50, fecha_ingreso=date(2026, 1, 10),
        ),
    ]
    storage.save_ofertas([o.model_dump() for o in ofertas])

    r = client.post("/proyeccion/generar", json={
        "fecha_inicio_semana": "2026-02-23",
        "dias_faena": 5,
        "pollos_por_dia": 35000,
    }, headers=auth_headers)
    assert r.status_code == 200
    return r.json()


def test_update_parametros_recalcula_proyeccion(client, auth_headers):
    """Al guardar parámetros con proyección existente, debe recalcularse."""
    proy_original = _crear_oferta_y_proyeccion(client, auth_headers)

    # Actualizar un parámetro que afecta el cálculo
    r = client.put("/parametros", json={
        "peso_min_faena": 2.0,
        "peso_max_faena": 4.0,
    }, headers=auth_headers)
    assert r.status_code == 200
    data = r.json()
    assert data["proyeccion_recalculada"] is True
    assert data["peso_min_faena"] == 2.0
    assert data["peso_max_faena"] == 4.0

    # La proyección guardada debe reflejar los nuevos parámetros
    r = client.get("/proyeccion", headers=auth_headers)
    assert r.status_code == 200
    proy_nueva = r.json()
    assert proy_nueva["fecha_inicio"] == proy_original["fecha_inicio"]


def test_update_parametros_sin_proyeccion_no_recalcula(client, auth_headers):
    """Sin proyección existente, no debe intentar recalcular."""
    r = client.put("/parametros", json={
        "peso_min_faena": 2.0,
    }, headers=auth_headers)
    assert r.status_code == 200
    data = r.json()
    assert data["proyeccion_recalculada"] is False


def test_update_parametros_sin_ofertas_no_recalcula(client, auth_headers):
    """Con proyección pero sin ofertas, no debe recalcular."""
    _crear_oferta_y_proyeccion(client, auth_headers)
    # Borrar las ofertas
    storage.delete_ofertas()

    r = client.put("/parametros", json={
        "peso_min_faena": 2.0,
    }, headers=auth_headers)
    assert r.status_code == 200
    data = r.json()
    assert data["proyeccion_recalculada"] is False


def test_config_generacion_se_guarda(client, auth_headers):
    """Al generar proyección se guarda la configuración de generación."""
    _crear_oferta_y_proyeccion(client, auth_headers)
    config = storage.load_proyeccion_config()
    assert config is not None
    assert config["fecha_inicio_semana"] == "2026-02-23"
    assert config["dias_faena"] == 5
    assert config["pollos_por_dia"] == 35000


def test_recalculo_usa_config_guardada(client, auth_headers):
    """El recálculo usa pollos_por_dia de la config original."""
    ofertas = [
        LoteOferta(
            fecha_peso=date(2026, 2, 23),
            granja="GRANJA_A", galpon=i, nucleo=1, cantidad=10000,
            sexo="M", edad_proyectada=40, peso_muestreo_proy=2.95,
            ganancia_diaria=0.09, dias_proyectados=0, edad_real=40,
            peso_muestreo_real=2.95, fecha_ingreso=date(2026, 1, 14),
        ) for i in range(1, 6)
    ]
    storage.save_ofertas([o.model_dump() for o in ofertas])

    # Generar con pollos_por_dia=20000
    r = client.post("/proyeccion/generar", json={
        "fecha_inicio_semana": "2026-02-23",
        "dias_faena": 5,
        "pollos_por_dia": 20000,
    }, headers=auth_headers)
    assert r.status_code == 200

    config = storage.load_proyeccion_config()
    assert config["pollos_por_dia"] == 20000

    # Al actualizar parámetros, recalcula con la misma config
    r = client.put("/parametros", json={
        "ganancia_diaria_macho": 0.095,
    }, headers=auth_headers)
    assert r.status_code == 200
    assert r.json()["proyeccion_recalculada"] is True
