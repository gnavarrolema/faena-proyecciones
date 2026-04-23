from datetime import date
from pathlib import Path

from backend.calculo import normalizar_granja_clave
from backend.parser_excel import leer_oferta_excel


def test_parser_excel_captura_fecha_global_oferta():
    base = Path(__file__).resolve().parents[1]
    contenido = (base / "Anexos" / "OFERTA DEL 16-4-26.xls").read_bytes()

    ofertas, _, _ = leer_oferta_excel(contenido)

    lote = next(
        oferta
        for oferta in ofertas
        if (normalizar_granja_clave(oferta.granja), oferta.galpon, oferta.nucleo, oferta.sexo)
        == ("MANANTIALES", 2, 2, "H")
    )

    assert lote.fecha_oferta == date(2026, 4, 16)