import React, { useState, useEffect } from 'react'
import { motion } from 'framer-motion'
import { ShieldCheck, AlertTriangle, AlertCircle, Info, TrendingUp, Loader2, RefreshCw, CheckCircle2, XCircle, Search } from 'lucide-react'
import { getValidacionCruzada } from '../services/api'

const containerVariants = {
  hidden: { opacity: 0 },
  show: { opacity: 1, transition: { staggerChildren: 0.08 } }
}
const itemVariants = {
  hidden: { opacity: 0, y: 15 },
  show: { opacity: 1, y: 0, transition: { duration: 0.3 } }
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
  if (cohorte.nivel === 'atrasada') return 'Revision inmediata'
  return formatWeekRange(cohorte.fecha_objetivo_desde || cohorte.fecha_faena_esperada_desde)
}

function getBrechaConfig(cohorte) {
  if (cohorte.estado_cantidad === 'por_encima') {
    return {
      label: `${formatSignedNumber(cohorte.diferencia_vs_max)} vs max`,
      color: 'var(--danger)'
    }
  }
  if (cohorte.diferencia_vs_min == null) {
    return { label: '-', color: 'var(--text-light)' }
  }
  return {
    label: `${formatSignedNumber(cohorte.diferencia_vs_min)} vs min`,
    color: cohorte.diferencia_vs_min < 0 ? 'var(--warning)' : 'var(--success)'
  }
}

const NIVEL_CONFIG = {
  alineada: { label: 'Alineada', color: '#16a34a', bg: '#f0fdf4', icon: '🟢' },
  parcial: { label: 'Parcial', color: '#6b7280', bg: '#f9fafb', icon: '⚪' },
  anticipada: { label: 'Anticipada', color: '#d97706', bg: '#fffbeb', icon: '🟡' },
  atrasada: { label: 'Atrasada', color: '#ea580c', bg: '#fff7ed', icon: '🟠' },
  mixta: { label: 'Mixta', color: '#2563eb', bg: '#eff6ff', icon: '🔵' },
  excedida: { label: 'Excedida', color: '#dc2626', bg: '#fef2f2', icon: '🔴' },
  sin_dato: { label: 'Sin dato', color: '#9ca3af', bg: '#f9fafb', icon: '⚫' },
}

