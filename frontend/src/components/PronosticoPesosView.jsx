import React, { useState, useEffect } from 'react'
import { motion } from 'framer-motion'
import {
  Activity, AlertTriangle, CheckCircle2, Loader2, TrendingDown,
  TrendingUp, Target, Filter, ChevronDown, ChevronUp, ShieldAlert, Clock
} from 'lucide-react'
import toast from 'react-hot-toast'
import { getPronosticoPesos, getAlertaTemprana } from '../services/api'

const containerVariants = {
  hidden: { opacity: 0 },
  show: { opacity: 1, transition: { staggerChildren: 0.08 } }
}
const itemVariants = {
  hidden: { opacity: 0, y: 15 },
  show: { opacity: 1, y: 0, transition: { duration: 0.3 } }
}

const DIAS_SEMANA = ['Lunes', 'Martes', 'Miércoles', 'Jueves', 'Viernes', 'Sábado']

function getDiaNombre(fechaStr) {
  if (!fechaStr) return '-'
  const dt = new Date(fechaStr + 'T12:00:00')
  const idx = dt.getDay() === 0 ? 6 : dt.getDay() - 1
  return DIAS_SEMANA[idx] || '-'
}

function formatNumber(n) {
  if (n == null) return '-'
  return n.toLocaleString('es-AR')
}

