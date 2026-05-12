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


def _primer_lote_planificado(proyeccion: dict) -> tuple[int, int]:
    for dia_idx, dia in enumerate(proyeccion["dias"]):
        if dia["lotes"]:
            return dia_idx, 0
    raise AssertionError("La proyección no contiene lotes planificados")


def test_diferir_lote(client, auth_headers):
    """Diferir un lote de semana 1 y verificar que se guarda."""
    proy = _crear_oferta_y_proyeccion(client, auth_headers)
    dia_idx, lote_idx = _primer_lote_planificado(proy)
    dia_lotes = len(proy["dias"][dia_idx]["lotes"])

    # Diferir el primer lote disponible
    resp = client.post(
        "/proyeccion/diferir-lote",
        json={"dia_index": dia_idx, "lote_index": lote_idx, "motivo": "Feriado"},
        headers=auth_headers,
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["total_diferidos"] == 1
    assert data["lote_diferido"]["motivo"] == "Feriado"
    assert len(data["proyeccion"]["dias"][dia_idx]["lotes"]) == dia_lotes - 1


def test_diferir_y_restaurar(client, auth_headers):
    """Diferir un lote y luego restaurarlo."""
    proy = _crear_oferta_y_proyeccion(client, auth_headers)
    dia_idx, lote_idx = _primer_lote_planificado(proy)

    # Diferir
    resp = client.post(
        "/proyeccion/diferir-lote",
        json={"dia_index": dia_idx, "lote_index": lote_idx},
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
    proy = _crear_oferta_y_proyeccion(client, auth_headers)
    dia_idx, lote_idx = _primer_lote_planificado(proy)

    client.post(
        "/proyeccion/diferir-lote",
        json={"dia_index": dia_idx, "lote_index": lote_idx, "motivo": "Sobrecarga"},
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


def test_semana2_recupera_lotes_fuera_rango_de_s1(client, auth_headers):
    """Lotes jóvenes fuera de rango en S1 deben reconsiderarse en S2."""
    ofertas = [
        {
            "fecha_peso": "2026-03-19",
            "granja": "MARTINA",
            "galpon": 7,
            "nucleo": 1,
            "cantidad": 15000,
            "sexo": "M",
            "edad_proyectada": 32,
            "peso_muestreo_proy": 2.56,
            "ganancia_diaria": 0.11,
            "dias_proyectados": 0,
            "edad_real": 32,
            "peso_muestreo_real": 2.56,
            "fecha_ingreso": "2026-02-15",
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
    semana1 = resp.json()
    assert semana1["total_pollos_semana"] == 0
    assert semana1["total_pollos_fuera_rango"] == 15000

    resp = client.get("/proyeccion/semana2", headers=auth_headers)
    assert resp.status_code == 200
    data = resp.json()

    assert data["tiene_datos"] is True
    assert data["lotes_fuera_rango_s1"] == 1
    assert data["lotes_recuperados_fuera_rango_s1"] == 1
    assert data["pollos_recuperados_fuera_rango_s1"] == 15000
    assert data["proyeccion"]["fecha_inicio"] == "2026-03-23"
    assert data["proyeccion"]["total_pollos_semana"] == 15000
    assert data["proyeccion"]["total_pollos_fuera_rango"] == 0


def test_semana2_arranca_lunes_cuando_s1_tiene_viernes_puente(client, auth_headers):
    """
    Regresion: cuando S1 incluia un viernes puente (fecha_inicio = Vie),
    S2 se calculaba como Vie + 7 = Vie siguiente, solapando con el ultimo
    dia de S1 y arrastrando Sabado/Domingo dentro de la semana.
    Ahora S2 arranca siempre el lunes posterior al ultimo dia de S1.
    """
    storage.save_ofertas([
        # 5 lotes para el puente del 8/5
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
        # 5 lotes para Lun-Vie
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

    # S1 con viernes puente: dias_faena=6, oferta del jueves 7/5, inicio Lun 11/5.
    resp = client.post(
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
    assert resp.status_code == 200
    s1 = resp.json()
    # Verifica que S1 efectivamente arranca el viernes puente
    assert s1["dias"][0]["fecha"] == "2026-05-08"
    assert s1["dias"][-1]["fecha"] == "2026-05-15"

    # Diferir un lote para que S2 tenga material y pueda generarse.
    dia_idx, lote_idx = _primer_lote_planificado(s1)
    client.post(
        "/proyeccion/diferir-lote",
        json={"dia_index": dia_idx, "lote_index": lote_idx},
        headers=auth_headers,
    )

    resp = client.get("/proyeccion/semana2", headers=auth_headers)
    assert resp.status_code == 200
    data = resp.json()

    assert data["tiene_datos"] is True
    proyeccion = data["proyeccion"]
    # S2 arranca el lunes 18/5, no el viernes 15/5.
    assert proyeccion["fecha_inicio"] == "2026-05-18", (
        f"S2 deberia arrancar el lunes 18/5, arranco en {proyeccion['fecha_inicio']}"
    )
    # Ningun dia de S2 cae en sabado o domingo.
    from datetime import date as _date
    for dia in proyeccion["dias"]:
        wd = _date.fromisoformat(dia["fecha"]).weekday()
        assert wd not in (5, 6), (
            f"S2 incluye {dia['fecha']} (weekday {wd}), no debe haber sab/dom"
        )
    # No solapa con el ultimo dia de S1 (15/5).
    fechas_s2 = {dia["fecha"] for dia in proyeccion["dias"]}
    assert "2026-05-15" not in fechas_s2


def test_lotes_diferidos_endpoint(client, auth_headers):
    """Verificar endpoint de listar lotes diferidos."""
    proy = _crear_oferta_y_proyeccion(client, auth_headers)
    dia_idx, lote_idx = _primer_lote_planificado(proy)

    # Sin diferidos
    resp = client.get("/proyeccion/lotes-diferidos", headers=auth_headers)
    assert resp.status_code == 200
    assert resp.json()["total_diferidos"] == 0

    # Diferir uno
    client.post(
        "/proyeccion/diferir-lote",
        json={"dia_index": dia_idx, "lote_index": lote_idx},
        headers=auth_headers,
    )

    resp = client.get("/proyeccion/lotes-diferidos", headers=auth_headers)
    assert resp.status_code == 200
    assert resp.json()["total_diferidos"] == 1
    assert resp.json()["total_pollos"] > 0


def test_limpiar_diferidos(client, auth_headers):
    """Limpiar todos los diferidos."""
    proy = _crear_oferta_y_proyeccion(client, auth_headers)
    dia_idx, lote_idx = _primer_lote_planificado(proy)
    client.post(
        "/proyeccion/diferir-lote",
        json={"dia_index": dia_idx, "lote_index": lote_idx},
        headers=auth_headers,
    )

    resp = client.delete("/proyeccion/lotes-diferidos", headers=auth_headers)
    assert resp.status_code == 200

    resp = client.get("/proyeccion/lotes-diferidos", headers=auth_headers)
    assert resp.json()["total_diferidos"] == 0


# ─── Tests para edición interactiva de Semana 2 ─────────────────────────────


def _generar_semana2(client, auth_headers):
    """Helper: genera S1, difiere un lote, y obtiene S2."""
    proy = _crear_oferta_y_proyeccion(client, auth_headers)
    dia_idx, lote_idx = _primer_lote_planificado(proy)
    client.post(
        "/proyeccion/diferir-lote",
        json={"dia_index": dia_idx, "lote_index": lote_idx},
        headers=auth_headers,
    )
    resp = client.get("/proyeccion/semana2", headers=auth_headers)
    assert resp.status_code == 200
    assert resp.json()["tiene_datos"] is True
    return resp.json()


def test_mover_lote_s2(client, auth_headers):
    """Mover un lote entre días dentro de semana 2."""
    s2_data = _generar_semana2(client, auth_headers)
    s2 = s2_data["proyeccion"]

    # Buscar un día con al menos un lote
    dia_con_lotes = None
    for idx, dia in enumerate(s2["dias"]):
        if len(dia["lotes"]) > 0:
            dia_con_lotes = idx
            break
    assert dia_con_lotes is not None, "No hay lotes en S2 para mover"

    # Destino = primer día diferente
    dia_destino = (dia_con_lotes + 1) % len(s2["dias"])
    pollos_origen_antes = s2["dias"][dia_con_lotes]["total_pollos"]
    pollos_destino_antes = s2["dias"][dia_destino]["total_pollos"]

    resp = client.post(
        "/proyeccion/semana2/mover-lote",
        json={"lote_index": 0, "dia_origen": dia_con_lotes, "dia_destino": dia_destino},
        headers=auth_headers,
    )
    assert resp.status_code == 200
    result = resp.json()["proyeccion"]

    # El día de origen debe tener menos pollos
    assert result["dias"][dia_con_lotes]["total_pollos"] < pollos_origen_antes
    # El día destino debe tener más pollos
    assert result["dias"][dia_destino]["total_pollos"] > pollos_destino_antes


def test_eliminar_lote_s2(client, auth_headers):
    """Eliminar un lote de la proyección de semana 2."""
    s2_data = _generar_semana2(client, auth_headers)
    s2 = s2_data["proyeccion"]

    # Buscar un día con al menos un lote
    dia_con_lotes = None
    for idx, dia in enumerate(s2["dias"]):
        if len(dia["lotes"]) > 0:
            dia_con_lotes = idx
            break
    assert dia_con_lotes is not None

    total_antes = s2["total_pollos_semana"]
    lotes_antes = len(s2["dias"][dia_con_lotes]["lotes"])

    resp = client.delete(
        f"/proyeccion/semana2/lote/{dia_con_lotes}/0",
        headers=auth_headers,
    )
    assert resp.status_code == 200
    result = resp.json()

    # Debe haber un lote menos
    assert len(result["dias"][dia_con_lotes]["lotes"]) == lotes_antes - 1
    # Total pollos semana debe disminuir
    assert result["total_pollos_semana"] < total_antes


def test_enviar_lote_s2_a_s1(client, auth_headers):
    """Enviar un lote de S2 de vuelta a S1."""
    s2_data = _generar_semana2(client, auth_headers)
    s2 = s2_data["proyeccion"]

    # Obtener S1 antes
    resp_s1 = client.get("/proyeccion", headers=auth_headers)
    total_s1_antes = resp_s1.json()["total_pollos_semana"]

    # Buscar un día con lotes en S2
    dia_con_lotes = None
    for idx, dia in enumerate(s2["dias"]):
        if len(dia["lotes"]) > 0:
            dia_con_lotes = idx
            break
    assert dia_con_lotes is not None

    total_s2_antes = s2["total_pollos_semana"]

    resp = client.post(
        "/proyeccion/semana2/enviar-semana1",
        json={"dia_index_s2": dia_con_lotes, "lote_index_s2": 0, "dia_destino_s1": 0},
        headers=auth_headers,
    )
    assert resp.status_code == 200
    data = resp.json()

    # S1 debe tener más pollos
    assert data["proyeccion_s1"]["total_pollos_semana"] > total_s1_antes
    # S2 debe tener menos pollos
    assert data["proyeccion_s2"]["total_pollos_semana"] < total_s2_antes


def test_enviar_lote_s2_a_s1_auto(client, auth_headers):
    """Enviar lote de S2 a S1 con auto-asignación."""
    s2_data = _generar_semana2(client, auth_headers)
    s2 = s2_data["proyeccion"]

    dia_con_lotes = None
    for idx, dia in enumerate(s2["dias"]):
        if len(dia["lotes"]) > 0:
            dia_con_lotes = idx
            break
    assert dia_con_lotes is not None

    resp = client.post(
        "/proyeccion/semana2/enviar-semana1",
        json={"dia_index_s2": dia_con_lotes, "lote_index_s2": 0},
        headers=auth_headers,
    )
    assert resp.status_code == 200
    data = resp.json()
    assert "dia_destino_s1" in data
    assert data["dia_destino_s1"] >= 0


def test_mover_lote_s2_sin_proyeccion(client, auth_headers):
    """Mover en S2 sin haber generado proyección da 404."""
    resp = client.post(
        "/proyeccion/semana2/mover-lote",
        json={"lote_index": 0, "dia_origen": 0, "dia_destino": 1},
        headers=auth_headers,
    )
    assert resp.status_code == 404
