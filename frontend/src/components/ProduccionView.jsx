import React, { useState, useEffect, useRef } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import { Factory, UploadCloud, FileSpreadsheet, Trash2, Calendar, TrendingDown, TrendingUp, Loader2, X, ArrowDown, ArrowUp, CheckCircle2, AlertTriangle, AlertCircle, MinusCircle, Info } from 'lucide-react'
import toast from 'react-hot-toast'
import { uploadProduccion, getProduccion, getSimulacionMortalidad, deleteProduccion, getForecastProduccion, getValidacionCruzada } from '../services/api'

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

function formatDateShort(d) {
  if (!d) return '-'
  const dt = new Date(d + 'T12:00:00')
  return dt.toLocaleDateString('es-AR', { day: 'numeric', month: 'short' })
}

function getCruceEstado(cohorte) {
  if (!cohorte) {
    return {
      key: 'sin_oferta',
      label: 'Sin oferta',
      tone: '#64748b',
      bg: '#f1f5f9',
      icon: <MinusCircle size={12} />,
      esAlerta: false,
    }
  }

  const nivel = cohorte.nivel || cohorte.estado_cantidad
  if (nivel === 'alineada' || nivel === 'en_rango') {
    return {
      key: 'alineada',
      label: 'Coherente',
      tone: '#047857',
      bg: '#d1fae5',
      icon: <CheckCircle2 size={12} />,
      esAlerta: false,
    }
  }
  if (nivel === 'parcial') {
    return {
      key: 'parcial',
      label: 'Parcial',
      tone: '#92400e',
      bg: '#fef3c7',
      icon: <AlertCircle size={12} />,
      esAlerta: false,
    }
  }
  if (nivel === 'excedida' || nivel === 'por_encima') {
    return {
      key: 'excedida',
      label: 'Excede',
      tone: '#b91c1c',
      bg: '#fee2e2',
      icon: <AlertTriangle size={12} />,
      esAlerta: true,
    }
  }
  if (nivel === 'anticipada') {
    return {
      key: 'anticipada',
      label: 'Anticipada',
      tone: '#b45309',
      bg: '#ffedd5',
      icon: <AlertTriangle size={12} />,
      esAlerta: true,
    }
  }
  if (nivel === 'atrasada') {
    return {
      key: 'atrasada',
      label: 'Atrasada',
      tone: '#7c3aed',
      bg: '#ede9fe',
      icon: <AlertTriangle size={12} />,
      esAlerta: true,
    }
  }
  if (nivel === 'mixta') {
    return {
      key: 'mixta',
      label: 'Mixta',
      tone: '#0369a1',
      bg: '#e0f2fe',
      icon: <Info size={12} />,
      esAlerta: true,
    }
  }

  return {
    key: 'sin_dato',
    label: 'Sin dato',
    tone: '#64748b',
    bg: '#f1f5f9',
    icon: <MinusCircle size={12} />,
    esAlerta: false,
  }
}

function getConfiabilidadCruce(cohorte) {
  if (!cohorte) return null
  if (cohorte.estado_fecha === 'alineada') return { label: 'Alta', tone: '#047857' }
  if (cohorte.desfase_dias != null && Math.abs(cohorte.desfase_dias) <= 3) return { label: 'Media', tone: '#92400e' }
  if (cohorte.estado_fecha === 'mixta') return { label: 'Media', tone: '#0369a1' }
  return { label: 'Baja', tone: '#b91c1c' }
}

