import React, { useState, useEffect } from 'react'
import { motion } from 'framer-motion'
import { Scale, AlertTriangle, CheckCircle2, ArrowUpDown, Save, Trash2, Loader2, MessageCircleWarning, Target, ShoppingCart, TrendingDown, Zap } from 'lucide-react'
import toast from 'react-hot-toast'
import { cargarPesosReales, getDesvio, deletePesosReales, getRecomendacionPeso } from '../services/api'

const containerVariants = {
  hidden: { opacity: 0 },
  show: { opacity: 1, transition: { staggerChildren: 0.08 } }
}
const itemVariants = {
  hidden: { opacity: 0, y: 15 },
  show: { opacity: 1, y: 0, transition: { duration: 0.3 } }
}

const DIAS_SEMANA = ['Lunes', 'Martes', 'Miércoles', 'Jueves', 'Viernes', 'Sábado', 'Domingo']

function getDiaNombre(fechaStr) {
  if (!fechaStr) return '-'
  const dt = new Date(fechaStr + 'T12:00:00')
  const idx = dt.getDay() === 0 ? 6 : dt.getDay() - 1
  return DIAS_SEMANA[idx]
}

function formatNumber(n) {
  if (n == null) return '-'
  return n.toLocaleString('es-AR')
}

function getNivelColor(nivel) {
  switch (nivel) {
    case 'normal': return 'var(--success)'
    case 'moderado': return 'var(--warning)'
    case 'critico': return '#ef4444'
    default: return 'var(--text-light)'
  }
}

function getNivelBg(nivel) {
  switch (nivel) {
    case 'normal': return 'rgba(34, 197, 94, 0.08)'
    case 'moderado': return 'rgba(251, 146, 60, 0.08)'
    case 'critico': return 'rgba(239, 68, 68, 0.08)'
    default: return 'transparent'
  }
}

function getNivelIcon(nivel) {
  switch (nivel) {
    case 'normal': return <CheckCircle2 size={16} color="var(--success)" />
    case 'moderado': return <AlertTriangle size={16} color="var(--warning)" />
    case 'critico': return <AlertTriangle size={16} color="#ef4444" />
    default: return <ArrowUpDown size={16} color="var(--text-light)" />
  }
}

