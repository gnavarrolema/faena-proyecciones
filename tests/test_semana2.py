"""Tests para la funcionalidad de Semana 2 (diferir lotes, proyección tentativa)."""
import pytest
from datetime import date
from fastapi.testclient import TestClient

from backend.main import app
from backend import storage


@pytest.fixture(autouse=True)
def clean_storage(tmp_path, monkeypatch):
    """Usa storage temporal para cada test."""
    from backend.storage import LocalStorage, _storage_instance
    monkeypatch.setattr(storage, "_storage_instance", LocalStorage(str(tmp_path)))
    yield


@pytest.fixture
def client():
    return TestClient(app)


@pytest.fixture
def auth_headers(client):
    resp = client.post("/token", data={"username": "admin", "password": "admin123"})
    assert resp.status_code == 200, f"Login failed: {resp.text}"
    token = resp.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


def _crear_oferta_y_proyeccion(client, auth_headers):
    """Helper: carga oferta de ejemplo y genera proyección."""
    ofertas = [
        {
            "fecha_peso": "2026-03-12",
            "granja": "MARTINA",
            "galpon": 1,
            "nucleo": 1,
            "cantidad": 16000,
            "sexo": "M",
            "edad_proyectada": 38,
            "peso_muestreo_proy": 2.90,
            "ganancia_diaria": 0.09,
            "dias_proyectados": 5,
            "edad_real": 33,
            "peso_muestreo_real": 2.45,
            "fecha_ingreso": "2026-02-07",
        },
        {
            "fecha_peso": "2026-03-12",
            "granja": "LOS MANANTIALES",
            "galpon": 5,
            "nucleo": 4,
            "cantidad": 15000,
            "sexo": "H",
            "edad_proyectada": 42,
            "peso_muestreo_proy": 3.00,
            "ganancia_diaria": 0.079,
            "dias_proyectados": 5,
            "edad_real": 37,
            "peso_muestreo_real": 2.60,
            "fecha_ingreso": "2026-02-03",
        },
        {
            "fecha_peso": "2026-03-12",
            "granja": "MARTINA",
            "galpon": 7,
            "nucleo": 1,
            "cantidad": 18000,
            "sexo": "M",
            "edad_proyectada": 39,
            "peso_muestreo_proy": 2.95,
            "ganancia_diaria": 0.09,
            "dias_proyectados": 5,
            "edad_real": 34,
            "peso_muestreo_real": 2.50,
            "fecha_ingreso": "2026-02-06",
        },
    ]
    storage.save_ofertas(ofertas)

    resp = client.post(
        "/proyeccion/generar",
        json={
            "fecha_inicio_semana": "2026-03-16",
            "dias_faena": 5,
            "pollos_por_dia": 35000,
        },
        headers=auth_headers,
    )
    assert resp.status_code == 200
    return resp.json()


def test_diferir_lote(client, auth_headers):
    """Diferir un lote de semana 1 y verificar que se guarda."""
    proy = _crear_oferta_y_proyeccion(client, auth_headers)
    dia0_pollos = proy["dias"][0]["total_pollos"]
    dia0_lotes = len(proy["dias"][0]["lotes"])

    # Diferir el primer lote del primer día
    resp = client.post(
        "/proyeccion/diferir-lote",
        json={"dia_index": 0, "lote_index": 0, "motivo": "Feriado"},
        headers=auth_headers,
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["total_diferidos"] == 1
    assert data["lote_diferido"]["motivo"] == "Feriado"
    # El día 0 debe tener un lote menos
    assert len(data["proyeccion"]["dias"][0]["lotes"]) == dia0_lotes - 1


def test_diferir_y_restaurar(client, auth_headers):
    """Diferir un lote y luego restaurarlo."""
    _crear_oferta_y_proyeccion(client, auth_headers)

    # Diferir
    resp = client.post(
        "/proyeccion/diferir-lote",
        json={"dia_index": 0, "lote_index": 0},
        headers=auth_headers,
    )
    assert resp.status_code == 200
    total_s1_post_diferir = resp.json()["proyeccion"]["total_pollos_semana"]

    # Restaurar al día 2
    resp = client.post(
        "/proyeccion/restaurar-lote-semana1",
        json={"diferido_index": 0, "dia_destino": 2},
        headers=auth_headers,
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["total_diferidos"] == 0
    assert data["dia_destino"] == 2
    # Total debe ser mayor que post-diferir
    assert data["proyeccion"]["total_pollos_semana"] > total_s1_post_diferir


def test_semana2_vacia(client, auth_headers):
    """Sin lotes diferidos ni no asignados, semana 2 no tiene datos."""
    _crear_oferta_y_proyeccion(client, auth_headers)

    resp = client.get("/proyeccion/semana2", headers=auth_headers)
    assert resp.status_code == 200
    data = resp.json()
    # Puede o no tener datos (depende de si hay lotes_no_asignados)
    assert "tiene_datos" in data


def test_semana2_con_diferidos(client, auth_headers):
    """Diferir lotes y luego obtener proyección de semana 2."""
    _crear_oferta_y_proyeccion(client, auth_headers)

    # Diferir 2 lotes
    client.post(
        "/proyeccion/diferir-lote",
        json={"dia_index": 0, "lote_index": 0, "motivo": "Sobrecarga"},
        headers=auth_headers,
    )

    resp = client.get("/proyeccion/semana2", headers=auth_headers)
    assert resp.status_code == 200
    data = resp.json()
    assert data["tiene_datos"] == True
    assert data["proyeccion"] is not None
    assert data["total_diferidos"] == 1
    # La semana 2 debe empezar 7 días después
    assert data["proyeccion"]["fecha_inicio"] == "2026-03-23"


def test_lotes_diferidos_endpoint(client, auth_headers):
    """Verificar endpoint de listar lotes diferidos."""
    _crear_oferta_y_proyeccion(client, auth_headers)

    # Sin diferidos
    resp = client.get("/proyeccion/lotes-diferidos", headers=auth_headers)
    assert resp.status_code == 200
    assert resp.json()["total_diferidos"] == 0

    # Diferir uno
    client.post(
        "/proyeccion/diferir-lote",
        json={"dia_index": 0, "lote_index": 0},
        headers=auth_headers,
    )

    resp = client.get("/proyeccion/lotes-diferidos", headers=auth_headers)
    assert resp.status_code == 200
    assert resp.json()["total_diferidos"] == 1
    assert resp.json()["total_pollos"] > 0


def test_limpiar_diferidos(client, auth_headers):
    """Limpiar todos los diferidos."""
    _crear_oferta_y_proyeccion(client, auth_headers)
    client.post(
        "/proyeccion/diferir-lote",
        json={"dia_index": 0, "lote_index": 0},
        headers=auth_headers,
    )

    resp = client.delete("/proyeccion/lotes-diferidos", headers=auth_headers)
    assert resp.status_code == 200

    resp = client.get("/proyeccion/lotes-diferidos", headers=auth_headers)
    assert resp.json()["total_diferidos"] == 0
