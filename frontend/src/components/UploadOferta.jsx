import { useState, useRef } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import { UploadCloud, CheckCircle2, FileSpreadsheet, AlertCircle, Trash2, FolderUp, TriangleAlert } from 'lucide-react'
import { uploadOferta } from '../services/api'

export default function UploadOferta({ onUpload, hayDatosExistentes }) {
  const [file, setFile] = useState(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState(null)
  const [dragging, setDragging] = useState(false)
  const [confirmado, setConfirmado] = useState(false)
  const inputRef = useRef(null)

  const handleFile = (f) => {
    if (f && (f.name.endsWith('.xlsx') || f.name.endsWith('.xls'))) {
      setFile(f)
      setError(null)
    } else {
      setError('Solo se aceptan archivos .xlsx o .xls')
    }
  }

  const handleUpload = async () => {
    if (!file) return
    if (hayDatosExistentes && !confirmado) return
    setLoading(true)
    setError(null)
    try {
      const data = await uploadOferta(file)
      onUpload(data)
    } catch (err) {
      setError(err.response?.data?.detail || 'Error al procesar el archivo')
    } finally {
      setLoading(false)
    }
  }

  return (
    <motion.div
      initial={{ opacity: 0, scale: 0.95 }}
      animate={{ opacity: 1, scale: 1 }}
      transition={{ duration: 0.3 }}
      style={{ maxWidth: 700, margin: '0 auto' }}
    >
      <div className="card">
        <div className="card-header">
          <h2><FolderUp size={18} style={{ verticalAlign: 'middle', marginRight: 6 }} /> Cargar Oferta de Granjas (Jueves)</h2>
        </div>
        <div className="card-body">
          <p style={{ marginBottom: '1rem', color: 'var(--text-light)', fontSize: '0.9rem' }}>
            Suba el archivo Excel con la <strong>oferta del jueves</strong> de granjas (formato OFERTA JUEV).
            Esta es la oferta base para armar la programación de faena de la próxima semana.
            Luego podrá ajustarla con la <strong>oferta del martes</strong> desde la pestaña Proyección.
          </p>
          <div style={{ marginBottom: '1rem', padding: '0.6rem 0.9rem', background: 'var(--info-light, #e0f2fe)', borderRadius: 8, fontSize: '0.85rem', color: 'var(--info, #0284c7)', display: 'flex', alignItems: 'center', gap: 8 }}>
            <AlertCircle size={16} />
            <span><strong>Flujo:</strong> Jueves → cargar oferta y generar proyección → Martes → ajustar con nueva oferta para mayor precisión.</span>
          </div>

          {/* Advertencia de sobreescritura */}
          <AnimatePresence>
            {hayDatosExistentes && (
              <motion.div
                initial={{ opacity: 0, height: 0, marginBottom: 0 }}
                animate={{ opacity: 1, height: 'auto', marginBottom: '1rem' }}
                exit={{ opacity: 0, height: 0, marginBottom: 0 }}
                style={{
                  padding: '0.85rem 1rem',
                  background: 'rgba(251, 146, 60, 0.12)',
                  border: '1px solid rgba(251, 146, 60, 0.45)',
                  borderRadius: 8,
                  fontSize: '0.875rem',
                  color: '#ea580c',
                }}
              >
                <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: '0.6rem', fontWeight: 600 }}>
                  <TriangleAlert size={17} />
                  <span>¡Atención! Ya existen datos cargados en el sistema</span>
                </div>
                <p style={{ margin: 0, marginBottom: '0.75rem', lineHeight: 1.5 }}>
                  Cargar un nuevo archivo <strong>reemplazará completamente</strong> la oferta actual y la proyección/planificación generada.
                  Si solo desea actualizar datos manteniendo la planificación, use la opción{' '}
                  <strong>«Ajuste Martes»</strong> en la pestaña Proyección.
                </p>
                <label style={{ display: 'flex', alignItems: 'center', gap: 8, cursor: 'pointer', fontWeight: 500, userSelect: 'none' }}>
                  <input
                    type="checkbox"
                    checked={confirmado}
                    onChange={(e) => setConfirmado(e.target.checked)}
                    style={{ width: 16, height: 16, accentColor: '#ea580c', cursor: 'pointer' }}
                  />
                  Entiendo que los datos actuales serán reemplazados y deseo continuar
                </label>
              </motion.div>
            )}
          </AnimatePresence>

          <div
            className={`upload-zone ${dragging ? 'dragging' : ''}`}
            onClick={() => inputRef.current?.click()}
            onDragOver={(e) => { e.preventDefault(); setDragging(true) }}
            onDragLeave={() => setDragging(false)}
            onDrop={(e) => {
              e.preventDefault()
              setDragging(false)
              handleFile(e.dataTransfer.files[0])
            }}
          >
            <div className="icon"><UploadCloud size={48} color={dragging ? 'var(--primary)' : 'var(--text-light)'} /></div>
            <p>
              {file
                ? <span className="filename" style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', gap: 6 }}><FileSpreadsheet size={16} /> {file.name}</span>
                : 'Arrastre un archivo Excel aquí o haga clic para seleccionar'
              }
            </p>
            <input
              ref={inputRef}
              type="file"
              accept=".xlsx,.xls"
              style={{ display: 'none' }}
              onChange={(e) => handleFile(e.target.files[0])}
            />
          </div>

          <AnimatePresence>
            {error && (
              <motion.div
                initial={{ opacity: 0, height: 0, marginTop: 0 }}
                animate={{ opacity: 1, height: 'auto', marginTop: '1rem' }}
                exit={{ opacity: 0, height: 0, marginTop: 0 }}
                style={{
                  padding: '0.75rem',
                  background: 'var(--danger-light)',
                  color: 'var(--danger)',
                  borderRadius: 6,
                  fontSize: '0.85rem',
                  display: 'flex',
                  alignItems: 'center',
                  gap: 6
                }}
              >
                <AlertCircle size={16} /> {error}
              </motion.div>
            )}
          </AnimatePresence>

          <div style={{ marginTop: '1.5rem', display: 'flex', gap: '0.75rem' }}>
            <button
              className="btn btn-primary"
              disabled={!file || loading || (hayDatosExistentes && !confirmado)}
              onClick={handleUpload}
            >
              {loading ? (
                <><span className="spinner" style={{ width: 16, height: 16, marginRight: 6 }}></span> Procesando...</>
              ) : (
                <><CheckCircle2 size={16} /> Cargar y Procesar</>
              )}
            </button>
            {file && (
              <button className="btn btn-outline" onClick={() => { setFile(null); setError(null) }}>
                <Trash2 size={16} /> Limpiar
              </button>
            )}
          </div>
        </div>
      </div>

      <div className="card">
        <div className="card-header">
          <h2><AlertCircle size={16} style={{ verticalAlign: 'middle', marginRight: 6 }} /> Formato esperado</h2>
        </div>
        <div className="card-body">
          <div className="table-container">
            <table>
              <thead>
                <tr>
                  <th>Columna</th>
                  <th>Campo</th>
                  <th>Ejemplo</th>
                </tr>
              </thead>
              <tbody>
                <tr><td>A</td><td>Fecha de Peso</td><td>12/2/2026</td></tr>
                <tr><td>B</td><td>Granja</td><td>LOS REMANSOS</td></tr>
                <tr><td>C</td><td>Galpón</td><td>5</td></tr>
                <tr><td>D</td><td>Núcleo</td><td>1</td></tr>
                <tr><td>E</td><td>Cantidad</td><td>4.370</td></tr>
                <tr><td>F</td><td>Sexo (M/H)</td><td>H</td></tr>
                <tr><td>G</td><td>Edad Proyectada</td><td>42</td></tr>
                <tr><td>H</td><td>Peso Muestreo Proy</td><td>2,78</td></tr>
                <tr><td>I</td><td>Ganancia Diaria</td><td>0,090</td></tr>
                <tr><td>J</td><td>Días Proyectados</td><td>0</td></tr>
                <tr><td>K</td><td>Edad Real</td><td>42</td></tr>
                <tr><td>L</td><td>Peso Muestreo Real</td><td>2,78</td></tr>
                <tr><td>N</td><td>Fecha de Ingreso</td><td>31/12/2025</td></tr>
              </tbody>
            </table>
          </div>
        </div>
      </div>
    </motion.div>
  )
}
