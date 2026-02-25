import { useState } from 'react'
import { motion } from 'framer-motion'
import { BarChart2, Activity, Home, List, AlertCircle } from 'lucide-react'
import { generarProyeccion } from '../services/api'

const DIAS_SEMANA = ['Lunes', 'Martes', 'Miércoles', 'Jueves', 'Viernes', 'Sábado']

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

export default function OfertaTable({ oferta, onGenerarProyeccion }) {
  const [fechaInicio, setFechaInicio] = useState('')
  const [pollosPorDia, setPollosPorDia] = useState(30000)
  const [diasFaena, setDiasFaena] = useState(6)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState(null)

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
      })
      onGenerarProyeccion(data)
    } catch (err) {
      setError(err.response?.data?.detail || 'Error al generar proyección')
    } finally {
      setLoading(false)
    }
  }

  // Resumen por granja
  const granjas = oferta.granjas || {}

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

      {/* Generar proyección */}
      <motion.div variants={itemVariants} className="card">
        <div className="card-header">
          <h2><Activity size={18} style={{ verticalAlign: 'middle', marginRight: 6 }} /> Generar Proyección de Faena</h2>
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
              <label>Días de Faena</label>
              <select
                className="form-control"
                value={diasFaena}
                onChange={(e) => setDiasFaena(parseInt(e.target.value))}
              >
                {[5, 6].map(d => <option key={d} value={d}>{d} días ({DIAS_SEMANA.slice(0, d).join(', ')})</option>)}
              </select>
            </div>
          </div>

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

          <button className="btn btn-primary" onClick={handleGenerar} disabled={loading}>
            {loading ? (
              <><span className="spinner" style={{ width: 16, height: 16, marginRight: 6 }}></span> Generando...</>
            ) : (
              <><BarChart2 size={16} /> Generar Proyección Automática</>
            )}
          </button>
        </div>
      </motion.div>

      {/* Resumen por granja */}
      <motion.div variants={itemVariants} className="card">
        <div className="card-header">
          <h2><Home size={18} style={{ verticalAlign: 'middle', marginRight: 6 }} /> Resumen por Granja</h2>
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
          <h2><List size={18} style={{ verticalAlign: 'middle', marginRight: 6 }} /> Oferta Completa ({oferta.ofertas.length} lotes)</h2>
        </div>
        <div className="card-body">
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
                </tr>
              </thead>
              <tbody>
                {oferta.ofertas.map((o, i) => (
                  <tr key={i}>
                    <td>{i + 1}</td>
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
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      </motion.div>
    </motion.div>
  )
}
