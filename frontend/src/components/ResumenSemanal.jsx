import { useState, useEffect } from 'react'
import { motion } from 'framer-motion'
import { TrendingUp, Calendar, Home, Download, PieChart, Factory, ShoppingCart } from 'lucide-react'
import toast from 'react-hot-toast'
import { exportResumenPDF } from '../utils/pdfExport'
import { getReferenciaProduccion, cargarDeficit } from '../services/api'

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

  useEffect(() => {
    if (!proyeccion?.fecha_inicio) { setRefProduccion(null); return }
    getReferenciaProduccion(proyeccion.fecha_inicio)
      .then(data => setRefProduccion(data))
      .catch(() => setRefProduccion(null))
  }, [proyeccion?.fecha_inicio])

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
            <TrendingUp size={20} /> No hay proyección generada aún.
          </p>
        </div>
      </motion.div>
    )
  }

  const { dias } = proyeccion

  // Calcular datos por granja
  const porGranja = {}
  dias.forEach((dia, diaIdx) => {
    dia.lotes.forEach(lote => {
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

      {/* Tabla resumen diario */}
      <motion.div variants={itemVariants} className="card">
        <div className="card-header">
          <h2><Calendar size={18} style={{ verticalAlign: 'middle', marginRight: 6 }} /> Resumen Diario</h2>
          <button className="btn btn-sm btn-outline" onClick={() => exportResumenPDF(proyeccion)}>
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
                    <strong>{dias.reduce((sum, d) => sum + d.lotes.filter(l => l.cantidad > 0).length, 0)}</strong>
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
        const lotesAsignados = dias.reduce((sum, d) => sum + d.lotes.filter(l => l.cantidad > 0).length, 0)
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
                      <td style={{ color: 'var(--success)' }}><strong>Asignados a proyección</strong></td>
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
          dia.lotes.forEach(lote => {
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
              Dato macro de carga en granja (semana {refProduccion.semana_produccion.fecha_desde} — {refProduccion.semana_produccion.fecha_hasta}).
              La oferta es el dato preciso; este es contexto para validar que no falten lotes.
            </p>
            <div className="stats-grid">
              <div className="stat-card">
                <div className="stat-label">Cargados en granja</div>
                <div className="stat-value">{formatNumber(refProduccion.semana_produccion.pollitos_cargados)}</div>
              </div>
              <div className="stat-card">
                <div className="stat-label">Disponible est. (6.5% mort.)</div>
                <div className="stat-value blue">
                  {formatNumber(
                    refProduccion.semana_produccion.simulaciones.find(
                      s => Math.abs(s.tasa_mortalidad - 0.065) < 0.001
                    )?.pollitos_disponibles
                  )}
                </div>
              </div>
              <div className="stat-card">
                <div className="stat-label">Oferta actual proyectada</div>
                <div className="stat-value green">{formatNumber(refProduccion.total_oferta_actual)}</div>
              </div>
              <div className="stat-card">
                <div className="stat-label">Cobertura oferta/disponible</div>
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
          </div>
        </motion.div>
      )}
    </motion.div>
  )
}
