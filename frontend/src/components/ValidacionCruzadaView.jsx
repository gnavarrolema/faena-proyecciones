import React, { useState, useEffect } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import { ShieldCheck, AlertTriangle, AlertCircle, Info, TrendingUp, Loader2, RefreshCw, CheckCircle2, XCircle, Search, GitMerge, Activity, BarChart3, Clock, Database, Target } from 'lucide-react'
import { getValidacionCruzada } from '../services/api'

// --- Sophisticated Animation Variants ---
const containerVariants = {
  hidden: { opacity: 0 },
  show: { opacity: 1, transition: { staggerChildren: 0.12, delayChildren: 0.1 } }
}
const itemVariants = {
  hidden: { opacity: 0, y: 30, filter: 'blur(10px)', scale: 0.98 },
  show: { opacity: 1, y: 0, filter: 'blur(0px)', scale: 1, transition: { type: 'spring', stiffness: 90, damping: 16 } }
}
const floatHover = {
  scale: 1.015,
  y: -4,
  boxShadow: '0 25px 30px -5px rgba(0, 0, 0, 0.1), 0 10px 15px -5px rgba(0, 0, 0, 0.04)',
  borderColor: 'rgba(255,255,255,0.8)',
  transition: { type: 'spring', stiffness: 400, damping: 25 }
}

function formatNumber(n) {
  if (n == null) return '-'
  return n.toLocaleString('es-AR')
}

function formatDate(d) {
  if (!d) return '-'
  const dt = new Date(d + 'T12:00:00')
  return dt.toLocaleDateString('es-AR', { day: 'numeric', month: 'short', year: 'numeric' })
}

function formatRange(a, b) {
  if (!a && !b) return '-'
  if (a === b) return formatDate(a)
  return `${formatDate(a)} - ${formatDate(b)}`
}

function formatDateTime(value) {
  if (!value) return 'Sin registro'
  const dt = new Date(value)
  if (Number.isNaN(dt.getTime())) return value
  return dt.toLocaleString('es-AR', {
    day: 'numeric',
    month: 'short',
    year: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
  })
}

function formatSignedNumber(n) {
  if (n == null) return '-'
  if (n === 0) return '0'
  const abs = Math.abs(n).toLocaleString('es-AR')
  return `${n > 0 ? '+' : '-'}${abs}`
}

function getWeekStart(dateStr) {
  if (!dateStr) return null
  const dt = new Date(`${dateStr}T12:00:00`)
  const day = dt.getDay()
  const offset = day === 0 ? -6 : 1 - day
  dt.setDate(dt.getDate() + offset)
  return dt
}

function formatWeekRange(dateStr) {
  const start = getWeekStart(dateStr)
  if (!start) return '-'
  const end = new Date(start)
  end.setDate(end.getDate() + 5)
  return `${start.toLocaleDateString('es-AR', { day: 'numeric', month: 'short' })} - ${end.toLocaleDateString('es-AR', { day: 'numeric', month: 'short' })}`
}

function getPlanningAction(cohorte) {
  switch (cohorte.nivel) {
    case 'anticipada':
      return {
        titulo: 'Mover a ventana esperada',
        detalle: `Programar desde la semana ${formatWeekRange(cohorte.fecha_faena_esperada_desde)}.`
      }
    case 'atrasada':
      return {
        titulo: 'Revisar prioridad de faena',
        detalle: 'La cohorte aparece tarde respecto a +42 dias; validar sobreedad o atraso del dato.'
      }
    case 'excedida':
      return {
        titulo: 'Validar exceso de aves',
        detalle: 'Separar por granja o lote para confirmar que no haya duplicidad o mezcla de semanas.'
      }
    case 'mixta':
      return {
        titulo: 'Desagregar la cohorte',
        detalle: 'Hay lotes dentro y fuera de la ventana esperada; conviene partir la planificación.'
      }
    case 'parcial':
      return {
        titulo: 'Planificar como cohorte parcial',
        detalle: 'Usar esta base para la semana y complementar con otras cohortes o compras.'
      }
    default:
      return {
        titulo: 'Planificar en la ventana actual',
        detalle: `La cohorte calza con la semana ${formatWeekRange(cohorte.fecha_objetivo_desde || cohorte.fecha_faena_esperada_desde)}.`
      }
  }
}

function getPlanningWeekLabel(cohorte) {
  if (cohorte.nivel === 'atrasada') return 'Revisión Inmediata'
  return formatWeekRange(cohorte.fecha_objetivo_desde || cohorte.fecha_faena_esperada_desde)
}

function getBrechaConfig(cohorte) {
  if (cohorte.estado_cantidad === 'por_encima') {
    return {
      label: `${formatSignedNumber(cohorte.diferencia_vs_max)} vs máx`,
      color: 'var(--danger)',
      bg: 'var(--danger-light)'
    }
  }
  if (cohorte.diferencia_vs_min == null) {
    return { label: '-', color: 'var(--text-light)', bg: 'rgba(0,0,0,0.05)' }
  }
  const esNegativo = cohorte.diferencia_vs_min < 0
  return {
    label: `${formatSignedNumber(cohorte.diferencia_vs_min)} vs mín`,
    color: esNegativo ? 'var(--warning)' : 'var(--success)',
    bg: esNegativo ? 'var(--warning-light)' : 'var(--success-light)'
  }
}

const NIVEL_CONFIG = {
  alineada: { label: 'Alineada', color: '#059669', bg: '#d1fae5', bgGradient: 'linear-gradient(135deg, #d1fae5 0%, #ecfdf5 100%)', icon: <CheckCircle2 size={14} /> },
  parcial: { label: 'Parcial', color: '#475569', bg: '#f1f5f9', bgGradient: 'linear-gradient(135deg, #f1f5f9 0%, #f8fafc 100%)', icon: <Target size={14} /> },
  anticipada: { label: 'Anticipada', color: '#b45309', bg: '#fef3c7', bgGradient: 'linear-gradient(135deg, #fef3c7 0%, #fffbeb 100%)', icon: <Clock size={14} /> },
  atrasada: { label: 'Atrasada', color: '#c2410c', bg: '#ffedd5', bgGradient: 'linear-gradient(135deg, #ffedd5 0%, #fff7ed 100%)', icon: <AlertTriangle size={14} /> },
  mixta: { label: 'Mixta', color: '#1d4ed8', bg: '#dbeafe', bgGradient: 'linear-gradient(135deg, #dbeafe 0%, #eff6ff 100%)', icon: <GitMerge size={14} /> },
  excedida: { label: 'Excedida', color: '#b91c1c', bg: '#fee2e2', bgGradient: 'linear-gradient(135deg, #fee2e2 0%, #fef2f2 100%)', icon: <XCircle size={14} /> },
  sin_dato: { label: 'Sin dato', color: '#64748b', bg: '#f1f5f9', bgGradient: 'linear-gradient(135deg, #f1f5f9 0%, #f8fafc 100%)', icon: <Info size={14} /> },
}

