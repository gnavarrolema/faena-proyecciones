import { useState, useEffect } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import { Settings2, Save, CheckCircle2, AlertCircle, Download } from 'lucide-react'
import { getParametros, updateParametros } from '../services/api'
import { exportParametrosPDF } from '../utils/pdfExport'

export default function ParametrosPanel({ onParametrosUpdated } = {}) {
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
      if (data.proyeccion_recalculada && onParametrosUpdated) {
        await onParametrosUpdated(data)
      }
      setMessage({ type: 'success', text: data.proyeccion_recalculada ? 'Parámetros guardados y planificación recalculada' : 'Parámetros guardados correctamente' })
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
      section: 'Ganancia de Peso', description: 'Crecimiento diario estimado por sexo. Se usa para proyectar el peso vivo al momento de faena.', items: [
        { key: 'ganancia_diaria_macho', label: 'Ganancia diaria machos (kg)', step: 0.001, help: 'Kg que gana un macho por día. Determina el peso proyectado de cada lote macho.' },
        { key: 'ganancia_diaria_hembra', label: 'Ganancia diaria hembras (kg)', step: 0.001, help: 'Kg que gana una hembra por día. Determina el peso proyectado de cada lote hembra.' },
      ]
    },
    {
      section: 'Rendimiento', description: 'Factores de conversión de peso vivo a peso canal y producción en cajas.', items: [
        { key: 'rendimiento_canal', label: 'Rendimiento canal (%)', step: 0.01, help: 'Porcentaje de peso vivo que se convierte en peso canal (ej: 0.87 = 87%).' },
        { key: 'kg_por_caja', label: 'Kg por caja', step: 0.5, help: 'Peso neto por caja. Se usa para calcular el calibre (pollos/caja) y la cantidad de cajas producidas.' },
        { key: 'descuento_sin_sexar', label: 'Ajuste peso machos/sin sexar (%)', step: 0.01, help: 'Descuento aplicado al peso proyectado de machos y lotes sin sexar (ej: 0.04 = 4% menos). No aplica a hembras.' },
      ]
    },
    {
      section: 'Edades Ideales', description: 'Edad objetivo de faena por sexo. El sistema prioriza asignar lotes que estén cerca de su edad ideal.', items: [
        { key: 'edad_ideal_macho', label: 'Edad ideal machos (días)', step: 1, type: 'int', help: 'Edad óptima de faena para machos. Los lotes se priorizan según qué tan cerca estén de este valor.' },
        { key: 'edad_ideal_hembra', label: 'Edad ideal hembras (días)', step: 1, type: 'int', help: 'Edad óptima de faena para hembras.' },
        { key: 'edad_ideal_sin_sexar', label: 'Edad ideal sin sexar (días)', step: 1, type: 'int', help: 'Edad óptima de faena para lotes sin sexar.' },
        { key: 'edad_min_faena', label: 'Edad mínima faena (días)', step: 1, type: 'int', help: 'Edad mínima aceptable para faenar un lote. Por debajo de esto no se asigna.' },
        { key: 'edad_max_faena', label: 'Edad máxima faena (días)', step: 1, type: 'int', help: 'Edad máxima aceptable. Por encima de esto el lote tiene prioridad urgente.' },
      ]
    },
    {
      section: 'Rango de Peso Faena', description: 'Límites de peso vivo aceptable para faenar. Se usan en alertas tempranas y validaciones.', items: [
        { key: 'peso_min_faena', label: 'Peso mínimo faena (kg)', step: 0.01, help: 'Peso vivo mínimo aceptable. Lotes por debajo generan alerta roja.' },
        { key: 'peso_max_faena', label: 'Peso máximo faena (kg)', step: 0.01, help: 'Peso vivo máximo aceptable. Lotes por encima generan alerta.' },
      ]
    },
    {
      section: 'Producción y Capacidad', description: 'Límites operativos de la planta. Definen el rango de pollos que se pueden faenar por día.', items: [
        { key: 'pollos_diarios_objetivo_min', label: 'Objetivo diario mín. (rango práctico)', step: 1000, type: 'int', help: 'Mínimo de pollos que conviene faenar por día para que la operación sea eficiente.' },
        { key: 'pollos_diarios_objetivo_max', label: 'Objetivo diario máx. (rango práctico)', step: 1000, type: 'int', help: 'Máximo objetivo diario en condiciones normales (sin horas extras).' },
        { key: 'capacidad_maxima_planta', label: 'Capacidad máx. planta (sin horas extras)', step: 1000, type: 'int', help: 'Capacidad real de la planta en jornada normal. Por encima se requieren horas extras.' },
        { key: 'capacidad_con_horas_extras', label: 'Capacidad máx. con horas extras', step: 1000, type: 'int', help: 'Límite absoluto de faena diaria incluyendo horas extras.' },
        { key: 'limite_sabado', label: 'Límite sábado (estricto)', step: 1000, type: 'int', help: 'Máximo de pollos que se pueden faenar los sábados.' },
      ]
    },
    {
      section: 'Objetivos de Recepción', description: 'Parámetros de peso objetivo para la recepción de aves.', items: [
        { key: 'peso_objetivo_recepcion', label: 'Peso objetivo recepción (kg)', step: 0.01, help: 'Peso vivo ideal esperado al momento de recibir los pollos en planta.' },
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
              <h3 style={{ fontSize: '0.9rem', color: 'var(--primary)', marginBottom: '0.25rem', borderBottom: '1px solid var(--border)', paddingBottom: '0.5rem' }}>
                {section.section}
              </h3>
              {section.description && (
                <p style={{ fontSize: '0.78rem', color: '#666', margin: '0 0 0.75rem 0' }}>{section.description}</p>
              )}
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
                    {field.help && (
                      <span style={{ fontSize: '0.72rem', color: '#999', marginTop: 2, display: 'block' }}>{field.help}</span>
                    )}
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
