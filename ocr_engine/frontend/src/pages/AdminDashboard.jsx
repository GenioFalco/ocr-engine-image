import React, { useState, useEffect } from 'react';
import api from '../api';
import { Users, UserPlus, Shield, CheckCircle, AlertCircle, RefreshCw, Mail, Lock } from 'lucide-react';

const AdminDashboard = () => {
    const [users, setUsers] = useState([]);
    const [loading, setLoading] = useState(true);

    // New User Form State
    const [showAddForm, setShowAddForm] = useState(false);
    const [newUsername, setNewUsername] = useState('');
    const [newEmail, setNewEmail] = useState('');
    const [newPassword, setNewPassword] = useState('');
    const [formError, setFormError] = useState('');
    const [formSuccess, setFormSuccess] = useState('');

    const fetchUsers = async () => {
        try {
            setLoading(true);
            const { data } = await api.get('/admin/users');
            setUsers(data);
        } catch (err) {
            console.error('Failed to load users:', err);
        } finally {
            setLoading(false);
        }
    };

    useEffect(() => {
        fetchUsers();
    }, []);

    const handleRegisterUser = async (e) => {
        e.preventDefault();
        setFormError('');
        setFormSuccess('');

        try {
            await api.post('/auth/register', {
                username: newUsername,
                email: newEmail,
                password: newPassword
            });
            setFormSuccess(`Пользователь ${newUsername} успешно создан.`);
            setNewUsername('');
            setNewEmail('');
            setNewPassword('');
            setShowAddForm(false);
            fetchUsers(); // Refresh the list
        } catch (err) {
            setFormError(err.response?.data?.detail || 'Ошибка при создании пользователя');
        }
    };

    return (
        <div className="space-y-8 animate-in fade-in duration-500">
            <div className="flex items-center justify-between">
                <div>
                    <h1 className="text-3xl font-bold tracking-tight text-slate-900">Панель Управления</h1>
                    <p className="text-slate-500 mt-1">Управление пользователями, схемами и мониторинг логов.</p>
                </div>
            </div>

            <div className="bg-white rounded-2xl shadow-sm border border-slate-100 overflow-hidden">
                <div className="p-6 border-b border-slate-100 flex items-center justify-between bg-slate-50/50">
                    <h2 className="text-lg font-semibold text-slate-800 flex items-center gap-2">
                        <Users className="w-5 h-5 text-primary" />
                        Пользователи Системы
                    </h2>
                    <button
                        onClick={() => setShowAddForm(!showAddForm)}
                        className="px-4 py-2 bg-slate-900 text-white text-sm font-medium rounded-lg hover:bg-slate-800 transition-colors flex items-center gap-2"
                    >
                        <UserPlus className="w-4 h-4" />
                        {showAddForm ? 'Отмена' : 'Создать пользователя'}
                    </button>
                </div>

                {/* Form to Add New User */}
                {showAddForm && (
                    <div className="p-6 border-b border-slate-100 bg-sky-50/30">
                        <form onSubmit={handleRegisterUser} className="max-w-2xl bg-white p-6 rounded-xl border border-slate-200 shadow-sm">
                            <h3 className="font-semibold text-slate-800 mb-4">Регистрация нового профиля</h3>

                            {formError && (
                                <div className="mb-4 p-3 bg-red-50 text-red-600 rounded-lg text-sm border border-red-100 flex items-center gap-2">
                                    <AlertCircle className="w-4 h-4" /> {formError}
                                </div>
                            )}

                            <div className="grid grid-cols-1 md:grid-cols-2 gap-4 mb-4">
                                <div>
                                    <label className="block text-xs font-semibold text-slate-500 uppercase tracking-wider mb-1">Логин</label>
                                    <input
                                        type="text"
                                        required
                                        value={newUsername}
                                        onChange={(e) => setNewUsername(e.target.value)}
                                        className="w-full p-2.5 bg-slate-50 border border-slate-200 rounded text-sm focus:ring-2 focus:ring-primary focus:border-primary outline-none transition-all"
                                        placeholder="Например: Ivan_Ivanov"
                                    />
                                </div>
                                <div>
                                    <label className="block text-xs font-semibold text-slate-500 uppercase tracking-wider mb-1">Email</label>
                                    <input
                                        type="email"
                                        value={newEmail}
                                        onChange={(e) => setNewEmail(e.target.value)}
                                        className="w-full p-2.5 bg-slate-50 border border-slate-200 rounded text-sm focus:ring-2 focus:ring-primary focus:border-primary outline-none transition-all"
                                        placeholder="ivan@company.ru"
                                    />
                                </div>
                            </div>
                            <div className="mb-6">
                                <label className="block text-xs font-semibold text-slate-500 uppercase tracking-wider mb-1">Пароль</label>
                                <input
                                    type="text"
                                    required
                                    minLength={4}
                                    value={newPassword}
                                    onChange={(e) => setNewPassword(e.target.value)}
                                    className="w-full p-2.5 bg-slate-50 border border-slate-200 rounded text-sm focus:ring-2 focus:ring-primary focus:border-primary outline-none transition-all font-mono"
                                    placeholder="Минимум 4 символа"
                                />
                            </div>
                            <button type="submit" className="w-full py-2.5 bg-primary text-white text-sm font-medium rounded-lg hover:bg-sky-600 transition-colors shadow-sm focus:ring-4 focus:ring-sky-100">
                                Зарегистрировать (Права: Пользователь)
                            </button>
                        </form>
                    </div>
                )}

                {formSuccess && (
                    <div className="m-6 p-4 bg-emerald-50 text-emerald-700 rounded-xl border border-emerald-100 text-sm flex items-center justify-between">
                        <span className="flex items-center gap-2"><CheckCircle className="w-5 h-5" /> {formSuccess}</span>
                        <button onClick={() => setFormSuccess('')} className="text-emerald-700 hover:text-emerald-900 font-bold">&times;</button>
                    </div>
                )}

                <div className="overflow-x-auto">
                    {loading ? (
                        <div className="p-12 flex justify-center">
                            <RefreshCw className="w-6 h-6 text-primary animate-spin" />
                        </div>
                    ) : (
                        <table className="w-full text-left text-sm text-slate-600">
                            <thead className="bg-slate-50 border-b border-slate-200 text-slate-500 uppercase text-xs font-semibold tracking-wider">
                                <tr>
                                    <th scope="col" className="px-6 py-4">ID</th>
                                    <th scope="col" className="px-6 py-4">Логин</th>
                                    <th scope="col" className="px-6 py-4">Email</th>
                                    <th scope="col" className="px-6 py-4 text-center">Роль</th>
                                </tr>
                            </thead>
                            <tbody className="divide-y divide-slate-100">
                                {users.map((user) => (
                                    <tr key={user.id} className="hover:bg-slate-50/50 transition-colors">
                                        <td className="px-6 py-4 font-mono text-xs text-slate-400">
                                            {user.id}
                                        </td>
                                        <td className="px-6 py-4 font-medium text-slate-900">
                                            {user.username}
                                        </td>
                                        <td className="px-6 py-4">
                                            {user.email || <span className="text-slate-300 italic">не указан</span>}
                                        </td>
                                        <td className="px-6 py-4 flex justify-center">
                                            {user.role === 'admin' ? (
                                                <span className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-md text-xs font-semibold bg-red-100 text-red-700 border border-red-200">
                                                    <Shield className="w-3.5 h-3.5" /> Админ
                                                </span>
                                            ) : (
                                                <span className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-md text-xs font-medium bg-slate-100 text-slate-600">
                                                    Юзер
                                                </span>
                                            )}
                                        </td>
                                    </tr>
                                ))}
                            </tbody>
                        </table>
                    )}
                </div>
            </div>
        </div>
    );
};

export default AdminDashboard;
