import React, { useState, useEffect } from 'react';
import { BrowserRouter as Router, Routes, Route, Navigate, useNavigate } from 'react-router-dom';
import Login from './pages/Login';
import ModuleSelect from './pages/ModuleSelect';
import UserDashboard from './pages/UserDashboard';
import AdminDashboard from './pages/AdminDashboard';
import ResultViewer from './pages/ResultViewer';
import BatchViewer from './pages/BatchViewer';
import RobotPortal from './pages/RobotPortal';
import Navbar from './components/Navbar';
import { ToastContainer } from './components/Toast';

// ── Animated 404 page ─────────────────────────────────────────────────────────
const NotFound = () => {
    const navigate = useNavigate();
    const [glitch, setGlitch] = useState(false);

    useEffect(() => {
        const interval = setInterval(() => {
            setGlitch(true);
            setTimeout(() => setGlitch(false), 200);
        }, 2500 + Math.random() * 2000);
        return () => clearInterval(interval);
    }, []);

    return (
        <div className="flex flex-col items-center justify-center min-h-[80vh] select-none overflow-hidden">
            <style>{`
                @keyframes scan {
                    0%   { top: 0%;   opacity: 0.6; }
                    50%  { opacity: 1; }
                    100% { top: 100%; opacity: 0.6; }
                }
                @keyframes flicker {
                    0%,100% { opacity: 1; }
                    50%     { opacity: 0.4; }
                }
                @keyframes glitch-1 {
                    0%   { clip-path: inset(10% 0 80% 0); transform: translate(-4px, 0); }
                    25%  { clip-path: inset(60% 0 10% 0); transform: translate(4px, 0);  }
                    50%  { clip-path: inset(30% 0 50% 0); transform: translate(-2px, 0); }
                    75%  { clip-path: inset(70% 0 5%  0); transform: translate(3px, 0);  }
                    100% { clip-path: inset(10% 0 80% 0); transform: translate(0, 0);    }
                }
                @keyframes glitch-2 {
                    0%   { clip-path: inset(80% 0 5%  0); transform: translate(4px, 0);  }
                    25%  { clip-path: inset(10% 0 70% 0); transform: translate(-4px, 0); }
                    50%  { clip-path: inset(50% 0 30% 0); transform: translate(2px, 0);  }
                    75%  { clip-path: inset(5%  0 60% 0); transform: translate(-3px, 0); }
                    100% { clip-path: inset(80% 0 5%  0); transform: translate(0, 0);    }
                }
                .glitch-layer-1 { animation: glitch-1 0.18s steps(1) infinite; }
                .glitch-layer-2 { animation: glitch-2 0.18s steps(1) infinite; }
            `}</style>

            {/* OCR scan frame */}
            <div className="relative w-72 h-72 mb-8">
                {['top-0 left-0 border-t-2 border-l-2', 'top-0 right-0 border-t-2 border-r-2',
                  'bottom-0 left-0 border-b-2 border-l-2', 'bottom-0 right-0 border-b-2 border-r-2'].map((cls, i) => (
                    <div key={i} className={`absolute w-6 h-6 border-sky-400 ${cls}`} />
                ))}

                {/* Scanning line */}
                <div
                    className="absolute left-0 right-0 h-0.5 bg-sky-400/60"
                    style={{ animation: 'scan 2.5s linear infinite' }}
                />

                {/* Main 404 text */}
                <div className="absolute inset-0 flex items-center justify-center">
                    <div className="relative">
                        <div
                            className="text-[7rem] font-black leading-none tracking-tighter text-slate-800"
                            style={glitch ? { animation: 'flicker 0.1s steps(1) 2' } : {}}
                        >
                            404
                        </div>
                        {glitch && (
                            <>
                                <div className="absolute inset-0 text-[7rem] font-black leading-none tracking-tighter text-sky-400 glitch-layer-1">
                                    404
                                </div>
                                <div className="absolute inset-0 text-[7rem] font-black leading-none tracking-tighter text-rose-400 glitch-layer-2">
                                    404
                                </div>
                            </>
                        )}
                    </div>
                </div>

                {/* Grid overlay */}
                <div
                    className="absolute inset-0 opacity-[0.04]"
                    style={{
                        backgroundImage: 'linear-gradient(#0ea5e9 1px, transparent 1px), linear-gradient(90deg, #0ea5e9 1px, transparent 1px)',
                        backgroundSize: '24px 24px',
                    }}
                />
            </div>

            <div className="text-center space-y-2 mb-8">
                <div className="inline-flex items-center gap-2 px-3 py-1 bg-rose-50 border border-rose-200 rounded-full mb-3">
                    <span className="w-1.5 h-1.5 rounded-full bg-rose-500 animate-pulse" />
                    <span className="text-xs font-mono font-semibold text-rose-600 uppercase tracking-widest">
                        DOCUMENT NOT FOUND
                    </span>
                </div>
                <h1 className="text-xl font-bold text-slate-800">Страница не существует</h1>
                <p className="text-sm text-slate-400 font-mono">CES OSR IDP не смог распознать этот адрес</p>
            </div>

            <div className="flex items-center gap-3">
                <button
                    onClick={() => navigate(-1)}
                    className="px-4 py-2 text-sm font-medium text-slate-600 bg-white border border-slate-200 rounded-lg hover:bg-slate-50 transition-colors shadow-sm"
                >
                    ← Назад
                </button>
                <button
                    onClick={() => navigate('/')}
                    className="px-5 py-2 text-sm font-semibold text-white bg-slate-900 rounded-lg hover:bg-slate-700 transition-colors shadow-sm"
                >
                    На главную
                </button>
            </div>
        </div>
    );
};

