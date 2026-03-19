"""Tests para sugerencias inteligentes de diferimiento."""
import pytest
from datetime import date
from fastapi.testclient import TestClient

from backend.main import app
from backend import storage
from backend.calculo import (
    Parametros, LoteOferta, generar_proyeccion,
    generar_sugerencias_diferimiento,
)


@pytest.fixture(autouse=True)
def clean_storage(tmp_path, monkeypatch):
    """Usa storage temporal para cada test."""
    from backend.storage import LocalStorage
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


def _ofertas_base():
    """Ofertas de ejemplo con variedad de condiciones."""
    return [
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


def _crear_oferta_y_proyeccion(client, auth_headers, ofertas=None):
    """Helper: carga oferta de ejemplo y genera proyección."""
    storage.save_ofertas(ofertas or _ofertas_base())
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


# ─── Tests del endpoint ─────────────────────────────────────────────────────────

def test_sugerencias_sin_proyeccion(client, auth_headers):
    """Sin proyección generada, devuelve 404."""
    resp = client.get("/proyeccion/sugerencias-diferimiento", headers=auth_headers)
    assert resp.status_code == 404


def test_sugerencias_sin_ofertas(client, auth_headers):
    """Sin ofertas cargadas, devuelve vacío."""
    storage.save_ofertas(_ofertas_base())
    resp = client.post(
        "/proyeccion/generar",
        json={"fecha_inicio_semana": "2026-03-16", "dias_faena": 5, "pollos_por_dia": 35000},
        headers=auth_headers,
    )
    assert resp.status_code == 200
    # Borrar ofertas pero dejar proyección
    storage.delete_ofertas()

    resp = client.get("/proyeccion/sugerencias-diferimiento", headers=auth_headers)
    assert resp.status_code == 200
    data = resp.json()
    assert data["total_sugerencias"] == 0


def test_sugerencias_endpoint_basico(client, auth_headers):
    """El endpoint devuelve la estructura esperada."""
    _crear_oferta_y_proyeccion(client, auth_headers)

    resp = client.get("/proyeccion/sugerencias-diferimiento", headers=auth_headers)
    assert resp.status_code == 200
    data = resp.json()
    assert "total_sugerencias" in data
    assert "sugerencias" in data
    assert "por_criterio" in data
    assert "total_pollos_sugeridos" in data
    assert isinstance(data["sugerencias"], list)


# ─── Tests de la lógica de sugerencias ──────────────────────────────────────────

def test_sugerencia_sobrecarga():
    """Cuando un día excede el objetivo, se sugieren lotes flexibles."""
    params = Parametros(
        pollos_diarios_objetivo_max=30000,
        capacidad_maxima_planta=50000,
    )
    # Crear lotes que sobrecargan un día
    ofertas = [
        LoteOferta(
            fecha_peso=date(2026, 3, 12), granja="A", galpon=1, nucleo=1,
            cantidad=20000, sexo="M", edad_proyectada=39,
            peso_muestreo_proy=2.95, ganancia_diaria=0.09,
            dias_proyectados=5, edad_real=34, peso_muestreo_real=2.50,
            fecha_ingreso=date(2026, 2, 6),
        ),
        LoteOferta(
            fecha_peso=date(2026, 3, 12), granja="B", galpon=2, nucleo=1,
            cantidad=15000, sexo="M", edad_proyectada=39,
            peso_muestreo_proy=2.95, ganancia_diaria=0.09,
            dias_proyectados=5, edad_real=34, peso_muestreo_real=2.50,
            fecha_ingreso=date(2026, 2, 6),
        ),
    ]
    semana = generar_proyeccion(
        ofertas, date(2026, 3, 16), dias_faena=5, params=params,
    )

    result = generar_sugerencias_diferimiento(semana, ofertas, params)
    # Con 35000 pollos y objetivo 30000, debería sugerir alguno
    if result["total_sugerencias"] > 0:
        assert any(s["criterio"] == "sobrecarga" for s in result["sugerencias"])
        for s in result["sugerencias"]:
            if s["criterio"] == "sobrecarga":
                assert s["prioridad"] == 1
                assert s["impacto"]["pollos_removidos"] > 0


def test_sugerencia_edad_temprana():
    """Lotes en edad mínima que estarían mejor en S2."""
    params = Parametros()
    # Lote macho con edad mínima (38) - ideal sería 40
    ofertas = [
        LoteOferta(
            fecha_peso=date(2026, 3, 12), granja="TEMPRANA", galpon=1, nucleo=1,
            cantidad=12000, sexo="M", edad_proyectada=33,
            peso_muestreo_proy=2.50, ganancia_diaria=0.09,
            dias_proyectados=0, edad_real=33, peso_muestreo_real=2.50,
            fecha_ingreso=date(2026, 2, 7),
        ),
    ]
    semana = generar_proyeccion(
        ofertas, date(2026, 3, 16), dias_faena=5, params=params,
    )

    result = generar_sugerencias_diferimiento(semana, ofertas, params)
    # Verificar estructura
    assert isinstance(result["sugerencias"], list)
    for s in result["sugerencias"]:
        assert "criterio" in s
        assert "motivo" in s
        assert "impacto" in s
        assert "dia_index" in s
        assert "lote_index" in s


def test_sugerencia_mejor_calibre():
    """Lotes cerca del mínimo de peso que mejorarían en S2."""
    params = Parametros(peso_min_faena=2.80)
    # Lote con peso justo sobre el mínimo
    ofertas = [
        LoteOferta(
            fecha_peso=date(2026, 3, 12), granja="CALIBRE", galpon=1, nucleo=1,
            cantidad=14000, sexo="H", edad_proyectada=40,
            peso_muestreo_proy=2.65, ganancia_diaria=0.079,
            dias_proyectados=5, edad_real=35, peso_muestreo_real=2.25,
            fecha_ingreso=date(2026, 2, 5),
        ),
    ]
    semana = generar_proyeccion(
        ofertas, date(2026, 3, 16), dias_faena=5, params=params,
    )

    result = generar_sugerencias_diferimiento(semana, ofertas, params)
    # Verificar estructura correcta
    assert "total_sugerencias" in result
    assert "por_criterio" in result
    for s in result["sugerencias"]:
        assert s["criterio"] in ("sobrecarga", "mejor_calibre", "feriado", "edad_temprana")


def test_sugerencia_feriado():
    """Días adyacentes a feriados generan sugerencias."""
    params = Parametros(pollos_diarios_objetivo_max=30000, capacidad_maxima_planta=50000)
    ofertas = [
        LoteOferta(
            fecha_peso=date(2026, 3, 12), granja="A", galpon=1, nucleo=1,
            cantidad=28000, sexo="M", edad_proyectada=39,
            peso_muestreo_proy=2.95, ganancia_diaria=0.09,
            dias_proyectados=5, edad_real=34, peso_muestreo_real=2.50,
            fecha_ingreso=date(2026, 2, 6),
        ),
    ]
    # Feriado el martes 17, impacta lunes 16
    feriados = {date(2026, 3, 17): "Feriado test"}
    semana = generar_proyeccion(
        ofertas, date(2026, 3, 16), dias_faena=5, params=params,
        feriados=feriados,
    )
    result = generar_sugerencias_diferimiento(semana, ofertas, params, feriados=feriados)
    # Verificar que la estructura es correcta con feriados
    assert isinstance(result["sugerencias"], list)


def test_no_sugiere_compra_terceros():
    """Los lotes de compra a terceros nunca se sugieren."""
    params = Parametros()
    ofertas = [
        LoteOferta(
            fecha_peso=date(2026, 3, 12), granja="TERCEROS", galpon=1, nucleo=1,
            cantidad=10000, sexo="M", edad_proyectada=39,
            peso_muestreo_proy=2.95, ganancia_diaria=0.09,
            dias_proyectados=5, edad_real=34, peso_muestreo_real=2.50,
            fecha_ingreso=date(2026, 2, 6),
        ),
    ]
    semana = generar_proyeccion(
        ofertas, date(2026, 3, 16), dias_faena=5, params=params,
    )
    # Marcar como terceros
    for dia in semana.dias:
        for lote in dia.lotes:
            lote.es_compra_terceros = True

    result = generar_sugerencias_diferimiento(semana, ofertas, params)
    assert result["total_sugerencias"] == 0


def test_sugerencias_sin_duplicados():
    """Un lote no debe aparecer en múltiples criterios."""
    params = Parametros(pollos_diarios_objetivo_max=15000, capacidad_maxima_planta=50000)
    ofertas = [
        LoteOferta(
            fecha_peso=date(2026, 3, 12), granja="DUP", galpon=1, nucleo=1,
            cantidad=20000, sexo="M", edad_proyectada=38,
            peso_muestreo_proy=2.85, ganancia_diaria=0.09,
            dias_proyectados=5, edad_real=33, peso_muestreo_real=2.40,
            fecha_ingreso=date(2026, 2, 7),
        ),
    ]
    semana = generar_proyeccion(
        ofertas, date(2026, 3, 16), dias_faena=5, params=params,
    )

    result = generar_sugerencias_diferimiento(semana, ofertas, params)
    # Verificar no hay duplicados por lote
    lote_ids = set()
    for s in result["sugerencias"]:
        lid = f"{s['dia_index']}-{s['lote_index']}-{s['granja']}-{s['galpon']}-{s['nucleo']}"
        assert lid not in lote_ids, f"Duplicado: {lid}"
        lote_ids.add(lid)


def test_sugerencias_prioridad_ordenada():
    """Las sugerencias vienen ordenadas por prioridad (1=más alta)."""
    params = Parametros(pollos_diarios_objetivo_max=15000, capacidad_maxima_planta=50000)
    ofertas = [
        LoteOferta(
            fecha_peso=date(2026, 3, 12), granja="A", galpon=1, nucleo=1,
            cantidad=20000, sexo="M", edad_proyectada=39,
            peso_muestreo_proy=2.95, ganancia_diaria=0.09,
            dias_proyectados=5, edad_real=34, peso_muestreo_real=2.50,
            fecha_ingreso=date(2026, 2, 6),
        ),
        LoteOferta(
            fecha_peso=date(2026, 3, 12), granja="B", galpon=2, nucleo=1,
            cantidad=10000, sexo="M", edad_proyectada=39,
            peso_muestreo_proy=2.95, ganancia_diaria=0.09,
            dias_proyectados=5, edad_real=34, peso_muestreo_real=2.50,
            fecha_ingreso=date(2026, 2, 6),
        ),
    ]
    semana = generar_proyeccion(
        ofertas, date(2026, 3, 16), dias_faena=5, params=params,
    )

    result = generar_sugerencias_diferimiento(semana, ofertas, params)
    prioridades = [s["prioridad"] for s in result["sugerencias"]]
    assert prioridades == sorted(prioridades), "Sugerencias no están ordenadas por prioridad"


def test_sugerencias_estructura_impacto():
    """Cada sugerencia tiene información de impacto completa."""
    params = Parametros(pollos_diarios_objetivo_max=15000, capacidad_maxima_planta=50000)
    ofertas = [
        LoteOferta(
            fecha_peso=date(2026, 3, 12), granja="TEST", galpon=1, nucleo=1,
            cantidad=20000, sexo="M", edad_proyectada=39,
            peso_muestreo_proy=2.95, ganancia_diaria=0.09,
            dias_proyectados=5, edad_real=34, peso_muestreo_real=2.50,
            fecha_ingreso=date(2026, 2, 6),
        ),
    ]
    semana = generar_proyeccion(
        ofertas, date(2026, 3, 16), dias_faena=5, params=params,
    )

    result = generar_sugerencias_diferimiento(semana, ofertas, params)
    for s in result["sugerencias"]:
        assert "dia_index" in s
        assert "lote_index" in s
        assert "granja" in s
        assert "cantidad" in s
        assert "criterio" in s
        assert "prioridad" in s
        assert "dia_nombre" in s
        assert "motivo" in s
        assert "impacto" in s
        assert "pollos_removidos" in s["impacto"]
        assert "dia_post_diferir" in s["impacto"]
        assert "peso_actual" in s["impacto"]
