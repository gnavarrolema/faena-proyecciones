import { useState, useEffect } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import { BarChart2, Activity, Home, List, AlertCircle, Download, CalendarOff, Plus, X } from 'lucide-react'
import toast from 'react-hot-toast'
import { generarProyeccion, generarEscenarios, getFeriados, addFeriadoCustom, deleteFeriadoCustom, getParametros, getOfertaTrazabilidad, getReferenciaProduccion } from '../services/api'
import { exportOfertaPDF } from '../utils/pdfExport'
import VariantesPicker from './VariantesPicker'

const DIAS_SEMANA = ['Lunes', 'Martes', 'Miércoles', 'Jueves', 'Viernes', 'Sábado', 'Domingo']

function formatNumber(n) {
  if (n == null) return '-'
  return n.toLocaleString('es-AR')
}

function getSexoBadge(sexo) {
  if (sexo === 'M') return <span className="badge badge-info">M</span>
  if (sexo === 'H') return <span className="badge badge-warning">H</span>
  return <span className="badge badge-success">-</span>
}

const containerVariants = {
  hidden: { opacity: 0 },
  show: {
    opacity: 1,
    transition: { staggerChildren: 0.1 }
  }
}

const itemVariants = {
  hidden: { opacity: 0, y: 20 },
  show: { opacity: 1, y: 0, transition: { duration: 0.4, ease: 'easeOut' } }
}

const PLAN_BADGES = {
  planificado: { label: 'Tomado en planificación', color: '#166534', bg: '#f0fdf4' },
  no_asignado: { label: 'Sin capacidad', color: '#92400e', bg: '#fffbeb' },
  fuera_rango: { label: 'Fuera de rango', color: '#991b1b', bg: '#fef2f2' },
  pendiente: { label: 'Pendiente', color: '#475569', bg: '#f8fafc' },
}

const MARTES_BADGES = {
  actualizado: { label: 'Ajustado con martes', color: '#1d4ed8', bg: '#eff6ff' },
  confirmado: { label: 'Confirmado con martes', color: '#0369a1', bg: '#f0f9ff' },
  sin_ajuste: { label: 'Sin archivo martes', color: '#64748b', bg: '#f8fafc' },
}

function getDiaNombre(fechaStr) {
  const dt = new Date(fechaStr + 'T12:00:00')
  const idx = dt.getDay() === 0 ? 6 : dt.getDay() - 1
  return DIAS_SEMANA[idx]
}

function formatDiasElegibles(dias) {
  if (!dias || dias.length === 0) return '-'
  return dias.map((dia) => getDiaNombre(dia)).join(', ')
}

function distribuirObjetivoConTopes(total, pesos, topes) {
  let restante = Math.max(0, Math.round(Number(total) || 0))
  const topesFinales = topes.map(v => Math.max(0, Math.round(Number(v) || 0)))
  const resultado = topesFinales.map(() => 0)
  const activos = new Set(topesFinales.map((_, idx) => idx).filter(idx => topesFinales[idx] > 0))
  const pesosFinales = pesos.slice(0, topesFinales.length).map(v => Math.max(0, Number(v) || 0))

  while (restante > 0 && activos.size > 0) {
    const indices = Array.from(activos)
    const sumaPesos = indices.reduce((acc, idx) => acc + pesosFinales[idx], 0)
    let asignado = 0

    for (const idx of indices) {
      const peso = sumaPesos > 0 ? pesosFinales[idx] : 1
      const divisor = sumaPesos > 0 ? sumaPesos : indices.length
      const cupo = topesFinales[idx] - resultado[idx]
      const sugerido = Math.max(1, Math.round(restante * peso / divisor))
      const valor = Math.min(cupo, sugerido)
      resultado[idx] += valor
      asignado += valor
      if (resultado[idx] >= topesFinales[idx]) activos.delete(idx)
    }

    restante -= asignado
    if (asignado <= 0) break
  }

  return resultado
}

const MODOS_PLANIFICACION = {
  cascada_madurez: {
    label: 'Prioridad por Madurez',
  },
  optimizacion_restricciones: {
    label: 'Optimización de Restricciones',
  },
}

function notificarResumenPlanificacion(proyeccion, origen = 'Planificación generada') {
  if (!proyeccion) return

  const infoModo = MODOS_PLANIFICACION[proyeccion.modo_planificacion] || MODOS_PLANIFICACION.cascada_madurez
  const diasTotales = proyeccion.dias?.length || 0
  const diasUtilizados = proyeccion.dias?.filter((dia) => (dia.total_pollos || 0) > 0).length || 0
  const totalNoAsignado = proyeccion.total_pollos_no_asignados || 0
  const totalFueraRango = proyeccion.total_pollos_fuera_rango || 0

  let estadoCobertura = 'Toda la oferta de esta semana quedó absorbida en la planificación.'
  if (totalNoAsignado > 0 && totalFueraRango > 0) {
    estadoCobertura = `Quedaron ${formatNumber(totalNoAsignado)} pollos sin capacidad y ${formatNumber(totalFueraRango)} fuera de rango.`
  } else if (totalNoAsignado > 0) {
    estadoCobertura = `Quedaron ${formatNumber(totalNoAsignado)} pollos sin capacidad en esta corrida.`
  } else if (totalFueraRango > 0) {
    estadoCobertura = `Quedaron ${formatNumber(totalFueraRango)} pollos fuera de rango para esta semana.`
  }

  const notaAlternativa = proyeccion.planificacion_alternativa
    ? 'También quedó disponible el modo de optimización como referencia técnica.'
    : ''

  toast.success(
    `${origen}: ${infoModo.label}. Se distribuyeron ${formatNumber(proyeccion.total_pollos_semana)} pollos en ${diasUtilizados} de ${diasTotales} días. ${estadoCobertura} ${notaAlternativa}`.trim(),
    { duration: 6500 },
  )
}

