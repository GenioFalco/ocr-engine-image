import React, { useState, useEffect, useRef } from 'react';
import { useNavigate, useParams } from 'react-router-dom';
import api from '../api';
import { toast } from '../components/Toast';
import {
    Upload, X, FileText, Scale, Scan, CheckCircle, AlertCircle,
    RefreshCw, Loader2, History, ChevronRight, ArrowLeft
} from 'lucide-react';

// ── Module config ─────────────────────────────────────────────────────────────
const MODULES = {
    'closing-docs': {
        title: 'Закрывающие документы',
        Icon: FileText,
        color: 'text-sky-600',
        bg: 'bg-sky-50',
        border: 'border-sky-200',
        badge: 'bg-sky-100 text-sky-700',
    },
    'enforcement': {
        title: 'Исполнительные листы',
        Icon: Scale,
        color: 'text-violet-600',
        bg: 'bg-violet-50',
        border: 'border-violet-200',
        badge: 'bg-violet-100 text-violet-700',
    },
    'standard': {
        title: 'Стандартный модуль',
        Icon: Scan,
        color: 'text-emerald-600',
        bg: 'bg-emerald-50',
        border: 'border-emerald-200',
        badge: 'bg-emerald-100 text-emerald-700',
    },
};

const fmt = (bytes) => {
    if (bytes < 1024) return `${bytes} B`;
    if (bytes < 1048576) return `${(bytes / 1024).toFixed(1)} KB`;
    return `${(bytes / 1048576).toFixed(1)} MB`;
};

const statusIcon = (s) => {
    if (s === 'done')       return <CheckCircle className="w-4 h-4 text-emerald-500" />;
    if (s === 'error')      return <AlertCircle className="w-4 h-4 text-red-500" />;
    if (s === 'processing') return <Loader2 className="w-4 h-4 text-blue-500 animate-spin" />;
    return <div className="w-4 h-4 rounded-full border-2 border-slate-300" />;
};

const statusLabel = { queued: 'Очередь', processing: 'Обработка…', done: 'Готово', error: 'Ошибка' };

