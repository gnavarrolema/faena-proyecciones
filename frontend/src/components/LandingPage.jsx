import { motion } from 'framer-motion';
import { useNavigate } from 'react-router-dom';
import { Activity, BarChart2, Shield, Zap } from 'lucide-react';

const LandingPage = () => {
    const navigate = useNavigate();

    const containerVariants = {
        hidden: { opacity: 0 },
        visible: {
            opacity: 1,
            transition: { staggerChildren: 0.2 }
        }
    };

    const itemVariants = {
        hidden: { opacity: 0, y: 30 },
        visible: { opacity: 1, y: 0, transition: { duration: 0.6, ease: "easeOut" } }
    };

    return (
        <div style={styles.wrapper}>
            <header style={styles.header}>
                <motion.div
                    initial={{ opacity: 0, x: -20 }}
                    animate={{ opacity: 1, x: 0 }}
                    style={styles.logo}
                >
                    <Activity color="#38bdf8" size={28} />
                    <span style={{ fontWeight: 'bold', fontSize: '20px' }}>ProyecFaena</span>
                </motion.div>

                <motion.button
                    initial={{ opacity: 0, x: 20 }}
                    animate={{ opacity: 1, x: 0 }}
                    whileHover={{ scale: 1.05 }}
                    whileTap={{ scale: 0.95 }}
                    style={styles.loginBtn}
                    onClick={() => navigate('/login')}
                >
                    Iniciar Sesión
                </motion.button>
            </header>

            <main style={styles.main}>
                <motion.section
                    variants={containerVariants}
                    initial="hidden"
                    animate="visible"
                    style={styles.hero}
                >
                    <motion.div variants={itemVariants} style={styles.badge}>
                        ✨ Plataforma Avanzada de Planificación
                    </motion.div>

                    <motion.h1 variants={itemVariants} style={styles.h1}>
                        Optimiza tu Planificación de <br />
                        <span style={{ color: '#38bdf8' }}>Faena Avícola</span>
                    </motion.h1>

                    <motion.p variants={itemVariants} style={styles.description}>
                        Sistema inteligente para cargar ofertas, proyectar pesos y edades, y
                        distribuir eficientemente los lotes a lo largo de la semana. Todo en tiempo real
                        y con precisión milimétrica.
                    </motion.p>

                    <motion.button
                        variants={itemVariants}
                        whileHover={{ scale: 1.05, boxShadow: '0 0 20px rgba(56, 189, 248, 0.4)' }}
                        whileTap={{ scale: 0.95 }}
                        style={styles.cta}
                        onClick={() => navigate('/login')}
                    >
                        Comenzar Ahora
                    </motion.button>
                </motion.section>

                <motion.section
                    initial={{ opacity: 0, y: 50 }}
                    whileInView={{ opacity: 1, y: 0 }}
                    viewport={{ once: true, margin: "-100px" }}
                    transition={{ duration: 0.8 }}
                    style={styles.features}
                >
                    <FeatureCard
                        icon={<BarChart2 size={32} color="#38bdf8" />}
                        title="Proyecciones Exactas"
                        desc="Calcula automáticamente el peso y edad proyectada de cada lote según ganancia diaria."
                    />
                    <FeatureCard
                        icon={<Zap size={32} color="#a855f7" />}
                        title="Distribución Dinámica"
                        desc="Asigna y mueve lotes entre días de la semana con feedback visual inmediato."
                    />
                    <FeatureCard
                        icon={<Shield size={32} color="#10b981" />}
                        title="Seguridad y Control"
                        desc="Entorno seguro con acceso autenticado para proteger la información estratégica."
                    />
                </motion.section>
            </main>

            <div style={styles.bgGlow1} />
            <div style={styles.bgGlow2} />
        </div>
    );
};

const FeatureCard = ({ icon, title, desc }) => (
    <motion.div
        whileHover={{ y: -10, backgroundColor: 'rgba(255, 255, 255, 0.08)' }}
        style={styles.featureCard}
    >
        <div style={styles.iconWrapper}>{icon}</div>
        <h3 style={styles.featureTitle}>{title}</h3>
        <p style={styles.featureDesc}>{desc}</p>
    </motion.div>
);

