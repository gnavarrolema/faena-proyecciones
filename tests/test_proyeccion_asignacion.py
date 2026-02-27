from datetime import date

from backend.calculo import (
    LoteOferta, Parametros, SemanaFaena,
    generar_proyeccion, aplicar_ajuste_martes,
    calcular_lote_proyectado,
    calcular_edad_fin_retiro_v2,
)


def _lote(cantidad: int, galpon: int, edad_proyectada: int = 40, peso: float = 2.95,
           ganancia: float = 0.0, granja: str = "TEST", sexo: str = "M",
           fecha_ingreso: date | None = None) -> LoteOferta:
    return LoteOferta(
        fecha_peso=date(2026, 2, 23),
        granja=granja,
        galpon=galpon,
        nucleo=1,
        cantidad=cantidad,
        sexo=sexo,
        edad_proyectada=edad_proyectada,
        peso_muestreo_proy=peso,
        ganancia_diaria=ganancia,
        dias_proyectados=0,
        edad_real=edad_proyectada,
        peso_muestreo_real=peso,
        fecha_ingreso=fecha_ingreso or date(2026, 1, 10),
    )


def test_respeta_tope_diario_maximo_y_reporta_no_asignados():
    ofertas = [
        _lote(23000, 1),
        _lote(23000, 2),
        _lote(36000, 3),
    ]

    params = Parametros(
        pollos_diarios_objetivo_min=25000,
        pollos_diarios_objetivo_max=35000,
        edad_min_faena=38,
        edad_max_faena=43,
        peso_min_faena=2.8,
        peso_max_faena=3.2,
    )

    semana = generar_proyeccion(
        ofertas=ofertas,
        fecha_inicio_semana=date(2026, 2, 23),
        dias_faena=6,
        pollos_por_dia=30000,
        params=params,
    )

    assert all(d.total_pollos <= params.pollos_diarios_objetivo_max for d in semana.dias)
    assert len(semana.lotes_no_asignados) == 1
    assert semana.lotes_no_asignados[0].cantidad == 36000
    assert "tope diario máximo" in semana.lotes_no_asignados[0].motivo


def test_descuento_sofia_no_afecta_asignacion_diaria():
    ofertas = [
        _lote(23000, 1),
        _lote(23000, 2),
        _lote(23000, 3),
    ]

    params_a = Parametros(descuento_sofia=10000)
    params_b = Parametros(descuento_sofia=5000)

    semana_a = generar_proyeccion(
        ofertas=ofertas,
        fecha_inicio_semana=date(2026, 2, 23),
        dias_faena=6,
        pollos_por_dia=30000,
        params=params_a,
    )

    semana_b = generar_proyeccion(
        ofertas=ofertas,
        fecha_inicio_semana=date(2026, 2, 23),
        dias_faena=6,
        pollos_por_dia=30000,
        params=params_b,
    )

    assert [d.total_pollos for d in semana_a.dias] == [d.total_pollos for d in semana_b.dias]
    assert semana_a.sofia == semana_a.total_pollos_semana - 10000
    assert semana_b.sofia == semana_b.total_pollos_semana - 5000


def test_lote_proyectado_preserva_datos_originales():
    """Verifica que calcular_lote_proyectado almacena los datos originales de la oferta."""
    oferta = _lote(15000, 1, ganancia=0.085)
    params = Parametros()
    lote = calcular_lote_proyectado(oferta, date(2026, 2, 25), params)

    assert lote.fecha_peso_original == date(2026, 2, 23)
    assert lote.ganancia_diaria_original == 0.085
    assert lote.fecha_ingreso_original == date(2026, 1, 10)


def test_heavier_lots_assigned_to_earlier_days_on_equal_deficit():
    """Lotes más pesados deben ir a días más tempranos cuando los déficits son iguales."""
    ofertas = [
        _lote(10000, 1, peso=3.15),  # pesado
        _lote(10000, 2, peso=2.85),  # liviano
    ]
    params = Parametros(
        pollos_diarios_objetivo_min=25000,
        pollos_diarios_objetivo_max=35000,
        edad_min_faena=38,
        edad_max_faena=43,
        peso_min_faena=2.8,
        peso_max_faena=3.2,
    )
    semana = generar_proyeccion(
        ofertas=ofertas,
        fecha_inicio_semana=date(2026, 2, 23),
        dias_faena=6,
        pollos_por_dia=30000,
        params=params,
    )
    # El lote más pesado (galpon 1) debería estar en un día anterior al más liviano
    dia_pesado = None
    dia_liviano = None
    for d_idx, dia in enumerate(semana.dias):
        for lote in dia.lotes:
            if lote.galpon == 1:
                dia_pesado = d_idx
            elif lote.galpon == 2:
                dia_liviano = d_idx
    if dia_pesado is not None and dia_liviano is not None:
        assert dia_pesado <= dia_liviano, (
            f"Lote pesado en día {dia_pesado}, lote liviano en día {dia_liviano}"
        )