function getNivelColor(nivel) {
  switch (nivel) {
    case 'normal': return 'var(--success, #22c55e)'
    case 'moderado': return 'var(--warning, #fb923c)'
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

function getNivelIcon(nivel, size = 16) {
  switch (nivel) {
    case 'normal': return <CheckCircle2 size={size} color="var(--success, #22c55e)" />
    case 'moderado': return <AlertTriangle size={size} color="var(--warning, #fb923c)" />
    case 'critico': return <AlertTriangle size={size} color="#ef4444" />
    default: return <Target size={size} color="var(--text-light)" />
  }
}

function getNivelLabel(nivel) {
  switch (nivel) {
    case 'normal': return 'Normal'
    case 'moderado': return 'Moderado'
    case 'critico': return 'Crítico'
    default: return '-'
  }
}

function PesoBar({ peso, min, max, objetivo }) {
  // Barra visual del rango de peso
  const rangoTotal = max - min
  const margen = rangoTotal * 0.5 // extensión visual fuera del rango
  const barMin = min - margen
  const barMax = max + margen
  const barRango = barMax - barMin

  const pesoPos = Math.max(0, Math.min(100, ((peso - barMin) / barRango) * 100))
  const objPos = ((objetivo - barMin) / barRango) * 100
  const zonaOkStart = ((min - barMin) / barRango) * 100
  const zonaOkEnd = ((max - barMin) / barRango) * 100

  let dotColor = '#22c55e'
  if (peso < min || peso > max) dotColor = '#ef4444'
  else if (peso < min + 0.05 || peso > max - 0.05) dotColor = '#fb923c'

  return (
    <div style={{ position: 'relative', height: 20, width: '100%', minWidth: 120 }}>
      {/* Fondo gris */}
      <div style={{
        position: 'absolute', top: 8, left: 0, right: 0, height: 4,
        background: 'var(--border, #e5e7eb)', borderRadius: 2,
      }} />
      {/* Zona verde (rango ideal) */}
      <div style={{
        position: 'absolute', top: 6, height: 8, borderRadius: 4,
        left: `${zonaOkStart}%`, width: `${zonaOkEnd - zonaOkStart}%`,
        background: 'rgba(34, 197, 94, 0.25)',
      }} />
      {/* Línea objetivo */}
      <div style={{
        position: 'absolute', top: 4, height: 12, width: 1,
        left: `${objPos}%`, background: 'var(--text-light, #9ca3af)',
      }} />
      {/* Punto del peso */}
      <div style={{
        position: 'absolute', top: 4, width: 12, height: 12, borderRadius: '50%',
        left: `calc(${pesoPos}% - 6px)`, background: dotColor,
        border: '2px solid white', boxShadow: '0 1px 3px rgba(0,0,0,0.3)',
      }} />
    </div>
  )
}

export default function PronosticoPesosView({ proyeccion }) {
  const [data, setData] = useState(null)
  const [loading, setLoading] = useState(true)
  const [filtroNivel, setFiltroNivel] = useState('todos') // todos | critico | moderado | normal
  const [filtroDia, setFiltroDia] = useState('todos')
  const [vistaActiva, setVistaActiva] = useState('lotes') // lotes | dias | granjas
  const [expandedGranjas, setExpandedGranjas] = useState({})
  const [alertaData, setAlertaData] = useState(null)
  const [alertaLoading, setAlertaLoading] = useState(false)
  const [alertaFiltroNivel, setAlertaFiltroNivel] = useState('todos')
  const [alertaExpandedGranjas, setAlertaExpandedGranjas] = useState({})
  const [alertaExpandedGalpones, setAlertaExpandedGalpones] = useState({})

  useEffect(() => {
    cargarPronostico()
    cargarAlertaTemprana()
  }, [proyeccion])

  const cargarPronostico = async () => {
    setLoading(true)
    try {
      const result = await getPronosticoPesos()
      setData(result)
    } catch (err) {
      if (err.response?.status === 404) {
        setData(null)
      } else {
        toast.error('Error cargando pronóstico: ' + (err.response?.data?.detail || err.message))
      }
    } finally {
      setLoading(false)
    }
  }

  const cargarAlertaTemprana = async () => {
    setAlertaLoading(true)
    try {
      const result = await getAlertaTemprana()
      setAlertaData(result)
    } catch (err) {
      if (err.response?.status === 404) {
        setAlertaData(null)
      }
    } finally {
      setAlertaLoading(false)
    }
  }

  if (!proyeccion || !proyeccion.dias) {
    return (
      <motion.div initial={{ opacity: 0, scale: 0.95 }} animate={{ opacity: 1, scale: 1 }} className="card">
        <div className="card-body" style={{ textAlign: 'center', padding: '3rem' }}>
          <p style={{ fontSize: '1.1rem', color: 'var(--text-light)', display: 'flex', alignItems: 'center', justifyContent: 'center', gap: 6 }}>
            <Activity size={20} /> No hay planificación generada. Genérela primero para ver el pronóstico de pesos.
          </p>
        </div>
      </motion.div>
    )
  }

  if (loading) {
    return (
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', padding: '4rem', gap: 8 }}>
        <Loader2 size={24} style={{ animation: 'spin 1s linear infinite' }} />
        <span style={{ color: 'var(--text-light)' }}>Cargando pronóstico de pesos...</span>
      </div>
    )
  }

  if (!data) {
    return (
      <motion.div initial={{ opacity: 0, scale: 0.95 }} animate={{ opacity: 1, scale: 1 }} className="card">
        <div className="card-body" style={{ textAlign: 'center', padding: '3rem' }}>
          <p style={{ fontSize: '1.1rem', color: 'var(--text-light)' }}>
            No se pudo generar el pronóstico. Verifique que exista una planificación y ofertas cargadas.
          </p>
        </div>
      </motion.div>
    )
  }

  // Filtrar lotes
  const lotesFiltrados = data.lotes.filter(l => {
    if (filtroNivel !== 'todos' && l.nivel !== filtroNivel) return false
    if (filtroDia !== 'todos' && l.dia_index !== parseInt(filtroDia)) return false
    return true
  })

  const toggleGranja = (granja) => {
    setExpandedGranjas(prev => ({ ...prev, [granja]: !prev[granja] }))
  }

  const toggleAlertaGranja = (granja) => {
    setAlertaExpandedGranjas(prev => ({ ...prev, [granja]: !prev[granja] }))
  }

  const toggleAlertaGalpon = (key) => {
    setAlertaExpandedGalpones(prev => ({ ...prev, [key]: !prev[key] }))
  }

  return (
    <motion.div variants={containerVariants} initial="hidden" animate="show">
      {/* Alerta global */}
      {data.alertas_criticas > 0 && (
        <motion.div variants={itemVariants} style={{
          padding: '1rem 1.2rem',
          background: 'rgba(239, 68, 68, 0.08)',
          border: '1px solid #ef4444',
          borderRadius: 10,
          display: 'flex', alignItems: 'flex-start', gap: 10,
          fontSize: '0.9rem',
          color: '#ef4444',
          fontWeight: 500,
          marginBottom: '0.75rem',
        }}>
          <AlertTriangle size={22} style={{ flexShrink: 0, marginTop: 1 }} />
          <div>
            <div style={{ fontWeight: 600, marginBottom: 2 }}>Atención: Lotes fuera de peso ideal</div>
            <div style={{ fontWeight: 400 }}>
              {data.alertas_criticas} lote{data.alertas_criticas !== 1 ? 's' : ''} con alerta crítica
              {data.alertas_moderadas > 0 && ` y ${data.alertas_moderadas} con alerta moderada`}.
              Estos lotes no llegarían al peso ideal para faena.
            </div>
          </div>
        </motion.div>
      )}

      {data.alertas_criticas === 0 && data.alertas_moderadas > 0 && (
        <motion.div variants={itemVariants} style={{
          padding: '1rem 1.2rem',
          background: 'rgba(251, 146, 60, 0.08)',
          border: '1px solid var(--warning, #fb923c)',
          borderRadius: 10,
          display: 'flex', alignItems: 'flex-start', gap: 10,
          fontSize: '0.9rem',
          color: 'var(--warning, #fb923c)',
          fontWeight: 500,
          marginBottom: '0.75rem',
        }}>
          <AlertTriangle size={22} style={{ flexShrink: 0, marginTop: 1 }} />
          <div>
            <div style={{ fontWeight: 600, marginBottom: 2 }}>Advertencia</div>
            <div style={{ fontWeight: 400 }}>
              {data.alertas_moderadas} lote{data.alertas_moderadas !== 1 ? 's' : ''} con peso al límite del rango aceptable.
            </div>
          </div>
        </motion.div>
      )}

      {data.alertas_criticas === 0 && data.alertas_moderadas === 0 && (
        <motion.div variants={itemVariants} style={{
          padding: '1rem 1.2rem',
          background: 'rgba(34, 197, 94, 0.08)',
          border: '1px solid var(--success, #22c55e)',
          borderRadius: 10,
          display: 'flex', alignItems: 'flex-start', gap: 10,
          fontSize: '0.9rem',
          color: 'var(--success, #22c55e)',
          fontWeight: 500,
          marginBottom: '0.75rem',
        }}>
          <CheckCircle2 size={22} style={{ flexShrink: 0, marginTop: 1 }} />
          <div>
            <div style={{ fontWeight: 600 }}>Todos los lotes dentro del rango ideal de peso</div>
          </div>
        </motion.div>
      )}

      {/* Stats */}
      <motion.div variants={itemVariants} className="stats-grid" style={{ marginBottom: '0.75rem' }}>
        <div className="stat-card">
          <div className="stat-label">Total Lotes</div>
          <div className="stat-value blue">{data.total_lotes}</div>
        </div>
        <div className="stat-card">
          <div className="stat-label">En Rango</div>
          <div className="stat-value" style={{ color: 'var(--success, #22c55e)' }}>
            {data.lotes_ok} <span style={{ fontSize: '0.75rem', fontWeight: 400 }}>({data.pct_ok}%)</span>
          </div>
        </div>
        <div className="stat-card">
          <div className="stat-label">Alerta Moderada</div>
          <div className="stat-value" style={{ color: 'var(--warning, #fb923c)' }}>
            {data.alertas_moderadas}
          </div>
        </div>
        <div className="stat-card">
          <div className="stat-label">Alerta Crítica</div>
          <div className="stat-value" style={{ color: '#ef4444' }}>
            {data.alertas_criticas}
          </div>
        </div>
      </motion.div>

      {/* Tabs de vista */}
      <motion.div variants={itemVariants} style={{
        display: 'flex', gap: '0.5rem', marginBottom: '0.75rem',
      }}>
        {[
          { id: 'alerta', label: '⚠ Alerta Temprana' },
          { id: 'lotes', label: 'Por Lote' },
          { id: 'dias', label: 'Por Día' },
          { id: 'granjas', label: 'Por Granja' },
        ].map(v => (
          <button
            key={v.id}
            onClick={() => setVistaActiva(v.id)}
            className={`btn btn-sm ${vistaActiva === v.id ? '' : 'btn-outline'}`}
            style={{
              background: vistaActiva === v.id ? 'var(--primary, #6366f1)' : 'transparent',
              color: vistaActiva === v.id ? 'white' : 'var(--text)',
              border: vistaActiva === v.id ? 'none' : '1px solid var(--border)',
              padding: '0.4rem 1rem',
              borderRadius: 6,
              fontSize: '0.85rem',
              cursor: 'pointer',
            }}
          >
            {v.label}
          </button>
        ))}
      </motion.div>

      {/* ─── Vista: Alerta Temprana ─── */}
      {vistaActiva === 'alerta' && (
        <motion.div variants={itemVariants}>
          {alertaLoading ? (
            <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', padding: '3rem', gap: 8 }}>
              <Loader2 size={24} style={{ animation: 'spin 1s linear infinite' }} />
              <span style={{ color: 'var(--text-light)' }}>Analizando lotes...</span>
            </div>
          ) : !alertaData ? (
            <div className="card">
              <div className="card-body" style={{ textAlign: 'center', padding: '3rem' }}>
                <p style={{ color: 'var(--text-light)' }}>
                  <ShieldAlert size={20} style={{ verticalAlign: 'middle', marginRight: 6 }} />
                  No hay ofertas cargadas para analizar. Cargue una oferta primero.
                </p>
              </div>
            </div>
          ) : (
            <>
              {/* Advertencia de datos antiguos */}
              {alertaData.dias_antiguedad > 2 && (
                <div style={{
                  padding: '0.85rem 1.2rem',
                  background: 'rgba(59, 130, 246, 0.08)',
                  border: '1px solid #3b82f6',
                  borderRadius: 10,
                  display: 'flex', alignItems: 'flex-start', gap: 10,
                  fontSize: '0.85rem', color: '#3b82f6', fontWeight: 500,
                  marginBottom: '0.75rem',
                }}>
                  <Clock size={20} style={{ flexShrink: 0, marginTop: 1 }} />
                  <div>
                    <div style={{ fontWeight: 600, marginBottom: 2 }}>Datos con {alertaData.dias_antiguedad} días de antigüedad</div>
                    <div style={{ fontWeight: 400 }}>
                      Oferta del {new Date(alertaData.fecha_oferta + 'T12:00:00').toLocaleDateString('es-AR')}.
                      Las edades y planificaciones se calculan a la fecha de hoy ({new Date(alertaData.fecha_referencia + 'T12:00:00').toLocaleDateString('es-AR')}).
                      Se recomienda cargar una oferta actualizada para mayor precisión.
                    </div>
                  </div>
                </div>
              )}

              {/* Alerta global temprana */}
              {alertaData.alertas_rojas > 0 && (
                <div style={{
                  padding: '1rem 1.2rem',
                  background: 'rgba(239, 68, 68, 0.08)',
                  border: '1px solid #ef4444',
                  borderRadius: 10,
                  display: 'flex', alignItems: 'flex-start', gap: 10,
                  fontSize: '0.9rem', color: '#ef4444', fontWeight: 500,
                  marginBottom: '0.75rem',
                }}>
                  <ShieldAlert size={22} style={{ flexShrink: 0, marginTop: 1 }} />
                  <div>
                    <div style={{ fontWeight: 600, marginBottom: 2 }}>Alerta Temprana: Lotes en riesgo</div>
                    <div style={{ fontWeight: 400 }}>
                      {alertaData.alertas_rojas} lote{alertaData.alertas_rojas !== 1 ? 's' : ''} con riesgo alto de no alcanzar el peso mínimo
                      {alertaData.alertas_amarillas > 0 && ` y ${alertaData.alertas_amarillas} con riesgo moderado`}.
                      Se recomienda acción correctiva.
                    </div>
                  </div>
                </div>
              )}

              {alertaData.alertas_rojas === 0 && alertaData.alertas_amarillas > 0 && (
                <div style={{
                  padding: '1rem 1.2rem',
                  background: 'rgba(251, 146, 60, 0.08)',
                  border: '1px solid var(--warning, #fb923c)',
                  borderRadius: 10,
                  display: 'flex', alignItems: 'flex-start', gap: 10,
                  fontSize: '0.9rem', color: 'var(--warning, #fb923c)', fontWeight: 500,
                  marginBottom: '0.75rem',
                }}>
                  <AlertTriangle size={22} style={{ flexShrink: 0, marginTop: 1 }} />
                  <div>
                    <div style={{ fontWeight: 600, marginBottom: 2 }}>Lotes a monitorear</div>
                    <div style={{ fontWeight: 400 }}>
                      {alertaData.alertas_amarillas} lote{alertaData.alertas_amarillas !== 1 ? 's' : ''} con peso ajustado que requieren seguimiento.
                    </div>
                  </div>
                </div>
              )}

              {alertaData.alertas_rojas === 0 && alertaData.alertas_amarillas === 0 && (
                <div style={{
                  padding: '1rem 1.2rem',
                  background: 'rgba(34, 197, 94, 0.08)',
                  border: '1px solid var(--success, #22c55e)',
                  borderRadius: 10,
                  display: 'flex', alignItems: 'flex-start', gap: 10,
                  fontSize: '0.9rem', color: 'var(--success, #22c55e)', fontWeight: 500,
                  marginBottom: '0.75rem',
                }}>
                  <CheckCircle2 size={22} style={{ flexShrink: 0, marginTop: 1 }} />
                  <div>
                    <div style={{ fontWeight: 600 }}>Todos los lotes proyectan peso dentro de rango</div>
                  </div>
                </div>
              )}

              {/* Stats alerta temprana */}
              <div className="stats-grid" style={{ marginBottom: '0.75rem' }}>
                <div className="stat-card">
                  <div className="stat-label">Total Lotes</div>
                  <div className="stat-value blue">{alertaData.total_lotes}</div>
                </div>
                <div className="stat-card">
                  <div className="stat-label">Planificación OK</div>
                  <div className="stat-value" style={{ color: 'var(--success, #22c55e)' }}>
                    {alertaData.lotes_ok} <span style={{ fontSize: '0.75rem', fontWeight: 400 }}>({alertaData.pct_ok}%)</span>
                  </div>
                </div>
                <div className="stat-card">
                  <div className="stat-label">Riesgo Moderado</div>
                  <div className="stat-value" style={{ color: 'var(--warning, #fb923c)' }}>
                    {alertaData.alertas_amarillas}
                  </div>
                </div>
                <div className="stat-card">
                  <div className="stat-label">Riesgo Alto</div>
                  <div className="stat-value" style={{ color: '#ef4444' }}>
                    {alertaData.alertas_rojas}
                  </div>
                </div>
              </div>

              {/* Tabla de lotes alerta temprana */}
              <div className="card" style={{ borderLeft: '4px solid var(--warning, #fb923c)', marginBottom: '0.75rem' }}>
                <div className="card-header" style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', flexWrap: 'wrap', gap: '0.5rem' }}>
                  <h2><ShieldAlert size={18} style={{ verticalAlign: 'middle', marginRight: 6 }} /> Planificación Anticipada por Lote</h2>
                  <div style={{ display: 'flex', gap: '0.5rem', alignItems: 'center' }}>
                    <Filter size={14} color="var(--text-light)" />
                    <select
                      value={alertaFiltroNivel}
                      onChange={e => setAlertaFiltroNivel(e.target.value)}
                      style={{
                        padding: '0.3rem 0.5rem', border: '1px solid var(--border)',
                        borderRadius: 6, fontSize: '0.8rem', background: 'var(--bg, white)',
                        color: 'var(--text)',
                      }}
                    >
                      <option value="todos">Todos los niveles</option>
                      <option value="rojo">Solo Riesgo Alto</option>
                      <option value="amarillo">Solo Riesgo Moderado</option>
                      <option value="verde">Solo OK</option>
                    </select>
                  </div>
                </div>
                <div className="card-body">
                  <div className="table-container">
                    <table>
                      <thead>
                        <tr>
                          <th>Granja</th>
                          <th className="text-center">G/N</th>
                          <th className="text-center">Sexo</th>
                          <th className="text-right">Aves</th>
                          <th className="text-right">Edad Actual</th>
                          <th className="text-right">Peso Actual</th>
                          <th className="text-right">Peso a Edad Ideal</th>
                          <th style={{ minWidth: 130 }}>Rango</th>
                          <th className="text-right">Gan. Actual</th>
                          <th className="text-right">Gan. Necesaria</th>
                          <th className="text-center">Días Rest.</th>
                          <th className="text-center">Estado</th>
                          <th>Detalle</th>
                        </tr>
                      </thead>
                      <tbody>
                        {(() => {
                          const filtrados = alertaData.lotes.filter(l =>
                            alertaFiltroNivel === 'todos' || l.nivel === alertaFiltroNivel
                          )
                          if (filtrados.length === 0) return (
                            <tr><td colSpan={13} style={{ textAlign: 'center', padding: '2rem', color: 'var(--text-light)' }}>
                              No hay lotes con el filtro seleccionado
                            </td></tr>
                          )
                          return filtrados.map((lote, idx) => {
                            const nivelColor = lote.nivel === 'verde' ? 'var(--success, #22c55e)'
                              : lote.nivel === 'amarillo' ? 'var(--warning, #fb923c)' : '#ef4444'
                            const nivelBg = lote.nivel === 'verde' ? 'rgba(34, 197, 94, 0.08)'
                              : lote.nivel === 'amarillo' ? 'rgba(251, 146, 60, 0.08)'
                              : lote.nivel === 'rojo' ? 'rgba(239, 68, 68, 0.08)' : 'transparent'
                            const nivelIconEl = lote.nivel === 'verde'
                              ? <CheckCircle2 size={16} color="var(--success, #22c55e)" />
                              : lote.nivel === 'amarillo'
                              ? <AlertTriangle size={16} color="var(--warning, #fb923c)" />
                              : <ShieldAlert size={16} color="#ef4444" />
                            return (
                              <tr key={idx} style={{ background: nivelBg }}>
                                <td>{lote.granja}</td>
                                <td className="text-center">{lote.galpon}/{lote.nucleo}</td>
                                <td className="text-center">{lote.sexo || '-'}</td>
                                <td className="text-right">{formatNumber(lote.cantidad)}</td>
                                <td className="text-right">{lote.edad_actual}d</td>
                                <td className="text-right">{lote.peso_actual?.toFixed(3)} kg</td>
                                <td className="text-right" style={{ fontWeight: 600, color: nivelColor }}>
                                  {lote.peso_en_edad_ideal?.toFixed(3)} kg
                                </td>
                                <td>
                                  <PesoBar
                                    peso={lote.peso_en_edad_ideal}
                                    min={lote.peso_min_faena}
                                    max={lote.peso_max_faena}
                                    objetivo={2.85}
                                  />
                                </td>
                                <td className="text-right" style={{
                                  color: lote.ganancia_deficiente ? '#ef4444' : 'inherit',
                                  fontWeight: lote.ganancia_deficiente ? 600 : 400,
                                }}>
                                  {lote.ganancia_diaria_lote?.toFixed(3)}
                                  {lote.ganancia_deficiente && (
                                    <TrendingDown size={12} style={{ marginLeft: 3, verticalAlign: 'middle' }} />
                                  )}
                                </td>
                                <td className="text-right" style={{
                                  fontWeight: 600,
                                  color: lote.ganancia_necesaria > lote.ganancia_diaria_lote * 1.1
                                    ? '#ef4444' : 'var(--success, #22c55e)',
                                }}>
                                  {lote.ganancia_necesaria?.toFixed(3)}
                                </td>
                                <td className="text-center">
                                  <span style={{
                                    display: 'inline-flex', alignItems: 'center', gap: 3,
                                    padding: '2px 8px', borderRadius: 12,
                                    background: lote.dias_restantes <= 3 ? 'rgba(239, 68, 68, 0.1)' :
                                      lote.dias_restantes <= 7 ? 'rgba(251, 146, 60, 0.1)' : 'rgba(34, 197, 94, 0.1)',
                                    fontSize: '0.8rem', fontWeight: 600,
                                    color: lote.dias_restantes <= 3 ? '#ef4444' :
                                      lote.dias_restantes <= 7 ? 'var(--warning, #fb923c)' : 'var(--success, #22c55e)',
                                  }}>
                                    <Clock size={11} />
                                    {lote.dias_restantes}d
                                  </span>
                                </td>
                                <td className="text-center">{nivelIconEl}</td>
                                <td style={{ fontSize: '0.8rem', color: nivelColor, maxWidth: 220 }}>
                                  {lote.mensaje}
                                </td>
                              </tr>
                            )
                          })
                        })()}
                      </tbody>
                    </table>
                  </div>
                  {alertaData.lotes.length > 0 && (
                    <div style={{ marginTop: '0.75rem', fontSize: '0.8rem', color: 'var(--text-light)' }}>
                      Mostrando {alertaData.lotes.filter(l => alertaFiltroNivel === 'todos' || l.nivel === alertaFiltroNivel).length} de {alertaData.total_lotes} lotes.
                      Rango ideal: {alertaData.peso_min_faena}–{alertaData.peso_max_faena} kg.
                      Ventana faena: {alertaData.edad_min_faena}–{alertaData.edad_max_faena} días.
                    </div>
                  )}
                </div>
              </div>

              {/* Resumen por granja - alerta temprana */}
              <div className="card" style={{ borderLeft: '4px solid var(--warning, #fb923c)' }}>
                <div className="card-header">
                  <h2><ShieldAlert size={18} style={{ verticalAlign: 'middle', marginRight: 6 }} /> Resumen por Granja</h2>
                </div>
                <div className="card-body">
                  <div className="table-container">
                    <table>
                      <thead>
                        <tr>
                          <th>Granja</th>
                          <th className="text-right">Lotes</th>
                          <th className="text-right">Aves</th>
                          <th className="text-right">Peso Prom. Ideal</th>
                          <th className="text-center" style={{ color: 'var(--success, #22c55e)' }}>OK</th>
                          <th className="text-center" style={{ color: 'var(--warning, #fb923c)' }}>Moderado</th>
                          <th className="text-center" style={{ color: '#ef4444' }}>Alto</th>
                          <th className="text-center">Estado</th>
                          <th></th>
                        </tr>
                      </thead>
                      <tbody>
                        {alertaData.granjas.map((g, idx) => {
                          const isExp = alertaExpandedGranjas[g.granja]
                          const lotesGranja = alertaData.lotes.filter(l => l.granja === g.granja)
                          const gnColor = g.nivel === 'verde' ? 'var(--success, #22c55e)'
                            : g.nivel === 'amarillo' ? 'var(--warning, #fb923c)' : '#ef4444'
                          const gnBg = g.nivel === 'verde' ? 'rgba(34, 197, 94, 0.08)'
                            : g.nivel === 'amarillo' ? 'rgba(251, 146, 60, 0.08)'
                            : g.nivel === 'rojo' ? 'rgba(239, 68, 68, 0.08)' : 'transparent'
                          const gnIcon = g.nivel === 'verde'
                            ? <CheckCircle2 size={16} color="var(--success, #22c55e)" />
                            : g.nivel === 'amarillo'
                            ? <AlertTriangle size={16} color="var(--warning, #fb923c)" />
                            : <ShieldAlert size={16} color="#ef4444" />
                          return (
                            <React.Fragment key={idx}>
                              <tr
                                style={{ background: gnBg, cursor: 'pointer' }}
                                onClick={() => toggleAlertaGranja(g.granja)}
                              >
                                <td><strong>{g.granja}</strong></td>
                                <td className="text-right">{g.total_lotes}</td>
                                <td className="text-right">{formatNumber(g.pollos_total)}</td>
                                <td className="text-right" style={{ fontWeight: 600 }}>{g.peso_promedio_ideal?.toFixed(3)} kg</td>
                                <td className="text-center" style={{ color: 'var(--success, #22c55e)', fontWeight: 600 }}>{g.lotes_verde}</td>
                                <td className="text-center" style={{ color: 'var(--warning, #fb923c)', fontWeight: 600 }}>{g.lotes_amarillo}</td>
                                <td className="text-center" style={{ color: '#ef4444', fontWeight: 600 }}>{g.lotes_rojo}</td>
                                <td className="text-center">{gnIcon}</td>
                                <td className="text-center">
                                  {isExp ? <ChevronUp size={14} /> : <ChevronDown size={14} />}
                                </td>
                              </tr>
                              {isExp && lotesGranja.map((lote, lidx) => {
                                const lnColor = lote.nivel === 'verde' ? 'var(--success, #22c55e)'
                                  : lote.nivel === 'amarillo' ? 'var(--warning, #fb923c)' : '#ef4444'
                                const lnIcon = lote.nivel === 'verde'
                                  ? <CheckCircle2 size={14} color="var(--success, #22c55e)" />
                                  : lote.nivel === 'amarillo'
                                  ? <AlertTriangle size={14} color="var(--warning, #fb923c)" />
                                  : <ShieldAlert size={14} color="#ef4444" />
                                return (
                                  <tr key={`${idx}-${lidx}`} style={{
                                    background: lote.nivel === 'verde' ? 'rgba(34, 197, 94, 0.04)'
                                      : lote.nivel === 'amarillo' ? 'rgba(251, 146, 60, 0.04)'
                                      : 'rgba(239, 68, 68, 0.04)',
                                    fontSize: '0.85rem',
                                  }}>
                                    <td style={{ paddingLeft: '2rem', color: 'var(--text-light)' }}>
                                      G{lote.galpon}/N{lote.nucleo}
                                    </td>
                                    <td className="text-right" style={{ color: 'var(--text-light)' }}>{lote.sexo || '-'}</td>
                                    <td className="text-right">{formatNumber(lote.cantidad)}</td>
                                    <td className="text-right" style={{ fontWeight: 600, color: lnColor }}>
                                      {lote.peso_en_edad_ideal?.toFixed(3)} kg
                                    </td>
                                    <td colSpan={3} style={{ fontSize: '0.8rem', color: lnColor }}>
                                      {lote.mensaje}
                                    </td>
                                    <td className="text-center">{lnIcon}</td>
                                    <td>
                                      <span style={{ fontSize: '0.75rem', color: 'var(--text-light)' }}>
                                        {lote.dias_restantes}d rest.
                                      </span>
                                    </td>
                                  </tr>
                                )
                              })}
                            </React.Fragment>
                          )
                        })}
                      </tbody>
                    </table>
                  </div>
                </div>
              </div>

              {/* Resumen por galpón / núcleo */}
              <div className="card" style={{ borderLeft: '4px solid #f97316', marginTop: '0.75rem' }}>
                <div className="card-header">
                  <h2><ShieldAlert size={18} style={{ verticalAlign: 'middle', marginRight: 6 }} /> Resumen por Galpón / Núcleo</h2>
                </div>
                <div className="card-body">
                  <div className="table-container">
                    <table>
                      <thead>
                        <tr>
                          <th>Granja</th>
                          <th className="text-center">G/N</th>
                          <th className="text-right">Lotes</th>
                          <th className="text-right">Aves</th>
                          <th className="text-right">% Riesgo Alto</th>
                          <th className="text-right">% En Alerta</th>
                          <th className="text-right">Peso Prom. Ideal</th>
                          <th className="text-center" style={{ color: 'var(--success, #22c55e)' }}>OK</th>
                          <th className="text-center" style={{ color: 'var(--warning, #fb923c)' }}>Moderado</th>
                          <th className="text-center" style={{ color: '#ef4444' }}>Alto</th>
                          <th className="text-center">Estado</th>
                          <th></th>
                        </tr>
                      </thead>
                      <tbody>
                        {(alertaData.galpones_nucleos || []).map((gn, idx) => {
                          const rowKey = `${gn.granja}-${gn.galpon}-${gn.nucleo}`
                          const isExp = alertaExpandedGalpones[rowKey]
                          const lotesGN = alertaData.lotes.filter(
                            l => l.granja === gn.granja && l.galpon === gn.galpon && l.nucleo === gn.nucleo
                          )
                          const gnColor = gn.nivel === 'verde' ? 'var(--success, #22c55e)'
                            : gn.nivel === 'amarillo' ? 'var(--warning, #fb923c)' : '#ef4444'
                          const gnBg = gn.nivel === 'verde' ? 'rgba(34, 197, 94, 0.08)'
                            : gn.nivel === 'amarillo' ? 'rgba(251, 146, 60, 0.08)'
                            : 'rgba(239, 68, 68, 0.08)'
                          const gnIcon = gn.nivel === 'verde'
                            ? <CheckCircle2 size={16} color="var(--success, #22c55e)" />
                            : gn.nivel === 'amarillo'
                            ? <AlertTriangle size={16} color="var(--warning, #fb923c)" />
                            : <ShieldAlert size={16} color="#ef4444" />

                          return (
                            <React.Fragment key={rowKey || idx}>
                              <tr
                                style={{ background: gnBg, cursor: 'pointer' }}
                                onClick={() => toggleAlertaGalpon(rowKey)}
                              >
                                <td><strong>{gn.granja}</strong></td>
                                <td className="text-center">{gn.galpon}/{gn.nucleo}</td>
                                <td className="text-right">{gn.total_lotes}</td>
                                <td className="text-right">{formatNumber(gn.pollos_total)}</td>
                                <td className="text-right" style={{ color: '#ef4444', fontWeight: 600 }}>{gn.pct_pollos_rojo}%</td>
                                <td className="text-right" style={{ color: gnColor, fontWeight: 600 }}>{gn.pct_pollos_alerta}%</td>
                                <td className="text-right" style={{ fontWeight: 600 }}>{gn.peso_promedio_ideal?.toFixed(3)} kg</td>
                                <td className="text-center" style={{ color: 'var(--success, #22c55e)', fontWeight: 600 }}>{gn.lotes_verde}</td>
                                <td className="text-center" style={{ color: 'var(--warning, #fb923c)', fontWeight: 600 }}>{gn.lotes_amarillo}</td>
                                <td className="text-center" style={{ color: '#ef4444', fontWeight: 600 }}>{gn.lotes_rojo}</td>
                                <td className="text-center">{gnIcon}</td>
                                <td className="text-center">
                                  {isExp ? <ChevronUp size={14} /> : <ChevronDown size={14} />}
                                </td>
                              </tr>
                              {isExp && lotesGN.map((lote, lidx) => {
                                const lnColor = lote.nivel === 'verde' ? 'var(--success, #22c55e)'
                                  : lote.nivel === 'amarillo' ? 'var(--warning, #fb923c)' : '#ef4444'
                                const lnIcon = lote.nivel === 'verde'
                                  ? <CheckCircle2 size={14} color="var(--success, #22c55e)" />
                                  : lote.nivel === 'amarillo'
                                  ? <AlertTriangle size={14} color="var(--warning, #fb923c)" />
                                  : <ShieldAlert size={14} color="#ef4444" />
                                return (
                                  <tr key={`${rowKey}-${lidx}`} style={{
                                    background: lote.nivel === 'verde' ? 'rgba(34, 197, 94, 0.04)'
                                      : lote.nivel === 'amarillo' ? 'rgba(251, 146, 60, 0.04)'
                                      : 'rgba(239, 68, 68, 0.04)',
                                    fontSize: '0.85rem',
                                  }}>
                                    <td style={{ paddingLeft: '2rem', color: 'var(--text-light)' }}>{lote.granja}</td>
                                    <td className="text-center">{lote.galpon}/{lote.nucleo}</td>
                                    <td className="text-right" style={{ color: 'var(--text-light)' }}>{lote.sexo || '-'}</td>
                                    <td className="text-right">{formatNumber(lote.cantidad)}</td>
                                    <td className="text-right" style={{ color: 'var(--text-light)' }}>{lote.edad_actual}d</td>
                                    <td className="text-right" style={{ color: 'var(--text-light)' }}>{lote.dias_restantes}d</td>
                                    <td className="text-right" style={{ fontWeight: 600, color: lnColor }}>{lote.peso_en_edad_ideal?.toFixed(3)} kg</td>
                                    <td colSpan={3} style={{ fontSize: '0.8rem', color: lnColor }}>{lote.mensaje}</td>
                                    <td className="text-center">{lnIcon}</td>
                                    <td></td>
                                  </tr>
                                )
                              })}
                            </React.Fragment>
                          )
                        })}
                      </tbody>
                    </table>
                  </div>
                  <div style={{ marginTop: '0.75rem', fontSize: '0.8rem', color: 'var(--text-light)' }}>
                    Ordenado por severidad y porcentaje de aves en riesgo. Expanda una fila para ver los lotes que componen cada galpón/núcleo.
                  </div>
                </div>
              </div>

              {/* Validación de mortalidad: cruce oferta vs producción */}
              {alertaData.validacion_mortalidad?.tiene_produccion && alertaData.validacion_mortalidad.cohortes.length > 0 && (
                <div className="card" style={{ borderLeft: '4px solid #8b5cf6', marginTop: '0.75rem' }}>
                  <div className="card-header" style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                    <h2><Activity size={18} style={{ verticalAlign: 'middle', marginRight: 6 }} /> Validación de Mortalidad por Cohorte</h2>
                    {alertaData.validacion_mortalidad.alertas > 0 && (
                      <span style={{
                        padding: '0.2rem 0.6rem', borderRadius: 12,
                        background: 'rgba(239, 68, 68, 0.1)', color: '#ef4444',
                        fontSize: '0.75rem', fontWeight: 600,
                      }}>
                        {alertaData.validacion_mortalidad.alertas} alerta{alertaData.validacion_mortalidad.alertas !== 1 ? 's' : ''}
                      </span>
                    )}
                  </div>
                  <div className="card-body">
                    <p style={{ fontSize: '0.8rem', color: 'var(--text-light)', marginBottom: '0.75rem' }}>
                      Cruza las aves reportadas en la oferta contra los pollitos cargados en la semana de ingreso (datos de producción).
                    </p>
                    <div className="table-container">
                      <table>
                        <thead>
                          <tr>
                            <th>Semana Ingreso</th>
                            <th>Faena Esperada</th>
                            <th className="text-right">Pollitos Cargados</th>
                            <th className="text-right">Esperados en Faena</th>
                            <th className="text-right">Aves en Oferta</th>
                            <th className="text-right">Cobertura Esperada</th>
                            <th className="text-center">Estado</th>
                            <th>Granjas</th>
                          </tr>
                        </thead>
                        <tbody>
                          {alertaData.validacion_mortalidad.cohortes.map((c, idx) => {
                            const nivelColor = c.nivel === 'alineada' ? 'var(--success, #22c55e)'
                              : c.nivel === 'mixta' ? '#3b82f6'
                              : c.nivel === 'anticipada' ? 'var(--warning, #fb923c)'
                              : c.nivel === 'atrasada' ? '#ea580c'
                              : c.nivel === 'excedida' ? '#ef4444'
                              : c.nivel === 'parcial' ? '#a78bfa'
                              : 'var(--text-light)'
                            const nivelBg = c.nivel === 'anticipada' ? 'rgba(251, 146, 60, 0.06)'
                              : c.nivel === 'atrasada' ? 'rgba(234, 88, 12, 0.06)'
                              : c.nivel === 'excedida' ? 'rgba(239, 68, 68, 0.06)'
                              : 'transparent'
                            const nivelLabel = c.nivel === 'alineada' ? 'Alineada'
                              : c.nivel === 'mixta' ? 'Mixta'
                              : c.nivel === 'anticipada' ? 'Anticipada'
                              : c.nivel === 'atrasada' ? 'Atrasada'
                              : c.nivel === 'excedida' ? 'Excedida'
                              : c.nivel === 'parcial' ? 'Parcial'
                              : 'Sin dato'
                            const desde = new Date(c.fecha_desde + 'T12:00:00')
                            const hasta = new Date(c.fecha_hasta + 'T12:00:00')
                            const faenaDesde = c.fecha_faena_esperada_desde ? new Date(c.fecha_faena_esperada_desde + 'T12:00:00') : null
                            const faenaHasta = c.fecha_faena_esperada_hasta ? new Date(c.fecha_faena_esperada_hasta + 'T12:00:00') : null
                            const coberturaEsperada = c.cobertura_pct_min != null && c.cobertura_pct_max != null
                              ? `${c.cobertura_pct_max.toFixed(1)}% - ${c.cobertura_pct_min.toFixed(1)}%`
                              : '-'
                            return (
                              <tr key={idx} style={{ background: nivelBg }}>
                                <td style={{ whiteSpace: 'nowrap', fontSize: '0.85rem' }}>
                                  {desde.toLocaleDateString('es-AR', { day: '2-digit', month: 'short' })} - {hasta.toLocaleDateString('es-AR', { day: '2-digit', month: 'short' })}
                                </td>
                                <td style={{ whiteSpace: 'nowrap', fontSize: '0.85rem' }}>
                                  {faenaDesde && faenaHasta
                                    ? `${faenaDesde.toLocaleDateString('es-AR', { day: '2-digit', month: 'short' })} - ${faenaHasta.toLocaleDateString('es-AR', { day: '2-digit', month: 'short' })}`
                                    : '-'}
                                </td>
                                <td className="text-right">{formatNumber(c.pollitos_cargados)}</td>
                                <td className="text-right">{formatNumber(c.esperados_faena_min)} - {formatNumber(c.esperados_faena_max)}</td>
                                <td className="text-right">{formatNumber(c.aves_en_oferta)}</td>
                                <td className="text-right" style={{ color: nivelColor, fontWeight: 600 }}>
                                  {coberturaEsperada}
                                </td>
                                <td className="text-center">
                                  <span style={{
                                    padding: '0.15rem 0.5rem', borderRadius: 10,
                                    fontSize: '0.75rem', fontWeight: 600,
                                    color: nivelColor,
                                    background: c.nivel === 'alineada' ? 'rgba(34, 197, 94, 0.1)'
                                      : c.nivel === 'mixta' ? 'rgba(59, 130, 246, 0.1)'
                                      : c.nivel === 'anticipada' ? 'rgba(251, 146, 60, 0.1)'
                                      : c.nivel === 'atrasada' ? 'rgba(234, 88, 12, 0.1)'
                                      : c.nivel === 'excedida' ? 'rgba(239, 68, 68, 0.1)'
                                      : c.nivel === 'parcial' ? 'rgba(167, 139, 250, 0.1)'
                                      : 'rgba(0,0,0,0.05)',
                                  }}>
                                    {nivelLabel}
                                  </span>
                                </td>
                                <td style={{ fontSize: '0.8rem', color: 'var(--text-light)' }}>
                                  {c.granjas?.join(', ')}
                                </td>
                              </tr>
                            )
                          })}
                        </tbody>
                      </table>
                    </div>
                  </div>
                </div>
              )}

              {alertaData.validacion_mortalidad && !alertaData.validacion_mortalidad.tiene_produccion && (
                <div style={{
                  padding: '0.75rem 1rem',
                  background: 'rgba(139, 92, 246, 0.06)',
                  border: '1px solid rgba(139, 92, 246, 0.2)',
                  borderRadius: 8, marginTop: '0.75rem',
                  fontSize: '0.85rem', color: '#7c3aed',
                }}>
                  <Activity size={16} style={{ verticalAlign: 'middle', marginRight: 6 }} />
                  Para validar mortalidad por cohorte, cargue el archivo de producción semanal en la pestaña correspondiente.
                </div>
              )}
            </>
          )}
        </motion.div>
      )}

      {/* ─── Vista: Por Lote ─── */}
      {vistaActiva === 'lotes' && (
        <motion.div variants={itemVariants} className="card" style={{ borderLeft: '4px solid var(--primary, #6366f1)' }}>
          <div className="card-header" style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', flexWrap: 'wrap', gap: '0.5rem' }}>
            <h2><Activity size={18} style={{ verticalAlign: 'middle', marginRight: 6 }} /> Pronóstico por Lote</h2>
            <div style={{ display: 'flex', gap: '0.5rem', alignItems: 'center' }}>
              <Filter size={14} color="var(--text-light)" />
              <select
                value={filtroNivel}
                onChange={e => setFiltroNivel(e.target.value)}
                style={{
                  padding: '0.3rem 0.5rem', border: '1px solid var(--border)',
                  borderRadius: 6, fontSize: '0.8rem', background: 'var(--bg, white)',
                  color: 'var(--text)',
                }}
              >
                <option value="todos">Todos los niveles</option>
                <option value="critico">Solo Críticos</option>
                <option value="moderado">Solo Moderados</option>
                <option value="normal">Solo Normales</option>
              </select>
              <select
                value={filtroDia}
                onChange={e => setFiltroDia(e.target.value)}
                style={{
                  padding: '0.3rem 0.5rem', border: '1px solid var(--border)',
                  borderRadius: 6, fontSize: '0.8rem', background: 'var(--bg, white)',
                  color: 'var(--text)',
                }}
              >
                <option value="todos">Todos los días</option>
                {data.dias.map(d => (
                  <option key={d.dia_index} value={d.dia_index}>
                    {getDiaNombre(d.fecha)} {d.fecha}
                  </option>
                ))}
              </select>
            </div>
          </div>
          <div className="card-body">
            <div className="table-container">
              <table>
                <thead>
                  <tr>
                    <th>Día</th>
                    <th>Granja</th>
                    <th className="text-center">G/N</th>
                    <th className="text-center">Sexo</th>
                    <th className="text-right">Aves</th>
                    <th className="text-right">Edad</th>
                    <th className="text-right">Peso Proy.</th>
                    <th style={{ minWidth: 130 }}>Rango</th>
                    <th className="text-right">Gan. Diaria</th>
                    <th className="text-center">Estado</th>
                    <th>Detalle</th>
                  </tr>
                </thead>
                <tbody>
                  {lotesFiltrados.length === 0 ? (
                    <tr><td colSpan={11} style={{ textAlign: 'center', padding: '2rem', color: 'var(--text-light)' }}>
                      No hay lotes con el filtro seleccionado
                    </td></tr>
                  ) : lotesFiltrados.map((lote, idx) => (
                    <tr key={idx} style={{ background: getNivelBg(lote.nivel) }}>
                      <td><strong>{getDiaNombre(lote.fecha)}</strong></td>
                      <td>{lote.granja}</td>
                      <td className="text-center">{lote.galpon}/{lote.nucleo}</td>
                      <td className="text-center">{lote.sexo || '-'}</td>
                      <td className="text-right">{formatNumber(lote.cantidad)}</td>
                      <td className="text-right">{lote.edad_fin_retiro}d</td>
                      <td className="text-right" style={{ fontWeight: 600, color: getNivelColor(lote.nivel) }}>
                        {lote.peso_proyectado?.toFixed(3)} kg
                      </td>
                      <td>
                        <PesoBar
                          peso={lote.peso_proyectado}
                          min={lote.peso_min}
                          max={lote.peso_max}
                          objetivo={lote.peso_objetivo}
                        />
                      </td>
                      <td className="text-right" style={{
                        color: lote.ganancia_deficiente ? '#ef4444' : 'inherit',
                        fontWeight: lote.ganancia_deficiente ? 600 : 400,
                      }}>
                        {lote.ganancia_diaria_lote != null
                          ? `${lote.ganancia_diaria_lote.toFixed(3)}`
                          : '-'}
                        {lote.ganancia_deficiente && (
                          <TrendingDown size={12} style={{ marginLeft: 3, verticalAlign: 'middle' }} />
                        )}
                      </td>
                      <td className="text-center">{getNivelIcon(lote.nivel)}</td>
                      <td style={{ fontSize: '0.8rem', color: getNivelColor(lote.nivel), maxWidth: 200 }}>
                        {lote.mensaje}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
            {lotesFiltrados.length > 0 && (
              <div style={{ marginTop: '0.75rem', fontSize: '0.8rem', color: 'var(--text-light)' }}>
                Mostrando {lotesFiltrados.length} de {data.total_lotes} lotes.
                Rango ideal: {data.peso_min_faena}–{data.peso_max_faena} kg.
                Objetivo recepción: {data.peso_objetivo} kg.
              </div>
            )}
          </div>
        </motion.div>
      )}

      {/* ─── Vista: Por Día ─── */}
      {vistaActiva === 'dias' && (
        <motion.div variants={itemVariants} className="card" style={{ borderLeft: '4px solid var(--primary, #6366f1)' }}>
          <div className="card-header">
            <h2><Activity size={18} style={{ verticalAlign: 'middle', marginRight: 6 }} /> Resumen por Día</h2>
          </div>
          <div className="card-body">
            <div className="table-container">
              <table>
                <thead>
                  <tr>
                    <th>Día</th>
                    <th>Fecha</th>
                    <th className="text-right">Pollos</th>
                    <th className="text-right">Peso Prom.</th>
                    <th className="text-right">Lotes</th>
                    <th className="text-center" style={{ color: 'var(--success, #22c55e)' }}>OK</th>
                    <th className="text-center" style={{ color: 'var(--warning, #fb923c)' }}>Moderado</th>
                    <th className="text-center" style={{ color: '#ef4444' }}>Crítico</th>
                    <th className="text-center">Estado</th>
                  </tr>
                </thead>
                <tbody>
                  {data.dias.map((dia, idx) => (
                    <tr key={idx} style={{ background: getNivelBg(dia.nivel) }}>
                      <td><strong>{getDiaNombre(dia.fecha)}</strong></td>
                      <td>{dia.fecha}</td>
                      <td className="text-right">{formatNumber(dia.total_pollos)}</td>
                      <td className="text-right" style={{ fontWeight: 600 }}>{dia.peso_promedio?.toFixed(3)} kg</td>
                      <td className="text-right">{dia.lotes_total}</td>
                      <td className="text-center" style={{ color: 'var(--success, #22c55e)', fontWeight: 600 }}>{dia.lotes_ok}</td>
                      <td className="text-center" style={{ color: 'var(--warning, #fb923c)', fontWeight: 600 }}>{dia.lotes_moderados}</td>
                      <td className="text-center" style={{ color: '#ef4444', fontWeight: 600 }}>{dia.lotes_criticos}</td>
                      <td className="text-center">{getNivelIcon(dia.nivel)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        </motion.div>
      )}

      {/* ─── Vista: Por Granja ─── */}
      {vistaActiva === 'granjas' && (
        <motion.div variants={itemVariants} className="card" style={{ borderLeft: '4px solid var(--primary, #6366f1)' }}>
          <div className="card-header">
            <h2><Activity size={18} style={{ verticalAlign: 'middle', marginRight: 6 }} /> Ranking por Granja</h2>
          </div>
          <div className="card-body">
            <div className="table-container">
              <table>
                <thead>
                  <tr>
                    <th>Granja</th>
                    <th className="text-right">Lotes</th>
                    <th className="text-right">Aves</th>
                    <th className="text-right">Peso Prom.</th>
                    <th className="text-center" style={{ color: 'var(--success, #22c55e)' }}>OK</th>
                    <th className="text-center" style={{ color: 'var(--warning, #fb923c)' }}>Moderado</th>
                    <th className="text-center" style={{ color: '#ef4444' }}>Crítico</th>
                    <th className="text-center">Estado</th>
                    <th></th>
                  </tr>
                </thead>
                <tbody>
                  {data.granjas.map((g, idx) => {
                    const isExpanded = expandedGranjas[g.granja]
                    const lotesGranja = data.lotes.filter(l => l.granja === g.granja)
                    return (
                      <React.Fragment key={idx}>
                        <tr
                          style={{ background: getNivelBg(g.nivel), cursor: 'pointer' }}
                          onClick={() => toggleGranja(g.granja)}
                        >
                          <td><strong>{g.granja}</strong></td>
                          <td className="text-right">{g.total_lotes}</td>
                          <td className="text-right">{formatNumber(g.pollos_total)}</td>
                          <td className="text-right" style={{ fontWeight: 600 }}>{g.peso_promedio?.toFixed(3)} kg</td>
                          <td className="text-center" style={{ color: 'var(--success, #22c55e)', fontWeight: 600 }}>{g.lotes_ok}</td>
                          <td className="text-center" style={{ color: 'var(--warning, #fb923c)', fontWeight: 600 }}>{g.lotes_moderados}</td>
                          <td className="text-center" style={{ color: '#ef4444', fontWeight: 600 }}>{g.lotes_criticos}</td>
                          <td className="text-center">{getNivelIcon(g.nivel)}</td>
                          <td className="text-center">
                            {isExpanded ? <ChevronUp size={14} /> : <ChevronDown size={14} />}
                          </td>
                        </tr>
                        {isExpanded && lotesGranja.map((lote, lidx) => (
                          <tr key={`${idx}-${lidx}`} style={{
                            background: getNivelBg(lote.nivel),
                            fontSize: '0.85rem',
                          }}>
                            <td style={{ paddingLeft: '2rem', color: 'var(--text-light)' }}>
                              G{lote.galpon}/N{lote.nucleo}
                            </td>
                            <td className="text-right" style={{ color: 'var(--text-light)' }}>{lote.sexo || '-'}</td>
                            <td className="text-right">{formatNumber(lote.cantidad)}</td>
                            <td className="text-right" style={{ fontWeight: 600, color: getNivelColor(lote.nivel) }}>
                              {lote.peso_proyectado?.toFixed(3)} kg
                            </td>
                            <td colSpan={3} style={{ fontSize: '0.8rem', color: getNivelColor(lote.nivel) }}>
                              {lote.mensaje}
                            </td>
                            <td className="text-center">{getNivelIcon(lote.nivel, 14)}</td>
                            <td>{getDiaNombre(lote.fecha)}</td>
                          </tr>
                        ))}
                      </React.Fragment>
                    )
                  })}
                </tbody>
              </table>
            </div>
          </div>
        </motion.div>
      )}
    </motion.div>
  )
}
