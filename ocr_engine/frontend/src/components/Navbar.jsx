import React from 'react';
import { useNavigate } from 'react-router-dom';
import { LogOut, LayoutDashboard, FileText } from 'lucide-react';

const Navbar = ({ role, onLogout }) => {
    const navigate = useNavigate();

    return (
        <nav className="bg-white border-b border-slate-200 sticky top-0 z-50">
            <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
                <div className="flex justify-between h-16">
                    <div className="flex items-center gap-2 cursor-pointer" onClick={() => navigate('/')}>
                        <div className="w-8 h-8 bg-primary rounded-lg flex items-center justify-center text-white font-bold shadow-sm">
                            OCR
                        </div>
                        <span className="font-bold text-xl text-slate-900 tracking-tight">Engine</span>
                        {role === 'admin' && (
                            <span className="ml-2 px-2 py-1 bg-red-100 text-red-700 text-xs font-semibold rounded-md">
                                ADMIN
                            </span>
                        )}
                    </div>

                    <div className="flex items-center gap-4">
                        <button
                            onClick={() => navigate('/')}
                            className="flex items-center gap-2 text-slate-600 hover:text-slate-900 font-medium px-3 py-2 rounded-md transition-colors"
                        >
                            <LayoutDashboard className="w-4 h-4" />
                            Дашборд
                        </button>
                        <button
                            onClick={onLogout}
                            className="flex items-center gap-2 text-red-600 hover:text-red-700 hover:bg-red-50 font-medium px-3 py-2 rounded-md transition-colors"
                        >
                            <LogOut className="w-4 h-4" />
                            Выход
                        </button>
                    </div>
                </div>
            </div>
        </nav>
    );
};

export default Navbar;
