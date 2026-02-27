import React, { useState } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import { BarChart, KanbanSquare, Table, ArrowLeftRight, X, Calendar, Settings2, PackageOpen, Download, RefreshCw, UploadCloud, CheckCircle2, AlertTriangle, PlusCircle, FileSpreadsheet, ChevronDown, ChevronRight, Ban } from 'lucide-react'
import toast from 'react-hot-toast'
import { eliminarLote, moverLote, uploadAjusteMartes } from '../services/api'
import { exportProyeccionPDF } from '../utils/pdfExport'

const DIAS_SEMANA = ['Lunes', 'Martes', 'Miércoles', 'Jueves', 'Viernes', 'Sábado']

function formatNumber(n) {
  if (n == null) return '-'
  return n.toLocaleString('es-AR')
}

function formatDate(d) {
  if (!d) return '-'
  const dt = new Date(d + 'T12:00:00')
  return dt.toLocaleDateString('es-AR', { weekday: 'short', day: 'numeric', month: 'short' })
}

function formatDiasElegibles(dias) {
  if (!dias || dias.length === 0) return '-'
  return dias.map((dia) => {
    const fecha = new Date(dia + 'T12:00:00')
    const idx = (fecha.getDay() + 6) % 7
    return DIAS_SEMANA[idx] || dia
  }).join(', ')
}

function getEdadColor(dif) {
  if (Math.abs(dif) <= 1) return 'green'
  if (Math.abs(dif) <= 3) return 'orange'
  return 'red'
}

const containerVariants = {
  hidden: { opacity: 0 },
  show: {
    opacity: 1,
    transition: { staggerChildren: 0.08 }
  }
}

const itemVariants = {
  hidden: { opacity: 0, scale: 0.95, y: 15 },
  show: { opacity: 1, scale: 1, y: 0, transition: { duration: 0.3 } }
}

