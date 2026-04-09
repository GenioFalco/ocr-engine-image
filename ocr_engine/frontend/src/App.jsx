import React, { useState, useEffect } from 'react';
import { BrowserRouter as Router, Routes, Route, Navigate } from 'react-router-dom';
import Login from './pages/Login';
import UserDashboard from './pages/UserDashboard';
import AdminDashboard from './pages/AdminDashboard';
import ResultViewer from './pages/ResultViewer';
import BatchViewer from './pages/BatchViewer';
import RobotPortal from './pages/RobotPortal';
import Navbar from './components/Navbar';

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
    return <UserDashboard />;
  };

  return (
    <Router>
      <div className="min-h-screen bg-surface flex flex-col">
        {/* Hide navbar for robot portal (it has its own header) */}
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
          </Routes>
        </main>
      </div>
    </Router>
  );
}

export default App;