const INSIGHT_STYLES = {
  critico: { border: '#fca5a5', bg: '#fef2f2', color: '#991b1b', icon: <XCircle size={18} color="#dc2626" /> },
  advertencia: { border: '#fcd34d', bg: '#fffbeb', color: '#92400e', icon: <AlertTriangle size={18} color="#d97706" /> },
  positivo: { border: '#86efac', bg: '#f0fdf4', color: '#166534', icon: <CheckCircle2 size={18} color="#16a34a" /> },
  info: { border: '#93c5fd', bg: '#eff6ff', color: '#1e40af', icon: <Info size={18} color="#2563eb" /> },
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
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', padding: '4rem', gap: 8 }}>
        <Loader2 size={24} style={{ animation: 'spin 1s linear infinite' }} />
        <span style={{ color: 'var(--text-light)' }}>Analizando validación cruzada...</span>
      </div>
    )
  }

  if (error) {
    return (
      <div className="card" style={{ borderLeft: '4px solid var(--danger)' }}>
        <div className="card-body" style={{ textAlign: 'center', padding: '2rem' }}>
          <p style={{ color: 'var(--danger)' }}>Error: {error}</p>
          <button className="btn btn-outline" onClick={cargar} style={{ marginTop: '1rem' }}>
            <RefreshCw size={14} /> Reintentar
          </button>
        </div>
      </div>
    )
  }

  if (!data) {
    return (
      <div className="card">
        <div className="card-body" style={{ textAlign: 'center', padding: '3rem' }}>
          <ShieldCheck size={36} color="var(--text-light)" style={{ marginBottom: 12 }} />
          <p style={{ fontSize: '1.1rem', color: 'var(--text-light)' }}>
            No hay datos suficientes para la validación cruzada.
          </p>
          <p style={{ fontSize: '0.9rem', color: 'var(--text-light)', marginTop: 8 }}>
            Cargue la oferta y los datos de producción (Pollitos BB) para generar el reporte.
          </p>
        </div>
      </div>
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
      <motion.div variants={itemVariants} className="card">
        <div className="card-header">
          <h2><ShieldCheck size={18} style={{ verticalAlign: 'middle', marginRight: 6 }} /> Validación Cruzada: Oferta ↔ Producción</h2>
          <button className="btn btn-sm btn-outline" onClick={cargar}>
            <RefreshCw size={14} /> Actualizar
          </button>
        </div>
        <div className="card-body">
          <div style={{ display: 'flex', gap: '1.5rem', flexWrap: 'wrap', marginBottom: '0.5rem' }}>
            <StatusBadge ok={tiene_oferta} label="Oferta" detail={tiene_oferta ? `${formatNumber(total_ofertas)} lotes` : 'No cargada'} />
            <StatusBadge ok={tiene_produccion} label="Producción" detail={tiene_produccion ? `${total_semanas_produccion} semanas` : 'No cargada'} />
            <StatusBadge ok={tiene_oferta && tiene_produccion} label="Cruce disponible"
              detail={tiene_oferta && tiene_produccion ? 'Datos completos' : 'Faltan datos'} />
          </div>
          <div style={{
            display: 'grid',
            gridTemplateColumns: 'repeat(auto-fit, minmax(280px, 1fr))',
            gap: '1rem',
            marginTop: '1rem',
          }}>
            <DataSourceCard
              title="Fuente de oferta"
              source={fuentes?.oferta}
              emptyText="No hay metadata histórica para esta carga."
              rows={[
                {
                  label: 'Persistido',
                  value: fuentes?.oferta?.persisted
                    ? `${formatNumber(fuentes.oferta.persisted.total_lotes)} lotes · ${formatNumber(fuentes.oferta.persisted.total_pollos)} aves`
                    : 'Sin datos',
                },
                {
                  label: 'Fechas peso',
                  value: formatRange(fuentes?.oferta?.persisted?.fecha_peso_desde, fuentes?.oferta?.persisted?.fecha_peso_hasta),
                },
                {
                  label: 'Fechas ingreso',
                  value: formatRange(fuentes?.oferta?.persisted?.fecha_ingreso_desde, fuentes?.oferta?.persisted?.fecha_ingreso_hasta),
                },
              ]}
            />
            <DataSourceCard
              title="Fuente de producción"
              source={fuentes?.produccion}
              emptyText="No hay metadata histórica para esta carga."
              rows={[
                {
                  label: 'Persistido',
                  value: fuentes?.produccion?.persisted
                    ? `${formatNumber(fuentes.produccion.persisted.total_semanas)} semanas · ${formatNumber(fuentes.produccion.persisted.total_pollitos)} pollitos`
                    : 'Sin datos',
                },
                {
                  label: 'Ventana cargada',
                  value: formatRange(fuentes?.produccion?.persisted?.fecha_desde, fuentes?.produccion?.persisted?.fecha_hasta),
                },
              ]}
            />
          </div>
        </div>
      </motion.div>

      {/* Resumen ejecutivo */}
      {cohortesList.length > 0 && (
        <motion.div variants={itemVariants} className="card" style={{ borderLeft: '4px solid var(--primary)' }}>
          <div className="card-header">
            <h2><TrendingUp size={18} style={{ verticalAlign: 'middle', marginRight: 6 }} /> Resumen Ejecutivo</h2>
            <span style={{ fontSize: '0.85rem', color: 'var(--text-light)' }}>
              Enfoque para la oferta vigente
            </span>
          </div>
          <div className="card-body">
            <p style={{ fontSize: '0.9rem', color: 'var(--text-light)', marginBottom: '1rem', lineHeight: 1.5 }}>
              La oferta actual se reparte en {cohortesList.length} cohorte{cohortesList.length !== 1 ? 's' : ''}. 
              {cohortesEnVentana.length > 0 && ` ${cohortesEnVentana.length} queda${cohortesEnVentana.length !== 1 ? 'n' : ''} dentro de la ventana esperada`} 
              {cohortesReprogramar.length > 0 && `, ${cohortesReprogramar.length} requiere${cohortesReprogramar.length !== 1 ? 'n' : ''} reprogramacion temporal`} 
              {cohortesPrioridad.length > 0 && ` y ${cohortesPrioridad.length} necesita${cohortesPrioridad.length !== 1 ? 'n' : ''} revision prioritaria`}. 
              {proximaSemanaPlan && ` La semana sugerida mas cercana parte en ${formatWeekRange(proximaSemanaPlan)}.`}
            </p>
            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(180px, 1fr))', gap: '1rem' }}>
              <KpiCard label="Cohortes en ventana" value={formatNumber(cohortesEnVentana.length)} color="var(--success)" />
              <KpiCard label="Reprogramar" value={formatNumber(cohortesReprogramar.length)} color="var(--warning)" />
              <KpiCard label="Revision prioritaria" value={formatNumber(cohortesPrioridad.length)} color="var(--danger)" />
              <KpiCard label="Aves ofertadas" value={formatNumber(totalOfertaCohortes)} color="var(--text)" />
              <KpiCard
                label="Balance vs esperado minimo"
                value={formatSignedNumber(balanceCohortes)}
                color={balanceCohortes >= 0 ? 'var(--success)' : 'var(--warning)'}
              />
              <KpiCard label="Proxima semana sugerida" value={proximaSemanaPlan ? formatWeekRange(proximaSemanaPlan) : '-'} color="var(--primary)" />
            </div>
          </div>
        </motion.div>
      )}

      {/* Insights */}
      {insights && insights.length > 0 && (
        <motion.div variants={itemVariants} className="card" style={{ borderLeft: '4px solid var(--primary)' }}>
          <div className="card-header">
            <h2><TrendingUp size={18} style={{ verticalAlign: 'middle', marginRight: 6 }} /> Insights y Recomendaciones</h2>
            <span style={{ fontSize: '0.85rem', color: 'var(--text-light)' }}>
              {insights.length} insight{insights.length !== 1 ? 's' : ''} detectado{insights.length !== 1 ? 's' : ''}
            </span>
          </div>
          <div className="card-body">
            <div style={{ display: 'flex', flexDirection: 'column', gap: '0.75rem' }}>
              {insights.map((ins, idx) => {
                const style = INSIGHT_STYLES[ins.tipo] || INSIGHT_STYLES.info
                return (
                  <div key={idx} style={{
                    border: `1px solid ${style.border}`,
                    borderRadius: 8,
                    padding: '0.85rem 1rem',
                    background: style.bg,
                    color: style.color,
                  }}>
                    <div style={{ display: 'flex', alignItems: 'flex-start', gap: 10 }}>
                      <div style={{ marginTop: 2, flexShrink: 0 }}>{style.icon}</div>
                      <div style={{ flex: 1 }}>
                        <div style={{ fontWeight: 600, fontSize: '0.9rem', marginBottom: 4 }}>
                          {ins.titulo}
                          <span style={{
                            fontSize: '0.75rem', fontWeight: 400, marginLeft: 8,
                            background: 'rgba(0,0,0,0.06)', padding: '2px 6px', borderRadius: 4,
                          }}>
                            {ins.categoria}
                          </span>
                        </div>
                        <div style={{ fontSize: '0.85rem', lineHeight: 1.5 }}>{ins.detalle}</div>
                        {ins.accion && (
                          <div style={{ fontSize: '0.8rem', marginTop: 6, fontStyle: 'italic', opacity: 0.85 }}>
                            💡 {ins.accion}
                          </div>
                        )}
                      </div>
                    </div>
                  </div>
                )
              })}
            </div>
          </div>
        </motion.div>
      )}

      {/* Factibilidad */}
      {fact && fact.encontrada && (
        <motion.div variants={itemVariants} className="card"
          style={{ borderLeft: `4px solid ${fact.deficit_peor ? 'var(--danger)' : 'var(--success)'}` }}>
          <div className="card-header">
            <h2>
              {fact.deficit_peor
                ? <AlertCircle size={18} color="var(--danger)" style={{ verticalAlign: 'middle', marginRight: 6 }} />
                : <CheckCircle2 size={18} color="var(--success)" style={{ verticalAlign: 'middle', marginRight: 6 }} />
              }
              Factibilidad de Producción
            </h2>
          </div>
          <div className="card-body">
            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(180px, 1fr))', gap: '1rem', marginBottom: '1.5rem' }}>
              <KpiCard label="Pollitos Cargados" value={formatNumber(fact.pollitos_cargados)} />
              <KpiCard label="Oferta Total" value={formatNumber(fact.total_oferta)} />
              <KpiCard label="Esperados en faena (mín.)" value={formatNumber(fact.disponibles_peor)}
                color="var(--orange)" />
              <KpiCard label="Esperados en faena (máx.)" value={formatNumber(fact.disponibles_mejor)}
                color="var(--primary)" />
              {fact.deficit_peor ? (
                <KpiCard label="Déficit" value={formatNumber(fact.deficit_peor)} color="var(--danger)" />
              ) : (
                <KpiCard label="Superávit" value={formatNumber(fact.disponibles_peor - fact.total_oferta)}
                  color="var(--success)" />
              )}
              <KpiCard label="Cobertura (peor caso)" value={`${fact.cobertura_pct_peor}%`}
                color={fact.cobertura_pct_peor > 100 ? 'var(--danger)' : 'var(--success)'} />
            </div>

            {/* Tabla de coberturas por tasa */}
            {fact.coberturas && fact.coberturas.length > 0 && (
              <>
                <h3 style={{ fontSize: '0.9rem', fontWeight: 600, marginBottom: '0.5rem', color: 'var(--text-light)' }}>
                  Cobertura por escenario esperado de recepción
                </h3>
                <div className="table-container">
                  <table>
                    <thead>
                      <tr>
                        <th>Escenario</th>
                        <th className="text-right">Esperados en Faena</th>
                        <th className="text-right">Cobertura</th>
                        <th>Estado</th>
                      </tr>
                    </thead>
                    <tbody>
                      {fact.coberturas.map((c, idx) => (
                        <tr key={idx} style={{
                          background: c.tasa === peorTasa ? 'rgba(251,146,60,0.06)' : undefined,
                        }}>
                          <td style={{ fontWeight: c.tasa === peorTasa ? 700 : 400 }}>
                            {c.tasa === peorTasa ? 'Conservador' : c.tasa === 4.5 ? 'Base' : `Escenario ${c.tasa}%`}
                          </td>
                          <td className="text-right">{formatNumber(c.disponibles)}</td>
                          <td className="text-right" style={{ fontWeight: 600 }}>{c.cobertura_pct}%</td>
                          <td>
                            {c.cobertura_pct <= 100
                              ? <span style={{ color: 'var(--success)', fontSize: '0.85rem' }}>✓ Cubierto</span>
                              : <span style={{ color: 'var(--danger)', fontSize: '0.85rem' }}>✗ Déficit</span>
                            }
                          </td>
                        </tr>
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
        <motion.div variants={itemVariants} className="card" style={{ borderLeft: '4px solid var(--warning)' }}>
          <div className="card-header">
            <h2><AlertTriangle size={18} color="var(--warning)" style={{ verticalAlign: 'middle', marginRight: 6 }} /> Planificacion por Cohortes</h2>
            <span style={{ fontSize: '0.85rem', color: 'var(--text-light)' }}>
              {cohortes.total_cohortes} cohortes · {cohortes.alertas} alerta{cohortes.alertas !== 1 ? 's' : ''}
            </span>
          </div>
          <div className="card-body">
            <p style={{ fontSize: '0.85rem', color: 'var(--text-light)', marginBottom: '1rem' }}>
              Esta vista convierte el cruce oferta-produccion en decisiones de planificacion. Cada cohorte muestra su ventana esperada de faena,
              la semana sugerida para programarla y la accion recomendada para la oferta mas reciente.
            </p>
            <div className="table-container" style={{ overflowX: 'auto' }}>
              <table className="validacion-cohortes-table">
                <colgroup>
                  <col style={{ width: '16%' }} />
                  <col style={{ width: '16%' }} />
                  <col style={{ width: '16%' }} />
                  <col style={{ width: '14%' }} />
                  <col style={{ width: '10%' }} />
                  <col style={{ width: '14%' }} />
                  <col style={{ width: '14%' }} />
                </colgroup>
                <thead>
                  <tr>
                    <th>Cohorte</th>
                    <th>Semana sugerida</th>
                    <th>Ventana esperada</th>
                    <th className="text-right">Oferta / Esperado</th>
                    <th className="text-right">Brecha</th>
                    <th>Estado</th>
                    <th>Accion sugerida</th>
                  </tr>
                </thead>
                <tbody>
                  {cohortes.cohortes.map((c, idx) => {
                    const cfg = NIVEL_CONFIG[c.nivel] || NIVEL_CONFIG.sin_dato
                    const accion = getPlanningAction(c)
                    const brecha = getBrechaConfig(c)
                    const coberturaEsperada = c.cobertura_pct_min != null && c.cobertura_pct_max != null
                      ? `${c.cobertura_pct_max}% - ${c.cobertura_pct_min}%`
                      : '-'
                    return (
                      <tr key={idx}>
                        <td style={COHORTE_WRAP_CELL_STYLE}>
                          <strong>{formatDate(c.fecha_desde)}</strong>
                          <span style={{ color: 'var(--text-light)', fontSize: '0.8rem' }}> – {formatDate(c.fecha_hasta)}</span>
                          <div style={{ ...COHORTE_META_TEXT_STYLE, fontSize: '0.78rem', marginTop: 4 }}>
                            {c.granjas?.join(', ') || '-'}
                            {c.lotes > 0 && <span> · {c.lotes} lotes</span>}
                          </div>
                        </td>
                        <td style={{ ...COHORTE_WRAP_CELL_STYLE, fontSize: '0.82rem', lineHeight: 1.45 }}>
                          <div><strong>{getPlanningWeekLabel(c)}</strong></div>
                          <div style={COHORTE_META_TEXT_STYLE}>
                            Oferta objetivo: {formatRange(c.fecha_objetivo_desde || c.fecha_oferta_desde, c.fecha_objetivo_hasta || c.fecha_oferta_hasta)}
                          </div>
                        </td>
                        <td style={{ ...COHORTE_WRAP_CELL_STYLE, fontSize: '0.8rem', lineHeight: 1.45 }}>
                          <div><strong>{formatRange(c.fecha_faena_esperada_desde, c.fecha_faena_esperada_hasta)}</strong></div>
                          <div style={COHORTE_META_TEXT_STYLE}>
                            Cargados: {formatNumber(c.pollitos_cargados)}
                          </div>
                        </td>
                        <td className="text-right">
                          <strong>{formatNumber(c.aves_en_oferta)}</strong>
                          <div style={{ color: 'var(--text-light)', fontSize: '0.75rem' }}>
                            vs {formatNumber(c.esperados_faena_min)} a {formatNumber(c.esperados_faena_max)}
                          </div>
                          <div style={{ color: cfg.color, fontSize: '0.75rem', fontWeight: 600 }}>
                            {coberturaEsperada}
                          </div>
                        </td>
                        <td className="text-right" style={{ fontWeight: 700, color: brecha.color }}>
                          {brecha.label}
                        </td>
                        <td style={COHORTE_WRAP_CELL_STYLE}>
                          <span style={{
                            display: 'inline-block',
                            padding: '2px 8px',
                            borderRadius: 12,
                            fontSize: '0.78rem',
                            fontWeight: 600,
                            background: cfg.bg,
                            color: cfg.color,
                            border: `1px solid ${cfg.color}22`,
                          }}>
                            {cfg.icon} {cfg.label}
                          </span>
                          {c.motivo && (
                            <div style={{ ...COHORTE_META_TEXT_STYLE, fontSize: '0.75rem', marginTop: 6, lineHeight: 1.35 }}>
                              {c.motivo}
                            </div>
                          )}
                        </td>
                        <td style={{ ...COHORTE_WRAP_CELL_STYLE, fontSize: '0.8rem', lineHeight: 1.45 }}>
                          <div style={{ fontWeight: 600 }}>{accion.titulo}</div>
                          <div style={{ ...COHORTE_META_TEXT_STYLE, marginTop: 4 }}>{accion.detalle}</div>
                        </td>
                      </tr>
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
        <motion.div variants={itemVariants} className="card" style={{ borderLeft: '4px solid var(--info, #3b82f6)' }}>
          <div className="card-header">
            <h2><Search size={18} color="var(--info, #3b82f6)" style={{ verticalAlign: 'middle', marginRight: 6 }} /> Consistencia de Edad</h2>
            <span style={{ fontSize: '0.85rem', color: 'var(--text-light)' }}>
              {consist.total} inconsistencia{consist.total !== 1 ? 's' : ''}
            </span>
          </div>
          <div className="card-body">
            <p style={{ fontSize: '0.85rem', color: 'var(--text-light)', marginBottom: '1rem' }}>
              Lotes donde la edad declarada difiere en más de 3 días de la edad calculada (fecha peso − fecha ingreso).
            </p>
            <div className="table-container">
              <table>
                <thead>
                  <tr>
                    <th>Lote #</th>
                    <th>Granja</th>
                    <th>Galpón</th>
                    <th className="text-right">Edad Declarada</th>
                    <th className="text-right">Edad Calculada</th>
                    <th className="text-right">Diferencia</th>
                  </tr>
                </thead>
                <tbody>
                  {consist.alertas.map((a, idx) => (
                    <tr key={idx}>
                      <td><strong>{a.lote}</strong></td>
                      <td>{a.granja}</td>
                      <td>{a.galpon}</td>
                      <td className="text-right">{a.edad_real} días</td>
                      <td className="text-right">{a.dias_calculados} días</td>
                      <td className="text-right" style={{ color: 'var(--danger)', fontWeight: 600 }}>
                        {a.diferencia} días
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        </motion.div>
      )}

      {/* Sin cruce posible */}
      {(!tiene_oferta || !tiene_produccion) && (
        <motion.div variants={itemVariants} className="card">
          <div className="card-body" style={{ textAlign: 'center', padding: '2rem' }}>
            <Info size={24} color="var(--text-light)" style={{ marginBottom: 8 }} />
            <p style={{ color: 'var(--text-light)', fontSize: '0.95rem' }}>
              {!tiene_oferta && !tiene_produccion && 'Cargue la oferta y los datos de producción para obtener el cruce completo.'}
              {tiene_oferta && !tiene_produccion && 'Cargue los datos de producción (Pollitos BB) para cruzar con la oferta existente.'}
              {!tiene_oferta && tiene_produccion && 'Cargue la oferta para cruzar con los datos de producción existentes.'}
            </p>
          </div>
        </motion.div>
      )}
    </motion.div>
  )
}

function StatusBadge({ ok, label, detail }) {
  return (
    <div style={{
      display: 'flex', alignItems: 'center', gap: 8,
      padding: '0.5rem 1rem',
      borderRadius: 8,
      background: ok ? 'rgba(34,197,94,0.06)' : 'rgba(239,68,68,0.06)',
      border: `1px solid ${ok ? 'rgba(34,197,94,0.2)' : 'rgba(239,68,68,0.2)'}`,
    }}>
      {ok
        ? <CheckCircle2 size={16} color="#16a34a" />
        : <XCircle size={16} color="#ef4444" />
      }
      <div>
        <div style={{ fontWeight: 600, fontSize: '0.85rem' }}>{label}</div>
        <div style={{ fontSize: '0.75rem', color: 'var(--text-light)' }}>{detail}</div>
      </div>
    </div>
  )
}

function KpiCard({ label, value, color }) {
  return (
    <div style={{
      background: '#f8fafc',
      border: '1px solid var(--border)',
      borderRadius: 8,
      padding: '0.75rem 1rem',
      textAlign: 'center',
    }}>
      <div style={{ fontSize: '0.75rem', color: 'var(--text-light)', marginBottom: 4 }}>{label}</div>
      <div style={{ fontSize: '1.3rem', fontWeight: 700, color: color || 'var(--text)' }}>{value}</div>
    </div>
  )
}

function DataSourceCard({ title, source, rows, emptyText }) {
  const mismatch = source?.metadata_matches_persisted === false

  return (
    <div style={{
      border: `1px solid ${mismatch ? 'rgba(245, 158, 11, 0.45)' : 'var(--border)'}`,
      borderRadius: 10,
      padding: '0.9rem 1rem',
      background: mismatch ? 'rgba(255, 251, 235, 0.7)' : '#f8fafc',
    }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', gap: 12, alignItems: 'baseline', marginBottom: 8 }}>
        <div style={{ fontWeight: 700, fontSize: '0.92rem' }}>{title}</div>
        <div style={{ fontSize: '0.74rem', color: 'var(--text-light)' }}>Storage persistido</div>
      </div>

      <div style={{ fontSize: '0.85rem', fontWeight: 600, color: 'var(--text)' }}>
        {source?.filename || 'Sin archivo registrado'}
      </div>
      <div style={{ fontSize: '0.76rem', color: 'var(--text-light)', marginTop: 4 }}>
        Última carga: {formatDateTime(source?.uploaded_at)}
      </div>
      {source?.sheet_name && (
        <div style={{ fontSize: '0.76rem', color: 'var(--text-light)', marginTop: 2 }}>
          Hoja: {source.sheet_name}
        </div>
      )}
      {!source?.filename && (
        <div style={{ fontSize: '0.76rem', color: 'var(--text-light)', marginTop: 6 }}>
          {emptyText}
        </div>
      )}

      <div style={{ display: 'grid', gap: 6, marginTop: '0.75rem' }}>
        {rows.map((row) => (
          <div key={row.label} style={{ display: 'flex', justifyContent: 'space-between', gap: 12, fontSize: '0.8rem' }}>
            <span style={{ color: 'var(--text-light)' }}>{row.label}</span>
            <span style={{ textAlign: 'right', color: 'var(--text)' }}>{row.value || '-'}</span>
          </div>
        ))}
      </div>

      {typeof source?.total_descartadas === 'number' && source.total_descartadas > 0 && (
        <div style={{ fontSize: '0.76rem', color: 'var(--warning)', marginTop: '0.7rem' }}>
          Filas descartadas al cargar: {formatNumber(source.total_descartadas)}
        </div>
      )}

      {mismatch && (
        <div style={{ fontSize: '0.76rem', color: '#92400e', marginTop: '0.7rem', lineHeight: 1.4 }}>
          El resumen persistido ya no coincide con la última metadata registrada. Conviene recargar el archivo para mantener la trazabilidad.
        </div>
      )}
    </div>
  )
}
