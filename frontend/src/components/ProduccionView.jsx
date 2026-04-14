import React, { useState, useEffect, useRef } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import { Factory, UploadCloud, FileSpreadsheet, Trash2, Calendar, TrendingDown, TrendingUp, Loader2, X, ArrowDown, ArrowUp } from 'lucide-react'
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

export default function ProduccionView() {
  const [produccion, setProduccion] = useState(null)
  const [simulacion, setSimulacion] = useState(null)
  const [forecast, setForecast] = useState(null)
  const [ofertaPorSemana, setOfertaPorSemana] = useState({})
  const [loading, setLoading] = useState(true)
  const [uploading, setUploading] = useState(false)
  const [file, setFile] = useState(null)
  const [ordenDesc, setOrdenDesc] = useState(true)
  const inputRef = useRef(null)
  const configSim = simulacion?.configuracion || null

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
          aves_en_oferta: c.aves_en_oferta || 0,
          lotes: c.lotes || 0,
          granjas: c.granjas || [],
        }
      }
      setOfertaPorSemana(mapa)
    } catch {
      // No offer data available
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
                <span> Las columnas <strong>Oferta Actual</strong> y <strong>Cobertura</strong> muestran las aves vinculadas desde el archivo de oferta para cada semana.</span>
              )}
            </p>
            <div className="table-container" style={{ maxHeight: '60vh', overflowY: 'auto', overflowX: 'auto', borderRadius: '8px', border: '1px solid var(--border)' }}>
              <table style={{ position: 'relative', width: '100%', borderCollapse: 'collapse' }}>
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
                      </>
                    )}
                  </tr>
                </thead>
                <tbody>
                  {(ordenDesc ? [...simulacion.simulacion].reverse() : simulacion.simulacion).map((sem, idx) => {
                    const oferta = ofertaPorSemana[sem.fecha_desde]
                    const peorCaso = sem.simulaciones[sem.simulaciones.length - 1]?.pollitos_disponibles || 0
                    const mejorCaso = sem.simulaciones[0]?.pollitos_disponibles || 0
                    const tieneOferta = Object.keys(ofertaPorSemana).length > 0
                    const coberturaPct = oferta && peorCaso > 0 ? Math.round(oferta.aves_en_oferta / peorCaso * 1000) / 10 : null
                    const enRango = oferta && oferta.aves_en_oferta >= peorCaso && oferta.aves_en_oferta <= mejorCaso
                    const excede = oferta && oferta.aves_en_oferta > mejorCaso
                    return (
                      <tr key={idx}>
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
                                  background: enRango ? '#d1fae5' : excede ? '#fee2e2' : '#fef3c7',
                                  color: enRango ? '#047857' : excede ? '#b91c1c' : '#92400e',
                                }}>
                                  {coberturaPct}%
                                </span>
                              ) : (
                                <span style={{ color: 'var(--text-light)', fontSize: '0.8rem' }}>-</span>
                              )}
                            </td>
                          </>
                        )}
                      </tr>
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
