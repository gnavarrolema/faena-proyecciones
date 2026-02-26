import { useState, useEffect } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import { FolderUp, List, KanbanSquare, TrendingUp, Settings2, Bird, LogOut, Loader2 } from 'lucide-react'
import { useNavigate } from 'react-router-dom'
import { useAuth } from '../context/AuthContext'
import { getOferta, getProyeccion } from '../services/api'
import UploadOferta from './UploadOferta'
import OfertaTable from './OfertaTable'
import ProyeccionView from './ProyeccionView'
import ParametrosPanel from './ParametrosPanel'
import ResumenSemanal from './ResumenSemanal'

const TABS = [
    { id: 'upload', label: 'Cargar Oferta', icon: <FolderUp size={16} /> },
    { id: 'oferta', label: 'Oferta', icon: <List size={16} /> },
    { id: 'proyeccion', label: 'Proyección', icon: <KanbanSquare size={16} /> },
    { id: 'resumen', label: 'Resumen', icon: <TrendingUp size={16} /> },
    { id: 'parametros', label: 'Parámetros', icon: <Settings2 size={16} /> },
]

const tabVariants = {
    initial: { opacity: 0, y: 15, scale: 0.98 },
    animate: { opacity: 1, y: 0, scale: 1 },
    exit: { opacity: 0, y: -15, scale: 0.98 }
}

const MainApp = () => {
    const [activeTab, setActiveTab] = useState('upload')
    const [oferta, setOferta] = useState(null)
    const [proyeccion, setProyeccion] = useState(null)
    const [initialLoading, setInitialLoading] = useState(true)
    const { logout } = useAuth();
    const navigate = useNavigate();

    // Cargar datos persistidos del backend al iniciar
    useEffect(() => {
        const cargarDatos = async () => {
            try {
                const [ofertaData, proyeccionData] = await Promise.allSettled([
                    getOferta(),
                    getProyeccion(),
                ]);

                if (ofertaData.status === 'fulfilled' && ofertaData.value?.ofertas?.length > 0) {
                    setOferta(ofertaData.value);
                }
                if (proyeccionData.status === 'fulfilled' && proyeccionData.value?.dias) {
                    setProyeccion(proyeccionData.value);
                }

                // Navegar a la pestaña más relevante según los datos existentes
                if (proyeccionData.status === 'fulfilled' && proyeccionData.value?.dias) {
                    setActiveTab('proyeccion');
                } else if (ofertaData.status === 'fulfilled' && ofertaData.value?.ofertas?.length > 0) {
                    setActiveTab('oferta');
                }
            } catch (err) {
                // Si falla (ej: no autenticado), simplemente empezar desde cero
                console.warn('No se pudieron cargar datos previos:', err);
            } finally {
                setInitialLoading(false);
            }
        };
        cargarDatos();
    }, []);

    const handleLogout = () => {
        logout();
        navigate('/');
    };

    return (
        <>
            <header className="app-header">
                <h1><Bird size={28} style={{ marginRight: 8 }} /> Proyección de Faena</h1>
                <nav className="app-nav">
                    {TABS.map(tab => (
                        <button
                            key={tab.id}
                            className={activeTab === tab.id ? 'active' : ''}
                            onClick={() => setActiveTab(tab.id)}
                            style={{ display: 'flex', alignItems: 'center', gap: 6 }}
                        >
                            {tab.icon} {tab.label}
                        </button>
                    ))}
                    <button onClick={handleLogout} className="logout-btn" style={{ display: 'flex', alignItems: 'center', gap: 6, marginLeft: 'auto', background: 'transparent', border: '1px solid rgba(255,255,255,0.2)', padding: '6px 12px', borderRadius: '6px', color: '#f87171', cursor: 'pointer' }}>
                        <LogOut size={16} /> Salir
                    </button>
                </nav>
            </header>

            <main className="app-content">
                {initialLoading ? (
                    <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', padding: '4rem', gap: '1rem' }}>
                        <Loader2 size={36} className="spin" style={{ animation: 'spin 1s linear infinite', color: 'var(--primary)' }} />
                        <p style={{ color: 'var(--text-light)' }}>Cargando datos guardados...</p>
                    </div>
                ) : (
                <AnimatePresence mode="wait">
                    <motion.div
                        key={activeTab}
                        variants={tabVariants}
                        initial="initial"
                        animate="animate"
                        exit="exit"
                        transition={{ duration: 0.3, ease: 'easeInOut' }}
                    >
                        {activeTab === 'upload' && (
                            <UploadOferta
                                onUpload={(data) => {
                                    setOferta(data)
                                    setActiveTab('oferta')
                                }}
                            />
                        )}

                        {activeTab === 'oferta' && (
                            <OfertaTable
                                oferta={oferta}
                                onGenerarProyeccion={(proy) => {
                                    setProyeccion(proy)
                                    setActiveTab('proyeccion')
                                }}
                            />
                        )}

                        {activeTab === 'proyeccion' && (
                            <ProyeccionView
                                proyeccion={proyeccion}
                                setProyeccion={setProyeccion}
                            />
                        )}

                        {activeTab === 'resumen' && (
                            <ResumenSemanal proyeccion={proyeccion} />
                        )}

                        {activeTab === 'parametros' && (
                            <ParametrosPanel />
                        )}
                    </motion.div>
                </AnimatePresence>
                )}
            </main>
        </>
    )
}

export default MainApp