function RangoOfertaBar({ cohorte, peorCaso, mejorCaso }) {
  if (!cohorte || !cohorte.aves_en_oferta || !peorCaso || !mejorCaso) {
    return <span style={{ color: 'var(--text-light)', fontSize: '0.8rem' }}>-</span>
  }

  const esperadoMin = cohorte.esperados_faena_min || peorCaso
  const esperadoMax = cohorte.esperados_faena_max || mejorCaso
  const oferta = cohorte.aves_en_oferta
  const escalaMax = Math.max(esperadoMax, oferta, 1)
  const rangoInicio = Math.max(0, Math.min(100, (esperadoMin / escalaMax) * 100))
  const rangoAncho = Math.max(3, Math.min(100 - rangoInicio, ((esperadoMax - esperadoMin) / escalaMax) * 100))
  const ofertaPos = Math.max(0, Math.min(100, (oferta / escalaMax) * 100))
  const estado = getCruceEstado(cohorte)

  return (
    <div style={{ minWidth: 170 }}>
      <div
        title={`Rango esperado ${formatNumber(esperadoMin)} - ${formatNumber(esperadoMax)} | Oferta ${formatNumber(oferta)}`}
        style={{
          position: 'relative',
          height: 18,
          borderRadius: 6,
          background: '#eef2f7',
          border: '1px solid #dbe3ef',
          overflow: 'hidden',
        }}
      >
        <div style={{
          position: 'absolute',
          left: `${rangoInicio}%`,
          width: `${rangoAncho}%`,
          top: 3,
          bottom: 3,
          borderRadius: 4,
          background: 'rgba(16, 185, 129, 0.28)',
          border: '1px solid rgba(16, 185, 129, 0.35)',
        }} />
        <div style={{
          position: 'absolute',
          left: `calc(${ofertaPos}% - 2px)`,
          top: 1,
          bottom: 1,
          width: 4,
          borderRadius: 4,
          background: estado.tone,
          boxShadow: '0 0 0 2px rgba(255,255,255,0.9)',
        }} />
      </div>
      <div style={{ display: 'flex', justifyContent: 'space-between', gap: 8, marginTop: 4, fontSize: '0.68rem', color: 'var(--text-light)' }}>
        <span>{formatNumber(esperadoMin)}</span>
        <span>{formatNumber(esperadoMax)}</span>
      </div>
    </div>
  )
}

function EstadoBadge({ cohorte }) {
  const estado = getCruceEstado(cohorte)
  return (
    <span style={{
      display: 'inline-flex',
      alignItems: 'center',
      gap: 4,
      padding: '3px 8px',
      borderRadius: 999,
      fontWeight: 700,
      fontSize: '0.72rem',
      background: estado.bg,
      color: estado.tone,
      whiteSpace: 'nowrap',
    }}>
      {estado.icon}
      {estado.label}
    </span>
  )
}

