import { useState } from 'react';
import { motion } from 'framer-motion';
import { useNavigate } from 'react-router-dom';
import { useAuth } from '../context/AuthContext';
import { login } from '../services/api';
import toast from 'react-hot-toast';

const Login = () => {
    const [username, setUsername] = useState('');
    const [password, setPassword] = useState('');
    const [isLoading, setIsLoading] = useState(false);
    const navigate = useNavigate();
    const { login: authLogin } = useAuth();

    const handleSubmit = async (e) => {
        e.preventDefault();
        setIsLoading(true);
        try {
            const data = await login(username, password);
            authLogin(data.access_token);
            toast.success('¡Bienvenido!');
            navigate('/app');
        } catch {
            toast.error('Usuario o contraseña incorrectos');
        } finally {
            setIsLoading(false);
        }
    };

    return (
        <div className="login-container" style={styles.container}>
            <motion.div
                initial={{ opacity: 0, y: 20 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ duration: 0.5 }}
                style={styles.card}
            >
                <h2 style={styles.title}>Iniciar Sesión</h2>
                <p style={styles.subtitle}>Proyección de Faena Avícola</p>

                <form onSubmit={handleSubmit} style={styles.form}>
                    <div style={styles.inputGroup}>
                        <label style={styles.label}>Usuario</label>
                        <input
                            type="text"
                            value={username}
                            onChange={(e) => setUsername(e.target.value)}
                            style={styles.input}
                            required
                        />
                    </div>

                    <div style={styles.inputGroup}>
                        <label style={styles.label}>Contraseña</label>
                        <input
                            type="password"
                            value={password}
                            onChange={(e) => setPassword(e.target.value)}
                            style={styles.input}
                            required
                        />
                    </div>

                    <motion.button
                        whileHover={{ scale: 1.02 }}
                        whileTap={{ scale: 0.98 }}
                        style={{ ...styles.button, opacity: isLoading ? 0.7 : 1 }}
                        type="submit"
                        disabled={isLoading}
                    >
                        {isLoading ? 'Ingresando...' : 'Ingresar'}
                    </motion.button>
                </form>
            </motion.div>
        </div>
    );
};

const styles = {
    container: {
        minHeight: '100vh',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        background: 'linear-gradient(135deg, #0f172a 0%, #1e293b 100%)',
        color: '#fff',
        fontFamily: 'Inter, sans-serif'
    },
    card: {
        background: 'rgba(255, 255, 255, 0.05)',
        backdropFilter: 'blur(10px)',
        borderRadius: '16px',
        padding: '40px',
        width: '100%',
        maxWidth: '400px',
        boxShadow: '0 4px 6px rgba(0, 0, 0, 0.1), 0 10px 15px rgba(0, 0, 0, 0.1)',
        border: '1px solid rgba(255, 255, 255, 0.1)'
    },
    title: {
        margin: '0 0 10px 0',
        fontSize: '28px',
        fontWeight: 'bold',
        textAlign: 'center',
        color: '#38bdf8'
    },
    subtitle: {
        margin: '0 0 30px 0',
        fontSize: '14px',
        textAlign: 'center',
        color: '#94a3b8'
    },
    form: {
        display: 'flex',
        flexDirection: 'column',
        gap: '20px'
    },
    inputGroup: {
        display: 'flex',
        flexDirection: 'column',
        gap: '8px'
    },
    label: {
        fontSize: '14px',
        color: '#cbd5e1'
    },
    input: {
        padding: '12px 16px',
        borderRadius: '8px',
        border: '1px solid rgba(255, 255, 255, 0.2)',
        background: 'rgba(0, 0, 0, 0.2)',
        color: '#fff',
        fontSize: '16px',
        outline: 'none',
        transition: 'border-color 0.2s'
    },
    button: {
        marginTop: '10px',
        padding: '14px',
        borderRadius: '8px',
        border: 'none',
        background: '#0284c7',
        color: '#fff',
        fontSize: '16px',
        fontWeight: 'bold',
        cursor: 'pointer',
        boxShadow: '0 4px 14px 0 rgba(0, 118, 255, 0.39)',
    }
};

export default Login;
