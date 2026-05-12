import React, { useState, useEffect } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import { AlertTriangle, AlertCircle, Info, TrendingUp, Loader2, RefreshCw, CheckCircle2, XCircle, Search, GitMerge, Activity, BarChart3, Clock, Database, Target, Box } from 'lucide-react'
import { getValidacionCruzada } from '../services/api'

// --- Premium Animation Variants ---
const containerVariants = {
  hidden: { opacity: 0 },
  show: { opacity: 1, transition: { staggerChildren: 0.08, delayChildren: 0.05, ease: 'easeOut' } }
}
const itemVariants = {
  hidden: { opacity: 0, y: 20, filter: 'blur(8px)', scale: 0.98 },
  show: { opacity: 1, y: 0, filter: 'blur(0px)', scale: 1, transition: { type: 'spring', stiffness: 120, damping: 20 } }
}
const floatHover = {
  scale: 1.015,
  y: -4,
  boxShadow: '0 20px 25px -5px rgba(0, 0, 0, 0.1), 0 10px 10px -5px rgba(0, 0, 0, 0.04)',
  borderColor: 'rgba(255,255,255,0.9)',
  transition: { type: 'spring', stiffness: 300, damping: 20 }
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

const INSIGHT_STYLES = {
  critico: { border: '#fca5a5', bg: 'linear-gradient(135deg, rgba(254, 242, 242, 0.9) 0%, rgba(255, 255, 255, 0.9) 100%)', color: '#991b1b', icon: <XCircle size={22} color="#dc2626" /> },
  advertencia: { border: '#fcd34d', bg: 'linear-gradient(135deg, rgba(255, 251, 235, 0.9) 0%, rgba(255, 255, 255, 0.9) 100%)', color: '#92400e', icon: <AlertTriangle size={22} color="#d97706" /> },
  positivo: { border: '#86efac', bg: 'linear-gradient(135deg, rgba(240, 253, 244, 0.9) 0%, rgba(255, 255, 255, 0.9) 100%)', color: '#166534', icon: <CheckCircle2 size={22} color="#16a34a" /> },
  info: { border: '#93c5fd', bg: 'linear-gradient(135deg, rgba(239, 246, 255, 0.9) 0%, rgba(255, 255, 255, 0.9) 100%)', color: '#1e40af', icon: <Info size={22} color="#2563eb" /> },
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
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', height: '65vh', flexDirection: 'column', gap: '2.5rem' }}>
        <div style={{ position: 'relative', width: 120, height: 120, display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
          {/* Anillos exteriores animados */}
          <motion.div
            animate={{ scale: [1, 1.25, 1], opacity: [0.3, 0.05, 0.3] }}
            transition={{ duration: 2.5, repeat: Infinity, ease: "easeInOut" }}
            style={{ position: 'absolute', width: '100%', height: '100%', borderRadius: '50%', border: '4px solid var(--primary-light)' }}
          />
          <motion.div
            animate={{ scale: [1, 1.5, 1], opacity: [0.15, 0, 0.15] }}
            transition={{ duration: 2.5, repeat: Infinity, ease: "easeInOut", delay: 0.2 }}
            style={{ position: 'absolute', width: '100%', height: '100%', borderRadius: '50%', border: '4px solid var(--primary-light)' }}
          />
          <motion.div
            animate={{ rotate: 360 }}
            transition={{ duration: 12, repeat: Infinity, ease: "linear" }}
            style={{ position: 'absolute', width: '110%', height: '110%', borderRadius: '50%', border: '2px dashed var(--primary)', opacity: 0.4 }}
          />
          <motion.div
            animate={{ rotate: -360 }}
            transition={{ duration: 16, repeat: Infinity, ease: "linear" }}
            style={{ position: 'absolute', width: '125%', height: '125%', borderRadius: '50%', border: '1px dashed var(--primary-light)', opacity: 0.3 }}
          />
          
          {/* Icono central */}
          <motion.div
            animate={{ scale: [1, 1.05, 1], boxShadow: ['0 10px 25px rgba(26,86,50,0.3)', '0 15px 35px rgba(26,86,50,0.5)', '0 10px 25px rgba(26,86,50,0.3)'] }}
            transition={{ duration: 2.5, repeat: Infinity, ease: "easeInOut" }}
            style={{ 
              background: 'linear-gradient(135deg, var(--primary) 0%, var(--primary-dark) 100%)', 
              width: 72, height: 72, borderRadius: '50%', display: 'flex', alignItems: 'center', justifyContent: 'center',
              zIndex: 10,
              border: '3px solid white'
            }}
          >
            <GitMerge size={34} color="white" style={{ filter: 'drop-shadow(0 2px 4px rgba(0,0,0,0.2))' }} />
          </motion.div>
        </div>

        <div style={{ textAlign: 'center', display: 'flex', flexDirection: 'column', gap: '0.4rem' }}>
          <motion.h3
            animate={{ opacity: [0.8, 1, 0.8] }}
            transition={{ duration: 2.5, repeat: Infinity, ease: "easeInOut" }}
            style={{ 
              fontSize: '1.4rem', fontWeight: 800, letterSpacing: '-0.01em', margin: 0,
              background: 'linear-gradient(135deg, var(--primary-dark) 0%, var(--primary) 100%)',
              WebkitBackgroundClip: 'text', WebkitTextFillColor: 'transparent'
            }}
          >
            Sincronizando Operativa
          </motion.h3>
          <motion.div
            initial={{ opacity: 0, y: 10 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: 0.3, duration: 0.5 }}
            style={{ color: 'var(--text-light)', fontSize: '0.95rem', fontWeight: 500, display: 'flex', alignItems: 'center', justifyContent: 'center', gap: '0.6rem' }}
          >
            <motion.div animate={{ rotate: 360 }} transition={{ repeat: Infinity, duration: 2, ease: "linear" }} style={{ display: 'flex', alignItems: 'center' }}>
              <Loader2 size={16} style={{ opacity: 0.7 }} />
            </motion.div>
            Cruzando datos de Oferta y Producción BB...
          </motion.div>
        </div>
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
            initial={{ scale: 0.9, opacity: 0 }}
            animate={{ scale: 1, opacity: 1 }}
            transition={{ type: 'spring', stiffness: 100, damping: 20 }}
            style={{ marginBottom: 20, display: 'inline-block', background: 'var(--bg)', padding: '1.5rem', borderRadius: '50%', boxShadow: '0 10px 25px rgba(0,0,0,0.05)' }}
          >
            <GitMerge size={56} color="var(--primary-light)" style={{ filter: 'drop-shadow(0 4px 6px rgba(45,138,78,0.2))' }} />
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

  const { validacion, insights, fuentes, planificacion, tiene_oferta, tiene_produccion, total_ofertas, total_semanas_produccion } = data
  const cohortes = validacion?.mortalidad_cohortes
  const consist = validacion?.consistencia_edad
  const concentracion = validacion?.concentracion_granjas
  const cohortesList = cohortes?.cohortes || []
  const cohortesEnVentana = cohortesList.filter(c => c.estado_fecha === 'alineada')
  const cohortesReprogramar = cohortesList.filter(c => c.nivel === 'anticipada' || c.nivel === 'mixta')
  const cohortesPrioridad = cohortesList.filter(c => c.nivel === 'atrasada' || c.nivel === 'excedida')
  const totalOfertaCohortes = cohortesList.reduce((acc, c) => acc + (c.aves_en_oferta || 0), 0)
  const totalEsperadoMinCohortes = cohortesList.reduce((acc, c) => acc + (c.esperados_faena_min || 0), 0)
  const balanceCohortes = totalOfertaCohortes - totalEsperadoMinCohortes
  const fechaInicioPlanificacion = planificacion?.fecha_inicio
  const proximaSemanaPlan = fechaInicioPlanificacion || (cohortesList.length > 0
    ? cohortesList
      .map(c => c.fecha_objetivo_desde || c.fecha_faena_esperada_desde)
      .filter(Boolean)
      .sort()[0]
    : null)
  const proximaSemanaPlanEsActiva = Boolean(fechaInicioPlanificacion)
  const proximaSemanaPlanLabel = proximaSemanaPlan ? formatWeekRange(proximaSemanaPlan) : '-'

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
          <motion.button whileHover={{ scale: 1.05, y: -1, boxShadow: '0 4px 10px rgba(0,0,0,0.1)' }} whileTap={{ scale: 0.95 }} className="btn btn-sm btn-outline" onClick={cargar} style={{ borderRadius: 20, transition: 'background 0.2s, color 0.2s, border 0.2s' }}>
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
              {proximaSemanaPlan && (
                <span> {proximaSemanaPlanEsActiva ? 'La planificación activa inicia' : 'La programación más inminente inicia'} la semana del <strong style={{ color: 'var(--primary)' }}>{proximaSemanaPlanLabel}</strong>.</span>
              )}
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
              <KpiCard icon={<Target size={16} />} label={proximaSemanaPlanEsActiva ? "Semana Planificada" : "Focus Próxima Sem."} value={proximaSemanaPlanLabel} color="var(--primary-dark)" />
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
                    whileHover={{ scale: 1.02, y: -4, boxShadow: '0 15px 30px -5px rgba(0,0,0,0.1)' }}
                    transition={{ type: 'spring', stiffness: 250, damping: 25, delay: idx * 0.05 }}
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

      {/* Concentración por Granja */}
      {concentracion && concentracion.granjas?.length > 0 && (
        <motion.div variants={itemVariants} className="card" style={{
          borderLeft: `4px solid ${concentracion.max_pct >= 40 ? 'var(--warning)' : 'var(--primary-light)'}`,
          overflow: 'hidden'
        }}>
          <div className="card-header" style={{ background: 'linear-gradient(to right, #f8fafc, #ffffff)' }}>
            <h2 style={{ fontSize: '1.15rem' }}>
              <Target size={18} style={{ marginRight: 8, color: 'var(--primary-light)' }} />
              Perfil de Concentración por Granja
            </h2>
            <span style={{ fontSize: '0.85rem', fontWeight: 600, color: 'var(--text-light)', background: '#f1f5f9', padding: '0.2rem 0.6rem', borderRadius: 12 }}>
              {concentracion.total_granjas} granja{concentracion.total_granjas !== 1 ? 's' : ''} · {formatNumber(concentracion.total_aves)} aves
            </span>
          </div>
          <div className="card-body">
            <div style={{ background: 'linear-gradient(135deg, #f0fdf4 0%, #ecfdf5 50%, #f0fdf4 100%)', borderRadius: 10, padding: '1rem 1.25rem', marginBottom: '1.25rem', border: '1px solid #bbf7d0', fontSize: '0.82rem', color: '#14532d', lineHeight: 1.6 }}>
              <div style={{ fontWeight: 700, marginBottom: 6, display: 'flex', alignItems: 'center', gap: 6, color: '#166534' }}>
                <Info size={14} /> ¿Cómo interpretar esta tabla?
              </div>
              <p style={{ margin: '0 0 6px 0' }}>
                Esta tabla desglosa la <strong>oferta de faena por granja</strong>, mostrando cómo se distribuye el volumen total entre los distintos proveedores. Permite identificar dependencias operativas y planificar la logística de retiro.
              </p>
              <ul style={{ margin: '4px 0 0 0', paddingLeft: '1.2rem', listStyle: 'disc' }}>
                <li><strong>Aves</strong>: Total de aves que la granja ofrece para faena en esta carga.</li>
                <li><strong>% Oferta</strong>: Proporción sobre el total de aves ofertadas. Si una sola granja supera el 40%, existe riesgo de concentración — cualquier problema en esa granja impactaría fuertemente la planificación.</li>
                <li><strong>Lotes</strong>: Cantidad de galpones o lotes distintos que la granja pone a disposición. Más lotes implica mayor flexibilidad para escalonar retiros.</li>
                <li><strong>Edad Prom.</strong>: Edad real promedio (en días) de las aves de esa granja, ponderada por cantidad. Aves más viejas tienen prioridad de faena; edades dispares entre granjas sugieren que se pueden secuenciar los retiros.</li>
                <li><strong>Peso Prom.</strong>: Peso de muestreo real promedio (en kg), ponderado por cantidad. Indica la categoría de producto esperada y ayuda a proyectar el rendimiento en planta.</li>
                <li><strong>Sexo</strong>: Sexo predominante en los lotes de la granja. Machos y hembras tienen rendimientos de faena distintos, lo que afecta la planificación de línea.</li>
                <li><strong>Cohorte Producción</strong>: Semana(s) de producción BB de donde provienen las aves. Vincula la oferta con el origen biológico y permite rastrear trazabilidad.</li>
              </ul>
            </div>
            {concentracion.max_pct >= 40 && (
              <div style={{ background: 'linear-gradient(135deg, #fffbeb 0%, #fef9c3 100%)', borderRadius: 10, padding: '0.8rem 1rem', marginBottom: '1rem', border: '1px solid #fde68a', fontSize: '0.82rem', color: '#78350f', display: 'flex', alignItems: 'center', gap: 8 }}>
                <AlertTriangle size={16} style={{ flexShrink: 0 }} />
                <span>Alta concentración: <strong>{concentracion.granjas[0].granja}</strong> representa el <strong>{concentracion.max_pct}%</strong> de la oferta total. Considerar diversificación de proveedores.</span>
              </div>
            )}
            <div className="table-container" style={{ borderRadius: 12, boxShadow: '0 4px 6px -1px rgba(0,0,0,0.05)' }}>
              <table>
                <thead style={{ background: 'linear-gradient(to right, #f8fafc, #f1f5f9)' }}>
                  <tr>
                    <th style={{ fontWeight: 700 }}>Granja</th>
                    <th className="text-right" style={{ fontWeight: 700 }}>Aves</th>
                    <th className="text-right" style={{ fontWeight: 700 }}>% Oferta</th>
                    <th className="text-right" style={{ fontWeight: 700 }}>Lotes</th>
                    <th className="text-right" style={{ fontWeight: 700 }}>Edad Prom.</th>
                    <th className="text-right" style={{ fontWeight: 700 }}>Peso Prom.</th>
                    <th style={{ fontWeight: 700 }}>Sexo</th>
                    <th style={{ fontWeight: 700 }}>Cohorte Producción</th>
                  </tr>
                </thead>
                <tbody>
                  {concentracion.granjas.map((g, idx) => (
                    <motion.tr key={idx} whileHover={{ backgroundColor: 'rgba(241, 245, 249, 0.8)' }}>
                      <td style={{ fontWeight: 700, color: 'var(--text)' }}>{g.granja}</td>
                      <td className="text-right" style={{ fontWeight: 600 }}>{formatNumber(g.aves)}</td>
                      <td className="text-right">
                        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'flex-end', gap: 6 }}>
                          <div style={{ width: 48, height: 6, borderRadius: 3, background: '#e2e8f0', overflow: 'hidden' }}>
                            <div style={{ width: `${Math.min(g.pct, 100)}%`, height: '100%', borderRadius: 3, background: g.pct >= 40 ? '#f59e0b' : g.pct >= 25 ? '#3b82f6' : '#94a3b8' }} />
                          </div>
                          <span style={{ fontWeight: 700, fontSize: '0.85rem', color: g.pct >= 40 ? '#b45309' : 'var(--text)' }}>{g.pct}%</span>
                        </div>
                      </td>
                      <td className="text-right" style={{ color: 'var(--text-light)' }}>{g.lotes}</td>
                      <td className="text-right" style={{ fontWeight: 500 }}>{g.edad_prom != null ? `${g.edad_prom} d` : '-'}</td>
                      <td className="text-right" style={{ fontWeight: 500 }}>{g.peso_prom != null ? `${g.peso_prom.toFixed(2)} kg` : '-'}</td>
                      <td>
                        {g.sexo_predominante
                          ? <span style={{ fontSize: '0.75rem', fontWeight: 600, padding: '2px 8px', borderRadius: 10, background: g.sexo_predominante === 'M' ? '#dbeafe' : g.sexo_predominante === 'H' ? '#fce7f3' : '#f3e8ff', color: g.sexo_predominante === 'M' ? '#1e40af' : g.sexo_predominante === 'H' ? '#9d174d' : '#6b21a8' }}>
                              {g.sexo_predominante === 'M' ? 'Macho' : g.sexo_predominante === 'H' ? 'Hembra' : 'Mixto'}
                            </span>
                          : <span style={{ color: 'var(--text-light)', fontSize: '0.8rem' }}>-</span>
                        }
                      </td>
                      <td style={{ fontSize: '0.78rem', color: 'var(--text-light)', maxWidth: 180 }}>
                        {g.cohortes.length > 0
                          ? g.cohortes.map((c, i) => <div key={i} style={{ whiteSpace: 'nowrap' }}>{c}</div>)
                          : <span style={{ fontStyle: 'italic' }}>Sin vínculo</span>
                        }
                      </td>
                    </motion.tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        </motion.div>
      )}

      {/* Validación Producción → Faena */}
      {cohortesList.length > 0 && (
        <motion.div variants={itemVariants} className="card" style={{
          borderLeft: '4px solid var(--primary)',
          borderRadius: 16,
          boxShadow: '0 10px 25px -5px rgba(0,0,0,0.05)'
        }}>
          <div className="card-header" style={{ padding: '1.25rem 1.5rem', background: 'white' }}>
            <h2 style={{ fontSize: '1.2rem', gap: '0.5rem' }}>
              <GitMerge size={20} color="var(--primary)" style={{ filter: 'drop-shadow(0 2px 4px rgba(26,86,50,0.2))' }} />
              Validación de Coherencia: Producción → Faena
            </h2>
            <span style={{ fontSize: '0.85rem', fontWeight: 600, color: 'var(--text-light)', background: '#f1f5f9', padding: '0.2rem 0.6rem', borderRadius: 12 }}>
              {cohortesList.length} semana{cohortesList.length !== 1 ? 's' : ''} cruzada{cohortesList.length !== 1 ? 's' : ''}
            </span>
          </div>
          <div className="card-body" style={{ padding: '0 1.5rem 1.5rem' }}>
            <div style={{ background: 'linear-gradient(135deg, #eff6ff 0%, #f0f9ff 50%, #eff6ff 100%)', borderRadius: 10, padding: '1rem 1.25rem', marginBottom: '1.25rem', border: '1px solid #bfdbfe', fontSize: '0.82rem', color: '#1e3a5f', lineHeight: 1.6 }}>
              <div style={{ fontWeight: 700, marginBottom: 6, display: 'flex', alignItems: 'center', gap: 6, color: '#1d4ed8' }}>
                <Info size={14} /> ¿Cómo leer esta tabla?
              </div>
              <p style={{ margin: '0 0 6px 0' }}>
                Cada fila representa una <strong>semana de producción</strong> del archivo de Pollitos BB. Se toman los pollitos cargados en granjas propias esa semana, se proyectan <strong>42 días de engorde</strong> y se descuenta una merma estimada del 4,5% al 7,5% para obtener el rango de aves que deberían llegar a faena. Luego se compara contra las aves que efectivamente aparecen en la oferta (vinculadas por su fecha de ingreso).
              </p>
              <ul style={{ margin: '4px 0 0 0', paddingLeft: '1.2rem', listStyle: 'disc' }}>
                <li><strong>Pollitos Cargados</strong>: Cantidad de pollitos BB enviados a granjas propias esa semana (dato del archivo de producción).</li>
                <li><strong>Esperados en Faena</strong>: Rango de aves que deberían llegar a planta tras 42 días, descontando entre 4,5% (mejor caso) y 7,5% (peor caso) de mortalidad.</li>
                <li><strong>Aves en Oferta</strong>: Cantidad de aves que las granjas efectivamente ofrecen para faena, cuyos lotes tienen fecha de ingreso dentro de esa semana de producción.</li>
                <li><strong>Diferencia</strong>: Aves en oferta menos el límite inferior del rango esperado. Un valor positivo indica que se ofrecen más aves de las esperadas; uno negativo, menos.</li>
                <li><strong>Veredicto</strong>: <em>Coherente</em> si la oferta cae dentro del rango esperado; <em>Excede</em> si supera el máximo; <em>Insuficiente</em> si no alcanza el mínimo.</li>
              </ul>
            </div>
            <div className="table-container" style={{ borderRadius: 12, boxShadow: '0 4px 6px -1px rgba(0,0,0,0.05)' }}>
              <table>
                <thead style={{ background: 'linear-gradient(to right, #f8fafc, #f1f5f9)' }}>
                  <tr>
                    <th style={{ fontWeight: 700 }}>Semana Producción</th>
                    <th className="text-right" style={{ fontWeight: 700 }}>Pollitos Cargados</th>
                    <th className="text-right" style={{ fontWeight: 700 }}>Esperados en Faena</th>
                    <th className="text-right" style={{ fontWeight: 700 }}>Aves en Oferta</th>
                    <th className="text-right" style={{ fontWeight: 700 }}>Diferencia</th>
                    <th style={{ fontWeight: 700 }}>Veredicto</th>
                  </tr>
                </thead>
                <tbody>
                  {cohortesList.map((c, idx) => {
                    const enRango = c.aves_en_oferta >= (c.esperados_faena_min || 0) && c.aves_en_oferta <= (c.esperados_faena_max || Infinity)
                    const excede = c.aves_en_oferta > (c.esperados_faena_max || Infinity)
                    const insuficiente = c.aves_en_oferta < (c.esperados_faena_min || 0)
                    const diff = c.aves_en_oferta - (c.esperados_faena_min || 0)
                    return (
                      <motion.tr key={idx} whileHover={{ backgroundColor: 'rgba(241, 245, 249, 0.8)' }} style={{ borderBottom: '1px solid rgba(226,232,240,0.5)' }}>
                        <td>
                          <div style={{ fontWeight: 700, fontSize: '0.9rem', color: 'var(--text)' }}>
                            {formatDate(c.fecha_desde)} → {formatDate(c.fecha_hasta)}
                          </div>
                          <div style={{ fontSize: '0.73rem', color: 'var(--text-light)', marginTop: 4 }}>
                            Faena esperada: {formatDate(c.fecha_faena_esperada_desde)} → {formatDate(c.fecha_faena_esperada_hasta)}
                          </div>
                          {c.granjas && c.granjas.length > 0 && (
                            <div style={{ fontSize: '0.72rem', color: 'var(--primary)', marginTop: 2, fontWeight: 500 }}>
                              {c.granjas.join(', ')} · {c.lotes} lote{c.lotes !== 1 ? 's' : ''}
                            </div>
                          )}
                        </td>
                        <td className="text-right" style={{ fontWeight: 700, fontSize: '1rem' }}>
                          {formatNumber(c.pollitos_cargados)}
                        </td>
                        <td className="text-right">
                          <div style={{ fontWeight: 600 }}>{formatNumber(c.esperados_faena_min)} – {formatNumber(c.esperados_faena_max)}</div>
                          <div style={{ fontSize: '0.7rem', color: 'var(--text-light)', marginTop: 2 }}>merma 4,5% a 7,5%</div>
                        </td>
                        <td className="text-right" style={{ fontWeight: 800, fontSize: '1rem', color: 'var(--text)' }}>
                          {formatNumber(c.aves_en_oferta)}
                        </td>
                        <td className="text-right">
                          <span style={{
                            display: 'inline-block', padding: '3px 8px', borderRadius: 6, fontWeight: 700, fontSize: '0.85rem',
                            background: enRango ? '#d1fae5' : excede ? '#fee2e2' : '#fef3c7',
                            color: enRango ? '#047857' : excede ? '#b91c1c' : '#92400e',
                            border: `1px solid ${enRango ? '#6ee7b7' : excede ? '#fca5a5' : '#fcd34d'}33`
                          }}>
                            {diff > 0 ? '+' : ''}{formatNumber(diff)}
                          </span>
                        </td>
                        <td>
                          <span style={{
                            display: 'inline-flex', alignItems: 'center', gap: 4, padding: '4px 10px',
                            borderRadius: 20, fontSize: '0.75rem', fontWeight: 700, textTransform: 'uppercase', letterSpacing: '0.04em',
                            background: enRango ? '#d1fae5' : excede ? '#fee2e2' : '#fef3c7',
                            color: enRango ? '#047857' : excede ? '#b91c1c' : '#92400e',
                          }}>
                            {enRango && <><CheckCircle2 size={12} /> Coherente</>}
                            {excede && <><AlertTriangle size={12} /> Excede</>}
                            {insuficiente && <><AlertCircle size={12} /> Insuficiente</>}
                          </span>
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
            <div style={{ background: 'linear-gradient(135deg, #eff6ff 0%, #f0f9ff 100%)', borderRadius: 10, padding: '1rem 1.25rem', marginBottom: '1.25rem', border: '1px solid #bfdbfe', fontSize: '0.82rem', color: '#1e3a5f', lineHeight: 1.6 }}>
              <div style={{ fontWeight: 700, marginBottom: 6, display: 'flex', alignItems: 'center', gap: 6, color: '#1d4ed8' }}>
                <Info size={14} /> ¿Cómo interpretar esta tabla?
              </div>
              <p style={{ margin: '0 0 6px 0' }}>
                Esta sección detecta <strong>inconsistencias</strong> entre la edad que la granja declara para un lote (<em>Edad Declarada</em>) y la edad que resulta de restar la fecha de ingreso del pollito BB a la granja de la fecha en que fue pesado (<em>Edad Modélica</em>). Si ambos datos fueran perfectos, deberían coincidir.
              </p>
              <ul style={{ margin: '4px 0 0 0', paddingLeft: '1.2rem', listStyle: 'disc' }}>
                <li><strong>Lote #</strong>: Número de fila del lote en el archivo de oferta cargado (1 = primera fila de datos).</li>
                <li><strong>Sector Productivo / Galpón</strong>: Granja y galpón de origen del lote.</li>
                <li><strong>Edad Declarada (Oferta)</strong>: Valor del campo EDAD REAL (col. K) del Excel de oferta — la edad en días informada por la granja al momento del pesaje.</li>
                <li><strong>Edad Modélica (BB)</strong>: Edad calculada como <code style={{ background: '#dbeafe', padding: '1px 4px', borderRadius: 3 }}>Fecha de Peso − Fecha de Ingreso</code> (cols. A y M del Excel). Representa cuántos días debería tener el ave según sus fechas de registro.</li>
                <li><strong>Delta</strong>: Diferencia = Edad Modélica − Edad Declarada. Un valor <strong>positivo</strong> (ej. +8) indica que las fechas sugieren un ave <em>más vieja</em> de lo declarado; un valor <strong>negativo</strong> indicaría lo contrario. Solo se muestran diferencias mayores a 3 días.</li>
              </ul>
              <p style={{ margin: '6px 0 0 0', fontStyle: 'italic', opacity: 0.85 }}>
                💡 Acción sugerida: verificar en el Excel original si la Fecha de Ingreso o la Edad Real del lote señalado tienen un error de carga.
              </p>
            </div>
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
                  {consist.alertas.map((a, idx) => {
                    const deltaPositivo = a.diferencia > 0
                    return (
                      <motion.tr key={idx} whileHover={{ backgroundColor: '#f1f5f9' }}>
                        <td><strong style={{ color: 'var(--primary-dark)', fontSize: '0.95rem' }}>{a.lote}</strong></td>
                        <td style={{ fontWeight: 500 }}>{a.granja}</td>
                        <td style={{ color: 'var(--text-light)' }}>{a.galpon}</td>
                        <td className="text-right" style={{ fontWeight: 600 }}>{a.edad_real} días</td>
                        <td className="text-right" style={{ color: 'var(--text-light)' }}>{a.dias_calculados} días</td>
                        <td className="text-right">
                          <span style={{ background: deltaPositivo ? '#fee2e2' : '#fef3c7', color: deltaPositivo ? '#b91c1c' : '#92400e', padding: '2px 8px', borderRadius: 6, fontWeight: 700, fontSize: '0.85rem' }}>
                            {a.diferencia > 0 ? '+' : ''}{a.diferencia} días
                          </span>
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
      whileHover={{ scale: 1.02, y: -2, boxShadow: '0 8px 15px -3px rgba(0,0,0,0.08)' }}
      transition={{ type: 'spring', stiffness: 300, damping: 20 }}
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
        <ColorIcon size={20} color={ok ? "#16a34a" : "#ef4444"} />
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
      whileHover={{ scale: 1.02, y: -4, boxShadow: '0 12px 20px -5px rgba(0,0,0,0.08), 0 8px 10px -6px rgba(0,0,0,0.04)' }}
      transition={{ type: 'spring', stiffness: 300, damping: 20 }}
      style={{
        background: 'linear-gradient(180deg, rgba(255,255,255,1) 0%, rgba(250,252,254,1) 100%)',
        border: '1px solid var(--border)',
        borderRadius: 14,
        padding: '1.2rem',
        display: 'flex', flexDirection: 'column',
        position: 'relative',
        overflow: 'hidden',
        boxShadow: '0 4px 6px -1px rgba(0,0,0,0.03)',
        ...style
      }}
    >
      <div style={{ position: 'absolute', top: 0, left: 0, width: 4, height: '100%', background: color || 'var(--primary)', opacity: 0.85 }} />
      <div style={{ fontSize: '0.75rem', color: 'var(--text-light)', marginBottom: 10, display: 'flex', alignItems: 'center', gap: 6, fontWeight: 700, textTransform: 'uppercase', letterSpacing: '0.04em' }}>
        {icon && <span style={{ opacity: 0.8, color: color || 'var(--text-light)', display: 'flex', background: 'rgba(0,0,0,0.03)', padding: '4px', borderRadius: '6px' }}>{icon}</span>}
        {label}
      </div>
      <div style={{ fontSize: '1.55rem', fontWeight: 800, color: color || 'var(--text)', letterSpacing: '-0.02em', marginTop: 'auto', textShadow: '0 1px 2px rgba(0,0,0,0.02)' }}>
        {value}
      </div>
    </motion.div>
  )
}

function DataSourceCard({ title, icon, source, rows, emptyText }) {
  const mismatch = source?.metadata_matches_persisted === false

  return (
    <motion.div 
      whileHover={{ scale: 1.01, y: -2, boxShadow: '0 15px 25px -5px rgba(0,0,0,0.08)' }}
      transition={{ type: 'spring', stiffness: 300, damping: 20 }}
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
