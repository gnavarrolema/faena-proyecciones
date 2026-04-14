import { useState, useEffect } from 'react'
import { motion } from 'framer-motion'
import { TrendingUp, Calendar, Home, Download, PieChart, Factory, ShoppingCart, AlertTriangle, Clock } from 'lucide-react'
import toast from 'react-hot-toast'
import { exportResumenPDF } from '../utils/pdfExport'
import { getReferenciaProduccion, cargarDeficit, getAnalisisTerceros, getSemana2, getParametros } from '../services/api'
import { formatBBReferenceSummary, getBBReferenceConfigFromCoverage, getBBReferenceConfigFromParams, getBBReferencePresetMeta } from '../utils/bbReferencePresets'

function formatNumber(n) {
  if (n == null) return '-'
  return n.toLocaleString('es-AR')
}

const DIAS_SEMANA = ['Lunes', 'Martes', 'Miércoles', 'Jueves', 'Viernes', 'Sábado', 'Domingo']

function getDiaNombre(fechaStr) {
  if (!fechaStr) return '-'
  const dt = new Date(fechaStr + 'T12:00:00')
  const idx = dt.getDay() === 0 ? 6 : dt.getDay() - 1
  return DIAS_SEMANA[idx]
}

function formatDateShort(fechaStr) {
  if (!fechaStr) return '-'
  const dt = new Date(fechaStr + 'T12:00:00')
  return dt.toLocaleDateString('es-AR', { day: 'numeric', month: 'short' })
}

const containerVariants = {
  hidden: { opacity: 0 },
  show: {
    opacity: 1,
    transition: { staggerChildren: 0.1 }
  }
}

const itemVariants = {
  hidden: { opacity: 0, y: 20 },
  show: { opacity: 1, y: 0, transition: { duration: 0.4, ease: 'easeOut' } }
}