export default function ProduccionView() {
  const [produccion, setProduccion] = useState(null)
  const [simulacion, setSimulacion] = useState(null)
  const [forecast, setForecast] = useState(null)
  const [ofertaPorSemana, setOfertaPorSemana] = useState({})
  const [loading, setLoading] = useState(true)
  const [uploading, setUploading] = useState(false)
  const [file, setFile] = useState(null)
  const [ordenDesc, setOrdenDesc] = useState(true)
  const [filtroCruce, setFiltroCruce] = useState('todas')
  const [semanaExpandida, setSemanaExpandida] = useState(null)
  const inputRef = useRef(null)
  const configSim = simulacion?.configuracion || null
  const cohortesCruzadas = Object.values(ofertaPorSemana)
  const resumenCruce = cohortesCruzadas.reduce((acc, cohorte) => {
    const estado = getCruceEstado(cohorte)
    acc.total += 1
    acc[estado.key] = (acc[estado.key] || 0) + 1
    if (estado.esAlerta) acc.alertas += 1
    return acc
  }, { total: 0, alertas: 0 })
  const tieneCruceOferta = cohortesCruzadas.length > 0
  const simulacionOrdenada = simulacion?.simulacion
    ? (ordenDesc ? [...simulacion.simulacion].reverse() : [...simulacion.simulacion])
    : []
  const simulacionFiltrada = simulacionOrdenada.filter((sem) => {
    if (filtroCruce === 'todas') return true
    const estado = getCruceEstado(ofertaPorSemana[sem.fecha_desde])
    if (filtroCruce === 'alertas') return estado.esAlerta
    if (filtroCruce === 'sin_oferta') return estado.key === 'sin_oferta'
    return estado.key === filtroCruce
  })

  useEffect(() => {
    cargarDatos()
  }, [])

  const cargarOfertaCruzada = async () => {
    try {
      const vc = await getValidacionCruzada()
      const cohortes = vc?.validacion?.mortalidad_cohortes?.cohortes || []
      const mapa = {}
      for (const c of cohortes) {
        mapa[c.fecha_desde] = {
          ...c,
          aves_en_oferta: c.aves_en_oferta || 0,
          lotes: c.lotes || 0,
          granjas: c.granjas || [],
        }
      }
      setOfertaPorSemana(mapa)
    } catch {
      // No offer data available
      setOfertaPorSemana({})
    }
  }

  const cargarDatos = async () => {
    setLoading(true)
    try {
      const [prodData, simData, forecastData] = await Promise.allSettled([
        getProduccion(),
        getSimulacionMortalidad(),
        getForecastProduccion(),
      ])
      if (prodData.status === 'fulfilled') setProduccion(prodData.value)
      if (simData.status === 'fulfilled') setSimulacion(simData.value)
      if (forecastData.status === 'fulfilled') setForecast(forecastData.value)
    } catch (err) {
      // No data yet
    } finally {
      setLoading(false)
    }
    cargarOfertaCruzada()
  }

  const handleUpload = async () => {
    if (!file) return
    setUploading(true)
    try {
      const data = await uploadProduccion(file)
      setProduccion(data)
      setFile(null)
      toast.success(`${data.total_semanas} semanas de producción cargadas`)
      // Mostrar alertas de sincronización operativa con oferta
      if (data.validacion_cruzada) {
        const vc = data.validacion_cruzada
        if (vc.factibilidad?.encontrada) {
          const f = vc.factibilidad
          if (f.deficit_peor) {
            toast(
              `Déficit detectado: la oferta actual (${formatNumber(f.total_oferta)}) supera la producción en el escenario conservador (${formatNumber(f.disponibles_peor)}) en ${formatNumber(f.deficit_peor)} aves.`,
              { icon: '🔴', duration: 12000, style: { background: '#fef2f2', border: '1px solid #fca5a5', color: '#991b1b', fontSize: '0.85rem' } }
            )
          } else {
            toast.success(
              `Producción cubre la oferta actual (${formatNumber(f.total_oferta)} aves, cobertura: ${f.cobertura_pct_peor}%)`,
              { duration: 6000, style: { fontSize: '0.85rem' } }
            )
          }
        }
        if (vc.mortalidad_cohortes?.alertas > 0) {
          toast(
            `${vc.mortalidad_cohortes.alertas} cohorte${vc.mortalidad_cohortes.alertas !== 1 ? 's' : ''} con fechas o cantidades fuera de lo esperado. Revise la Sincronización Operativa.`,
            { icon: '⚠️', duration: 10000, style: { background: '#fffbeb', border: '1px solid #f59e0b', color: '#92400e', fontSize: '0.85rem' } }
          )
        }
      }
      // Recargar simulación y cruce
      try {
        const sim = await getSimulacionMortalidad()
        setSimulacion(sim)
      } catch {}
      try {
        const fc = await getForecastProduccion()
        setForecast(fc)
      } catch {}
      cargarOfertaCruzada()
    } catch (err) {
      toast.error('Error: ' + (err.response?.data?.detail || err.message))
    } finally {
      setUploading(false)
    }
  }

  const handleDelete = async () => {
    if (!window.confirm('¿Eliminar los datos de producción cargados?')) return
    try {
      await deleteProduccion()
      setProduccion(null)
      setSimulacion(null)
      setForecast(null)
      setOfertaPorSemana({})
      setSemanaExpandida(null)
      toast.success('Datos de producción eliminados')
    } catch (err) {
      toast.error('Error: ' + (err.response?.data?.detail || err.message))
    }
  }

  const handleFile = (f) => {
    if (f && (f.name.endsWith('.xlsx') || f.name.endsWith('.xls'))) {
      setFile(f)
    } else {
      toast.error('Solo se aceptan archivos .xlsx o .xls')
    }
  }

  if (loading) {
    return (
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', padding: '4rem', gap: 8 }}>
        <Loader2 size={24} style={{ animation: 'spin 1s linear infinite' }} />
        <span style={{ color: 'var(--text-light)' }}>Cargando datos de cargas...</span>
      </div>
    )
  }

  return (
    <motion.div variants={containerVariants} initial="hidden" animate="show">
      {/* Upload */}
      <motion.div variants={itemVariants} className="card">
        <div className="card-header">
          <h2><Factory size={18} style={{ verticalAlign: 'middle', marginRight: 6 }} /> Cargas de Pollitos BB en Granjas</h2>
          {produccion && (
            <button className="btn btn-sm btn-danger" onClick={handleDelete}>
              <Trash2 size={14} /> Limpiar
            </button>
          )}
        </div>
        <div className="card-body">
          <p style={{ marginBottom: '1rem', fontSize: '0.9rem', color: 'var(--text-light)' }}>
            Suba el archivo "13.Datos Produccion por Semana" para ver la cantidad de pollitos cargados en granjas propias
            y simular la disponibilidad a distintas tasas de mortalidad.
          </p>
          <div style={{ display: 'flex', gap: '0.75rem', alignItems: 'center', flexWrap: 'wrap' }}>
            <div
              style={{
                flex: 1, minWidth: 200,
                border: '1px dashed var(--border)', borderRadius: 8,
                padding: '0.75rem 1rem', cursor: 'pointer',
                background: file ? 'rgba(34, 197, 94, 0.05)' : '#f8fafc',
                display: 'flex', alignItems: 'center', gap: 8,
                fontSize: '0.85rem', transition: 'all 0.2s',
              }}
              onClick={() => inputRef.current?.click()}
            >
              {file ? (
                <><FileSpreadsheet size={16} color="var(--success)" /> {file.name}</>
              ) : (
                <><UploadCloud size={16} color="var(--text-light)" /> Seleccionar archivo Excel...</>
              )}
              <input ref={inputRef} type="file" accept=".xlsx,.xls" style={{ display: 'none' }}
                onChange={(e) => handleFile(e.target.files[0])} />
            </div>
            <button className="btn btn-primary" disabled={!file || uploading} onClick={handleUpload}
              style={{ whiteSpace: 'nowrap' }}>
              {uploading ? (
                <><span className="spinner" style={{ width: 14, height: 14, marginRight: 6 }}></span> Cargando...</>
              ) : (
                <><UploadCloud size={14} /> Cargar Datos</>
              )}
            </button>
            {file && (
              <button className="btn btn-sm btn-outline" onClick={() => setFile(null)}>
                <X size={14} />
              </button>
            )}
          </div>
        </div>
      </motion.div>

      {/* Tabla de semanas cargadas */}
      {produccion && produccion.semanas && produccion.semanas.length > 0 && (
        <motion.div variants={itemVariants} className="card">
          <div className="card-header">
            <h2><Calendar size={18} style={{ verticalAlign: 'middle', marginRight: 6 }} /> Semanas Cargadas</h2>
            <span style={{ fontSize: '0.85rem', color: 'var(--text-light)' }}>
              {produccion.total_semanas} semanas · {formatNumber(produccion.total_pollitos)} pollitos totales
            </span>
          </div>
          <div className="card-body">
            <div className="table-container" style={{ maxHeight: 300, overflowY: 'auto' }}>
              <table>
                <thead>
                  <tr>
                    <th>Semana</th>
                    <th>Desde</th>
                    <th>Hasta</th>
                    <th className="text-right">Pollitos Cargados</th>
                  </tr>
                </thead>
                <tbody>
                  {produccion.semanas.map((s, idx) => (
                    <tr key={idx}>
                      <td><strong>{idx + 1}</strong></td>
                      <td>{formatDate(s.fecha_desde)}</td>
                      <td>{formatDate(s.fecha_hasta)}</td>
                      <td className="text-right">{formatNumber(s.pollitos_cargados)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        </motion.div>
      )}

      {/* Simulación de mortalidad */}
      {simulacion && simulacion.simulacion && simulacion.simulacion.length > 0 && (
        <motion.div variants={itemVariants} className="card" style={{ borderLeft: '4px solid var(--warning)' }}>
          <div className="card-header" style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', flexWrap: 'wrap', gap: '1rem' }}>
            <div>
              <h2><TrendingDown size={18} style={{ verticalAlign: 'middle', marginRight: 6 }} /> Simulación de Mortalidad</h2>
              <span style={{ fontSize: '0.85rem', color: 'var(--text-light)' }}>
                Disponibilidad estimada en {simulacion.simulacion.length} semanas
              </span>
            </div>
            <button 
              className="btn btn-sm btn-outline" 
              onClick={() => setOrdenDesc(!ordenDesc)}
              style={{ display: 'flex', alignItems: 'center', gap: '6px', background: 'var(--bg-card)', whiteSpace: 'nowrap' }}
            >
              {ordenDesc ? (
                <><ArrowUp size={14} /> <span style={{ fontSize: '0.85rem', fontWeight: 500 }}>Ver Primeros</span></>
              ) : (
                <><ArrowDown size={14} /> <span style={{ fontSize: '0.85rem', fontWeight: 500 }}>Ver Últimos</span></>
              )}
            </button>
          </div>
          <div className="card-body">
            <p style={{ marginBottom: '1rem', fontSize: '0.85rem', color: 'var(--text-light)' }}>
              Planificación estimada de pollitos disponibles para faena usando la configuración vigente de referencia BB.
              La fecha de faena se proyecta con <strong>fecha de carga + {configSim?.dias_hasta_faena ?? 42} días</strong>
              {configSim?.tolerancia_dias != null && ` y un margen operativo de ±${configSim.tolerancia_dias} días para los cruces.`}
              {' '}
              Los escenarios de merma van de <strong>{configSim?.mortalidad_min ?? simulacion.tasas[0]}%</strong> a <strong>{configSim?.mortalidad_max ?? simulacion.tasas[simulacion.tasas.length - 1]}%</strong>.
              {Object.keys(ofertaPorSemana).length > 0 && (
                <span> El cruce compara la oferta actual contra el rango esperado por cohorte.</span>
              )}
            </p>
            {tieneCruceOferta && (
              <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(150px, 1fr))', gap: '0.75rem', marginBottom: '1rem' }}>
                {[
                  { key: 'total', label: 'Cohortes cruzadas', value: resumenCruce.total, tone: 'var(--text)' },
                  { key: 'alineada', label: 'Coherentes', value: resumenCruce.alineada || 0, tone: '#047857' },
                  { key: 'parcial', label: 'Parciales', value: resumenCruce.parcial || 0, tone: '#92400e' },
                  { key: 'alertas', label: 'Con alerta', value: resumenCruce.alertas || 0, tone: '#b91c1c' },
                ].map(item => (
                  <div key={item.key} style={{
                    border: '1px solid var(--border)',
                    borderRadius: 8,
                    padding: '0.75rem 0.9rem',
                    background: '#fff',
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'space-between',
                    gap: 10,
                  }}>
                    <span style={{ color: 'var(--text-light)', fontSize: '0.78rem', fontWeight: 700, textTransform: 'uppercase' }}>{item.label}</span>
                    <strong style={{ color: item.tone, fontSize: '1.15rem' }}>{formatNumber(item.value)}</strong>
                  </div>
                ))}
              </div>
            )}
            {tieneCruceOferta && (
              <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', flexWrap: 'wrap', marginBottom: '1rem' }}>
                {[
                  ['todas', 'Todas'],
                  ['alertas', 'Alertas'],
                  ['alineada', 'Coherentes'],
                  ['parcial', 'Parciales'],
                  ['excedida', 'Excedidas'],
                  ['sin_oferta', 'Sin oferta'],
                ].map(([key, label]) => (
                  <button
                    key={key}
                    type="button"
                    className={`btn btn-sm ${filtroCruce === key ? 'btn-primary' : 'btn-outline'}`}
                    onClick={() => setFiltroCruce(key)}
                  >
                    {label}
                  </button>
                ))}
                <span style={{ marginLeft: 'auto', fontSize: '0.78rem', color: 'var(--text-light)', fontWeight: 600 }}>
                  {simulacionFiltrada.length} fila{simulacionFiltrada.length !== 1 ? 's' : ''}
                </span>
              </div>
            )}
            <div className="table-container" style={{ maxHeight: '60vh', overflowY: 'auto', overflowX: 'auto', borderRadius: '8px', border: '1px solid var(--border)' }}>
              <table style={{ position: 'relative', width: '100%', borderCollapse: 'collapse', minWidth: tieneCruceOferta ? 1380 : undefined }}>
                <thead style={{ position: 'sticky', top: 0, zIndex: 10, backgroundColor: '#f8fafc', boxShadow: '0 2px 4px rgba(0,0,0,0.06)' }}>
                  <tr>
                    <th>Semana Carga</th>
                    <th>Faena Estimada</th>
                    <th className="text-right">Cargados</th>
                    {simulacion.tasas.map(t => {
                      const formattedT = Number(t).toLocaleString('es-AR', { maximumFractionDigits: 1 })
                      return (
                        <th key={t} className="text-right" style={{
                          background: t === simulacion.tasas[simulacion.tasas.length - 1] ? 'rgba(251, 146, 60, 0.1)' : undefined,
                          fontWeight: t === simulacion.tasas[simulacion.tasas.length - 1] ? 700 : undefined,
                        }}>
                          Mort. {formattedT}%
                        </th>
                      )
                    })}
                    {Object.keys(ofertaPorSemana).length > 0 && (
                      <>
                        <th className="text-right" style={{ background: 'rgba(59, 130, 246, 0.08)', fontWeight: 700, borderLeft: '2px solid rgba(59, 130, 246, 0.3)' }}>Oferta Actual</th>
                        <th className="text-right" style={{ background: 'rgba(59, 130, 246, 0.08)', fontWeight: 700 }}>Cobertura</th>
                        <th style={{ background: 'rgba(59, 130, 246, 0.08)', fontWeight: 700 }}>Rango vs Oferta</th>
                        <th style={{ background: 'rgba(59, 130, 246, 0.08)', fontWeight: 700 }}>Estado</th>
                      </>
                    )}
                  </tr>
                </thead>
                <tbody>
                  {simulacionFiltrada.map((sem, idx) => {
                    const oferta = ofertaPorSemana[sem.fecha_desde]
                    const peorCaso = sem.simulaciones[sem.simulaciones.length - 1]?.pollitos_disponibles || 0
                    const mejorCaso = sem.simulaciones[0]?.pollitos_disponibles || 0
                    const tieneOferta = Object.keys(ofertaPorSemana).length > 0
                    const coberturaPct = oferta && peorCaso > 0 ? Math.round(oferta.aves_en_oferta / peorCaso * 1000) / 10 : null
                    const estadoCruce = getCruceEstado(oferta)
                    const confiabilidad = getConfiabilidadCruce(oferta)
                    const estaExpandida = semanaExpandida === sem.fecha_desde
                    return (
                      <React.Fragment key={sem.fecha_desde || idx}>
                        <tr>
                        <td>
                          <strong>{formatDateShort(sem.fecha_desde)}</strong>
                          <span style={{ color: 'var(--text-light)', fontSize: '0.8rem' }}> – {formatDateShort(sem.fecha_hasta)}</span>
                        </td>
                        <td style={{ color: 'var(--primary)', fontWeight: 500 }}>
                          {formatDate(sem.fecha_faena_estimada)}
                        </td>
                        <td className="text-right">
                          <strong>{formatNumber(sem.pollitos_cargados)}</strong>
                        </td>
                        {sem.simulaciones.map((sim, sIdx) => (
                          <td key={sIdx} className="text-right" style={{
                            background: simulacion.tasas[sIdx] === simulacion.tasas[simulacion.tasas.length - 1] ? 'rgba(251, 146, 60, 0.08)' : undefined,
                            fontWeight: simulacion.tasas[sIdx] === simulacion.tasas[simulacion.tasas.length - 1] ? 600 : undefined,
                          }}>
                            {formatNumber(sim.pollitos_disponibles)}
                          </td>
                        ))}
                        {tieneOferta && (
                          <>
                            <td className="text-right" style={{ borderLeft: '2px solid rgba(59, 130, 246, 0.3)', fontWeight: 700, fontSize: '0.95rem' }}>
                              {oferta ? formatNumber(oferta.aves_en_oferta) : <span style={{ color: 'var(--text-light)', fontWeight: 400, fontSize: '0.8rem' }}>Sin oferta</span>}
                            </td>
                            <td className="text-right">
                              {coberturaPct != null ? (
                                <span style={{
                                  display: 'inline-block', padding: '2px 8px', borderRadius: 10, fontWeight: 700, fontSize: '0.8rem',
                                  background: estadoCruce.bg,
                                  color: estadoCruce.tone,
                                }}>
                                  {coberturaPct}%
                                </span>
                              ) : (
                                <span style={{ color: 'var(--text-light)', fontSize: '0.8rem' }}>-</span>
                              )}
                            </td>
                            <td>
                              <RangoOfertaBar cohorte={oferta} peorCaso={peorCaso} mejorCaso={mejorCaso} />
                            </td>
                            <td>
                              <div style={{ display: 'flex', alignItems: 'center', gap: 8, flexWrap: 'wrap' }}>
                                <EstadoBadge cohorte={oferta} />
                                {oferta && (
                                  <button
                                    type="button"
                                    className="btn btn-sm btn-outline"
                                    onClick={() => setSemanaExpandida(estaExpandida ? null : sem.fecha_desde)}
                                    style={{ padding: '0.25rem 0.5rem' }}
                                  >
                                    {estaExpandida ? 'Ocultar' : 'Detalle'}
                                  </button>
                                )}
                              </div>
                            </td>
                          </>
                        )}
                      </tr>
                      {tieneOferta && oferta && estaExpandida && (
                        <tr>
                          <td colSpan={3 + sem.simulaciones.length + 4} style={{ background: '#f8fafc', whiteSpace: 'normal' }}>
                            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(190px, 1fr))', gap: '0.75rem', fontSize: '0.8rem' }}>
                              <div>
                                <strong>Ventana oferta</strong>
                                <div style={{ color: 'var(--text-light)' }}>{formatDate(oferta.fecha_objetivo_desde)} - {formatDate(oferta.fecha_objetivo_hasta)}</div>
                              </div>
                              <div>
                                <strong>Faena esperada</strong>
                                <div style={{ color: 'var(--text-light)' }}>{formatDate(oferta.fecha_faena_esperada_desde)} - {formatDate(oferta.fecha_faena_esperada_hasta)}</div>
                              </div>
                              <div>
                                <strong>Granjas y lotes</strong>
                                <div style={{ color: 'var(--text-light)' }}>{oferta.granjas?.join(', ') || '-'} - {oferta.lotes || 0} lote{oferta.lotes !== 1 ? 's' : ''}</div>
                              </div>
                              <div>
                                <strong>Confiabilidad</strong>
                                <div style={{ color: confiabilidad?.tone || 'var(--text-light)', fontWeight: 700 }}>{confiabilidad?.label || '-'}</div>
                              </div>
                            </div>
                            {oferta.motivo && (
                              <div style={{ marginTop: '0.65rem', color: 'var(--text-light)', fontSize: '0.8rem' }}>{oferta.motivo}</div>
                            )}
                          </td>
                        </tr>
                      )}
                      </React.Fragment>
                    )
                  })}
                </tbody>
              </table>
            </div>
          </div>
        </motion.div>
      )}

      {/* Forecast de producción */}
      {forecast && forecast.semanas && forecast.semanas.length > 0 && (
        <motion.div variants={itemVariants} className="card">
          <div className="card-header" style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', flexWrap: 'wrap', gap: '1rem' }}>
            <div>
              <h2><TrendingUp size={18} style={{ verticalAlign: 'middle', marginRight: 6 }} /> Forecast de Producción ({forecast.semanas.length} semanas)</h2>
              <span style={{ fontSize: '0.85rem', color: 'var(--text-light)' }}>
                Planificación estimada según escenarios de mortalidad.
              </span>
            </div>
            <button 
              className="btn btn-sm btn-outline" 
              onClick={() => setOrdenDesc(!ordenDesc)}
              style={{ display: 'flex', alignItems: 'center', gap: '6px', background: 'var(--bg-card)', whiteSpace: 'nowrap' }}
            >
              {ordenDesc ? (
                <><ArrowUp size={14} /> <span style={{ fontSize: '0.85rem', fontWeight: 500 }}>Ver Primeros</span></>
              ) : (
                <><ArrowDown size={14} /> <span style={{ fontSize: '0.85rem', fontWeight: 500 }}>Ver Últimos</span></>
              )}
            </button>
          </div>
          <div className="card-body">
            <p style={{ color: 'var(--text-light)', fontSize: '0.85rem', marginBottom: '1rem' }}>
              Planificación estimada de pollitos disponibles para faena según las cargas registradas y distintos escenarios de mortalidad.
            </p>
            <div className="table-responsive" style={{ maxHeight: '60vh', overflowY: 'auto', borderRadius: '8px', border: '1px solid var(--border)' }}>
              <table className="data-table" style={{ position: 'relative', width: '100%', borderCollapse: 'collapse' }}>
                <thead style={{ position: 'sticky', top: 0, zIndex: 10, backgroundColor: '#f8fafc', boxShadow: '0 2px 4px rgba(0,0,0,0.06)' }}>
                  <tr>
                    <th>Semana de Faena</th>
                    <th className="text-right">Cargas Incluidas</th>
                    <th className="text-right">Mejor Caso</th>
                    <th className="text-right">Peor Caso</th>
                    <th className="text-right">Rango</th>
                  </tr>
                </thead>
                <tbody>
                  {(ordenDesc ? [...forecast.semanas].reverse() : forecast.semanas).map((sem, idx) => {
                    const mejor = sem.mejor_caso?.pollitos_disponibles ?? 0
                    const peor = sem.peor_caso?.pollitos_disponibles ?? 0
                    return (
                      <tr key={idx}>
                        <td>
                          <strong>{formatDateShort(sem.inicio)}</strong>
                          <span style={{ color: 'var(--text-light)', fontSize: '0.8rem' }}> – {formatDateShort(sem.fin)}</span>
                        </td>
                        <td className="text-right">{sem.semanas_incluidas}</td>
                        <td className="text-right" style={{ color: 'var(--primary)', fontWeight: 600 }}>
                          {formatNumber(mejor)}
                        </td>
                        <td className="text-right" style={{ color: 'var(--orange)', fontWeight: 600 }}>
                          {formatNumber(peor)}
                        </td>
                        <td className="text-right" style={{ fontSize: '0.85rem', color: 'var(--text-light)' }}>
                          {mejor > 0 ? `${formatNumber(peor)} – ${formatNumber(mejor)}` : '—'}
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

      {/* Empty state */}
      {!produccion && (
        <motion.div variants={itemVariants} className="card">
          <div className="card-body" style={{ textAlign: 'center', padding: '3rem' }}>
            <p style={{ fontSize: '1.1rem', color: 'var(--text-light)', display: 'flex', alignItems: 'center', justifyContent: 'center', gap: 6 }}>
              <Factory size={20} /> No hay datos de cargas registrados. Suba el archivo Excel para comenzar.
            </p>
          </div>
        </motion.div>
      )}
    </motion.div>
  )
}