export default function DesvioView({ proyeccion }) {
  const [desvioData, setDesvioData] = useState(null)
  const [pesosInput, setPesosInput] = useState({})
  const [loading, setLoading] = useState(true)
  const [saving, setSaving] = useState(false)
  const [recomendacion, setRecomendacion] = useState(null)

  useEffect(() => {
    cargarDesvio()
  }, [])

  const cargarRecomendacion = async () => {
    try {
      const data = await getRecomendacionPeso()
      setRecomendacion(data)
    } catch {
      setRecomendacion(null)
    }
  }

  const cargarDesvio = async () => {
    setLoading(true)
    try {
      const data = await getDesvio()
      setDesvioData(data)
      // Pre-fill inputs con pesos reales existentes
      const inputs = {}
      data.dias.forEach(d => {
        if (d.peso_real != null) {
          inputs[d.fecha] = d.peso_real.toString()
        }
      })
      setPesosInput(inputs)
    } catch {
      // No desvío data yet
      setDesvioData(null)
      // Pre-fill con fechas de la proyección
      if (proyeccion?.dias) {
        const inputs = {}
        proyeccion.dias.forEach(d => { inputs[d.fecha] = '' })
        setPesosInput(inputs)
      }
    } finally {
      setLoading(false)
      cargarRecomendacion()
    }
  }

  const handleSave = async () => {
    const pesos = Object.entries(pesosInput)
      .filter(([, val]) => val && parseFloat(val) > 0)
      .map(([fecha, val]) => ({
        fecha,
        peso_promedio_real: parseFloat(val),
      }))

    if (pesos.length === 0) {
      toast.error('Ingrese al menos un peso real')
      return
    }

    setSaving(true)
    try {
      await cargarPesosReales(pesos)
      toast.success(`${pesos.length} pesos reales guardados`)
      await cargarDesvio()
      await cargarRecomendacion()
    } catch (err) {
      toast.error('Error: ' + (err.response?.data?.detail || err.message))
    } finally {
      setSaving(false)
    }
  }

  const handleDelete = async () => {
    if (!window.confirm('¿Eliminar todos los pesos reales cargados?')) return
    try {
      await deletePesosReales()
      setDesvioData(null)
      if (proyeccion?.dias) {
        const inputs = {}
        proyeccion.dias.forEach(d => { inputs[d.fecha] = '' })
        setPesosInput(inputs)
      }
      toast.success('Pesos reales eliminados')
    } catch (err) {
      toast.error('Error: ' + (err.response?.data?.detail || err.message))
    }
  }

  if (!proyeccion || !proyeccion.dias) {
    return (
      <motion.div initial={{ opacity: 0, scale: 0.95 }} animate={{ opacity: 1, scale: 1 }} className="card">
        <div className="card-body" style={{ textAlign: 'center', padding: '3rem' }}>
          <p style={{ fontSize: '1.1rem', color: 'var(--text-light)', display: 'flex', alignItems: 'center', justifyContent: 'center', gap: 6 }}>
            <Scale size={20} /> No hay proyección generada. Genérela primero para cargar desvíos.
          </p>
        </div>
      </motion.div>
    )
  }

  if (loading) {
    return (
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', padding: '4rem', gap: 8 }}>
        <Loader2 size={24} style={{ animation: 'spin 1s linear infinite' }} />
        <span style={{ color: 'var(--text-light)' }}>Cargando desvíos...</span>
      </div>
    )
  }

  const dias = proyeccion.dias

  return (
    <motion.div variants={containerVariants} initial="hidden" animate="show">
      {/* Alerta de desvío */}
      {desvioData?.mensaje_alerta && (
        <motion.div variants={itemVariants} style={{
          padding: '1rem 1.2rem',
          background: getNivelBg(desvioData.alerta_semana),
          border: `1px solid ${getNivelColor(desvioData.alerta_semana)}`,
          borderRadius: 10,
          display: 'flex', alignItems: 'flex-start', gap: 10,
          fontSize: '0.9rem',
          color: getNivelColor(desvioData.alerta_semana),
          fontWeight: 500,
        }}>
          <MessageCircleWarning size={22} style={{ flexShrink: 0, marginTop: 1 }} />
          <div>
            <div style={{ fontWeight: 600, marginBottom: 2 }}>Alerta para Comercial</div>
            <div style={{ fontWeight: 400 }}>{desvioData.mensaje_alerta}</div>
          </div>
        </motion.div>
      )}

      {/* Stats */}
      {desvioData && (
        <motion.div variants={itemVariants} className="stats-grid">
          <div className="stat-card">
            <div className="stat-label">Desvío Promedio</div>
            <div className="stat-value" style={{ color: getNivelColor(desvioData.alerta_semana) }}>
              {desvioData.desvio_promedio_semana != null
                ? `${desvioData.desvio_promedio_semana > 0 ? '+' : ''}${(desvioData.desvio_promedio_semana * 1000).toFixed(0)}g`
                : '-'}
            </div>
          </div>
          <div className="stat-card">
            <div className="stat-label">Nivel de Alerta</div>
            <div className="stat-value" style={{ color: getNivelColor(desvioData.alerta_semana), textTransform: 'capitalize' }}>
              {desvioData.alerta_semana?.replace('_', ' ') || '-'}
            </div>
          </div>
          <div className="stat-card">
            <div className="stat-label">Días con Datos</div>
            <div className="stat-value blue">
              {desvioData.dias.filter(d => d.peso_real != null).length} / {desvioData.dias.length}
            </div>
          </div>
        </motion.div>
      )}

      {/* Formulario + Tabla */}
      <motion.div variants={itemVariants} className="card" style={{ borderLeft: '4px solid var(--primary)' }}>
        <div className="card-header">
          <h2><Scale size={18} style={{ verticalAlign: 'middle', marginRight: 6 }} /> Cargar Peso Real Recibido</h2>
          <div style={{ display: 'flex', gap: '0.5rem' }}>
            {desvioData && (
              <button className="btn btn-sm btn-danger" onClick={handleDelete}>
                <Trash2 size={14} /> Limpiar
              </button>
            )}
          </div>
        </div>
        <div className="card-body">
          <p style={{ marginBottom: '1rem', fontSize: '0.85rem', color: 'var(--text-light)' }}>
            Ingrese el peso promedio real recibido (kg) para cada día. Luego presione "Guardar" para ver la comparación.
          </p>
          <div className="table-container">
            <table>
              <thead>
                <tr>
                  <th>Día</th>
                  <th className="text-right">Pollos</th>
                  <th className="text-right">Peso Proyectado</th>
                  <th className="text-center" style={{ minWidth: 120 }}>Peso Real (kg)</th>
                  {desvioData && <>
                    <th className="text-right">Desvío (kg)</th>
                    <th className="text-right">Desvío (%)</th>
                    <th className="text-center">Estado</th>
                  </>}
                </tr>
              </thead>
              <tbody>
                {dias.map((dia, idx) => {
                  const desvDia = desvioData?.dias?.find(d => d.fecha === dia.fecha)
                  return (
                    <tr key={idx} style={{ background: desvDia ? getNivelBg(desvDia.nivel) : undefined }}>
                      <td><strong>{getDiaNombre(dia.fecha)}</strong></td>
                      <td className="text-right">{formatNumber(dia.total_pollos)}</td>
                      <td className="text-right">{dia.peso_promedio_ponderado?.toFixed(3)} kg</td>
                      <td className="text-center">
                        <input
                          type="number"
                          step="0.001"
                          min="0"
                          placeholder="ej: 3.150"
                          value={pesosInput[dia.fecha] || ''}
                          onChange={(e) => setPesosInput(prev => ({ ...prev, [dia.fecha]: e.target.value }))}
                          style={{
                            width: '100%', maxWidth: 110,
                            padding: '0.35rem 0.5rem',
                            border: '1px solid var(--border)',
                            borderRadius: 6,
                            fontSize: '0.85rem',
                            textAlign: 'center',
                          }}
                        />
                      </td>
                      {desvioData && <>
                        <td className="text-right" style={{ color: getNivelColor(desvDia?.nivel), fontWeight: 600 }}>
                          {desvDia?.desvio_absoluto != null
                            ? `${desvDia.desvio_absoluto > 0 ? '+' : ''}${desvDia.desvio_absoluto.toFixed(3)}`
                            : '-'}
                        </td>
                        <td className="text-right" style={{ color: getNivelColor(desvDia?.nivel) }}>
                          {desvDia?.desvio_porcentual != null
                            ? `${desvDia.desvio_porcentual > 0 ? '+' : ''}${desvDia.desvio_porcentual.toFixed(1)}%`
                            : '-'}
                        </td>
                        <td className="text-center">
                          {desvDia ? getNivelIcon(desvDia.nivel) : '-'}
                        </td>
                      </>}
                    </tr>
                  )
                })}
              </tbody>
            </table>
          </div>
          <div style={{ marginTop: '1rem', display: 'flex', justifyContent: 'flex-end' }}>
            <button className="btn btn-primary" onClick={handleSave} disabled={saving}>
              {saving ? (
                <><span className="spinner" style={{ width: 14, height: 14, marginRight: 6 }}></span> Guardando...</>
              ) : (
                <><Save size={14} /> Guardar Pesos Reales</>
              )}
            </button>
          </div>
        </div>
      </motion.div>

      {/* Recomendación Óptima basada en Peso Objetivo */}
      {recomendacion && (
        <motion.div variants={itemVariants} className="card" style={{
          borderLeft: `4px solid ${recomendacion.peso_por_debajo ? '#ef4444' : 'var(--success)'}`,
        }}>
          <div className="card-header">
            <h2><Target size={18} style={{ verticalAlign: 'middle', marginRight: 6 }} /> Recomendación Óptima — Peso Objetivo: {recomendacion.peso_objetivo?.toFixed(2)} kg</h2>
          </div>
          <div className="card-body">
            {/* Mensaje principal */}
            <div style={{
              padding: '0.8rem 1rem',
              background: recomendacion.peso_por_debajo ? 'rgba(239, 68, 68, 0.06)' : 'rgba(34, 197, 94, 0.06)',
              border: `1px solid ${recomendacion.peso_por_debajo ? 'rgba(239, 68, 68, 0.2)' : 'rgba(34, 197, 94, 0.2)'}`,
              borderRadius: 8,
              fontSize: '0.9rem',
              marginBottom: recomendacion.peso_por_debajo ? '1rem' : 0,
              color: recomendacion.peso_por_debajo ? '#dc2626' : '#16a34a',
            }}>
              {recomendacion.recomendacion}
            </div>

            {/* Detalle por día si hay déficit */}
            {recomendacion.peso_por_debajo && recomendacion.dias_afectados.length > 0 && (
              <>
                {/* Stats rápidos */}
                <div className="stats-grid" style={{ marginBottom: '1rem' }}>
                  <div className="stat-card">
                    <div className="stat-label">Kg Déficit Total</div>
                    <div className="stat-value" style={{ color: '#ef4444' }}>{formatNumber(Math.round(recomendacion.total_kg_deficit))}</div>
                  </div>
                  <div className="stat-card">
                    <div className="stat-label">Pollos Compensación</div>
                    <div className="stat-value" style={{ color: '#f97316' }}>{formatNumber(recomendacion.total_pollos_compensacion)}</div>
                  </div>
                  <div className="stat-card">
                    <div className="stat-label">Absorción</div>
                    <div className="stat-value" style={{
                      color: recomendacion.puede_absorber_sin_extras ? '#16a34a'
                        : recomendacion.puede_absorber_con_extras ? '#f97316' : '#ef4444',
                      fontSize: '0.85rem',
                    }}>
                      {recomendacion.puede_absorber_sin_extras ? (
                        <><CheckCircle2 size={16} style={{ marginRight: 4 }} />Sin H. Extras</>
                      ) : recomendacion.puede_absorber_con_extras ? (
                        <><Zap size={16} style={{ marginRight: 4 }} />Con H. Extras</>
                      ) : (
                        <><ShoppingCart size={16} style={{ marginRight: 4 }} />Requiere Terceros</>
                      )}
                    </div>
                  </div>
                </div>

                {/* Tabla detalle */}
                <div className="table-container">
                  <table>
                    <thead>
                      <tr>
                        <th>Día</th>
                        <th className="text-right">Peso Ref.</th>
                        <th className="text-right">Objetivo</th>
                        <th className="text-right">Diferencia</th>
                        <th className="text-right">Kg Déficit</th>
                        <th className="text-right">Pollos Comp.</th>
                        <th className="text-center">Margen Normal</th>
                        <th className="text-center">Margen c/ Extras</th>
                        <th className="text-center">Estado</th>
                      </tr>
                    </thead>
                    <tbody>
                      {recomendacion.dias_afectados.map((d, idx) => (
                        <tr key={idx} style={{
                          background: d.requiere_terceros ? 'rgba(239, 68, 68, 0.04)'
                            : d.puede_sin_extras ? 'rgba(34, 197, 94, 0.04)'
                            : 'rgba(251, 146, 60, 0.04)',
                        }}>
                          <td>
                            <strong>{d.dia_nombre}</strong>
                            <span style={{ fontSize: '0.7rem', color: 'var(--text-light)', marginLeft: 4 }}>
                              ({d.fuente_peso === 'real' ? 'peso real' : 'proyectado'})
                            </span>
                          </td>
                          <td className="text-right">{d.peso_referencia?.toFixed(3)} kg</td>
                          <td className="text-right">{d.peso_objetivo?.toFixed(2)} kg</td>
                          <td className="text-right" style={{ color: '#ef4444', fontWeight: 600 }}>
                            -{d.diferencia_peso?.toFixed(3)} kg
                          </td>
                          <td className="text-right" style={{ fontWeight: 600 }}>
                            {formatNumber(Math.round(d.kg_deficit))}
                          </td>
                          <td className="text-right" style={{ fontWeight: 600 }}>
                            {formatNumber(d.pollos_compensacion)}
                          </td>
                          <td className="text-center">{formatNumber(d.margen_sin_extras)}</td>
                          <td className="text-center">{formatNumber(d.margen_con_extras)}</td>
                          <td className="text-center">
                            {d.puede_sin_extras ? (
                              <span style={{ color: '#16a34a', fontWeight: 600, fontSize: '0.8rem' }}>
                                <CheckCircle2 size={14} /> OK
                              </span>
                            ) : d.puede_con_extras ? (
                              <span style={{ color: '#f97316', fontWeight: 600, fontSize: '0.8rem' }}>
                                <Zap size={14} /> H. Extras
                              </span>
                            ) : (
                              <span style={{ color: '#ef4444', fontWeight: 600, fontSize: '0.8rem' }}>
                                <ShoppingCart size={14} /> Terceros
                              </span>
                            )}
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>

                {/* Alerta para comercial */}
                {recomendacion.alerta_comercial && (
                  <div style={{
                    marginTop: '1rem',
                    padding: '0.7rem 1rem',
                    background: 'rgba(251, 146, 60, 0.08)',
                    border: '1px solid rgba(251, 146, 60, 0.25)',
                    borderRadius: 8,
                    fontSize: '0.85rem',
                    color: '#ea580c',
                    display: 'flex',
                    alignItems: 'center',
                    gap: 8,
                  }}>
                    <TrendingDown size={16} style={{ flexShrink: 0 }} />
                    <div>
                      <strong>Alerta para Comercial: </strong>
                      {recomendacion.alerta_comercial}
                    </div>
                  </div>
                )}
              </>
            )}
          </div>
        </motion.div>
      )}
    </motion.div>
  )
}