export default function ResumenSemanal({ proyeccion }) {
  const [refProduccion, setRefProduccion] = useState(null)
  const [deficitLoading, setDeficitLoading] = useState(false)
  const [analisisTerceros, setAnalisisTerceros] = useState(null)
  const [semana2, setSemana2] = useState(null)
  const [parametros, setParametros] = useState(null)

  useEffect(() => {
    getParametros()
      .then(data => setParametros(data))
      .catch(() => setParametros(null))
  }, [])

  useEffect(() => {
    if (!proyeccion?.fecha_inicio) { setRefProduccion(null); return }
    getReferenciaProduccion(proyeccion.fecha_inicio)
      .then(data => setRefProduccion(data))
      .catch(() => setRefProduccion(null))
  }, [proyeccion?.fecha_inicio])

  useEffect(() => {
    if (!proyeccion?.dias?.length) { setAnalisisTerceros(null); return }
    getAnalisisTerceros()
      .then(data => setAnalisisTerceros(data))
      .catch(() => setAnalisisTerceros(null))
  }, [proyeccion?.total_pollos_semana])

  useEffect(() => {
    if (!proyeccion?.dias?.length) { setSemana2(null); return }
    getSemana2()
      .then(data => {
        if (data.tiene_datos && data.proyeccion) setSemana2(data)
        else setSemana2(null)
      })
      .catch(() => setSemana2(null))
  }, [proyeccion?.total_pollos_semana])

  const coberturasRef = refProduccion?.coberturas || []
  const bbReferenceConfig = getBBReferenceConfigFromParams(parametros) || getBBReferenceConfigFromCoverage(refProduccion)
  const bbReferencePreset = getBBReferencePresetMeta(bbReferenceConfig)
  const bbReferenceResumen = formatBBReferenceSummary(bbReferenceConfig)
  const totalSemanasRef = refProduccion?.semana_produccion?.total_semanas || refProduccion?.total_semanas_referenciadas || 0
  const referenciaEsConsolidada = refProduccion?.metodo_cruce === 'cohortes_planificadas' || totalSemanasRef > 1
  const semanasBBReferenciadas = refProduccion?.semana_produccion?.semanas_referenciadas || []
  const peorEscenarioRef = coberturasRef[coberturasRef.length - 1] || null
  const notaReferencia = referenciaEsConsolidada
    ? `Referencia consolidada de ${totalSemanasRef} semana${totalSemanasRef !== 1 ? 's' : ''} de carga según las cohortes realmente planificadas.`
    : `Referencia macro de carga en granja (semana ${refProduccion?.semana_produccion?.fecha_desde} — ${refProduccion?.semana_produccion?.fecha_hasta}).`
  const notaVentanaRef = refProduccion?.dias_hasta_faena_referencia != null
    ? `Ventana de referencia: carga + ${refProduccion.dias_hasta_faena_referencia} días (±${refProduccion.tolerancia_cruce_dias}).`
    : null
  const notaTercerosRef = refProduccion?.total_compra_terceros > 0
    ? `Compra a terceros no incluida en esta cobertura: ${formatNumber(refProduccion.total_compra_terceros)} pollos.`
    : null

  const handleCargarDeficit = async () => {
    setDeficitLoading(true)
    try {
      const result = await cargarDeficit()
      toast.success(result.mensaje)
    } catch (err) {
      toast.error('Error: ' + (err.response?.data?.detail || err.message))
    } finally {
      setDeficitLoading(false)
    }
  }

  if (!proyeccion || !proyeccion.dias) {
    return (
      <motion.div
        initial={{ opacity: 0, scale: 0.95 }}
        animate={{ opacity: 1, scale: 1 }}
        className="card"
      >
        <div className="card-body" style={{ textAlign: 'center', padding: '3rem' }}>
          <p style={{ fontSize: '1.1rem', color: 'var(--text-light)', display: 'flex', alignItems: 'center', justifyContent: 'center', gap: 6 }}>
            <TrendingUp size={20} /> No hay planificación generada aún.
          </p>
        </div>
      </motion.div>
    )
  }

  const { dias } = proyeccion

  // Calcular datos por granja
  const porGranja = {}
  dias.forEach((dia, diaIdx) => {
    dia.lotes.filter(l => !l.excluido).forEach(lote => {
      if (!porGranja[lote.granja]) {
        porGranja[lote.granja] = {
          dias: new Array(dias.length).fill(0),
          total: 0,
          cajas: 0,
        }
      }
      porGranja[lote.granja].dias[diaIdx] += lote.cantidad
      porGranja[lote.granja].total += lote.cantidad
      porGranja[lote.granja].cajas += lote.cajas
    })
  })

  return (
    <motion.div
      variants={containerVariants}
      initial="hidden"
      animate="show"
    >
      {/* Stats principales */}
      <motion.div variants={itemVariants} className="stats-grid">
        <div className="stat-card">
          <div className="stat-label">Total Pollos Semana</div>
          <div className="stat-value green">{formatNumber(proyeccion.total_pollos_semana)}</div>
        </div>
        <div className="stat-card">
          <div className="stat-label">Sofía</div>
          <div className="stat-value blue">{formatNumber(proyeccion.sofia)}</div>
        </div>
        <div className="stat-card">
          <div className="stat-label">Promedio Edad</div>
          <div className="stat-value orange">{proyeccion.promedio_edad_semana?.toFixed(1)} días</div>
        </div>
        <div className="stat-card">
          <div className="stat-label">Cajas Semanales</div>
          <div className="stat-value">{formatNumber(proyeccion.produccion_cajas_semanales)}</div>
        </div>
      </motion.div>

      <motion.div variants={itemVariants} style={{
        marginBottom: '1rem',
        padding: '0.85rem 1rem',
        borderRadius: 12,
        border: '1px solid var(--border)',
        background: 'linear-gradient(135deg, rgba(99, 102, 241, 0.07) 0%, var(--card-bg) 100%)',
        display: 'flex',
        justifyContent: 'space-between',
        alignItems: 'center',
        gap: '0.75rem',
        flexWrap: 'wrap',
      }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 8, flexWrap: 'wrap' }}>
          <span className={`badge ${bbReferencePreset.isCustom ? 'badge-warning' : 'badge-info'}`}>
            Referencia BB activa: {bbReferencePreset.label}
          </span>
          <span style={{ fontSize: '0.84rem', color: 'var(--text)' }}>{bbReferenceResumen}</span>
        </div>
        <span style={{ fontSize: '0.76rem', color: 'var(--text-light)' }}>{bbReferencePreset.description}</span>
      </motion.div>

      {/* Tabla resumen diario */}
      <motion.div variants={itemVariants} className="card">
        <div className="card-header">
          <h2><Calendar size={18} style={{ verticalAlign: 'middle', marginRight: 6 }} /> Resumen Diario</h2>
          <button className="btn btn-sm btn-outline" onClick={() => exportResumenPDF(proyeccion, refProduccion)}>
            <Download size={14} /> Descargar PDF
          </button>
        </div>
        <div className="card-body">
          <div className="table-container">
            <table>
              <thead>
                <tr>
                  <th>Día</th>
                  <th>Fecha</th>
                  <th className="text-right">Pollos</th>
                  <th className="text-right">Lotes</th>
                  <th className="text-right">Peso Prom.</th>
                  <th className="text-right">Dif. Edad Prom.</th>
                  <th className="text-right">Calibre Prom.</th>
                  <th className="text-right">Cajas</th>
                </tr>
              </thead>
              <tbody>
                {dias.map((dia, idx) => (
                  <tr key={idx} style={{
                    transition: 'background-color 0.2s',
                    background: dia.nivel_carga === 'horas_extras' ? 'rgba(239,68,68,0.06)' : dia.nivel_carga === 'alto' ? 'rgba(251,146,60,0.06)' : undefined,
                  }}>
                    <td>
                      <strong>{getDiaNombre(dia.fecha)}</strong>
                      {dia.es_sabado && <span style={{ fontSize: '0.7rem', color: '#ea580c', marginLeft: 4 }}>(Sáb)</span>}
                    </td>
                    <td>{dia.fecha}</td>
                    <td className="text-right" style={dia.nivel_carga === 'horas_extras' ? { color: '#ef4444', fontWeight: 700 } : {}}>
                      {formatNumber(dia.total_pollos)}
                      {dia.alerta_horas_extras && <span style={{ fontSize: '0.7rem', color: '#ef4444', marginLeft: 4 }}>HE</span>}
                      {dia.gallinas_habilitado && (
                        dia.gallinas_livianas_cantidad > 0 && dia.gallinas_pesadas_cantidad > 0
                          ? <>
                              <span style={{ fontSize: '0.7rem', color: '#7c3aed', marginLeft: 4 }}>+{formatNumber(dia.gallinas_livianas_cantidad)}liv</span>
                              <span style={{ fontSize: '0.7rem', color: '#be185d', marginLeft: 2 }}>+{formatNumber(dia.gallinas_pesadas_cantidad)}pes</span>
                            </>
                          : dia.gallinas_pesadas_cantidad > 0
                            ? <span style={{ fontSize: '0.7rem', color: '#be185d', marginLeft: 4 }}>+{formatNumber(dia.gallinas_pesadas_cantidad)}pes</span>
                            : <span style={{ fontSize: '0.7rem', color: '#7c3aed', marginLeft: 4 }}>+{formatNumber(dia.gallinas_cantidad)}g</span>
                      )}
                    </td>
                    <td className="text-right">{dia.lotes.filter(l => l.cantidad > 0).length}</td>
                    <td className="text-right">{dia.peso_promedio_ponderado?.toFixed(2)} kg</td>
                    <td className="text-right">{dia.diferencia_edad_promedio?.toFixed(1)}</td>
                    <td className="text-right">{dia.calibre_promedio_ponderado?.toFixed(2)}</td>
                    <td className="text-right">{formatNumber(dia.cajas_totales)}</td>
                  </tr>
                ))}
                <tr className="row-subtotal">
                  <td colSpan={2}><strong>TOTAL SEMANA</strong></td>
                  <td className="text-right"><strong>{formatNumber(proyeccion.total_pollos_semana)}</strong></td>
                  <td className="text-right">
                    <strong>{dias.reduce((sum, d) => sum + d.lotes.filter(l => l.cantidad > 0 && !l.excluido).length, 0)}</strong>
                  </td>
                  <td colSpan={2}></td>
                  <td></td>
                  <td className="text-right"><strong>{formatNumber(proyeccion.produccion_cajas_semanales)}</strong></td>
                </tr>
              </tbody>
            </table>
          </div>
        </div>
      </motion.div>

      {/* Tabla resumen por granja */}
      <motion.div variants={itemVariants} className="card">
        <div className="card-header">
          <h2><Home size={18} style={{ verticalAlign: 'middle', marginRight: 6 }} /> Distribución por Granja</h2>
        </div>
        <div className="card-body">
          <div className="table-container">
            <table>
              <thead>
                <tr>
                  <th>Granja</th>
                  {dias.map((_, idx) => (
                    <th key={idx} className="text-right">{getDiaNombre(dias[idx]?.fecha)}</th>
                  ))}
                  <th className="text-right">Total</th>
                  <th className="text-right">Cajas</th>
                </tr>
              </thead>
              <tbody>
                {Object.entries(porGranja)
                  .sort((a, b) => b[1].total - a[1].total)
                  .map(([granja, info]) => (
                    <tr key={granja} style={{ transition: 'background-color 0.2s' }}>
                      <td><strong>{granja}</strong></td>
                      {info.dias.map((cant, idx) => (
                        <td key={idx} className="text-right">
                          {cant > 0 ? formatNumber(cant) : '-'}
                        </td>
                      ))}
                      <td className="text-right"><strong>{formatNumber(info.total)}</strong></td>
                      <td className="text-right">{formatNumber(Math.round(info.cajas))}</td>
                    </tr>
                  ))}
                <tr className="row-subtotal">
                  <td><strong>TOTAL</strong></td>
                  {dias.map((dia, idx) => (
                    <td key={idx} className="text-right"><strong>{formatNumber(dia.total_pollos)}</strong></td>
                  ))}
                  <td className="text-right"><strong>{formatNumber(proyeccion.total_pollos_semana)}</strong></td>
                  <td className="text-right"><strong>{formatNumber(proyeccion.produccion_cajas_semanales)}</strong></td>
                </tr>
              </tbody>
            </table>
          </div>
        </div>
      </motion.div>

      {/* Cobertura de la Oferta */}
      {(() => {
        const pollosAsignados = proyeccion.total_pollos_semana || 0
        const pollosFueraRango = proyeccion.total_pollos_fuera_rango || 0
        const pollosNoAsignados = proyeccion.total_pollos_no_asignados || 0
        const totalOfertados = pollosAsignados + pollosFueraRango + pollosNoAsignados
        if (pollosFueraRango === 0 && pollosNoAsignados === 0) return null

        const lotesFR = proyeccion.lotes_fuera_rango || []
        const lotesNA = proyeccion.lotes_no_asignados || []
        const lotesAsignados = dias.reduce((sum, d) => sum + d.lotes.filter(l => l.cantidad > 0 && !l.excluido).length, 0)
        const pctAsignados = totalOfertados > 0 ? ((pollosAsignados / totalOfertados) * 100).toFixed(1) : '0.0'

        return (
          <motion.div variants={itemVariants} className="card">
            <div className="card-header">
              <h2><PieChart size={18} style={{ verticalAlign: 'middle', marginRight: 6 }} /> Cobertura de la Oferta</h2>
            </div>
            <div className="card-body">
              <div className="stats-grid" style={{ marginBottom: '1rem' }}>
                <div className="stat-card">
                  <div className="stat-label">Total Ofertados</div>
                  <div className="stat-value">{formatNumber(totalOfertados)}</div>
                </div>
                <div className="stat-card">
                  <div className="stat-label">Asignados ({pctAsignados}%)</div>
                  <div className="stat-value green">{formatNumber(pollosAsignados)}</div>
                </div>
                <div className="stat-card">
                  <div className="stat-label">Fuera de Rango</div>
                  <div className="stat-value" style={{ color: 'var(--danger, #ef4444)' }}>{formatNumber(pollosFueraRango)}</div>
                </div>
                <div className="stat-card">
                  <div className="stat-label">Exceso Capacidad</div>
                  <div className="stat-value orange">{formatNumber(pollosNoAsignados)}</div>
                </div>
              </div>

              <div className="table-container">
                <table>
                  <thead>
                    <tr>
                      <th>Categoría</th>
                      <th className="text-right">Lotes</th>
                      <th className="text-right">Pollos</th>
                    </tr>
                  </thead>
                  <tbody>
                    <tr>
                      <td style={{ color: 'var(--success)' }}><strong>Asignados a planificación</strong></td>
                      <td className="text-right">{lotesAsignados}</td>
                      <td className="text-right">{formatNumber(pollosAsignados)}</td>
                    </tr>
                    {pollosFueraRango > 0 && (
                      <tr>
                        <td style={{ color: 'var(--danger, #ef4444)' }}><strong>Fuera de rango (edad/peso)</strong></td>
                        <td className="text-right">{lotesFR.length}</td>
                        <td className="text-right">{formatNumber(pollosFueraRango)}</td>
                      </tr>
                    )}
                    {pollosNoAsignados > 0 && (
                      <tr>
                        <td style={{ color: 'var(--warning)' }}><strong>Exceso de capacidad diaria</strong></td>
                        <td className="text-right">{lotesNA.length}</td>
                        <td className="text-right">{formatNumber(pollosNoAsignados)}</td>
                      </tr>
                    )}
                    <tr className="row-subtotal">
                      <td><strong>TOTAL OFERTADOS</strong></td>
                      <td className="text-right"><strong>{lotesAsignados + lotesFR.length + lotesNA.length}</strong></td>
                      <td className="text-right"><strong>{formatNumber(totalOfertados)}</strong></td>
                    </tr>
                  </tbody>
                </table>
              </div>
              {pollosNoAsignados > 0 && (
                <div style={{ marginTop: '1rem', display: 'flex', justifyContent: 'flex-end' }}>
                  <button
                    className="btn btn-sm btn-outline"
                    onClick={handleCargarDeficit}
                    disabled={deficitLoading}
                    style={{ borderColor: '#f97316', color: '#f97316' }}
                  >
                    {deficitLoading
                      ? 'Guardando...'
                      : `Trasladar ${lotesNA.length} lote${lotesNA.length !== 1 ? 's' : ''} a semana siguiente`}
                  </button>
                </div>
              )}
            </div>
          </motion.div>
        )
      })()}

      {/* Compra a Terceros */}
      {(() => {
        const lotesTerceros = []
        dias.forEach((dia) => {
          dia.lotes.filter(l => !l.excluido).forEach(lote => {
            if (lote.es_compra_terceros) {
              lotesTerceros.push({ ...lote, fecha: dia.fecha })
            }
          })
        })
        if (lotesTerceros.length === 0) return null

        const totalPollosTerceros = lotesTerceros.reduce((sum, l) => sum + l.cantidad, 0)
        const totalCajasTerceros = lotesTerceros.reduce((s, l) => s + l.cajas, 0)
        const pesoPromTerceros = totalPollosTerceros > 0
          ? (lotesTerceros.reduce((s, l) => s + l.peso_vivo_retiro * l.cantidad, 0) / totalPollosTerceros)
          : 0
        const pctTerceros = proyeccion.total_pollos_semana > 0
          ? ((totalPollosTerceros / proyeccion.total_pollos_semana) * 100).toFixed(1)
          : '0.0'

        return (
          <motion.div variants={itemVariants} className="card" style={{ borderLeft: '4px solid #7c3aed' }}>
            <div className="card-header">
              <h2><ShoppingCart size={18} style={{ verticalAlign: 'middle', marginRight: 6 }} /> Compra a Terceros</h2>
            </div>
            <div className="card-body">
              <div className="stats-grid" style={{ marginBottom: '1rem' }}>
                <div className="stat-card">
                  <div className="stat-label">Total Pollos Terceros</div>
                  <div className="stat-value" style={{ color: '#7c3aed' }}>{formatNumber(totalPollosTerceros)}</div>
                </div>
                <div className="stat-card">
                  <div className="stat-label">% del Total Semanal</div>
                  <div className="stat-value" style={{ color: '#7c3aed' }}>{pctTerceros}%</div>
                </div>
                <div className="stat-card">
                  <div className="stat-label">Peso Prom. Ponderado</div>
                  <div className="stat-value" style={{ color: '#7c3aed' }}>{pesoPromTerceros.toFixed(2)} kg</div>
                </div>
                <div className="stat-card">
                  <div className="stat-label">Cajas Terceros</div>
                  <div className="stat-value" style={{ color: '#7c3aed' }}>{formatNumber(totalCajasTerceros)}</div>
                </div>
              </div>

              <div className="table-container">
                <table>
                  <thead>
                    <tr>
                      <th>Día</th>
                      <th>Proveedor</th>
                      <th className="text-right">Cantidad</th>
                      <th className="text-right">Peso Vivo</th>
                      <th className="text-right">Edad</th>
                      <th className="text-right">Cajas</th>
                      <th>Motivo</th>
                    </tr>
                  </thead>
                  <tbody>
                    {lotesTerceros.map((lote, idx) => (
                      <tr key={idx} style={{ background: 'rgba(168,85,247,0.03)' }}>
                        <td><strong>{getDiaNombre(lote.fecha)}</strong></td>
                        <td>{lote.granja}</td>
                        <td className="text-right">{formatNumber(lote.cantidad)}</td>
                        <td className="text-right">{lote.peso_vivo_retiro?.toFixed(2)} kg</td>
                        <td className="text-right">{lote.edad_fin_retiro}</td>
                        <td className="text-right">{formatNumber(lote.cajas)}</td>
                        <td style={{ color: '#7c3aed', fontSize: '0.85rem', fontStyle: 'italic' }}>{lote.motivo_compra || '-'}</td>
                      </tr>
                    ))}
                    <tr className="row-subtotal">
                      <td colSpan={2}><strong>TOTAL TERCEROS</strong></td>
                      <td className="text-right"><strong>{formatNumber(totalPollosTerceros)}</strong></td>
                      <td className="text-right"><strong>{pesoPromTerceros.toFixed(2)} kg</strong></td>
                      <td></td>
                      <td className="text-right"><strong>{formatNumber(totalCajasTerceros)}</strong></td>
                      <td></td>
                    </tr>
                  </tbody>
                </table>
              </div>
            </div>
          </motion.div>
        )
      })()}

      {/* Referencia de Cargas en Granja */}
      {refProduccion?.encontrada && (
        <motion.div variants={itemVariants} className="card" style={{ borderLeft: '4px solid #6366f1' }}>
          <div className="card-header">
            <h2><Factory size={18} style={{ verticalAlign: 'middle', marginRight: 6 }} /> Referencia de Cargas en Granja</h2>
          </div>
          <div className="card-body">
            <p style={{ marginBottom: '1rem', fontSize: '0.8rem', color: 'var(--text-light)' }}>
              {[notaReferencia, notaVentanaRef].filter(Boolean).join(' ')} El plan propio es el dato comparado; este bloque sirve para validar disponibilidad viva de la planificación.
            </p>
            <div className="stats-grid">
              <div className="stat-card">
                <div className="stat-label">Cargados referenciados</div>
                <div className="stat-value">{formatNumber(refProduccion.semana_produccion.pollitos_cargados)}</div>
              </div>
              <div className="stat-card">
                <div className="stat-label">Disponible est. ({peorEscenarioRef?.tasa ?? '-'}% mort.)</div>
                <div className="stat-value blue">
                  {formatNumber(peorEscenarioRef?.disponibles)}
                </div>
              </div>
              <div className="stat-card">
                <div className="stat-label">Plan propio actual</div>
                <div className="stat-value green">{formatNumber(refProduccion.total_oferta_actual)}</div>
              </div>
              <div className="stat-card">
                <div className="stat-label">Cobertura plan/disponible</div>
                <div className="stat-value" style={{
                  color: refProduccion.cobertura_pct == null
                    ? 'var(--text-light)'
                    : refProduccion.cobertura_pct > 105
                    ? '#ef4444'
                    : refProduccion.cobertura_pct >= 80
                    ? '#22c55e'
                    : '#f97316'
                }}>
                  {refProduccion.cobertura_pct != null ? `${refProduccion.cobertura_pct}%` : '-'}
                </div>
              </div>
            </div>
            {notaTercerosRef && (
              <p style={{ marginTop: '0.75rem', marginBottom: 0, fontSize: '0.75rem', color: 'var(--text-light)' }}>
                {notaTercerosRef}
              </p>
            )}

            {semanasBBReferenciadas.length > 0 && (
              <div style={{ marginTop: '1rem' }}>
                <h3 style={{ fontSize: '0.9rem', marginBottom: '0.6rem', color: 'var(--text)' }}>
                  Semanas BB que alimentan este plan
                </h3>
                <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(220px, 1fr))', gap: '0.75rem' }}>
                  {semanasBBReferenciadas.map((sem) => (
                    <div key={sem.fecha_desde} style={{
                      border: '1px solid var(--border)',
                      borderRadius: 10,
                      padding: '0.85rem 0.9rem',
                      background: 'rgba(99, 102, 241, 0.04)',
                    }}>
                      <div style={{ fontSize: '0.82rem', fontWeight: 600, color: 'var(--text)', marginBottom: 4 }}>
                        BB {formatDateShort(sem.fecha_desde)} - {formatDateShort(sem.fecha_hasta)}
                      </div>
                      <div style={{ fontSize: '0.78rem', color: 'var(--text-light)' }}>
                        {formatNumber(sem.pollitos_cargados)} pollitos cargados
                      </div>
                      <div style={{ fontSize: '0.78rem', color: 'var(--text-light)', marginTop: 2 }}>
                        Faena estimada: {formatDateShort(sem.fecha_faena_estimada)}
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            )}

            {/* Tabla multi-escenario de mortalidad */}
            {refProduccion.coberturas && refProduccion.coberturas.length > 0 && (
              <div style={{ marginTop: '1.2rem' }}>
                <h3 style={{ fontSize: '0.9rem', marginBottom: '0.6rem', color: 'var(--text)' }}>
                  Cobertura por escenario de mortalidad
                </h3>
                <div className="table-container">
                  <table>
                    <thead>
                      <tr>
                        <th>Mortalidad</th>
                        <th className="text-right">Disponibles</th>
                        <th className="text-right">Plan</th>
                        <th className="text-right">Cobertura</th>
                        <th className="text-right">Diferencia</th>
                      </tr>
                    </thead>
                    <tbody>
                      {refProduccion.coberturas.map((c, idx) => {
                        const espeor = idx === refProduccion.coberturas.length - 1
                        const esmejor = idx === 0
                        const dif = refProduccion.total_oferta_actual - c.disponibles
                        const cobColor = c.cobertura_pct == null
                          ? 'var(--text-light)'
                          : c.cobertura_pct > 105
                          ? '#ef4444'
                          : c.cobertura_pct >= 80
                          ? '#22c55e'
                          : '#f97316'
                        return (
                          <tr key={c.tasa} style={{
                            background: espeor ? 'rgba(239,68,68,0.04)' : esmejor ? 'rgba(34,197,94,0.04)' : undefined,
                            fontWeight: (espeor || esmejor) ? 600 : 400,
                          }}>
                            <td>
                              {c.tasa}%
                              {esmejor && <span style={{ fontSize: '0.7rem', marginLeft: 4, color: '#22c55e' }}>(mejor)</span>}
                              {espeor && <span style={{ fontSize: '0.7rem', marginLeft: 4, color: '#ef4444' }}>(peor)</span>}
                            </td>
                            <td className="text-right">{formatNumber(c.disponibles)}</td>
                            <td className="text-right">{formatNumber(refProduccion.total_oferta_actual)}</td>
                            <td className="text-right" style={{ color: cobColor }}>
                              {c.cobertura_pct != null ? `${c.cobertura_pct}%` : '-'}
                            </td>
                            <td className="text-right" style={{
                              color: dif > 0 ? '#ef4444' : '#22c55e',
                            }}>
                              {dif > 0 ? `+${formatNumber(dif)}` : formatNumber(dif)}
                            </td>
                          </tr>
                        )
                      })}
                    </tbody>
                  </table>
                </div>
                <p style={{ marginTop: '0.5rem', fontSize: '0.75rem', color: 'var(--text-light)' }}>
                  Diferencia positiva = el plan propio excede la producción disponible. Negativa = hay margen.
                </p>
              </div>
            )}

            {/* Sugerencia de compra a terceros por déficit de producción (analisisTerceros) */}
            {analisisTerceros?.deficit_produccion?.hay_deficit && (() => {
              const dp = analisisTerceros.deficit_produccion
              return (
                <div style={{
                  marginTop: '1.2rem',
                  padding: '0.85rem 1rem',
                  background: 'rgba(249, 115, 22, 0.08)',
                  border: '1px solid rgba(249, 115, 22, 0.3)',
                  borderLeft: '4px solid #f97316',
                  borderRadius: 8,
                }}>
                  <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: '0.5rem' }}>
                    <AlertTriangle size={16} color="#ea580c" />
                    <strong style={{ color: '#ea580c', fontSize: '0.9rem' }}>
                      Sugerencia de Compra a Terceros
                    </strong>
                  </div>
                  <p style={{ fontSize: '0.85rem', color: 'var(--text)', margin: 0 }}>
                    {dp.recomendacion_terceros}
                  </p>
                  <div className="stats-grid" style={{ marginTop: '0.75rem' }}>
                    <div className="stat-card">
                      <div className="stat-label">Producción propia (7.5%)</div>
                      <div className="stat-value blue">{formatNumber(dp.disponibles_peor)}</div>
                    </div>
                    <div className="stat-card">
                      <div className="stat-label">{dp.contexto === 'plan_propio' ? 'Plan propio' : 'Oferta total'}</div>
                      <div className="stat-value">{formatNumber(dp.total_oferta)}</div>
                    </div>
                    <div className="stat-card">
                      <div className="stat-label">Déficit estimado</div>
                      <div className="stat-value" style={{ color: '#ef4444' }}>{formatNumber(dp.deficit_peor)}</div>
                    </div>
                    <div className="stat-card">
                      <div className="stat-label">Cobertura</div>
                      <div className="stat-value orange">{dp.cobertura_pct_peor}%</div>
                    </div>
                  </div>
                </div>
              )
            })()}
          </div>
        </motion.div>
      )}

      {/* ── Semana 2 — Planificación Tentativa ───────────────────────────── */}
      {semana2?.tiene_datos && semana2.proyeccion && (() => {
        const s2 = semana2.proyeccion
        const diasS2 = s2.dias || []
        const totalPollosS2 = s2.total_pollos_semana || diasS2.reduce((s, d) => s + d.total_pollos, 0)
        const cajasS2 = s2.produccion_cajas_semanales || diasS2.reduce((s, d) => s + (d.cajas_totales || 0), 0)
        const edadPromS2 = s2.promedio_edad_semana
        const sofiaS2 = s2.sofia

        // Datos por granja S2
        const porGranjaS2 = {}
        diasS2.forEach((dia, diaIdx) => {
          dia.lotes.forEach(lote => {
            if (!porGranjaS2[lote.granja]) {
              porGranjaS2[lote.granja] = { dias: new Array(diasS2.length).fill(0), total: 0, cajas: 0 }
            }
            porGranjaS2[lote.granja].dias[diaIdx] += lote.cantidad
            porGranjaS2[lote.granja].total += lote.cantidad
            porGranjaS2[lote.granja].cajas += lote.cajas
          })
        })

        // Totales combinados S1+S2
        const totalPollosGlobal = (proyeccion.total_pollos_semana || 0) + totalPollosS2
        const cajasGlobal = (proyeccion.produccion_cajas_semanales || 0) + cajasS2

        return (
          <>
            {/* Encabezado Semana 2 */}
            <motion.div variants={itemVariants} className="card" style={{ borderLeft: '4px solid #8b5cf6', marginTop: '1.5rem' }}>
              <div className="card-header">
                <h2><Clock size={18} style={{ verticalAlign: 'middle', marginRight: 6 }} /> Semana 2 — Planificación Tentativa</h2>
                <span style={{ fontSize: '0.75rem', padding: '2px 8px', background: '#f3e8ff', color: '#7c3aed', borderRadius: 12, fontWeight: 600 }}>TENTATIVA</span>
              </div>
              <div className="card-body">
                {/* KPIs Semana 2 */}
                <div className="stats-grid" style={{ marginBottom: '1.2rem' }}>
                  <div className="stat-card">
                    <div className="stat-label">Total Pollos S2</div>
                    <div className="stat-value" style={{ color: '#7c3aed' }}>{formatNumber(totalPollosS2)}</div>
                  </div>
                  {sofiaS2 != null && (
                    <div className="stat-card">
                      <div className="stat-label">Sofía S2</div>
                      <div className="stat-value blue">{formatNumber(sofiaS2)}</div>
                    </div>
                  )}
                  <div className="stat-card">
                    <div className="stat-label">Edad Prom. S2</div>
                    <div className="stat-value orange">{edadPromS2?.toFixed(1) || '-'} días</div>
                  </div>
                  <div className="stat-card">
                    <div className="stat-label">Cajas S2</div>
                    <div className="stat-value">{formatNumber(cajasS2)}</div>
                  </div>
                </div>

                {/* Info diferidos */}
                <p style={{ fontSize: '0.8rem', color: 'var(--text-light)', marginBottom: '1rem' }}>
                  {semana2.total_diferidos} lote{semana2.total_diferidos !== 1 ? 's' : ''} diferido{semana2.total_diferidos !== 1 ? 's' : ''}
                  {semana2.lotes_no_asignados_s1 > 0 && <> + {semana2.lotes_no_asignados_s1} no asignado{semana2.lotes_no_asignados_s1 !== 1 ? 's' : ''} de S1</>}
                  {semana2.lotes_recuperados_fuera_rango_s1 > 0 && <> + {semana2.lotes_recuperados_fuera_rango_s1} fuera de rango recuperado{semana2.lotes_recuperados_fuera_rango_s1 !== 1 ? 's' : ''} de S1</>}
                </p>

                {/* Tabla resumen diario S2 */}
                <div className="table-container">
                  <table>
                    <thead>
                      <tr>
                        <th>Día</th>
                        <th>Fecha</th>
                        <th className="text-right">Pollos</th>
                        <th className="text-right">Lotes</th>
                        <th className="text-right">Peso Prom.</th>
                        <th className="text-right">Dif. Edad Prom.</th>
                        <th className="text-right">Cajas</th>
                      </tr>
                    </thead>
                    <tbody>
                      {diasS2.map((dia, idx) => (
                        <tr key={idx} style={{ opacity: 0.92 }}>
                          <td><strong>{getDiaNombre(dia.fecha)}</strong></td>
                          <td>{dia.fecha}</td>
                          <td className="text-right">{formatNumber(dia.total_pollos)}</td>
                          <td className="text-right">{dia.lotes.filter(l => l.cantidad > 0).length}</td>
                          <td className="text-right">{dia.peso_promedio_ponderado?.toFixed(2)} kg</td>
                          <td className="text-right">{dia.diferencia_edad_promedio?.toFixed(1)}</td>
                          <td className="text-right">{formatNumber(dia.cajas_totales)}</td>
                        </tr>
                      ))}
                      <tr className="row-subtotal">
                        <td colSpan={2}><strong>TOTAL S2</strong></td>
                        <td className="text-right"><strong>{formatNumber(totalPollosS2)}</strong></td>
                        <td className="text-right"><strong>{diasS2.reduce((sum, d) => sum + d.lotes.filter(l => l.cantidad > 0).length, 0)}</strong></td>
                        <td colSpan={2}></td>
                        <td className="text-right"><strong>{formatNumber(cajasS2)}</strong></td>
                      </tr>
                    </tbody>
                  </table>
                </div>

                {/* Distribución por granja S2 */}
                {Object.keys(porGranjaS2).length > 0 && (
                  <div style={{ marginTop: '1.2rem' }}>
                    <h3 style={{ fontSize: '0.9rem', marginBottom: '0.6rem', color: 'var(--text)' }}>
                      <Home size={14} style={{ verticalAlign: 'middle', marginRight: 4 }} /> Distribución por Granja — S2
                    </h3>
                    <div className="table-container">
                      <table>
                        <thead>
                          <tr>
                            <th>Granja</th>
                            {diasS2.map((_, idx) => (
                              <th key={idx} className="text-right">{getDiaNombre(diasS2[idx]?.fecha)}</th>
                            ))}
                            <th className="text-right">Total</th>
                            <th className="text-right">Cajas</th>
                          </tr>
                        </thead>
                        <tbody>
                          {Object.entries(porGranjaS2)
                            .sort((a, b) => b[1].total - a[1].total)
                            .map(([granja, info]) => (
                              <tr key={granja}>
                                <td><strong>{granja}</strong></td>
                                {info.dias.map((cant, idx) => (
                                  <td key={idx} className="text-right">{cant > 0 ? formatNumber(cant) : '-'}</td>
                                ))}
                                <td className="text-right"><strong>{formatNumber(info.total)}</strong></td>
                                <td className="text-right">{formatNumber(Math.round(info.cajas))}</td>
                              </tr>
                            ))}
                          <tr className="row-subtotal">
                            <td><strong>TOTAL</strong></td>
                            {diasS2.map((dia, idx) => (
                              <td key={idx} className="text-right"><strong>{formatNumber(dia.total_pollos)}</strong></td>
                            ))}
                            <td className="text-right"><strong>{formatNumber(totalPollosS2)}</strong></td>
                            <td className="text-right"><strong>{formatNumber(cajasS2)}</strong></td>
                          </tr>
                        </tbody>
                      </table>
                    </div>
                  </div>
                )}
              </div>
            </motion.div>

            {/* Resumen Global S1 + S2 */}
            <motion.div variants={itemVariants} className="card" style={{ borderLeft: '4px solid #059669', marginTop: '1rem' }}>
              <div className="card-header">
                <h2><TrendingUp size={18} style={{ verticalAlign: 'middle', marginRight: 6 }} /> Resumen Global — Semana 1 + Semana 2</h2>
              </div>
              <div className="card-body">
                <div className="stats-grid">
                  <div className="stat-card">
                    <div className="stat-label">Total Pollos S1</div>
                    <div className="stat-value green">{formatNumber(proyeccion.total_pollos_semana)}</div>
                  </div>
                  <div className="stat-card">
                    <div className="stat-label">Total Pollos S2</div>
                    <div className="stat-value" style={{ color: '#7c3aed' }}>{formatNumber(totalPollosS2)}</div>
                  </div>
                  <div className="stat-card">
                    <div className="stat-label">Total Global (S1+S2)</div>
                    <div className="stat-value" style={{ color: '#059669', fontSize: '1.6rem' }}>{formatNumber(totalPollosGlobal)}</div>
                  </div>
                  <div className="stat-card">
                    <div className="stat-label">Cajas Global (S1+S2)</div>
                    <div className="stat-value" style={{ color: '#059669' }}>{formatNumber(cajasGlobal)}</div>
                  </div>
                </div>
              </div>
            </motion.div>
          </>
        )
      })()}
    </motion.div>
  )
}
