import { useState } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import { FolderUp, List, KanbanSquare, TrendingUp, Settings2, Bird, LogOut } from 'lucide-react'
import { useNavigate } from 'react-router-dom'
import { useAuth } from '../context/AuthContext'
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
    const { logout } = useAuth();
    const navigate = useNavigate();

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
            </main>
        </>
    )
}

export default MainApp
