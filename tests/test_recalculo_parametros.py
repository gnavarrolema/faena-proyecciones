"""Tests para verificar que al actualizar parámetros se recalcula la proyección."""
from datetime import date
import pytest
from fastapi.testclient import TestClient
from backend.main import app
from backend.calculo import LoteOferta, Parametros, SemanaFaena, aplicar_ajuste_martes
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


def test_update_parametros_sin_ofertas_recalcula_proyeccion_actual(client, auth_headers):
    """Con proyección vigente, debe recalcular aunque la oferta original ya no esté disponible."""
    proy_original = _crear_oferta_y_proyeccion(client, auth_headers)
    storage.delete_ofertas()

    r = client.put("/parametros", json={
        "ganancia_diaria_macho": 0.12,
    }, headers=auth_headers)
    assert r.status_code == 200
    data = r.json()
    assert data["proyeccion_recalculada"] is True

    r = client.get("/proyeccion", headers=auth_headers)
    assert r.status_code == 200
    proy_nueva = r.json()

    lote_original = next(l for dia in proy_original["dias"] for l in dia["lotes"] if l["sexo"] == "M")
    lote_nuevo = next(l for dia in proy_nueva["dias"] for l in dia["lotes"] if l["sexo"] == "M")
    assert lote_nuevo["peso_vivo_retiro"] != lote_original["peso_vivo_retiro"]


def test_config_generacion_se_guarda(client, auth_headers):
    """Al generar proyección se guarda la configuración de generación."""
    _crear_oferta_y_proyeccion(client, auth_headers)
    config = storage.load_proyeccion_config()
    assert config is not None
    assert config["fecha_inicio_semana"] == "2026-02-23"
    assert config["dias_faena"] == 5
    assert config["pollos_por_dia"] == 35000


def test_get_proyeccion_persiste_planificacion_alternativa(client, auth_headers):
    """La alternativa debe seguir disponible al recargar la proyección guardada."""
    proy = _crear_oferta_y_proyeccion(client, auth_headers)

    assert proy["modo_planificacion"] in {"cascada_madurez", "optimizacion_restricciones"}
    assert proy.get("planificacion_alternativa") is not None
    assert storage.load_proyeccion_alternativa() is not None

    r = client.get("/proyeccion", headers=auth_headers)
    assert r.status_code == 200
    data = r.json()

    assert data["modo_planificacion"] == proy["modo_planificacion"]
    assert data["planificacion_alternativa"]["modo_planificacion"] == proy["planificacion_alternativa"]["modo_planificacion"]


def test_activar_proyeccion_persiste_swap_de_alternativa(client, auth_headers):
    """Al activar la alternativa, la proyección guardada debe reflejar ambos modos intercambiados."""
    proy = _crear_oferta_y_proyeccion(client, auth_headers)
    alternativa = proy["planificacion_alternativa"]
    principal = {k: v for k, v in proy.items() if k != "planificacion_alternativa"}

    r = client.post(
        "/proyeccion/activar",
        json={
            "proyeccion": alternativa,
            "planificacion_alternativa": principal,
        },
        headers=auth_headers,
    )
    assert r.status_code == 200

    r = client.get("/proyeccion", headers=auth_headers)
    assert r.status_code == 200
    data = r.json()

    assert data["modo_planificacion"] == alternativa["modo_planificacion"]
    assert data["planificacion_alternativa"]["modo_planificacion"] == principal["modo_planificacion"]


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


def test_update_parametros_preserva_datos_del_ajuste_martes(client, auth_headers):
    """Si la proyección ya fue ajustada con oferta del martes, el recálculo debe mantener esos datos."""
    _crear_oferta_y_proyeccion(client, auth_headers)

    semana = SemanaFaena(**storage.load_proyeccion())
    oferta_martes = [
        LoteOferta(
            fecha_peso=date(2026, 2, 23),
            granja="GRANJA_A", galpon=1, nucleo=1, cantidad=16000,
            sexo="M", edad_proyectada=41, peso_muestreo_proy=3.05,
            ganancia_diaria=0.095, dias_proyectados=0, edad_real=41,
            peso_muestreo_real=3.05, fecha_ingreso=date(2026, 1, 14),
        ),
        LoteOferta(
            fecha_peso=date(2026, 2, 23),
            granja="GRANJA_B", galpon=2, nucleo=1, cantidad=20000,
            sexo="H", edad_proyectada=44, peso_muestreo_proy=2.50,
            ganancia_diaria=0.079, dias_proyectados=0, edad_real=44,
            peso_muestreo_real=2.50, fecha_ingreso=date(2026, 1, 10),
        ),
    ]

    semana_ajustada, _ = aplicar_ajuste_martes(oferta_martes, semana, Parametros())
    storage.save_ofertas_martes([o.model_dump() for o in oferta_martes])
    storage.save_proyeccion(semana_ajustada.model_dump())

    r = client.put("/parametros", json={
        "ganancia_diaria_macho": 0.1,
    }, headers=auth_headers)
    assert r.status_code == 200
    assert r.json()["proyeccion_recalculada"] is True

    r = client.get("/proyeccion", headers=auth_headers)
    assert r.status_code == 200
    proy_nueva = r.json()
    lote_macho = next(l for dia in proy_nueva["dias"] for l in dia["lotes"] if l["granja"] == "GRANJA_A")
    assert lote_macho["cantidad"] == 16000
    assert lote_macho["peso_actual"] == 3.05
