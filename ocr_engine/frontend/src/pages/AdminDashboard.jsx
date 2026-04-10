import React, { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import api from '../api';
import { toast } from '../components/Toast';
import {
    Users, UserPlus, CheckCircle, AlertCircle, RefreshCw,
    FileText, List, Activity, Cpu, Trash2, Play, Plus, X,
    ChevronDown, ChevronRight, ChevronLeft, Settings, Check, Copy,
    PieChart, Star
} from 'lucide-react';

// ─── Sidebar nav config ───────────────────────────────────────────────────────
const NAV = [
    { id: 'analytics',label: 'Аналитика',       icon: PieChart },
    { id: 'users',    label: 'Пользователи',    icon: Users },
    { id: 'jobs',     label: 'Все задания',      icon: Activity },
    { id: 'doctypes', label: 'Типы документов',  icon: FileText },
    { id: 'contracts',label: 'Контракты',        icon: List },
    { id: 'models',   label: 'Модели ИИ',        icon: Cpu },
    { id: 'apikeys',  label: 'API Ключи',        icon: Settings },
];

// ─── Reusable atoms ───────────────────────────────────────────────────────────
const Btn = ({ onClick, variant = 'primary', size = 'md', children, disabled, type = 'button' }) => {
    const base = 'inline-flex items-center gap-1.5 font-medium rounded-lg transition-colors disabled:opacity-50 cursor-pointer';
    const sizes = { sm: 'px-3 py-1.5 text-xs', md: 'px-4 py-2 text-sm' };
    const variants = {
        primary: 'bg-slate-900 text-white hover:bg-slate-700',
        danger:  'bg-red-50 text-red-600 hover:bg-red-100 border border-red-200',
        ghost:   'bg-white text-slate-600 hover:bg-slate-50 border border-slate-200',
        success: 'bg-emerald-600 text-white hover:bg-emerald-700',
    };
    return <button type={type} className={`${base} ${sizes[size]} ${variants[variant]}`} onClick={onClick} disabled={disabled}>{children}</button>;
};

const Badge = ({ value, map }) => {
    const cfg = map[value] || { label: value, cls: 'bg-slate-100 text-slate-500' };
    return <span className={`inline-flex items-center px-2 py-0.5 rounded text-xs font-semibold ${cfg.cls}`}>{cfg.label}</span>;
};

const roleBadge = {
    admin: { label: 'Админ',    cls: 'bg-rose-100 text-rose-700' },
    user:  { label: 'Юзер',     cls: 'bg-sky-100 text-sky-700' },
    robot: { label: '🤖 Робот', cls: 'bg-violet-100 text-violet-700' },
};
const statusBadge = {
    done:       { label: 'Готово',    cls: 'bg-emerald-100 text-emerald-700' },
    processing: { label: 'В работе',  cls: 'bg-blue-100 text-blue-700' },
    error:      { label: 'Ошибка',    cls: 'bg-red-100 text-red-700' },
    pending:    { label: 'Ожидание',  cls: 'bg-amber-100 text-amber-700' },
};

// ─── DataTable with pagination ────────────────────────────────────────────────
const PAGE_SIZE = 10;

const DataTable = ({ cols, rows, emptyText = 'Нет данных', onRowClick }) => {
    const [page, setPage] = useState(1);
    const totalPages = Math.ceil(rows.length / PAGE_SIZE);
    const sliced = rows.slice((page - 1) * PAGE_SIZE, page * PAGE_SIZE);

    return (
        <div>
            <div className="overflow-x-auto">
                <table className="w-full text-sm text-left text-slate-600">
                    <thead className="bg-slate-50 text-xs text-slate-500 uppercase tracking-wider border-b border-slate-100">
                        <tr>{cols.map(c => <th key={c.key} className="px-5 py-3">{c.label}</th>)}</tr>
                    </thead>
                    <tbody className="divide-y divide-slate-50">
                        {sliced.length === 0
                            ? <tr><td colSpan={cols.length} className="px-5 py-10 text-center text-slate-400 italic">{emptyText}</td></tr>
                            : sliced.map((row, i) => (
                                <tr
                                    key={i}
                                    onClick={() => onRowClick?.(row)}
                                    className={`hover:bg-slate-50/60 transition-colors ${onRowClick ? 'cursor-pointer' : ''}`}
                                >
                                    {cols.map(c => <td key={c.key} className="px-5 py-3">{c.render ? c.render(row) : row[c.key]}</td>)}
                                </tr>
                            ))
                        }
                    </tbody>
                </table>
            </div>

            {totalPages > 1 && (
                <div className="px-5 py-3 border-t border-slate-100 flex items-center justify-between bg-slate-50/40">
                    <p className="text-xs text-slate-400">
                        {(page - 1) * PAGE_SIZE + 1}–{Math.min(page * PAGE_SIZE, rows.length)} из {rows.length}
                    </p>
                    <div className="flex items-center gap-1">
                        <button
                            onClick={() => setPage(p => Math.max(1, p - 1))}
                            disabled={page === 1}
                            className="p-1.5 rounded-md hover:bg-slate-200 disabled:opacity-30 disabled:cursor-not-allowed transition-colors"
                        >
                            <ChevronLeft className="w-4 h-4 text-slate-600" />
                        </button>
                        {Array.from({ length: totalPages }, (_, i) => i + 1)
                            .filter(p => p === 1 || p === totalPages || Math.abs(p - page) <= 1)
                            .reduce((acc, p, idx, arr) => {
                                if (idx > 0 && arr[idx - 1] !== p - 1) acc.push('...');
                                acc.push(p);
                                return acc;
                            }, [])
                            .map((p, idx) => p === '...' ? (
                                <span key={`dots-${idx}`} className="px-1 text-slate-400 text-xs">…</span>
                            ) : (
                                <button
                                    key={p}
                                    onClick={() => setPage(p)}
                                    className={`min-w-[28px] h-7 rounded-md text-xs font-medium transition-colors
                                        ${page === p ? 'bg-slate-900 text-white' : 'text-slate-600 hover:bg-slate-200'}`}
                                >
                                    {p}
                                </button>
                            ))}
                        <button
                            onClick={() => setPage(p => Math.min(totalPages, p + 1))}
                            disabled={page === totalPages}
                            className="p-1.5 rounded-md hover:bg-slate-200 disabled:opacity-30 disabled:cursor-not-allowed transition-colors"
                        >
                            <ChevronRight className="w-4 h-4 text-slate-600" />
                        </button>
                    </div>
                </div>
            )}
        </div>
    );
};

const SectionWrap = ({ title, action, children }) => (
    <div>
        <div className="px-6 py-4 border-b border-slate-100 flex items-center justify-between bg-slate-50/40">
            <h2 className="text-base font-semibold text-slate-800">{title}</h2>
            {action}
        </div>
        {children}
    </div>
);

// ─── Section: Users ───────────────────────────────────────────────────────────
const UsersSection = () => {
    const [users, setUsers] = useState([]);
    const [loading, setLoading] = useState(true);
    const [showForm, setShowForm] = useState(false);
    const [form, setForm] = useState({ username: '', email: '', password: '', role: 'user' });

    const load = async () => { setLoading(true); const { data } = await api.get('/admin/users'); setUsers(data); setLoading(false); };
    useEffect(() => { load(); }, []);

    const submit = async (e) => {
        e.preventDefault();
        try {
            await api.post('/auth/register', form);
            toast.success(`Пользователь «${form.username}» (${form.role}) создан.`);
            setForm({ username: '', email: '', password: '', role: 'user' });
            setShowForm(false);
            load();
        } catch (err) {
            toast.error(err.response?.data?.detail || 'Ошибка создания');
        }
    };

    const cols = [
        { key: 'id',       label: 'ID',     render: r => <span className="font-mono text-xs text-slate-400">{r.id}</span> },
        { key: 'username', label: 'Логин',  render: r => <span className="font-semibold text-slate-900">{r.username}</span> },
        { key: 'email',    label: 'Email',  render: r => r.email || <span className="text-slate-300 italic">—</span> },
        { key: 'role',     label: 'Роль',   render: r => <Badge value={r.role} map={roleBadge} /> },
        {
            key: 'is_active', label: 'Статус', render: r => r.is_active
                ? <span className="text-xs text-emerald-600 font-medium">✓ Активен</span>
                : <span className="text-xs text-slate-400">Заблокирован</span>
        },
    ];

    return (
        <SectionWrap
            title={`Пользователи (${users.length})`}
            action={<Btn size="sm" variant={showForm ? 'ghost' : 'primary'} onClick={() => setShowForm(!showForm)}>
                {showForm ? <><X className="w-3.5 h-3.5" />Отмена</> : <><UserPlus className="w-3.5 h-3.5" />Создать</>}
            </Btn>}
        >
            {showForm && (
                <div className="p-6 bg-sky-50/40 border-b border-slate-100">
                    <form onSubmit={submit} className="max-w-2xl bg-white p-5 rounded-xl border border-slate-200 shadow-sm space-y-4">
                        <h3 className="font-semibold text-slate-800">Новый пользователь</h3>
                        <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                            {[['Логин *', 'text', 'username', 'ivan_petrov', true], ['Email', 'email', 'email', 'ivan@company.ru', false]].map(([lbl, type, key, ph, req]) => (
                                <div key={key}>
                                    <label className="block text-xs font-semibold text-slate-500 uppercase mb-1">{lbl}</label>
                                    <input type={type} required={req} value={form[key]}
                                        onChange={e => setForm(f => ({ ...f, [key]: e.target.value }))}
                                        placeholder={ph} className="w-full p-2.5 bg-slate-50 border border-slate-200 rounded-lg text-sm focus:ring-2 focus:ring-primary outline-none" />
                                </div>
                            ))}
                            <div>
                                <label className="block text-xs font-semibold text-slate-500 uppercase mb-1">Пароль *</label>
                                <input type="text" required minLength={4} value={form.password}
                                    onChange={e => setForm(f => ({ ...f, password: e.target.value }))}
                                    placeholder="Минимум 4 символа" className="w-full p-2.5 bg-slate-50 border border-slate-200 rounded-lg text-sm focus:ring-2 focus:ring-primary outline-none font-mono" />
                            </div>
                            <div>
                                <label className="block text-xs font-semibold text-slate-500 uppercase mb-1">Роль *</label>
                                <select value={form.role} onChange={e => setForm(f => ({ ...f, role: e.target.value }))}
                                    className="w-full p-2.5 bg-slate-50 border border-slate-200 rounded-lg text-sm focus:ring-2 focus:ring-primary outline-none">
                                    <option value="user">👤 Пользователь — доступ к интерфейсу</option>
                                    <option value="robot">🤖 Робот — только API доступ</option>
                                </select>
                            </div>
                        </div>
                        <Btn type="submit" variant="primary">Зарегистрировать</Btn>
                    </form>
                </div>
            )}
            {loading
                ? <div className="py-12 flex justify-center"><RefreshCw className="w-6 h-6 text-primary animate-spin" /></div>
                : <DataTable cols={cols} rows={users} emptyText="Пользователей нет" />}
        </SectionWrap>
    );
};

// ─── Section: All Jobs ────────────────────────────────────────────────────────
const JobsSection = () => {
    const navigate = useNavigate();
    const [jobs, setJobs] = useState([]);
    const [loading, setLoading] = useState(true);
    const load = async () => { setLoading(true); const { data } = await api.get('/admin/jobs'); setJobs(data); setLoading(false); };
    useEffect(() => { load(); }, []);

    const cols = [
        { key: 'id',        label: 'ID',      render: r => <span className="font-mono text-[11px] text-slate-400">{String(r.id).substring(0, 8)}…</span> },
        { key: 'user_id',   label: 'User',    render: r => <span className="font-mono text-xs">{r.user_id}</span> },
        { key: 'mode',      label: 'Режим',   render: r => <span className="text-xs font-bold uppercase text-slate-500">{r.mode}</span> },
        { key: 'status',    label: 'Статус',  render: r => <Badge value={r.status} map={statusBadge} /> },
        { key: 'created_at',label: 'Создано', render: r => <span className="text-xs text-slate-400">{new Date(r.created_at).toLocaleString('ru-RU')}</span> },
        {
            key: 'error_message', label: 'Ошибка', render: r => r.error_message
                ? <span className="text-xs text-red-500 max-w-[200px] block truncate" title={r.error_message}>{r.error_message}</span>
                : <span className="text-slate-300">—</span>
        },
        {
            key: 'open', label: '', render: r => r.status === 'done' && (
                <span className="text-xs text-primary font-medium">Открыть ↗</span>
            )
        },
    ];

    return (
        <SectionWrap title={`Все задания (${jobs.length})`} action={<Btn size="sm" variant="ghost" onClick={load}><RefreshCw className="w-3.5 h-3.5" />Обновить</Btn>}>
            {loading
                ? <div className="py-12 flex justify-center"><RefreshCw className="w-6 h-6 text-primary animate-spin" /></div>
                : <DataTable
                    cols={cols}
                    rows={jobs}
                    emptyText="Заданий нет"
                    onRowClick={(row) => row.status === 'done' && navigate(`/result/${row.id}`)}
                />}
        </SectionWrap>
    );
};

// ─── Section: Document Types ──────────────────────────────────────────────────
const DocTypesSection = () => {
    const [items, setItems] = useState([]);
    const [loading, setLoading] = useState(true);
    const [showForm, setShowForm] = useState(false);
    const [form, setForm] = useState({ name: '', description: '' });

    const load = async () => { setLoading(true); const { data } = await api.get('/admin/document_types'); setItems(data); setLoading(false); };
    useEffect(() => { load(); }, []);

    const submit = async (e) => {
        e.preventDefault();
        try {
            await api.post('/admin/document_types', form);
            toast.success(`Тип «${form.name}» создан.`);
            setForm({ name: '', description: '' });
            setShowForm(false);
            load();
        } catch (err) {
            toast.error(err.response?.data?.detail || 'Ошибка создания типа');
        }
    };

    const del = async (id, name) => {
        if (!confirm(`Удалить тип «${name}»?`)) return;
        try {
            await api.delete(`/admin/document_types/${id}`);
            toast.success(`Тип «${name}» удалён.`);
            load();
        } catch (err) {
            toast.error(err.response?.data?.detail || 'Нельзя удалить — есть связанные контракты');
        }
    };

    const cols = [
        { key: 'id',          label: 'ID' },
        { key: 'name',        label: 'Название',  render: r => <span className="font-semibold text-slate-900">{r.name}</span> },
        { key: 'description', label: 'Описание',  render: r => r.description || <span className="text-slate-300 italic">—</span> },
        { key: 'actions',     label: '',           render: r => <Btn onClick={() => del(r.id, r.name)} variant="danger" size="sm"><Trash2 className="w-3 h-3" />Удалить</Btn> },
    ];

    return (
        <SectionWrap title="Типы документов" action={<Btn size="sm" variant={showForm ? 'ghost' : 'primary'} onClick={() => setShowForm(!showForm)}>
            {showForm ? <><X className="w-3.5 h-3.5" />Отмена</> : <><Plus className="w-3.5 h-3.5" />Добавить</>}
        </Btn>}>
            {showForm && (
                <div className="p-6 bg-sky-50/40 border-b border-slate-100">
                    <form onSubmit={submit} className="max-w-lg bg-white p-5 rounded-xl border border-slate-200 shadow-sm space-y-4">
                        <h3 className="font-semibold text-slate-800">Новый тип документа</h3>
                        {[['Название *', 'name', 'Например: invoice_sf', true], ['Описание', 'description', 'Счёт-фактура', false]].map(([lbl, key, ph, req]) => (
                            <div key={key}>
                                <label className="block text-xs font-semibold text-slate-500 uppercase mb-1">{lbl}</label>
                                <input required={req} value={form[key]} onChange={e => setForm(f => ({ ...f, [key]: e.target.value }))}
                                    placeholder={ph} className="w-full p-2.5 bg-slate-50 border border-slate-200 rounded-lg text-sm focus:ring-2 focus:ring-primary outline-none" />
                            </div>
                        ))}
                        <Btn type="submit" variant="primary">Создать тип</Btn>
                    </form>
                </div>
            )}
            {loading
                ? <div className="py-12 flex justify-center"><RefreshCw className="w-6 h-6 text-primary animate-spin" /></div>
                : <DataTable cols={cols} rows={items} emptyText="Типов нет" />}
        </SectionWrap>
    );
};

// ─── Section: Contracts ───────────────────────────────────────────────────────
const ContractsSection = () => {
    const [items, setItems] = useState([]);
    const [loading, setLoading] = useState(true);
    const [showForm, setShowForm] = useState(false);
    const [expanded, setExpanded] = useState(null);
    const [form, setForm] = useState({ document_type_name: '', json_schema: '{\n  \n}', is_default: false });

    const load = async () => { setLoading(true); const { data } = await api.get('/admin/contracts'); setItems(data); setLoading(false); };
    useEffect(() => { load(); }, []);

    const submit = async (e) => {
        e.preventDefault();
        let schema;
        try { schema = JSON.parse(form.json_schema); } catch { toast.error('Некорректный JSON!'); return; }
        try {
            await api.post('/admin/contracts', { ...form, json_schema: schema });
            toast.success('Контракт создан.');
            setShowForm(false);
            load();
        } catch (err) {
            toast.error(err.response?.data?.detail || 'Ошибка создания контракта');
        }
    };

    const del = async (id) => {
        if (!confirm('Удалить контракт?')) return;
        try {
            await api.delete(`/admin/contracts/${id}`);
            toast.success('Контракт удалён.');
            load();
        } catch {
            toast.error('Не удалось удалить контракт.');
        }
    };

    return (
        <SectionWrap title="JSON Контракты (схемы полей)" action={<Btn size="sm" variant={showForm ? 'ghost' : 'primary'} onClick={() => setShowForm(!showForm)}>
            {showForm ? <><X className="w-3.5 h-3.5" />Отмена</> : <><Plus className="w-3.5 h-3.5" />Добавить</>}
        </Btn>}>
            {showForm && (
                <div className="p-6 bg-sky-50/40 border-b border-slate-100">
                    <form onSubmit={submit} className="max-w-2xl bg-white p-5 rounded-xl border border-slate-200 shadow-sm space-y-4">
                        <h3 className="font-semibold text-slate-800">Новый контракт</h3>
                        <div>
                            <label className="block text-xs font-semibold text-slate-500 uppercase mb-1">Тип документа *</label>
                            <input required value={form.document_type_name} onChange={e => setForm(f => ({ ...f, document_type_name: e.target.value }))}
                                placeholder="invoice_sf" className="w-full p-2.5 bg-slate-50 border border-slate-200 rounded-lg text-sm focus:ring-2 focus:ring-primary outline-none" />
                        </div>
                        <div>
                            <label className="block text-xs font-semibold text-slate-500 uppercase mb-1">JSON Схема *</label>
                            <textarea required rows={10} value={form.json_schema} onChange={e => setForm(f => ({ ...f, json_schema: e.target.value }))}
                                className="w-full p-2.5 bg-slate-50 border border-slate-200 rounded-lg text-sm font-mono focus:ring-2 focus:ring-primary outline-none" />
                        </div>
                        <label className="flex items-center gap-2 text-sm cursor-pointer">
                            <input type="checkbox" checked={form.is_default} onChange={e => setForm(f => ({ ...f, is_default: e.target.checked }))} className="rounded" />
                            Использовать по умолчанию
                        </label>
                        <Btn type="submit" variant="primary">Сохранить контракт</Btn>
                    </form>
                </div>
            )}
            {loading
                ? <div className="py-12 flex justify-center"><RefreshCw className="w-6 h-6 text-primary animate-spin" /></div>
                : items.length === 0
                    ? <p className="p-10 text-center text-slate-400 italic">Контрактов нет.</p>
                    : <div className="divide-y divide-slate-100">
                        {items.map(item => (
                            <div key={item.id}>
                                <div className="px-5 py-3.5 flex items-center justify-between hover:bg-slate-50/50">
                                    <button onClick={() => setExpanded(expanded === item.id ? null : item.id)} className="flex items-center gap-2 text-sm font-semibold text-slate-800">
                                        {expanded === item.id ? <ChevronDown className="w-4 h-4 text-slate-400" /> : <ChevronRight className="w-4 h-4 text-slate-400" />}
                                        #{item.id} — {item.document_type}
                                    </button>
                                    <Btn onClick={() => del(item.id)} variant="danger" size="sm"><Trash2 className="w-3 h-3" />Удалить</Btn>
                                </div>
                                {expanded === item.id && (
                                    <div className="px-5 pb-4">
                                        <pre className="bg-slate-900 text-emerald-400 rounded-xl p-4 text-xs overflow-x-auto leading-relaxed">{JSON.stringify(item.schema, null, 2)}</pre>
                                    </div>
                                )}
                            </div>
                        ))}
                    </div>}
        </SectionWrap>
    );
};

// ─── Section: AI Models ───────────────────────────────────────────────────────
const ModelsSection = () => {
    const [items, setItems] = useState([]);
    const [loading, setLoading] = useState(true);
    const [showForm, setShowForm] = useState(false);
    const [form, setForm] = useState({ name: '', provider: 'gigachat', model_name: '', api_key: '', temperature: 0.1, max_tokens: 4096 });

    const load = async () => { setLoading(true); const { data } = await api.get('/admin/models'); setItems(data); setLoading(false); };
    useEffect(() => { load(); }, []);

    const submit = async (e) => {
        e.preventDefault();
        try {
            await api.post('/admin/models', form);
            toast.success('Модель добавлена.');
            setShowForm(false);
            load();
        } catch (err) {
            toast.error(err.response?.data?.detail || 'Ошибка добавления модели');
        }
    };

    const del = async (id) => {
        if (!confirm('Удалить модель?')) return;
        try { await api.delete(`/admin/models/${id}`); toast.success('Модель удалена.'); load(); }
        catch { toast.error('Ошибка удаления модели.'); }
    };

    const activate = async (id) => {
        try { await api.post(`/admin/models/${id}/activate`); toast.success('Модель активирована.'); load(); }
        catch { toast.error('Не удалось активировать.'); }
    };

    const cols = [
        { key: 'name',       label: 'Название',   render: r => <span className="font-semibold text-slate-900">{r.name}</span> },
        { key: 'provider',   label: 'Провайдер',  render: r => <span className="uppercase text-xs font-bold text-slate-500">{r.provider}</span> },
        { key: 'model_name', label: 'Модель',     render: r => <span className="font-mono text-xs">{r.model_name}</span> },
        { key: 'api_key',    label: 'Ключ',       render: r => <span className="font-mono text-xs text-slate-400">{r.api_key}</span> },
        {
            key: 'is_active', label: 'Статус', render: r => r.is_active
                ? <span className="text-xs font-bold text-emerald-600 bg-emerald-50 px-2 py-0.5 rounded-full">● Активная</span>
                : <span className="text-xs text-slate-400">Неактивна</span>
        },
        {
            key: 'actions', label: '', render: r => (
                <div className="flex items-center gap-2">
                    {!r.is_active && <Btn onClick={() => activate(r.id)} variant="success" size="sm"><Play className="w-3 h-3" />Активировать</Btn>}
                    <Btn onClick={() => del(r.id)} variant="danger" size="sm"><Trash2 className="w-3 h-3" /></Btn>
                </div>
            )
        },
    ];

    return (
        <SectionWrap title="Модели ИИ" action={<Btn size="sm" variant={showForm ? 'ghost' : 'primary'} onClick={() => setShowForm(!showForm)}>
            {showForm ? <><X className="w-3.5 h-3.5" />Отмена</> : <><Plus className="w-3.5 h-3.5" />Добавить</>}
        </Btn>}>
            {showForm && (
                <div className="p-6 bg-sky-50/40 border-b border-slate-100">
                    <form onSubmit={submit} className="max-w-2xl bg-white p-5 rounded-xl border border-slate-200 shadow-sm space-y-4">
                        <h3 className="font-semibold text-slate-800">Новая модель</h3>
                        <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                            {[['Название *', 'name', 'GigaChat-Pro'], ['API Ключ *', 'api_key', 'sk-...']].map(([lbl, key, ph]) => (
                                <div key={key}>
                                    <label className="block text-xs font-semibold text-slate-500 uppercase mb-1">{lbl}</label>
                                    <input required value={form[key]} onChange={e => setForm(f => ({ ...f, [key]: e.target.value }))}
                                        placeholder={ph} className="w-full p-2.5 bg-slate-50 border border-slate-200 rounded-lg text-sm focus:ring-2 focus:ring-primary outline-none" />
                                </div>
                            ))}
                            <div>
                                <label className="block text-xs font-semibold text-slate-500 uppercase mb-1">Провайдер *</label>
                                <select value={form.provider} onChange={e => setForm(f => ({ ...f, provider: e.target.value }))}
                                    className="w-full p-2.5 bg-slate-50 border border-slate-200 rounded-lg text-sm focus:ring-2 focus:ring-primary outline-none">
                                    <option value="gigachat">GigaChat</option>
                                    <option value="openrouter">OpenRouter</option>
                                    <option value="qwen">Qwen</option>
                                </select>
                            </div>
                            <div>
                                <label className="block text-xs font-semibold text-slate-500 uppercase mb-1">Имя модели *</label>
                                <input required value={form.model_name} onChange={e => setForm(f => ({ ...f, model_name: e.target.value }))}
                                    placeholder="GigaChat-Pro" className="w-full p-2.5 bg-slate-50 border border-slate-200 rounded-lg text-sm focus:ring-2 focus:ring-primary outline-none" />
                            </div>
                        </div>
                        <div className="grid grid-cols-2 gap-4">
                            {[['Temperature', 'temperature', 0.01, 0, 2], ['Max Tokens', 'max_tokens', 1, 1, 32000]].map(([lbl, key, step, min, max]) => (
                                <div key={key}>
                                    <label className="block text-xs font-semibold text-slate-500 uppercase mb-1">{lbl}</label>
                                    <input type="number" step={step} min={min} max={max} value={form[key]}
                                        onChange={e => setForm(f => ({ ...f, [key]: key === 'temperature' ? parseFloat(e.target.value) : parseInt(e.target.value) }))}
                                        className="w-full p-2.5 bg-slate-50 border border-slate-200 rounded-lg text-sm focus:ring-2 focus:ring-primary outline-none" />
                                </div>
                            ))}
                        </div>
                        <Btn type="submit" variant="primary">Добавить модель</Btn>
                    </form>
                </div>
            )}
            {loading
                ? <div className="py-12 flex justify-center"><RefreshCw className="w-6 h-6 text-primary animate-spin" /></div>
                : <DataTable cols={cols} rows={items} emptyText="Моделей нет" />}
        </SectionWrap>
    );
};

// ─── Section: API Keys ────────────────────────────────────────────────────────
const ApiKeysSection = () => {
    const [keys, setKeys] = useState([]);
    const [users, setUsers] = useState([]);
    const [loading, setLoading] = useState(true);
    const [showForm, setShowForm] = useState(false);
    const [form, setForm] = useState({ user_id: '', label: '' });
    const [newKey, setNewKey] = useState(null);
    const [copiedField, setCopiedField] = useState(null);

    const copy = (field, text) => {
        navigator.clipboard.writeText(text);
        setCopiedField(field);
        setTimeout(() => setCopiedField(null), 2000);
    };

    const load = async () => {
        setLoading(true);
        const [keysRes, usersRes] = await Promise.all([api.get('/auth/admin/api_keys'), api.get('/admin/users')]);
        setKeys(keysRes.data);
        setUsers(usersRes.data.filter(u => u.role === 'robot'));
        setLoading(false);
    };
    useEffect(() => { load(); }, []);

    const generate = async (e) => {
        e.preventDefault();
        try {
            const { data } = await api.post('/auth/admin/api_keys', form);
            setNewKey(data);
            setShowForm(false);
            load();
            toast.info('Ключ создан. Сохраните Client Secret — он показывается только один раз!');
        } catch (err) {
            toast.error(err.response?.data?.detail || 'Ошибка генерации ключа');
        }
    };

    const revoke = async (id, clientId) => {
        if (!confirm(`Отозвать ключ ${clientId}? Робот потеряет доступ.`)) return;
        try {
            await api.delete(`/auth/admin/api_keys/${id}`);
            toast.success('Ключ отозван.');
            load();
        } catch {
            toast.error('Не удалось отозвать ключ.');
        }
    };

    const cols = [
        { key: 'client_id',    label: 'Client ID',              render: r => <span className="font-mono text-xs text-slate-700">{r.client_id}</span> },
        { key: 'label',        label: 'Метка',                  render: r => <span className="text-sm text-slate-600">{r.label}</span> },
        { key: 'username',     label: 'Учётка',                 render: r => <span className="font-semibold text-violet-700">{r.username}</span> },
        {
            key: 'is_active', label: 'Статус', render: r => r.is_active
                ? <span className="text-xs font-bold text-emerald-600">● Активен</span>
                : <span className="text-xs text-slate-400">Отозван</span>
        },
        {
            key: 'last_used_at', label: 'Последнее использование', render: r => r.last_used_at
                ? <span className="text-xs text-slate-400">{new Date(r.last_used_at).toLocaleString('ru-RU')}</span>
                : <span className="text-slate-300 italic text-xs">никогда</span>
        },
        {
            key: 'actions', label: '', render: r => r.is_active &&
                <Btn onClick={() => revoke(r.id, r.client_id)} variant="danger" size="sm"><Trash2 className="w-3 h-3" />Отозвать</Btn>
        },
    ];

    return (
        <SectionWrap title="API Ключи (Client ID / Secret)" action={
            <Btn size="sm" variant={showForm ? 'ghost' : 'primary'} onClick={() => setShowForm(!showForm)}>
                {showForm ? <><X className="w-3.5 h-3.5" />Отмена</> : <><Plus className="w-3.5 h-3.5" />Выдать ключ</>}
            </Btn>
        }>
            {/* One-time secret banner */}
            {newKey && (
                <div className="m-6 p-5 bg-amber-50 border border-amber-300 rounded-xl space-y-3">
                    <div className="flex items-center gap-2 text-amber-800 font-semibold text-sm">
                        ⚠️ Сохраните данные — Client Secret показывается ТОЛЬКО ОДИН РАЗ!
                    </div>
                    <div className="space-y-2">
                        {[['Client ID', 'client_id', newKey.client_id], ['Client Secret', 'client_secret', newKey.client_secret]].map(([lbl, field, val]) => (
                            <div key={field}>
                                <p className="text-xs font-semibold text-amber-700 uppercase mb-1">{lbl}</p>
                                <div className="flex items-center gap-2">
                                    <code className="flex-1 bg-white border border-amber-200 rounded-lg px-3 py-2 text-xs font-mono text-slate-800 break-all">{val}</code>
                                    <button onClick={() => copy(field, val)}
                                        className="p-2 rounded-lg bg-amber-100 hover:bg-amber-200 text-amber-700 transition-colors shrink-0">
                                        {copiedField === field ? <Check className="w-4 h-4 text-emerald-600" /> : <Copy className="w-4 h-4" />}
                                    </button>
                                </div>
                            </div>
                        ))}
                    </div>
                    <button onClick={() => setNewKey(null)} className="text-xs text-amber-600 hover:text-amber-800 font-medium underline">Я сохранил — закрыть</button>
                </div>
            )}

            {showForm && (
                <div className="p-6 bg-sky-50/40 border-b border-slate-100">
                    <form onSubmit={generate} className="max-w-lg bg-white p-5 rounded-xl border border-slate-200 shadow-sm space-y-4">
                        <h3 className="font-semibold text-slate-800">Выдать API ключ роботу</h3>
                        <div>
                            <label className="block text-xs font-semibold text-slate-500 uppercase mb-1">Учётка робота *</label>
                            <select required value={form.user_id} onChange={e => setForm(f => ({ ...f, user_id: e.target.value }))}
                                className="w-full p-2.5 bg-slate-50 border border-slate-200 rounded-lg text-sm focus:ring-2 focus:ring-primary outline-none">
                                <option value="">— выберите учётку —</option>
                                {users.map(u => <option key={u.id} value={u.id}>🤖 {u.username}</option>)}
                            </select>
                            {users.length === 0 && <p className="text-xs text-slate-400 mt-1">Нет учёток с ролью «Робот». Создайте сначала в разделе Пользователи.</p>}
                        </div>
                        <div>
                            <label className="block text-xs font-semibold text-slate-500 uppercase mb-1">Метка (необязательно)</label>
                            <input value={form.label} onChange={e => setForm(f => ({ ...f, label: e.target.value }))}
                                placeholder="Например: Sherpa RPA Production" className="w-full p-2.5 bg-slate-50 border border-slate-200 rounded-lg text-sm focus:ring-2 focus:ring-primary outline-none" />
                        </div>
                        <Btn type="submit" variant="primary">Сгенерировать ключ</Btn>
                    </form>
                </div>
            )}

            {loading
                ? <div className="py-12 flex justify-center"><RefreshCw className="w-6 h-6 text-primary animate-spin" /></div>
                : <DataTable cols={cols} rows={keys} emptyText="API ключей нет. Создайте первый." />}
        </SectionWrap>
    );
};

// ─── Analytics Section ────────────────────────────────────────────────────────
const AnalyticsSection = () => {
    const [stats, setStats] = useState(null);
    const [loading, setLoading] = useState(true);

    const load = async () => {
        try {
            setLoading(true);
            const { data } = await api.get('/admin/analytics');
            setStats(data);
        } catch {
            toast.error('Ошибка загрузки дашборда');
        } finally {
            setLoading(false);
        }
    };

    useEffect(() => { load(); }, []);

    if (loading) return <div className="p-12 flex justify-center"><RefreshCw className="w-8 h-8 text-primary animate-spin" /></div>;
    if (!stats) return null;

    return (
        <div className="p-6 space-y-6">
            {/* Top Cards */}
            <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
                <div className="bg-white p-5 rounded-2xl border border-slate-200 shadow-sm">
                    <div className="text-slate-500 font-semibold mb-1 text-sm uppercase tracking-wide">Всего документов</div>
                    <div className="text-3xl font-black text-slate-800">{stats.total_jobs}</div>
                </div>
                <div className="bg-white p-5 rounded-2xl border border-slate-200 shadow-sm relative overflow-hidden">
                    <div className="text-slate-500 font-semibold mb-1 text-sm uppercase tracking-wide">Ошибок</div>
                    <div className="text-3xl font-black text-red-600">{stats.failed_jobs}</div>
                    {stats.failed_jobs > 0 && <div className="absolute right-4 top-4 text-xs font-bold text-red-500 bg-red-100 px-2 py-1 rounded">Внимание</div>}
                </div>
                <div className="bg-white p-5 rounded-2xl border border-slate-200 shadow-sm">
                    <div className="text-slate-500 font-semibold mb-1 text-sm uppercase tracking-wide flex items-center gap-1.5">
                        <Star className="w-4 h-4 text-amber-500" />
                        Средняя оценка
                    </div>
                    <div className="text-3xl font-black text-slate-800">{stats.overall_rating} <span className="text-sm font-semibold text-slate-400">/ 5.0</span></div>
                </div>
            </div>

            <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
                {/* Распределение по модулям */}
                <div className="bg-white p-6 rounded-2xl border border-slate-200 shadow-sm">
                    <h3 className="text-lg font-bold text-slate-800 mb-6 flex items-center gap-2">
                        <Activity className="w-5 h-5 text-indigo-500" />
                        Статистика по модулям
                    </h3>
                    <div className="space-y-5">
                        {stats.module_stats.length === 0 && <p className="text-sm text-slate-400 italic">Нет данных</p>}
                        {stats.module_stats.map((m, i) => {
                            const pct = stats.total_jobs > 0 ? (m.count / stats.total_jobs) * 100 : 0;
                            return (
                                <div key={i}>
                                    <div className="flex justify-between items-end mb-1">
                                        <span className="text-sm font-semibold text-slate-700 capitalize">{m.name}</span>
                                        <div className="text-right">
                                            <span className="text-sm font-bold text-slate-900">{m.count}</span>
                                            <span className="text-xs text-slate-500 ml-2">(⭐️ {m.avg_rating})</span>
                                        </div>
                                    </div>
                                    <div className="h-2 w-full bg-slate-100 rounded-full overflow-hidden">
                                        <div className="h-full bg-indigo-500 rounded-full transition-all duration-500" style={{ width: `${pct}%` }}></div>
                                    </div>
                                </div>
                            );
                        })}
                    </div>
                </div>

                {/* Оценки */}
                <div className="bg-white p-6 rounded-2xl border border-slate-200 shadow-sm">
                    <h3 className="text-lg font-bold text-slate-800 mb-6 flex items-center gap-2">
                        <Star className="w-5 h-5 text-amber-500" />
                        Распределение оценок
                    </h3>
                    <div className="space-y-4">
                        {[5, 4, 3, 2, 1].map(r => {
                            const strR = String(r);
                            const count = stats.rating_distribution[strR] || 0;
                            // Check if rating_distribution is empty to avoid NaN
                            const allCounts = Object.values(stats.rating_distribution);
                            const maxCount = allCounts.length > 0 ? Math.max(...allCounts, 1) : 1;
                            const pct = (count / maxCount) * 100;
                            return (
                                <div key={r} className="flex items-center gap-3">
                                    <div className="flex items-center gap-1 w-12 shrink-0">
                                        <span className="font-bold text-slate-700">{r}</span>
                                        <Star className="w-3.5 h-3.5 text-amber-400 fill-amber-400" />
                                    </div>
                                    <div className="flex-1 h-3 bg-slate-100 rounded-full overflow-hidden">
                                        <div className={`h-full rounded-full transition-all duration-500 ${r >= 4 ? 'bg-emerald-500' : r === 3 ? 'bg-amber-400' : 'bg-red-500'}`} style={{ width: `${pct}%` }}></div>
                                    </div>
                                    <div className="w-10 text-right text-sm font-semibold text-slate-600">{count}</div>
                                </div>
                            );
                        })}
                    </div>
                </div>
            </div>
        </div>
    );
};

// ─── Main AdminDashboard ──────────────────────────────────────────────────────
const SECTIONS = {
    analytics: AnalyticsSection, users: UsersSection, jobs: JobsSection, doctypes: DocTypesSection,
    contracts: ContractsSection, models: ModelsSection, apikeys: ApiKeysSection,
};

const AdminDashboard = () => {
    const [active, setActive] = useState('analytics');
    const ActiveSection = SECTIONS[active];

    return (
        <div className="flex gap-0 -mx-4 sm:-mx-6 lg:-mx-8 -my-8 min-h-[calc(100vh-64px)]">
            {/* Sidebar */}
            <aside className="w-56 shrink-0 bg-white border-r border-slate-200 flex flex-col py-6 px-3">
                <div className="px-3 mb-6">
                    <p className="text-xs font-bold uppercase tracking-widest text-slate-400">Панель администратора</p>
                </div>
                <nav className="flex flex-col gap-1">
                    {NAV.map(item => {
                        const Icon = item.icon;
                        const isActive = active === item.id;
                        return (
                            <button key={item.id} onClick={() => setActive(item.id)}
                                className={`flex items-center gap-3 px-3 py-2.5 rounded-lg text-sm font-medium transition-colors text-left w-full
                                    ${isActive ? 'bg-slate-900 text-white shadow-sm' : 'text-slate-600 hover:bg-slate-100 hover:text-slate-900'}`}>
                                <Icon className="w-4 h-4 shrink-0" />
                                {item.label}
                            </button>
                        );
                    })}
                </nav>
            </aside>

            {/* Main content */}
            <main className="flex-1 min-w-0 bg-slate-50/40">
                <div className="bg-white border-b border-slate-200 px-6 py-4">
                    <h1 className="text-lg font-bold text-slate-900">{NAV.find(n => n.id === active)?.label}</h1>
                </div>
                <div className="bg-white min-h-full shadow-sm">
                    <ActiveSection />
                </div>
            </main>
        </div>
    );
};

export default AdminDashboard;