const UserDashboard = () => {
    const navigate = useNavigate();
    const { moduleId } = useParams();
    const module = MODULES[moduleId] || MODULES['closing-docs'];
    const { title, Icon, color, bg, border, badge } = module;

    const fileInputRef = useRef(null);
    const [dragOver, setDragOver] = useState(false);

    const [selectedFiles, setSelectedFiles] = useState([]);
    const [batch, setBatch]           = useState([]);
    const [uploading, setUploading]   = useState(false);

    const [history, setHistory]       = useState([]);
    const [histLoading, setHistLoading] = useState(true);
    const [jobNames, setJobNames]     = useState({});

    const fetchHistory = async () => {
        setHistLoading(true);
        try {
            const { data } = await api.get('/jobs');
            setHistory(data);
        } catch { }
        finally { setHistLoading(false); }
        try {
            setJobNames(JSON.parse(localStorage.getItem('ocr_job_names') || '{}'));
        } catch { }
    };
    useEffect(() => { fetchHistory(); }, []);

    // ── File selection ────────────────────────────────────────────────────────
    const addFiles = (files) => {
        const newItems = Array.from(files).map(file => ({
            id: Math.random().toString(36).slice(2), file,
        }));
        setSelectedFiles(prev => [...prev, ...newItems]);
    };

    const removeFile = (id) => setSelectedFiles(prev => prev.filter(f => f.id !== id));

    const onDrop = (e) => { e.preventDefault(); setDragOver(false); addFiles(e.dataTransfer.files); };

    // ── Upload ────────────────────────────────────────────────────────────────
    const handleUpload = async () => {
        if (!selectedFiles.length) return;
        setUploading(true);

        const initialBatch = selectedFiles.map(({ id, file }) => ({
            id, name: file.name, size: file.size, file, status: 'queued', jobId: null, error: null,
        }));
        setBatch(initialBatch);
        setSelectedFiles([]);

        const doneJobIds = [];
        let errorCount = 0;

        for (let i = 0; i < initialBatch.length; i++) {
            const item = initialBatch[i];
            setBatch(prev => prev.map(b => b.id === item.id ? { ...b, status: 'processing' } : b));

            try {
                const formData = new FormData();
                formData.append('file', item.file);
                formData.append('module', moduleId || 'standard');
                
                const { data } = await api.post('/process', formData, {
                    headers: { 'Content-Type': 'multipart/form-data' },
                });
                const jobId = data.job_id;
                doneJobIds.push(jobId);

                // Save filename to localStorage
                try {
                    const stored = JSON.parse(localStorage.getItem('ocr_job_names') || '{}');
                    stored[jobId] = item.name;
                    localStorage.setItem('ocr_job_names', JSON.stringify(stored));
                } catch { }

                setBatch(prev => prev.map(b => b.id === item.id ? { ...b, status: 'done', jobId } : b));
            } catch (err) {
                errorCount++;
                const msg = err.response?.data?.detail || 'Ошибка загрузки';
                setBatch(prev => prev.map(b => b.id === item.id ? { ...b, status: 'error', error: msg } : b));
            }
        }

        setUploading(false);
        fetchHistory();

        if (doneJobIds.length > 0 && errorCount === 0) {
            toast.success(`Готово! ${doneJobIds.length > 1 ? doneJobIds.length + ' файлов' : '1 файл'} распознан(о).`);
        } else if (doneJobIds.length > 0 && errorCount > 0) {
            toast.warning(`Распознано: ${doneJobIds.length}, с ошибкой: ${errorCount}`);
        } else if (errorCount > 0) {
            toast.error('Не удалось обработать файлы.');
        }

        if (doneJobIds.length === 1) {
            navigate(`/result/${doneJobIds[0]}`);
        } else if (doneJobIds.length > 1) {
            navigate(`/batch/${doneJobIds.join(',')}`);
        }
    };

    const allDone = batch.length > 0 && batch.every(b => b.status === 'done' || b.status === 'error');
    const doneIds = batch.filter(b => b.status === 'done').map(b => b.jobId);

    return (
        <div className="max-w-4xl mx-auto space-y-6">

            {/* ─── Module header ──────────────────────────────────────────── */}
            <div className="flex items-center gap-4">
                <button
                    onClick={() => navigate('/')}
                    className="flex items-center gap-1.5 text-sm text-slate-500 hover:text-slate-800 font-medium
                        px-3 py-2 rounded-lg border border-slate-200 bg-white hover:bg-slate-50 transition-colors shadow-sm"
                >
                    <ArrowLeft className="w-4 h-4" /> Модули
                </button>

                <div className="flex items-center gap-3">
                    <div className={`w-9 h-9 rounded-xl ${bg} ${border} border flex items-center justify-center`}>
                        <Icon className={`w-5 h-5 ${color}`} />
                    </div>
                    <div>
                        <h1 className="text-lg font-bold text-slate-900 leading-tight">{title}</h1>
                        <p className="text-xs text-slate-400">Загрузите PDF-файлы для распознавания</p>
                    </div>
                </div>
            </div>

            {/* ─── Upload zone ─────────────────────────────────────────────── */}
            {batch.length === 0 && (
                <div
                    onClick={() => !uploading && fileInputRef.current.click()}
                    onDragOver={(e) => { e.preventDefault(); setDragOver(true); }}
                    onDragLeave={() => setDragOver(false)}
                    onDrop={onDrop}
                    className={`relative border-2 border-dashed rounded-2xl p-10 text-center cursor-pointer transition-all
                        ${dragOver
                            ? `${border} ${bg} scale-[1.01]`
                            : 'border-slate-200 bg-white hover:border-slate-300 hover:bg-slate-50/40'
                        }`}
                >
                    <input
                        ref={fileInputRef}
                        type="file"
                        multiple
                        accept=".pdf,application/pdf"
                        className="hidden"
                        onChange={e => addFiles(e.target.files)}
                    />
                    <Upload className={`w-10 h-10 mx-auto mb-3 transition-colors ${dragOver ? color : 'text-slate-300'}`} />
                    <p className="text-base font-semibold text-slate-700">Перетащите файлы или нажмите для выбора</p>
                    <p className="text-sm text-slate-400 mt-1">Поддерживается: PDF • Можно выбрать несколько файлов сразу</p>
                </div>
            )}

            {/* ─── Selected files (before upload) ──────────────────────────── */}
            {selectedFiles.length > 0 && (
                <div className="bg-white rounded-2xl border border-slate-200 shadow-sm overflow-hidden">
                    <div className="px-5 py-4 border-b border-slate-100 flex items-center justify-between">
                        <p className="text-sm font-semibold text-slate-800">Выбрано файлов: {selectedFiles.length}</p>
                        <button onClick={() => fileInputRef.current.click()}
                            className={`text-xs font-medium hover:underline ${color}`}>+ Добавить ещё</button>
                    </div>
                    <ul className="divide-y divide-slate-50 max-h-72 overflow-y-auto">
                        {selectedFiles.map(({ id, file }) => (
                            <li key={id} className="flex items-center gap-3 px-5 py-3 hover:bg-slate-50/40">
                                <FileText className="w-4 h-4 text-slate-400 shrink-0" />
                                <div className="flex-1 min-w-0">
                                    <p className="text-sm font-medium text-slate-800 truncate">{file.name}</p>
                                    <p className="text-xs text-slate-400">{fmt(file.size)}</p>
                                </div>
                                <button onClick={() => removeFile(id)}
                                    className="p-1 rounded hover:bg-slate-100 text-slate-400 hover:text-rose-500 transition-colors">
                                    <X className="w-3.5 h-3.5" />
                                </button>
                            </li>
                        ))}
                    </ul>
                    <div className="px-5 py-4 bg-slate-50/40 border-t border-slate-100 flex items-center gap-3">
                        <button onClick={handleUpload}
                            className="flex items-center gap-2 px-5 py-2.5 bg-slate-900 text-white text-sm font-semibold
                                rounded-xl hover:bg-slate-700 transition-colors shadow-sm">
                            <Upload className="w-4 h-4" /> Распознать все ({selectedFiles.length})
                        </button>
                        <button onClick={() => setSelectedFiles([])}
                            className="text-sm text-slate-400 hover:text-slate-600">Очистить</button>
                    </div>
                </div>
            )}

            {/* ─── Batch progress ───────────────────────────────────────────── */}
            {batch.length > 0 && (
                <div className="bg-white rounded-2xl border border-slate-200 shadow-sm overflow-hidden">
                    <div className="px-5 py-4 border-b border-slate-100 flex items-center justify-between">
                        <p className="text-sm font-semibold text-slate-800">
                            Обработка пакета — {batch.filter(b => b.status === 'done').length}/{batch.length} готово
                        </p>
                        {allDone && doneIds.length > 0 && (
                            <button
                                onClick={() => doneIds.length === 1
                                    ? navigate(`/result/${doneIds[0]}`)
                                    : navigate(`/batch/${doneIds.join(',')}`)}
                                className="flex items-center gap-1.5 px-4 py-2 bg-emerald-600 text-white text-sm
                                    font-semibold rounded-lg hover:bg-emerald-700 transition-colors">
                                Открыть результаты <ChevronRight className="w-4 h-4" />
                            </button>
                        )}
                    </div>
                    <ul className="divide-y divide-slate-50 max-h-80 overflow-y-auto">
                        {batch.map(item => (
                            <li key={item.id} className="flex items-center gap-3 px-5 py-3">
                                {statusIcon(item.status)}
                                <div className="flex-1 min-w-0">
                                    <p className="text-sm font-medium text-slate-800 truncate">{item.name}</p>
                                    {item.error && <p className="text-xs text-red-500 mt-0.5">{item.error}</p>}
                                </div>
                                <span className={`text-xs font-medium px-2 py-0.5 rounded-full ${
                                    item.status === 'done'       ? 'bg-emerald-100 text-emerald-700' :
                                    item.status === 'error'      ? 'bg-red-100 text-red-600' :
                                    item.status === 'processing' ? 'bg-blue-100 text-blue-700' :
                                                                   'bg-slate-100 text-slate-500'}`}>
                                    {statusLabel[item.status]}
                                </span>
                                {item.status === 'done' && item.jobId && (
                                    <button onClick={() => navigate(`/result/${item.jobId}`)}
                                        className={`text-xs font-medium hover:underline ml-2 ${color}`}>
                                        Открыть
                                    </button>
                                )}
                            </li>
                        ))}
                    </ul>
                    {allDone && (
                        <div className="px-5 py-3 bg-slate-50/40 border-t border-slate-100 flex gap-3">
                            <button onClick={() => { setBatch([]); fetchHistory(); }}
                                className="text-sm text-slate-500 hover:text-slate-800 font-medium">← Новый пакет</button>
                        </div>
                    )}
                </div>
            )}

            {/* ─── History ──────────────────────────────────────────────────── */}
            {batch.length === 0 && (
                <div className="bg-white rounded-2xl border border-slate-200 shadow-sm overflow-hidden">
                    <div className="px-5 py-4 border-b border-slate-100 flex items-center justify-between">
                        <h2 className="text-sm font-semibold text-slate-800 flex items-center gap-2">
                            <History className="w-4 h-4 text-slate-400" /> История заданий
                        </h2>
                        <button onClick={fetchHistory}
                            className="text-xs text-slate-400 hover:text-slate-700 flex items-center gap-1">
                            <RefreshCw className="w-3 h-3" /> Обновить
                        </button>
                    </div>
                    {histLoading ? (
                        <div className="py-10 flex justify-center">
                            <RefreshCw className="w-5 h-5 text-primary animate-spin" />
                        </div>
                    ) : history.length === 0 ? (
                        <p className="py-10 text-center text-slate-400 italic text-sm">Загруженных документов нет</p>
                    ) : (
                        <ul className="divide-y divide-slate-50">
                            {history.map(job => (
                                <li key={job.id} onClick={() => navigate(`/result/${job.id}`)}
                                    className="flex items-center gap-3 px-5 py-3 hover:bg-slate-50/60 cursor-pointer transition-colors group">
                                    <FileText className="w-4 h-4 text-slate-300 shrink-0" />
                                    <div className="flex-1 min-w-0">
                                        <p className="text-sm font-medium text-slate-700 truncate">
                                            {jobNames[job.id] || (
                                                <span className="font-mono text-slate-400 text-xs">
                                                    {String(job.id).substring(0, 8)}…
                                                </span>
                                            )}
                                        </p>
                                        <p className="text-xs text-slate-400">{new Date(job.created_at).toLocaleString('ru-RU')}</p>
                                    </div>
                                    <span className={`text-xs font-medium px-2 py-0.5 rounded-full ${
                                        job.status === 'done'  ? 'bg-emerald-100 text-emerald-700' :
                                        job.status === 'error' ? 'bg-red-100 text-red-600' :
                                                                 'bg-blue-100 text-blue-700'}`}>
                                        {statusLabel[job.status] || job.status}
                                    </span>
                                    <ChevronRight className="w-4 h-4 text-slate-300 group-hover:text-slate-500 transition-colors" />
                                </li>
                            ))}
                        </ul>
                    )}
                </div>
            )}
        </div>
    );
};

export default UserDashboard;