const INSIGHT_STYLES = {
  critico: { border: '#fca5a5', bg: 'linear-gradient(135deg, rgba(254, 242, 242, 0.9) 0%, rgba(255, 255, 255, 0.9) 100%)', color: '#991b1b', icon: <XCircle size={22} color="#dc2626" /> },
  advertencia: { border: '#fcd34d', bg: 'linear-gradient(135deg, rgba(255, 251, 235, 0.9) 0%, rgba(255, 255, 255, 0.9) 100%)', color: '#92400e', icon: <AlertTriangle size={22} color="#d97706" /> },
  positivo: { border: '#86efac', bg: 'linear-gradient(135deg, rgba(240, 253, 244, 0.9) 0%, rgba(255, 255, 255, 0.9) 100%)', color: '#166534', icon: <CheckCircle2 size={22} color="#16a34a" /> },
  info: { border: '#93c5fd', bg: 'linear-gradient(135deg, rgba(239, 246, 255, 0.9) 0%, rgba(255, 255, 255, 0.9) 100%)', color: '#1e40af', icon: <Info size={22} color="#2563eb" /> },
}

const COHORTE_WRAP_CELL_STYLE = {
  whiteSpace: 'normal',
  verticalAlign: 'top',
}

const COHORTE_META_TEXT_STYLE = {
  color: 'var(--text-light)',
  whiteSpace: 'normal',
  wordBreak: 'break-word',
}

