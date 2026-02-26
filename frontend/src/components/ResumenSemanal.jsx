import { motion } from 'framer-motion'
import { TrendingUp, Calendar, Home, Download, PieChart } from 'lucide-react'
import { exportResumenPDF } from '../utils/pdfExport'

function formatNumber(n) {
  if (n == null) return '-'
  return n.toLocaleString('es-AR')
}

const DIAS_SEMANA = ['Lunes', 'Martes', 'Miércoles', 'Jueves', 'Viernes', 'Sábado']

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

export default function ResumenSemanal({ proyeccion }) {
  if (!proyeccion || !proyeccion.dias) {
    return (
      <motion.div
        initial={{ opacity: 0, scale: 0.95 }}
        animate={{ opacity: 1, scale: 1 }}
        className="card"
      >
        <div className="card-body" style={{ textAlign: 'center', padding: '3rem' }}>
          <p style={{ fontSize: '1.1rem', color: 'var(--text-light)', display: 'flex', alignItems: 'center', justifyContent: 'center', gap: 6 }}>
            <TrendingUp size={20} /> No hay proyección generada aún.
          </p>
        </div>
      </motion.div>
    )
  }

  const { dias } = proyeccion

  // Calcular datos por granja
  const porGranja = {}
  dias.forEach((dia, diaIdx) => {
    dia.lotes.forEach(lote => {
      if (!porGranja[lote.granja]) {
        porGranja[lote.granja] = {
          dias: new Array(dias.length).fill(0),
          total: 0,
          cajas: 0,
        }
      }
      porGranja[lote.granja].dias[diaIdx] += lote.cantidad
      porGranja[lote.granja].total += lote.cantidad
      porGranja[lote.granja].cajas += lote.cajas
    })
  })

  return (
    <motion.div
      variants={containerVariants}
      initial="hidden"
      animate="show"
    >
      {/* Stats principales */}
      <motion.div variants={itemVariants} className="stats-grid">
        <div className="stat-card">
          <div className="stat-label">Total Pollos Semana</div>
          <div className="stat-value green">{formatNumber(proyeccion.total_pollos_semana)}</div>
        </div>
        <div className="stat-card">
          <div className="stat-label">Sofía</div>
          <div className="stat-value blue">{formatNumber(proyeccion.sofia)}</div>
        </div>
        <div className="stat-card">
          <div className="stat-label">Promedio Edad</div>
          <div className="stat-value orange">{proyeccion.promedio_edad_semana?.toFixed(1)} días</div>
        </div>
        <div className="stat-card">
          <div className="stat-label">Cajas Semanales</div>
          <div className="stat-value">{formatNumber(proyeccion.produccion_cajas_semanales)}</div>
        </div>
      </motion.div>

      {/* Tabla resumen diario */}
      <motion.div variants={itemVariants} className="card">
        <div className="card-header">
          <h2><Calendar size={18} style={{ verticalAlign: 'middle', marginRight: 6 }} /> Resumen Diario</h2>
          <button className="btn btn-sm btn-outline" onClick={() => exportResumenPDF(proyeccion)}>
            <Download size={14} /> Descargar PDF
          </button>
        </div>
        <div className="card-body">
          <div className="table-container">
            <table>
              <thead>
                <tr>
                  <th>Día</th>
                  <th>Fecha</th>
                  <th className="text-right">Pollos</th>
                  <th className="text-right">Lotes</th>
                  <th className="text-right">Peso Prom.</th>
                  <th className="text-right">Dif. Edad Prom.</th>
                  <th className="text-right">Calibre Prom.</th>
                  <th className="text-right">Cajas</th>
                </tr>
              </thead>
              <tbody>
                {dias.map((dia, idx) => (
                  <tr key={idx} style={{ transition: 'background-color 0.2s' }}>
                    <td><strong>{DIAS_SEMANA[idx]}</strong></td>
                    <td>{dia.fecha}</td>
                    <td className="text-right">{formatNumber(dia.total_pollos)}</td>
                    <td className="text-right">{dia.lotes.filter(l => l.cantidad > 0).length}</td>
                    <td className="text-right">{dia.peso_promedio_ponderado?.toFixed(2)} kg</td>
                    <td className="text-right">{dia.diferencia_edad_promedio?.toFixed(1)}</td>
                    <td className="text-right">{dia.calibre_promedio_ponderado?.toFixed(2)}</td>
                    <td className="text-right">{formatNumber(dia.cajas_totales)}</td>
                  </tr>
                ))}
                <tr className="row-subtotal">
                  <td colSpan={2}><strong>TOTAL SEMANA</strong></td>
                  <td className="text-right"><strong>{formatNumber(proyeccion.total_pollos_semana)}</strong></td>
                  <td className="text-right">
                    <strong>{dias.reduce((sum, d) => sum + d.lotes.filter(l => l.cantidad > 0).length, 0)}</strong>
                  </td>
                  <td colSpan={2}></td>
                  <td></td>
                  <td className="text-right"><strong>{formatNumber(proyeccion.produccion_cajas_semanales)}</strong></td>
                </tr>
              </tbody>
            </table>
          </div>
        </div>
      </motion.div>

      {/* Tabla resumen por granja */}
      <motion.div variants={itemVariants} className="card">
        <div className="card-header">
          <h2><Home size={18} style={{ verticalAlign: 'middle', marginRight: 6 }} /> Distribución por Granja</h2>
        </div>
        <div className="card-body">
          <div className="table-container">
            <table>
              <thead>
                <tr>
                  <th>Granja</th>
                  {dias.map((_, idx) => (
                    <th key={idx} className="text-right">{DIAS_SEMANA[idx]}</th>
                  ))}
                  <th className="text-right">Total</th>
                  <th className="text-right">Cajas</th>
                </tr>
              </thead>
              <tbody>
                {Object.entries(porGranja)
                  .sort((a, b) => b[1].total - a[1].total)
                  .map(([granja, info]) => (
                    <tr key={granja} style={{ transition: 'background-color 0.2s' }}>
                      <td><strong>{granja}</strong></td>
                      {info.dias.map((cant, idx) => (
                        <td key={idx} className="text-right">
                          {cant > 0 ? formatNumber(cant) : '-'}
                        </td>
                      ))}
                      <td className="text-right"><strong>{formatNumber(info.total)}</strong></td>
                      <td className="text-right">{formatNumber(Math.round(info.cajas))}</td>
                    </tr>
                  ))}
                <tr className="row-subtotal">
                  <td><strong>TOTAL</strong></td>
                  {dias.map((dia, idx) => (
                    <td key={idx} className="text-right"><strong>{formatNumber(dia.total_pollos)}</strong></td>
                  ))}
                  <td className="text-right"><strong>{formatNumber(proyeccion.total_pollos_semana)}</strong></td>
                  <td className="text-right"><strong>{formatNumber(proyeccion.produccion_cajas_semanales)}</strong></td>
                </tr>
              </tbody>
            </table>
          </div>
        </div>
      </motion.div>

      {/* Cobertura de la Oferta */}
      {(() => {
        const pollosAsignados = proyeccion.total_pollos_semana || 0
        const pollosFueraRango = proyeccion.total_pollos_fuera_rango || 0
        const pollosNoAsignados = proyeccion.total_pollos_no_asignados || 0
        const totalOfertados = pollosAsignados + pollosFueraRango + pollosNoAsignados
        if (pollosFueraRango === 0 && pollosNoAsignados === 0) return null

        const lotesFR = proyeccion.lotes_fuera_rango || []
        const lotesNA = proyeccion.lotes_no_asignados || []
        const lotesAsignados = dias.reduce((sum, d) => sum + d.lotes.filter(l => l.cantidad > 0).length, 0)
        const pctAsignados = totalOfertados > 0 ? ((pollosAsignados / totalOfertados) * 100).toFixed(1) : '0.0'

        return (
          <motion.div variants={itemVariants} className="card">
            <div className="card-header">
              <h2><PieChart size={18} style={{ verticalAlign: 'middle', marginRight: 6 }} /> Cobertura de la Oferta</h2>
            </div>
            <div className="card-body">
              <div className="stats-grid" style={{ marginBottom: '1rem' }}>
                <div className="stat-card">
                  <div className="stat-label">Total Ofertados</div>
                  <div className="stat-value">{formatNumber(totalOfertados)}</div>
                </div>
                <div className="stat-card">
                  <div className="stat-label">Asignados ({pctAsignados}%)</div>
                  <div className="stat-value green">{formatNumber(pollosAsignados)}</div>
                </div>
                <div className="stat-card">
                  <div className="stat-label">Fuera de Rango</div>
                  <div className="stat-value" style={{ color: 'var(--danger, #ef4444)' }}>{formatNumber(pollosFueraRango)}</div>
                </div>
                <div className="stat-card">
                  <div className="stat-label">Exceso Capacidad</div>
                  <div className="stat-value orange">{formatNumber(pollosNoAsignados)}</div>
                </div>
              </div>

              <div className="table-container">
                <table>
                  <thead>
                    <tr>
                      <th>Categoría</th>
                      <th className="text-right">Lotes</th>
                      <th className="text-right">Pollos</th>
                    </tr>
                  </thead>
                  <tbody>
                    <tr>
                      <td style={{ color: 'var(--success)' }}><strong>Asignados a proyección</strong></td>
                      <td className="text-right">{lotesAsignados}</td>
                      <td className="text-right">{formatNumber(pollosAsignados)}</td>
                    </tr>
                    {pollosFueraRango > 0 && (
                      <tr>
                        <td style={{ color: 'var(--danger, #ef4444)' }}><strong>Fuera de rango (edad/peso)</strong></td>
                        <td className="text-right">{lotesFR.length}</td>
                        <td className="text-right">{formatNumber(pollosFueraRango)}</td>
                      </tr>
                    )}
                    {pollosNoAsignados > 0 && (
                      <tr>
                        <td style={{ color: 'var(--warning)' }}><strong>Exceso de capacidad diaria</strong></td>
                        <td className="text-right">{lotesNA.length}</td>
                        <td className="text-right">{formatNumber(pollosNoAsignados)}</td>
                      </tr>
                    )}
                    <tr className="row-subtotal">
                      <td><strong>TOTAL OFERTADOS</strong></td>
                      <td className="text-right"><strong>{lotesAsignados + lotesFR.length + lotesNA.length}</strong></td>
                      <td className="text-right"><strong>{formatNumber(totalOfertados)}</strong></td>
                    </tr>
                  </tbody>
                </table>
              </div>
            </div>
          </motion.div>
        )
      })()}
    </motion.div>
  )
}