def test_ajuste_martes_detecta_fuera_de_rango_post_ajuste():
    """El ajuste del martes debe alertar si un lote queda fuera de rango tras actualización."""
    params = Parametros(
        pollos_diarios_objetivo_min=25000,
        pollos_diarios_objetivo_max=35000,
        edad_min_faena=38,
        edad_max_faena=43,
        peso_min_faena=2.80,
        peso_max_faena=3.20,
    )

    # Generar proyección con oferta del jueves
    ofertas_jueves = [_lote(15000, 1, peso=2.95)]
    semana = generar_proyeccion(
        ofertas=ofertas_jueves,
        fecha_inicio_semana=date(2026, 2, 23),
        dias_faena=6,
        pollos_por_dia=30000,
        params=params,
    )

    # Oferta del martes: el lote ahora tiene peso mucho menor (fuera de rango)
    ofertas_martes = [_lote(15000, 1, peso=2.30)]
    resultado, resumen = aplicar_ajuste_martes(ofertas_martes, semana, params)

    # Debe detectar que el lote está fuera de rango tras el ajuste
    assert resumen.lotes_fuera_rango_post_ajuste > 0
    assert len(resumen.detalle_fuera_rango_post_ajuste) > 0
    assert "Peso" in resumen.detalle_fuera_rango_post_ajuste[0]["alerta"]


def test_ajuste_martes_matchea_por_sexo():
    """
    El ajuste debe usar (granja, galpon, nucleo, sexo) como clave.
    Lotes del mismo galpón pero distinto sexo deben matchear correctamente,
    cada uno con su par del martes.
    """
    params = Parametros(
        pollos_diarios_objetivo_min=25000,
        pollos_diarios_objetivo_max=60000,
        edad_min_faena=38,
        edad_max_faena=45,
        peso_min_faena=2.50,
        peso_max_faena=3.50,
    )

    # Oferta jueves: dos lotes del mismo galpón (M y H)
    oferta_m = _lote(11000, 3, edad_proyectada=40, peso=2.95, sexo="M")
    oferta_h = LoteOferta(
        fecha_peso=date(2026, 2, 23),
        granja="TEST",
        galpon=3,
        nucleo=1,
        cantidad=12000,
        sexo="H",
        edad_proyectada=40,
        peso_muestreo_proy=2.85,
        ganancia_diaria=0.079,
        dias_proyectados=0,
        edad_real=40,
        peso_muestreo_real=2.85,
        fecha_ingreso=date(2026, 1, 10),
    )

    semana = generar_proyeccion(
        ofertas=[oferta_m, oferta_h],
        fecha_inicio_semana=date(2026, 2, 23),
        dias_faena=6,
        pollos_por_dia=30000,
        params=params,
    )

    # Oferta martes: mismo galpón, M sube de peso, H baja
    martes_m = _lote(11000, 3, edad_proyectada=42, peso=3.10, sexo="M")
    martes_h = LoteOferta(
        fecha_peso=date(2026, 2, 25),
        granja="TEST",
        galpon=3,
        nucleo=1,
        cantidad=12000,
        sexo="H",
        edad_proyectada=42,
        peso_muestreo_proy=2.75,
        ganancia_diaria=0.079,
        dias_proyectados=0,
        edad_real=42,
        peso_muestreo_real=2.75,
        fecha_ingreso=date(2026, 1, 10),
    )

    resultado, resumen = aplicar_ajuste_martes([martes_m, martes_h], semana, params)

    # Ambos deben haber sido actualizados (no tratados como nuevos o faltantes)
    assert resumen.lotes_nuevos == 0, f"No debería haber lotes nuevos, hay {resumen.lotes_nuevos}"
    assert resumen.lotes_faltantes == 0, f"No debería haber faltantes, hay {resumen.lotes_faltantes}"
    assert resumen.lotes_actualizados == 2, f"Deberían actualizarse 2 lotes, se actualizaron {resumen.lotes_actualizados}"

    # Verificar que cada lote tiene el sexo correcto tras el ajuste
    for dia in resultado.dias:
        for lote in dia.lotes:
            if lote.sexo == "M":
                # El macho debería tener datos del martes_m (peso subió)
                assert lote.peso_actual == 3.10, f"Macho debería tener peso 3.10, tiene {lote.peso_actual}"
            elif lote.sexo == "H":
                # La hembra debería tener datos del martes_h (peso bajó)
                assert lote.peso_actual == 2.75, f"Hembra debería tener peso 2.75, tiene {lote.peso_actual}"


