import React, { useState, useEffect } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import { Layers, Save, Trash2, Eye, GitCompareArrows, RotateCcw, Loader2, CheckCircle2, X, Check, FileText } from 'lucide-react'
import toast from 'react-hot-toast'
import {
  guardarEscenario, listarEscenarios, deleteEscenario,
  compararEscenarios, cargarEscenario,
} from '../services/api'

const containerVariants = {
  hidden: { opacity: 0 },
  show: { opacity: 1, transition: { staggerChildren: 0.08 } }
}
const itemVariants = {
  hidden: { opacity: 0, y: 15 },
  show: { opacity: 1, y: 0, transition: { duration: 0.3 } }
}

const DIAS_SEMANA = ['Lunes', 'Martes', 'Miércoles', 'Jueves', 'Viernes', 'Sábado']

function formatNumber(n) {
  if (n == null) return '-'
  return n.toLocaleString('es-AR')
}

function formatDateTime(iso) {
  if (!iso) return '-'
  const dt = new Date(iso)
  return dt.toLocaleDateString('es-AR', { day: 'numeric', month: 'short', year: 'numeric', hour: '2-digit', minute: '2-digit' })
}

export default function EscenariosView({ proyeccion, setProyeccion }) {
  const [escenarios, setEscenarios] = useState([])
  const [loading, setLoading] = useState(true)
  const [saving, setSaving] = useState(false)
  const [nombre, setNombre] = useState('')
  const [descripcion, setDescripcion] = useState('')
  const [selected, setSelected] = useState(new Set())
  const [comparacion, setComparacion] = useState(null)
  const [comparando, setComparando] = useState(false)

  useEffect(() => {
    cargarEscenarios()
  }, [])

  const cargarEscenarios = async () => {
    setLoading(true)
    try {
      const data = await listarEscenarios()
      setEscenarios(data)
    } catch {
      setEscenarios([])
    } finally {
      setLoading(false)
    }
  }

  const handleGuardar = async () => {
    if (!nombre.trim()) {
      toast.error('Ingrese un nombre para el escenario')
      return
    }
    setSaving(true)
    try {
      await guardarEscenario(nombre.trim(), descripcion.trim())
      toast.success(`Escenario "${nombre}" guardado`)
      setNombre('')
      setDescripcion('')
      await cargarEscenarios()
    } catch (err) {
      toast.error('Error: ' + (err.response?.data?.detail || err.message))
    } finally {
      setSaving(false)
    }
  }

  const handleEliminar = async (id, nombreEsc) => {
    if (!window.confirm(`¿Eliminar el escenario "${nombreEsc}"?`)) return
    try {
      await deleteEscenario(id)
      toast.success('Escenario eliminado')
      setSelected(prev => { const n = new Set(prev); n.delete(id); return n })
      setComparacion(null)
      await cargarEscenarios()
    } catch (err) {
      toast.error('Error: ' + (err.response?.data?.detail || err.message))
    }
  }

  const handleCargar = async (id, nombreEsc) => {
    if (!window.confirm(`¿Restaurar "${nombreEsc}" como la proyección activa? Esto reemplazará la proyección actual.`)) return
    try {
      const data = await cargarEscenario(id)
      if (data.proyeccion) setProyeccion(data.proyeccion)
      toast.success(`Escenario "${nombreEsc}" cargado`)
    } catch (err) {
      toast.error('Error: ' + (err.response?.data?.detail || err.message))
    }
  }

  const toggleSelect = (id) => {
    setSelected(prev => {
      const n = new Set(prev)
      if (n.has(id)) n.delete(id)
      else if (n.size < 3) n.add(id)
      else toast.error('Máximo 3 escenarios para comparar')
      return n
    })
    setComparacion(null)
  }

  const handleComparar = async () => {
    if (selected.size < 2) {
      toast.error('Seleccione al menos 2 escenarios')
      return
    }
    setComparando(true)
    try {
      const data = await compararEscenarios([...selected])
      setComparacion(data.escenarios)
    } catch (err) {
      toast.error('Error: ' + (err.response?.data?.detail || err.message))
    } finally {
      setComparando(false)
    }
  }

  if (loading) {
    return (
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', padding: '4rem', gap: 8 }}>
        <Loader2 size={24} style={{ animation: 'spin 1s linear infinite' }} />
        <span style={{ color: 'var(--text-light)' }}>Cargando escenarios...</span>
      </div>
    )
  }

  return (
    <motion.div variants={containerVariants} initial="hidden" animate="show">
      {/* Guardar escenario */}
      <motion.div variants={itemVariants} className="card" style={{ borderLeft: '4px solid var(--primary)' }}>
        <div className="card-header">
          <h2><Layers size={18} style={{ verticalAlign: 'middle', marginRight: 6 }} /> Guardar Escenario Actual</h2>
        </div>
        <div className="card-body">
          {!proyeccion ? (
            <p style={{ color: 'var(--text-light)', fontSize: '0.9rem' }}>
              No hay proyección generada. Genérela primero para poder guardar un escenario.
            </p>
          ) : (
            <>
              <p style={{ marginBottom: '0.75rem', fontSize: '0.85rem', color: 'var(--text-light)' }}>
                Guarde la proyección actual como escenario. Luego puede generar otra proyección con parámetros distintos y compararlas.
              </p>
              <div style={{ display: 'flex', gap: '0.75rem', flexWrap: 'wrap', alignItems: 'flex-end' }}>
                <div style={{ flex: 1, minWidth: 180 }}>
                  <label style={{ fontSize: '0.8rem', fontWeight: 600, color: 'var(--text-light)', display: 'block', marginBottom: 4 }}>
                    Nombre *
                  </label>
                  <input
                    type="text"
                    value={nombre}
                    onChange={(e) => setNombre(e.target.value)}
                    placeholder="ej: Semana sin sábado"
                    style={{
                      width: '100%', padding: '0.5rem 0.75rem',
                      border: '1px solid var(--border)', borderRadius: 6,
                      fontSize: '0.9rem',
                    }}
                  />
                </div>
                <div style={{ flex: 1, minWidth: 180 }}>
                  <label style={{ fontSize: '0.8rem', fontWeight: 600, color: 'var(--text-light)', display: 'block', marginBottom: 4 }}>
                    Descripción (opcional)
                  </label>
                  <input
                    type="text"
                    value={descripcion}
                    onChange={(e) => setDescripcion(e.target.value)}
                    placeholder="ej: Sin horas extra, tope 35k"
                    style={{
                      width: '100%', padding: '0.5rem 0.75rem',
                      border: '1px solid var(--border)', borderRadius: 6,
                      fontSize: '0.9rem',
                    }}
                  />
                </div>
                <button className="btn btn-primary" disabled={saving || !nombre.trim()} onClick={handleGuardar}
                  style={{ whiteSpace: 'nowrap' }}>
                  {saving ? (
                    <><span className="spinner" style={{ width: 14, height: 14, marginRight: 6 }}></span> Guardando...</>
                  ) : (
                    <><Save size={14} /> Guardar</>
                  )}
                </button>
              </div>
            </>
          )}
        </div>
      </motion.div>

      {/* Lista de escenarios */}
      <motion.div variants={itemVariants} className="card">
        <div className="card-header">
          <h2><FileText size={18} style={{ verticalAlign: 'middle', marginRight: 6 }} /> Escenarios Guardados ({escenarios.length})</h2>
          {selected.size >= 2 && (
            <button className="btn btn-primary" onClick={handleComparar} disabled={comparando}
              style={{ whiteSpace: 'nowrap' }}>
              {comparando ? (
                <><span className="spinner" style={{ width: 14, height: 14, marginRight: 6 }}></span> Comparando...</>
              ) : (
                <><GitCompareArrows size={14} /> Comparar ({selected.size})</>
              )}
            </button>
          )}
        </div>
        <div className="card-body">
          {escenarios.length === 0 ? (
            <p style={{ textAlign: 'center', color: 'var(--text-light)', padding: '2rem', fontSize: '0.9rem' }}>
              No hay escenarios guardados aún. Guarde la proyección actual para comenzar.
            </p>
          ) : (
            <div style={{ display: 'flex', flexDirection: 'column', gap: '0.75rem' }}>
              {escenarios.map((esc) => (
                <div
                  key={esc.id}
                  style={{
                    display: 'flex', alignItems: 'center', gap: '0.75rem',
                    padding: '0.75rem 1rem',
                    border: `2px solid ${selected.has(esc.id) ? 'var(--primary)' : 'var(--border)'}`,
                    borderRadius: 10,
                    background: selected.has(esc.id) ? 'rgba(99, 102, 241, 0.04)' : 'transparent',
                    transition: 'all 0.2s',
                    cursor: 'pointer',
                  }}
                  onClick={() => toggleSelect(esc.id)}
                >
                  <div style={{
                    width: 24, height: 24, borderRadius: 6,
                    border: `2px solid ${selected.has(esc.id) ? 'var(--primary)' : 'var(--border)'}`,
                    display: 'flex', alignItems: 'center', justifyContent: 'center',
                    background: selected.has(esc.id) ? 'var(--primary)' : 'transparent',
                    transition: 'all 0.2s', flexShrink: 0,
                  }}>
                    {selected.has(esc.id) && <Check size={14} color="white" />}
                  </div>
                  <div style={{ flex: 1, minWidth: 0 }}>
                    <div style={{ fontWeight: 600, fontSize: '0.95rem' }}>{esc.nombre}</div>
                    {esc.descripcion && (
                      <div style={{ fontSize: '0.8rem', color: 'var(--text-light)', marginTop: 2 }}>{esc.descripcion}</div>
                    )}
                    <div style={{ fontSize: '0.8rem', color: 'var(--text-light)', marginTop: 4, display: 'flex', gap: '1rem', flexWrap: 'wrap' }}>
                      <span>{formatDateTime(esc.fecha_creacion)}</span>
                      {esc.resumen && (
                        <>
                          <span>📊 {formatNumber(esc.resumen.total_pollos)} pollos</span>
                          <span>📦 {formatNumber(esc.resumen.cajas)} cajas</span>
                          <span>📅 {esc.resumen.dias} días</span>
                        </>
                      )}
                    </div>
                  </div>
                  <div style={{ display: 'flex', gap: '0.4rem', flexShrink: 0 }}
                    onClick={(e) => e.stopPropagation()}>
                    <button className="btn btn-sm btn-outline" title="Cargar como activo"
                      onClick={() => handleCargar(esc.id, esc.nombre)}>
                      <RotateCcw size={14} />
                    </button>
                    <button className="btn btn-sm btn-danger" title="Eliminar"
                      onClick={() => handleEliminar(esc.id, esc.nombre)}>
                      <Trash2 size={14} />
                    </button>
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>
      </motion.div>

      {/* Comparación */}
      <AnimatePresence>
        {comparacion && comparacion.length >= 2 && (
          <motion.div
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0, y: 20 }}
            className="card"
            style={{ borderLeft: '4px solid var(--info)' }}
          >
            <div className="card-header">
              <h2><GitCompareArrows size={18} style={{ verticalAlign: 'middle', marginRight: 6 }} /> Comparación de Escenarios</h2>
              <button className="btn btn-sm btn-outline" onClick={() => setComparacion(null)}>
                <X size={14} /> Cerrar
              </button>
            </div>
            <div className="card-body">
              {/* Resumen side-by-side */}
              <div className="table-container" style={{ overflowX: 'auto' }}>
                <table>
                  <thead>
                    <tr>
                      <th>Métrica</th>
                      {comparacion.map(esc => (
                        <th key={esc.id} className="text-right" style={{ minWidth: 140 }}>
                          <strong>{esc.nombre}</strong>
                        </th>
                      ))}
                    </tr>
                  </thead>
                  <tbody>
                    <tr>
                      <td><strong>Total Pollos</strong></td>
                      {comparacion.map(esc => (
                        <td key={esc.id} className="text-right" style={{ fontWeight: 600 }}>
                          {formatNumber(esc.resumen?.total_pollos)}
                        </td>
                      ))}
                    </tr>
                    <tr>
                      <td><strong>Cajas</strong></td>
                      {comparacion.map(esc => (
                        <td key={esc.id} className="text-right">
                          {formatNumber(esc.resumen?.cajas)}
                        </td>
                      ))}
                    </tr>
                    <tr>
                      <td><strong>Sofía</strong></td>
                      {comparacion.map(esc => (
                        <td key={esc.id} className="text-right">
                          {formatNumber(esc.resumen?.sofia)}
                        </td>
                      ))}
                    </tr>
                    <tr>
                      <td><strong>Promedio Edad</strong></td>
                      {comparacion.map(esc => (
                        <td key={esc.id} className="text-right">
                          {esc.resumen?.promedio_edad?.toFixed(1) || '-'}
                        </td>
                      ))}
                    </tr>
                    <tr>
                      <td><strong>Días de Faena</strong></td>
                      {comparacion.map(esc => (
                        <td key={esc.id} className="text-right">
                          {esc.resumen?.dias || '-'}
                        </td>
                      ))}
                    </tr>
                    <tr>
                      <td><strong>Obj. Diario Min</strong></td>
                      {comparacion.map(esc => (
                        <td key={esc.id} className="text-right">
                          {formatNumber(esc.parametros?.pollos_diarios_objetivo_min)}
                        </td>
                      ))}
                    </tr>
                    <tr>
                      <td><strong>Obj. Diario Max</strong></td>
                      {comparacion.map(esc => (
                        <td key={esc.id} className="text-right">
                          {formatNumber(esc.parametros?.pollos_diarios_objetivo_max)}
                        </td>
                      ))}
                    </tr>
                  </tbody>
                </table>
              </div>

              {/* Pollos por día */}
              <h3 style={{ margin: '1.5rem 0 0.75rem', fontSize: '0.95rem', fontWeight: 600 }}>
                Distribución Diaria
              </h3>
              <div className="table-container" style={{ overflowX: 'auto' }}>
                <table>
                  <thead>
                    <tr>
                      <th>Día</th>
                      {comparacion.map(esc => (
                        <th key={esc.id} className="text-right">{esc.nombre}</th>
                      ))}
                    </tr>
                  </thead>
                  <tbody>
                    {(() => {
                      // Determinar la cantidad máxima de días entre los escenarios
                      const maxDias = Math.max(...comparacion.map(e => e.resumen?.pollos_por_dia?.length || 0))
                      const rows = []
                      for (let i = 0; i < maxDias; i++) {
                        rows.push(
                          <tr key={i}>
                            <td><strong>{DIAS_SEMANA[i] || `Día ${i + 1}`}</strong></td>
                            {comparacion.map(esc => {
                              const ppd = esc.resumen?.pollos_por_dia?.[i]
                              const total = ppd?.total || 0
                              const excede = total > (esc.parametros?.pollos_diarios_objetivo_max || 42000)
                              return (
                                <td key={esc.id} className="text-right"
                                  style={{
                                    fontWeight: 600,
                                    color: excede ? '#ef4444' : undefined,
                                    background: excede ? 'rgba(239, 68, 68, 0.05)' : undefined,
                                  }}>
                                  {total > 0 ? formatNumber(total) : '-'}
                                  {excede && ' ⚠'}
                                </td>
                              )
                            })}
                          </tr>
                        )
                      }
                      return rows
                    })()}
                    <tr className="row-subtotal">
                      <td><strong>TOTAL</strong></td>
                      {comparacion.map(esc => (
                        <td key={esc.id} className="text-right">
                          <strong>{formatNumber(esc.resumen?.total_pollos)}</strong>
                        </td>
                      ))}
                    </tr>
                  </tbody>
                </table>
              </div>
            </div>
          </motion.div>
        )}
      </AnimatePresence>
    </motion.div>
  )
}
