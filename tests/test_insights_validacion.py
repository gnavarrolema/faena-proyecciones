"""Tests para el endpoint GET /validacion-cruzada y la función _generar_insights_validacion."""
from datetime import date, timedelta

import pytest
from backend.main import app, _generar_insights_validacion
from backend.calculo import LoteOferta
from backend.parser_produccion import SemanaProduccion, DIAS_HASTA_FAENA
from backend import storage

from fastapi.testclient import TestClient

client = TestClient(app)


@pytest.fixture(autouse=True)
def clean_storage(tmp_path, monkeypatch):
    monkeypatch.setenv("STORAGE_BACKEND", "local")
    monkeypatch.setenv("LOCAL_STORAGE_PATH", str(tmp_path))
    storage._storage_instance = storage.LocalStorage(str(tmp_path))
    yield
    storage._storage_instance = None


@pytest.fixture
def auth_header(monkeypatch):
    """Genera un token válido para los requests."""
    from backend.auth import create_access_token
    token = create_access_token(data={"sub": "admin"})
    return {"Authorization": f"Bearer {token}"}


def _lote(
    granja="GRANJA_A",
    cantidad=5000,
    fecha_peso=date(2026, 3, 16),
    fecha_ingreso=date(2026, 2, 2),
    edad_real=42,
) -> LoteOferta:
    return LoteOferta(
        fecha_peso=fecha_peso,
        granja=granja,
        galpon=1,
        nucleo=1,
        cantidad=cantidad,
        sexo="M",
        edad_proyectada=42,
        peso_muestreo_proy=2.80,
        ganancia_diaria=0.09,
        dias_proyectados=0,
        edad_real=edad_real,
        peso_muestreo_real=2.80,
        fecha_ingreso=fecha_ingreso,
    )


def _guardar_produccion(fecha_desde: date, pollitos: int):
    sem = SemanaProduccion(
        fecha_desde=fecha_desde,
        fecha_hasta=fecha_desde + timedelta(days=6),
        pollitos_cargados=pollitos,
    )
    storage.save_produccion([sem.model_dump()])


# ─── Tests para _generar_insights_validacion ─────────────────────────────────────

class TestGenerarInsights:
    def test_sin_datos_retorna_lista_vacia(self):
        assert _generar_insights_validacion({}) == []

    def test_insight_deficit(self):
        validacion = {
            "factibilidad": {
                "encontrada": True,
                "total_oferta": 100000,
                "disponibles_peor": 93500,
                "disponibles_mejor": 95500,
                "deficit_peor": 6500,
                "cobertura_pct_peor": 106.95,
                "pollitos_cargados": 100000,
            }
        }
        insights = _generar_insights_validacion(validacion)
        criticos = [i for i in insights if i["tipo"] == "critico"]
        assert len(criticos) >= 1
        assert any("Déficit" in i["titulo"] for i in criticos)

    def test_insight_superavit(self):
        validacion = {
            "factibilidad": {
                "encontrada": True,
                "total_oferta": 50000,
                "disponibles_peor": 93500,
                "disponibles_mejor": 95500,
                "deficit_peor": None,
                "cobertura_pct_peor": 53.5,
                "pollitos_cargados": 100000,
            }
        }
        insights = _generar_insights_validacion(validacion)
        positivos = [i for i in insights if i["tipo"] == "positivo"]
        assert len(positivos) >= 1
        assert any("suficiente" in i["titulo"].lower() for i in positivos)

    def test_insight_cobertura_ajustada(self):
        validacion = {
            "factibilidad": {
                "encontrada": True,
                "total_oferta": 90000,
                "disponibles_peor": 93500,
                "disponibles_mejor": 95500,
                "deficit_peor": None,
                "cobertura_pct_peor": 96.3,
                "pollitos_cargados": 100000,
            }
        }
        insights = _generar_insights_validacion(validacion)
        advertencias = [i for i in insights if i["tipo"] == "advertencia"]
        assert any("ajustada" in i["titulo"].lower() for i in advertencias)

    def test_insight_mortalidad_critica(self):
        validacion = {
            "mortalidad_cohortes": {
                "cohortes": [
                    {
                        "nivel": "critica",
                        "mortalidad_pct": 15.0,
                        "granjas": ["GRANJA_A", "GRANJA_B"],
                    },
                ],
                "total_cohortes": 1,
                "alertas": 1,
            }
        }
        insights = _generar_insights_validacion(validacion)
        criticos = [i for i in insights if i["tipo"] == "critico" and i["categoria"] == "mortalidad"]
        assert len(criticos) == 1
        assert "crítica" in criticos[0]["titulo"].lower()

    def test_insight_mortalidad_elevada(self):
        validacion = {
            "mortalidad_cohortes": {
                "cohortes": [
                    {"nivel": "elevada", "mortalidad_pct": 8.5, "granjas": ["G1"]},
                ],
                "total_cohortes": 1,
                "alertas": 1,
            }
        }
        insights = _generar_insights_validacion(validacion)
        advs = [i for i in insights if i["tipo"] == "advertencia" and i["categoria"] == "mortalidad"]
        assert len(advs) == 1

    def test_insight_datos_inconsistentes(self):
        validacion = {
            "mortalidad_cohortes": {
                "cohortes": [
                    {"nivel": "inconsistente", "mortalidad_pct": -5.0, "granjas": ["G1"]},
                ],
                "total_cohortes": 1,
                "alertas": 1,
            }
        }
        insights = _generar_insights_validacion(validacion)
        criticos = [i for i in insights if i["tipo"] == "critico" and i["categoria"] == "datos"]
        assert len(criticos) == 1

    def test_insight_consistencia_edad(self):
        validacion = {
            "consistencia_edad": {
                "total": 3,
                "alertas": [
                    {"lote": 1, "granja": "G1", "galpon": 1, "edad_real": 35, "dias_calculados": 42, "diferencia": 7},
                    {"lote": 2, "granja": "G2", "galpon": 2, "edad_real": 30, "dias_calculados": 42, "diferencia": 12},
                    {"lote": 3, "granja": "G3", "galpon": 1, "edad_real": 50, "dias_calculados": 42, "diferencia": 8},
                ],
            }
        }
        insights = _generar_insights_validacion(validacion)
        info = [i for i in insights if i["categoria"] == "consistencia"]
        assert len(info) == 1
        assert "3" in info[0]["titulo"]

    def test_insight_tendencia_mortalidad_alza(self):
        """Cohortes con mortalidad creciente generan insight de tendencia."""
        validacion = {
            "mortalidad_cohortes": {
                "cohortes": [
                    {"nivel": "excelente", "mortalidad_pct": 3.5, "granjas": ["G1"]},
                    {"nivel": "normal", "mortalidad_pct": 4.0, "granjas": ["G1"]},
                    {"nivel": "normal", "mortalidad_pct": 5.5, "granjas": ["G1"]},
                    {"nivel": "elevada", "mortalidad_pct": 7.0, "granjas": ["G1"]},
                ],
                "total_cohortes": 4,
                "alertas": 1,
            }
        }
        insights = _generar_insights_validacion(validacion)
        tendencia = [i for i in insights if i["categoria"] == "tendencia"]
        assert len(tendencia) == 1
        assert "alza" in tendencia[0]["titulo"].lower()

    def test_insight_sensibilidad(self):
        validacion = {
            "factibilidad": {
                "encontrada": True,
                "total_oferta": 50000,
                "disponibles_peor": 93500,
                "disponibles_mejor": 95500,
                "deficit_peor": None,
                "cobertura_pct_peor": 53.5,
                "pollitos_cargados": 100000,
            }
        }
        insights = _generar_insights_validacion(validacion)
        sens = [i for i in insights if i["categoria"] == "sensibilidad"]
        assert len(sens) == 1
        assert "2.000" in sens[0]["detalle"] or "2,000" in sens[0]["detalle"]


