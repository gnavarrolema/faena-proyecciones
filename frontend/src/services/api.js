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

export default api;
