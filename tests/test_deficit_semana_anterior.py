from datetime import date

import pytest
from fastapi.testclient import TestClient

from backend import storage
from backend.calculo import LoteOferta
from backend.config import ADMIN_PASSWORD, ADMIN_USERNAME
from backend.main import app


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
    r = client.post("/token", data={"username": ADMIN_USERNAME, "password": ADMIN_PASSWORD})
    assert r.status_code == 200
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


def _oferta(granja: str, galpon: int, cantidad: int) -> LoteOferta:
    return LoteOferta(
        fecha_peso=date(2026, 4, 20),
        granja=granja,
        galpon=galpon,
        nucleo=1,
        cantidad=cantidad,
        sexo="M",
        edad_proyectada=42,
        peso_muestreo_proy=2.8,
        ganancia_diaria=0.09,
        dias_proyectados=0,
        edad_real=42,
        peso_muestreo_real=2.8,
        fecha_ingreso=date(2026, 3, 9),
    )


def _guardar_deficit(ofertas: list[LoteOferta]) -> None:
    storage.save_deficit({
        "lotes": [],
        "ofertas_originales": [o.model_dump() for o in ofertas],
        "total_pollos": sum(o.cantidad for o in ofertas),
        "total_lotes": len(ofertas),
        "semana_origen": "2026-04-13",
        "fecha_guardado": "2026-04-20T09:00:00",
    })


def test_generar_incluye_deficit_sin_duplicar_y_lo_consume(client, auth_headers):
    oferta_base = [
        _oferta("GRANJA_A", 1, 10000),
        _oferta("GRANJA_B", 2, 12000),
    ]
    storage.save_ofertas([o.model_dump() for o in oferta_base])

    deficit_duplicado = _oferta("GRANJA_A", 1, 10000)
    deficit_unico = _oferta("GRANJA_C", 3, 8000)
    _guardar_deficit([deficit_duplicado, deficit_unico])

    r = client.post("/proyeccion/generar", json={
        "fecha_inicio_semana": "2026-04-20",
        "dias_faena": 5,
        "pollos_por_dia": 45000,
        "incluir_deficit": True,
    }, headers=auth_headers)

    assert r.status_code == 200
    data = r.json()
    deficit_info = data["deficit_semana_anterior"]
    assert deficit_info["lotes_agregados"] == 1
    assert deficit_info["pollos_agregados"] == 8000
    assert deficit_info["lotes_duplicados_omitidos"] == 1
    assert deficit_info["lotes_invalidos"] == 0
    assert storage.load_deficit() is None

    r = client.get("/proyeccion/deficit-guardado", headers=auth_headers)
    assert r.status_code == 200
    assert r.json()["existe"] is False


def test_comparar_referencias_no_consume_deficit_hasta_aplicar(client, auth_headers):
    storage.save_ofertas([_oferta("GRANJA_A", 1, 10000).model_dump()])
    _guardar_deficit([_oferta("GRANJA_C", 3, 8000)])

    r = client.post("/proyeccion/generar-escenarios", json={
        "fecha_inicio_semana": "2026-04-20",
        "dias_faena": 5,
        "pollos_por_dia": 45000,
        "incluir_deficit": True,
    }, headers=auth_headers)

    assert r.status_code == 200
    data = r.json()
    assert data["deficit_semana_anterior"]["lotes_agregados"] == 1
    assert storage.load_deficit() is not None

    variante = data["variantes"][0]["proyeccion"]
    r = client.post("/proyeccion/aplicar-variante", json=variante, headers=auth_headers)

    assert r.status_code == 200
    assert storage.load_deficit() is None