def test_ajuste_martes_duplicados_mismo_sexo():
    """
    Cuando hay dos lotes con la misma (granja, galpon, nucleo, sexo) pero distinta
    fecha_ingreso, el ajuste debe matchear cada uno con su par correcto del martes
    usando la clave 5-tupla (granja, galpon, nucleo, sexo, fecha_ingreso).
    """
    params = Parametros(
        pollos_diarios_objetivo_min=25000,
        pollos_diarios_objetivo_max=60000,
        edad_min_faena=38,
        edad_max_faena=45,
        peso_min_faena=2.50,
        peso_max_faena=3.50,
    )

    # Dos lotes M del mismo galpón con distinta fecha_ingreso (distintas camadas)
    lote_a = _lote(12000, 3, edad_proyectada=40, peso=2.95, fecha_ingreso=date(2026, 1, 10))
    lote_b = _lote(10000, 3, edad_proyectada=38, peso=2.80, fecha_ingreso=date(2026, 1, 11))

    semana = generar_proyeccion(
        ofertas=[lote_a, lote_b],
        fecha_inicio_semana=date(2026, 2, 23),
        dias_faena=6,
        pollos_por_dia=30000,
        params=params,
    )

    # Martes: mismas dos camadas (misma fecha_ingreso), cantidades actualizadas
    martes_a = _lote(11500, 3, edad_proyectada=42, peso=3.05, fecha_ingreso=date(2026, 1, 10))
    martes_b = _lote(9800, 3, edad_proyectada=40, peso=2.90, fecha_ingreso=date(2026, 1, 11))

    resultado, resumen = aplicar_ajuste_martes([martes_a, martes_b], semana, params)

    assert resumen.lotes_nuevos == 0, f"No debería haber lotes nuevos, hay {resumen.lotes_nuevos}"
    assert resumen.lotes_faltantes == 0, f"No debería haber faltantes, hay {resumen.lotes_faltantes}"
    # Ambos deben haber sido actualizados
    assert resumen.lotes_actualizados == 2, f"Deberían actualizarse 2 lotes, se actualizaron {resumen.lotes_actualizados}"

    # Verificar que cada lote conservó su par correcto por fecha_ingreso
    for dia in resultado.dias:
        for lote in dia.lotes:
            if lote.fecha_ingreso_original == date(2026, 1, 10):
                assert lote.cantidad == 11500, f"Lote A debería tener 11500, tiene {lote.cantidad}"
            elif lote.fecha_ingreso_original == date(2026, 1, 11):
                assert lote.cantidad == 9800, f"Lote B debería tener 9800, tiene {lote.cantidad}"


def test_ajuste_martes_no_duplica_lote_previamente_no_asignado():
    """
    Un lote que estaba en lotes_no_asignados (no cupó por capacidad en la
    proyección original) y aparece en la oferta del martes NO debe quedar
    duplicado: si logra asignarse a un día como "nuevo", debe eliminarse
    de lotes_no_asignados.
    """
    params = Parametros(
        pollos_diarios_objetivo_min=10000,
        pollos_diarios_objetivo_max=15000,
        edad_min_faena=38,
        edad_max_faena=45,
        peso_min_faena=2.50,
        peso_max_faena=3.50,
    )

    # Oferta jueves: 2 lotes que llenan el tope (15k cada uno pero max=15k)
    # El segundo lote quedará como no_asignado
    lote_ok = _lote(14000, 1, peso=2.95)
    lote_excedente = _lote(8000, 2, peso=2.90)

    semana = generar_proyeccion(
        ofertas=[lote_ok, lote_excedente],
        fecha_inicio_semana=date(2026, 2, 23),
        dias_faena=6,
        pollos_por_dia=10000,
        params=params,
    )

    # Verificar precondición: lote_excedente podría estar en no_asignados
    # o asignado si cupó en otro día. Si cupó en un día, ajustamos el test.
    total_asignados = sum(d.total_pollos for d in semana.dias)
    no_asignados_granjas = {(l.granja, l.galpon) for l in semana.lotes_no_asignados}

    # Oferta martes: incluye el lote_excedente (misma clave) con datos actualizados
    martes_excedente = _lote(7500, 2, peso=2.95)

    resultado, resumen = aplicar_ajuste_martes([martes_excedente], semana, params)

    # Contar cuántas veces aparece el lote (galpon=2) en días + no_asignados
    apariciones_en_dias = 0
    for dia in resultado.dias:
        for lote in dia.lotes:
            if lote.galpon == 2 and lote.granja == "TEST":
                apariciones_en_dias += 1

    apariciones_no_asignados = 0
    for lna in resultado.lotes_no_asignados:
        if lna.galpon == 2 and lna.granja == "TEST":
            apariciones_no_asignados += 1

    # El lote NO debe estar duplicado (en días Y en no_asignados a la vez)
    total_apariciones = apariciones_en_dias + apariciones_no_asignados
    assert total_apariciones <= 1, (
        f"Lote G2 aparece {apariciones_en_dias} veces en días y "
        f"{apariciones_no_asignados} en no_asignados (duplicado!)"
    )