export default function OfertaTable({ oferta, onGenerarProyeccion, deficitGuardado, onDeficitUsado }) {
  const [fechaInicio, setFechaInicio] = useState('')
  const [pollosPorDia, setPollosPorDia] = useState(35000)
  const [usarObjetivosDiarios, setUsarObjetivosDiarios] = useState(false)
  const [objetivosDiarios, setObjetivosDiarios] = useState([35000, 35000, 35000, 35000, 35000])
  const [diasFaena, setDiasFaena] = useState(5)
  const [habilitarSabado, setHabilitarSabado] = useState(false)
  const [trazabilidad, setTrazabilidad] = useState(null)
  const [trazabilidadLoading, setTrazabilidadLoading] = useState(false)
  const [parametrosPlan, setParametrosPlan] = useState(null)

  useEffect(() => {
    getParametros().then(params => {
      setParametrosPlan(params)
      if (params.pollos_diarios_objetivo_max) {
        setPollosPorDia(params.pollos_diarios_objetivo_max)
        setObjetivosDiarios(prev => prev.map(() => params.pollos_diarios_objetivo_max))
      }
    }).catch(() => {})
  }, [])

  const cantidadDiasObjetivo = habilitarSabado ? Math.max(diasFaena, 6) : diasFaena

  useEffect(() => {
    setObjetivosDiarios(prev => {
      const base = prev.length > 0 ? prev : [pollosPorDia]
      return Array.from({ length: cantidadDiasObjetivo }, (_, idx) => base[idx] ?? pollosPorDia)
    })
  }, [cantidadDiasObjetivo, pollosPorDia])

  useEffect(() => {
    let active = true
    const cargarTrazabilidad = async () => {
      setTrazabilidadLoading(true)
      try {
        const data = await getOfertaTrazabilidad()
        if (active) setTrazabilidad(data)
      } catch {
        if (active) setTrazabilidad(null)
      } finally {
        if (active) setTrazabilidadLoading(false)
      }
    }

    if (oferta?.ofertas?.length > 0) {
      cargarTrazabilidad()
    }

    return () => { active = false }
  }, [oferta?.total_lotes, oferta?.total_pollos])
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState(null)
  const [feriadosSemana, setFeriadosSemana] = useState([])
  const [feriadosLoading, setFeriadosLoading] = useState(false)
  const [customFeriadoFecha, setCustomFeriadoFecha] = useState('')
  const [customFeriadoDesc, setCustomFeriadoDesc] = useState('')
  const [addingCustom, setAddingCustom] = useState(false)
  const [incluirDeficit, setIncluirDeficit] = useState(false)
  const [variantesData, setVariantesData] = useState(null)
  const [variantesLoading, setVariantesLoading] = useState(false)
  const [referenciaBB, setReferenciaBB] = useState(null)
  const [referenciaBBLoading, setReferenciaBBLoading] = useState(false)
  // Gallinas
  const [gallinasDia, setGallinasDia] = useState({}) // {fecha_iso: {livianas: int, pesadas: int}}
  const [gallinasInputFecha, setGallinasInputFecha] = useState('')
  const [gallinasInputCant, setGallinasInputCant] = useState(25000)
  const [gallinasInputTipo, setGallinasInputTipo] = useState('liviana')

  // Cargar feriados cuando se selecciona fecha de inicio
  useEffect(() => {
    if (!fechaInicio) {
      setFeriadosSemana([])
      return
    }

    const cargarFeriados = async () => {
      setFeriadosLoading(true)
      try {
        const dt = new Date(fechaInicio + 'T12:00:00')
        const anio = dt.getFullYear()
        const todos = await getFeriados(anio)

        // Filtrar feriados que caen en la semana seleccionada (lunes a sábado)
        const inicio = new Date(fechaInicio + 'T00:00:00')
        const fin = new Date(inicio)
        fin.setDate(fin.getDate() + (diasFaena >= 6 ? 5 : 4))
        fin.setHours(23, 59, 59, 999)

        const diasReales = habilitarSabado ? 5 : (diasFaena >= 6 ? 5 : 4)
        const enSemana = todos.filter(f => {
          const fd = new Date(f.fecha + 'T12:00:00')
          return fd >= inicio && fd <= fin && fd.getDay() !== 0 // excluir domingos
        })
        setFeriadosSemana(enSemana)
      } catch (err) {
        console.warn('Error cargando feriados:', err)
        setFeriadosSemana([])
      } finally {
        setFeriadosLoading(false)
      }
    }
    cargarFeriados()
  }, [fechaInicio, diasFaena, habilitarSabado])

  useEffect(() => {
    let active = true
    if (!fechaInicio) {
      setReferenciaBB(null)
      return () => { active = false }
    }

    const cargarReferenciaBB = async () => {
      setReferenciaBBLoading(true)
      try {
        const data = await getReferenciaProduccion(fechaInicio)
        if (active) setReferenciaBB(data)
      } catch {
        if (active) setReferenciaBB(null)
      } finally {
        if (active) setReferenciaBBLoading(false)
      }
    }

    cargarReferenciaBB()
    return () => { active = false }
  }, [fechaInicio])

  if (!oferta || !oferta.ofertas || oferta.ofertas.length === 0) {
    return (
      <motion.div
        initial={{ opacity: 0, scale: 0.95 }}
        animate={{ opacity: 1, scale: 1 }}
        className="card"
      >
        <div className="card-body" style={{ textAlign: 'center', padding: '3rem' }}>
          <p style={{ fontSize: '1.1rem', color: 'var(--text-light)', display: 'flex', alignItems: 'center', justifyContent: 'center', gap: 6 }}>
            <List size={20} /> No hay oferta cargada. Vaya a "Cargar Oferta" primero.
          </p>
        </div>
      </motion.div>
    )
  }

  const handleAddCustomFeriado = async () => {
    if (!customFeriadoFecha) return
    setAddingCustom(true)
    try {
      await addFeriadoCustom(customFeriadoFecha, customFeriadoDesc || 'Feriado personalizado')
      toast.success('Feriado agregado')
      setCustomFeriadoFecha('')
      setCustomFeriadoDesc('')
      // Re-cargar feriados
      if (fechaInicio) {
        const dt = new Date(fechaInicio + 'T12:00:00')
        const todos = await getFeriados(dt.getFullYear())
        const inicio = new Date(fechaInicio + 'T00:00:00')
        const fin = new Date(inicio)
        fin.setDate(fin.getDate() + (diasFaena >= 6 ? 5 : 4))
        fin.setHours(23, 59, 59, 999)
        const enSemana = todos.filter(f => {
          const fd = new Date(f.fecha + 'T12:00:00')
          return fd >= inicio && fd <= fin && fd.getDay() !== 0
        })
        setFeriadosSemana(enSemana)
      }
    } catch (err) {
      toast.error(err.response?.data?.detail || 'Error al agregar feriado')
    } finally {
      setAddingCustom(false)
    }
  }

  const handleDeleteCustomFeriado = async (fecha) => {
    try {
      await deleteFeriadoCustom(fecha)
      toast.success('Feriado eliminado')
      setFeriadosSemana(prev => prev.filter(f => f.fecha !== fecha))
    } catch (err) {
      toast.error(err.response?.data?.detail || 'Error al eliminar feriado')
    }
  }

  const handleGenerar = async () => {
    if (!fechaInicio) {
      setError('Seleccione la fecha de inicio de la semana (lunes)')
      return
    }
    setLoading(true)
    setError(null)
    try {
      const data = await generarProyeccion({
        fecha_inicio_semana: fechaInicio,
        dias_faena: diasFaena,
        pollos_por_dia: pollosPorDia,
        objetivos_diarios: usarObjetivosDiarios ? objetivosDiarios.slice(0, cantidadDiasObjetivo) : null,
        habilitar_sabado: habilitarSabado,
        gallinas: Object.keys(gallinasDia).length > 0 ? gallinasDia : null,
        incluir_deficit: incluirDeficit,
      })
      if (incluirDeficit && onDeficitUsado) onDeficitUsado()
      try {
        const trazData = await getOfertaTrazabilidad()
        setTrazabilidad(trazData)
      } catch {}
      onGenerarProyeccion(data)
      notificarResumenPlanificacion(data)
    } catch (err) {
      setError(err.response?.data?.detail || 'Error al generar la planificación')
    } finally {
      setLoading(false)
    }
  }

  // Resumen por granja
  const granjas = oferta.granjas || {}
  const diasHabiles = diasFaena - feriadosSemana.length
  const totalObjetivoPlan = objetivosDiarios
    .slice(0, cantidadDiasObjetivo)
    .reduce((acc, val) => acc + (Number(val) || 0), 0)
  const coberturasBB = referenciaBB?.coberturas || []
  const coberturaPeorBB = coberturasBB.length > 0 ? coberturasBB[coberturasBB.length - 1] : null
  const coberturaMejorBB = coberturasBB.length > 0 ? coberturasBB[0] : null
  const disponibleBBPeor = coberturaPeorBB?.disponibles ?? null
  const disponibleBBMejor = coberturaMejorBB?.disponibles ?? null
  const deficitObjetivoBB = disponibleBBPeor != null ? Math.max(0, totalObjetivoPlan - disponibleBBPeor) : 0
  const excedenteObjetivoBB = disponibleBBPeor != null ? Math.max(0, disponibleBBPeor - totalObjetivoPlan) : 0
  const coberturaObjetivoBB = disponibleBBPeor && disponibleBBPeor > 0
    ? Math.round((totalObjetivoPlan / disponibleBBPeor) * 1000) / 10
    : null
  const capacidadConHorasExtras = parametrosPlan?.capacidad_con_horas_extras || pollosPorDia
  const limiteSabado = parametrosPlan?.limite_sabado || 20000
  const topesObjetivo = Array.from({ length: cantidadDiasObjetivo }, (_, idx) => {
    if (idx === 5) return habilitarSabado ? limiteSabado : 0
    return pollosPorDia
  })
  const topesHorasExtras = Array.from({ length: cantidadDiasObjetivo }, (_, idx) => {
    if (idx === 5) return habilitarSabado ? limiteSabado : 0
    return capacidadConHorasExtras
  })
  const capacidadSemanalObjetivo = topesObjetivo.reduce((acc, val) => acc + val, 0)
  const capacidadSemanalHorasExtras = topesHorasExtras.reduce((acc, val) => acc + val, 0)
  const objetivoSugeridoBB = disponibleBBPeor != null
    ? Math.min(disponibleBBPeor, capacidadSemanalObjetivo)
    : capacidadSemanalObjetivo
  const bbSuperaCapacidad = disponibleBBPeor != null && disponibleBBPeor > capacidadSemanalObjetivo
  const fechaObjetivoLabel = (idx) => {
    if (!fechaInicio) return DIAS_SEMANA[idx] || `Día ${idx + 1}`
    const dt = new Date(fechaInicio + 'T12:00:00')
    dt.setDate(dt.getDate() + idx)
    const dia = DIAS_SEMANA[idx] || `Día ${idx + 1}`
    return `${dia} ${dt.toLocaleDateString('es-AR', { day: '2-digit', month: '2-digit' })}`
  }

  return (
    <motion.div
      variants={containerVariants}
      initial="hidden"
      animate="show"
    >
      {/* Stats */}
      <motion.div variants={itemVariants} className="stats-grid">
        <div className="stat-card">
          <div className="stat-label">Total Lotes</div>
          <div className="stat-value blue">{oferta.total_lotes}</div>
        </div>
        <div className="stat-card">
          <div className="stat-label">Total Pollos</div>
          <div className="stat-value green">{formatNumber(oferta.total_pollos)}</div>
        </div>
        <div className="stat-card">
          <div className="stat-label">Granjas</div>
          <div className="stat-value orange">{Object.keys(granjas).length}</div>
        </div>
      </motion.div>

      {/* Generar planificación */}
      <motion.div variants={itemVariants} className="card">
        <div className="card-header">
          <h2><Activity size={18} style={{ verticalAlign: 'middle', marginRight: 6 }} /> Generar Planificación de Faena</h2>
        </div>
        <div className="card-body">
          <div className="form-row">
            <div className="form-group">
              <label>Fecha Inicio Semana (Lunes)</label>
              <input
                type="date"
                className="form-control"
                value={fechaInicio}
                onChange={(e) => setFechaInicio(e.target.value)}
              />
            </div>
            <div className="form-group">
              <label>Pollos por Día (objetivo)</label>
              <input
                type="number"
                className="form-control"
                value={pollosPorDia}
                onChange={(e) => setPollosPorDia(parseInt(e.target.value) || 0)}
              />
            </div>
            <div className="form-group">
              <label>Días de Faena (L-V)</label>
              <select
                className="form-control"
                value={diasFaena}
                onChange={(e) => setDiasFaena(parseInt(e.target.value))}
              >
                <option value={5}>5 días (Lun-Vie)</option>
              </select>
            </div>
          </div>

          <div style={{
            padding: '0.85rem 1rem',
            background: usarObjetivosDiarios ? 'rgba(22, 101, 52, 0.07)' : '#f8fafc',
            border: `1px solid ${usarObjetivosDiarios ? 'rgba(22, 101, 52, 0.25)' : 'var(--border)'}`,
            borderRadius: 8,
            marginBottom: '1rem',
          }}>
            <label style={{
              display: 'flex',
              alignItems: 'center',
              gap: 8,
              fontSize: '0.9rem',
              cursor: 'pointer',
              marginBottom: usarObjetivosDiarios ? '0.75rem' : 0,
            }}>
              <input
                type="checkbox"
                checked={usarObjetivosDiarios}
                onChange={(e) => setUsarObjetivosDiarios(e.target.checked)}
              />
              <span style={{ fontWeight: 700, color: usarObjetivosDiarios ? '#166534' : 'var(--text-light)' }}>
                Usar objetivo comercial por día
              </span>
              {usarObjetivosDiarios && (
                <span style={{
                  padding: '0.15rem 0.5rem',
                  background: 'rgba(22, 101, 52, 0.1)',
                  borderRadius: 12,
                  fontSize: '0.78rem',
                  color: '#166534',
                  fontWeight: 600,
                }}>
                  Total semana: {formatNumber(totalObjetivoPlan)}
                </span>
              )}
            </label>

            {usarObjetivosDiarios && (
              <>
                <div style={{ display: 'flex', gap: '0.5rem', flexWrap: 'wrap', marginBottom: '0.65rem' }}>
                  <button
                    type="button"
                    className="btn btn-sm btn-outline"
                    onClick={() => setObjetivosDiarios(prev => prev.map(() => pollosPorDia))}
                  >
                    Igualar a objetivo general
                  </button>
                  <button
                    type="button"
                    className="btn btn-sm btn-outline"
                    onClick={() => setObjetivosDiarios(prev => prev.map((_, idx) => (idx <= 1 ? 38000 : 35000)))}
                  >
                    Perfil gerente 38/38/35/35/35
                  </button>
                  {referenciaBB?.encontrada && disponibleBBPeor != null && (
                    <button
                      type="button"
                      className="btn btn-sm btn-outline"
                      onClick={() => {
                        setObjetivosDiarios(distribuirObjetivoConTopes(objetivoSugeridoBB, objetivosDiarios, topesObjetivo))
                        toast.success(`Objetivo semanal ajustado a ${formatNumber(objetivoSugeridoBB)} pollos`)
                      }}
                    >
                      Ajustar sugerido
                    </button>
                  )}
                </div>
                {fechaInicio && (
                  <div style={{
                    display: 'grid',
                    gridTemplateColumns: 'repeat(auto-fit, minmax(170px, 1fr))',
                    gap: '0.65rem',
                    padding: '0.75rem',
                    marginBottom: '0.75rem',
                    background: referenciaBB?.encontrada
                      ? (deficitObjetivoBB > 0 ? 'rgba(251, 146, 60, 0.1)' : (bbSuperaCapacidad ? 'rgba(59, 130, 246, 0.08)' : 'rgba(34, 197, 94, 0.08)'))
                      : '#f8fafc',
                    border: `1px solid ${referenciaBB?.encontrada
                      ? (deficitObjetivoBB > 0 ? 'rgba(251, 146, 60, 0.35)' : (bbSuperaCapacidad ? 'rgba(59, 130, 246, 0.25)' : 'rgba(34, 197, 94, 0.25)'))
                      : 'var(--border)'}`,
                    borderRadius: 8,
                  }}>
                    <div>
                      <div style={{ fontSize: '0.72rem', color: 'var(--text-light)', marginBottom: 2 }}>Referencia BB</div>
                      <div style={{ fontWeight: 700, color: referenciaBB?.encontrada ? 'var(--text)' : 'var(--text-light)' }}>
                        {referenciaBBLoading
                          ? 'Consultando...'
                          : referenciaBB?.encontrada
                            ? `${formatNumber(disponibleBBPeor)} disp.`
                            : 'Sin referencia'}
                      </div>
                      {referenciaBB?.encontrada && disponibleBBMejor != null && disponibleBBPeor != null && (
                        <div style={{ fontSize: '0.72rem', color: 'var(--text-light)', marginTop: 2 }}>
                          Rango {formatNumber(disponibleBBPeor)} - {formatNumber(disponibleBBMejor)}
                        </div>
                      )}
                    </div>
                    <div>
                      <div style={{ fontSize: '0.72rem', color: 'var(--text-light)', marginBottom: 2 }}>Cobertura objetivo</div>
                      <div style={{ fontWeight: 700, color: deficitObjetivoBB > 0 ? '#ea580c' : '#166534' }}>
                        {coberturaObjetivoBB != null ? `${coberturaObjetivoBB}%` : '-'}
                      </div>
                      {referenciaBB?.encontrada && (
                        <div style={{ fontSize: '0.72rem', color: 'var(--text-light)', marginTop: 2 }}>
                          Contra peor escenario configurado
                        </div>
                      )}
                    </div>
                    <div>
                      <div style={{ fontSize: '0.72rem', color: 'var(--text-light)', marginBottom: 2 }}>Capacidad semanal</div>
                      <div style={{ fontWeight: 700, color: bbSuperaCapacidad ? '#1d4ed8' : 'var(--text)' }}>
                        {formatNumber(capacidadSemanalObjetivo)}
                      </div>
                      <div style={{ fontSize: '0.72rem', color: 'var(--text-light)', marginTop: 2 }}>
                        Sugerido: {formatNumber(objetivoSugeridoBB)} · Máx. con HE: {formatNumber(capacidadSemanalHorasExtras)}
                      </div>
                    </div>
                    <div>
                      <div style={{ fontSize: '0.72rem', color: 'var(--text-light)', marginBottom: 2 }}>
                        {bbSuperaCapacidad ? 'BB sobre capacidad' : (deficitObjetivoBB > 0 ? 'Déficit propio' : 'Margen propio')}
                      </div>
                      <div style={{ fontWeight: 700, color: deficitObjetivoBB > 0 ? '#ea580c' : (bbSuperaCapacidad ? '#1d4ed8' : '#166534') }}>
                        {referenciaBB?.encontrada
                          ? formatNumber(bbSuperaCapacidad ? disponibleBBPeor - capacidadSemanalObjetivo : (deficitObjetivoBB > 0 ? deficitObjetivoBB : excedenteObjetivoBB))
                          : '-'}
                      </div>
                      {referenciaBB?.encontrada && referenciaBB.total_semanas_referenciadas > 0 && (
                        <div style={{ fontSize: '0.72rem', color: 'var(--text-light)', marginTop: 2 }}>
                          {referenciaBB.total_semanas_referenciadas} semana{referenciaBB.total_semanas_referenciadas !== 1 ? 's' : ''} BB
                        </div>
                      )}
                    </div>
                  </div>
                )}
                <div style={{
                  display: 'grid',
                  gridTemplateColumns: 'repeat(auto-fit, minmax(130px, 1fr))',
                  gap: '0.65rem',
                }}>
                  {objetivosDiarios.slice(0, cantidadDiasObjetivo).map((valor, idx) => (
                    <div key={idx}>
                      <label style={{ fontSize: '0.75rem', color: 'var(--text-light)', display: 'block', marginBottom: 3 }}>
                        {fechaObjetivoLabel(idx)}
                      </label>
                      <input
                        type="number"
                        className="form-control"
                        value={valor}
                        min={0}
                        step={1000}
                        onChange={(e) => {
                          const siguiente = [...objetivosDiarios]
                          siguiente[idx] = parseInt(e.target.value) || 0
                          setObjetivosDiarios(siguiente)
                        }}
                      />
                    </div>
                  ))}
                </div>
              </>
            )}
          </div>

          {/* Sábado + Gallinas */}
          <div style={{ display: 'flex', gap: '1.5rem', flexWrap: 'wrap', marginBottom: '1rem' }}>
            <label style={{
              display: 'flex', alignItems: 'center', gap: 8,
              fontSize: '0.9rem', cursor: 'pointer',
              padding: '0.5rem 0.75rem',
              background: habilitarSabado ? 'rgba(251, 146, 60, 0.1)' : '#f8fafc',
              border: `1px solid ${habilitarSabado ? 'rgba(251, 146, 60, 0.3)' : 'var(--border)'}`,
              borderRadius: 8,
            }}>
              <input
                type="checkbox"
                checked={habilitarSabado}
                onChange={(e) => setHabilitarSabado(e.target.checked)}
              />
              <span style={{ fontWeight: 600, color: habilitarSabado ? '#ea580c' : 'var(--text-light)' }}>
                Habilitar Sábado (máx. 20.000 aves)
              </span>
              {habilitarSabado && (
                <span style={{ fontSize: '0.75rem', color: '#ea580c', fontStyle: 'italic' }}>
                  Solo para feriados o gallinas
                </span>
              )}
            </label>
          </div>

          {/* Gallinas */}
          {fechaInicio && (
            <div style={{
              padding: '0.75rem 1rem',
              background: Object.keys(gallinasDia).length > 0 ? 'rgba(139, 92, 246, 0.08)' : '#f8fafc',
              border: `1px solid ${Object.keys(gallinasDia).length > 0 ? 'rgba(139, 92, 246, 0.25)' : 'var(--border)'}`,
              borderRadius: 8,
              marginBottom: '1rem',
            }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: '0.5rem' }}>
                <span style={{ fontSize: '0.85rem', fontWeight: 600, color: '#7c3aed' }}>
                  Faena de Gallinas
                </span>
                <span style={{ fontSize: '0.75rem', color: 'var(--text-light)' }}>
                  (reduce la capacidad de pollos ese día)
                </span>
              </div>
              <div style={{ display: 'flex', gap: '0.5rem', alignItems: 'flex-end', flexWrap: 'wrap' }}>
                <div>
                  <label style={{ fontSize: '0.75rem', color: 'var(--text-light)', display: 'block', marginBottom: 2 }}>Fecha</label>
                  <input
                    type="date"
                    className="form-control"
                    value={gallinasInputFecha}
                    onChange={e => setGallinasInputFecha(e.target.value)}
                    style={{ fontSize: '0.85rem', padding: '0.35rem 0.5rem' }}
                  />
                </div>
                <div>
                  <label style={{ fontSize: '0.75rem', color: 'var(--text-light)', display: 'block', marginBottom: 2 }}>Tipo</label>
                  <select
                    className="form-control"
                    value={gallinasInputTipo}
                    onChange={e => setGallinasInputTipo(e.target.value)}
                    style={{ fontSize: '0.85rem', padding: '0.35rem 0.5rem', minWidth: 110 }}
                  >
                    <option value="liviana">Liviana</option>
                    <option value="pesada">Pesada</option>
                  </select>
                </div>
                <div>
                  <label style={{ fontSize: '0.75rem', color: 'var(--text-light)', display: 'block', marginBottom: 2 }}>Cantidad</label>
                  <input
                    type="number"
                    className="form-control"
                    value={gallinasInputCant}
                    onChange={e => setGallinasInputCant(parseInt(e.target.value) || 0)}
                    style={{ fontSize: '0.85rem', padding: '0.35rem 0.5rem', width: 120 }}
                  />
                </div>
                <button
                  className="btn btn-sm btn-outline"
                  disabled={!gallinasInputFecha || gallinasInputCant <= 0}
                  onClick={() => {
                    setGallinasDia(prev => {
                      const entry = prev[gallinasInputFecha] || { livianas: 0, pesadas: 0 }
                      return {
                        ...prev,
                        [gallinasInputFecha]: {
                          ...entry,
                          [gallinasInputTipo === 'pesada' ? 'pesadas' : 'livianas']: gallinasInputCant,
                        },
                      }
                    })
                    setGallinasInputFecha('')
                  }}
                  style={{ padding: '0.35rem 0.7rem' }}
                >
                  <Plus size={14} /> Agregar
                </button>
              </div>
              {Object.keys(gallinasDia).length > 0 && (
                <div style={{ display: 'flex', flexWrap: 'wrap', gap: '0.4rem', marginTop: '0.5rem' }}>
                  {Object.entries(gallinasDia).map(([fecha, val]) => {
                    const chips = []
                    if (val.livianas > 0) {
                      chips.push(
                        <span key={`${fecha}-liv`} style={{
                          display: 'inline-flex', alignItems: 'center', gap: 6,
                          padding: '0.3rem 0.7rem',
                          background: 'rgba(139, 92, 246, 0.12)',
                          border: '1px solid rgba(139, 92, 246, 0.3)',
                          borderRadius: 20, fontSize: '0.8rem', color: '#7c3aed',
                        }}>
                          <strong>{getDiaNombre(fecha)}</strong> — {val.livianas.toLocaleString('es-AR')} livianas
                          <button
                            onClick={() => setGallinasDia(prev => {
                              const next = { ...prev }
                              if (next[fecha]) {
                                next[fecha] = { ...next[fecha], livianas: 0 }
                                if (next[fecha].pesadas <= 0) delete next[fecha]
                              }
                              return next
                            })}
                            style={{ background: 'none', border: 'none', cursor: 'pointer', padding: 0, color: '#7c3aed', display: 'flex' }}
                          >
                            <X size={12} />
                          </button>
                        </span>
                      )
                    }
                    if (val.pesadas > 0) {
                      chips.push(
                        <span key={`${fecha}-pes`} style={{
                          display: 'inline-flex', alignItems: 'center', gap: 6,
                          padding: '0.3rem 0.7rem',
                          background: 'rgba(219, 39, 119, 0.1)',
                          border: '1px solid rgba(219, 39, 119, 0.3)',
                          borderRadius: 20, fontSize: '0.8rem', color: '#be185d',
                        }}>
                          <strong>{getDiaNombre(fecha)}</strong> — {val.pesadas.toLocaleString('es-AR')} pesadas
                          <button
                            onClick={() => setGallinasDia(prev => {
                              const next = { ...prev }
                              if (next[fecha]) {
                                next[fecha] = { ...next[fecha], pesadas: 0 }
                                if (next[fecha].livianas <= 0) delete next[fecha]
                              }
                              return next
                            })}
                            style={{ background: 'none', border: 'none', cursor: 'pointer', padding: 0, color: '#be185d', display: 'flex' }}
                          >
                            <X size={12} />
                          </button>
                        </span>
                      )
                    }
                    return chips
                  })}
                </div>
              )}
            </div>
          )}

          {/* Feriados detectados en la semana */}
          <AnimatePresence>
            {fechaInicio && (
              <motion.div
                initial={{ opacity: 0, height: 0 }}
                animate={{ opacity: 1, height: 'auto' }}
                exit={{ opacity: 0, height: 0 }}
                style={{ marginBottom: '1rem', overflow: 'hidden' }}
              >
                <div style={{
                  padding: '0.85rem 1rem',
                  background: feriadosSemana.length > 0 ? 'rgba(251, 146, 60, 0.1)' : 'rgba(34, 197, 94, 0.08)',
                  border: `1px solid ${feriadosSemana.length > 0 ? 'rgba(251, 146, 60, 0.35)' : 'rgba(34, 197, 94, 0.25)'}`,
                  borderRadius: 8,
                }}>
                  <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: feriadosSemana.length > 0 ? '0.6rem' : 0 }}>
                    <CalendarOff size={16} color={feriadosSemana.length > 0 ? '#ea580c' : '#16a34a'} />
                    <span style={{ fontSize: '0.85rem', fontWeight: 600, color: feriadosSemana.length > 0 ? '#ea580c' : '#16a34a' }}>
                      {feriadosLoading ? 'Verificando feriados...' :
                        feriadosSemana.length > 0
                          ? `${feriadosSemana.length} feriado${feriadosSemana.length > 1 ? 's' : ''} en esta semana — se saltarán al generar (${diasHabiles} días hábiles)`
                          : 'Sin feriados en esta semana'
                      }
                    </span>
                  </div>

                  {feriadosSemana.length > 0 && (
                    <div style={{ display: 'flex', flexWrap: 'wrap', gap: '0.4rem', marginBottom: '0.6rem' }}>
                      {feriadosSemana.map(f => (
                        <span key={f.fecha} style={{
                          display: 'inline-flex', alignItems: 'center', gap: 6,
                          padding: '0.3rem 0.7rem',
                          background: f.tipo === 'custom' ? 'rgba(139, 92, 246, 0.12)' : 'rgba(251, 146, 60, 0.15)',
                          border: `1px solid ${f.tipo === 'custom' ? 'rgba(139, 92, 246, 0.3)' : 'rgba(251, 146, 60, 0.3)'}`,
                          borderRadius: 20, fontSize: '0.8rem',
                          color: f.tipo === 'custom' ? '#7c3aed' : '#ea580c',
                        }}>
                          <CalendarOff size={12} />
                          <strong>{getDiaNombre(f.fecha)}</strong> — {f.nombre}
                          {f.tipo === 'custom' && (
                            <button
                              onClick={() => handleDeleteCustomFeriado(f.fecha)}
                              style={{
                                background: 'none', border: 'none', cursor: 'pointer',
                                padding: 0, marginLeft: 2, color: '#7c3aed',
                                display: 'flex', alignItems: 'center',
                              }}
                              title="Eliminar feriado"
                            >
                              <X size={12} />
                            </button>
                          )}
                        </span>
                      ))}
                    </div>
                  )}

                  {/* Agregar feriado custom */}
                  <div style={{
                    display: 'flex', gap: '0.5rem', alignItems: 'flex-end', flexWrap: 'wrap',
                    paddingTop: feriadosSemana.length > 0 ? '0.4rem' : '0.6rem',
                    borderTop: feriadosSemana.length > 0 ? '1px solid rgba(0,0,0,0.06)' : 'none',
                  }}>
                    <div style={{ flex: '0 0 auto' }}>
                      <label style={{ fontSize: '0.75rem', color: 'var(--text-light)', display: 'block', marginBottom: 2 }}>Fecha</label>
                      <input
                        type="date"
                        className="form-control"
                        value={customFeriadoFecha}
                        onChange={e => setCustomFeriadoFecha(e.target.value)}
                        style={{ fontSize: '0.85rem', padding: '0.35rem 0.5rem' }}
                      />
                    </div>
                    <div style={{ flex: 1, minWidth: 140 }}>
                      <label style={{ fontSize: '0.75rem', color: 'var(--text-light)', display: 'block', marginBottom: 2 }}>Descripción (opcional)</label>
                      <input
                        type="text"
                        className="form-control"
                        placeholder="Ej: Feriado puente, Compensación..."
                        value={customFeriadoDesc}
                        onChange={e => setCustomFeriadoDesc(e.target.value)}
                        style={{ fontSize: '0.85rem', padding: '0.35rem 0.5rem' }}
                      />
                    </div>
                    <button
                      className="btn btn-sm btn-outline"
                      disabled={!customFeriadoFecha || addingCustom}
                      onClick={handleAddCustomFeriado}
                      style={{ whiteSpace: 'nowrap', padding: '0.35rem 0.7rem' }}
                    >
                      <Plus size={14} /> Agregar feriado
                    </button>
                  </div>
                </div>
              </motion.div>
            )}
          </AnimatePresence>

          {error && (
            <div style={{
              marginBottom: '1rem',
              padding: '0.75rem',
              background: 'var(--danger-light)',
              color: 'var(--danger)',
              borderRadius: 6,
              fontSize: '0.85rem',
              display: 'flex',
              alignItems: 'center',
              gap: 6
            }}>
              <AlertCircle size={16} /> {error}
            </div>
          )}

          {/* Déficit semana anterior */}
          {deficitGuardado?.existe && (
            <div style={{
              padding: '0.75rem 1rem',
              background: incluirDeficit ? 'rgba(59, 130, 246, 0.1)' : '#f8fafc',
              border: `1px solid ${incluirDeficit ? 'rgba(59, 130, 246, 0.3)' : 'var(--border)'}`,
              borderRadius: 8,
              marginBottom: '1rem',
            }}>
              <label style={{
                display: 'flex', alignItems: 'center', gap: 8,
                fontSize: '0.9rem', cursor: 'pointer',
              }}>
                <input
                  type="checkbox"
                  checked={incluirDeficit}
                  onChange={(e) => setIncluirDeficit(e.target.checked)}
                />
                <span style={{ fontWeight: 600, color: incluirDeficit ? '#2563eb' : 'var(--text-light)' }}>
                  Incluir déficit de semana anterior
                </span>
                <span style={{
                  padding: '0.15rem 0.5rem',
                  background: 'rgba(59, 130, 246, 0.12)',
                  borderRadius: 12,
                  fontSize: '0.78rem',
                  color: '#2563eb',
                  fontWeight: 600,
                }}>
                  {deficitGuardado.total_lotes} lote{deficitGuardado.total_lotes !== 1 ? 's' : ''} — {formatNumber(deficitGuardado.total_pollos)} pollos
                </span>
              </label>
              <span style={{ fontSize: '0.75rem', color: 'var(--text-light)', marginLeft: 26 }}>
                Semana origen: {deficitGuardado.semana_origen}
              </span>
            </div>
          )}

          <div style={{ display: 'flex', gap: '0.75rem', flexWrap: 'wrap' }}>
            <button className="btn btn-primary" onClick={handleGenerar} disabled={loading || variantesLoading}>
              {loading ? (
                <><span className="spinner" style={{ width: 16, height: 16, marginRight: 6 }}></span> Generando...</>
              ) : (
                <><BarChart2 size={16} /> Generar Planificación{feriadosSemana.length > 0 ? ` (${diasHabiles} días hábiles)` : ''}{habilitarSabado ? ' + Sábado' : ''}</>
              )}
            </button>
            <button
              className="btn btn-outline"
              disabled={loading || variantesLoading || !fechaInicio}
              onClick={async () => {
                if (!fechaInicio) {
                  setError('Seleccione la fecha de inicio de la semana (lunes)')
                  return
                }
                setVariantesLoading(true)
                setError(null)
                try {
                  const data = await generarEscenarios({
                    fecha_inicio_semana: fechaInicio,
                    dias_faena: diasFaena,
                    pollos_por_dia: pollosPorDia,
                    objetivos_diarios: usarObjetivosDiarios ? objetivosDiarios.slice(0, cantidadDiasObjetivo) : null,
                    habilitar_sabado: habilitarSabado,
                    gallinas: Object.keys(gallinasDia).length > 0 ? gallinasDia : null,
                    incluir_deficit: incluirDeficit,
                  })
                  setVariantesData(data)
                } catch (err) {
                  setError(err.response?.data?.detail || 'Error al generar variantes')
                } finally {
                  setVariantesLoading(false)
                }
              }}
            >
              {variantesLoading ? (
                <><span className="spinner" style={{ width: 16, height: 16, marginRight: 6 }}></span> Comparando...</>
              ) : (
                <><Activity size={16} /> Comparar Referencias</>
              )}
            </button>
          </div>

          {/* Modal de variantes */}
          <AnimatePresence>
            {variantesData && (
              <VariantesPicker
                data={variantesData}
                onSelect={(proyeccion) => {
                  setVariantesData(null)
                  if (incluirDeficit && onDeficitUsado) onDeficitUsado()
                  onGenerarProyeccion(proyeccion)
                  notificarResumenPlanificacion(proyeccion, 'Referencia activada')
                }}
                onClose={() => setVariantesData(null)}
              />
            )}
          </AnimatePresence>
        </div>
      </motion.div>

      {/* Resumen por granja */}
      <motion.div variants={itemVariants} className="card">
        <div className="card-header">
          <h2><Home size={18} style={{ verticalAlign: 'middle', marginRight: 6 }} /> Resumen por Granja</h2>
          <button className="btn btn-sm btn-outline" onClick={() => exportOfertaPDF(oferta)}>
            <Download size={14} /> Descargar PDF
          </button>
        </div>
        <div className="card-body">
          <div className="table-container">
            <table>
              <thead>
                <tr>
                  <th>Granja</th>
                  <th className="text-right">Lotes</th>
                  <th className="text-right">Pollos</th>
                </tr>
              </thead>
              <tbody>
                {Object.entries(granjas).map(([nombre, info]) => (
                  <tr key={nombre}>
                    <td><strong>{nombre}</strong></td>
                    <td className="text-right">{info.lotes}</td>
                    <td className="text-right">{formatNumber(info.pollos)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      </motion.div>

      {/* Tabla de oferta completa */}
      <motion.div variants={itemVariants} className="card">
        <div className="card-header">
          <h2><List size={18} style={{ verticalAlign: 'middle', marginRight: 6 }} /> Oferta del Jueves y Trazabilidad ({oferta.ofertas.length} lotes)</h2>
        </div>
        <div className="card-body">
          <p style={{ marginBottom: '1rem', fontSize: '0.9rem', color: 'var(--text-light)' }}>
            Esta vista muestra la oferta base del jueves. Los registros <strong>tachados</strong> ya fueron tomados en la planificación actual.
            Si existe archivo del martes, se indica si el lote fue confirmado o ajustado con esos datos.
          </p>

          <div style={{ marginBottom: '1rem', padding: '0.85rem 1rem', borderRadius: 8, background: '#f8fafc', border: '1px solid var(--border)', fontSize: '0.84rem', color: 'var(--text-light)', lineHeight: 1.55 }}>
            <strong style={{ color: 'var(--text)' }}>Cómo leer esta vista:</strong> “Tomado en planificación” significa que el lote ya quedó asignado a un día. “Sin capacidad” significa que el lote <strong>sí fue evaluado</strong> para uno o más días elegibles, pero no cupo sin superar el tope diario. “Fuera de rango” significa que, recalculando edad y peso para cada día de la semana, no alcanzó los mínimos para entrar a faena.
          </div>

          {trazabilidad && (
            <div className="stats-grid" style={{ marginBottom: '1rem' }}>
              <div className="stat-card">
                <div className="stat-label">Tomados en planificación</div>
                <div className="stat-value green">{trazabilidad.resumen.planificados}</div>
              </div>
              <div className="stat-card">
                <div className="stat-label">Sin capacidad</div>
                <div className="stat-value orange">{trazabilidad.resumen.no_asignados}</div>
              </div>
              <div className="stat-card">
                <div className="stat-label">Fuera de rango</div>
                <div className="stat-value" style={{ color: '#dc2626' }}>{trazabilidad.resumen.fuera_rango}</div>
              </div>
              <div className="stat-card">
                <div className="stat-label">Ajustados con martes</div>
                <div className="stat-value blue">{trazabilidad.resumen.ajustados_martes}</div>
              </div>
            </div>
          )}

          <div className="table-container" style={{ maxHeight: '500px', overflowY: 'auto' }}>
            <table>
              <thead>
                <tr>
                  <th>#</th>
                  <th>Fecha Peso</th>
                  <th>Granja</th>
                  <th>Galpón</th>
                  <th>Núcleo</th>
                  <th className="text-right">Cantidad</th>
                  <th>Sexo</th>
                  <th className="text-right">Edad Proy.</th>
                  <th className="text-right">Peso Proy.</th>
                  <th className="text-right">Ganancia</th>
                  <th className="text-right">Días Proy.</th>
                  <th className="text-right">Edad Real</th>
                  <th className="text-right">Peso Real</th>
                  <th>F. Ingreso</th>
                  <th>Estado planificación</th>
                  <th>Martes</th>
                  <th>Detalle</th>
                </tr>
              </thead>
              <tbody>
                {(trazabilidad?.registros || oferta.ofertas.map((o, i) => ({
                  id: i + 1,
                  oferta_jueves: o,
                  estado_planificacion: 'pendiente',
                  tomado_en_planificacion: false,
                  detalle_planificacion: null,
                  ajuste_martes: { estado: 'sin_ajuste', disponible: false, oferta: null },
                }))).map((registro) => {
                  const o = registro.oferta_jueves
                  const planBadge = PLAN_BADGES[registro.estado_planificacion] || PLAN_BADGES.pendiente
                  const martesBadge = MARTES_BADGES[registro.ajuste_martes?.estado] || MARTES_BADGES.sin_ajuste
                  const rowStyle = registro.tomado_en_planificacion
                    ? { textDecoration: 'line-through', opacity: 0.62, background: 'rgba(22, 163, 74, 0.05)' }
                    : registro.estado_planificacion === 'fuera_rango'
                      ? { background: 'rgba(239, 68, 68, 0.04)' }
                      : registro.estado_planificacion === 'no_asignado'
                        ? { background: 'rgba(245, 158, 11, 0.05)' }
                        : undefined

                  return (
                    <tr key={registro.id} style={rowStyle}>
                      <td>{registro.id}</td>
                      <td>{o.fecha_peso}</td>
                      <td><strong>{o.granja}</strong></td>
                      <td className="text-center">{o.galpon}</td>
                      <td className="text-center">{o.nucleo}</td>
                      <td className="text-right">{formatNumber(o.cantidad)}</td>
                      <td className="text-center">{getSexoBadge(o.sexo)}</td>
                      <td className="text-right">{o.edad_proyectada}</td>
                      <td className="text-right">{o.peso_muestreo_proy?.toFixed(2)}</td>
                      <td className="text-right">{o.ganancia_diaria?.toFixed(3)}</td>
                      <td className="text-right">{o.dias_proyectados}</td>
                      <td className="text-right">{o.edad_real}</td>
                      <td className="text-right">{o.peso_muestreo_real?.toFixed(2)}</td>
                      <td>{o.fecha_ingreso}</td>
                      <td>
                        <span style={{
                          display: 'inline-block', padding: '2px 8px', borderRadius: 12,
                          fontSize: '0.76rem', fontWeight: 600, background: planBadge.bg, color: planBadge.color,
                        }}>
                          {planBadge.label}
                        </span>
                      </td>
                      <td>
                        <span style={{
                          display: 'inline-block', padding: '2px 8px', borderRadius: 12,
                          fontSize: '0.76rem', fontWeight: 600, background: martesBadge.bg, color: martesBadge.color,
                        }}>
                          {martesBadge.label}
                        </span>
                      </td>
                      <td style={{ fontSize: '0.8rem', minWidth: 210 }}>
                        {registro.estado_planificacion === 'planificado' && registro.detalle_planificacion && (
                          <div>
                            <strong>{registro.detalle_planificacion.dia}</strong>
                            <span style={{ color: 'var(--text-light)' }}> · {registro.detalle_planificacion.fecha}</span>
                          </div>
                        )}
                        {registro.estado_planificacion !== 'planificado' && registro.detalle_planificacion?.motivo && (
                          <div>{registro.detalle_planificacion.motivo}</div>
                        )}
                        {registro.estado_planificacion === 'no_asignado' && registro.detalle_planificacion?.dias_elegibles?.length > 0 && (
                          <div style={{ color: 'var(--text-light)', marginTop: 4 }}>
                            Días elegibles evaluados: {formatDiasElegibles(registro.detalle_planificacion.dias_elegibles)}
                          </div>
                        )}
                        {registro.estado_planificacion === 'fuera_rango' && registro.detalle_planificacion?.detalle_por_dia?.length > 0 && (
                          <div style={{ color: 'var(--text-light)', marginTop: 4 }}>
                            El lote se revisó contra todos los días de la semana y no alcanzó mínimos de edad/peso.
                          </div>
                        )}
                        {registro.ajuste_martes?.estado === 'actualizado' && registro.ajuste_martes?.oferta && (
                          <div style={{ color: 'var(--text-light)', marginTop: 4 }}>
                            Martes: {formatNumber(registro.ajuste_martes.oferta.cantidad)} aves, {registro.ajuste_martes.oferta.peso_muestreo_proy?.toFixed(2)} kg
                          </div>
                        )}
                        {registro.estado_planificacion === 'pendiente' && !registro.detalle_planificacion && (
                          <div style={{ color: 'var(--text-light)' }}>Aún no entra en la planificación actual.</div>
                        )}
                      </td>
                    </tr>
                  )
                })}
              </tbody>
            </table>
          </div>

          {trazabilidadLoading && (
            <p style={{ marginTop: '0.75rem', fontSize: '0.82rem', color: 'var(--text-light)' }}>
              Actualizando trazabilidad de oferta...
            </p>
          )}

          {trazabilidad?.ajuste_martes_cargado && trazabilidad.nuevos_martes?.length > 0 && (
            <div style={{ marginTop: '1rem', padding: '0.85rem 1rem', border: '1px solid rgba(59,130,246,0.2)', borderRadius: 8, background: 'rgba(59,130,246,0.05)' }}>
              <strong style={{ color: '#2563eb', fontSize: '0.9rem' }}>Lotes nuevos del martes</strong>
              <p style={{ fontSize: '0.82rem', color: 'var(--text-light)', marginTop: 6 }}>
                {trazabilidad.nuevos_martes.length} lote{trazabilidad.nuevos_martes.length !== 1 ? 's' : ''} no estaba{trazabilidad.nuevos_martes.length !== 1 ? 'n' : ''} en la oferta del jueves.
                Estos registros se consideran adicionales al comparar jueves vs martes.
              </p>
            </div>
          )}
        </div>
      </motion.div>
    </motion.div>
  )
}