export default function ProyeccionView({ proyeccion, setProyeccion }) {
  const [viewMode, setViewMode] = useState('cards') // 'cards' | 'table'
  const [movingLote, setMovingLote] = useState(null)
  const [loading, setLoading] = useState(false)
  const [ajusteFile, setAjusteFile] = useState(null)
  const [ajusteLoading, setAjusteLoading] = useState(false)
  const [ajusteResumen, setAjusteResumen] = useState(null)
  const [ajusteOpen, setAjusteOpen] = useState(false)
  const [expandedFR, setExpandedFR] = useState(new Set())
  const ajusteInputRef = React.useRef(null)

  if (!proyeccion || !proyeccion.dias) {
    return (
      <motion.div
        initial={{ opacity: 0, scale: 0.95 }}
        animate={{ opacity: 1, scale: 1 }}
        className="card"
      >
        <div className="card-body" style={{ textAlign: 'center', padding: '3rem' }}>
          <p style={{ fontSize: '1.1rem', color: 'var(--text-light)', display: 'flex', alignItems: 'center', justifyContent: 'center', gap: 6 }}>
            <BarChart size={20} /> No hay proyección generada. Genérela desde la pestaña "Oferta".
          </p>
        </div>
      </motion.div>
    )
  }

  const handleDelete = async (diaIdx, loteIdx) => {
    if (!window.confirm('¿Eliminar este lote de la proyección?')) return
    setLoading(true)
    try {
      const data = await eliminarLote(diaIdx, loteIdx)
      setProyeccion(data)
    } catch (err) {
      toast.error('Error al eliminar: ' + (err.response?.data?.detail || err.message))
    } finally {
      setLoading(false)
    }
  }

  const handleMove = async (diaOrigen, loteIdx, diaDestino) => {
    setLoading(true)
    try {
      const data = await moverLote({
        lote_index: loteIdx,
        dia_origen: diaOrigen,
        dia_destino: diaDestino,
      })
      setProyeccion(data)
      setMovingLote(null)
    } catch (err) {
      toast.error('Error al mover: ' + (err.response?.data?.detail || err.message))
    } finally {
      setLoading(false)
    }
  }

  const handleAjusteMartes = async () => {
    if (!ajusteFile) return
    setAjusteLoading(true)
    try {
      const data = await uploadAjusteMartes(ajusteFile)
      setProyeccion(data.proyeccion)
      setAjusteResumen(data.resumen_ajuste)
      setAjusteFile(null)
      toast.success('Proyección ajustada con oferta del martes')
    } catch (err) {
      toast.error('Error al ajustar: ' + (err.response?.data?.detail || err.message))
    } finally {
      setAjusteLoading(false)
    }
  }

  const handleAjusteFile = (f) => {
    if (f && (f.name.endsWith('.xlsx') || f.name.endsWith('.xls'))) {
      setAjusteFile(f)
    } else {
      toast.error('Solo se aceptan archivos .xlsx o .xls')
    }
  }

  const { dias } = proyeccion
  const lotesNoAsignados = proyeccion.lotes_no_asignados || []
  const lotesFueraRango = proyeccion.lotes_fuera_rango || []

  const toggleFR = (idx) => {
    setExpandedFR(prev => {
      const next = new Set(prev)
      if (next.has(idx)) next.delete(idx)
      else next.add(idx)
      return next
    })
  }

  return (
    <motion.div
      variants={containerVariants}
      initial="hidden"
      animate="show"
    >
      {/* Stats generales */}
      <motion.div variants={itemVariants} className="stats-grid">
        <div className="stat-card">
          <div className="stat-label">Total Pollos Semana</div>
          <div className="stat-value green">{formatNumber(proyeccion.total_pollos_semana)}</div>
        </div>
        <div className="stat-card">
          <div className="stat-label">Promedio Edad Semana</div>
          <div className="stat-value blue">{proyeccion.promedio_edad_semana?.toFixed(1)}</div>
        </div>
        <div className="stat-card">
          <div className="stat-label">Cajas Semanales</div>
          <div className="stat-value orange">{formatNumber(proyeccion.produccion_cajas_semanales)}</div>
        </div>
        <div className="stat-card">
          <div className="stat-label">Sofía (Total - 10.000)</div>
          <div className="stat-value">{formatNumber(proyeccion.sofia)}</div>
        </div>
      </motion.div>

      {/* Ajuste con Oferta del Martes */}
      <motion.div variants={itemVariants} className="card" style={{ borderLeft: '4px solid var(--info)' }}>
        <div
          className="card-header"
          style={{ cursor: 'pointer', userSelect: 'none' }}
          onClick={() => setAjusteOpen(!ajusteOpen)}
        >
          <h2><RefreshCw size={18} style={{ verticalAlign: 'middle', marginRight: 6 }} /> Ajustar con Oferta del Martes</h2>
          <span style={{ fontSize: '0.85rem', color: 'var(--text-light)' }}>
            {ajusteOpen ? '▲ Cerrar' : '▼ Abrir'}
          </span>
        </div>
        <AnimatePresence>
          {ajusteOpen && (
            <motion.div
              initial={{ height: 0, opacity: 0 }}
              animate={{ height: 'auto', opacity: 1 }}
              exit={{ height: 0, opacity: 0 }}
              style={{ overflow: 'hidden' }}
            >
              <div className="card-body">
                <p style={{ marginBottom: '1rem', fontSize: '0.9rem', color: 'var(--text-light)' }}>
                  Suba la oferta del martes para actualizar los datos de peso, edad y ganancia de los lotes.
                  Las asignaciones de día se mantienen.
                </p>
                <div style={{ display: 'flex', gap: '0.75rem', alignItems: 'center', flexWrap: 'wrap' }}>
                  <div
                    style={{
                      flex: 1,
                      minWidth: 200,
                      border: '1px dashed var(--border)',
                      borderRadius: 8,
                      padding: '0.75rem 1rem',
                      cursor: 'pointer',
                      background: ajusteFile ? 'var(--info-light)' : '#f8fafc',
                      display: 'flex',
                      alignItems: 'center',
                      gap: 8,
                      fontSize: '0.85rem',
                      transition: 'all 0.2s',
                    }}
                    onClick={() => ajusteInputRef.current?.click()}
                  >
                    {ajusteFile ? (
                      <><FileSpreadsheet size={16} color="var(--info)" /> {ajusteFile.name}</>
                    ) : (
                      <><UploadCloud size={16} color="var(--text-light)" /> Seleccionar archivo Excel...</>
                    )}
                    <input
                      ref={ajusteInputRef}
                      type="file"
                      accept=".xlsx,.xls"
                      style={{ display: 'none' }}
                      onChange={(e) => handleAjusteFile(e.target.files[0])}
                    />
                  </div>
                  <button
                    className="btn btn-primary"
                    disabled={!ajusteFile || ajusteLoading}
                    onClick={handleAjusteMartes}
                    style={{ whiteSpace: 'nowrap' }}
                  >
                    {ajusteLoading ? (
                      <><span className="spinner" style={{ width: 14, height: 14, marginRight: 6 }}></span> Ajustando...</>
                    ) : (
                      <><RefreshCw size={14} /> Aplicar Ajuste</>
                    )}
                  </button>
                  {ajusteFile && (
                    <button className="btn btn-sm btn-outline" onClick={() => setAjusteFile(null)}>
                      <X size={14} />
                    </button>
                  )}
                </div>

                {/* Resumen del ajuste */}
                {ajusteResumen && (
                  <motion.div
                    initial={{ opacity: 0, y: 10 }}
                    animate={{ opacity: 1, y: 0 }}
                    style={{ marginTop: '1rem', padding: '1rem', background: '#f8fafc', borderRadius: 8, border: '1px solid var(--border)' }}
                  >
                    <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '0.75rem' }}>
                      <strong style={{ fontSize: '0.9rem' }}>Resultado del ajuste</strong>
                      <button className="btn btn-sm btn-outline" onClick={() => setAjusteResumen(null)}>
                        <X size={12} />
                      </button>
                    </div>
                    <div style={{ display: 'flex', gap: '1rem', flexWrap: 'wrap', marginBottom: '0.75rem' }}>
                      {ajusteResumen.lotes_actualizados > 0 && (
                        <span style={{ display: 'flex', alignItems: 'center', gap: 4, fontSize: '0.85rem', color: 'var(--success)' }}>
                          <CheckCircle2 size={14} /> {ajusteResumen.lotes_actualizados} lotes actualizados
                        </span>
                      )}
                      {ajusteResumen.lotes_nuevos_asignados > 0 && (
                        <span style={{ display: 'flex', alignItems: 'center', gap: 4, fontSize: '0.85rem', color: 'var(--success)' }}>
                          <CheckCircle2 size={14} /> {ajusteResumen.lotes_nuevos_asignados} lotes nuevos asignados
                        </span>
                      )}
                      {(ajusteResumen.lotes_nuevos - (ajusteResumen.lotes_nuevos_asignados || 0) - (ajusteResumen.lotes_nuevos_fuera_rango || 0)) > 0 && (
                        <span style={{ display: 'flex', alignItems: 'center', gap: 4, fontSize: '0.85rem', color: 'var(--info)' }}>
                          <PlusCircle size={14} /> {ajusteResumen.lotes_nuevos - (ajusteResumen.lotes_nuevos_asignados || 0) - (ajusteResumen.lotes_nuevos_fuera_rango || 0)} lotes nuevos sin capacidad
                        </span>
                      )}
                      {ajusteResumen.lotes_nuevos_fuera_rango > 0 && (
                        <span style={{ display: 'flex', alignItems: 'center', gap: 4, fontSize: '0.85rem', color: 'var(--danger, #ef4444)' }}>
                          <Ban size={14} /> {ajusteResumen.lotes_nuevos_fuera_rango} lotes nuevos fuera de rango
                        </span>
                      )}
                      {ajusteResumen.lotes_fuera_rango_post_ajuste > 0 && (
                        <span style={{ display: 'flex', alignItems: 'center', gap: 4, fontSize: '0.85rem', color: 'var(--danger, #ef4444)' }}>
                          <AlertTriangle size={14} /> {ajusteResumen.lotes_fuera_rango_post_ajuste} lotes existentes ahora fuera de rango
                        </span>
                      )}
                      {ajusteResumen.lotes_faltantes > 0 && (
                        <span style={{ display: 'flex', alignItems: 'center', gap: 4, fontSize: '0.85rem', color: 'var(--warning)' }}>
                          <AlertTriangle size={14} /> {ajusteResumen.lotes_faltantes} lotes no encontrados en martes
                        </span>
                      )}
                      {ajusteResumen.lotes_actualizados === 0 && ajusteResumen.lotes_nuevos === 0 && ajusteResumen.lotes_faltantes === 0 && (
                        <span style={{ fontSize: '0.85rem', color: 'var(--text-light)' }}>Sin cambios detectados.</span>
                      )}
                    </div>

                    {/* Detalle de actualizaciones */}
                    {ajusteResumen.detalle_actualizados?.length > 0 && (
                      <div style={{ marginBottom: '0.5rem' }}>
                        <p style={{ fontSize: '0.8rem', fontWeight: 600, color: 'var(--text-light)', marginBottom: 4 }}>Cambios:</p>
                        <div className="table-container" style={{ maxHeight: 180, overflowY: 'auto' }}>
                          <table>
                            <thead>
                              <tr>
                                <th>Granja</th>
                                <th>Galpón</th>
                                <th>Día</th>
                                <th>Cambios</th>
                              </tr>
                            </thead>
                            <tbody>
                              {ajusteResumen.detalle_actualizados.map((d, i) => (
                                <tr key={i}>
                                  <td><strong>{d.granja}</strong></td>
                                  <td className="text-center">{d.galpon}</td>
                                  <td>{d.dia}</td>
                                  <td style={{ fontSize: '0.8rem' }}>{d.cambios}</td>
                                </tr>
                              ))}
                            </tbody>
                          </table>
                        </div>
                      </div>
                    )}

                    {/* Lotes existentes ahora fuera de rango tras ajuste martes */}
                    {ajusteResumen.detalle_fuera_rango_post_ajuste?.length > 0 && (
                      <div style={{ marginBottom: '0.5rem' }}>
                        <p style={{ fontSize: '0.8rem', fontWeight: 600, color: 'var(--danger, #ef4444)', marginBottom: 4 }}>⚠ Lotes existentes ahora fuera de rango (revisar manualmente):</p>
                        <div className="table-container" style={{ maxHeight: 180, overflowY: 'auto' }}>
                          <table>
                            <thead>
                              <tr>
                                <th>Granja</th>
                                <th>Galpón</th>
                                <th>Cantidad</th>
                                <th>Día</th>
                                <th>Alerta</th>
                              </tr>
                            </thead>
                            <tbody>
                              {ajusteResumen.detalle_fuera_rango_post_ajuste.map((d, i) => (
                                <tr key={i}>
                                  <td><strong>{d.granja}</strong></td>
                                  <td className="text-center">{d.galpon}</td>
                                  <td className="text-right">{formatNumber(d.cantidad)}</td>
                                  <td>{d.dia}</td>
                                  <td style={{ fontSize: '0.8rem', color: 'var(--danger, #ef4444)' }}>{d.alerta}</td>
                                </tr>
                              ))}
                            </tbody>
                          </table>
                        </div>
                      </div>
                    )}

                    {/* Lotes nuevos asignados automáticamente */}
                    {ajusteResumen.detalle_nuevos_asignados?.length > 0 && (
                      <div style={{ marginBottom: '0.5rem' }}>
                        <p style={{ fontSize: '0.8rem', fontWeight: 600, color: 'var(--success)', marginBottom: 4 }}>Lotes nuevos asignados:</p>
                        <div className="table-container" style={{ maxHeight: 180, overflowY: 'auto' }}>
                          <table>
                            <thead>
                              <tr>
                                <th>Granja</th>
                                <th>Galpón</th>
                                <th>Núcleo</th>
                                <th className="text-right">Cantidad</th>
                                <th>Día asignado</th>
                              </tr>
                            </thead>
                            <tbody>
                              {ajusteResumen.detalle_nuevos_asignados.map((d, i) => (
                                <tr key={i}>
                                  <td><strong>{d.granja}</strong></td>
                                  <td className="text-center">{d.galpon}</td>
                                  <td className="text-center">{d.nucleo}</td>
                                  <td className="text-right">{formatNumber(d.cantidad)}</td>
                                  <td>{d.dia}</td>
                                </tr>
                              ))}
                            </tbody>
                          </table>
                        </div>
                      </div>
                    )}

                    {/* Lotes faltantes (en proyección pero no en martes) */}
                    {ajusteResumen.detalle_faltantes?.length > 0 && (
                      <div style={{ marginBottom: '0.5rem' }}>
                        <p style={{ fontSize: '0.8rem', fontWeight: 600, color: 'var(--warning)', marginBottom: 4 }}>⚠ Lotes no encontrados en oferta del martes (se mantienen sin cambios):</p>
                        <div className="table-container" style={{ maxHeight: 180, overflowY: 'auto' }}>
                          <table>
                            <thead>
                              <tr>
                                <th>Granja</th>
                                <th>Galpón</th>
                                <th>Núcleo</th>
                                <th className="text-right">Cantidad</th>
                                <th>Sexo</th>
                                <th>Día</th>
                              </tr>
                            </thead>
                            <tbody>
                              {ajusteResumen.detalle_faltantes.map((d, i) => (
                                <tr key={i}>
                                  <td><strong>{d.granja}</strong></td>
                                  <td className="text-center">{d.galpon}</td>
                                  <td className="text-center">{d.nucleo}</td>
                                  <td className="text-right">{formatNumber(d.cantidad)}</td>
                                  <td className="text-center">{d.sexo}</td>
                                  <td>{d.dia}</td>
                                </tr>
                              ))}
                            </tbody>
                          </table>
                        </div>
                      </div>
                    )}
                  </motion.div>
                )}
              </div>
            </motion.div>
          )}
        </AnimatePresence>
      </motion.div>

      {lotesNoAsignados.length > 0 && (
        <motion.div variants={itemVariants} className="card" style={{ borderLeft: '4px solid var(--warning)' }}>
          <div className="card-header">
            <h2><PackageOpen size={18} style={{ verticalAlign: 'middle', marginRight: 6 }} /> Lotes no asignados por tope diario</h2>
          </div>
          <div className="card-body">
            <p style={{ marginBottom: '0.8rem', fontSize: '0.9rem', color: 'var(--text-light)' }}>
              {lotesNoAsignados.length} lotes no asignados ({formatNumber(proyeccion.total_pollos_no_asignados || 0)} pollos). Revise estos lotes para decidir ajuste manual o cambio de parámetros.
            </p>
            <div className="table-container" style={{ maxHeight: '260px', overflowY: 'auto' }}>
              <table>
                <thead>
                  <tr>
                    <th>Granja</th>
                    <th>Galpón</th>
                    <th>Núcleo</th>
                    <th className="text-right">Cantidad</th>
                    <th>Días elegibles</th>
                    <th>Motivo</th>
                  </tr>
                </thead>
                <tbody>
                  {lotesNoAsignados.map((lote, idx) => (
                    <tr key={`no-asignado-${idx}`}>
                      <td><strong>{lote.granja}</strong></td>
                      <td className="text-center">{lote.galpon}</td>
                      <td className="text-center">{lote.nucleo}</td>
                      <td className="text-right">{formatNumber(lote.cantidad)}</td>
                      <td>{formatDiasElegibles(lote.dias_elegibles)}</td>
                      <td style={{ color: 'var(--warning)' }}>{lote.motivo}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        </motion.div>
      )}

      {lotesFueraRango.length > 0 && (
        <motion.div variants={itemVariants} className="card" style={{ borderLeft: '4px solid var(--danger, #ef4444)' }}>
          <div className="card-header">
            <h2><Ban size={18} style={{ verticalAlign: 'middle', marginRight: 6 }} /> Lotes fuera de rango (edad/peso)</h2>
          </div>
          <div className="card-body">
            <p style={{ marginBottom: '0.8rem', fontSize: '0.9rem', color: 'var(--text-light)' }}>
              {lotesFueraRango.length} lotes fuera de rango ({formatNumber(proyeccion.total_pollos_fuera_rango || 0)} pollos).
              No cumplen los requisitos de edad o peso para ningún día de faena.
            </p>
            <div className="table-container" style={{ maxHeight: '360px', overflowY: 'auto' }}>
              <table>
                <thead>
                  <tr>
                    <th style={{ width: 28 }}></th>
                    <th>Granja</th>
                    <th>Galpón</th>
                    <th>Núcleo</th>
                    <th className="text-right">Cantidad</th>
                    <th>Sexo</th>
                    <th>Motivo</th>
                  </tr>
                </thead>
                <tbody>
                  {lotesFueraRango.map((lote, idx) => (
                    <React.Fragment key={`fr-${idx}`}>
                      <tr
                        style={{ cursor: 'pointer' }}
                        onClick={() => toggleFR(idx)}
                      >
                        <td style={{ padding: '0.3rem 0.4rem' }}>
                          {expandedFR.has(idx)
                            ? <ChevronDown size={14} />
                            : <ChevronRight size={14} />
                          }
                        </td>
                        <td><strong>{lote.granja}</strong></td>
                        <td className="text-center">{lote.galpon}</td>
                        <td className="text-center">{lote.nucleo}</td>
                        <td className="text-right">{formatNumber(lote.cantidad)}</td>
                        <td className="text-center">{lote.sexo || '-'}</td>
                        <td style={{ color: 'var(--danger, #ef4444)', fontSize: '0.85rem' }}>{lote.motivo}</td>
                      </tr>
                      {expandedFR.has(idx) && lote.detalle_por_dia?.length > 0 && (
                        <tr>
                          <td colSpan={7} style={{ padding: '0 0.5rem 0.5rem 2rem', background: '#fef2f2' }}>
                            <table style={{ width: '100%', fontSize: '0.8rem' }}>
                              <thead>
                                <tr>
                                  <th>Día</th>
                                  <th className="text-right">Edad Proy.</th>
                                  <th className="text-right">Peso Proy.</th>
                                  <th>Razón</th>
                                </tr>
                              </thead>
                              <tbody>
                                {lote.detalle_por_dia.map((d, dIdx) => (
                                  <tr key={dIdx}>
                                    <td>{formatDate(d.fecha)}</td>
                                    <td className="text-right">{d.edad_proyectada}</td>
                                    <td className="text-right">{d.peso_proyectado?.toFixed(2)}</td>
                                    <td style={{ color: 'var(--danger, #ef4444)' }}>{d.razon}</td>
                                  </tr>
                                ))}
                              </tbody>
                            </table>
                          </td>
                        </tr>
                      )}
                    </React.Fragment>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        </motion.div>
      )}

      {/* Toggle vista */}
      <motion.div variants={itemVariants} className="tabs" style={{ justifyContent: 'space-between' }}>
        <div style={{ display: 'flex', gap: '0.5rem' }}>
          <button className={`tab ${viewMode === 'cards' ? 'active' : ''}`} onClick={() => setViewMode('cards')}>
            <KanbanSquare size={16} style={{ verticalAlign: 'middle', marginRight: 4 }} /> Vista por Día
          </button>
          <button className={`tab ${viewMode === 'table' ? 'active' : ''}`} onClick={() => setViewMode('table')}>
            <Table size={16} style={{ verticalAlign: 'middle', marginRight: 4 }} /> Vista Tabla
          </button>
        </div>
        <button className="btn btn-sm btn-outline" onClick={() => exportProyeccionPDF(proyeccion)} style={{ marginBottom: '0.5rem' }}>
          <Download size={14} /> Descargar PDF
        </button>
      </motion.div>

      {/* Modal de mover */}
      <AnimatePresence>
        {movingLote && (
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            className="modal-overlay"
            onClick={() => setMovingLote(null)}
          >
            <motion.div
              initial={{ scale: 0.9, y: 20 }}
              animate={{ scale: 1, y: 0 }}
              exit={{ scale: 0.9, y: 20 }}
              className="modal"
              onClick={e => e.stopPropagation()}
            >
              <div className="modal-header">
                <h3><ArrowLeftRight size={18} style={{ verticalAlign: 'middle', marginRight: 6 }} /> Mover lote a otro día</h3>
                <button className="btn btn-sm btn-outline" onClick={() => setMovingLote(null)}>
                  <X size={16} />
                </button>
              </div>
              <div className="modal-body">
                <p style={{ marginBottom: '1rem', fontSize: '0.9rem' }}>
                  Mover <strong>{movingLote.lote.granja} G{movingLote.lote.galpon}</strong> ({formatNumber(movingLote.lote.cantidad)} pollos) desde {DIAS_SEMANA[movingLote.diaIdx]}:
                </p>
                <div style={{ display: 'flex', flexDirection: 'column', gap: '0.5rem' }}>
                  {dias.map((d, idx) => (
                    idx !== movingLote.diaIdx && (
                      <button
                        key={idx}
                        className="btn btn-outline"
                        onClick={() => handleMove(movingLote.diaIdx, movingLote.loteIdx, idx)}
                        disabled={loading}
                        style={{ justifyContent: 'flex-start' }}
                      >
                        <Calendar size={16} style={{ marginRight: 6 }} /> {DIAS_SEMANA[idx]} ({formatDate(d.fecha)}) — {formatNumber(d.total_pollos)} pollos
                      </button>
                    )
                  ))}
                </div>
              </div>
            </motion.div>
          </motion.div>
        )}
      </AnimatePresence>

      {/* Vista Cards */}
      {viewMode === 'cards' && (
        <motion.div
          initial={{ opacity: 0, y: 10 }}
          animate={{ opacity: 1, y: 0 }}
          className="proyeccion-grid"
        >
          {dias.map((dia, diaIdx) => (
            <div className="day-column" key={diaIdx}>
              <div className="day-header">
                <span>{DIAS_SEMANA[diaIdx]}</span>
                <span className="day-total">{formatNumber(dia.total_pollos)}</span>
              </div>
              <div className="day-body">
                {dia.lotes.length === 0 ? (
                  <p style={{ textAlign: 'center', color: 'var(--text-light)', padding: '1rem', fontSize: '0.8rem' }}>
                    Sin lotes asignados
                  </p>
                ) : (
                  dia.lotes.map((lote, loteIdx) => (
                    <motion.div
                      key={loteIdx}
                      initial={{ opacity: 0, scale: 0.9 }}
                      animate={{ opacity: 1, scale: 1 }}
                      transition={{ delay: loteIdx * 0.05 }}
                      className="lote-card"
                    >
                      <div className="lote-header">
                        <span>{lote.granja} G{lote.galpon}</span>
                        <span className={`badge badge-${lote.sexo === 'M' ? 'info' : lote.sexo === 'H' ? 'warning' : 'success'}`}>
                          {lote.sexo || '-'}
                        </span>
                      </div>
                      <div className="lote-detail">
                        <span>Pollos: {formatNumber(lote.cantidad)}</span>
                        <span>Edad: {lote.edad_fin_retiro}</span>
                      </div>
                      <div className="lote-detail">
                        <span>Peso: {lote.peso_vivo_retiro?.toFixed(2)} kg</span>
                        <span style={{ color: `var(--${getEdadColor(lote.diferencia_edad_ideal)})` }}>
                          Dif: {lote.diferencia_edad_ideal > 0 ? '+' : ''}{lote.diferencia_edad_ideal}
                        </span>
                      </div>
                      <div className="lote-detail">
                        <span>Faenado: {lote.peso_faenado?.toFixed(2)}</span>
                        <span>Cajas: {formatNumber(lote.cajas)}</span>
                      </div>
                      <div className="lote-actions">
                        <button
                          className="btn btn-sm btn-outline"
                          onClick={() => setMovingLote({ diaIdx, loteIdx, lote })}
                        >
                          <ArrowLeftRight size={12} style={{ marginRight: 2 }} /> Mover
                        </button>
                        <button
                          className="btn btn-sm btn-danger"
                          onClick={() => handleDelete(diaIdx, loteIdx)}
                        >
                          <X size={12} style={{ marginRight: 2 }} /> Eliminar
                        </button>
                      </div>
                    </motion.div>
                  ))
                )}
              </div>
              <div className="day-summary">
                <span className="label">Peso prom.</span>
                <span className="value">{dia.peso_promedio_ponderado?.toFixed(2)} kg</span>
                <span className="label">Dif. edad prom.</span>
                <span className="value" style={{ color: `var(--${getEdadColor(dia.diferencia_edad_promedio)})` }}>
                  {dia.diferencia_edad_promedio?.toFixed(1)}
                </span>
                <span className="label">Cajas</span>
                <span className="value">{formatNumber(dia.cajas_totales)}</span>
              </div>
            </div>
          ))}
        </motion.div>
      )}

      {/* Vista Tabla */}
      {viewMode === 'table' && (
        <motion.div
          initial={{ opacity: 0, scale: 0.98 }}
          animate={{ opacity: 1, scale: 1 }}
          className="card"
        >
          <div className="card-body">
            <div className="table-container" style={{ maxHeight: '600px', overflowY: 'auto' }}>
              <table>
                <thead>
                  <tr>
                    <th>Día</th>
                    <th>Fecha</th>
                    <th>Granja</th>
                    <th>Galpón</th>
                    <th>Núcleo</th>
                    <th className="text-right">Cantidad</th>
                    <th>Sexo</th>
                    <th className="text-right">Edad Fin</th>
                    <th className="text-right">Dif. Edad</th>
                    <th className="text-right">Peso Vivo</th>
                    <th className="text-right">Peso Faenado</th>
                    <th className="text-right">Calibre</th>
                    <th className="text-right">Cajas</th>
                    <th>Acciones</th>
                  </tr>
                </thead>
                <tbody>
                  {dias.map((dia, diaIdx) => (
                    <React.Fragment key={`day-${diaIdx}`}>
                      {dia.lotes.map((lote, loteIdx) => (
                        <tr key={`${diaIdx}-${loteIdx}`}>
                          {loteIdx === 0 && (
                            <td rowSpan={dia.lotes.length + 1} style={{ verticalAlign: 'top', fontWeight: 600 }}>
                              {DIAS_SEMANA[diaIdx]}
                            </td>
                          )}
                          <td>{formatDate(dia.fecha)}</td>
                          <td><strong>{lote.granja}</strong></td>
                          <td className="text-center">{lote.galpon}</td>
                          <td className="text-center">{lote.nucleo}</td>
                          <td className="text-right">{formatNumber(lote.cantidad)}</td>
                          <td className="text-center">
                            <span className={`badge badge-${lote.sexo === 'M' ? 'info' : lote.sexo === 'H' ? 'warning' : 'success'}`}>
                              {lote.sexo || '-'}
                            </span>
                          </td>
                          <td className="text-right">{lote.edad_fin_retiro}</td>
                          <td className="text-right" style={{ color: `var(--${getEdadColor(lote.diferencia_edad_ideal)})` }}>
                            {lote.diferencia_edad_ideal > 0 ? '+' : ''}{lote.diferencia_edad_ideal}
                          </td>
                          <td className="text-right">{lote.peso_vivo_retiro?.toFixed(2)}</td>
                          <td className="text-right">{lote.peso_faenado?.toFixed(2)}</td>
                          <td className="text-right">{lote.calibre_promedio?.toFixed(2)}</td>
                          <td className="text-right">{formatNumber(lote.cajas)}</td>
                          <td>
                            <button className="btn btn-sm btn-danger" onClick={() => handleDelete(diaIdx, loteIdx)}>✕</button>
                          </td>
                        </tr>
                      ))}
                      <tr className="row-subtotal" key={`sub-${diaIdx}`}>
                        <td colSpan={4}><strong>Subtotal {DIAS_SEMANA[diaIdx]}</strong></td>
                        <td className="text-right"><strong>{formatNumber(dia.total_pollos)}</strong></td>
                        <td></td>
                        <td></td>
                        <td className="text-right" style={{ color: `var(--${getEdadColor(dia.diferencia_edad_promedio)})` }}>
                          {dia.diferencia_edad_promedio?.toFixed(1)}
                        </td>
                        <td className="text-right">{dia.peso_promedio_ponderado?.toFixed(2)}</td>
                        <td></td>
                        <td className="text-right">{dia.calibre_promedio_ponderado?.toFixed(2)}</td>
                        <td className="text-right">{formatNumber(dia.cajas_totales)}</td>
                        <td></td>
                      </tr>
                    </React.Fragment>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        </motion.div>
      )}
    </motion.div>
  )
}