const styles = {
    wrapper: {
        minHeight: '100vh',
        backgroundColor: '#0f172a',
        color: '#f8fafc',
        fontFamily: 'Inter, system-ui, sans-serif',
        overflow: 'hidden',
        position: 'relative'
    },
    header: {
        display: 'flex',
        justifyContent: 'space-between',
        alignItems: 'center',
        padding: '24px 48px',
        position: 'relative',
        zIndex: 10
    },
    logo: {
        display: 'flex',
        alignItems: 'center',
        gap: '12px'
    },
    loginBtn: {
        background: 'rgba(255, 255, 255, 0.1)',
        border: '1px solid rgba(255, 255, 255, 0.2)',
        color: '#fff',
        padding: '10px 24px',
        borderRadius: '20px',
        cursor: 'pointer',
        fontWeight: '500',
        backdropFilter: 'blur(10px)'
    },
    main: {
        maxWidth: '1200px',
        margin: '0 auto',
        padding: '60px 24px',
        position: 'relative',
        zIndex: 10
    },
    hero: {
        textAlign: 'center',
        display: 'flex',
        flexDirection: 'column',
        alignItems: 'center',
        marginTop: '40px'
    },
    badge: {
        background: 'rgba(56, 189, 248, 0.1)',
        color: '#38bdf8',
        padding: '8px 16px',
        borderRadius: '20px',
        fontSize: '14px',
        fontWeight: '600',
        marginBottom: '24px',
        border: '1px solid rgba(56, 189, 248, 0.2)'
    },
    h1: {
        fontSize: '64px',
        lineHeight: '1.1',
        fontWeight: '800',
        margin: '0 0 24px 0',
        letterSpacing: '-1px'
    },
    description: {
        fontSize: '20px',
        lineHeight: '1.6',
        color: '#94a3b8',
        maxWidth: '600px',
        margin: '0 0 40px 0'
    },
    cta: {
        background: 'linear-gradient(135deg, #0ea5e9 0%, #2563eb 100%)',
        color: '#fff',
        border: 'none',
        padding: '16px 40px',
        borderRadius: '30px',
        fontSize: '18px',
        fontWeight: 'bold',
        cursor: 'pointer',
        boxShadow: '0 10px 20px rgba(14, 165, 233, 0.3)'
    },
    features: {
        display: 'grid',
        gridTemplateColumns: 'repeat(auto-fit, minmax(300px, 1fr))',
        gap: '30px',
        marginTop: '100px'
    },
    featureCard: {
        background: 'rgba(255, 255, 255, 0.03)',
        border: '1px solid rgba(255, 255, 255, 0.05)',
        borderRadius: '24px',
        padding: '40px 30px',
        transition: 'all 0.3s ease'
    },
    iconWrapper: {
        width: '64px',
        height: '64px',
        borderRadius: '16px',
        background: 'rgba(255, 255, 255, 0.05)',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        marginBottom: '24px'
    },
    featureTitle: {
        fontSize: '22px',
        fontWeight: 'bold',
        margin: '0 0 12px 0'
    },
    featureDesc: {
        color: '#94a3b8',
        lineHeight: '1.6',
        margin: 0
    },
    bgGlow1: {
        position: 'absolute',
        top: '-20%',
        left: '-10%',
        width: '50vw',
        height: '50vw',
        background: 'radial-gradient(circle, rgba(14,165,233,0.15) 0%, rgba(15,23,42,0) 70%)',
        zIndex: 1,
        pointerEvents: 'none'
    },
    bgGlow2: {
        position: 'absolute',
        bottom: '-20%',
        right: '-10%',
        width: '60vw',
        height: '60vw',
        background: 'radial-gradient(circle, rgba(168,85,247,0.1) 0%, rgba(15,23,42,0) 70%)',
        zIndex: 1,
        pointerEvents: 'none'
    }
};

export default LandingPage;
