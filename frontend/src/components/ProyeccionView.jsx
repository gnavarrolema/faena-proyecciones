import React, { useState, useEffect } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import { BarChart, KanbanSquare, Table, ArrowLeftRight, X, Calendar, Settings2, PackageOpen, Download, RefreshCw, UploadCloud, CheckCircle2, AlertTriangle, PlusCircle, FileSpreadsheet, ChevronDown, ChevronRight, Ban, AlertOctagon, ShoppingCart, Loader2, Factory, ArrowRight, Undo2, Clock, Lightbulb, Check, Eye, EyeOff, Slash, GitBranch } from 'lucide-react'
import toast from 'react-hot-toast'
import { eliminarLote, moverLote, uploadAjusteMartes, configurarGallinas, quitarGallinas, generarProyeccion, agregarLote, getAnalisisTerceros, cargarDeficit, getParametros, diferirLote, restaurarLoteSemana1, getSemana2, clearLotesDiferidos, getSugerenciasDiferimiento, getOfertaTrazabilidad, moverLoteS2, eliminarLoteS2, enviarLoteS2aS1, excluirLote, getLotesDisponibles, incluirLoteDisponible } from '../services/api'
import { exportProyeccionPDF } from '../utils/pdfExport'
import { formatBBReferenceSummary, getBBReferenceConfigFromCoverage, getBBReferenceConfigFromParams, getBBReferencePresetMeta } from '../utils/bbReferencePresets'

const DIAS_SEMANA = ['Lunes', 'Martes', 'Miércoles', 'Jueves', 'Viernes', 'Sábado', 'Domingo']

function getDiaNombre(fechaStr) {
  if (!fechaStr) return '-'
  const dt = new Date(fechaStr + 'T12:00:00')
  const idx = dt.getDay() === 0 ? 6 : dt.getDay() - 1
  return DIAS_SEMANA[idx]
}

function formatNumber(n) {
  if (n == null) return '-'
  return n.toLocaleString('es-AR')
}

function formatDate(d) {
  if (!d) return '-'
  const dt = new Date(d + 'T12:00:00')
  return dt.toLocaleDateString('es-AR', { weekday: 'short', day: 'numeric', month: 'short' })
}

function formatDiasElegibles(dias) {
  if (!dias || dias.length === 0) return '-'
  return dias.map((dia) => {
    const fecha = new Date(dia + 'T12:00:00')
    const idx = (fecha.getDay() + 6) % 7
    return DIAS_SEMANA[idx] || dia
  }).join(', ')
}

function getEdadColor(dif) {
  if (Math.abs(dif) <= 1) return 'green'
  if (Math.abs(dif) <= 3) return 'orange'
  return 'red'
}

function getNivelCargaStyle(nivel) {
  if (nivel === 'horas_extras') return { background: 'rgba(239,68,68,0.12)', borderColor: '#ef4444' }
  if (nivel === 'alto') return { background: 'rgba(251,146,60,0.1)', borderColor: '#f97316' }
  return {}
}

function getNivelCargaLabel(dia) {
  if (dia.nivel_carga === 'horas_extras')
    return { text: 'HORAS EXTRAS', color: '#ef4444', icon: <AlertOctagon size={12} /> }
  if (dia.nivel_carga === 'alto')
    return { text: 'CARGA ALTA', color: '#f97316', icon: <AlertTriangle size={12} /> }
  return null
}

