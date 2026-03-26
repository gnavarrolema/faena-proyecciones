import React, { useState, useEffect } from 'react'
import { motion } from 'framer-motion'
import {
  Activity, AlertTriangle, CheckCircle2, Loader2, TrendingDown,
  TrendingUp, Target, Filter, ChevronDown, ChevronUp, ShieldAlert, Clock
} from 'lucide-react'
import toast from 'react-hot-toast'
import { getPronosticoPesos, getAlertaTemprana } from '../services/api'

// --- Premium Animation Variants ---
const containerVariants = {
  hidden: { opacity: 0 },
  show: { opacity: 1, transition: { staggerChildren: 0.08, delayChildren: 0.05, ease: 'easeOut' } }
}
const itemVariants = {
  hidden: { opacity: 0, y: 20, filter: 'blur(8px)', scale: 0.98 },
  show: { opacity: 1, y: 0, filter: 'blur(0px)', scale: 1, transition: { type: 'spring', stiffness: 120, damping: 20 } }
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
  const [vistaActiva, setVistaActiva] = useState('alerta') // alerta | lotes | dias | granjas
  const [expandedGranjas, setExpandedGranjas] = useState({})
  const [alertaData, setAlertaData] = useState(null)
  const [alertaLoading, setAlertaLoading] = useState(false)
  const [alertaFiltroNivel, setAlertaFiltroNivel] = useState('todos')
  const [alertaExpandedGranjas, setAlertaExpandedGranjas] = useState({})
  const [alertaExpandedGalpones, setAlertaExpandedGalpones] = useState({})
  const [showExplicacion, setShowExplicacion] = useState(false)

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

      {/* Explicación de cálculos */}
      <motion.div variants={itemVariants} style={{ marginBottom: '0.75rem' }}>
        <button
          onClick={() => setShowExplicacion(!showExplicacion)}
          style={{
            display: 'flex', alignItems: 'center', gap: 6,
            background: 'rgba(99, 102, 241, 0.06)',
            border: '1px solid rgba(99, 102, 241, 0.2)',
            borderRadius: 8, padding: '0.5rem 1rem',
            fontSize: '0.85rem', color: 'var(--primary, #6366f1)',
            cursor: 'pointer', fontWeight: 500, width: '100%',
            justifyContent: 'space-between',
          }}
        >
          <span>📐 ¿Cómo se calculan los pesos y métricas?</span>
          {showExplicacion ? <ChevronUp size={16} /> : <ChevronDown size={16} />}
        </button>
        {showExplicacion && (
          <div style={{
            background: 'var(--bg, white)',
            border: '1px solid var(--border, #e5e7eb)',
            borderTop: 'none',
            borderRadius: '0 0 8px 8px',
            padding: '1rem 1.2rem',
            fontSize: '0.84rem',
            lineHeight: 1.7,
            color: 'var(--text)',
          }}>
            <div style={{ marginBottom: '0.75rem' }}>
              <strong>Datos de entrada (Archivo de Oferta Excel)</strong>
              <p style={{ margin: '0.3rem 0', color: 'var(--text-light)' }}>
                Se leen las columnas: <em>Fecha de Peso, Granja, Galpón, Núcleo, Cantidad, Sexo, Edad Proyectada,
                Peso Muestreo Proyectado, Ganancia Diaria, Días Proyectados, Edad Real, Peso Muestreo Real y Fecha de Ingreso</em>.
              </p>
            </div>

            <div style={{ marginBottom: '0.75rem' }}>
              <strong>Edad Hoy (edad actual del lote)</strong>
              <p style={{ margin: '0.3rem 0', color: 'var(--text-light)' }}>
                <code style={{ background: 'rgba(0,0,0,0.05)', padding: '1px 4px', borderRadius: 3 }}>
                  Edad Hoy = Edad Proyectada + (Fecha de Hoy − Fecha Base)
                </code><br />
                Donde <em>Fecha Base = Fecha de Peso + Días Proyectados</em>. Los "Días Proyectados" indican cuántos días 
                después del pesaje se emitió la oferta, por lo que la Edad Proyectada ya incluye esos días.
              </p>
            </div>

            <div style={{ marginBottom: '0.75rem' }}>
              <strong>Peso Vivo Proyectado al retiro / a edad ideal</strong>
              <p style={{ margin: '0.3rem 0', color: 'var(--text-light)' }}>
                <code style={{ background: 'rgba(0,0,0,0.05)', padding: '1px 4px', borderRadius: 3 }}>
                  Peso Vivo = (Días Extra × Ganancia Diaria) + Peso Muestreo Real + Medio Día
                </code><br />
                • <em>Días Extra</em> = Edad al retiro − Edad Real − 1<br />
                • <em>Ganancia Diaria</em>: se usa la del lote (columna "Ganancia Diaria" de la oferta); si no está disponible, 
                se usa la global por sexo (Macho: 0.090, Hembra: 0.079 kg/día)<br />
                • <em>Medio Día</em> = 0.090 × 0.5 = 0.045 kg (ajuste de medio día, siempre con ganancia macho)<br />
                • Para <strong>Machos y Mixtos</strong>: se aplica un descuento del 4% → <code style={{ background: 'rgba(0,0,0,0.05)', padding: '1px 4px', borderRadius: 3 }}>Peso × 0.96</code><br />
                • Para <strong>Hembras</strong>: sin descuento
              </p>
            </div>

            <div style={{ marginBottom: '0.75rem' }}>
              <strong>Ganancia Mínima Necesaria</strong>
              <p style={{ margin: '0.3rem 0', color: 'var(--text-light)' }}>
                Es la ganancia diaria mínima que debería tener el lote <strong>desde hoy</strong> para alcanzar el peso mínimo de faena 
                ({data.peso_min_faena} kg) a su edad ideal. Se calcula a partir del peso estimado actual:
                <br />
                <code style={{ background: 'rgba(0,0,0,0.05)', padding: '1px 4px', borderRadius: 3 }}>
                  Peso Estimado Hoy = Peso Real + (Edad Hoy − Edad Real) × Gan. Diaria Lote
                </code><br />
                <code style={{ background: 'rgba(0,0,0,0.05)', padding: '1px 4px', borderRadius: 3 }}>
                  Gan. Necesaria = (Peso Objetivo − Peso Estimado Hoy − Medio Día) / (Días Restantes − 1)
                </code><br />
                Para M/MIX, el peso objetivo se ajusta por el descuento: Peso Mín / 0.96
              </p>
            </div>

            <div style={{ marginBottom: '0.75rem' }}>
              <strong>Clasificación Semáforo (Alerta Temprana)</strong>
              <p style={{ margin: '0.3rem 0', color: 'var(--text-light)' }}>
                • <span style={{ color: '#22c55e', fontWeight: 600 }}>Verde</span>: peso proyectado a edad ideal dentro del rango {data.peso_min_faena}–{data.peso_max_faena} kg con margen suficiente<br />
                • <span style={{ color: '#fb923c', fontWeight: 600 }}>Amarillo</span>: peso al límite ({'<'}100g sobre mín.), necesita mejorar ganancia ({'>'}10% sobre la actual), o sobrepeso a edad ideal pero alcanzable faenando antes<br />
                • <span style={{ color: '#ef4444', fontWeight: 600 }}>Rojo</span>: no alcanza peso mínimo ni a edad máxima ({data.dias?.length > 0 ? '' : '43d'}), o sobrepeso incluso a edad mínima
              </p>
            </div>

            <div style={{ marginBottom: '0.75rem' }}>
              <strong>Clasificación Semáforo (Por Lote - Planificación)</strong>
              <p style={{ margin: '0.3rem 0', color: 'var(--text-light)' }}>
                • <span style={{ color: '#22c55e', fontWeight: 600 }}>Normal</span>: peso proyectado al día de faena asignado dentro del rango<br />
                • <span style={{ color: '#fb923c', fontWeight: 600 }}>Moderado</span>: bajo peso o sobrepeso con déficit/exceso ≤ 150g<br />
                • <span style={{ color: '#ef4444', fontWeight: 600 }}>Crítico</span>: bajo peso o sobrepeso con déficit/exceso {'>'} 150g
              </p>
            </div>

            <div>
              <strong>Parámetros de referencia</strong>
              <p style={{ margin: '0.3rem 0', color: 'var(--text-light)' }}>
                Rango de peso aceptable: {data.peso_min_faena}–{data.peso_max_faena} kg | 
                Peso objetivo recepción: {data.peso_objetivo} kg | 
                Edad ideal: Macho 40d, Hembra 44d, Mixto 42d | 
                Ventana de faena: 38–43 días de edad | 
                Rendimiento canal: 87% | 
                Calibre = 20 kg / Peso faenado
              </p>
            </div>
          </div>
        )}
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
              <motion.div variants={itemVariants} className="card" style={{
                borderTop: '4px solid var(--warning, #fb923c)',
                borderRadius: 16,
                boxShadow: '0 10px 25px -5px rgba(0,0,0,0.05)',
                marginBottom: '1.5rem'
              }}>
                <div className="card-header" style={{ padding: '1.25rem 1.5rem', background: '#ffffff', borderBottom: '1px solid rgba(226,232,240,0.6)', display: 'flex', justifyContent: 'space-between', alignItems: 'center', flexWrap: 'wrap', gap: '0.5rem' }}>
                  <h2 style={{ fontSize: '1.2rem', gap: '0.5rem', color: '#b45309', display: 'flex', alignItems: 'center' }}>
                    <ShieldAlert size={20} style={{ filter: 'drop-shadow(0 2px 4px rgba(245, 158, 11, 0.3))', marginRight: 8 }} /> 
                    Planificación Anticipada por Lote
                  </h2>
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
                <div className="card-body" style={{ padding: '0 1.5rem 1.5rem 1.5rem' }}>
                  <div className="table-container" style={{ borderRadius: 12, boxShadow: '0 4px 6px -1px rgba(0,0,0,0.05)', marginTop: '1rem' }}>
                    <table>
                      <thead style={{ background: 'linear-gradient(to right, #f8fafc, #f1f5f9)' }}>
                        <tr>
                          <th>Granja</th>
                          <th className="text-center">Galpón / Núcleo</th>
                          <th className="text-center">Sexo</th>
                          <th className="text-right">Cantidad de Aves</th>
                          <th className="text-right">Edad Hoy (días)</th>
                          <th className="text-right">Peso Real (kg)</th>
                          <th className="text-right">Peso Proy. a Edad Ideal (kg)</th>
                          <th style={{ minWidth: 130 }}>Rango Aceptable</th>
                          <th className="text-right">Gan. Diaria Oferta</th>
                          <th className="text-right">Gan. Mín. Necesaria</th>
                          <th className="text-center">Días a Edad Ideal</th>
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
                              <motion.tr key={idx} 
                                whileHover={{ backgroundColor: 'rgba(255, 255, 255, 0.9)', scale: 1.002, transformOrigin: 'left center' }}
                                style={{ 
                                  background: nivelBg.replace('0.08', '0.04'),
                                  borderLeft: `3px solid ${nivelColor}`,
                                  borderBottom: '1px solid rgba(226,232,240,0.5)',
                                  transition: 'background 0.2s ease, border-left 0.2s ease'
                                }}
                              >
                                <td style={{ fontWeight: 600, color: 'var(--text)' }}>{lote.granja}</td>
                                <td className="text-center" style={{ color: 'var(--text-light)', fontSize: '0.85rem' }}>{lote.galpon}/{lote.nucleo}</td>
                                <td className="text-center" style={{ color: 'var(--text-light)' }}>{lote.sexo || '-'}</td>
                                <td className="text-right" style={{ fontWeight: 500 }}>{formatNumber(lote.cantidad)}</td>
                                <td className="text-right" style={{ color: 'var(--text-light)' }}>{lote.edad_actual}d</td>
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
                                <td style={{ fontSize: '0.8rem', color: nivelColor, minWidth: 200, maxWidth: 300, whiteSpace: 'normal', wordBreak: 'break-word', lineHeight: 1.4 }}>
                                  {lote.mensaje}
                                </td>
                              </motion.tr>
                            )
                          })
                        })()}
                      </tbody>
                    </table>
                  </div>
                  {alertaData.lotes.length > 0 && (
                    <div style={{ marginTop: '1rem', fontSize: '0.8rem', color: 'var(--text-light)', background: 'rgba(0,0,0,0.015)', padding: '0.75rem 1rem', borderRadius: 8 }}>
                      <strong>📝 Metadata:</strong> Mostrando {alertaData.lotes.filter(l => alertaFiltroNivel === 'todos' || l.nivel === alertaFiltroNivel).length} de {alertaData.total_lotes} lotes.
                      Rango ideal: <span style={{fontWeight:500}}>{alertaData.peso_min_faena}–{alertaData.peso_max_faena} kg</span>.
                      Ventana faena: <span style={{fontWeight:500}}>{alertaData.edad_min_faena}–{alertaData.edad_max_faena} días</span>.
                      <br />
                      <div style={{ marginTop: 6, opacity: 0.8 }}>
                        <em>Peso Real</em> corresponde a la columna "Peso Muestreo Real" del archivo de oferta.
                        La <em>Ganancia Diaria Oferta</em> proviene de la columna "Ganancia Diaria".
                        La <em>Edad Hoy</em> se calcula sumando los días transcurridos desde la fecha base de la oferta a la edad proyectada.
                      </div>
                    </div>
                  )}
                </div>
              </motion.div>

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
                          <th className="text-right">Cant. Lotes</th>
                          <th className="text-right">Total Aves</th>
                          <th className="text-right">Peso Prom. a Edad Ideal (kg)</th>
                          <th className="text-center" style={{ color: 'var(--success, #22c55e)' }}>En Rango</th>
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
                          <th className="text-center">Galpón / Núcleo</th>
                          <th className="text-right">Cant. Lotes</th>
                          <th className="text-right">Total Aves</th>
                          <th className="text-right">% Riesgo Alto</th>
                          <th className="text-right">% En Alerta</th>
                          <th className="text-right">Peso Prom. a Edad Ideal (kg)</th>
                          <th className="text-center" style={{ color: 'var(--success, #22c55e)' }}>En Rango</th>
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

                    {/* Explicación de columnas y cálculos */}
                    <div style={{
                      marginTop: '1rem',
                      padding: '0.85rem 1rem',
                      background: 'rgba(139, 92, 246, 0.04)',
                      border: '1px solid rgba(139, 92, 246, 0.15)',
                      borderRadius: 8,
                      fontSize: '0.8rem',
                      lineHeight: 1.7,
                      color: 'var(--text-light)',
                    }}>
                      <div style={{ fontWeight: 600, color: 'var(--text)', marginBottom: '0.4rem' }}>
                        📐 ¿Cómo se calculan estas métricas?
                      </div>
                      <div style={{ marginBottom: '0.4rem' }}>
                        <strong>Semana Ingreso:</strong> semana en que se cargaron los pollitos BB según el archivo de producción.
                        Cada lote de la oferta se asocia a una semana de ingreso mediante su columna "Fecha de Ingreso".
                      </div>
                      <div style={{ marginBottom: '0.4rem' }}>
                        <strong>Faena Esperada:</strong> ventana estimada sumando 42 días a la semana de ingreso
                        (ej: ingreso 07-feb → faena esperada desde 21-mar). Representa cuándo esas aves deberían estar listas.
                      </div>
                      <div style={{ marginBottom: '0.4rem' }}>
                        <strong>Pollitos Cargados:</strong> total de pollitos BB reportados en el archivo de producción semanal para esa semana de ingreso.
                      </div>
                      <div style={{ marginBottom: '0.4rem' }}>
                        <strong>Esperados en Faena:</strong> rango de aves que se espera recibir vivas en planta, aplicando una merma de referencia
                        entre 4.5% y 7.5% sobre los pollitos cargados.
                        <br />
                        <span style={{ fontStyle: 'italic' }}>
                          Mínimo = Pollitos × (1 − 7.5%) &nbsp;|&nbsp; Máximo = Pollitos × (1 − 4.5%)
                        </span>
                      </div>
                      <div style={{ marginBottom: '0.4rem' }}>
                        <strong>Aves en Oferta:</strong> suma de la columna "Cantidad" de todos los lotes de la oferta cuya "Fecha de Ingreso"
                        cae dentro de esa semana de producción.
                      </div>
                      <div style={{ marginBottom: '0.4rem' }}>
                        <strong>Cobertura Esperada:</strong> porcentaje que representan las aves en oferta respecto al rango esperado en faena.
                        <br />
                        <span style={{ fontStyle: 'italic' }}>
                          Cobertura = Aves en Oferta / Esperados en Faena × 100%
                        </span>
                        <br />
                        Un valor cercano a 100% indica buena alineación. Valores muy bajos ({'<'}50%) sugieren cobertura parcial;
                        valores superiores a 100% pueden indicar aves de otras cohortes o diferimientos.
                      </div>
                      <div>
                        <strong>Estado:</strong><br />
                        • <span style={{ color: 'var(--success, #22c55e)', fontWeight: 600 }}>Alineada</span>: cantidad y fechas dentro de lo esperado<br />
                        • <span style={{ color: '#a78bfa', fontWeight: 600 }}>Parcial</span>: la oferta cubre solo una parte (puede ser normal si la oferta viene por granja)<br />
                        • <span style={{ color: 'var(--warning, #fb923c)', fontWeight: 600 }}>Anticipada</span>: la oferta planea faenar antes de la ventana de +42 días<br />
                        • <span style={{ color: '#ea580c', fontWeight: 600 }}>Atrasada</span>: la oferta planea faenar después de la ventana esperada<br />
                        • <span style={{ color: '#3b82f6', fontWeight: 600 }}>Mixta</span>: lotes con fechas dentro y fuera de la ventana<br />
                        • <span style={{ color: '#ef4444', fontWeight: 600 }}>Excedida</span>: aves en oferta superan el máximo esperado para la cohorte
                      </div>
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
                    <th>Día Faena</th>
                    <th>Granja</th>
                    <th className="text-center">Galpón / Núcleo</th>
                    <th className="text-center">Sexo</th>
                    <th className="text-right">Cantidad de Aves</th>
                    <th className="text-right">Edad al Retiro (días)</th>
                    <th className="text-right">Peso Vivo Proy. (kg)</th>
                    <th style={{ minWidth: 130 }}>Rango Aceptable</th>
                    <th className="text-right">Gan. Diaria Oferta</th>
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
                    <th>Día Faena</th>
                    <th>Fecha</th>
                    <th className="text-right">Total Aves</th>
                    <th className="text-right">Peso Prom. Ponderado (kg)</th>
                    <th className="text-right">Cant. Lotes</th>
                    <th className="text-center" style={{ color: 'var(--success, #22c55e)' }}>En Rango</th>
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
                    <th className="text-right">Cant. Lotes</th>
                    <th className="text-right">Total Aves</th>
                    <th className="text-right">Peso Prom. Ponderado (kg)</th>
                    <th className="text-center" style={{ color: 'var(--success, #22c55e)' }}>En Rango</th>
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
