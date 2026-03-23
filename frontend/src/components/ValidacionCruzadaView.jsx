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

const NIVEL_CONFIG = {
  excelente: { label: 'Excelente', color: '#16a34a', bg: '#f0fdf4', icon: '🟢' },
  normal: { label: 'Normal', color: '#2563eb', bg: '#eff6ff', icon: '🔵' },
  elevada: { label: 'Elevada', color: '#d97706', bg: '#fffbeb', icon: '🟡' },
  critica: { label: 'Crítica', color: '#dc2626', bg: '#fef2f2', icon: '🔴' },
  inconsistente: { label: 'Inconsistente', color: '#7c3aed', bg: '#f5f3ff', icon: '🟣' },
  cobertura_parcial: { label: 'Cobertura parcial', color: '#6b7280', bg: '#f9fafb', icon: '⚪' },
  sin_dato: { label: 'Sin dato', color: '#9ca3af', bg: '#f9fafb', icon: '⚫' },
}

const INSIGHT_STYLES = {
  critico: { border: '#fca5a5', bg: '#fef2f2', color: '#991b1b', icon: <XCircle size={18} color="#dc2626" /> },
  advertencia: { border: '#fcd34d', bg: '#fffbeb', color: '#92400e', icon: <AlertTriangle size={18} color="#d97706" /> },
  positivo: { border: '#86efac', bg: '#f0fdf4', color: '#166534', icon: <CheckCircle2 size={18} color="#16a34a" /> },
  info: { border: '#93c5fd', bg: '#eff6ff', color: '#1e40af', icon: <Info size={18} color="#2563eb" /> },
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

  const { validacion, insights, tiene_oferta, tiene_produccion, total_ofertas, total_semanas_produccion } = data
  const fact = validacion?.factibilidad
  const mort = validacion?.mortalidad_cohortes
  const consist = validacion?.consistencia_edad

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
        </div>
      </motion.div>

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
              <KpiCard label="Disponibles (6.5% mort.)" value={formatNumber(fact.disponibles_peor)}
                color="var(--orange)" />
              <KpiCard label="Disponibles (4.5% mort.)" value={formatNumber(fact.disponibles_mejor)}
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
                  Cobertura por escenario de mortalidad
                </h3>
                <div className="table-container">
                  <table>
                    <thead>
                      <tr>
                        <th>Tasa Mortalidad</th>
                        <th className="text-right">Disponibles</th>
                        <th className="text-right">Cobertura</th>
                        <th>Estado</th>
                      </tr>
                    </thead>
                    <tbody>
                      {fact.coberturas.map((c, idx) => (
                        <tr key={idx} style={{
                          background: c.tasa === 6.5 ? 'rgba(251,146,60,0.06)' : undefined,
                        }}>
                          <td style={{ fontWeight: c.tasa === 6.5 ? 700 : 400 }}>{c.tasa}%</td>
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

      {/* Mortalidad por cohortes */}
      {mort && mort.cohortes && mort.cohortes.length > 0 && (
        <motion.div variants={itemVariants} className="card" style={{ borderLeft: '4px solid var(--warning)' }}>
          <div className="card-header">
            <h2><AlertTriangle size={18} color="var(--warning)" style={{ verticalAlign: 'middle', marginRight: 6 }} /> Mortalidad Implícita por Cohorte</h2>
            <span style={{ fontSize: '0.85rem', color: 'var(--text-light)' }}>
              {mort.total_cohortes} cohortes · {mort.alertas} alerta{mort.alertas !== 1 ? 's' : ''}
            </span>
          </div>
          <div className="card-body">
            <p style={{ fontSize: '0.85rem', color: 'var(--text-light)', marginBottom: '1rem' }}>
              Mortalidad implícita calculada como <code style={{ fontSize: '0.8rem' }}>(1 − aves_en_oferta / pollitos_cargados) × 100</code>.
              Compara las aves de la oferta con los pollitos cargados en la semana de producción correspondiente.
            </p>
            <div className="table-container" style={{ overflowX: 'auto' }}>
              <table>
                <thead>
                  <tr>
                    <th>Semana Producción</th>
                    <th className="text-right">Cargados</th>
                    <th className="text-right">En Oferta</th>
                    <th className="text-right">Diferencia</th>
                    <th className="text-right">Mortalidad</th>
                    <th className="text-right">Cobertura</th>
                    <th>Nivel</th>
                    <th>Granjas</th>
                  </tr>
                </thead>
                <tbody>
                  {mort.cohortes.map((c, idx) => {
                    const cfg = NIVEL_CONFIG[c.nivel] || NIVEL_CONFIG.sin_dato
                    return (
                      <tr key={idx}>
                        <td>
                          <strong>{formatDate(c.fecha_desde)}</strong>
                          <span style={{ color: 'var(--text-light)', fontSize: '0.8rem' }}> – {formatDate(c.fecha_hasta)}</span>
                        </td>
                        <td className="text-right">{formatNumber(c.pollitos_cargados)}</td>
                        <td className="text-right">{formatNumber(c.aves_en_oferta)}</td>
                        <td className="text-right" style={{
                          color: c.diferencia > 0 ? 'var(--danger)' : 'var(--success)',
                          fontWeight: 600,
                        }}>
                          {c.diferencia > 0 ? '-' : '+'}{formatNumber(Math.abs(c.diferencia))}
                        </td>
                        <td className="text-right" style={{ fontWeight: 600, color: cfg.color }}>
                          {c.mortalidad_pct != null ? `${c.mortalidad_pct}%` : '-'}
                        </td>
                        <td className="text-right">{c.cobertura_pct != null ? `${c.cobertura_pct}%` : '-'}</td>
                        <td>
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
                        </td>
                        <td style={{ fontSize: '0.8rem' }}>
                          {c.granjas?.join(', ') || '-'}
                          {c.lotes > 0 && <span style={{ color: 'var(--text-light)' }}> ({c.lotes} lotes)</span>}
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