function getSexoBadge(sexo) {
  if (sexo === 'M') return <span className="badge badge-info">M</span>
  if (sexo === 'H') return <span className="badge badge-warning">H</span>
  return <span className="badge badge-success">-</span>
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

const containerVariants = {
  hidden: { opacity: 0 },
  show: {
    opacity: 1,
    transition: { staggerChildren: 0.08 }
  }
}

const itemVariants = {
  hidden: { opacity: 0, scale: 0.95, y: 15 },
  show: { opacity: 1, scale: 1, y: 0, transition: { duration: 0.3 } }
}

export default function ProyeccionView({ proyeccion, setProyeccion, planificacionAlternativa, onSwapPlanificacion }) {
  const [viewMode, setViewMode] = useState('cards') // 'cards' | 'table'
  const [movingLote, setMovingLote] = useState(null)
  const [loading, setLoading] = useState(false)
  const [ajusteFile, setAjusteFile] = useState(null)
  const [ajusteLoading, setAjusteLoading] = useState(false)
  const [ajusteResumen, setAjusteResumen] = useState(null)
  const [ajusteOpen, setAjusteOpen] = useState(false)
  const [expandedFR, setExpandedFR] = useState(new Set())
  const [gallinasInput, setGallinasInput] = useState({}) // {diaIdx: cantidad}
  const [redistribuyendo, setRedistribuyendo] = useState(null) // índice del día en redistribución
  const [showTercerosModal, setShowTercerosModal] = useState(false)
  const [tercerosLoading, setTercerosLoading] = useState(false)
  const [tercerosForm, setTercerosForm] = useState({
    dia_faena: 0, granja: '', galpon: 1, nucleo: 1, cantidad: '',
    sexo: 'M', edad_proyectada: '', peso_muestreo_proy: '',
    ganancia_diaria: 0.09, fecha_peso: '', fecha_ingreso: '', motivo_compra: ''
  })
  const [analisisTerceros, setAnalisisTerceros] = useState(null)
  const [parametros, setParametros] = useState({
    pollos_diarios_objetivo_max: 38000,
    capacidad_maxima_planta: 42000,
    capacidad_con_horas_extras: 45000,
    limite_sabado: 20000,
    produccion_dias_hasta_faena: 42,
    produccion_tolerancia_cruce_dias: 3,
    produccion_mortalidad_min: 0.045,
    produccion_mortalidad_max: 0.075,
    produccion_mortalidad_paso: 0.005,
  })
  const [semana2Data, setSemana2Data] = useState(null)
  const [semana2Loading, setSemana2Loading] = useState(false)
  const [semana2Open, setSemana2Open] = useState(false)
  const [diferirLoading, setDiferirLoading] = useState(null) // 'diaIdx-loteIdx'
  const [movingLoteS2, setMovingLoteS2] = useState(null)  // {diaIdx, loteIdx, lote}
  const [sendingToS1, setSendingToS1] = useState(null)     // {diaIdx, loteIdx, lote}
  const [s2ActionLoading, setS2ActionLoading] = useState(false)
  const [sugerencias, setSugerencias] = useState(null)
  const [sugerenciasOpen, setSugerenciasOpen] = useState(false)
  const [sugerenciasLoading, setSugerenciasLoading] = useState(false)
  const [sugerenciasIgnoradas, setSugerenciasIgnoradas] = useState(new Set())
  const [trazabilidad, setTrazabilidad] = useState(null)
  const [trazabilidadLoading, setTrazabilidadLoading] = useState(false)
  const [trazabilidadOpen, setTrazabilidadOpen] = useState(true)
  const [excluirMotivo, setExcluirMotivo] = useState('')
  const [excluirTarget, setExcluirTarget] = useState(null) // {diaIdx, loteIdx}
  const [disponiblesModal, setDisponiblesModal] = useState(false)
  const [disponibles, setDisponibles] = useState([])
  const [disponiblesLoading, setDisponiblesLoading] = useState(false)
  const [incluyendoLote, setIncluyendoLote] = useState(null)
  const [incluirDiaDestino, setIncluirDiaDestino] = useState(0)
  const ajusteInputRef = React.useRef(null)

  // Etiquetas de modo de planificación
  const MODOS_PLANIFICACION = {
    cascada_madurez: {
      label: 'Prioridad por Madurez',
      descripcion: 'Prioriza lotes por edad, permite fraccionamiento para alcanzar el objetivo diario.',
      color: '#2563eb',
      bg: 'rgba(37, 99, 235, 0.08)',
      shadow: 'rgba(37, 99, 235, 0.28)',
    },
    optimizacion_restricciones: {
      label: 'Distribución Equilibrada',
      descripcion: 'Asigna lotes enteros distribuyendo la carga de forma equilibrada entre los días.',
      color: '#7c3aed',
      bg: 'rgba(124, 58, 237, 0.08)',
      shadow: 'rgba(124, 58, 237, 0.28)',
    },
  }

  // Modo activo = el de la proyección actual
  const modoPrincipal = proyeccion?.modo_planificacion || 'cascada_madurez'
  const modoAlternativo = planificacionAlternativa?.modo_planificacion || (modoPrincipal === 'cascada_madurez' ? 'optimizacion_restricciones' : 'cascada_madurez')
  const infoModo = MODOS_PLANIFICACION[modoPrincipal] || MODOS_PLANIFICACION.cascada_madurez
  const alternativaDisponible = Boolean(planificacionAlternativa)
  const modosComparables = [modoPrincipal, modoAlternativo].filter((modo, indice, modos) => modo && modos.indexOf(modo) === indice)
  const diasTotalesPlan = proyeccion?.dias?.length || 0
  const diasConPlan = proyeccion?.dias?.filter((dia) => (dia.total_pollos || 0) > 0).length || 0
  const totalSinCapacidad = proyeccion?.total_pollos_no_asignados || 0
  const totalFueraRango = proyeccion?.total_pollos_fuera_rango || 0
  const bbReferenceConfig = getBBReferenceConfigFromParams(parametros)
    || getBBReferenceConfigFromCoverage(proyeccion?.factibilidad_produccion)
  const bbReferencePreset = getBBReferencePresetMeta(bbReferenceConfig)
  const bbReferenceResumen = formatBBReferenceSummary(bbReferenceConfig)
  const resumenPlanificacion = [
    'Primero se consideran los lotes habilitados por edad, peso y días elegibles para faena.',
    'Después se reparte la carga respetando capacidad diaria, feriados, sábado habilitado y eventos de gallinas.',
    totalSinCapacidad > 0 || totalFueraRango > 0
      ? 'Los lotes que no entran en la semana quedan señalados como sin capacidad o fuera de rango para que el ajuste sea visible.'
      : 'En esta corrida no quedaron lotes pendientes por capacidad ni por rango de faena.',
  ]

  // Cargar semana 2 cuando cambia la proyección
  const cargarSemana2 = async () => {
    setSemana2Loading(true)
    try {
      const data = await getSemana2()
      setSemana2Data(data)
    } catch {
      setSemana2Data(null)
    } finally {
      setSemana2Loading(false)
    }
  }

  useEffect(() => {
    if (proyeccion?.dias?.length) cargarSemana2()
  }, [proyeccion?.total_pollos_semana])

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

    if (proyeccion?.dias?.length) cargarTrazabilidad()

    return () => { active = false }
  }, [proyeccion?.total_pollos_semana, proyeccion?.total_pollos_no_asignados, proyeccion?.total_pollos_fuera_rango])

  const handleDiferir = async (diaIdx, loteIdx, motivo = '') => {
    setDiferirLoading(`${diaIdx}-${loteIdx}`)
    try {
      const data = await diferirLote(diaIdx, loteIdx, motivo)
      setProyeccion(data.proyeccion)
      toast.success(`Lote diferido a Semana 2 (${data.total_diferidos} diferidos)`)
    } catch (err) {
      toast.error('Error al diferir: ' + (err.response?.data?.detail || err.message))
    } finally {
      setDiferirLoading(null)
    }
  }

  const handleRestaurar = async (diferidoIndex, diaDestino = null) => {
    try {
      const data = await restaurarLoteSemana1(diferidoIndex, diaDestino)
      setProyeccion(data.proyeccion)
      toast.success(`Lote restaurado a Semana 1 (${getDiaNombre(proyeccion.dias[data.dia_destino]?.fecha)})`)
    } catch (err) {
      toast.error('Error al restaurar: ' + (err.response?.data?.detail || err.message))
    }
  }

  const handleLimpiarDiferidos = async () => {
    if (!window.confirm('¿Limpiar todos los lotes diferidos a Semana 2?')) return
    try {
      await clearLotesDiferidos()
      setSemana2Data(null)
      toast.success('Lotes diferidos limpiados')
    } catch (err) {
      toast.error(err.response?.data?.detail || 'Error al limpiar diferidos')
    }
  }

  // ─── Semana 2: edición interactiva ─────────────────────────────────────────
  const handleMoveS2 = async (diaOrigen, loteIdx, diaDestino) => {
    setS2ActionLoading(true)
    try {
      const data = await moverLoteS2({
        lote_index: loteIdx,
        dia_origen: diaOrigen,
        dia_destino: diaDestino,
      })
      setSemana2Data(prev => ({ ...prev, proyeccion: data.proyeccion }))
      setMovingLoteS2(null)
      toast.success('Lote movido en Semana 2')
    } catch (err) {
      toast.error('Error al mover en S2: ' + (err.response?.data?.detail || err.message))
    } finally {
      setS2ActionLoading(false)
    }
  }

  const handleDeleteS2 = async (diaIdx, loteIdx) => {
    if (!window.confirm('¿Eliminar este lote de la planificación de Semana 2?')) return
    setS2ActionLoading(true)
    try {
      const data = await eliminarLoteS2(diaIdx, loteIdx)
      setSemana2Data(prev => ({ ...prev, proyeccion: data }))
      toast.success('Lote eliminado de Semana 2')
    } catch (err) {
      toast.error('Error al eliminar de S2: ' + (err.response?.data?.detail || err.message))
    } finally {
      setS2ActionLoading(false)
    }
  }

  const handleEnviarAS1 = async (diaIdxS2, loteIdxS2, diaDestinoS1 = null) => {
    setS2ActionLoading(true)
    try {
      const data = await enviarLoteS2aS1(diaIdxS2, loteIdxS2, diaDestinoS1)
      setProyeccion(data.proyeccion_s1)
      setSemana2Data(prev => ({ ...prev, proyeccion: data.proyeccion_s2, total_diferidos: data.total_diferidos }))
      setSendingToS1(null)
      toast.success(`Lote enviado a Semana 1 (${getDiaNombre(data.proyeccion_s1.dias[data.dia_destino_s1]?.fecha)})`)
    } catch (err) {
      toast.error('Error al enviar a S1: ' + (err.response?.data?.detail || err.message))
    } finally {
      setS2ActionLoading(false)
    }
  }

  // ─── Sugerencias de diferimiento ───────────────────────────────────────────
  const cargarSugerencias = async () => {
    setSugerenciasLoading(true)
    try {
      const data = await getSugerenciasDiferimiento()
      setSugerencias(data)
      setSugerenciasIgnoradas(new Set())
    } catch {
      setSugerencias(null)
    } finally {
      setSugerenciasLoading(false)
    }
  }

  useEffect(() => {
    if (proyeccion?.dias?.length) cargarSugerencias()
  }, [proyeccion?.total_pollos_semana])

  const handleAceptarSugerencia = async (sug) => {
    setDiferirLoading(`${sug.dia_index}-${sug.lote_index}`)
    try {
      const data = await diferirLote(sug.dia_index, sug.lote_index, `Sugerencia: ${sug.criterio}`)
      setProyeccion(data.proyeccion)
      toast.success(`Lote ${sug.granja} G${sug.galpon} diferido a S2`)
    } catch (err) {
      toast.error('Error al diferir: ' + (err.response?.data?.detail || err.message))
    } finally {
      setDiferirLoading(null)
    }
  }

  const handleAceptarTodas = async () => {
    if (!sugerencias?.sugerencias?.length) return
    const activas = sugerencias.sugerencias.filter((_, i) => !sugerenciasIgnoradas.has(i))
    if (!activas.length) return
    if (!window.confirm(`¿Diferir ${activas.length} lote${activas.length > 1 ? 's' : ''} sugeridos a Semana 2?`)) return

    // Diferir de atrás para adelante para no invalidar índices
    const ordenadas = [...activas].sort((a, b) => {
      if (b.dia_index !== a.dia_index) return b.dia_index - a.dia_index
      return b.lote_index - a.lote_index
    })

    let ultima = null
    for (const sug of ordenadas) {
      try {
        ultima = await diferirLote(sug.dia_index, sug.lote_index, `Sugerencia: ${sug.criterio}`)
      } catch {
        // Si falla uno (por índices ya cambiados), seguir con el resto
      }
    }
    if (ultima) {
      setProyeccion(ultima.proyeccion)
      toast.success(`${ordenadas.length} lotes diferidos a S2`)
    }
  }

  const handleIgnorarSugerencia = (idx) => {
    setSugerenciasIgnoradas(prev => {
      const next = new Set(prev)
      next.add(idx)
      return next
    })
  }

  // Cargar parámetros y análisis de déficit al montar o cuando cambia la proyección
  useEffect(() => {
    getParametros().then(p => setParametros(prev => ({ ...prev, ...p }))).catch(() => {})
  }, [])

  useEffect(() => {
    const cargarAnalisis = async () => {
      try {
        const data = await getAnalisisTerceros()
        setAnalisisTerceros(data)
      } catch {
        setAnalisisTerceros(null)
      }
    }
    if (proyeccion?.dias?.length) cargarAnalisis()
  }, [proyeccion?.total_pollos_semana])

  const resetTercerosForm = () => setTercerosForm({
    dia_faena: 0, granja: '', galpon: 1, nucleo: 1, cantidad: '',
    sexo: 'M', edad_proyectada: '', peso_muestreo_proy: '',
    ganancia_diaria: 0.09, fecha_peso: '', fecha_ingreso: '', motivo_compra: ''
  })

  const handleRegenerarConSabado = async () => {
    try {
      const gallinasMap = {}
      proyeccion.eventos_gallinas?.forEach(e => {
        if (!gallinasMap[e.fecha]) gallinasMap[e.fecha] = { livianas: 0, pesadas: 0 }
        if (e.tipo === 'pesada') gallinasMap[e.fecha].pesadas += e.cantidad
        else gallinasMap[e.fecha].livianas += e.cantidad
      })
      const data = await generarProyeccion({
        fecha_inicio_semana: proyeccion.fecha_inicio,
        dias_faena: 6,
        pollos_por_dia: proyeccion.dias.length > 0
          ? Math.round(proyeccion.total_pollos_semana / proyeccion.dias.length)
          : 35000,
        habilitar_sabado: true,
        gallinas: Object.keys(gallinasMap).length > 0 ? gallinasMap : null,
      })
      setProyeccion(data)
      toast.success('Planificación regenerada con sábado habilitado')
    } catch (err) {
      toast.error('Error: ' + (err.response?.data?.detail || err.message))
    }
  }

  const handleRedistribuir = async (diaIdx) => {
    if (!window.confirm('¿Redistribuir todos los lotes de este día a los días restantes?')) return
    setRedistribuyendo(diaIdx)
    try {
      const data = await redistribuirDia(diaIdx)
      setProyeccion(data)
      toast.success('Lotes redistribuidos sobre los días restantes respetando elegibilidad y capacidad diaria')
    } catch (err) {
      toast.error('Error al redistribuir: ' + (err.response?.data?.detail || err.message))
    } finally {
      setRedistribuyendo(null)
    }
  }

  if (!proyeccion || !proyeccion.dias) {
    return (
      <motion.div
        initial={{ opacity: 0, scale: 0.95 }}
        animate={{ opacity: 1, scale: 1 }}
        className="card"
      >
        <div className="card-body" style={{ textAlign: 'center', padding: '3rem' }}>
          <p style={{ fontSize: '1.1rem', color: 'var(--text-light)', display: 'flex', alignItems: 'center', justifyContent: 'center', gap: 6 }}>
            <BarChart size={20} /> No hay planificación generada. Genérela desde la pestaña "Oferta".
          </p>
        </div>
      </motion.div>
    )
  }

  const handleDelete = async (diaIdx, loteIdx) => {
    if (!window.confirm('¿Eliminar este lote de la planificación?')) return
    setLoading(true)
    try {
      const data = await eliminarLote(diaIdx, loteIdx)
      setProyeccion(data)
    } catch (err) {
      toast.error('Error al eliminar: ' + (err.response?.data?.detail || err.message))
    } finally {
      setLoading(false)
    }
  }

  const handleExcluir = async (diaIdx, loteIdx, motivo = '') => {
    setLoading(true)
    try {
      const data = await excluirLote(diaIdx, loteIdx, motivo)
      setProyeccion(data)
      setExcluirTarget(null)
      setExcluirMotivo('')
      toast.success('Lote actualizado')
    } catch (err) {
      toast.error('Error: ' + (err.response?.data?.detail || err.message))
    } finally {
      setLoading(false)
    }
  }

  const handleCargarDisponibles = async () => {
    setDisponiblesLoading(true)
    try {
      const data = await getLotesDisponibles()
      setDisponibles(data.disponibles || [])
      setDisponiblesModal(true)
    } catch (err) {
      toast.error('Error: ' + (err.response?.data?.detail || err.message))
    } finally {
      setDisponiblesLoading(false)
    }
  }

  const handleIncluirLote = async (loteDisp) => {
    setIncluyendoLote(loteDisp)
    setLoading(true)
    try {
      const data = await incluirLoteDisponible({
        origen: loteDisp.origen,
        dia_index: loteDisp.dia_index,
        lote_index: loteDisp.lote_index,
        pool_index: loteDisp.pool_index,
        dia_destino: incluirDiaDestino,
      })
      setProyeccion(data)
      // Refrescar lista de disponibles
      const disp = await getLotesDisponibles()
      setDisponibles(disp.disponibles || [])
      toast.success('Lote incorporado a la planificación')
    } catch (err) {
      toast.error('Error: ' + (err.response?.data?.detail || err.message))
    } finally {
      setLoading(false)
      setIncluyendoLote(null)
    }
  }

  const handleMove = async (diaOrigen, loteIdx, diaDestino) => {
    setLoading(true)
    try {
      const data = await moverLote({
        lote_index: loteIdx,
        dia_origen: diaOrigen,
        dia_destino: diaDestino,
      })
      setProyeccion(data)
      setMovingLote(null)
    } catch (err) {
      toast.error('Error al mover: ' + (err.response?.data?.detail || err.message))
    } finally {
      setLoading(false)
    }
  }

  const handleAjusteMartes = async () => {
    if (!ajusteFile) return
    setAjusteLoading(true)
    try {
      const data = await uploadAjusteMartes(ajusteFile)
      setProyeccion(data.proyeccion)
      setAjusteResumen(data.resumen_ajuste)
      setAjusteFile(null)
      toast.success('Planificación ajustada con oferta del martes')
      // Alertar si hubo filas descartadas en la oferta del martes
      if (data.filas_descartadas?.length > 0) {
        const granjas = [...new Set(data.filas_descartadas.map(f => f.granja))].join(', ')
        const aves = data.pollos_descartados || data.filas_descartadas.reduce((s, f) => s + (f.cantidad || 0), 0)
        toast(
          `Oferta martes: ${data.total_descartadas} lote${data.total_descartadas !== 1 ? 's' : ''} descartados (${granjas}, ${aves.toLocaleString('es-AR')} aves). Sin fecha de peso → no se proyectan.`,
          { icon: '⚠️', duration: 12000, style: { background: '#fffbeb', border: '1px solid #f59e0b', color: '#92400e', fontSize: '0.85rem' } }
        )
      }
      if (data.resumen_filas) {
        const rf = data.resumen_filas
        if (rf.filas_vacias > 0) {
          toast(
            `Oferta martes: ${rf.filas_vacias} fila${rf.filas_vacias !== 1 ? 's' : ''} tenían granja vacía y fueron ignoradas.`,
            { icon: '⚠️', duration: 10000, style: { background: '#fef2f2', border: '1px solid #fca5a5', color: '#991b1b', fontSize: '0.85rem' } }
          )
        }
      }
    } catch (err) {
      toast.error('Error al ajustar: ' + (err.response?.data?.detail || err.message))
    } finally {
      setAjusteLoading(false)
    }
  }

  const handleAjusteFile = (f) => {
    if (f && (f.name.endsWith('.xlsx') || f.name.endsWith('.xls'))) {
      setAjusteFile(f)
    } else {
      toast.error('Solo se aceptan archivos .xlsx o .xls')
    }
  }

  const handleAgregarTerceros = async () => {
    const { granja, cantidad, edad_proyectada, peso_muestreo_proy, fecha_peso, fecha_ingreso } = tercerosForm
    if (!granja || !cantidad || !edad_proyectada || !peso_muestreo_proy || !fecha_peso || !fecha_ingreso) {
      toast.error('Completar todos los campos obligatorios')
      return
    }
    setTercerosLoading(true)
    try {
      const payload = {
        granja: tercerosForm.granja,
        galpon: Number(tercerosForm.galpon),
        nucleo: Number(tercerosForm.nucleo),
        cantidad: Number(tercerosForm.cantidad),
        sexo: tercerosForm.sexo,
        edad_proyectada: Number(tercerosForm.edad_proyectada),
        peso_muestreo_proy: Number(tercerosForm.peso_muestreo_proy),
        ganancia_diaria: Number(tercerosForm.ganancia_diaria),
        fecha_peso: tercerosForm.fecha_peso,
        fecha_ingreso: tercerosForm.fecha_ingreso,
        dia_faena: Number(tercerosForm.dia_faena),
        es_compra_terceros: true,
        motivo_compra: tercerosForm.motivo_compra || 'Compra a terceros',
      }
      const data = await agregarLote(payload)
      setProyeccion(data)
      toast.success(`Lote de terceros agregado a ${getDiaNombre(proyeccion.dias[payload.dia_faena]?.fecha)}`)
      setShowTercerosModal(false)
      resetTercerosForm()
    } catch (err) {
      toast.error('Error: ' + (err.response?.data?.detail || err.message))
    } finally {
      setTercerosLoading(false)
    }
  }

  const { dias } = proyeccion
  const lotesNoAsignados = proyeccion.lotes_no_asignados || []
  const lotesFueraRango = proyeccion.lotes_fuera_rango || []

  const toggleFR = (idx) => {
    setExpandedFR(prev => {
      const next = new Set(prev)
      if (next.has(idx)) next.delete(idx)
      else next.add(idx)
      return next
    })
  }

  return (
    <motion.div
      variants={containerVariants}
      initial="hidden"
      animate="show"
    >
      {/* Selector de modo de planificación */}
      {modosComparables.length > 0 && (
        <motion.div variants={itemVariants} className="planificacion-switcher">
          <div className="planificacion-switcher__header">
            <div className="planificacion-switcher__eyebrow">
              <GitBranch size={18} />
              <span>Modo de planificación</span>
            </div>
            <p className="planificacion-switcher__helper">
              {alternativaDisponible
                ? 'El análisis actual queda marcado como activo. Si quieres comparar la distribución, selecciona la otra opción.'
                : 'Esta proyección no tiene una alternativa guardada todavía. El modo activo sigue visible para que sepas con qué análisis estás trabajando.'}
            </p>
          </div>

          <div className="planificacion-switcher__options">
            {modosComparables.map((modo) => {
              const config = MODOS_PLANIFICACION[modo]
              const isActive = modo === modoPrincipal
              const isDisabled = !isActive && !alternativaDisponible

              return (
                <button
                  key={modo}
                  type="button"
                  className={`planificacion-option ${isActive ? 'is-active' : ''} ${isDisabled ? 'is-disabled' : ''}`}
                  onClick={isActive || isDisabled ? undefined : onSwapPlanificacion}
                  aria-pressed={isActive}
                  aria-disabled={isDisabled}
                  disabled={isDisabled}
                  title={isActive
                    ? 'Modo actualmente seleccionado para el análisis'
                    : isDisabled
                      ? 'La alternativa no está disponible en esta proyección guardada'
                      : 'Cambiar a este modo de planificación'}
                  style={{
                    '--plan-color': config.color,
                    '--plan-bg': config.bg,
                    '--plan-shadow': config.shadow,
                  }}
                >
                  <div className="planificacion-option__top">
                    <div className="planificacion-option__title-group">
                      <span className="planificacion-option__status">
                        {isActive ? <CheckCircle2 size={14} /> : <ArrowLeftRight size={14} />}
                        {isActive ? 'Activo para el análisis' : isDisabled ? 'Alternativa no disponible' : 'Alternativa disponible'}
                      </span>
                      <strong className="planificacion-option__title">{config.label}</strong>
                    </div>
                    <span className="planificacion-option__action">
                      {isActive ? 'Seleccionado' : isDisabled ? 'No disponible' : 'Usar este modo'}
                    </span>
                  </div>
                  <p className="planificacion-option__description">{config.descripcion}</p>
                </button>
              )
            })}
          </div>

          <div className="planificacion-switcher__footer">
            <span className="planificacion-switcher__summary">
              Estás analizando con <strong>{infoModo.label}</strong>
            </span>
            <span className="planificacion-switcher__compare">
              {alternativaDisponible
                ? 'Toca la tarjeta alternativa para recalcular y comparar el resultado.'
                : 'Vuelve a generar la planificación para guardar también la alternativa comparable.'}
            </span>
          </div>
        </motion.div>
      )}

      <motion.div
        variants={itemVariants}
        className="planificacion-details"
        style={{
          '--details-color': infoModo.color,
          '--details-bg': infoModo.bg,
          '--details-border': `${infoModo.color}33`,
          '--details-color-alpha': `${infoModo.color}44`,
        }}
      >
        <div className="planificacion-details__header">
          <div className="planificacion-details__title-area">
            <div className="planificacion-details__title">
              <Lightbulb size={20} />
              Cómo se armó esta planificación
            </div>
            <div className="planificacion-details__desc">
              <strong style={{ color: infoModo.color }}>{infoModo.label}:</strong> {infoModo.descripcion}
            </div>
          </div>
          {planificacionAlternativa && (
            <div className="planificacion-details__suggestion">
              También puedes probar <strong>{MODOS_PLANIFICACION[modoAlternativo]?.label}</strong> para comparar otra distribución.
            </div>
          )}
        </div>

        <div className="planificacion-details__config">
          <div style={{ display: 'flex', alignItems: 'center', gap: 10, flexWrap: 'wrap' }}>
            <span className={`badge ${bbReferencePreset.isCustom ? 'badge-warning' : 'badge-info'}`}>
              Referencia BB activa: {bbReferencePreset.label}
            </span>
            <span style={{ fontSize: '0.86rem', color: 'var(--text)', fontWeight: 500 }}>{bbReferenceResumen}</span>
          </div>
          <span style={{ fontSize: '0.8rem', color: 'var(--text-light)' }}>{bbReferencePreset.description}</span>
        </div>

        <div className="planificacion-details__steps">
          {resumenPlanificacion.map((texto, idx) => (
            <div key={idx} className="planificacion-details__step">
              <Check size={18} />
              <span>{texto}</span>
            </div>
          ))}
        </div>

        <div className="planificacion-details__tags">
          <span className="badge badge-info" style={{ padding: '0.35rem 0.75rem', fontSize: '0.8rem' }}>Planificados: {formatNumber(proyeccion.total_pollos_semana)}</span>
          <span className="badge badge-success" style={{ padding: '0.35rem 0.75rem', fontSize: '0.8rem' }}>Días usados: {diasConPlan}/{diasTotalesPlan}</span>
          <span className="badge badge-warning" style={{ padding: '0.35rem 0.75rem', fontSize: '0.8rem' }}>Sin capacidad: {formatNumber(totalSinCapacidad)}</span>
          <span className="badge badge-danger" style={{ padding: '0.35rem 0.75rem', fontSize: '0.8rem' }}>Fuera de rango: {formatNumber(totalFueraRango)}</span>
        </div>
      </motion.div>

      {/* Header Dashboard section */}
      <div style={{ display: 'flex', flexDirection: 'column', gap: '1.25rem', marginBottom: '1.5rem' }}>
        {/* Stats generales */}
        <motion.div variants={itemVariants} className="stats-grid" style={{ marginBottom: 0 }}>
          <div className="stat-card" style={{ padding: '1.25rem' }}>
            <div className="stat-label" style={{ color: 'var(--success)' }}><BarChart size={16} /> Total Pollos Semana</div>
            <div className="stat-value green" style={{ fontSize: '1.8rem' }}>{formatNumber(proyeccion.total_pollos_semana)}</div>
          </div>
          <div className="stat-card" style={{ padding: '1.25rem' }}>
            <div className="stat-label" style={{ color: 'var(--info)' }}><Clock size={16} /> Promedio Edad Semana</div>
            <div className="stat-value blue" style={{ fontSize: '1.8rem', display: 'flex', alignItems: 'baseline', gap: '0.4rem' }}>
              {proyeccion.promedio_edad_semana?.toFixed(1)} 
              <span style={{ fontSize: '1rem', color: 'var(--text-light)', fontWeight: 500 }}>días</span>
            </div>
          </div>
          <div className="stat-card" style={{ padding: '1.25rem' }}>
            <div className="stat-label" style={{ color: 'var(--warning)' }}><PackageOpen size={16} /> Cajas Semanales</div>
            <div className="stat-value orange" style={{ fontSize: '1.8rem' }}>{formatNumber(proyeccion.produccion_cajas_semanales)}</div>
          </div>
          <div className="stat-card" style={{ padding: '1.25rem' }}>
            <div className="stat-label" style={{ color: 'var(--primary)' }}><Factory size={16} /> Sofía</div>
            <div className="stat-value" style={{ fontSize: '1.8rem' }}>{formatNumber(proyeccion.sofia)}</div>
          </div>
        </motion.div>

        {/* Dashboard Alerts Grid (Factibilidad, Feriados, Gallinas, Compra Terceros) */}
        <motion.div variants={itemVariants} style={{
          display: 'grid',
          gridTemplateColumns: 'repeat(auto-fit, minmax(350px, 1fr))',
          gap: '1rem'
        }}>
          {proyeccion.factibilidad_produccion && proyeccion.factibilidad_produccion.encontrada && (() => {
            const fact = proyeccion.factibilidad_produccion
            const hayDeficit = fact.deficit_peor != null && fact.deficit_peor > 0
            const borderColor = hayDeficit ? '#f97316' : '#22c55e'
            const bgColor = hayDeficit ? 'rgba(249, 115, 22, 0.08)' : 'rgba(34, 197, 94, 0.08)'
            const iconColor = hayDeficit ? '#ea580c' : '#16a34a'
            const sujeto = fact.contexto === 'plan_propio' ? 'plan propio' : 'oferta'
            const notaCohortes = fact.total_semanas_referenciadas > 1
              ? `Cruce consolidado sobre ${fact.total_semanas_referenciadas} semanas de carga BB.`
              : null
            const notaTerceros = fact.total_compra_terceros > 0
              ? `Compra a terceros fuera de este cruce: ${formatNumber(fact.total_compra_terceros)} pollos.`
              : null
            const notaVentana = `Referencia BB: carga + ${fact.dias_hasta_faena_referencia} días (±${fact.tolerancia_cruce_dias}).`
            const semanasReferenciadas = fact.semanas_referenciadas || []

            return (
              <div style={{
                padding: '1rem 1.25rem',
                background: bgColor,
                border: `1px solid ${borderColor}40`,
                borderLeft: `4px solid ${borderColor}`,
                borderRadius: 10,
                display: 'flex',
                alignItems: 'flex-start',
                gap: 12,
                height: '100%',
              }}>
                <Factory size={22} color={iconColor} style={{ marginTop: 2, flexShrink: 0 }} />
                <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
                  {hayDeficit ? (
                    <>
                      <div style={{ fontWeight: 600, color: '#ea580c', fontSize: '0.95rem' }}>Déficit de Producción Detectado</div>
                      <span style={{ fontSize: '0.85rem', color: 'var(--text)', lineHeight: 1.5 }}>
                        El {sujeto} ({formatNumber(fact.total_oferta)}) excede la producción disponible ({formatNumber(fact.disponibles_peor)} en el escenario conservador) en <strong style={{ color: '#ef4444' }}>{formatNumber(fact.deficit_peor)} pollos</strong>. Cobertura: <strong>{fact.cobertura_pct_peor}%</strong>.
                      </span>
                      {(notaCohortes || notaTerceros || notaVentana) && (
                        <span style={{ fontSize: '0.78rem', color: 'var(--text-light)', lineHeight: 1.4 }}>
                          {[notaCohortes, notaTerceros, notaVentana].filter(Boolean).join(' ')}
                        </span>
                      )}
                      {semanasReferenciadas.length > 0 && (
                        <div style={{ display: 'flex', flexWrap: 'wrap', gap: 6, marginTop: 2 }}>
                          {semanasReferenciadas.map((sem) => (
                            <span key={sem.fecha_desde} style={{
                              fontSize: '0.74rem',
                              color: 'var(--text)',
                              background: 'rgba(255,255,255,0.7)',
                              border: '1px solid var(--border)',
                              borderRadius: 999,
                              padding: '0.2rem 0.55rem',
                            }}>
                              BB {formatDate(sem.fecha_desde)} - {formatDate(sem.fecha_hasta)} · {formatNumber(sem.pollitos_cargados)}
                            </span>
                          ))}
                        </div>
                      )}
                      <button 
                        className="btn btn-sm"
                        style={{
                          background: '#7c3aed', color: '#fff', border: 'none', 
                          alignSelf: 'flex-start', marginTop: 4, padding: '0.35rem 0.8rem',
                          display: 'flex', alignItems: 'center', gap: 6
                        }}
                        onClick={() => setShowTercerosModal(true)}
                      >
                        <ShoppingCart size={14} /> Agregar compra a terceros
                      </button>
                    </>
                  ) : (
                    <>
                      <div style={{ fontWeight: 600, color: '#16a34a', fontSize: '0.95rem' }}>Producción OK</div>
                      <span style={{ fontSize: '0.85rem', color: 'var(--text)', lineHeight: 1.5 }}>
                        La producción propia ({formatNumber(fact.disponibles_peor)} en el escenario conservador) cubre el {sujeto} ({formatNumber(fact.total_oferta)}). Cobertura: <strong>{fact.cobertura_pct_peor}%</strong>.
                      </span>
                      {(notaCohortes || notaTerceros || notaVentana) && (
                        <span style={{ fontSize: '0.78rem', color: 'var(--text-light)', lineHeight: 1.4 }}>
                          {[notaCohortes, notaTerceros, notaVentana].filter(Boolean).join(' ')}
                        </span>
                      )}
                      {semanasReferenciadas.length > 0 && (
                        <div style={{ display: 'flex', flexWrap: 'wrap', gap: 6, marginTop: 2 }}>
                          {semanasReferenciadas.map((sem) => (
                            <span key={sem.fecha_desde} style={{
                              fontSize: '0.74rem',
                              color: 'var(--text)',
                              background: 'rgba(255,255,255,0.7)',
                              border: '1px solid var(--border)',
                              borderRadius: 999,
                              padding: '0.2rem 0.55rem',
                            }}>
                              BB {formatDate(sem.fecha_desde)} - {formatDate(sem.fecha_hasta)} · {formatNumber(sem.pollitos_cargados)}
                            </span>
                          ))}
                        </div>
                      )}
                      {/* Botón opcional de compras a terceros, aunque todo este OK */}
                      <button 
                        className="btn btn-sm btn-outline"
                        style={{
                          alignSelf: 'flex-start', marginTop: 4, padding: '0.2rem 0.6rem',
                          fontSize: '0.75rem', display: 'flex', alignItems: 'center', gap: 4
                        }}
                        onClick={() => setShowTercerosModal(true)}
                      >
                        <ShoppingCart size={12} /> Compra manual
                      </button>
                    </>
                  )}
                </div>
              </div>
            )
          })()}

          {/* Feriados o Gallinas */}
          <div style={{ display: 'flex', flexDirection: 'column', gap: '1rem', height: '100%' }}>
            {proyeccion.feriados_aplicados && proyeccion.feriados_aplicados.length > 0 && (
              <div style={{
                padding: '1rem 1.25rem',
                background: 'rgba(251, 146, 60, 0.08)',
                border: '1px solid rgba(251, 146, 60, 0.3)',
                borderLeft: '4px solid #f97316',
                borderRadius: 10,
                display: 'flex',
                flexDirection: 'column',
                gap: 8,
              }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                  <Calendar size={18} color="#ea580c" />
                  <strong style={{ color: '#ea580c', fontSize: '0.95rem' }}>
                    {proyeccion.feriados_aplicados.length} feriado{proyeccion.feriados_aplicados.length > 1 ? 's' : ''} esta semana
                  </strong>
                </div>
                {proyeccion.feriados_aplicados.map(f => (
                  <div key={f.fecha} style={{ fontSize: '0.85rem', display: 'flex', alignItems: 'center', gap: 6, flexWrap: 'wrap' }}>
                    <span style={{ fontWeight: 600, color: '#9a3412' }}>{getDiaNombre(f.fecha)} {f.nombre}</span>
                    <span style={{ color: 'var(--text-light)' }}>— redistribuyendo sobre los días restantes</span>
                  </div>
                ))}
                <div style={{ display: 'flex', gap: '0.5rem', marginTop: 4 }}>
                  {!dias.some(d => d.es_sabado) && (
                    <button className="btn btn-sm btn-outline" style={{ fontSize: '0.75rem', borderColor: '#ea580c', color: '#ea580c' }} onClick={async () => {
                      try {
                        setLoading(true)
                        const data = await generarProyeccion({
                          fecha_inicio_semana: proyeccion.fecha_inicio, dias_faena: 6,
                          pollos_por_dia: Math.round(proyeccion.total_pollos_semana / dias.length),
                          habilitar_sabado: true,
                          gallinas: proyeccion.eventos_gallinas?.length > 0 ? Object.fromEntries(proyeccion.eventos_gallinas.map(e => [e.fecha, { livianas: e.gallinas_livianas_cantidad || 0, pesadas: e.gallinas_pesadas_cantidad || 0 }])) : null,
                        })
                        setProyeccion(data)
                        toast.success('Planificación regenerada con sábado habilitado')
                      } catch (err) { toast.error(err.response?.data?.detail || 'Error al regenerar') } finally { setLoading(false) }
                    }}>
                      Habilitar sábado
                    </button>
                  )}
                  <button className="btn btn-sm btn-outline" style={{ fontSize: '0.75rem', borderColor: '#ea580c', color: '#ea580c' }} onClick={async () => {
                    if (lotesNoAsignados.length > 0) {
                      try { const result = await cargarDeficit(); toast.success(result.mensaje || 'Déficit trasladado a semana siguiente'); } catch (err) { toast.error(err.response?.data?.detail || 'Error al trasladar déficit') }
                    } else { toast('No hay lotes no asignados para diferir', { icon: 'ℹ️' }) }
                  }}>
                    Diferir a semana siguiente
                  </button>
                </div>
              </div>
            )}

            {proyeccion.eventos_gallinas && proyeccion.eventos_gallinas.length > 0 && (
              <div style={{
                padding: '0.85rem 1.25rem', background: 'rgba(139, 92, 246, 0.08)',
                border: '1px solid rgba(139, 92, 246, 0.25)', borderLeft: '4px solid #8b5cf6',
                borderRadius: 10, display: 'flex', flexDirection: 'column', gap: 6,
              }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                  <AlertTriangle size={18} color="#7c3aed" />
                  <strong style={{ color: '#7c3aed', fontSize: '0.9rem' }}>Evento de Gallinas Programado</strong>
                </div>
                <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap' }}>
                  {proyeccion.eventos_gallinas.map((e, i) => (
                    <span key={i} style={{ padding: '0.15rem 0.5rem', background: 'rgba(139, 92, 246, 0.1)', borderRadius: 4, fontSize: '0.8rem', color: e.tipo === 'pesada' ? '#be185d' : '#7c3aed', fontWeight: 500 }}>
                      {getDiaNombre(e.fecha)}: {formatNumber(e.cantidad)} {e.tipo}s
                    </span>
                  ))}
                </div>
              </div>
            )}
          </div>
        </motion.div>
      </div>

      <motion.div variants={itemVariants} className="card" style={{ borderLeft: '4px solid var(--primary)' }}>
        <div
          className="card-header"
          style={{ cursor: 'pointer', userSelect: 'none' }}
          onClick={() => setTrazabilidadOpen(!trazabilidadOpen)}
        >
          <h2><Table size={18} style={{ verticalAlign: 'middle', marginRight: 6 }} /> Trazabilidad de Oferta del Jueves</h2>
          <span style={{ fontSize: '0.85rem', color: 'var(--text-light)', display: 'flex', alignItems: 'center', gap: 6 }}>
            {trazabilidadOpen ? <><EyeOff size={14} /> Ocultar</> : <><Eye size={14} /> Mostrar</>}
          </span>
        </div>
        <AnimatePresence>
          {trazabilidadOpen && (
            <motion.div
              initial={{ height: 0, opacity: 0 }}
              animate={{ height: 'auto', opacity: 1 }}
              exit={{ height: 0, opacity: 0 }}
              style={{ overflow: 'hidden' }}
            >
              <div className="card-body">
                <p style={{ marginBottom: '1rem', fontSize: '0.9rem', color: 'var(--text-light)' }}>
                  Aquí puede consultar la oferta base del jueves desde la misma pantalla de planificación. Los registros <strong>tachados</strong> ya fueron tomados en cuenta por la planificación actual.
                </p>

                <div style={{ marginBottom: '1rem', padding: '0.85rem 1rem', borderRadius: 8, background: '#f8fafc', border: '1px solid var(--border)', fontSize: '0.84rem', color: 'var(--text-light)', lineHeight: 1.55 }}>
                  <strong style={{ color: 'var(--text)' }}>Cómo leer esta vista:</strong> “Tomado en planificación” indica que el lote quedó asignado a un día. “Sin capacidad” indica que el lote <strong>sí fue evaluado</strong> en sus días elegibles, pero no cupo sin superar el tope diario. “Fuera de rango” indica que, recalculando edad y peso para cada día de la semana, el lote no alcanzó los mínimos para entrar a faena.
                </div>

                {trazabilidad && (
                  <div className="stats-grid" style={{ marginBottom: '1rem' }}>
                    <div className="stat-card">
                      <div className="stat-label">Tomados en planificación</div>
                      <div className="stat-value green">{formatNumber(trazabilidad.resumen.planificados)}</div>
                    </div>
                    <div className="stat-card">
                      <div className="stat-label">Sin capacidad</div>
                      <div className="stat-value orange">{formatNumber(trazabilidad.resumen.no_asignados)}</div>
                    </div>
                    <div className="stat-card">
                      <div className="stat-label">Fuera de rango</div>
                      <div className="stat-value" style={{ color: '#dc2626' }}>{formatNumber(trazabilidad.resumen.fuera_rango)}</div>
                    </div>
                    <div className="stat-card">
                      <div className="stat-label">Ajustados con martes</div>
                      <div className="stat-value blue">{formatNumber(trazabilidad.resumen.ajustados_martes)}</div>
                    </div>
                  </div>
                )}

                <div className="table-container" style={{ maxHeight: '420px', overflowY: 'auto' }}>
                  <table>
                    <thead>
                      <tr>
                        <th>#</th>
                        <th>Granja</th>
                        <th className="text-center">Galpón</th>
                        <th className="text-center">Núcleo</th>
                        <th className="text-right">Cantidad</th>
                        <th className="text-center">Sexo</th>
                        <th className="text-right">Edad</th>
                        <th className="text-right">Peso</th>
                        <th>Estado planificación</th>
                        <th>Martes</th>
                        <th>Detalle</th>
                      </tr>
                    </thead>
                    <tbody>
                      {(trazabilidad?.registros || []).map((registro) => {
                        const lote = registro.oferta_jueves
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
                            <td><strong>{lote.granja}</strong></td>
                            <td className="text-center">{lote.galpon}</td>
                            <td className="text-center">{lote.nucleo}</td>
                            <td className="text-right">{formatNumber(lote.cantidad)}</td>
                            <td className="text-center">{getSexoBadge(lote.sexo)}</td>
                            <td className="text-right">{lote.edad_proyectada}</td>
                            <td className="text-right">{lote.peso_muestreo_proy?.toFixed(2)}</td>
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
                            <td style={{ fontSize: '0.8rem', minWidth: 220 }}>
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
              </div>
            </motion.div>
          )}
        </AnimatePresence>
      </motion.div>

      {/* Ajuste con Oferta del Martes */}
      <motion.div variants={itemVariants} className="card card-compact" style={{ borderLeft: '4px solid var(--info)' }}>
        <div
          className="card-header"
          style={{ cursor: 'pointer', userSelect: 'none' }}
          onClick={() => setAjusteOpen(!ajusteOpen)}
        >
          <h2><RefreshCw size={18} style={{ verticalAlign: 'middle', marginRight: 6 }} /> Ajustar con Oferta del Martes</h2>
          <span style={{ fontSize: '0.85rem', color: 'var(--text-light)' }}>
            {ajusteOpen ? '▲ Cerrar' : '▼ Abrir'}
          </span>
        </div>
        <AnimatePresence>
          {ajusteOpen && (
            <motion.div
              initial={{ height: 0, opacity: 0 }}
              animate={{ height: 'auto', opacity: 1 }}
              exit={{ height: 0, opacity: 0 }}
              style={{ overflow: 'hidden' }}
            >
              <div className="card-body">
                <p style={{ marginBottom: '1rem', fontSize: '0.9rem', color: 'var(--text-light)' }}>
                  Suba la oferta del martes para actualizar los datos de peso, edad y ganancia de los lotes.
                  Las asignaciones de día se mantienen.
                </p>
                <div style={{ display: 'flex', gap: '0.75rem', alignItems: 'center', flexWrap: 'wrap' }}>
                  <div
                    style={{
                      flex: 1,
                      minWidth: 200,
                      border: '1px dashed var(--border)',
                      borderRadius: 8,
                      padding: '0.75rem 1rem',
                      cursor: 'pointer',
                      background: ajusteFile ? 'var(--info-light)' : '#f8fafc',
                      display: 'flex',
                      alignItems: 'center',
                      gap: 8,
                      fontSize: '0.85rem',
                      transition: 'all 0.2s',
                    }}
                    onClick={() => ajusteInputRef.current?.click()}
                  >
                    {ajusteFile ? (
                      <><FileSpreadsheet size={16} color="var(--info)" /> {ajusteFile.name}</>
                    ) : (
                      <><UploadCloud size={16} color="var(--text-light)" /> Seleccionar archivo Excel...</>
                    )}
                    <input
                      ref={ajusteInputRef}
                      type="file"
                      accept=".xlsx,.xls"
                      style={{ display: 'none' }}
                      onChange={(e) => handleAjusteFile(e.target.files[0])}
                    />
                  </div>
                  <button
                    className="btn btn-primary"
                    disabled={!ajusteFile || ajusteLoading}
                    onClick={handleAjusteMartes}
                    style={{ whiteSpace: 'nowrap' }}
                  >
                    {ajusteLoading ? (
                      <><span className="spinner" style={{ width: 14, height: 14, marginRight: 6 }}></span> Ajustando...</>
                    ) : (
                      <><RefreshCw size={14} /> Aplicar Ajuste</>
                    )}
                  </button>
                  {ajusteFile && (
                    <button className="btn btn-sm btn-outline" onClick={() => setAjusteFile(null)}>
                      <X size={14} />
                    </button>
                  )}
                </div>

                {/* Resumen del ajuste */}
                {ajusteResumen && (
                  <motion.div
                    initial={{ opacity: 0, y: 10 }}
                    animate={{ opacity: 1, y: 0 }}
                    style={{ marginTop: '1rem', padding: '1rem', background: '#f8fafc', borderRadius: 8, border: '1px solid var(--border)' }}
                  >
                    <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '0.75rem' }}>
                      <strong style={{ fontSize: '0.9rem' }}>Resultado del ajuste</strong>
                      <button className="btn btn-sm btn-outline" onClick={() => setAjusteResumen(null)}>
                        <X size={12} />
                      </button>
                    </div>
                    <div style={{ display: 'flex', gap: '1rem', flexWrap: 'wrap', marginBottom: '0.75rem' }}>
                      {ajusteResumen.lotes_actualizados > 0 && (
                        <span style={{ display: 'flex', alignItems: 'center', gap: 4, fontSize: '0.85rem', color: 'var(--success)' }}>
                          <CheckCircle2 size={14} /> {ajusteResumen.lotes_actualizados} lotes actualizados
                        </span>
                      )}
                      {ajusteResumen.lotes_nuevos_asignados > 0 && (
                        <span style={{ display: 'flex', alignItems: 'center', gap: 4, fontSize: '0.85rem', color: 'var(--success)' }}>
                          <CheckCircle2 size={14} /> {ajusteResumen.lotes_nuevos_asignados} lotes nuevos asignados
                        </span>
                      )}
                      {ajusteResumen.lotes_reinsertados_no_asignados > 0 && (
                        <span style={{ display: 'flex', alignItems: 'center', gap: 4, fontSize: '0.85rem', color: 'var(--success)' }}>
                          <Undo2 size={14} /> {ajusteResumen.lotes_reinsertados_no_asignados} remanentes reinsertados
                        </span>
                      )}
                      {(ajusteResumen.lotes_nuevos - (ajusteResumen.lotes_nuevos_asignados || 0) - (ajusteResumen.lotes_nuevos_fuera_rango || 0)) > 0 && (
                        <span style={{ display: 'flex', alignItems: 'center', gap: 4, fontSize: '0.85rem', color: 'var(--info)' }}>
                          <PlusCircle size={14} /> {ajusteResumen.lotes_nuevos - (ajusteResumen.lotes_nuevos_asignados || 0) - (ajusteResumen.lotes_nuevos_fuera_rango || 0)} lotes nuevos sin capacidad
                        </span>
                      )}
                      {ajusteResumen.lotes_nuevos_fuera_rango > 0 && (
                        <span style={{ display: 'flex', alignItems: 'center', gap: 4, fontSize: '0.85rem', color: 'var(--danger, #ef4444)' }}>
                          <Ban size={14} /> {ajusteResumen.lotes_nuevos_fuera_rango} lotes nuevos fuera de rango
                        </span>
                      )}
                      {ajusteResumen.lotes_fuera_rango_post_ajuste > 0 && (
                        <span style={{ display: 'flex', alignItems: 'center', gap: 4, fontSize: '0.85rem', color: 'var(--danger, #ef4444)' }}>
                          <AlertTriangle size={14} /> {ajusteResumen.lotes_fuera_rango_post_ajuste} lotes existentes ahora fuera de rango
                        </span>
                      )}
                      {ajusteResumen.lotes_faltantes > 0 && (
                        <span style={{ display: 'flex', alignItems: 'center', gap: 4, fontSize: '0.85rem', color: 'var(--warning)' }}>
                          <AlertTriangle size={14} /> {ajusteResumen.lotes_faltantes} lotes no encontrados en martes
                        </span>
                      )}
                      {ajusteResumen.lotes_actualizados === 0 && ajusteResumen.lotes_nuevos === 0 && ajusteResumen.lotes_faltantes === 0 && ajusteResumen.lotes_reinsertados_no_asignados === 0 && (
                        <span style={{ fontSize: '0.85rem', color: 'var(--text-light)' }}>Sin cambios detectados.</span>
                      )}
                    </div>

                    {/* Detalle de actualizaciones */}
                    {ajusteResumen.detalle_actualizados?.length > 0 && (
                      <div style={{ marginBottom: '0.5rem' }}>
                        <p style={{ fontSize: '0.8rem', fontWeight: 600, color: 'var(--text-light)', marginBottom: 4 }}>Cambios:</p>
                        <div className="table-container" style={{ maxHeight: 180, overflowY: 'auto' }}>
                          <table>
                            <thead>
                              <tr>
                                <th>Granja</th>
                                <th>Galpón</th>
                                <th>Día</th>
                                <th>Cambios</th>
                              </tr>
                            </thead>
                            <tbody>
                              {ajusteResumen.detalle_actualizados.map((d, i) => (
                                <tr key={i}>
                                  <td><strong>{d.granja}</strong></td>
                                  <td className="text-center">{d.galpon}</td>
                                  <td>{d.dia}</td>
                                  <td style={{ fontSize: '0.8rem' }}>{d.cambios}</td>
                                </tr>
                              ))}
                            </tbody>
                          </table>
                        </div>
                      </div>
                    )}

                    {/* Lotes existentes ahora fuera de rango tras ajuste martes */}
                    {ajusteResumen.detalle_fuera_rango_post_ajuste?.length > 0 && (
                      <div style={{ marginBottom: '0.5rem' }}>
                        <p style={{ fontSize: '0.8rem', fontWeight: 600, color: 'var(--danger, #ef4444)', marginBottom: 4 }}>⚠ Lotes existentes ahora fuera de rango (revisar manualmente):</p>
                        <div className="table-container" style={{ maxHeight: 180, overflowY: 'auto' }}>
                          <table>
                            <thead>
                              <tr>
                                <th>Granja</th>
                                <th>Galpón</th>
                                <th>Cantidad</th>
                                <th>Día</th>
                                <th>Alerta</th>
                              </tr>
                            </thead>
                            <tbody>
                              {ajusteResumen.detalle_fuera_rango_post_ajuste.map((d, i) => (
                                <tr key={i}>
                                  <td><strong>{d.granja}</strong></td>
                                  <td className="text-center">{d.galpon}</td>
                                  <td className="text-right">{formatNumber(d.cantidad)}</td>
                                  <td>{d.dia}</td>
                                  <td style={{ fontSize: '0.8rem', color: 'var(--danger, #ef4444)' }}>{d.alerta}</td>
                                </tr>
                              ))}
                            </tbody>
                          </table>
                        </div>
                      </div>
                    )}

                    {/* Lotes nuevos asignados automáticamente */}
                    {ajusteResumen.detalle_nuevos_asignados?.length > 0 && (
                      <div style={{ marginBottom: '0.5rem' }}>
                        <p style={{ fontSize: '0.8rem', fontWeight: 600, color: 'var(--success)', marginBottom: 4 }}>Lotes nuevos asignados:</p>
                        <div className="table-container" style={{ maxHeight: 180, overflowY: 'auto' }}>
                          <table>
                            <thead>
                              <tr>
                                <th>Granja</th>
                                <th>Galpón</th>
                                <th>Núcleo</th>
                                <th className="text-right">Cantidad</th>
                                <th>Día asignado</th>
                              </tr>
                            </thead>
                            <tbody>
                              {ajusteResumen.detalle_nuevos_asignados.map((d, i) => (
                                <tr key={i}>
                                  <td><strong>{d.granja}</strong></td>
                                  <td className="text-center">{d.galpon}</td>
                                  <td className="text-center">{d.nucleo}</td>
                                  <td className="text-right">{formatNumber(d.cantidad)}</td>
                                  <td>{d.dia}</td>
                                </tr>
                              ))}
                            </tbody>
                          </table>
                        </div>
                      </div>
                    )}

                    {/* Backlog previo reinsertado automáticamente */}
                    {ajusteResumen.detalle_reinsertados_no_asignados?.length > 0 && (
                      <div style={{ marginBottom: '0.5rem' }}>
                        <p style={{ fontSize: '0.8rem', fontWeight: 600, color: 'var(--success)', marginBottom: 4 }}>Remanentes previos reinsertados:</p>
                        <div className="table-container" style={{ maxHeight: 180, overflowY: 'auto' }}>
                          <table>
                            <thead>
                              <tr>
                                <th>Granja</th>
                                <th>Galpón</th>
                                <th>Núcleo</th>
                                <th className="text-right">Cantidad</th>
                                <th>Día asignado</th>
                              </tr>
                            </thead>
                            <tbody>
                              {ajusteResumen.detalle_reinsertados_no_asignados.map((d, i) => (
                                <tr key={i}>
                                  <td><strong>{d.granja}</strong></td>
                                  <td className="text-center">{d.galpon}</td>
                                  <td className="text-center">{d.nucleo}</td>
                                  <td className="text-right">{formatNumber(d.cantidad)}</td>
                                  <td>{d.dia}</td>
                                </tr>
                              ))}
                            </tbody>
                          </table>
                        </div>
                      </div>
                    )}

                    {/* Lotes faltantes (en proyección pero no en martes) */}
                    {ajusteResumen.detalle_faltantes?.length > 0 && (
                      <div style={{ marginBottom: '0.5rem' }}>
                        <p style={{ fontSize: '0.8rem', fontWeight: 600, color: 'var(--warning)', marginBottom: 4 }}>⚠ Lotes no encontrados en oferta del martes (se mantienen sin cambios):</p>
                        <div className="table-container" style={{ maxHeight: 180, overflowY: 'auto' }}>
                          <table>
                            <thead>
                              <tr>
                                <th>Granja</th>
                                <th>Galpón</th>
                                <th>Núcleo</th>
                                <th className="text-right">Cantidad</th>
                                <th>Sexo</th>
                                <th>Día</th>
                              </tr>
                            </thead>
                            <tbody>
                              {ajusteResumen.detalle_faltantes.map((d, i) => (
                                <tr key={i}>
                                  <td><strong>{d.granja}</strong></td>
                                  <td className="text-center">{d.galpon}</td>
                                  <td className="text-center">{d.nucleo}</td>
                                  <td className="text-right">{formatNumber(d.cantidad)}</td>
                                  <td className="text-center">{d.sexo}</td>
                                  <td>{d.dia}</td>
                                </tr>
                              ))}
                            </tbody>
                          </table>
                        </div>
                      </div>
                    )}
                  </motion.div>
                )}
              </div>
            </motion.div>
          )}
        </AnimatePresence>
      </motion.div>

      {lotesNoAsignados.length > 0 && (
        <motion.div variants={itemVariants} className="card card-compact" style={{ borderLeft: '4px solid var(--warning)' }}>
          <div className="card-header">
            <h2><PackageOpen size={18} style={{ verticalAlign: 'middle', marginRight: 6 }} /> Lotes no asignados por tope diario</h2>
            <button
              className="btn btn-sm btn-outline"
              onClick={async () => {
                try {
                  const result = await cargarDeficit()
                  toast.success(result.mensaje || `${result.lotes_trasladados} lotes trasladados al déficit para la semana siguiente`)
                } catch (err) {
                  toast.error(err.response?.data?.detail || 'Error al trasladar déficit')
                }
              }}
              style={{ fontSize: '0.8rem' }}
              title="Guardar estos lotes como déficit para incluirlos en la planificación de la semana siguiente"
            >
              <ArrowLeftRight size={14} /> Trasladar a semana siguiente
            </button>
          </div>
          <div className="card-body">
            <p style={{ marginBottom: '0.8rem', fontSize: '0.9rem', color: 'var(--text-light)' }}>
              {lotesNoAsignados.length} lotes no asignados ({formatNumber(proyeccion.total_pollos_no_asignados || 0)} pollos). Revise estos lotes para decidir ajuste manual o cambio de parámetros.
            </p>
            <div className="table-container" style={{ maxHeight: '260px', overflowY: 'auto' }}>
              <table>
                <thead>
                  <tr>
                    <th>Granja</th>
                    <th>Galpón</th>
                    <th>Núcleo</th>
                    <th className="text-right">Cantidad</th>
                    <th>Días elegibles</th>
                    <th>Motivo</th>
                  </tr>
                </thead>
                <tbody>
                  {lotesNoAsignados.map((lote, idx) => (
                    <tr key={`no-asignado-${idx}`}>
                      <td><strong>{lote.granja}</strong></td>
                      <td className="text-center">{lote.galpon}</td>
                      <td className="text-center">{lote.nucleo}</td>
                      <td className="text-right">{formatNumber(lote.cantidad)}</td>
                      <td>{formatDiasElegibles(lote.dias_elegibles)}</td>
                      <td style={{ color: 'var(--warning)' }}>{lote.motivo}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        </motion.div>
      )}

      {lotesFueraRango.length > 0 && (
        <motion.div variants={itemVariants} className="card card-compact" style={{ borderLeft: '4px solid var(--danger, #ef4444)' }}>
          <div className="card-header">
            <h2><Ban size={18} style={{ verticalAlign: 'middle', marginRight: 6 }} /> Lotes fuera de rango (edad/peso)</h2>
          </div>
          <div className="card-body">
            <p style={{ marginBottom: '0.8rem', fontSize: '0.9rem', color: 'var(--text-light)' }}>
              {lotesFueraRango.length} lotes fuera de rango ({formatNumber(proyeccion.total_pollos_fuera_rango || 0)} pollos).
              No cumplen los requisitos de edad o peso para ningún día de faena.
            </p>
            <div className="table-container" style={{ maxHeight: '360px', overflowY: 'auto' }}>
              <table>
                <thead>
                  <tr>
                    <th style={{ width: 28 }}></th>
                    <th>Granja</th>
                    <th>Galpón</th>
                    <th>Núcleo</th>
                    <th className="text-right">Cantidad</th>
                    <th>Sexo</th>
                    <th>Motivo</th>
                  </tr>
                </thead>
                <tbody>
                  {lotesFueraRango.map((lote, idx) => (
                    <React.Fragment key={`fr-${idx}`}>
                      <tr
                        style={{ cursor: 'pointer' }}
                        onClick={() => toggleFR(idx)}
                      >
                        <td style={{ padding: '0.3rem 0.4rem' }}>
                          {expandedFR.has(idx)
                            ? <ChevronDown size={14} />
                            : <ChevronRight size={14} />
                          }
                        </td>
                        <td><strong>{lote.granja}</strong></td>
                        <td className="text-center">{lote.galpon}</td>
                        <td className="text-center">{lote.nucleo}</td>
                        <td className="text-right">{formatNumber(lote.cantidad)}</td>
                        <td className="text-center">{lote.sexo || '-'}</td>
                        <td style={{ color: 'var(--danger, #ef4444)', fontSize: '0.85rem' }}>{lote.motivo}</td>
                      </tr>
                      {expandedFR.has(idx) && lote.detalle_por_dia?.length > 0 && (
                        <tr>
                          <td colSpan={7} style={{ padding: '0 0.5rem 0.5rem 2rem', background: '#fef2f2' }}>
                            <table style={{ width: '100%', fontSize: '0.8rem' }}>
                              <thead>
                                <tr>
                                  <th>Día</th>
                                  <th className="text-right">Edad Proy.</th>
                                  <th className="text-right">Peso Proy.</th>
                                  <th>Razón</th>
                                </tr>
                              </thead>
                              <tbody>
                                {lote.detalle_por_dia.map((d, dIdx) => (
                                  <tr key={dIdx}>
                                    <td>{formatDate(d.fecha)}</td>
                                    <td className="text-right">{d.edad_proyectada}</td>
                                    <td className="text-right">{d.peso_proyectado?.toFixed(2)}</td>
                                    <td style={{ color: 'var(--danger, #ef4444)' }}>{d.razon}</td>
                                  </tr>
                                ))}
                              </tbody>
                            </table>
                          </td>
                        </tr>
                      )}
                    </React.Fragment>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        </motion.div>
      )}

      {/* ═══ Sugerencias inteligentes de diferimiento ═══ */}
      {sugerencias && sugerencias.total_sugerencias > 0 && (() => {
        const activas = sugerencias.sugerencias.filter((_, i) => !sugerenciasIgnoradas.has(i))
        const CRITERIO_LABELS = {
          sobrecarga: { label: 'Sobrecarga', color: '#ef4444', icon: '⚠️' },
          mejor_calibre: { label: 'Mejor calibre', color: '#f59e0b', icon: '⚖️' },
          feriado: { label: 'Feriado', color: '#6366f1', icon: '📅' },
          edad_temprana: { label: 'Edad temprana', color: '#0ea5e9', icon: '🐣' },
        }
        return (
          <motion.div variants={itemVariants} className="card card-compact" style={{ borderLeft: '4px solid #f59e0b', marginBottom: '0.5rem' }}>
            <div
              className="card-header"
              style={{ cursor: 'pointer', userSelect: 'none', background: 'rgba(245, 158, 11, 0.04)' }}
              onClick={() => setSugerenciasOpen(!sugerenciasOpen)}
            >
              <h2 style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                <Lightbulb size={18} color="#f59e0b" />
                Sugerencias de diferimiento
                <span style={{
                  padding: '0.15rem 0.5rem',
                  background: 'rgba(245, 158, 11, 0.12)',
                  border: '1px solid rgba(245, 158, 11, 0.3)',
                  borderRadius: 12,
                  fontSize: '0.72rem',
                  color: '#d97706',
                  fontWeight: 600,
                }}>
                  {activas.length} sugerencia{activas.length !== 1 ? 's' : ''}
                </span>
                {sugerencias.total_pollos_sugeridos > 0 && (
                  <span style={{ fontSize: '0.78rem', color: 'var(--text-light)', fontWeight: 400 }}>
                    ({formatNumber(sugerencias.total_pollos_sugeridos)} pollos)
                  </span>
                )}
              </h2>
              <span style={{ fontSize: '0.85rem', color: 'var(--text-light)' }}>
                {sugerenciasOpen ? '▲ Cerrar' : '▼ Abrir'}
              </span>
            </div>
            <AnimatePresence>
              {sugerenciasOpen && (
                <motion.div
                  initial={{ height: 0, opacity: 0 }}
                  animate={{ height: 'auto', opacity: 1 }}
                  exit={{ height: 0, opacity: 0 }}
                  style={{ overflow: 'hidden' }}
                >
                  <div className="card-body">
                    {/* Info banner */}
                    <div style={{
                      padding: '0.6rem 0.9rem',
                      background: 'rgba(245, 158, 11, 0.06)',
                      border: '1px solid rgba(245, 158, 11, 0.2)',
                      borderRadius: 8,
                      marginBottom: '0.75rem',
                      fontSize: '0.82rem',
                      color: '#92400e',
                      display: 'flex',
                      alignItems: 'center',
                      justifyContent: 'space-between',
                      flexWrap: 'wrap',
                      gap: 8,
                    }}>
                      <span>
                        El sistema sugiere diferir estos lotes a Semana 2 para optimizar la planificación.
                        <strong> Usted decide</strong> cuáles aceptar.
                      </span>
                      <div style={{ display: 'flex', gap: 6 }}>
                        {activas.length > 1 && (
                          <button
                            className="btn btn-sm"
                            style={{ background: '#d97706', color: 'white', fontSize: '0.78rem' }}
                            onClick={handleAceptarTodas}
                          >
                            <Check size={12} /> Aceptar todas ({activas.length})
                          </button>
                        )}
                        <button
                          className="btn btn-sm btn-outline"
                          style={{ borderColor: '#d97706', color: '#d97706', fontSize: '0.78rem' }}
                          onClick={cargarSugerencias}
                          disabled={sugerenciasLoading}
                        >
                          <RefreshCw size={12} /> Actualizar
                        </button>
                      </div>
                    </div>

                    {/* Badges por criterio */}
                    {sugerencias.por_criterio && Object.keys(sugerencias.por_criterio).length > 0 && (
                      <div style={{ display: 'flex', gap: 6, marginBottom: '0.75rem', flexWrap: 'wrap' }}>
                        {Object.entries(sugerencias.por_criterio).map(([criterio, count]) => {
                          const info = CRITERIO_LABELS[criterio] || { label: criterio, color: '#6b7280', icon: '📌' }
                          return (
                            <span key={criterio} style={{
                              display: 'inline-flex', alignItems: 'center', gap: 4,
                              padding: '0.2rem 0.6rem',
                              background: `${info.color}10`,
                              border: `1px solid ${info.color}30`,
                              borderRadius: 16,
                              fontSize: '0.75rem',
                              color: info.color,
                              fontWeight: 600,
                            }}>
                              {info.icon} {info.label}: {count}
                            </span>
                          )
                        })}
                      </div>
                    )}

                    {/* Lista de sugerencias */}
                    <div style={{ display: 'flex', flexDirection: 'column', gap: '0.5rem' }}>
                      {sugerencias.sugerencias.map((sug, idx) => {
                        if (sugerenciasIgnoradas.has(idx)) return null
                        const info = CRITERIO_LABELS[sug.criterio] || { label: sug.criterio, color: '#6b7280', icon: '📌' }
                        const isLoading = diferirLoading === `${sug.dia_index}-${sug.lote_index}`
                        return (
                          <motion.div
                            key={idx}
                            initial={{ opacity: 0, x: -10 }}
                            animate={{ opacity: 1, x: 0 }}
                            transition={{ delay: idx * 0.05 }}
                            style={{
                              padding: '0.7rem 0.9rem',
                              background: `${info.color}06`,
                              border: `1px solid ${info.color}20`,
                              borderLeft: `3px solid ${info.color}`,
                              borderRadius: 8,
                              display: 'flex',
                              alignItems: 'flex-start',
                              gap: 10,
                            }}
                          >
                            <div style={{ flex: 1 }}>
                              <div style={{ display: 'flex', alignItems: 'center', gap: 6, marginBottom: 4 }}>
                                <span style={{
                                  padding: '0.1rem 0.4rem',
                                  background: `${info.color}15`,
                                  border: `1px solid ${info.color}30`,
                                  borderRadius: 10,
                                  fontSize: '0.68rem',
                                  color: info.color,
                                  fontWeight: 700,
                                  textTransform: 'uppercase',
                                }}>
                                  {info.icon} {info.label}
                                </span>
                                <strong style={{ fontSize: '0.88rem' }}>{sug.granja} G{sug.galpon} N{sug.nucleo}</strong>
                                <span className={`badge badge-${sug.sexo === 'M' ? 'info' : sug.sexo === 'H' ? 'warning' : 'success'}`}>
                                  {sug.sexo}
                                </span>
                                <span style={{ fontSize: '0.78rem', color: 'var(--text-light)' }}>
                                  {formatNumber(sug.cantidad)} pollos · {sug.dia_nombre}
                                </span>
                              </div>
                              <p style={{ margin: 0, fontSize: '0.82rem', color: 'var(--text-light)', lineHeight: 1.4 }}>
                                {sug.motivo}
                              </p>
                              {sug.impacto?.peso_estimado_s2 && (
                                <div style={{ marginTop: 4, fontSize: '0.78rem', color: info.color }}>
                                  Peso S1: {sug.impacto.peso_actual?.toFixed(3)} kg → S2: ~{sug.impacto.peso_estimado_s2?.toFixed(3)} kg
                                  {sug.impacto.mejora_peso_g > 0 && <strong> (+{sug.impacto.mejora_peso_g}g)</strong>}
                                </div>
                              )}
                            </div>
                            <div style={{ display: 'flex', gap: 4, alignItems: 'center', flexShrink: 0 }}>
                              <button
                                className="btn btn-sm"
                                style={{ background: '#d97706', color: 'white', fontSize: '0.75rem', padding: '0.25rem 0.6rem' }}
                                onClick={() => handleAceptarSugerencia(sug)}
                                disabled={isLoading}
                                title="Aceptar: diferir este lote a S2"
                              >
                                {isLoading
                                  ? <Loader2 size={12} style={{ animation: 'spin 1s linear infinite' }} />
                                  : <><Check size={12} /> Aceptar</>
                                }
                              </button>
                              <button
                                className="btn btn-sm btn-outline"
                                style={{ fontSize: '0.75rem', padding: '0.25rem 0.5rem', color: 'var(--text-light)', borderColor: 'var(--border)' }}
                                onClick={() => handleIgnorarSugerencia(idx)}
                                title="Ignorar esta sugerencia"
                              >
                                <EyeOff size={12} />
                              </button>
                            </div>
                          </motion.div>
                        )
                      })}
                    </div>
                  </div>
                </motion.div>
              )}
            </AnimatePresence>
          </motion.div>
        )
      })()}

      {/* Toggle vista */}
      <motion.div variants={itemVariants} className="tabs" style={{ justifyContent: 'space-between' }}>
        <div style={{ display: 'flex', gap: '0.5rem' }}>
          <button className={`tab ${viewMode === 'cards' ? 'active' : ''}`} onClick={() => setViewMode('cards')}>
            <KanbanSquare size={16} style={{ verticalAlign: 'middle', marginRight: 4 }} /> Vista por Día
          </button>
          <button className={`tab ${viewMode === 'table' ? 'active' : ''}`} onClick={() => setViewMode('table')}>
            <Table size={16} style={{ verticalAlign: 'middle', marginRight: 4 }} /> Vista Tabla
          </button>
        </div>
        <div style={{ display: 'flex', gap: '0.5rem' }}>
          <button
            className="btn btn-sm btn-outline"
            onClick={() => setShowTercerosModal(true)}
            style={{ borderColor: '#7c3aed', color: '#7c3aed', marginBottom: '0.5rem' }}
          >
            <ShoppingCart size={14} style={{ marginRight: 4 }} /> Compra Terceros
          </button>
          <button
            className="btn btn-sm btn-outline"
            onClick={handleCargarDisponibles}
            style={{ borderColor: '#059669', color: '#059669', marginBottom: '0.5rem' }}
            disabled={disponiblesLoading}
          >
            {disponiblesLoading
              ? <Loader2 size={14} style={{ animation: 'spin 1s linear infinite', marginRight: 4 }} />
              : <PackageOpen size={14} style={{ marginRight: 4 }} />
            }
            Lotes Disponibles
          </button>
          <button className="btn btn-sm btn-outline" onClick={() => exportProyeccionPDF(proyeccion)} style={{ marginBottom: '0.5rem' }}>
            <Download size={14} /> Descargar PDF
          </button>
        </div>
      </motion.div>

      {/* Modal de mover */}
      <AnimatePresence>
        {movingLote && (
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            className="modal-overlay"
            onClick={() => setMovingLote(null)}
          >
            <motion.div
              initial={{ scale: 0.9, y: 20 }}
              animate={{ scale: 1, y: 0 }}
              exit={{ scale: 0.9, y: 20 }}
              className="modal"
              onClick={e => e.stopPropagation()}
            >
              <div className="modal-header">
                <h3><ArrowLeftRight size={18} style={{ verticalAlign: 'middle', marginRight: 6 }} /> Mover lote a otro día</h3>
                <button className="btn btn-sm btn-outline" onClick={() => setMovingLote(null)}>
                  <X size={16} />
                </button>
              </div>
              <div className="modal-body">
                <p style={{ marginBottom: '1rem', fontSize: '0.9rem' }}>
                  Mover <strong>{movingLote.lote.granja} G{movingLote.lote.galpon}</strong> ({formatNumber(movingLote.lote.cantidad)} pollos) desde {getDiaNombre(dias[movingLote.diaIdx]?.fecha)}:
                </p>
                <div style={{ display: 'flex', flexDirection: 'column', gap: '0.5rem' }}>
                  {dias.map((d, idx) => (
                    idx !== movingLote.diaIdx && (
                      <button
                        key={idx}
                        className="btn btn-outline"
                        onClick={() => handleMove(movingLote.diaIdx, movingLote.loteIdx, idx)}
                        disabled={loading}
                        style={{ justifyContent: 'flex-start' }}
                      >
                        <Calendar size={16} style={{ marginRight: 6 }} /> {getDiaNombre(d.fecha)} ({formatDate(d.fecha)}) — {formatNumber(d.total_pollos)} pollos
                      </button>
                    )
                  ))}
                </div>
              </div>
            </motion.div>
          </motion.div>
        )}
      </AnimatePresence>

      {/* Modal de compra a terceros */}
      <AnimatePresence>
        {showTercerosModal && (
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            className="modal-overlay"
            onClick={() => { setShowTercerosModal(false); resetTercerosForm() }}
          >
            <motion.div
              initial={{ scale: 0.9, y: 20 }}
              animate={{ scale: 1, y: 0 }}
              exit={{ scale: 0.9, y: 20 }}
              className="modal"
              style={{ maxWidth: 620 }}
              onClick={e => e.stopPropagation()}
            >
              <div className="modal-header" style={{ background: 'rgba(168,85,247,0.06)' }}>
                <h3 style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
                  <ShoppingCart size={18} style={{ color: '#7c3aed' }} /> Agregar Lote de Terceros
                </h3>
                <button className="btn btn-sm btn-outline" onClick={() => { setShowTercerosModal(false); resetTercerosForm() }}>
                  <X size={16} />
                </button>
              </div>
              <div className="modal-body" style={{ display: 'flex', flexDirection: 'column', gap: '0.75rem' }}>
                <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '0.75rem' }}>
                  <div>
                    <label style={{ fontSize: '0.8rem', fontWeight: 600, color: 'var(--text-light)', marginBottom: 4, display: 'block' }}>Día de Faena *</label>
                    <select
                      className="form-control"
                      value={tercerosForm.dia_faena}
                      onChange={e => setTercerosForm({ ...tercerosForm, dia_faena: e.target.value })}
                      style={{ width: '100%' }}
                    >
                      {dias.map((d, idx) => (
                        <option key={idx} value={idx}>{getDiaNombre(d.fecha)} - {formatDate(d.fecha)}</option>
                      ))}
                    </select>
                  </div>
                  <div>
                    <label style={{ fontSize: '0.8rem', fontWeight: 600, color: 'var(--text-light)', marginBottom: 4, display: 'block' }}>Proveedor *</label>
                    <input
                      className="form-control"
                      type="text"
                      placeholder="Nombre del proveedor"
                      value={tercerosForm.granja}
                      onChange={e => setTercerosForm({ ...tercerosForm, granja: e.target.value })}
                      style={{ width: '100%' }}
                    />
                  </div>
                </div>
                <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '0.75rem' }}>
                  <div>
                    <label style={{ fontSize: '0.8rem', fontWeight: 600, color: 'var(--text-light)', marginBottom: 4, display: 'block' }}>Cantidad de Pollos *</label>
                    <input
                      className="form-control"
                      type="number"
                      placeholder="Ej: 10000"
                      value={tercerosForm.cantidad}
                      onChange={e => setTercerosForm({ ...tercerosForm, cantidad: e.target.value })}
                      style={{ width: '100%' }}
                    />
                  </div>
                  <div>
                    <label style={{ fontSize: '0.8rem', fontWeight: 600, color: 'var(--text-light)', marginBottom: 4, display: 'block' }}>Sexo</label>
                    <select
                      className="form-control"
                      value={tercerosForm.sexo}
                      onChange={e => setTercerosForm({ ...tercerosForm, sexo: e.target.value })}
                      style={{ width: '100%' }}
                    >
                      <option value="M">Macho</option>
                      <option value="H">Hembra</option>
                      <option value="MIX">Mixto</option>
                    </select>
                  </div>
                </div>
                <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr 1fr', gap: '0.75rem' }}>
                  <div>
                    <label style={{ fontSize: '0.8rem', fontWeight: 600, color: 'var(--text-light)', marginBottom: 4, display: 'block' }}>Edad Proyectada *</label>
                    <input
                      className="form-control"
                      type="number"
                      placeholder="Ej: 38"
                      value={tercerosForm.edad_proyectada}
                      onChange={e => setTercerosForm({ ...tercerosForm, edad_proyectada: e.target.value })}
                      style={{ width: '100%' }}
                    />
                  </div>
                  <div>
                    <label style={{ fontSize: '0.8rem', fontWeight: 600, color: 'var(--text-light)', marginBottom: 4, display: 'block' }}>Peso Muestreo (kg) *</label>
                    <input
                      className="form-control"
                      type="number"
                      step="0.01"
                      placeholder="Ej: 2.90"
                      value={tercerosForm.peso_muestreo_proy}
                      onChange={e => setTercerosForm({ ...tercerosForm, peso_muestreo_proy: e.target.value })}
                      style={{ width: '100%' }}
                    />
                  </div>
                  <div>
                    <label style={{ fontSize: '0.8rem', fontWeight: 600, color: 'var(--text-light)', marginBottom: 4, display: 'block' }}>Ganancia Diaria</label>
                    <input
                      className="form-control"
                      type="number"
                      step="0.001"
                      value={tercerosForm.ganancia_diaria}
                      onChange={e => setTercerosForm({ ...tercerosForm, ganancia_diaria: e.target.value })}
                      style={{ width: '100%' }}
                    />
                  </div>
                </div>
                <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr 1fr', gap: '0.75rem' }}>
                  <div>
                    <label style={{ fontSize: '0.8rem', fontWeight: 600, color: 'var(--text-light)', marginBottom: 4, display: 'block' }}>Fecha Peso *</label>
                    <input
                      className="form-control"
                      type="date"
                      value={tercerosForm.fecha_peso}
                      onChange={e => setTercerosForm({ ...tercerosForm, fecha_peso: e.target.value })}
                      style={{ width: '100%' }}
                    />
                  </div>
                  <div>
                    <label style={{ fontSize: '0.8rem', fontWeight: 600, color: 'var(--text-light)', marginBottom: 4, display: 'block' }}>Fecha Ingreso *</label>
                    <input
                      className="form-control"
                      type="date"
                      value={tercerosForm.fecha_ingreso}
                      onChange={e => setTercerosForm({ ...tercerosForm, fecha_ingreso: e.target.value })}
                      style={{ width: '100%' }}
                    />
                  </div>
                  <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '0.5rem' }}>
                    <div>
                      <label style={{ fontSize: '0.8rem', fontWeight: 600, color: 'var(--text-light)', marginBottom: 4, display: 'block' }}>Galpón</label>
                      <input
                        className="form-control"
                        type="number"
                        value={tercerosForm.galpon}
                        onChange={e => setTercerosForm({ ...tercerosForm, galpon: e.target.value })}
                        style={{ width: '100%' }}
                      />
                    </div>
                    <div>
                      <label style={{ fontSize: '0.8rem', fontWeight: 600, color: 'var(--text-light)', marginBottom: 4, display: 'block' }}>Núcleo</label>
                      <input
                        className="form-control"
                        type="number"
                        value={tercerosForm.nucleo}
                        onChange={e => setTercerosForm({ ...tercerosForm, nucleo: e.target.value })}
                        style={{ width: '100%' }}
                      />
                    </div>
                  </div>
                </div>
                {/* Indicador de capacidad del día seleccionado */}
                {(() => {
                  const diaSeleccionado = dias[Number(tercerosForm.dia_faena)]
                  if (!diaSeleccionado) return null
                  const esSabado = new Date(diaSeleccionado.fecha + 'T12:00:00').getDay() === 6
                  const capNormal = esSabado ? parametros.limite_sabado : parametros.capacidad_maxima_planta
                  const capExtras = parametros.capacidad_con_horas_extras
                  const objMax = parametros.pollos_diarios_objetivo_max
                  const totalActual = (diaSeleccionado.total_pollos || 0) + (diaSeleccionado.gallinas_cantidad || 0)
                  const cantAgregar = Number(tercerosForm.cantidad) || 0
                  const totalProyectado = totalActual + cantAgregar

                  let nivelActual = totalActual > capNormal ? 'horas_extras' : totalActual > objMax ? 'alto' : 'normal'
                  let nivelProyectado = totalProyectado > capNormal ? 'horas_extras' : totalProyectado > objMax ? 'alto' : 'normal'
                  const excedeLimiteAbsoluto = totalProyectado > capExtras

                  const colorNivel = (n) => n === 'horas_extras' ? '#ef4444' : n === 'alto' ? '#f97316' : '#22c55e'
                  const labelNivel = (n) => n === 'horas_extras' ? 'Horas Extras' : n === 'alto' ? 'Carga Alta' : 'Normal'

                  const pct = (v) => Math.min(100, Math.round((v / capExtras) * 100))

                  return (
                    <div style={{
                      padding: '0.75rem 1rem',
                      background: excedeLimiteAbsoluto ? 'rgba(239,68,68,0.08)' : 'rgba(124,58,237,0.06)',
                      border: `1px solid ${excedeLimiteAbsoluto ? 'rgba(239,68,68,0.4)' : 'rgba(124,58,237,0.2)'}`,
                      borderRadius: 8,
                      fontSize: '0.82rem',
                    }}>
                      <div style={{ fontWeight: 600, marginBottom: 8, color: excedeLimiteAbsoluto ? '#ef4444' : '#7c3aed' }}>
                        Capacidad del día — {getDiaNombre(diaSeleccionado.fecha)} {formatDate(diaSeleccionado.fecha)}
                      </div>

                      {/* Barra de progreso */}
                      <div style={{ position: 'relative', height: 10, background: 'rgba(0,0,0,0.08)', borderRadius: 6, marginBottom: 8, overflow: 'hidden' }}>
                        {/* Barra actual */}
                        <div style={{
                          position: 'absolute', left: 0, top: 0, bottom: 0,
                          width: `${pct(totalActual)}%`,
                          background: colorNivel(nivelActual),
                          borderRadius: 6,
                          transition: 'width 0.3s',
                          opacity: 0.5,
                        }} />
                        {/* Barra proyectada */}
                        {cantAgregar > 0 && (
                          <div style={{
                            position: 'absolute', left: 0, top: 0, bottom: 0,
                            width: `${pct(totalProyectado)}%`,
                            background: colorNivel(nivelProyectado),
                            borderRadius: 6,
                            transition: 'width 0.3s',
                            opacity: 0.85,
                          }} />
                        )}
                        {/* Marcadores */}
                        <div style={{ position: 'absolute', left: `${pct(objMax)}%`, top: 0, bottom: 0, width: 1, background: '#f97316', opacity: 0.7 }} title={`Carga alta: ${formatNumber(objMax)}`} />
                        <div style={{ position: 'absolute', left: `${pct(capNormal)}%`, top: 0, bottom: 0, width: 1, background: '#ef4444', opacity: 0.7 }} title={`Cap. máx: ${formatNumber(capNormal)}`} />
                      </div>

                      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', flexWrap: 'wrap', gap: 6 }}>
                        <div style={{ display: 'flex', gap: 12 }}>
                          <span style={{ color: 'var(--text-light)' }}>
                            Actual: <strong style={{ color: colorNivel(nivelActual) }}>{formatNumber(totalActual)}</strong>
                            <span style={{
                              marginLeft: 4, padding: '0.1rem 0.4rem',
                              background: colorNivel(nivelActual) + '22',
                              border: `1px solid ${colorNivel(nivelActual)}44`,
                              borderRadius: 8, fontSize: '0.75rem', color: colorNivel(nivelActual),
                            }}>{labelNivel(nivelActual)}</span>
                          </span>
                          {cantAgregar > 0 && (
                            <span style={{ color: 'var(--text-light)' }}>
                              → Con compra: <strong style={{ color: colorNivel(nivelProyectado) }}>{formatNumber(totalProyectado)}</strong>
                              <span style={{
                                marginLeft: 4, padding: '0.1rem 0.4rem',
                                background: colorNivel(nivelProyectado) + '22',
                                border: `1px solid ${colorNivel(nivelProyectado)}44`,
                                borderRadius: 8, fontSize: '0.75rem', color: colorNivel(nivelProyectado),
                              }}>{labelNivel(nivelProyectado)}</span>
                            </span>
                          )}
                        </div>
                        <span style={{ fontSize: '0.75rem', color: 'var(--text-light)' }}>
                          Cap. máx: {formatNumber(esSabado ? parametros.limite_sabado : parametros.capacidad_maxima_planta)} / Con ext: {formatNumber(capExtras)}
                        </span>
                      </div>

                      {excedeLimiteAbsoluto && (
                        <div style={{ marginTop: 8, color: '#ef4444', fontWeight: 600, display: 'flex', alignItems: 'center', gap: 4 }}>
                          <AlertTriangle size={13} /> Excede la capacidad máxima con horas extras ({formatNumber(capExtras)}). Reducir la cantidad o elegir otro día.
                        </div>
                      )}
                    </div>
                  )
                })()}

                <div>
                  <label style={{ fontSize: '0.8rem', fontWeight: 600, color: 'var(--text-light)', marginBottom: 4, display: 'block' }}>Motivo de Compra</label>
                  <textarea
                    className="form-control"
                    placeholder="Ej: Déficit de oferta propia, demanda comercial alta..."
                    value={tercerosForm.motivo_compra}
                    onChange={e => setTercerosForm({ ...tercerosForm, motivo_compra: e.target.value })}
                    rows={2}
                    style={{ width: '100%', resize: 'vertical' }}
                  />
                </div>
              </div>
              <div className="modal-footer">
                <button className="btn btn-outline" onClick={() => { setShowTercerosModal(false); resetTercerosForm() }}>
                  Cancelar
                </button>
                {(() => {
                  const diaSeleccionado = dias[Number(tercerosForm.dia_faena)]
                  const esSabado = diaSeleccionado ? new Date(diaSeleccionado.fecha + 'T12:00:00').getDay() === 6 : false
                  const capExtras = parametros.capacidad_con_horas_extras
                  const totalActual = (diaSeleccionado?.total_pollos || 0) + (diaSeleccionado?.gallinas_cantidad || 0)
                  const excede = totalActual + (Number(tercerosForm.cantidad) || 0) > capExtras
                  return (
                    <button
                      className="btn"
                      style={{ background: excede ? '#9ca3af' : '#7c3aed', color: 'white', cursor: excede ? 'not-allowed' : 'pointer' }}
                      onClick={handleAgregarTerceros}
                      disabled={tercerosLoading || excede}
                      title={excede ? `Excede la capacidad máxima (${formatNumber(capExtras)} pollos)` : ''}
                    >
                      {tercerosLoading
                        ? <><Loader2 size={14} style={{ animation: 'spin 1s linear infinite', marginRight: 4 }} /> Agregando...</>
                        : <><PlusCircle size={14} style={{ marginRight: 4 }} /> Agregar Lote</>
                      }
                    </button>
                  )
                })()}
              </div>
            </motion.div>
          </motion.div>
        )}
      </AnimatePresence>

      {/* Alerta: horas extras → sugerir sábado */}
      {proyeccion.dias.some(d => d.alerta_horas_extras) && !proyeccion.dias.some(d => d.es_sabado) && (
        <motion.div variants={itemVariants} style={{
          padding: '0.75rem 1rem',
          background: 'rgba(234,179,8,0.12)',
          border: '1px solid rgba(234,179,8,0.4)',
          borderRadius: 8,
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
          gap: 12,
          flexWrap: 'wrap',
        }}>
          <span style={{ display: 'flex', alignItems: 'center', gap: 6, fontSize: '0.9rem', color: '#854d0e' }}>
            <AlertTriangle size={16} />
            Hay días con horas extra. Se recomienda habilitar el sábado para redistribuir la carga.
          </span>
          <button
            className="btn btn-sm"
            style={{ background: '#854d0e', color: 'white', whiteSpace: 'nowrap' }}
            onClick={handleRegenerarConSabado}
          >
            Regenerar con sábado
          </button>
        </motion.div>
      )}

      {/* Vista Cards */}
      {viewMode === 'cards' && (
        <motion.div
          initial={{ opacity: 0, y: 10 }}
          animate={{ opacity: 1, y: 0 }}
          className="proyeccion-grid"
        >
          {dias.map((dia, diaIdx) => {
            const nivelLabel = getNivelCargaLabel(dia)
            const nivelStyle = getNivelCargaStyle(dia.nivel_carga)
            return (
            <div className="day-column" key={diaIdx} style={nivelStyle}>
              <div className="day-header" style={dia.nivel_carga === 'horas_extras' ? { background: '#fef2f2', borderBottom: '2px solid #ef4444' } : dia.nivel_carga === 'alto' ? { borderBottom: '2px solid #f97316' } : {}}>
                <div style={{ display: 'flex', flexDirection: 'column', gap: 2 }}>
                  <span>{getDiaNombre(dia.fecha)}{dia.es_sabado ? ' (Sáb)' : ''}</span>
                  {nivelLabel && (
                    <span style={{ display: 'flex', alignItems: 'center', gap: 3, fontSize: '0.65rem', fontWeight: 700, color: nivelLabel.color }}>
                      {nivelLabel.icon} {nivelLabel.text}
                    </span>
                  )}
                  {dia.gallinas_habilitado && (
                    <span style={{ fontSize: '0.65rem', color: '#7c3aed', fontWeight: 600 }}>
                      {dia.gallinas_livianas_cantidad > 0 && dia.gallinas_pesadas_cantidad > 0
                        ? `+ ${formatNumber(dia.gallinas_livianas_cantidad)} liv. + ${formatNumber(dia.gallinas_pesadas_cantidad)} pes.`
                        : dia.gallinas_pesadas_cantidad > 0
                          ? <span style={{ color: '#be185d' }}>+ {formatNumber(dia.gallinas_pesadas_cantidad)} pesadas</span>
                          : `+ ${formatNumber(dia.gallinas_cantidad)} gallinas`
                      }
                    </span>
                  )}
                  {(dia.gallinas_habilitado || dia.nivel_carga === 'horas_extras') && dia.lotes.length > 0 && (
                    <button
                      className="btn btn-sm btn-outline"
                      style={{ fontSize: '0.6rem', padding: '0.1rem 0.35rem', color: '#7c3aed', borderColor: '#7c3aed', marginTop: 2 }}
                      onClick={() => handleRedistribuir(diaIdx)}
                      disabled={redistribuyendo !== null}
                      title="Redistribuir lotes de este día a los días restantes"
                    >
                      {redistribuyendo === diaIdx
                        ? <Loader2 size={10} style={{ animation: 'spin 1s linear infinite' }} />
                        : 'Redistribuir'}
                    </button>
                  )}
                </div>
                <span className="day-total" style={dia.nivel_carga === 'horas_extras' ? { color: '#ef4444' } : {}}>{formatNumber(dia.total_pollos)}</span>
              </div>
              <div className="day-body">
                {dia.lotes.length === 0 ? (
                  <p style={{ textAlign: 'center', color: 'var(--text-light)', padding: '1rem', fontSize: '0.8rem' }}>
                    Sin lotes asignados
                  </p>
                ) : (
                  dia.lotes.map((lote, loteIdx) => (
                    <motion.div
                      key={loteIdx}
                      initial={{ opacity: 0, scale: 0.9 }}
                      animate={{ opacity: 1, scale: 1 }}
                      transition={{ delay: loteIdx * 0.05 }}
                      className={`lote-card${lote.excluido ? ' lote-excluido' : ''}`}
                      style={lote.excluido ? { borderLeft: '3px solid #9ca3af', background: 'rgba(156,163,175,0.06)' } : lote.sobreedad ? { borderLeft: '3px solid #f59e0b', background: 'rgba(245,158,11,0.04)' } : lote.es_compra_terceros ? { borderLeft: '3px solid #7c3aed', background: 'rgba(168,85,247,0.03)' } : undefined}
                    >
                      <div className="lote-header">
                        <span style={lote.excluido ? { textDecoration: 'line-through', opacity: 0.5 } : undefined}>{lote.granja} G{lote.galpon}</span>
                        <div style={{ display: 'flex', gap: 4, alignItems: 'center' }}>
                          {lote.excluido && (
                            <span title={lote.motivo_exclusion || 'Lote excluido de la planificación'} style={{ display: 'inline-flex', alignItems: 'center', gap: 2, padding: '0.1rem 0.4rem', background: 'rgba(156,163,175,0.15)', border: '1px solid rgba(156,163,175,0.3)', borderRadius: 12, fontSize: '0.65rem', color: '#6b7280', fontWeight: 600 }}>
                              <Slash size={10} /> Excluido
                            </span>
                          )}
                          {lote.sobreedad && !lote.excluido && (
                            <span title="Lote sobreedad/sobrepeso — asignado con prioridad" style={{ display: 'inline-flex', alignItems: 'center', gap: 2, padding: '0.1rem 0.4rem', background: 'rgba(245,158,11,0.12)', border: '1px solid rgba(245,158,11,0.3)', borderRadius: 12, fontSize: '0.65rem', color: '#d97706', fontWeight: 600 }}>
                              <AlertTriangle size={10} /> Sobreedad
                            </span>
                          )}
                          {lote.es_compra_terceros && !lote.excluido && (
                            <span style={{ display: 'inline-flex', alignItems: 'center', gap: 2, padding: '0.1rem 0.4rem', background: 'rgba(168,85,247,0.12)', border: '1px solid rgba(168,85,247,0.3)', borderRadius: 12, fontSize: '0.65rem', color: '#7c3aed', fontWeight: 600 }}>
                              <ShoppingCart size={10} /> Terceros
                            </span>
                          )}
                          <span className={`badge badge-${lote.sexo === 'M' ? 'info' : lote.sexo === 'H' ? 'warning' : 'success'}`}>
                            {lote.sexo || '-'}
                          </span>
                        </div>
                      </div>
                      {lote.excluido && lote.motivo_exclusion && (
                        <div className="lote-detail" style={{ color: '#6b7280', fontSize: '0.75rem', fontStyle: 'italic' }}>
                          <span>Motivo: {lote.motivo_exclusion}</span>
                        </div>
                      )}
                      <div className="lote-detail" style={lote.excluido ? { opacity: 0.45, textDecoration: 'line-through' } : undefined}>
                        <span>Pollos: {formatNumber(lote.cantidad)}</span>
                        <span>Edad: {lote.edad_fin_retiro}</span>
                      </div>
                      <div className="lote-detail" style={lote.excluido ? { opacity: 0.45, textDecoration: 'line-through' } : undefined}>
                        <span>Peso: {lote.peso_vivo_retiro?.toFixed(2)} kg</span>
                        <span style={lote.excluido ? {} : { color: `var(--${getEdadColor(lote.diferencia_edad_ideal)})` }}>
                          Dif: {lote.diferencia_edad_ideal > 0 ? '+' : ''}{lote.diferencia_edad_ideal}
                        </span>
                      </div>
                      <div className="lote-detail" style={lote.excluido ? { opacity: 0.45, textDecoration: 'line-through' } : undefined}>
                        <span>Faenado: {lote.peso_faenado?.toFixed(2)}</span>
                        <span>Cajas: {formatNumber(lote.cajas)}</span>
                      </div>
                      {lote.es_compra_terceros && lote.motivo_compra && !lote.excluido && (
                        <div className="lote-detail" style={{ color: '#7c3aed', fontSize: '0.75rem', fontStyle: 'italic' }}>
                          <span>{lote.motivo_compra}</span>
                        </div>
                      )}
                      <div className="lote-actions">
                        {lote.excluido ? (
                          <button
                            className="btn btn-sm btn-outline"
                            style={{ borderColor: '#10b981', color: '#10b981' }}
                            onClick={() => handleExcluir(diaIdx, loteIdx)}
                            title="Restaurar este lote a la planificación"
                          >
                            <Undo2 size={12} style={{ marginRight: 2 }} /> Restaurar
                          </button>
                        ) : (
                          <>
                            <button
                              className="btn btn-sm btn-outline"
                              onClick={() => setMovingLote({ diaIdx, loteIdx, lote })}
                            >
                              <ArrowLeftRight size={12} style={{ marginRight: 2 }} /> Mover
                            </button>
                            <button
                              className="btn btn-sm btn-outline"
                              style={{ borderColor: '#6366f1', color: '#6366f1' }}
                              onClick={() => handleDiferir(diaIdx, loteIdx)}
                              disabled={diferirLoading === `${diaIdx}-${loteIdx}`}
                              title="Diferir este lote a Semana 2"
                            >
                              {diferirLoading === `${diaIdx}-${loteIdx}`
                                ? <Loader2 size={12} style={{ animation: 'spin 1s linear infinite' }} />
                                : <><ArrowRight size={12} style={{ marginRight: 2 }} /> S2</>
                              }
                            </button>
                            <button
                              className="btn btn-sm btn-outline"
                              style={{ borderColor: '#9ca3af', color: '#6b7280' }}
                              onClick={() => setExcluirTarget({ diaIdx, loteIdx })}
                              title="Excluir lote (tachar sin eliminar)"
                            >
                              <Slash size={12} style={{ marginRight: 2 }} /> Tachar
                            </button>
                            <button
                              className="btn btn-sm btn-danger"
                              onClick={() => handleDelete(diaIdx, loteIdx)}
                            >
                              <X size={12} style={{ marginRight: 2 }} /> Eliminar
                            </button>
                          </>
                        )}
                      </div>
                    </motion.div>
                  ))
                )}
              </div>
              <div className="day-summary">
                <span className="label">Peso prom.</span>
                <span className="value">{dia.peso_promedio_ponderado?.toFixed(2)} kg</span>
                <span className="label">Dif. edad prom.</span>
                <span className="value" style={{ color: `var(--${getEdadColor(dia.diferencia_edad_promedio)})` }}>
                  {dia.diferencia_edad_promedio?.toFixed(1)}
                </span>
                <span className="label">Cajas</span>
                <span className="value">{formatNumber(dia.cajas_totales)}</span>
              </div>
            </div>
            )
          })}
        </motion.div>
      )}

      {/* Vista Tabla */}
      {viewMode === 'table' && (
        <motion.div
          initial={{ opacity: 0, scale: 0.98 }}
          animate={{ opacity: 1, scale: 1 }}
          className="card"
        >
          <div className="card-body">
            <div className="table-container" style={{ maxHeight: '600px', overflowY: 'auto' }}>
              <table>
                <thead>
                  <tr>
                    <th>Día</th>
                    <th>Fecha</th>
                    <th>Granja</th>
                    <th>Galpón</th>
                    <th>Núcleo</th>
                    <th className="text-right">Cantidad</th>
                    <th>Sexo</th>
                    <th className="text-right">Edad Fin</th>
                    <th className="text-right">Dif. Edad</th>
                    <th className="text-right">Peso Vivo</th>
                    <th className="text-right">Peso Faenado</th>
                    <th className="text-right">Calibre</th>
                    <th className="text-right">Cajas</th>
                    <th>Acciones</th>
                  </tr>
                </thead>
                <tbody>
                  {dias.map((dia, diaIdx) => (
                    <React.Fragment key={`day-${diaIdx}`}>
                      {dia.lotes.map((lote, loteIdx) => (
                        <tr key={`${diaIdx}-${loteIdx}`} style={lote.excluido ? { background: 'rgba(156,163,175,0.08)', opacity: 0.55 } : lote.sobreedad ? { background: 'rgba(245,158,11,0.06)' } : lote.es_compra_terceros ? { background: 'rgba(168,85,247,0.04)' } : undefined}>
                          {loteIdx === 0 && (
                            <td rowSpan={dia.lotes.length + 1} style={{ verticalAlign: 'top', fontWeight: 600 }}>
                              {getDiaNombre(dia.fecha)}
                            </td>
                          )}
                          <td>{formatDate(dia.fecha)}</td>
                          <td style={lote.excluido ? { textDecoration: 'line-through' } : undefined}>
                            <strong>{lote.granja}</strong>
                            {lote.excluido && (
                              <span title={lote.motivo_exclusion || 'Excluido'} style={{ display: 'inline-flex', alignItems: 'center', gap: 2, marginLeft: 6, padding: '0.1rem 0.4rem', background: 'rgba(156,163,175,0.15)', border: '1px solid rgba(156,163,175,0.3)', borderRadius: 12, fontSize: '0.6rem', color: '#6b7280', fontWeight: 600 }}>
                                <Slash size={9} /> Excluido
                              </span>
                            )}
                            {lote.sobreedad && !lote.excluido && (
                              <span title="Lote sobreedad/sobrepeso — asignado con prioridad" style={{ display: 'inline-flex', alignItems: 'center', gap: 2, marginLeft: 6, padding: '0.1rem 0.4rem', background: 'rgba(245,158,11,0.12)', border: '1px solid rgba(245,158,11,0.3)', borderRadius: 12, fontSize: '0.6rem', color: '#d97706', fontWeight: 600 }}>
                                <AlertTriangle size={9} /> Sobreedad
                              </span>
                            )}
                            {lote.es_compra_terceros && !lote.excluido && (
                              <span style={{ display: 'inline-flex', alignItems: 'center', gap: 2, marginLeft: 6, padding: '0.1rem 0.4rem', background: 'rgba(168,85,247,0.12)', border: '1px solid rgba(168,85,247,0.3)', borderRadius: 12, fontSize: '0.6rem', color: '#7c3aed', fontWeight: 600 }}>
                                <ShoppingCart size={9} /> Terceros
                              </span>
                            )}
                          </td>
                          <td className="text-center" style={lote.excluido ? { textDecoration: 'line-through' } : undefined}>{lote.galpon}</td>
                          <td className="text-center" style={lote.excluido ? { textDecoration: 'line-through' } : undefined}>{lote.nucleo}</td>
                          <td className="text-right" style={lote.excluido ? { textDecoration: 'line-through' } : undefined}>{formatNumber(lote.cantidad)}</td>
                          <td className="text-center">
                            <span className={`badge badge-${lote.sexo === 'M' ? 'info' : lote.sexo === 'H' ? 'warning' : 'success'}`}>
                              {lote.sexo || '-'}
                            </span>
                          </td>
                          <td className="text-right" style={lote.excluido ? { textDecoration: 'line-through' } : undefined}>{lote.edad_fin_retiro}</td>
                          <td className="text-right" style={lote.excluido ? { textDecoration: 'line-through' } : { color: `var(--${getEdadColor(lote.diferencia_edad_ideal)})` }}>
                            {lote.diferencia_edad_ideal > 0 ? '+' : ''}{lote.diferencia_edad_ideal}
                          </td>
                          <td className="text-right" style={lote.excluido ? { textDecoration: 'line-through' } : undefined}>{lote.peso_vivo_retiro?.toFixed(2)}</td>
                          <td className="text-right" style={lote.excluido ? { textDecoration: 'line-through' } : undefined}>{lote.peso_faenado?.toFixed(2)}</td>
                          <td className="text-right" style={lote.excluido ? { textDecoration: 'line-through' } : undefined}>{lote.calibre_promedio?.toFixed(2)}</td>
                          <td className="text-right" style={lote.excluido ? { textDecoration: 'line-through' } : undefined}>{formatNumber(lote.cajas)}</td>
                          <td style={{ display: 'flex', gap: 4 }}>
                            {lote.excluido ? (
                              <button className="btn btn-sm btn-outline" style={{ borderColor: '#10b981', color: '#10b981', fontSize: '0.7rem' }} onClick={() => handleExcluir(diaIdx, loteIdx)} title="Restaurar">
                                <Undo2 size={11} />
                              </button>
                            ) : (
                              <>
                                <button className="btn btn-sm btn-outline" style={{ borderColor: '#9ca3af', color: '#6b7280', fontSize: '0.7rem' }} onClick={() => setExcluirTarget({ diaIdx, loteIdx })} title="Tachar">
                                  <Slash size={11} />
                                </button>
                                <button className="btn btn-sm btn-danger" onClick={() => handleDelete(diaIdx, loteIdx)}>✕</button>
                              </>
                            )}
                          </td>
                        </tr>
                      ))}
                      <tr className="row-subtotal" key={`sub-${diaIdx}`}>
                        <td colSpan={4}><strong>Subtotal {getDiaNombre(dia.fecha)}</strong></td>
                        <td className="text-right"><strong>{formatNumber(dia.total_pollos)}</strong></td>
                        <td></td>
                        <td></td>
                        <td className="text-right" style={{ color: `var(--${getEdadColor(dia.diferencia_edad_promedio)})` }}>
                          {dia.diferencia_edad_promedio?.toFixed(1)}
                        </td>
                        <td className="text-right">{dia.peso_promedio_ponderado?.toFixed(2)}</td>
                        <td></td>
                        <td className="text-right">{dia.calibre_promedio_ponderado?.toFixed(2)}</td>
                        <td className="text-right">{formatNumber(dia.cajas_totales)}</td>
                        <td></td>
                      </tr>
                    </React.Fragment>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        </motion.div>
      )}

      {/* ═══ Semana 2 — Planificación Tentativa ═══ */}
      <motion.div variants={itemVariants} className="card" style={{ borderLeft: '4px solid #6366f1', marginTop: '1.5rem' }}>
        <div
          className="card-header"
          style={{ cursor: 'pointer', userSelect: 'none', background: 'rgba(99, 102, 241, 0.04)' }}
          onClick={() => { setSemana2Open(!semana2Open); if (!semana2Open && !semana2Data) cargarSemana2() }}
        >
          <h2 style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
            <Clock size={18} color="#6366f1" />
            Semana 2 — Planificación Tentativa
            <span style={{
              padding: '0.15rem 0.5rem',
              background: 'rgba(99, 102, 241, 0.12)',
              border: '1px solid rgba(99, 102, 241, 0.3)',
              borderRadius: 12,
              fontSize: '0.7rem',
              color: '#6366f1',
              fontWeight: 600,
            }}>
              TENTATIVA
            </span>
            {semana2Data?.total_diferidos > 0 && (
              <span style={{
                padding: '0.15rem 0.5rem',
                background: 'rgba(99, 102, 241, 0.08)',
                borderRadius: 12,
                fontSize: '0.72rem',
                color: '#6366f1',
              }}>
                {semana2Data.total_diferidos} lote{semana2Data.total_diferidos > 1 ? 's' : ''} diferido{semana2Data.total_diferidos > 1 ? 's' : ''}
              </span>
            )}
            {semana2Data?.lotes_recuperados_fuera_rango_s1 > 0 && (
              <span style={{
                padding: '0.15rem 0.5rem',
                background: 'rgba(14, 165, 233, 0.08)',
                borderRadius: 12,
                fontSize: '0.72rem',
                color: '#0369a1',
              }}>
                {semana2Data.lotes_recuperados_fuera_rango_s1} lote{semana2Data.lotes_recuperados_fuera_rango_s1 > 1 ? 's' : ''} recuperado{semana2Data.lotes_recuperados_fuera_rango_s1 > 1 ? 's' : ''} de S1
              </span>
            )}
          </h2>
          <span style={{ fontSize: '0.85rem', color: 'var(--text-light)' }}>
            {semana2Open ? '▲ Cerrar' : '▼ Abrir'}
          </span>
        </div>
        <AnimatePresence>
          {semana2Open && (
            <motion.div
              initial={{ height: 0, opacity: 0 }}
              animate={{ height: 'auto', opacity: 1 }}
              exit={{ height: 0, opacity: 0 }}
              style={{ overflow: 'hidden' }}
            >
              <div className="card-body">
                {semana2Loading ? (
                  <div style={{ textAlign: 'center', padding: '2rem' }}>
                    <Loader2 size={24} style={{ animation: 'spin 1s linear infinite', color: '#6366f1' }} />
                    <p style={{ marginTop: '0.5rem', color: 'var(--text-light)', fontSize: '0.9rem' }}>Generando planificación tentativa...</p>
                  </div>
                ) : !semana2Data?.tiene_datos ? (
                  <div style={{ textAlign: 'center', padding: '2rem' }}>
                    <p style={{ color: 'var(--text-light)', fontSize: '0.9rem' }}>
                      No hay lotes diferidos, no asignados ni fuera de rango recuperables para proyectar en Semana 2.
                    </p>
                    <p style={{ color: 'var(--text-light)', fontSize: '0.82rem', marginTop: '0.5rem' }}>
                      Use el botón <strong style={{ color: '#6366f1' }}>S2</strong> en cualquier lote para diferirlo a la semana siguiente. Los lotes jóvenes fuera de rango se reconsideran automáticamente si entran en S2.
                    </p>
                  </div>
                ) : (() => {
                  const s2 = semana2Data.proyeccion
                  const diferidos = semana2Data.lotes_diferidos || []
                  return (
                    <>
                      {/* Info banner */}
                      <div style={{
                        padding: '0.7rem 1rem',
                        background: 'rgba(99, 102, 241, 0.06)',
                        border: '1px solid rgba(99, 102, 241, 0.2)',
                        borderRadius: 8,
                        marginBottom: '1rem',
                        fontSize: '0.85rem',
                        color: '#4f46e5',
                        display: 'flex',
                        alignItems: 'center',
                        justifyContent: 'space-between',
                        flexWrap: 'wrap',
                        gap: 8,
                      }}>
                        <span>
                          Planificación indicativa para la semana del <strong>{formatDate(s2.fecha_inicio)}</strong> al <strong>{formatDate(s2.fecha_fin)}</strong>.
                          {semana2Data.lotes_no_asignados_s1 > 0 && (
                            <> Incluye {semana2Data.lotes_no_asignados_s1} lote{semana2Data.lotes_no_asignados_s1 > 1 ? 's' : ''} no asignados de S1.</>
                          )}
                          {semana2Data.lotes_recuperados_fuera_rango_s1 > 0 && (
                            <> Reconsidera {semana2Data.lotes_recuperados_fuera_rango_s1} lote{semana2Data.lotes_recuperados_fuera_rango_s1 > 1 ? 's' : ''} joven{semana2Data.lotes_recuperados_fuera_rango_s1 > 1 ? 'es' : ''} que quedó fuera de rango en S1.</>
                          )}
                        </span>
                        <div style={{ display: 'flex', gap: 6 }}>
                          <button
                            className="btn btn-sm btn-outline"
                            style={{ borderColor: '#6366f1', color: '#6366f1', fontSize: '0.78rem' }}
                            onClick={cargarSemana2}
                            disabled={semana2Loading}
                          >
                            <RefreshCw size={12} /> Actualizar
                          </button>
                          {diferidos.length > 0 && (
                            <button
                              className="btn btn-sm btn-outline"
                              style={{ borderColor: '#ef4444', color: '#ef4444', fontSize: '0.78rem' }}
                              onClick={handleLimpiarDiferidos}
                            >
                              <X size={12} /> Limpiar diferidos
                            </button>
                          )}
                        </div>
                      </div>

                      {/* KPIs Semana 2 */}
                      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(160px, 1fr))', gap: '0.75rem', marginBottom: '1rem' }}>
                        <div className="stat-card" style={{ borderLeft: '3px solid #6366f1' }}>
                          <div className="stat-label">Total Pollos S2</div>
                          <div className="stat-value" style={{ color: '#6366f1' }}>{formatNumber(s2.total_pollos_semana)}</div>
                        </div>
                        <div className="stat-card" style={{ borderLeft: '3px solid #6366f1' }}>
                          <div className="stat-label">Prom. Edad S2</div>
                          <div className="stat-value" style={{ color: '#6366f1' }}>{s2.promedio_edad_semana?.toFixed(1)}</div>
                        </div>
                        <div className="stat-card" style={{ borderLeft: '3px solid #6366f1' }}>
                          <div className="stat-label">Cajas S2</div>
                          <div className="stat-value" style={{ color: '#6366f1' }}>{formatNumber(s2.produccion_cajas_semanales)}</div>
                        </div>
                        <div className="stat-card" style={{ borderLeft: '3px solid #6366f1' }}>
                          <div className="stat-label">Días de Faena</div>
                          <div className="stat-value" style={{ color: '#6366f1' }}>{s2.dias?.length || 0}</div>
                        </div>
                        <div className="stat-card" style={{ borderLeft: '3px solid #0ea5e9' }}>
                          <div className="stat-label">Recuperados de S1</div>
                          <div className="stat-value" style={{ color: '#0369a1' }}>{formatNumber(semana2Data.pollos_recuperados_fuera_rango_s1 || 0)}</div>
                        </div>
                      </div>

                      {/* Lotes diferidos — con botón restaurar */}
                      {diferidos.length > 0 && (
                        <div style={{ marginBottom: '1rem' }}>
                          <h3 style={{ fontSize: '0.9rem', fontWeight: 600, color: '#6366f1', marginBottom: '0.5rem', display: 'flex', alignItems: 'center', gap: 6 }}>
                            <ArrowRight size={14} /> Lotes diferidos de Semana 1
                          </h3>
                          <div className="table-container" style={{ maxHeight: 200, overflowY: 'auto' }}>
                            <table>
                              <thead>
                                <tr>
                                  <th>Granja</th>
                                  <th>Galpón</th>
                                  <th>Núcleo</th>
                                  <th className="text-right">Cantidad</th>
                                  <th>Sexo</th>
                                  <th>Origen S1</th>
                                  <th>Motivo</th>
                                  <th>Acción</th>
                                </tr>
                              </thead>
                              <tbody>
                                {diferidos.map((d, idx) => (
                                  <tr key={idx}>
                                    <td><strong>{d.granja}</strong></td>
                                    <td className="text-center">{d.galpon}</td>
                                    <td className="text-center">{d.nucleo}</td>
                                    <td className="text-right">{formatNumber(d.cantidad)}</td>
                                    <td className="text-center">{d.sexo}</td>
                                    <td>{getDiaNombre(d.dia_origen_fecha)}</td>
                                    <td style={{ fontSize: '0.8rem', color: 'var(--text-light)' }}>{d.motivo || '-'}</td>
                                    <td>
                                      <button
                                        className="btn btn-sm btn-outline"
                                        style={{ fontSize: '0.7rem', padding: '0.15rem 0.4rem', borderColor: '#6366f1', color: '#6366f1' }}
                                        onClick={() => handleRestaurar(idx)}
                                        title="Restaurar este lote a Semana 1"
                                      >
                                        <Undo2 size={11} style={{ marginRight: 2 }} /> Restaurar
                                      </button>
                                    </td>
                                  </tr>
                                ))}
                              </tbody>
                            </table>
                          </div>
                        </div>
                      )}

                      {/* Grilla de días Semana 2 (solo lectura) */}
                      {s2.dias && s2.dias.length > 0 && (
                        <div className="proyeccion-grid">
                          {s2.dias.map((dia, diaIdx) => (
                            <div className="day-column" key={diaIdx} style={{ borderColor: '#6366f180' }}>
                              <div className="day-header" style={{ background: 'rgba(99, 102, 241, 0.06)', color: '#4338ca', borderBottomColor: '#818cf8' }}>
                                <div style={{ display: 'flex', flexDirection: 'column', gap: 2 }}>
                                  <span>{getDiaNombre(dia.fecha)}</span>
                                  <span style={{ fontSize: '0.7rem', color: '#6366f1' }}>S2</span>
                                </div>
                                <span className="day-total" style={{ color: '#6366f1' }}>{formatNumber(dia.total_pollos)}</span>
                              </div>
                              <div className="day-body">
                                {dia.lotes.length === 0 ? (
                                  <p style={{ textAlign: 'center', color: 'var(--text-light)', padding: '0.75rem', fontSize: '0.78rem' }}>
                                    Sin lotes
                                  </p>
                                ) : (
                                  dia.lotes.map((lote, loteIdx) => (
                                    <div
                                      key={loteIdx}
                                      className="lote-card"
                                      style={{ borderLeft: '3px solid #6366f1', background: 'rgba(99, 102, 241, 0.02)' }}
                                    >
                                      <div className="lote-header">
                                        <span>{lote.granja} G{lote.galpon}</span>
                                        <div style={{ display: 'flex', gap: 4, alignItems: 'center' }}>
                                          {lote.sobreedad && (
                                            <span title="Lote sobreedad/sobrepeso" style={{ display: 'inline-flex', alignItems: 'center', gap: 2, padding: '0.1rem 0.4rem', background: 'rgba(245,158,11,0.12)', border: '1px solid rgba(245,158,11,0.3)', borderRadius: 12, fontSize: '0.65rem', color: '#d97706', fontWeight: 600 }}>
                                              <AlertTriangle size={10} /> Sobreedad
                                            </span>
                                          )}
                                          <span className={`badge badge-${lote.sexo === 'M' ? 'info' : lote.sexo === 'H' ? 'warning' : 'success'}`}>
                                            {lote.sexo || '-'}
                                          </span>
                                        </div>
                                      </div>
                                      <div className="lote-detail">
                                        <span>Pollos: {formatNumber(lote.cantidad)}</span>
                                        <span>Edad: {lote.edad_fin_retiro}</span>
                                      </div>
                                      <div className="lote-detail">
                                        <span>Peso: {lote.peso_vivo_retiro?.toFixed(2)} kg</span>
                                        <span>Cajas: {formatNumber(lote.cajas)}</span>
                                      </div>
                                      <div className="lote-detail">
                                        <span>Faenado: {lote.peso_faenado?.toFixed(2)}</span>
                                        <span style={{ color: `var(--${getEdadColor(lote.diferencia_edad_ideal)})` }}>
                                          Dif: {lote.diferencia_edad_ideal > 0 ? '+' : ''}{lote.diferencia_edad_ideal}
                                        </span>
                                      </div>
                                      <div className="lote-actions">
                                        <button
                                          className="btn btn-sm btn-outline"
                                          onClick={() => setMovingLoteS2({ diaIdx, loteIdx, lote })}
                                          disabled={s2ActionLoading}
                                        >
                                          <ArrowLeftRight size={12} style={{ marginRight: 2 }} /> Mover
                                        </button>
                                        <button
                                          className="btn btn-sm btn-outline"
                                          style={{ borderColor: '#10b981', color: '#10b981' }}
                                          onClick={() => setSendingToS1({ diaIdx, loteIdx, lote })}
                                          disabled={s2ActionLoading}
                                          title="Enviar este lote a Semana 1"
                                        >
                                          <Undo2 size={12} style={{ marginRight: 2 }} /> S1
                                        </button>
                                        <button
                                          className="btn btn-sm btn-danger"
                                          onClick={() => handleDeleteS2(diaIdx, loteIdx)}
                                          disabled={s2ActionLoading}
                                        >
                                          <X size={12} style={{ marginRight: 2 }} /> Eliminar
                                        </button>
                                      </div>
                                    </div>
                                  ))
                                )}
                              </div>
                              <div className="day-summary">
                                <span className="label">Peso prom.</span>
                                <span className="value">{dia.peso_promedio_ponderado?.toFixed(2)} kg</span>
                                <span className="label">Dif. edad prom.</span>
                                <span className="value" style={{ color: `var(--${getEdadColor(dia.diferencia_edad_promedio)})` }}>
                                  {dia.diferencia_edad_promedio?.toFixed(1)}
                                </span>
                                <span className="label">Cajas</span>
                                <span className="value">{formatNumber(dia.cajas_totales)}</span>
                              </div>
                            </div>
                          ))}
                        </div>
                      )}

                      {/* Modal de mover lote en S2 */}
                      <AnimatePresence>
                        {movingLoteS2 && (
                          <motion.div
                            initial={{ opacity: 0 }}
                            animate={{ opacity: 1 }}
                            exit={{ opacity: 0 }}
                            className="modal-overlay"
                            onClick={() => setMovingLoteS2(null)}
                          >
                            <motion.div
                              initial={{ scale: 0.9, y: 20 }}
                              animate={{ scale: 1, y: 0 }}
                              exit={{ scale: 0.9, y: 20 }}
                              className="modal"
                              onClick={e => e.stopPropagation()}
                            >
                              <div className="modal-header">
                                <h3><ArrowLeftRight size={18} style={{ verticalAlign: 'middle', marginRight: 6 }} /> Mover lote en Semana 2</h3>
                                <button className="btn btn-sm btn-outline" onClick={() => setMovingLoteS2(null)}>
                                  <X size={16} />
                                </button>
                              </div>
                              <div className="modal-body">
                                <p style={{ marginBottom: '1rem', fontSize: '0.9rem' }}>
                                  Mover <strong>{movingLoteS2.lote.granja} G{movingLoteS2.lote.galpon}</strong> ({formatNumber(movingLoteS2.lote.cantidad)} pollos) desde {getDiaNombre(s2.dias[movingLoteS2.diaIdx]?.fecha)}:
                                </p>
                                <div style={{ display: 'flex', flexDirection: 'column', gap: '0.5rem' }}>
                                  {s2.dias.map((d, idx) => (
                                    idx !== movingLoteS2.diaIdx && (
                                      <button
                                        key={idx}
                                        className="btn btn-outline"
                                        onClick={() => handleMoveS2(movingLoteS2.diaIdx, movingLoteS2.loteIdx, idx)}
                                        disabled={s2ActionLoading}
                                        style={{ justifyContent: 'flex-start' }}
                                      >
                                        <Calendar size={16} style={{ marginRight: 6 }} /> {getDiaNombre(d.fecha)} ({formatDate(d.fecha)}) — {formatNumber(d.total_pollos)} pollos
                                      </button>
                                    )
                                  ))}
                                </div>
                              </div>
                            </motion.div>
                          </motion.div>
                        )}
                      </AnimatePresence>

                      {/* Modal de enviar lote de S2 a S1 */}
                      <AnimatePresence>
                        {sendingToS1 && (
                          <motion.div
                            initial={{ opacity: 0 }}
                            animate={{ opacity: 1 }}
                            exit={{ opacity: 0 }}
                            className="modal-overlay"
                            onClick={() => setSendingToS1(null)}
                          >
                            <motion.div
                              initial={{ scale: 0.9, y: 20 }}
                              animate={{ scale: 1, y: 0 }}
                              exit={{ scale: 0.9, y: 20 }}
                              className="modal"
                              onClick={e => e.stopPropagation()}
                            >
                              <div className="modal-header">
                                <h3><Undo2 size={18} style={{ verticalAlign: 'middle', marginRight: 6 }} /> Enviar lote a Semana 1</h3>
                                <button className="btn btn-sm btn-outline" onClick={() => setSendingToS1(null)}>
                                  <X size={16} />
                                </button>
                              </div>
                              <div className="modal-body">
                                <p style={{ marginBottom: '1rem', fontSize: '0.9rem' }}>
                                  Enviar <strong>{sendingToS1.lote.granja} G{sendingToS1.lote.galpon}</strong> ({formatNumber(sendingToS1.lote.cantidad)} pollos) a Semana 1. Elegir día destino:
                                </p>
                                <div style={{ display: 'flex', flexDirection: 'column', gap: '0.5rem' }}>
                                  <button
                                    className="btn btn-outline"
                                    onClick={() => handleEnviarAS1(sendingToS1.diaIdx, sendingToS1.loteIdx, null)}
                                    disabled={s2ActionLoading}
                                    style={{ justifyContent: 'flex-start', borderColor: '#10b981', color: '#10b981' }}
                                  >
                                    <CheckCircle2 size={16} style={{ marginRight: 6 }} /> Auto-asignar al día con mayor déficit
                                  </button>
                                  {dias.map((d, idx) => (
                                    <button
                                      key={idx}
                                      className="btn btn-outline"
                                      onClick={() => handleEnviarAS1(sendingToS1.diaIdx, sendingToS1.loteIdx, idx)}
                                      disabled={s2ActionLoading}
                                      style={{ justifyContent: 'flex-start' }}
                                    >
                                      <Calendar size={16} style={{ marginRight: 6 }} /> {getDiaNombre(d.fecha)} ({formatDate(d.fecha)}) — {formatNumber(d.total_pollos)} pollos
                                    </button>
                                  ))}
                                </div>
                              </div>
                            </motion.div>
                          </motion.div>
                        )}
                      </AnimatePresence>

                      {/* Lotes fuera de rango en S2 */}
                      {s2.lotes_fuera_rango?.length > 0 && (
                        <div style={{ marginTop: '0.75rem', padding: '0.6rem 0.8rem', background: 'rgba(239, 68, 68, 0.06)', border: '1px solid rgba(239, 68, 68, 0.2)', borderRadius: 8, fontSize: '0.82rem' }}>
                          <strong style={{ color: '#ef4444' }}>{s2.lotes_fuera_rango.length} lotes fuera de rango en S2</strong>
                          <span style={{ color: 'var(--text-light)', marginLeft: 8 }}>
                            ({formatNumber(s2.total_pollos_fuera_rango)} pollos) — No alcanzan edad/peso para la semana 2.
                          </span>
                        </div>
                      )}
                    </>
                  )
                })()}
              </div>
            </motion.div>
          )}
        </AnimatePresence>
      </motion.div>

      {/* Modal Excluir - motivo */}
      <AnimatePresence>
        {excluirTarget && (
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            className="modal-overlay"
            onClick={() => { setExcluirTarget(null); setExcluirMotivo('') }}
          >
            <motion.div
              initial={{ scale: 0.9, y: 20 }}
              animate={{ scale: 1, y: 0 }}
              exit={{ scale: 0.9, y: 20 }}
              className="modal"
              style={{ maxWidth: 440 }}
              onClick={e => e.stopPropagation()}
            >
              <div className="modal-header" style={{ background: 'rgba(156,163,175,0.08)' }}>
                <h3 style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
                  <Slash size={18} style={{ color: '#6b7280' }} /> Excluir lote de la planificación
                </h3>
                <button className="btn btn-sm btn-outline" onClick={() => { setExcluirTarget(null); setExcluirMotivo('') }}>
                  <X size={16} />
                </button>
              </div>
              <div className="modal-body">
                <p style={{ marginBottom: '0.75rem', fontSize: '0.9rem', color: 'var(--text-light)' }}>
                  Este lote quedará tachado y no computará en la capacidad ni producción del día. Puede restaurarlo en cualquier momento.
                </p>
                <label style={{ fontWeight: 600, fontSize: '0.85rem', marginBottom: 4, display: 'block' }}>Motivo (opcional)</label>
                <select
                  value={excluirMotivo}
                  onChange={e => setExcluirMotivo(e.target.value)}
                  style={{ width: '100%', padding: '0.5rem', borderRadius: 8, border: '1px solid var(--border)', marginBottom: '0.5rem', fontSize: '0.85rem' }}
                >
                  <option value="">— Seleccionar motivo —</option>
                  <option value="Faenado anticipadamente (viernes)">Faenado anticipadamente (viernes)</option>
                  <option value="Decisión comercial">Decisión comercial</option>
                  <option value="Problema sanitario">Problema sanitario</option>
                  <option value="Peso insuficiente">Peso insuficiente</option>
                  <option value="Diferido a otra semana">Diferido a otra semana</option>
                </select>
                <input
                  type="text"
                  placeholder="O escribir motivo personalizado..."
                  value={excluirMotivo}
                  onChange={e => setExcluirMotivo(e.target.value)}
                  style={{ width: '100%', padding: '0.5rem', borderRadius: 8, border: '1px solid var(--border)', fontSize: '0.85rem' }}
                />
              </div>
              <div className="modal-footer">
                <button className="btn btn-outline" onClick={() => { setExcluirTarget(null); setExcluirMotivo('') }}>
                  Cancelar
                </button>
                <button
                  className="btn"
                  style={{ background: '#6b7280', color: 'white' }}
                  onClick={() => handleExcluir(excluirTarget.diaIdx, excluirTarget.loteIdx, excluirMotivo)}
                  disabled={loading}
                >
                  {loading
                    ? <><Loader2 size={14} style={{ animation: 'spin 1s linear infinite', marginRight: 4 }} /> Procesando...</>
                    : <><Slash size={14} style={{ marginRight: 4 }} /> Confirmar Exclusión</>
                  }
                </button>
              </div>
            </motion.div>
          </motion.div>
        )}
      </AnimatePresence>

      {/* Modal Lotes Disponibles */}
      <AnimatePresence>
        {disponiblesModal && (
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            className="modal-overlay"
            onClick={() => setDisponiblesModal(false)}
          >
            <motion.div
              initial={{ scale: 0.9, y: 20 }}
              animate={{ scale: 1, y: 0 }}
              exit={{ scale: 0.9, y: 20 }}
              className="modal"
              style={{ maxWidth: 800 }}
              onClick={e => e.stopPropagation()}
            >
              <div className="modal-header" style={{ background: 'rgba(5,150,105,0.06)' }}>
                <h3 style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
                  <PackageOpen size={18} style={{ color: '#059669' }} /> Lotes disponibles para incluir
                </h3>
                <button className="btn btn-sm btn-outline" onClick={() => setDisponiblesModal(false)}>
                  <X size={16} />
                </button>
              </div>
              <div className="modal-body">
                {disponibles.length === 0 ? (
                  <p style={{ textAlign: 'center', color: 'var(--text-light)', padding: '2rem' }}>
                    No hay lotes disponibles para incluir. Todos los lotes están asignados activamente.
                  </p>
                ) : (
                  <>
                    <p style={{ marginBottom: '0.75rem', fontSize: '0.9rem', color: 'var(--text-light)' }}>
                      {disponibles.length} lotes disponibles ({formatNumber(disponibles.reduce((s, l) => s + l.cantidad, 0))} pollos). Seleccione el día destino y haga click en "Incluir".
                    </p>
                    <div style={{ marginBottom: '0.75rem' }}>
                      <label style={{ fontWeight: 600, fontSize: '0.85rem', marginRight: 8 }}>Día destino:</label>
                      <select
                        value={incluirDiaDestino}
                        onChange={e => setIncluirDiaDestino(Number(e.target.value))}
                        style={{ padding: '0.4rem 0.6rem', borderRadius: 8, border: '1px solid var(--border)', fontSize: '0.85rem' }}
                      >
                        {dias.map((dia, idx) => (
                          <option key={idx} value={idx}>{getDiaNombre(dia.fecha)} {formatDate(dia.fecha)} ({formatNumber(dia.total_pollos)} pollos)</option>
                        ))}
                      </select>
                    </div>
                    <div className="table-container" style={{ maxHeight: '400px', overflowY: 'auto' }}>
                      <table>
                        <thead>
                          <tr>
                            <th>Origen</th>
                            <th>Granja</th>
                            <th>Galpón</th>
                            <th>Núcleo</th>
                            <th className="text-right">Cantidad</th>
                            <th>Sexo</th>
                            <th>Detalle</th>
                            <th>Acción</th>
                          </tr>
                        </thead>
                        <tbody>
                          {disponibles.map((lote, idx) => (
                            <tr key={idx}>
                              <td>
                                <span style={{
                                  display: 'inline-flex', alignItems: 'center', gap: 3, padding: '0.15rem 0.5rem',
                                  borderRadius: 12, fontSize: '0.7rem', fontWeight: 600,
                                  background: lote.origen === 'excluido' ? 'rgba(156,163,175,0.12)' : 'rgba(245,158,11,0.12)',
                                  color: lote.origen === 'excluido' ? '#6b7280' : '#d97706',
                                }}>
                                  {lote.origen === 'excluido' ? <><Slash size={10} /> Excluido</> : <><AlertTriangle size={10} /> Sin asignar</>}
                                </span>
                              </td>
                              <td><strong>{lote.granja}</strong></td>
                              <td className="text-center">{lote.galpon}</td>
                              <td className="text-center">{lote.nucleo}</td>
                              <td className="text-right">{formatNumber(lote.cantidad)}</td>
                              <td className="text-center">
                                <span className={`badge badge-${lote.sexo === 'M' ? 'info' : lote.sexo === 'H' ? 'warning' : 'success'}`}>
                                  {lote.sexo || '-'}
                                </span>
                              </td>
                              <td style={{ fontSize: '0.78rem', color: 'var(--text-light)' }}>
                                {lote.origen === 'excluido'
                                  ? (lote.motivo_exclusion || `Día ${formatDate(lote.fecha_dia)}`)
                                  : (lote.motivo || formatDiasElegibles(lote.dias_elegibles))
                                }
                              </td>
                              <td>
                                <button
                                  className="btn btn-sm"
                                  style={{ background: '#059669', color: 'white', fontSize: '0.75rem' }}
                                  onClick={() => handleIncluirLote(lote)}
                                  disabled={loading || incluyendoLote === lote}
                                >
                                  {incluyendoLote === lote
                                    ? <Loader2 size={12} style={{ animation: 'spin 1s linear infinite' }} />
                                    : <><PlusCircle size={12} style={{ marginRight: 3 }} /> Incluir</>
                                  }
                                </button>
                              </td>
                            </tr>
                          ))}
                        </tbody>
                      </table>
                    </div>
                  </>
                )}
              </div>
              <div className="modal-footer">
                <button className="btn btn-outline" onClick={() => setDisponiblesModal(false)}>Cerrar</button>
              </div>
            </motion.div>
          </motion.div>
        )}
      </AnimatePresence>

    </motion.div>
  )
}
