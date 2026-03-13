import axios from 'axios';

// En desarrollo local → http://127.0.0.1:5000
// En producción (Cloud Run) → URL del backend inyectada en build via VITE_API_URL
const API_BASE = import.meta.env.VITE_API_URL || 'http://127.0.0.1:5000';

const api = axios.create({
  baseURL: API_BASE,
  headers: { 'Content-Type': 'application/json' },
});

// Request interceptor for token injection
api.interceptors.request.use(
  (config) => {
    const token = localStorage.getItem('token');
    if (token) {
      config.headers.Authorization = `Bearer ${token}`;
    }
    return config;
  },
  (error) => Promise.reject(error)
);

// Response interceptor: redirigir al login si el token expiró
api.interceptors.response.use(
  (response) => response,
  (error) => {
    if (error.response?.status === 401) {
      localStorage.removeItem('token');
      window.location.href = '/login';
    }
    return Promise.reject(error);
  }
);

// ─── Autenticación ─────────────────────────────────────────────────────────────

export const login = (username, password) => {
  const formData = new URLSearchParams();
  formData.append('username', username);
  formData.append('password', password);

  return api.post('/token', formData, {
    headers: { 'Content-Type': 'application/x-www-form-urlencoded' }
  }).then(r => r.data);
};

// ─── Parámetros ────────────────────────────────────────────────────────────────

export const getParametros = () => api.get('/parametros').then(r => r.data);
export const updateParametros = (params) => api.put('/parametros', params).then(r => r.data);

// ─── Oferta ────────────────────────────────────────────────────────────────────

export const uploadOferta = (file, sheetName) => {
  const form = new FormData();
  form.append('file', file);
  if (sheetName) form.append('sheet_name', sheetName);
  return api.post('/oferta/upload', form, {
    headers: { 'Content-Type': 'multipart/form-data' },
  }).then(r => r.data);
};

export const getOferta = () => api.get('/oferta').then(r => r.data);
export const clearOferta = () => api.delete('/oferta').then(r => r.data);

export const uploadAjusteMartes = (file, sheetName) => {
  const form = new FormData();
  form.append('file', file);
  if (sheetName) form.append('sheet_name', sheetName);
  return api.post('/oferta/ajuste-martes', form, {
    headers: { 'Content-Type': 'multipart/form-data' },
  }).then(r => r.data);
};

// ─── Proyección ────────────────────────────────────────────────────────────────

export const generarProyeccion = (params) =>
  api.post('/proyeccion/generar', params).then(r => r.data);

export const getProyeccion = () => api.get('/proyeccion').then(r => r.data);

export const moverLote = (data) =>
  api.post('/proyeccion/mover-lote', data).then(r => r.data);

export const agregarLote = (data) =>
  api.post('/proyeccion/agregar-lote', data).then(r => r.data);

export const eliminarLote = (diaIndex, loteIndex) =>
  api.delete(`/proyeccion/lote/${diaIndex}/${loteIndex}`).then(r => r.data);

// ─── Feriados ──────────────────────────────────────────────────────────────────

export const getFeriados = (anio) => api.get(`/feriados?anio=${anio}`).then(r => r.data);
export const getFeriadosCustom = () => api.get('/feriados/custom').then(r => r.data);
export const addFeriadoCustom = (fecha, descripcion) =>
  api.post('/feriados/custom', { fecha, descripcion }).then(r => r.data);
export const deleteFeriadoCustom = (fecha) =>
  api.delete(`/feriados/custom/${fecha}`).then(r => r.data);

// ─── Producción Semanal ────────────────────────────────────────────────────────

export const uploadProduccion = (file, sheetName) => {
  const form = new FormData();
  form.append('file', file);
  if (sheetName) form.append('sheet_name', sheetName);
  return api.post('/produccion/upload', form, {
    headers: { 'Content-Type': 'multipart/form-data' },
  }).then(r => r.data);
};

export const getProduccion = () => api.get('/produccion').then(r => r.data);
export const getSimulacionMortalidad = () => api.get('/produccion/simulacion').then(r => r.data);
export const deleteProduccion = () => api.delete('/produccion').then(r => r.data);

// ─── Desvío de Peso ────────────────────────────────────────────────────────────

export const cargarPesosReales = (pesos) =>
  api.post('/desvio/pesos-reales', { pesos }).then(r => r.data);
export const getDesvio = () => api.get('/desvio').then(r => r.data);
export const deletePesosReales = () => api.delete('/desvio').then(r => r.data);

// ─── Gallinas ─────────────────────────────────────────────────────────────────

export const configurarGallinas = (diaIndex, cantidad, tipo = 'liviana', descripcion) =>
  api.post('/proyeccion/gallinas', { dia_index: diaIndex, cantidad, tipo, descripcion }).then(r => r.data);
export const quitarGallinas = (diaIndex, tipo = null) =>
  api.delete(`/proyeccion/gallinas/${diaIndex}${tipo ? `?tipo=${tipo}` : ''}`).then(r => r.data);

// ─── Escenarios ────────────────────────────────────────────────────────────────

export const guardarEscenario = (nombre, descripcion) =>
  api.post('/escenarios/guardar', { nombre, descripcion }).then(r => r.data);
export const listarEscenarios = () => api.get('/escenarios').then(r => r.data);
export const getEscenario = (id) => api.get(`/escenarios/${id}`).then(r => r.data);
export const deleteEscenario = (id) => api.delete(`/escenarios/${id}`).then(r => r.data);
export const compararEscenarios = (ids) =>
  api.post('/escenarios/comparar', { ids }).then(r => r.data);
export const cargarEscenario = (id) =>
  api.post(`/escenarios/${id}/cargar`).then(r => r.data);

// ─── Producción: referencia cruzada ────────────────────────────────────────────

export const getReferenciaProduccion = (fechaFaena) =>
  api.get(`/produccion/referencia?fecha_faena=${fechaFaena}`).then(r => r.data);

// ─── Redistribuir día ──────────────────────────────────────────────────────────

export const redistribuirDia = (diaIndex) =>
  api.post('/proyeccion/redistribuir-dia', { dia_index: diaIndex }).then(r => r.data);

// ─── Déficit entre semanas ─────────────────────────────────────────────────────

export const cargarDeficit = () =>
  api.post('/proyeccion/cargar-deficit').then(r => r.data);
export const getDeficitGuardado = () =>
  api.get('/proyeccion/deficit-guardado').then(r => r.data);
export const clearDeficitGuardado = () =>
  api.delete('/proyeccion/deficit-guardado').then(r => r.data);

export default api;

