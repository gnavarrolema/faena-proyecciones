import { useState } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import { X, CheckCircle2, AlertTriangle, Calendar, Clock } from 'lucide-react'
import toast from 'react-hot-toast'
import { aplicarVariante } from '../services/api'

const DIAS_SEMANA = ['Lunes', 'Martes', 'Miércoles', 'Jueves', 'Viernes', 'Sábado', 'Domingo']

function formatNumber(n) {
  if (n == null) return '-'
  return n.toLocaleString('es-AR')
}

function getDiaNombre(fechaStr) {
  if (!fechaStr) return '-'
  const dt = new Date(fechaStr + 'T12:00:00')
  const idx = dt.getDay() === 0 ? 6 : dt.getDay() - 1
  return DIAS_SEMANA[idx]
}

function formatDateShort(fechaStr) {
  if (!fechaStr) return '-'
  const dt = new Date(fechaStr + 'T12:00:00')
  return dt.toLocaleDateString('es-AR', { day: 'numeric', month: 'short' })
}

const ETIQUETA_COLORS = {
  Conservador: { bg: 'rgba(34, 197, 94, 0.12)', border: 'rgba(34, 197, 94, 0.35)', text: '#16a34a' },
  Equilibrado: { bg: 'rgba(59, 130, 246, 0.12)', border: 'rgba(59, 130, 246, 0.35)', text: '#2563eb' },
  Intensivo: { bg: 'rgba(251, 146, 60, 0.12)', border: 'rgba(251, 146, 60, 0.35)', text: '#ea580c' },
}