# ─── Tests P0: calcular_edad_fin_retiro_v2 con dias_proyectados ──────────────

def test_edad_fin_retiro_con_dias_proyectados():
    """
    La edad_fin debe descontar los dias_proyectados de la fecha_peso.
    Ejemplo real del Excel: fecha_peso=2026-02-11, dias_proy=1, edad_proy=36,
    fecha_retiro=2026-02-18, fecha_base_oferta=2026-02-12.
    Excel: (18-12)+36 = 42.  Sin fix: (18-11)+36 = 43.
    """
    edad = calcular_edad_fin_retiro_v2(
        fecha_fin_retiro=date(2026, 2, 18),
        fecha_peso=date(2026, 2, 11),
        edad_proyectada=36,
        dias_proyectados=1,
    )
    assert edad == 42, f"Esperado 42, obtenido {edad}"


def test_edad_fin_retiro_con_muchos_dias_proyectados():
    """
    Caso extremo: fecha_peso=2026-02-06, dias_proy=6, edad_proy=34.
    fecha_base_oferta = 2026-02-12.
    Excel: (18-12)+34 = 40.  Sin fix: (18-6)+34 = 46 (error de 6 dias).
    """
    edad = calcular_edad_fin_retiro_v2(
        fecha_fin_retiro=date(2026, 2, 18),
        fecha_peso=date(2026, 2, 6),
        edad_proyectada=34,
        dias_proyectados=6,
    )
    assert edad == 40, f"Esperado 40, obtenido {edad}"


def test_edad_fin_retiro_sin_dias_proyectados():
    """Cuando dias_proyectados=0 el resultado no cambia (backward-compatible)."""
    edad = calcular_edad_fin_retiro_v2(
        fecha_fin_retiro=date(2026, 2, 18),
        fecha_peso=date(2026, 2, 12),
        edad_proyectada=36,
        dias_proyectados=0,
    )
    assert edad == 42, f"Esperado 42, obtenido {edad}"


def test_lote_proyectado_usa_fecha_base_correcta():
    """
    calcular_lote_proyectado debe usar la fecha base de oferta (no fecha_peso)
    cuando el lote tiene dias_proyectados > 0.
    """
    oferta = LoteOferta(
        fecha_peso=date(2026, 2, 11),
        granja="TEST",
        galpon=1,
        nucleo=1,
        cantidad=15000,
        sexo="M",
        edad_proyectada=36,
        peso_muestreo_proy=2.50,
        ganancia_diaria=0.09,
        dias_proyectados=1,  # fecha_base = 2026-02-12
        edad_real=35,
        peso_muestreo_real=2.41,
        fecha_ingreso=date(2026, 1, 10),
    )
    params = Parametros()
    lote = calcular_lote_proyectado(oferta, date(2026, 2, 18), params)

    # Edad = (2026-02-18 - 2026-02-12) + 36 = 42
    assert lote.edad_fin_retiro == 42, f"Esperado 42, obtenido {lote.edad_fin_retiro}"


# ─── Test P2: cajas semanales = suma de cajas diarias ─────────────────────────

def test_cajas_semanales_es_suma_de_cajas_diarias():
    """
    Las cajas semanales deben ser la suma de cajas_totales de cada dia,
    no total_pollos / calibre_semanal_ponderado.
    """
    ofertas = [
        _lote(15000, 1, peso=2.95),
        _lote(12000, 2, peso=3.10),
    ]
    params = Parametros(
        pollos_diarios_objetivo_min=25000,
        pollos_diarios_objetivo_max=35000,
        edad_min_faena=38,
        edad_max_faena=43,
        peso_min_faena=2.8,
        peso_max_faena=3.2,
    )

    semana = generar_proyeccion(
        ofertas=ofertas,
        fecha_inicio_semana=date(2026, 2, 23),
        dias_faena=6,
        pollos_por_dia=30000,
        params=params,
    )

    suma_cajas_diarias = sum(d.cajas_totales for d in semana.dias)
    assert semana.produccion_cajas_semanales == suma_cajas_diarias, (
        f"Cajas semanales ({semana.produccion_cajas_semanales}) "
        f"deberia ser la suma de cajas diarias ({suma_cajas_diarias})"
    )
