import React, { useState, useRef, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { LayoutDashboard, LogOut, User, ChevronDown } from 'lucide-react';

const Navbar = ({ role, onLogout }) => {
    const navigate = useNavigate();
    const [dropdownOpen, setDropdownOpen] = useState(false);
    const dropdownRef = useRef(null);
    const username = localStorage.getItem('username') || 'Пользователь';

    // Close dropdown on outside click
    useEffect(() => {
        const handler = (e) => {
            if (dropdownRef.current && !dropdownRef.current.contains(e.target)) {
                setDropdownOpen(false);
            }
        };
        document.addEventListener('mousedown', handler);
        return () => document.removeEventListener('mousedown', handler);
    }, []);

    return (
        <nav className="bg-white border-b border-slate-200 sticky top-0 z-50 shadow-sm">
            <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
                <div className="flex justify-between h-16">
                    {/* Logo */}
                    <div className="flex items-center gap-3 cursor-pointer" onClick={() => navigate('/')}>
                        <img src="/logo.svg" alt="Logo" className="h-8 object-contain" />
                        <span className="font-bold text-lg text-slate-800 tracking-tight">CES OSR IDP</span>
                        {role === 'admin' && (
                            <span className="ml-2 px-2 py-0.5 bg-rose-100 text-rose-700 text-xs font-bold rounded-md border border-rose-200">
                                ADMIN
                            </span>
                        )}
                    </div>

                    {/* Right side */}
                    <div className="flex items-center gap-3">
                        <button
                            onClick={() => navigate('/')}
                            className="hidden sm:flex items-center gap-1.5 text-slate-500 hover:text-slate-900 font-medium px-3 py-2 rounded-md transition-colors text-sm"
                        >
                            <LayoutDashboard className="w-4 h-4" />
                            Дашборд
                        </button>

                        {/* User Dropdown */}
                        <div className="relative" ref={dropdownRef}>
                            <button
                                onClick={() => setDropdownOpen(!dropdownOpen)}
                                className="flex items-center gap-2 px-3 py-2 rounded-lg border border-slate-200 bg-slate-50 hover:bg-slate-100 transition-colors text-sm font-medium text-slate-700"
                            >
                                <div className="w-6 h-6 rounded-full bg-primary flex items-center justify-center text-white text-xs font-bold">
                                    {username.charAt(0).toUpperCase()}
                                </div>
                                <span className="hidden sm:block max-w-[120px] truncate">{username}</span>
                                <ChevronDown className={`w-3.5 h-3.5 text-slate-400 transition-transform ${dropdownOpen ? 'rotate-180' : ''}`} />
                            </button>

                            {dropdownOpen && (
                                <div className="absolute right-0 mt-2 w-52 bg-white rounded-xl border border-slate-200 shadow-lg py-1 z-50 animate-in fade-in slide-in-from-top-2 duration-150">
                                    <div className="px-4 py-3 border-b border-slate-100">
                                        <p className="text-xs text-slate-400 font-medium uppercase tracking-wide">Вы вошли как</p>
                                        <p className="text-sm font-semibold text-slate-800 mt-0.5 truncate">{username}</p>
                                        <p className="text-xs text-slate-400 mt-0.5">{role === 'admin' ? 'Администратор' : 'Пользователь'}</p>
                                    </div>

                                    <div className="py-1">
                                        <button
                                            onClick={() => { setDropdownOpen(false); onLogout(); }}
                                            className="w-full flex items-center gap-2.5 px-4 py-2.5 text-sm text-rose-600 hover:bg-rose-50 transition-colors text-left font-medium"
                                        >
                                            <LogOut className="w-4 h-4" />
                                            Выйти
                                        </button>
                                    </div>
                                </div>
                            )}
                        </div>
                    </div>
                </div>
            </div>
        </nav>
    );
};

export default Navbar;
