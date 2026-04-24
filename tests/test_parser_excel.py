from datetime import date
from pathlib import Path

from backend.calculo import normalizar_granja_clave
from backend.parser_excel import leer_oferta_excel


def test_parser_excel_captura_fecha_global_oferta():
    fixture = Path(__file__).resolve().parent / "fixtures" / "oferta_fecha_global.xls"
    contenido = fixture.read_bytes()

    ofertas, _, _ = leer_oferta_excel(contenido)

    lote = next(
        oferta
        for oferta in ofertas
        if (normalizar_granja_clave(oferta.granja), oferta.galpon, oferta.nucleo, oferta.sexo)
        == ("MANANTIALES", 2, 2, "H")
    )

    assert lote.fecha_oferta == date(2026, 4, 16)