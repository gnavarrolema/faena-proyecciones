import { useState, useEffect } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import { Settings2, Save, CheckCircle2, AlertCircle, Download } from 'lucide-react'
import { getParametros, updateParametros } from '../services/api'
import { exportParametrosPDF } from '../utils/pdfExport'

export default function ParametrosPanel() {
  const [params, setParams] = useState(null)
  const [loading, setLoading] = useState(true)
  const [saving, setSaving] = useState(false)
  const [message, setMessage] = useState(null)

  useEffect(() => {
    loadParams()
  }, [])

  const loadParams = async () => {
    try {
      const data = await getParametros()
      setParams(data)
    } catch {
      setMessage({ type: 'error', text: 'Error al cargar parámetros' })
    } finally {
      setLoading(false)
    }
  }

  const handleSave = async () => {
    setSaving(true)
    setMessage(null)
    try {
      const data = await updateParametros(params)
      setParams(data)
      setMessage({ type: 'success', text: 'Parámetros guardados correctamente' })
      setTimeout(() => setMessage(null), 3000)
    } catch {
      setMessage({ type: 'error', text: 'Error al guardar' })
    } finally {
      setSaving(false)
    }
  }

  const handleChange = (key, value) => {
    setParams(prev => ({ ...prev, [key]: value }))
  }

  if (loading) {
    return <div className="loading"><div className="spinner"></div> Cargando parámetros...</div>
  }

  if (!params) return null

  const fields = [
    {
      section: 'Ganancia de Peso', items: [
        { key: 'ganancia_diaria_macho', label: 'Ganancia diaria machos (kg)', step: 0.001 },
        { key: 'ganancia_diaria_hembra', label: 'Ganancia diaria hembras (kg)', step: 0.001 },
        { key: 'medio_dia_ganancia', label: 'Factor medio día', step: 0.1 },
      ]
    },
    {
      section: 'Rendimiento', items: [
        { key: 'rendimiento_canal', label: 'Rendimiento canal (%)', step: 0.01 },
        { key: 'kg_por_caja', label: 'Kg por caja', step: 0.5 },
        { key: 'descuento_sin_sexar', label: 'Descuento sin sexar (%)', step: 0.01 },
      ]
    },
    {
      section: 'Edades Ideales', items: [
        { key: 'edad_ideal_macho', label: 'Edad ideal machos (días)', step: 1, type: 'int' },
        { key: 'edad_ideal_hembra', label: 'Edad ideal hembras (días)', step: 1, type: 'int' },
        { key: 'edad_ideal_sin_sexar', label: 'Edad ideal sin sexar (días)', step: 1, type: 'int' },
        { key: 'edad_min_faena', label: 'Edad mínima faena (días)', step: 1, type: 'int' },
        { key: 'edad_max_faena', label: 'Edad máxima faena (días)', step: 1, type: 'int' },
      ]
    },
    {
      section: 'Rango de Peso Faena', items: [
        { key: 'peso_min_faena', label: 'Peso mínimo faena (kg)', step: 0.01 },
        { key: 'peso_max_faena', label: 'Peso máximo faena (kg)', step: 0.01 },
      ]
    },
    {
      section: 'Producción', items: [
        { key: 'pollos_diarios_objetivo_min', label: 'Pollos diarios mín.', step: 1000, type: 'int' },
        { key: 'pollos_diarios_objetivo_max', label: 'Pollos diarios máx.', step: 1000, type: 'int' },
        { key: 'descuento_sofia', label: 'Descuento Sofía', step: 1000, type: 'int' },
      ]
    },
  ]

  return (
    <motion.div
      initial={{ opacity: 0, scale: 0.95 }}
      animate={{ opacity: 1, scale: 1 }}
      style={{ maxWidth: 800, margin: '0 auto' }}
    >
      <div className="card">
        <div className="card-header">
          <h2><Settings2 size={18} style={{ verticalAlign: 'middle', marginRight: 6 }} /> Parámetros de Cálculo</h2>
          <div style={{ display: 'flex', gap: '0.5rem' }}>
            <button className="btn btn-sm btn-outline" onClick={() => exportParametrosPDF(params)}>
              <Download size={14} /> Descargar PDF
            </button>
            <button className="btn btn-primary" onClick={handleSave} disabled={saving}>
              {saving ? (
                <><span className="spinner" style={{ width: 14, height: 14, marginRight: 6 }}></span> Guardando...</>
              ) : (
                <><Save size={14} style={{ marginRight: 4 }} /> Guardar</>
              )}
            </button>
          </div>
        </div>
        <div className="card-body">
          <AnimatePresence>
            {message && (
              <motion.div
                initial={{ opacity: 0, height: 0, marginBottom: 0 }}
                animate={{ opacity: 1, height: 'auto', marginBottom: '1rem' }}
                exit={{ opacity: 0, height: 0, marginBottom: 0 }}
                style={{
                  padding: '0.75rem',
                  background: message.type === 'error' ? 'var(--danger-light)' : 'var(--success-light)',
                  color: message.type === 'error' ? 'var(--danger)' : 'var(--success)',
                  borderRadius: 6,
                  fontSize: '0.85rem',
                  display: 'flex',
                  alignItems: 'center',
                  gap: 6
                }}
              >
                {message.type === 'error' ? <AlertCircle size={16} /> : <CheckCircle2 size={16} />}
                {message.text}
              </motion.div>
            )}
          </AnimatePresence>

          {fields.map(section => (
            <div key={section.section} style={{ marginBottom: '1.5rem' }}>
              <h3 style={{ fontSize: '0.9rem', color: 'var(--primary)', marginBottom: '0.75rem', borderBottom: '1px solid var(--border)', paddingBottom: '0.5rem' }}>
                {section.section}
              </h3>
              <div className="form-row">
                {section.items.map(field => (
                  <div className="form-group" key={field.key}>
                    <label>{field.label}</label>
                    <input
                      type="number"
                      className="form-control"
                      value={params[field.key] ?? ''}
                      step={field.step}
                      onChange={(e) => handleChange(
                        field.key,
                        field.type === 'int' ? parseInt(e.target.value) || 0 : parseFloat(e.target.value) || 0
                      )}
                    />
                  </div>
                ))}
              </div>
            </div>
          ))}
        </div>
      </div>
    </motion.div>
  )
}
