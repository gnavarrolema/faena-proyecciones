"""
Tests de integración API para la funcionalidad de Ajuste con Oferta del Martes.
Usa TestClient de FastAPI (no requiere servidor corriendo).
"""
import pytest
import openpyxl
from io import BytesIO
from datetime import date, datetime

from fastapi.testclient import TestClient
from backend.main import app
from backend import storage


# ─── Fixtures ────────────────────────────────────────────────────────────────────

@pytest.fixture(autouse=True)
def clean_storage(tmp_path, monkeypatch):
    """Usa un directorio temporal para storage en cada test."""
    monkeypatch.setenv("STORAGE_BACKEND", "local")
    monkeypatch.setenv("LOCAL_STORAGE_PATH", str(tmp_path))
    # Reinicializar el singleton de storage con la nueva ruta temporal
    storage._storage_instance = storage.LocalStorage(str(tmp_path))
    yield
    storage._storage_instance = None


@pytest.fixture()
def client():
    return TestClient(app)


@pytest.fixture()
def auth_headers(client):
    r = client.post("/token", data={"username": "admin", "password": "admin123"})
    assert r.status_code == 200, f"Login failed: {r.text}"
    token = r.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


# ─── Helpers ─────────────────────────────────────────────────────────────────────

def _crear_excel_oferta(lotes_data, sheet_title="OFERTA MART"):
    """Crea un archivo Excel sintético con formato de oferta."""
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = sheet_title

    headers_row = [
        "Fecha de Peso", "GRANJA", "Galpon", "Nucleo", "cantidad",
        "sexo", "Edad Proyectada", "Peso Muestreo Proy", "Ganancia Diaria",
        "Dias proyectados", "EDAD REAL", "Peso Muestreo REAL", "FECHA DE INGRESO"
    ]
    for col, h in enumerate(headers_row, 1):
        ws.cell(row=3, column=col, value=h)

    for row_idx, lote in enumerate(lotes_data, 4):
        ws.cell(row=row_idx, column=1, value=datetime.combine(lote["fecha_peso"], datetime.min.time()))
        ws.cell(row=row_idx, column=2, value=lote["granja"])
        ws.cell(row=row_idx, column=3, value=lote["galpon"])
        ws.cell(row=row_idx, column=4, value=lote["nucleo"])
        ws.cell(row=row_idx, column=5, value=lote["cantidad"])
        ws.cell(row=row_idx, column=6, value=lote["sexo"])
        ws.cell(row=row_idx, column=7, value=lote["edad_proyectada"])
        ws.cell(row=row_idx, column=8, value=lote["peso_muestreo_proy"])
        ws.cell(row=row_idx, column=9, value=lote["ganancia_diaria"])
        ws.cell(row=row_idx, column=10, value=lote["dias_proyectados"])
        ws.cell(row=row_idx, column=11, value=lote["edad_real"])
        ws.cell(row=row_idx, column=12, value=lote["peso_muestreo_real"])
        ws.cell(row=row_idx, column=13, value=datetime.combine(lote["fecha_ingreso"], datetime.min.time()))

    buf = BytesIO()
    wb.save(buf)
    buf.seek(0)
    return buf


LOTE_BASE = {
    "fecha_peso": date(2026, 2, 23),
    "granja": "TEST",
    "galpon": 1,
    "nucleo": 1,
    "cantidad": 15000,
    "sexo": "M",
    "edad_proyectada": 40,
    "peso_muestreo_proy": 2.95,
    "ganancia_diaria": 0.09,
    "dias_proyectados": 0,
    "edad_real": 40,
    "peso_muestreo_real": 2.95,
    "fecha_ingreso": date(2026, 1, 10),
}


def _generar_proyeccion(client, auth_headers, lotes_data=None):
    """Sube oferta y genera proyección. Retorna la proyección."""
    lotes = lotes_data or [LOTE_BASE]
    excel = _crear_excel_oferta(lotes, sheet_title="OFERTA JUEV")
    client.post(
        "/oferta/upload",
        headers=auth_headers,
        files={"file": ("oferta.xlsx", excel, "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")},
    )
    r = client.post(
        "/proyeccion/generar",
        headers=auth_headers,
        json={"fecha_inicio_semana": "2026-02-23", "dias_faena": 6, "pollos_por_dia": 30000},
    )
    assert r.status_code == 200, f"Generar proyección falló: {r.text}"
    return r.json()


# ─── Tests ───────────────────────────────────────────────────────────────────────

def test_ajuste_martes(client, auth_headers):
    """Flujo completo: generar proyección con jueves, ajustar con martes."""
    # 1. Generar proyección base
    proy = _generar_proyeccion(client, auth_headers)
    assert proy["total_pollos_semana"] > 0

    # 2. Obtener lotes asignados para construir oferta martes
    all_lotes = []
    for dia in proy.get("dias", []):
        for l in dia.get("lotes", []):
            all_lotes.append(l)
    assert len(all_lotes) > 0

    # 3. Construir oferta martes con datos ligeramente distintos
    martes_data = []
    for lote in all_lotes:
        martes_data.append({
            "fecha_peso": date.fromisoformat(lote["fecha_peso_original"]),
            "granja": lote["granja"],
            "galpon": lote["galpon"],
            "nucleo": lote["nucleo"],
            "cantidad": lote["cantidad"],
            "sexo": lote["sexo"],
            "edad_proyectada": lote["edad_actual"] + 2,
            "peso_muestreo_proy": round(lote["peso_actual"] + 0.05, 3),
            "ganancia_diaria": lote.get("ganancia_diaria_original", 0.09),
            "dias_proyectados": 0,
            "edad_real": lote["edad_actual"] + 2,
            "peso_muestreo_real": round(lote["peso_actual"] + 0.05, 3),
            "fecha_ingreso": date.fromisoformat(lote["fecha_ingreso_original"]),
        })

    excel_martes = _crear_excel_oferta(martes_data)

    # 4. Llamar al endpoint de ajuste
    r = client.post(
        "/oferta/ajuste-martes",
        headers=auth_headers,
        files={"file": ("martes.xlsx", excel_martes, "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")},
    )
    assert r.status_code == 200, f"Ajuste martes falló: {r.text}"
    data = r.json()

    # 5. Verificar resumen
    resumen = data["resumen_ajuste"]
    assert resumen["lotes_actualizados"] > 0
    assert resumen["lotes_nuevos"] == 0
    assert resumen["lotes_faltantes"] == 0

    # 6. Verificar que la proyección se persistió
    r2 = client.get("/proyeccion", headers=auth_headers)
    assert r2.status_code == 200
    proy2 = r2.json()
    assert proy2["total_pollos_semana"] == data["proyeccion"]["total_pollos_semana"]


def test_ajuste_sin_proyeccion(client, auth_headers):
    """El endpoint debe rechazar si no hay proyección existente."""
    martes_data = [LOTE_BASE]
    excel = _crear_excel_oferta(martes_data)

    r = client.post(
        "/oferta/ajuste-martes",
        headers=auth_headers,
        files={"file": ("test.xlsx", excel, "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")},
    )
    assert r.status_code == 400
    assert "No hay proyección" in r.json()["detail"]


def test_ajuste_archivo_invalido(client, auth_headers):
    """El endpoint debe rechazar archivos que no sean Excel."""
    r = client.post(
        "/oferta/ajuste-martes",
        headers=auth_headers,
        files={"file": ("test.txt", b"not an excel file", "text/plain")},
    )
    assert r.status_code == 400