// ── Main App ──────────────────────────────────────────────────────────────────
function App() {
    const [isAuthenticated, setIsAuthenticated] = useState(false);
    const [role, setRole] = useState(null);

    useEffect(() => {
        const token = localStorage.getItem('token');
        const userRole = localStorage.getItem('role');
        if (token) {
            setIsAuthenticated(true);
            setRole(userRole);
        }
    }, []);

    const handleLogin = (userRole) => {
        setIsAuthenticated(true);
        setRole(userRole);
    };

    const handleLogout = () => {
        localStorage.removeItem('token');
        localStorage.removeItem('role');
        localStorage.removeItem('username');
        setIsAuthenticated(false);
        setRole(null);
    };

    const renderHome = () => {
        if (!isAuthenticated) return <Navigate to="/login" />;
        if (role === 'admin') return <AdminDashboard />;
        if (role === 'robot') return <RobotPortal onLogout={handleLogout} />;
        return <ModuleSelect />;
    };

    return (
        <Router>
            {/* Global toast notifications — rendered outside main layout */}
            <ToastContainer />

            <div className="min-h-screen bg-surface flex flex-col">
                {isAuthenticated && role !== 'robot' && <Navbar role={role} onLogout={handleLogout} />}

                <main className={`flex-1 w-full ${role !== 'robot' ? 'max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8' : ''}`}>
                    <Routes>
                        <Route path="/login" element={
                            !isAuthenticated ? <Login onLogin={handleLogin} /> : <Navigate to="/" />
                        } />

                        <Route path="/" element={renderHome()} />

                        <Route path="/result/:jobId" element={
                            isAuthenticated ? <ResultViewer /> : <Navigate to="/login" />
                        } />

                        <Route path="/batch/:jobIds" element={
                            isAuthenticated ? <BatchViewer /> : <Navigate to="/login" />
                        } />

                        {/* Module workspace */}
                        <Route path="/module/:moduleId" element={
                            isAuthenticated ? <UserDashboard /> : <Navigate to="/login" />
                        } />

                        {/* 404 catch-all */}
                        <Route path="*" element={<NotFound />} />
                    </Routes>
                </main>
            </div>
        </Router>
    );
}

export default App;