# ─── Tests para endpoint GET /validacion-cruzada ────────────────────────────────

class TestEndpointValidacionCruzada:
    def test_sin_datos_retorna_404(self, auth_header):
        resp = client.get("/validacion-cruzada", headers=auth_header)
        assert resp.status_code == 404

    def test_solo_produccion(self, auth_header):
        _guardar_produccion(date(2026, 2, 2), 100000)
        resp = client.get("/validacion-cruzada", headers=auth_header)
        assert resp.status_code == 200
        data = resp.json()
        assert data["tiene_produccion"] is True
        assert data["tiene_oferta"] is False

    def test_con_oferta_y_produccion(self, auth_header):
        fecha_prod = date(2026, 2, 2)
        fecha_faena = fecha_prod + timedelta(days=DIAS_HASTA_FAENA)
        _guardar_produccion(fecha_prod, 100000)

        ofertas = [_lote(cantidad=80000, fecha_peso=fecha_faena, fecha_ingreso=fecha_prod)]
        storage.save_ofertas([o.model_dump() for o in ofertas])

        resp = client.get("/validacion-cruzada", headers=auth_header)
        assert resp.status_code == 200
        data = resp.json()
        assert data["tiene_oferta"] is True
        assert data["tiene_produccion"] is True
        assert "factibilidad" in data["validacion"]
        assert len(data["insights"]) > 0

    def test_con_deficit_genera_insight_critico(self, auth_header):
        fecha_prod = date(2026, 2, 2)
        fecha_faena = fecha_prod + timedelta(days=DIAS_HASTA_FAENA)
        _guardar_produccion(fecha_prod, 50000)

        ofertas = [_lote(cantidad=50000, fecha_peso=fecha_faena, fecha_ingreso=fecha_prod)]
        storage.save_ofertas([o.model_dump() for o in ofertas])

        resp = client.get("/validacion-cruzada", headers=auth_header)
        assert resp.status_code == 200
        data = resp.json()
        criticos = [i for i in data["insights"] if i["tipo"] == "critico"]
        assert len(criticos) >= 1

    def test_requiere_autenticacion(self):
        resp = client.get("/validacion-cruzada")
        assert resp.status_code == 401
