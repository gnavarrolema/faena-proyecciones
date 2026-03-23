import { useState, useEffect } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import { FolderUp, List, KanbanSquare, TrendingUp, Settings2, Bird, LogOut, Loader2, Factory, Scale, Layers, Activity, ShieldCheck } from 'lucide-react'
import { useNavigate } from 'react-router-dom'
import { useAuth } from '../context/AuthContext'
import { getOferta, getProyeccion, getDeficitGuardado, clearDeficitGuardado } from '../services/api'
import UploadOferta from './UploadOferta'
import OfertaTable from './OfertaTable'
import ProyeccionView from './ProyeccionView'
import ParametrosPanel from './ParametrosPanel'
import ResumenSemanal from './ResumenSemanal'
import ProduccionView from './ProduccionView'
import DesvioView from './DesvioView'
import EscenariosView from './EscenariosView'
import PronosticoPesosView from './PronosticoPesosView'
import ValidacionCruzadaView from './ValidacionCruzadaView'

const TABS = [
    { id: 'upload', label: 'Cargar Oferta', icon: <FolderUp size={16} /> },
    { id: 'oferta', label: 'Oferta', icon: <List size={16} /> },
    { id: 'proyeccion', label: 'Proyección', icon: <KanbanSquare size={16} /> },
    { id: 'resumen', label: 'Resumen', icon: <TrendingUp size={16} /> },
    { id: 'produccion', label: 'Cargas Pollitos BB', icon: <Factory size={16} /> },
    { id: 'validacion', label: 'Validación Cruzada', icon: <ShieldCheck size={16} /> },
    { id: 'desvios', label: 'Desvíos', icon: <Scale size={16} /> },
    { id: 'pronostico', label: 'Pronóstico Pesos', icon: <Activity size={16} /> },
    { id: 'escenarios', label: 'Escenarios', icon: <Layers size={16} /> },
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
    const [deficitGuardado, setDeficitGuardado] = useState(null)
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

    // Cargar déficit de semana anterior al iniciar
    useEffect(() => {
        getDeficitGuardado()
            .then(d => { if (d.existe) setDeficitGuardado(d) })
            .catch(() => {})
    }, []);

    const handleLogout = () => {
        logout();
        navigate('/');
    };

    return (
        <>
            <header className="app-header">
                <motion.div 
                    className="app-header-logo"
                    initial={{ opacity: 0, x: -20 }}
                    animate={{ opacity: 1, x: 0 }}
                    transition={{ duration: 0.5 }}
                >
                    <Bird size={28} className="logo-icon" /> 
                    <h1>Proyección de Faena</h1>
                </motion.div>

                <nav className="app-nav">
                    {TABS.map(tab => {
                        const isActive = activeTab === tab.id;
                        return (
                            <button
                                key={tab.id}
                                className={`nav-btn ${isActive ? 'active' : ''}`}
                                onClick={() => setActiveTab(tab.id)}
                            >
                                {isActive && (
                                    <motion.div
                                        layoutId="active-nav-indicator"
                                        className="nav-btn-indicator"
                                        initial={false}
                                        transition={{ type: "spring", stiffness: 500, damping: 30 }}
                                    />
                                )}
                                <span className="nav-btn-content">
                                    {tab.icon} {tab.label}
                                </span>
                            </button>
                        );
                    })}
                    <button onClick={handleLogout} className="logout-btn">
                        <LogOut size={16} /> <span>Salir</span>
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
                                    hayDatosExistentes={!!(oferta || proyeccion)}
                                    deficitGuardado={deficitGuardado}
                                    onClearDeficit={() => {
                                        clearDeficitGuardado()
                                            .then(() => setDeficitGuardado(null))
                                            .catch(() => {})
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
                                    deficitGuardado={deficitGuardado}
                                    onDeficitUsado={() => {
                                        setDeficitGuardado(null)
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

                            {activeTab === 'produccion' && (
                                <ProduccionView />
                            )}

                            {activeTab === 'validacion' && (
                                <ValidacionCruzadaView />
                            )}

                            {activeTab === 'desvios' && (
                                <DesvioView proyeccion={proyeccion} />
                            )}

                            {activeTab === 'pronostico' && (
                                <PronosticoPesosView proyeccion={proyeccion} />
                            )}

                            {activeTab === 'escenarios' && (
                                <EscenariosView
                                    proyeccion={proyeccion}
                                    setProyeccion={setProyeccion}
                                />
                            )}

                            {activeTab === 'parametros' && (
                                <ParametrosPanel
                                    onParametrosUpdated={async () => {
                                        try {
                                            const proy = await getProyeccion()
                                            if (proy?.dias) setProyeccion(proy)
                                        } catch { /* no projection */ }
                                    }}
                                />
                            )}
                        </motion.div>
                    </AnimatePresence>
                )}
            </main>
        </>
    )
}

export default MainApp