export default function VariantesPicker({ data, onSelect, onClose }) {
  const [applying, setApplying] = useState(null)

  if (!data || !data.variantes || data.variantes.length === 0) return null

  const { variantes, motivos_complejidad } = data

  const handleSelect = async (variante) => {
    setApplying(variante.etiqueta)
    try {
      await aplicarVariante(variante.proyeccion)
      toast.success(`Variante "${variante.etiqueta}" aplicada`)
      onSelect(variante.proyeccion)
    } catch (err) {
      toast.error(err.response?.data?.detail || 'Error al aplicar variante')
    } finally {
      setApplying(null)
    }
  }

  return (
    <div className="modal-overlay" onClick={onClose}>
      <motion.div
        className="modal"
        initial={{ opacity: 0, scale: 0.95 }}
        animate={{ opacity: 1, scale: 1 }}
        exit={{ opacity: 0, scale: 0.95 }}
        onClick={(e) => e.stopPropagation()}
        style={{ maxWidth: variantes.length > 1 ? 950 : 500, width: '95vw' }}
      >
        <div className="card-header" style={{ borderBottom: '1px solid var(--border)' }}>
          <h2 style={{ margin: 0, fontSize: '1.1rem' }}>
            Variantes de Planificación
          </h2>
          <button className="btn btn-sm btn-outline" onClick={onClose}>
            <X size={14} />
          </button>
        </div>

        {/* Motivos de complejidad */}
        {data.es_compleja && (
          <div style={{
            padding: '0.6rem 1rem',
            background: 'rgba(251, 146, 60, 0.08)',
            borderBottom: '1px solid var(--border)',
            fontSize: '0.8rem',
            color: 'var(--text-light)',
            display: 'flex',
            gap: 12,
            flexWrap: 'wrap',
          }}>
            <strong style={{ color: '#ea580c' }}>Semana compleja:</strong>
            {motivos_complejidad.feriados && <span><Calendar size={12} /> Feriados</span>}
            {motivos_complejidad.gallinas && <span><Clock size={12} /> Gallinas</span>}
            {motivos_complejidad.carga_excedida && <span><AlertTriangle size={12} /> Alta carga</span>}
          </div>
        )}

        <div style={{
          padding: '1rem',
          display: 'grid',
          gridTemplateColumns: `repeat(${variantes.length}, 1fr)`,
          gap: '1rem',
        }}>
          {variantes.map((v) => {
            const colors = ETIQUETA_COLORS[v.etiqueta] || ETIQUETA_COLORS.Equilibrado
            const r = v.resumen
            return (
              <div key={v.etiqueta} style={{
                border: `2px solid ${colors.border}`,
                borderRadius: 10,
                overflow: 'hidden',
              }}>
                {/* Header */}
                <div style={{
                  padding: '0.6rem 0.8rem',
                  background: colors.bg,
                  borderBottom: `1px solid ${colors.border}`,
                }}>
                  <div style={{ fontWeight: 700, color: colors.text, fontSize: '1rem' }}>
                    {v.etiqueta}
                  </div>
                  <div style={{ fontSize: '0.75rem', color: 'var(--text-light)', marginTop: 2 }}>
                    {v.descripcion}
                  </div>
                </div>

                {/* Métricas */}
                <div style={{ padding: '0.75rem 0.8rem' }}>
                  <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '0.5rem', fontSize: '0.82rem' }}>
                    <div>
                      <span style={{ color: 'var(--text-light)' }}>Total pollos</span>
                      <div style={{ fontWeight: 700, fontSize: '1.1rem' }}>{formatNumber(r.total_pollos)}</div>
                    </div>
                    <div>
                      <span style={{ color: 'var(--text-light)' }}>Cajas</span>
                      <div style={{ fontWeight: 700, fontSize: '1.1rem' }}>{formatNumber(Math.round(r.cajas_semanales))}</div>
                    </div>
                    <div>
                      <span style={{ color: 'var(--text-light)' }}>Días</span>
                      <div style={{ fontWeight: 600 }}>{r.dias_efectivos}</div>
                    </div>
                    <div>
                      <span style={{ color: 'var(--text-light)' }}>Máx/día</span>
                      <div style={{ fontWeight: 600 }}>{formatNumber(r.max_carga_dia)}</div>
                    </div>
                    <div>
                      <span style={{ color: 'var(--text-light)' }}>No asignados</span>
                      <div style={{
                        fontWeight: 600,
                        color: r.pollos_no_asignados > 0 ? '#ea580c' : '#16a34a',
                      }}>
                        {formatNumber(r.pollos_no_asignados)}
                      </div>
                    </div>
                    <div>
                      <span style={{ color: 'var(--text-light)' }}>Fuera rango</span>
                      <div style={{
                        fontWeight: 600,
                        color: r.pollos_fuera_rango > 0 ? '#ef4444' : '#16a34a',
                      }}>
                        {formatNumber(r.pollos_fuera_rango)}
                      </div>
                    </div>
                  </div>

                  {/* Badges */}
                  <div style={{ display: 'flex', gap: 6, marginTop: '0.6rem', flexWrap: 'wrap' }}>
                    {r.usa_sabado && (
                      <span style={{
                        padding: '0.15rem 0.5rem', borderRadius: 12,
                        background: 'rgba(251, 146, 60, 0.15)', color: '#ea580c',
                        fontSize: '0.72rem', fontWeight: 600,
                      }}>
                        Sábado
                      </span>
                    )}
                    {r.usa_horas_extras && (
                      <span style={{
                        padding: '0.15rem 0.5rem', borderRadius: 12,
                        background: 'rgba(239, 68, 68, 0.12)', color: '#ef4444',
                        fontSize: '0.72rem', fontWeight: 600,
                      }}>
                        Horas extras
                      </span>
                    )}
                    {!r.usa_horas_extras && !r.usa_sabado && (
                      <span style={{
                        padding: '0.15rem 0.5rem', borderRadius: 12,
                        background: 'rgba(34, 197, 94, 0.12)', color: '#16a34a',
                        fontSize: '0.72rem', fontWeight: 600,
                      }}>
                        Sin extras
                      </span>
                    )}
                  </div>

                  {/* Distribución diaria */}
                  <div style={{ marginTop: '0.75rem', borderTop: '1px solid var(--border)', paddingTop: '0.5rem' }}>
                    <div style={{ fontSize: '0.72rem', color: 'var(--text-light)', marginBottom: '0.3rem', fontWeight: 600 }}>
                      Distribución diaria
                    </div>
                    {(v.proyeccion.dias || []).map((dia) => (
                      <div key={dia.fecha} style={{
                        display: 'flex', justifyContent: 'space-between',
                        fontSize: '0.78rem', padding: '0.15rem 0',
                        color: dia.nivel_carga === 'horas_extras' ? '#ef4444' : 'inherit',
                      }}>
                        <span>{getDiaNombre(dia.fecha)} · {formatDateShort(dia.fecha)}</span>
                        <span style={{ fontWeight: 600 }}>{formatNumber(dia.total_pollos)}</span>
                      </div>
                    ))}
                  </div>
                </div>

                {/* Botón seleccionar */}
                <div style={{ padding: '0.5rem 0.8rem', borderTop: '1px solid var(--border)' }}>
                  <button
                    className="btn btn-primary"
                    style={{ width: '100%', fontSize: '0.85rem', padding: '0.5rem' }}
                    disabled={applying !== null}
                    onClick={() => handleSelect(v)}
                  >
                    {applying === v.etiqueta ? (
                      <><span className="spinner" style={{ width: 14, height: 14, marginRight: 4 }}></span> Aplicando...</>
                    ) : (
                      <><CheckCircle2 size={14} /> Seleccionar</>
                    )}
                  </button>
                </div>
              </div>
            )
          })}
        </div>
      </motion.div>
    </div>
  )
}