export default function ValidacionCruzadaView() {
  const [data, setData] = useState(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)

  const cargar = async () => {
    setLoading(true)
    setError(null)
    try {
      const result = await getValidacionCruzada()
      setData(result)
    } catch (err) {
      if (err.response?.status === 404) {
        setData(null)
      } else {
        setError(err.response?.data?.detail || err.message)
      }
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => { cargar() }, [])

  if (loading) {
    return (
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', height: '60vh', flexDirection: 'column', gap: '1rem' }}>
        <motion.div
          animate={{ rotate: 360, scale: [1, 1.1, 1] }}
          transition={{ repeat: Infinity, duration: 1.5, ease: "easeInOut" }}
        >
          <Activity size={32} color="var(--primary)" />
        </motion.div>
        <motion.span
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          transition={{ repeat: Infinity, duration: 1.5, ease: "easeInOut", repeatType: "reverse" }}
          style={{ color: 'var(--text-light)', fontWeight: 600, letterSpacing: '0.05em' }}
        >
          Sincronizando operaciones...
        </motion.span>
      </div>
    )
  }

  if (error) {
    return (
      <div className="card" style={{ borderLeft: '4px solid var(--danger)', boxShadow: '0 10px 25px rgba(239,68,68,0.1)' }}>
        <div className="card-body" style={{ textAlign: 'center', padding: '3rem 2rem' }}>
          <AlertCircle size={48} color="var(--danger)" style={{ margin: '0 auto 1.5rem', opacity: 0.8 }} />
          <h3 style={{ fontSize: '1.25rem', color: 'var(--danger)', marginBottom: '0.5rem', fontWeight: 600 }}>Error de Carga</h3>
          <p style={{ color: 'var(--text-light)', marginBottom: '2rem' }}>{error}</p>
          <button className="btn btn-outline" onClick={cargar}>
            <RefreshCw size={16} /> Reintentar Operación
          </button>
        </div>
      </div>
    )
  }

  if (!data) {
    return (
      <motion.div initial={{ opacity: 0, y: 20 }} animate={{ opacity: 1, y: 0 }} className="card" style={{
        background: 'linear-gradient(135deg, #ffffff 0%, #f8fafc 100%)',
        border: '1px solid rgba(226,232,240,0.8)'
      }}>
        <div className="card-body" style={{ textAlign: 'center', padding: '4rem 2rem' }}>
          <motion.div
            animate={{ y: [0, -10, 0] }}
            transition={{ repeat: Infinity, duration: 3, ease: "easeInOut" }}
          >
            <GitMerge size={56} color="var(--primary-light)" style={{ marginBottom: 20, filter: 'drop-shadow(0 4px 6px rgba(45,138,78,0.3))' }} />
          </motion.div>
          <h2 style={{ fontSize: '1.4rem', fontWeight: 700, color: 'var(--text)', marginBottom: '0.5rem' }}>
            Sincronización Operativa Inactiva
          </h2>
          <p style={{ fontSize: '1rem', color: 'var(--text-light)', maxWidth: '500px', margin: '0 auto 1rem' }}>
            No hay datos suficientes para realizar el cruce entre los módulos de Oferta y Producción.
          </p>
          <p style={{ fontSize: '0.9rem', color: 'var(--text-light)', background: 'rgba(0,0,0,0.03)', padding: '0.75rem 1.5rem', borderRadius: 20, display: 'inline-block' }}>
            💡 Cargue la oferta validada y los datos de producción de Pollitos BB para habilitar el reporte dinámico.
          </p>
        </div>
      </motion.div>
    )
  }

  const { validacion, insights, fuentes, tiene_oferta, tiene_produccion, total_ofertas, total_semanas_produccion } = data
  const fact = validacion?.factibilidad
  const cohortes = validacion?.mortalidad_cohortes
  const consist = validacion?.consistencia_edad
  const peorTasa = fact?.coberturas?.[fact.coberturas.length - 1]?.tasa
  const cohortesList = cohortes?.cohortes || []
  const cohortesEnVentana = cohortesList.filter(c => c.estado_fecha === 'alineada')
  const cohortesReprogramar = cohortesList.filter(c => c.nivel === 'anticipada' || c.nivel === 'mixta')
  const cohortesPrioridad = cohortesList.filter(c => c.nivel === 'atrasada' || c.nivel === 'excedida')
  const totalOfertaCohortes = cohortesList.reduce((acc, c) => acc + (c.aves_en_oferta || 0), 0)
  const totalEsperadoMinCohortes = cohortesList.reduce((acc, c) => acc + (c.esperados_faena_min || 0), 0)
  const balanceCohortes = totalOfertaCohortes - totalEsperadoMinCohortes
  const proximaSemanaPlan = cohortesList.length > 0
    ? cohortesList
      .map(c => c.fecha_objetivo_desde || c.fecha_faena_esperada_desde)
      .filter(Boolean)
      .sort()[0]
    : null

  return (
    <motion.div variants={containerVariants} initial="hidden" animate="show">
      {/* Header con estado */}
      <motion.div variants={itemVariants} className="card" style={{
        background: 'linear-gradient(180deg, rgba(255,255,255,1) 0%, rgba(248,250,252,1) 100%)',
        overflow: 'visible'
      }}>
        <div className="card-header" style={{
          borderBottom: 'none', paddingBottom: '0.75rem'
        }}>
          <h2 style={{
            fontSize: '1.4rem', fontWeight: 800,
            background: 'linear-gradient(135deg, var(--primary-dark) 0%, var(--primary-light) 100%)',
            WebkitBackgroundClip: 'text', WebkitTextFillColor: 'transparent',
            display: 'flex', alignItems: 'center', gap: '0.5rem'
          }}>
            <GitMerge size={22} color="var(--primary)" style={{ filter: 'drop-shadow(0 2px 4px rgba(26,86,50,0.2))' }} />
            Sincronización Operativa: Oferta ↔ Producción
          </h2>
          <motion.button whileHover={{ scale: 1.05 }} whileTap={{ scale: 0.95 }} className="btn btn-sm btn-outline" onClick={cargar} style={{ borderRadius: 20 }}>
            <RefreshCw size={14} /> Actualizar
          </motion.button>
        </div>
        <div className="card-body" style={{ paddingTop: '0.5rem' }}>
          <div style={{ display: 'flex', gap: '1rem', flexWrap: 'wrap', marginBottom: '1.5rem' }}>
            <StatusBadge ok={tiene_oferta} label="Datos de Oferta" detail={tiene_oferta ? `${formatNumber(total_ofertas)} lotes en oferta` : 'Sin archivo'} iconType="oferta" />
            <StatusBadge ok={tiene_produccion} label="Módulo Producción" detail={tiene_produccion ? `${total_semanas_produccion} semanas activas` : 'Sin registro'} iconType="produccion" />
            <StatusBadge ok={tiene_oferta && tiene_produccion} label="Estado de Cruce"
              detail={tiene_oferta && tiene_produccion ? 'Validación habilitada' : 'Faltan datos operacionales'} iconType="cruce" />
          </div>

          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(320px, 1fr))', gap: '1.5rem' }}>
            <DataSourceCard
              title="Registro de Oferta"
              icon={<Box size={16} />}
              source={fuentes?.oferta}
              emptyText="No se encontraron datos históricos para la carga de oferta."
              rows={[
                { label: 'Volumen Persistido', value: fuentes?.oferta?.persisted ? `${formatNumber(fuentes.oferta.persisted.total_lotes)} lotes · ${formatNumber(fuentes.oferta.persisted.total_pollos)} aves` : 'Vacío' },
                { label: 'Rango Fecha Peso', value: formatRange(fuentes?.oferta?.persisted?.fecha_peso_desde, fuentes?.oferta?.persisted?.fecha_peso_hasta) },
                { label: 'Rango Ingreso', value: formatRange(fuentes?.oferta?.persisted?.fecha_ingreso_desde, fuentes?.oferta?.persisted?.fecha_ingreso_hasta) },
              ]}
            />
            <DataSourceCard
              title="Registro de Producción"
              icon={<Database size={16} />}
              source={fuentes?.produccion}
              emptyText="No se encontraron datos históricos de producción BB."
              rows={[
                { label: 'Volumen Persistido', value: fuentes?.produccion?.persisted ? `${formatNumber(fuentes.produccion.persisted.total_semanas)} sem · ${formatNumber(fuentes.produccion.persisted.total_pollitos)} pollitos` : 'Vacío' },
                { label: 'Ventana Cargada', value: formatRange(fuentes?.produccion?.persisted?.fecha_desde, fuentes?.produccion?.persisted?.fecha_hasta) },
              ]}
            />
          </div>
        </div>
      </motion.div>

      {/* Resumen ejecutivo */}
      {cohortesList.length > 0 && (
        <motion.div variants={itemVariants} className="card" style={{
          borderLeft: '4px solid var(--primary-light)',
          boxShadow: '0 10px 15px -3px rgba(0,0,0,0.05), 0 4px 6px -2px rgba(0,0,0,0.02)'
        }}>
          <div className="card-header" style={{ background: 'transparent' }}>
            <h2 style={{ fontSize: '1.15rem' }}><BarChart3 size={18} style={{ marginRight: 8, color: 'var(--primary-light)' }} /> Resumen Ejecutivo de Flujo</h2>
            <span style={{ fontSize: '0.85rem', color: 'var(--text-light)', fontWeight: 600, background: 'rgba(0,0,0,0.04)', padding: '0.2rem 0.6rem', borderRadius: 12 }}>
              Visión Agregada
            </span>
          </div>
          <div className="card-body">
            <p style={{ fontSize: '0.95rem', color: 'var(--text)', marginBottom: '1.5rem', lineHeight: 1.6, fontWeight: 500 }}>
              La oferta proyectada se distribuye en <strong>{cohortesList.length} cohorte{cohortesList.length !== 1 ? 's' : ''}</strong> de interés operativo. 
              {cohortesEnVentana.length > 0 && <span> Actualmente <strong>{cohortesEnVentana.length}</strong> {cohortesEnVentana.length !== 1 ? 'se encuentran' : 'se encuentra'} dentro de la ventana óptima de faena</span>} 
              {cohortesReprogramar.length > 0 && <span>, mientras que <strong style={{ color: 'var(--warning)' }}>{cohortesReprogramar.length}</strong> {cohortesReprogramar.length !== 1 ? 'requieren' : 'requiere'} reprogramación de tiempos</span>} 
              {cohortesPrioridad.length > 0 && <span> y <strong style={{ color: 'var(--danger)' }}>{cohortesPrioridad.length}</strong> {cohortesPrioridad.length !== 1 ? 'necesitan' : 'necesita'} intervención prioritaria</span>}. 
              {proximaSemanaPlan && <span> La programación más inminente inicia la semana del <strong style={{ color: 'var(--primary)' }}>{formatWeekRange(proximaSemanaPlan)}</strong>.</span>}
            </p>
            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(180px, 1fr))', gap: '1rem' }}>
              <KpiCard icon={<CheckCircle2 size={16} />} label="En Ventana Óptima" value={formatNumber(cohortesEnVentana.length)} color="var(--success)" />
              <KpiCard icon={<Clock size={16} />} label="Revisión Tiempos" value={formatNumber(cohortesReprogramar.length)} color="var(--warning)" />
              <KpiCard icon={<AlertCircle size={16} />} label="Alerta Prioritaria" value={formatNumber(cohortesPrioridad.length)} color="var(--danger)" />
              <KpiCard icon={<TrendingUp size={16} />} label="Aves Consolidadas" value={formatNumber(totalOfertaCohortes)} color="var(--text)" />
              <KpiCard
                icon={<Activity size={16} />}
                label="Balance vs Mínimo"
                value={formatSignedNumber(balanceCohortes)}
                color={balanceCohortes >= 0 ? 'var(--success)' : 'var(--warning)'}
              />
              <KpiCard icon={<Target size={16} />} label="Focus Próxima Sem." value={proximaSemanaPlan ? formatWeekRange(proximaSemanaPlan) : '-'} color="var(--primary-dark)" />
            </div>
          </div>
        </motion.div>
      )}

      {/* Insights */}
      {insights && insights.length > 0 && (
        <motion.div variants={itemVariants} className="card" style={{
          border: 'none', background: 'transparent', boxShadow: 'none'
        }}>
          <div style={{ padding: '0 0.5rem 1rem 0.5rem', display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
            <h2 style={{ fontSize: '1.2rem', fontWeight: 700, display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
              <TrendingUp size={20} color="var(--primary)" /> Insights e Inteligencia Estratégica
            </h2>
            <span style={{ fontSize: '0.85rem', fontWeight: 600, color: 'var(--primary)', background: 'var(--success-light)', padding: '0.2rem 0.8rem', borderRadius: 20 }}>
              {insights.length} Recomendaci{insights.length !== 1 ? 'ones' : 'ón'}
            </span>
          </div>
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(400px, 1fr))', gap: '1rem' }}>
            <AnimatePresence>
              {insights.map((ins, idx) => {
                const style = INSIGHT_STYLES[ins.tipo] || INSIGHT_STYLES.info
                return (
                  <motion.div
                    key={idx}
                    initial={{ opacity: 0, scale: 0.95 }}
                    animate={{ opacity: 1, scale: 1 }}
                    whileHover={{ scale: 1.02, y: -2, boxShadow: '0 10px 20px rgba(0,0,0,0.06)' }}
                    transition={{ type: 'spring', stiffness: 200, delay: idx * 0.05 }}
                    style={{
                      border: `1px solid ${style.border}`,
                      borderRadius: 16,
                      padding: '1.2rem',
                      background: style.bg,
                      color: style.color,
                      display: 'flex',
                      flexDirection: 'column',
                      justifyContent: 'space-between',
                      boxShadow: '0 4px 6px -1px rgba(0,0,0,0.03)',
                      position: 'relative',
                      overflow: 'hidden'
                    }}>
                    <div style={{
                      position: 'absolute', top: '-10px', right: '-10px', opacity: 0.05,
                      transform: 'rotate(-15deg) scale(2.5)'
                    }}>
                      {style.icon}
                    </div>
                    <div style={{ display: 'flex', alignItems: 'flex-start', gap: 12, position: 'relative', zIndex: 1 }}>
                      <div style={{ marginTop: 2, flexShrink: 0, background: 'rgba(255,255,255,0.7)', padding: 6, borderRadius: '50%', boxShadow: '0 2px 4px rgba(0,0,0,0.05)' }}>{style.icon}</div>
                      <div style={{ flex: 1 }}>
                        <div style={{ fontWeight: 700, fontSize: '0.95rem', marginBottom: 4, display: 'flex', alignItems: 'center', flexWrap: 'wrap', gap: '0.5rem' }}>
                          {ins.titulo}
                          <span style={{
                            fontSize: '0.7rem', fontWeight: 600, textTransform: 'uppercase', letterSpacing: '0.04em',
                            background: 'rgba(0,0,0,0.08)', padding: '2px 8px', borderRadius: 12, display: 'inline-block'
                          }}>
                            {ins.categoria}
                          </span>
                        </div>
                        <div style={{ fontSize: '0.88rem', lineHeight: 1.5, opacity: 0.9 }}>{ins.detalle}</div>
                      </div>
                    </div>
                    {ins.accion && (
                      <div style={{
                        marginTop: 12,
                        padding: '0.6rem 0.8rem',
                        background: 'rgba(255,255,255,0.7)',
                        borderRadius: 8,
                        fontSize: '0.82rem',
                        fontWeight: 500,
                        border: `1px dashed ${style.border}`,
                        display: 'flex', alignItems: 'center', gap: '6px',
                        position: 'relative', zIndex: 1
                      }}>
                         <Activity size={14} /> {ins.accion}
                      </div>
                    )}
                  </motion.div>
                )
              })}
            </AnimatePresence>
          </div>
        </motion.div>
      )}

      {/* Factibilidad */}
      {fact && fact.encontrada && (
        <motion.div variants={itemVariants} className="card"
          style={{
            borderLeft: `4px solid ${fact.deficit_peor ? 'var(--danger)' : 'var(--success)'}`,
            overflow: 'hidden'
          }}>
          <div className="card-header" style={{ background: fact.deficit_peor ? 'linear-gradient(to right, #fef2f2, #ffffff)' : 'linear-gradient(to right, #f0fdf4, #ffffff)' }}>
            <h2 style={{ color: fact.deficit_peor ? '#991b1b' : '#166534' }}>
              {fact.deficit_peor
                ? <AlertCircle size={20} style={{ verticalAlign: 'middle', marginRight: 8, color: '#dc2626' }} />
                : <ShieldCheck size={20} style={{ verticalAlign: 'middle', marginRight: 8, color: '#16a34a' }} />
              }
              Diagnóstico de Factibilidad Productiva
            </h2>
            <div style={{ fontSize: '0.85rem', fontWeight: 600, color: fact.deficit_peor ? '#dc2626' : '#16a34a', background: 'white', padding: '0.2rem 0.8rem', borderRadius: 12, border: `1px solid ${fact.deficit_peor ? '#fca5a5' : '#86efac'}` }}>
              {fact.cobertura_pct_peor}% Escenario Base
            </div>
          </div>
          <div className="card-body">
            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(180px, 1fr))', gap: '1rem', marginBottom: '2rem' }}>
              <KpiCard label="Carga Poblacional" value={formatNumber(fact.pollitos_cargados)} />
              <KpiCard label="Volumen en Oferta" value={formatNumber(fact.total_oferta)} />
              <KpiCard label="Extracción Est. (Mín)" value={formatNumber(fact.disponibles_peor)} color="var(--orange)" />
              <KpiCard label="Extracción Est. (Máx)" value={formatNumber(fact.disponibles_mejor)} color="var(--primary)" />
              
              {fact.deficit_peor ? (
                <motion.div animate={{ scale: [1, 1.02, 1] }} transition={{ repeat: Infinity, duration: 2 }}>
                  <KpiCard label="Déficit Proyectado" value={formatNumber(fact.deficit_peor)} color="var(--danger)" style={{ border: '2px solid rgba(239,68,68,0.3)', background: 'var(--danger-light)' }} />
                </motion.div>
              ) : (
                <KpiCard label="Margen Superávit" value={formatNumber(fact.disponibles_peor - fact.total_oferta)} color="var(--success)" style={{ background: 'var(--success-light)', border: '1px solid rgba(16,185,129,0.3)' }} />
              )}
            </div>

            {/* Tabla de coberturas por tasa */}
            {fact.coberturas && fact.coberturas.length > 0 && (
              <>
                <h3 style={{ fontSize: '0.95rem', fontWeight: 700, marginBottom: '0.8rem', color: 'var(--text)', display: 'flex', alignItems: 'center', gap: '6px' }}>
                  <Activity size={16} color="var(--primary-light)" /> Modelado de Escenarios Dinámicos
                </h3>
                <div className="table-container" style={{ borderRadius: 12, boxShadow: '0 4px 6px -1px rgba(0,0,0,0.05)' }}>
                  <table>
                    <thead style={{ background: 'linear-gradient(to right, #f8fafc, #f1f5f9)' }}>
                      <tr>
                        <th style={{ color: 'var(--text)', fontWeight: 700 }}>Escenario de Rendimiento</th>
                        <th className="text-right" style={{ color: 'var(--text)', fontWeight: 700 }}>Extracción Proyectada</th>
                        <th className="text-right" style={{ color: 'var(--text)', fontWeight: 700 }}>Tasa Cobertura</th>
                        <th style={{ color: 'var(--text)', fontWeight: 700 }}>Evaluación</th>
                      </tr>
                    </thead>
                    <tbody>
                      {fact.coberturas.map((c, idx) => (
                        <motion.tr key={idx} whileHover={{ backgroundColor: 'rgba(241, 245, 249, 0.8)' }} style={{
                          background: c.tasa === peorTasa ? 'rgba(251,146,60,0.08)' : 'white',
                          borderLeft: c.tasa === peorTasa ? '4px solid #f97316' : '4px solid transparent'
                        }}>
                          <td style={{ fontWeight: c.tasa === peorTasa ? 700 : 500, color: c.tasa === peorTasa ? '#9a3412' : 'var(--text)' }}>
                            {c.tasa === peorTasa ? 'Conservador (Mínimo)' : c.tasa === 4.5 ? 'Base (Promedio)' : `Modelado ${c.tasa}%`}
                          </td>
                          <td className="text-right" style={{ fontWeight: 600 }}>{formatNumber(c.disponibles)}</td>
                          <td className="text-right" style={{ fontWeight: 700, fontSize: '0.9rem', color: c.cobertura_pct <= 100 ? '#059669' : '#dc2626' }}>{c.cobertura_pct}%</td>
                          <td>
                            {c.cobertura_pct <= 100
                              ? <span style={{ display: 'inline-flex', alignItems: 'center', gap: 4, background: '#d1fae5', color: '#047857', padding: '2px 8px', borderRadius: 12, fontSize: '0.75rem', fontWeight: 600 }}><CheckCircle2 size={12} /> Factible</span>
                              : <span style={{ display: 'inline-flex', alignItems: 'center', gap: 4, background: '#fee2e2', color: '#b91c1c', padding: '2px 8px', borderRadius: 12, fontSize: '0.75rem', fontWeight: 600 }}><AlertTriangle size={12} /> Excedido</span>
                            }
                          </td>
                        </motion.tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </>
            )}
          </div>
        </motion.div>
      )}

      {/* Planificacion por cohortes */}
      {cohortes && cohortes.cohortes && cohortes.cohortes.length > 0 && (
        <motion.div variants={itemVariants} className="card" style={{
          borderTop: '4px solid var(--warning)',
          borderRadius: 16,
          boxShadow: '0 10px 25px -5px rgba(0,0,0,0.05)'
        }}>
          <div className="card-header" style={{ padding: '1.25rem 1.5rem', background: 'white' }}>
            <h2 style={{ fontSize: '1.2rem', gap: '0.5rem' }}>
              <GitMerge size={20} color="var(--warning)" style={{ filter: 'drop-shadow(0 2px 4px rgba(245, 158, 11, 0.3))' }} /> 
              Matriz de Planificación por Cohortes
            </h2>
            <div style={{ display: 'flex', gap: '0.5rem', alignItems: 'center' }}>
              <span style={{ fontSize: '0.8rem', fontWeight: 600, color: 'var(--text-light)', background: '#f1f5f9', padding: '0.2rem 0.6rem', borderRadius: 12 }}>
                {cohortes.total_cohortes} Bloques
              </span>
              {cohortes.alertas > 0 && (
                <motion.span animate={{ scale: [1, 1.05, 1] }} transition={{ repeat: Infinity, duration: 2 }} style={{ fontSize: '0.8rem', fontWeight: 600, color: '#991b1b', background: '#fee2e2', padding: '0.2rem 0.6rem', borderRadius: 12, display: 'flex', alignItems: 'center', gap: 4 }}>
                  <AlertCircle size={12} /> {cohortes.alertas} Alertas
                </motion.span>
              )}
            </div>
          </div>
          <div className="card-body" style={{ padding: '0 1.5rem 1.5rem' }}>
            <p style={{ fontSize: '0.9rem', color: 'var(--text-light)', marginBottom: '1.5rem', maxWidth: '80%' }}>
              Traducción del cruce operativo en decisiones precisas de planificación temporal. Cada bloque muestra su ventana biológica estimada, el encuadre temporal sugerido y la mejor acción heurística.
            </p>
            <div className="table-container" style={{ borderRadius: 12, boxShadow: '0 4px 6px -1px rgba(0,0,0,0.05)' }}>
              <table className="validacion-cohortes-table">
                <colgroup>
                  <col style={{ width: '16%' }} />
                  <col style={{ width: '16%' }} />
                  <col style={{ width: '16%' }} />
                  <col style={{ width: '15%' }} />
                  <col style={{ width: '11%' }} />
                  <col style={{ width: '12%' }} />
                  <col style={{ width: '14%' }} />
                </colgroup>
                <thead style={{ background: 'linear-gradient(to right, #f8fafc, #f1f5f9)' }}>
                  <tr>
                    <th>Bloque Biológico</th>
                    <th>Horizonte Sugerido</th>
                    <th>Ventana Biológica</th>
                    <th className="text-right">Aves / Proyección</th>
                    <th className="text-right">Desvío</th>
                    <th>Status</th>
                    <th>Heurística</th>
                  </tr>
                </thead>
                <tbody>
                  {cohortes.cohortes.map((c, idx) => {
                    const cfg = NIVEL_CONFIG[c.nivel] || NIVEL_CONFIG.sin_dato
                    const accion = getPlanningAction(c)
                    const brecha = getBrechaConfig(c)
                    const coberturaEsperada = c.cobertura_pct_min != null && c.cobertura_pct_max != null
                      ? `${c.cobertura_pct_max}% a ${c.cobertura_pct_min}%`
                      : '-'
                    return (
                      <motion.tr key={idx} whileHover={{ backgroundColor: 'rgba(248, 250, 252, 0.9)' }} style={{ borderBottom: '1px solid rgba(226,232,240,0.5)' }}>
                        <td style={COHORTE_WRAP_CELL_STYLE}>
                          <div style={{ fontWeight: 700, fontSize: '0.9rem', color: 'var(--text)' }}>
                            {formatDate(c.fecha_desde)} <span style={{ color: 'var(--text-light)', fontWeight: 400 }}>→</span> {formatDate(c.fecha_hasta)}
                          </div>
                          <div style={{ ...COHORTE_META_TEXT_STYLE, fontSize: '0.75rem', marginTop: 6, opacity: 0.85 }}>
                            {c.granjas?.join(', ') || '-'}
                            {c.lotes > 0 && <span style={{ display: 'block', marginTop: 2, fontWeight: 600, color: 'var(--primary)' }}>{c.lotes} lotes vinculados</span>}
                          </div>
                        </td>
                        <td style={{ ...COHORTE_WRAP_CELL_STYLE, fontSize: '0.85rem' }}>
                          <div style={{ fontWeight: 700, color: 'var(--primary-dark)', fontSize: '0.9rem' }}>{getPlanningWeekLabel(c)}</div>
                          <div style={{ ...COHORTE_META_TEXT_STYLE, marginTop: 4, fontSize: '0.75rem' }}>
                            Target Inicial:<br/>{formatRange(c.fecha_objetivo_desde || c.fecha_oferta_desde, c.fecha_objetivo_hasta || c.fecha_oferta_hasta)}
                          </div>
                        </td>
                        <td style={{ ...COHORTE_WRAP_CELL_STYLE, fontSize: '0.85rem' }}>
                          <div style={{ fontWeight: 600, color: 'var(--text)' }}>{formatRange(c.fecha_faena_esperada_desde, c.fecha_faena_esperada_hasta)}</div>
                          <div style={{ ...COHORTE_META_TEXT_STYLE, marginTop: 4, display: 'inline-block', background: 'rgba(0,0,0,0.03)', padding: '2px 6px', borderRadius: 4, fontSize: '0.7rem' }}>
                            Base: {formatNumber(c.pollitos_cargados)} pollitos
                          </div>
                        </td>
                        <td className="text-right" style={{ verticalAlign: 'top' }}>
                          <div style={{ fontWeight: 800, fontSize: '1rem', color: 'var(--text)' }}>{formatNumber(c.aves_en_oferta)}</div>
                          <div style={{ color: 'var(--text-light)', fontSize: '0.7rem', marginTop: 4 }}>
                            Proyección: {formatNumber(c.esperados_faena_min)} - {formatNumber(c.esperados_faena_max)}
                          </div>
                          <div style={{ color: cfg.color, fontSize: '0.75rem', fontWeight: 700, marginTop: 4, background: cfg.bg, display: 'inline-block', padding: '2px 6px', borderRadius: 4 }}>
                            Cob: {coberturaEsperada}
                          </div>
                        </td>
                        <td className="text-right" style={{ verticalAlign: 'top' }}>
                          <span style={{
                            display: 'inline-block',
                            padding: '4px 8px',
                            background: brecha.bg || 'transparent',
                            color: brecha.color,
                            borderRadius: 6,
                            fontWeight: 700,
                            fontSize: '0.8rem',
                            border: `1px solid ${brecha.color}33`
                          }}>
                            {brecha.label}
                          </span>
                        </td>
                        <td style={COHORTE_WRAP_CELL_STYLE}>
                          <span style={{
                            display: 'inline-flex',
                            alignItems: 'center',
                            gap: '4px',
                            padding: '4px 10px',
                            borderRadius: 20,
                            fontSize: '0.75rem',
                            fontWeight: 700,
                            background: cfg.bgGradient || cfg.bg,
                            color: cfg.color,
                            border: `1px solid ${cfg.color}15`,
                            boxShadow: `0 2px 4px ${cfg.color}15`,
                            textTransform: 'uppercase',
                            letterSpacing: '0.04em'
                          }}>
                            {cfg.icon} {cfg.label}
                          </span>
                          {c.motivo && (
                            <div style={{ ...COHORTE_META_TEXT_STYLE, fontSize: '0.7rem', marginTop: 8, lineHeight: 1.4, opacity: 0.9, padding: '4px', background: 'rgba(0,0,0,0.015)', borderRadius: 4 }}>
                              {c.motivo}
                            </div>
                          )}
                        </td>
                        <td style={{ ...COHORTE_WRAP_CELL_STYLE, fontSize: '0.8rem', background: 'rgba(248,250,252,0.4)', borderLeft: '1px solid rgba(226,232,240,0.5)' }}>
                          <div style={{ fontWeight: 700, color: 'var(--text)', marginBottom: 4, display: 'flex', alignItems: 'center', gap: 4 }}>
                            <Box size={14} style={{opacity: 0.5}} /> {accion.titulo}
                          </div>
                          <div style={{ ...COHORTE_META_TEXT_STYLE, fontSize: '0.75rem', lineHeight: 1.4, opacity: 0.85 }}>{accion.detalle}</div>
                        </td>
                      </motion.tr>
                    )
                  })}
                </tbody>
              </table>
            </div>
          </div>
        </motion.div>
      )}

      {/* Consistencia de edad */}
      {consist && consist.total > 0 && (
        <motion.div variants={itemVariants} className="card" style={{ borderTop: '4px solid var(--info)', boxShadow: '0 8px 16px -4px rgba(59, 130, 246, 0.1)' }}>
          <div className="card-header" style={{ background: 'linear-gradient(to right, #eff6ff, #ffffff)' }}>
            <h2 style={{ color: '#1d4ed8' }}><Search size={20} style={{ verticalAlign: 'middle', marginRight: 8, color: '#2563eb' }} /> Anomalías de Consistencia de Edad</h2>
            <span style={{ fontSize: '0.8rem', fontWeight: 600, color: '#1e40af', background: '#dbeafe', padding: '0.2rem 0.8rem', borderRadius: 12 }}>
              {consist.total} discrepancia{consist.total !== 1 ? 's' : ''} mayor a 3 días
            </span>
          </div>
          <div className="card-body">
            <div className="table-container" style={{ borderRadius: 12, boxShadow: '0 4px 6px -1px rgba(0,0,0,0.05)' }}>
              <table>
                <thead style={{ background: '#f8fafc' }}>
                  <tr>
                    <th>Lote #</th>
                    <th>Sector Productivo</th>
                    <th>Galpón</th>
                    <th className="text-right">Edad Declarada (Oferta)</th>
                    <th className="text-right">Edad Modélica (BB)</th>
                    <th className="text-right">Delta</th>
                  </tr>
                </thead>
                <tbody>
                  {consist.alertas.map((a, idx) => (
                    <motion.tr key={idx} whileHover={{ backgroundColor: '#f1f5f9' }}>
                      <td><strong style={{ color: 'var(--primary-dark)', fontSize: '0.95rem' }}>{a.lote}</strong></td>
                      <td style={{ fontWeight: 500 }}>{a.granja}</td>
                      <td style={{ color: 'var(--text-light)' }}>{a.galpon}</td>
                      <td className="text-right" style={{ fontWeight: 600 }}>{a.edad_real} días</td>
                      <td className="text-right" style={{ color: 'var(--text-light)' }}>{a.dias_calculados} días</td>
                      <td className="text-right">
                        <span style={{ background: '#fee2e2', color: '#b91c1c', padding: '2px 8px', borderRadius: 6, fontWeight: 700, fontSize: '0.85rem' }}>
                          {a.diferencia > 0 ? '+' : ''}{a.diferencia} días
                        </span>
                      </td>
                    </motion.tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        </motion.div>
      )}

      {/* Sin cruce posible */}
      {(!tiene_oferta || !tiene_produccion) && (
        <motion.div variants={itemVariants} className="card" style={{ background: 'linear-gradient(135deg, #f8fafc 0%, #f1f5f9 100%)', border: '1px dashed var(--border)' }}>
          <div className="card-body" style={{ textAlign: 'center', padding: '3rem 2rem' }}>
            <Activity size={32} color="var(--text-light)" style={{ marginBottom: 12, opacity: 0.5 }} />
            <p style={{ color: 'var(--text)', fontSize: '1rem', fontWeight: 500 }}>
              {!tiene_oferta && !tiene_produccion && 'En espera de datos matriz (Oferta y BB) para inicializar motor de cruce.'}
              {tiene_oferta && !tiene_produccion && 'Oferta OK. Ingresa el layer de Producción (Pollitos BB) para proyectar el flujo.'}
              {!tiene_oferta && tiene_produccion && 'Producción OK. Ingresa el layer de Oferta para habilitar la conciliación de faena.'}
            </p>
          </div>
        </motion.div>
      )}
    </motion.div>
  )
}

function StatusBadge({ ok, label, detail, iconType }) {
  let ColorIcon = ok ? CheckCircle2 : XCircle;
  if(iconType === 'oferta') ColorIcon = Box;
  if(iconType === 'produccion') ColorIcon = Database;
  if(iconType === 'cruce') ColorIcon = GitMerge;

  return (
    <motion.div 
      whileHover={{ y: -2, boxShadow: '0 4px 6px rgba(0,0,0,0.05)' }}
      style={{
        display: 'flex', alignItems: 'center', gap: 12,
        padding: '0.75rem 1.25rem',
        borderRadius: 12,
        background: ok ? 'linear-gradient(135deg, rgba(34,197,94,0.08) 0%, rgba(34,197,94,0.02) 100%)' : 'linear-gradient(135deg, rgba(239,68,68,0.08) 0%, rgba(239,68,68,0.02) 100%)',
        border: `1px solid ${ok ? 'rgba(34,197,94,0.3)' : 'rgba(239,68,68,0.3)'}`,
        flex: '1 1 min-content',
        whiteSpace: 'nowrap'
      }}
    >
      <div style={{ 
        position: 'relative', 
        background: ok ? 'rgba(34,197,94,0.15)' : 'rgba(239,68,68,0.15)',
        padding: 8, borderRadius: 10, display: 'flex'
      }}>
        {ok && iconType === 'cruce' ? (
          <motion.div animate={{ rotate: 360 }} transition={{ repeat: Infinity, duration: 10, ease: "linear" }}>
            <ColorIcon size={20} color={ok ? "#16a34a" : "#ef4444"} />
          </motion.div>
        ) : (
          <ColorIcon size={20} color={ok ? "#16a34a" : "#ef4444"} />
        )}
      </div>
      <div>
        <div style={{ fontWeight: 700, fontSize: '0.9rem', color: 'var(--text)' }}>{label}</div>
        <div style={{ fontSize: '0.8rem', color: 'var(--text-light)', marginTop: 2 }}>{detail}</div>
      </div>
    </motion.div>
  )
}

function KpiCard({ icon, label, value, color, style = {} }) {
  return (
    <motion.div 
      whileHover={{ scale: 1.03, y: -2, boxShadow: '0 8px 12px rgba(0,0,0,0.05)' }}
      style={{
        background: '#ffffff',
        border: '1px solid var(--border)',
        borderRadius: 12,
        padding: '1rem',
        display: 'flex', flexDirection: 'column',
        position: 'relative',
        overflow: 'hidden',
        boxShadow: '0 2px 4px rgba(0,0,0,0.01)',
        ...style
      }}
    >
      <div style={{ position: 'absolute', top: 0, left: 0, width: 4, height: '100%', background: color || 'var(--primary)' }} />
      <div style={{ fontSize: '0.75rem', color: 'var(--text-light)', marginBottom: 8, display: 'flex', alignItems: 'center', gap: 6, fontWeight: 600, textTransform: 'uppercase', letterSpacing: '0.03em' }}>
        {icon && <span style={{ opacity: 0.7, color: color || 'var(--text-light)' }}>{icon}</span>}
        {label}
      </div>
      <div style={{ fontSize: '1.4rem', fontWeight: 800, color: color || 'var(--text)', letterSpacing: '-0.02em', marginTop: 'auto' }}>
        {value}
      </div>
    </motion.div>
  )
}

function DataSourceCard({ title, icon, source, rows, emptyText }) {
  const mismatch = source?.metadata_matches_persisted === false

  return (
    <motion.div 
      whileHover={{ boxShadow: '0 10px 15px -3px rgba(0,0,0,0.05)' }}
      style={{
        border: `1px solid ${mismatch ? 'rgba(245, 158, 11, 0.45)' : 'rgba(226, 232, 240, 0.8)'}`,
        borderRadius: 16,
        padding: '1.25rem',
        background: mismatch ? 'linear-gradient(135deg, rgba(255, 251, 235, 0.8) 0%, rgba(255, 255, 255, 1) 100%)' : 'linear-gradient(135deg, #ffffff 0%, #f8fafc 100%)',
        position: 'relative'
      }}
    >
      {mismatch && <div style={{ position: 'absolute', top: 0, left: 0, right: 0, height: 4, background: '#f59e0b', borderRadius: '16px 16px 0 0' }} />}
      
      <div style={{ display: 'flex', justifyContent: 'space-between', gap: 12, alignItems: 'center', marginBottom: 16 }}>
        <div style={{ fontWeight: 800, fontSize: '1.05rem', color: 'var(--text)', display: 'flex', alignItems: 'center', gap: 8 }}>
          <span style={{ padding: 6, background: 'rgba(0,0,0,0.03)', borderRadius: 8, color: 'var(--primary)' }}>{icon}</span>
          {title}
        </div>
        <div style={{ fontSize: '0.7rem', color: 'white', background: 'var(--text-light)', padding: '2px 8px', borderRadius: 12, fontWeight: 600, letterSpacing: '0.05em', textTransform: 'uppercase' }}>
          Sistema Persistido
        </div>
      </div>

      <div style={{ background: 'rgba(248,250,252,0.8)', padding: '10px 12px', borderRadius: 10, border: '1px solid rgba(0,0,0,0.03)' }}>
        <div style={{ fontSize: '0.9rem', fontWeight: 700, color: 'var(--primary-dark)', display: 'flex', alignItems: 'center', gap: 6 }}>
          {source?.filename || 'Sin archivo registrado en matriz'}
        </div>
        <div style={{ fontSize: '0.75rem', color: 'var(--text-light)', marginTop: 6, display: 'flex', alignItems: 'center', gap: 4 }}>
          <Clock size={12} /> Actualización: <span style={{ fontWeight: 600 }}>{formatDateTime(source?.uploaded_at)}</span>
        </div>
        {source?.sheet_name && (
          <div style={{ fontSize: '0.75rem', color: 'var(--text-light)', marginTop: 4, display: 'flex', alignItems: 'center', gap: 4 }}>
            <Database size={12} /> Hoja de cálculo: <span style={{ fontWeight: 600 }}>{source.sheet_name}</span>
          </div>
        )}
        {!source?.filename && (
          <div style={{ fontSize: '0.8rem', color: 'var(--text-light)', marginTop: 8, fontStyle: 'italic' }}>
            {emptyText}
          </div>
        )}
      </div>

      <div style={{ display: 'grid', gap: 8, marginTop: '1rem', padding: '0 4px' }}>
        {rows.map((row) => (
          <div key={row.label} style={{ display: 'flex', justifyContent: 'space-between', gap: 12, fontSize: '0.85rem', alignItems: 'center', borderBottom: '1px dashed rgba(226,232,240,0.6)', paddingBottom: '6px' }}>
            <span style={{ color: 'var(--text-light)', fontWeight: 500 }}>{row.label}</span>
            <span style={{ textAlign: 'right', color: 'var(--text)', fontWeight: 700 }}>{row.value || '-'}</span>
          </div>
        ))}
      </div>

      {typeof source?.total_descartadas === 'number' && source.total_descartadas > 0 && (
        <motion.div initial={{ opacity: 0 }} animate={{ opacity: 1 }} style={{ fontSize: '0.8rem', color: '#9a3412', marginTop: '1rem', background: '#fff7ed', padding: '6px 12px', borderRadius: 8, display: 'flex', alignItems: 'center', gap: 6, fontWeight: 600 }}>
          <AlertTriangle size={14} /> Filtro Ingesta: {formatNumber(source.total_descartadas)} descartes
        </motion.div>
      )}

      {mismatch && (
        <motion.div initial={{ opacity: 0 }} animate={{ opacity: 1 }} style={{ fontSize: '0.8rem', color: '#92400e', marginTop: '1rem', lineHeight: 1.5, background: '#fef3c7', padding: '10px 12px', borderRadius: 8, border: '1px solid #fde68a' }}>
          <strong>⚠️ Trazabilidad en riesgo:</strong> El resumen pre-calculado difiere de la metadata física. Se aconseja recargar archivo matriz.
        </motion.div>
      )}
    </motion.div>
  )
}
