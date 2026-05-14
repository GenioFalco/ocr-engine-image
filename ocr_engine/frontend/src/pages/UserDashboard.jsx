import React, { useState, useEffect, useRef } from 'react';
import { useNavigate, useParams } from 'react-router-dom';
import api from '../api';
import { toast } from '../components/Toast';
import {
    Upload, X, FileText, Scale, Scan, CheckCircle, AlertCircle,
    RefreshCw, Loader2, History, ChevronRight, ArrowLeft, AlignLeft, Copy,
    Package,
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
    'text-extract': {
        title: 'Извлечение текста',
        Icon: AlignLeft,
        color: 'text-orange-600',
        bg: 'bg-orange-50',
        border: 'border-orange-200',
        badge: 'bg-orange-100 text-orange-700',
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

// ── Batch localStorage helpers ────────────────────────────────────────────────
const BATCHES_KEY = 'ocr_batches';

const saveBatch = (jobIds, module, created_at) => {
    try {
        const batches = JSON.parse(localStorage.getItem(BATCHES_KEY) || '[]');
        batches.unshift({ id: `batch-${Date.now()}`, jobIds, module, created_at });
        localStorage.setItem(BATCHES_KEY, JSON.stringify(batches.slice(0, 100)));
    } catch { }
};

const loadBatches = () => {
    try { return JSON.parse(localStorage.getItem(BATCHES_KEY) || '[]'); } catch { return []; }
};

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

    // ── History state ─────────────────────────────────────────────────────────
    const [histJobs, setHistJobs]       = useState([]);   // current page items
    const [histTotal, setHistTotal]     = useState(0);
    const [histPages, setHistPages]     = useState(1);
    const [histPage, setHistPage]       = useState(1);
    const [histLoading, setHistLoading] = useState(true);
    const [jobNames, setJobNames]         = useState({});
    const [textResult, setTextResult]     = useState(null); // для модуля text-extract
    const [batches, setBatches]           = useState([]);   // from localStorage
    const [filterModule, setFilterModule] = useState('');
    const [filterDate, setFilterDate]     = useState('');

    const PER_PAGE = 50;

    const fetchHistory = async (page = histPage, mod = filterModule, date = filterDate) => {
        setHistLoading(true);
        try {
            const params = new URLSearchParams({ page, per_page: PER_PAGE });
            if (mod)  params.set('module', mod);
            if (date) params.set('date', date);
            const { data } = await api.get(`/jobs?${params}`);
            setHistJobs(data.items || []);
            setHistTotal(data.total || 0);
            setHistPages(data.pages || 1);
        } catch { }
        finally { setHistLoading(false); }
        try {
            setJobNames(JSON.parse(localStorage.getItem('ocr_job_names') || '{}'));
        } catch { }
        setBatches(loadBatches());
    };

    useEffect(() => { fetchHistory(1, filterModule, filterDate); }, []);

    const applyFilters = () => {
        setHistPage(1);
        fetchHistory(1, filterModule, filterDate);
    };

    const resetFilters = () => {
        setFilterModule('');
        setFilterDate('');
        setHistPage(1);
        fetchHistory(1, '', '');
    };

    const goToPage = (p) => {
        setHistPage(p);
        fetchHistory(p, filterModule, filterDate);
    };

    // ── Build unified history items (batches + individual) ───────────────────
    const historyItems = React.useMemo(() => {
        if (!histJobs.length) return [];
        const jobMap = Object.fromEntries(histJobs.map(j => [j.id, j]));
        const items = [];
        const addedBatchIds = new Set();

        for (const job of histJobs) {
            const parentBatch = batches.find(b => b.jobIds.includes(job.id));
            if (parentBatch) {
                if (!addedBatchIds.has(parentBatch.id)) {
                    addedBatchIds.add(parentBatch.id);
                    const batchJobs = parentBatch.jobIds.map(id => jobMap[id]).filter(Boolean);
                    const allDone  = batchJobs.length > 0 && batchJobs.every(j => j.status === 'done');
                    const hasError = batchJobs.some(j => j.status === 'error');
                    const batchStatus = allDone ? 'done' : hasError ? 'error' : 'processing';
                    items.push({
                        type: 'batch',
                        batch: parentBatch,
                        status: batchStatus,
                        date: job.created_at,
                        count: parentBatch.jobIds.length,
                    });
                }
            } else {
                items.push({ type: 'job', job });
            }
        }
        return items;
    }, [histJobs, batches]);

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
        setTextResult(null);

        const initialBatch = selectedFiles.map(({ id, file }) => ({
            id, name: file.name, size: file.size, file, status: 'queued', jobId: null, error: null,
        }));
        setBatch(initialBatch);
        setSelectedFiles([]);

        const doneJobIds = [];
        let errorCount = 0;
        const uploadedAt = new Date().toISOString();

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
            // Save batch to localStorage so history can group them
            saveBatch(doneJobIds, moduleId || 'standard', uploadedAt);
            navigate(`/batch/${doneJobIds.join(',')}?module=${moduleId || 'standard'}`);
        }
    };

    const allDone = batch.length > 0 && batch.every(b => b.status === 'done' || b.status === 'error');
    const doneIds = batch.filter(b => b.status === 'done').map(b => b.jobId);

    // ── Результат извлечения текста ───────────────────────────────────────────
    if (textResult) {
        return (
            <div className="max-w-4xl mx-auto space-y-4">
                <div className="flex items-center gap-4">
                    <button
                        onClick={() => setTextResult(null)}
                        className="flex items-center gap-1.5 text-sm text-slate-500 hover:text-slate-800 font-medium
                            px-3 py-2 rounded-lg border border-slate-200 bg-white hover:bg-slate-50 transition-colors shadow-sm"
                    >
                        <ArrowLeft className="w-4 h-4" /> Назад
                    </button>
                    <div>
                        <h1 className="text-lg font-bold text-slate-900">{textResult.filename}</h1>
                        <p className="text-xs text-slate-400">{textResult.total_pages} стр. · Метод: OCR + нативный текст</p>
                    </div>
                    <button
                        onClick={() => { navigator.clipboard.writeText(textResult.full_text); toast.success('Скопировано!'); }}
                        className="ml-auto flex items-center gap-1.5 text-sm font-medium px-3 py-2 rounded-lg
                            bg-orange-50 border border-orange-200 text-orange-700 hover:bg-orange-100 transition-colors"
                    >
                        <Copy className="w-4 h-4" /> Копировать всё
                    </button>
                </div>

                {textResult.pages.map(p => (
                    <div key={p.page} className="bg-white border border-slate-200 rounded-xl overflow-hidden">
                        <div className="flex items-center justify-between px-4 py-2 bg-slate-50 border-b border-slate-200">
                            <span className="text-xs font-semibold text-slate-500 uppercase tracking-wider">
                                Страница {p.page}
                            </span>
                            <span className={`text-[10px] font-medium px-2 py-0.5 rounded-full ${
                                p.method === 'native'
                                    ? 'bg-emerald-100 text-emerald-700'
                                    : 'bg-orange-100 text-orange-700'
                            }`}>
                                {p.method === 'native' ? 'Нативный текст' : 'OCR (Tesseract)'}
                            </span>
                        </div>
                        <pre className="p-4 text-sm text-slate-700 whitespace-pre-wrap font-mono leading-relaxed">
                            {p.text || <span className="text-slate-300 italic">Текст не обнаружен</span>}
                        </pre>
                    </div>
                ))}
            </div>
        );
    }

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
                                    : navigate(`/batch/${doneIds.join(',')}?module=${moduleId || 'standard'}`)}
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
                    {/* Header */}
                    <div className="px-5 py-3.5 border-b border-slate-100 flex items-center justify-between">
                        <h2 className="text-sm font-semibold text-slate-800 flex items-center gap-2">
                            <History className="w-4 h-4 text-slate-400" />
                            История заданий
                            {histTotal > 0 && (
                                <span className="text-xs font-normal text-slate-400">— всего {histTotal}</span>
                            )}
                        </h2>
                        <button onClick={() => fetchHistory(histPage, filterModule, filterDate)}
                            className="text-xs text-slate-400 hover:text-slate-700 flex items-center gap-1">
                            <RefreshCw className="w-3 h-3" /> Обновить
                        </button>
                    </div>

                    {/* ── Filters ── */}
                    <div className="px-5 py-3 bg-slate-50/60 border-b border-slate-100 flex flex-wrap items-end gap-3">
                        {/* Module filter */}
                        <div className="flex flex-col gap-1">
                            <label className="text-[10px] font-semibold uppercase tracking-wider text-slate-400">Модуль</label>
                            <select
                                value={filterModule}
                                onChange={e => setFilterModule(e.target.value)}
                                className="text-xs border border-slate-200 rounded-lg px-2.5 py-1.5 bg-white text-slate-700 focus:outline-none focus:ring-1 focus:ring-primary"
                            >
                                <option value="">Все модули</option>
                                {Object.entries(MODULES).map(([key, m]) => (
                                    <option key={key} value={key}>{m.title}</option>
                                ))}
                            </select>
                        </div>
                        {/* Date filter */}
                        <div className="flex flex-col gap-1">
                            <label className="text-[10px] font-semibold uppercase tracking-wider text-slate-400">Дата</label>
                            <input
                                type="date"
                                value={filterDate}
                                onChange={e => setFilterDate(e.target.value)}
                                className="text-xs border border-slate-200 rounded-lg px-2.5 py-1.5 bg-white text-slate-700 focus:outline-none focus:ring-1 focus:ring-primary"
                            />
                        </div>
                        {/* Buttons */}
                        <div className="flex gap-2 pb-0.5">
                            <button
                                onClick={applyFilters}
                                className="text-xs font-semibold px-3 py-1.5 bg-slate-900 text-white rounded-lg hover:bg-slate-700 transition-colors"
                            >
                                Применить
                            </button>
                            {(filterModule || filterDate) && (
                                <button
                                    onClick={resetFilters}
                                    className="text-xs font-medium px-3 py-1.5 border border-slate-200 text-slate-500 rounded-lg hover:bg-slate-50 transition-colors"
                                >
                                    Сбросить
                                </button>
                            )}
                        </div>
                    </div>

                    {/* ── List ── */}
                    {histLoading ? (
                        <div className="py-10 flex justify-center">
                            <RefreshCw className="w-5 h-5 text-primary animate-spin" />
                        </div>
                    ) : historyItems.length === 0 ? (
                        <p className="py-10 text-center text-slate-400 italic text-sm">
                            {filterModule || filterDate ? 'Ничего не найдено по фильтрам' : 'Загруженных документов нет'}
                        </p>
                    ) : (
                        <ul className="divide-y divide-slate-50">
                            {historyItems.map((item) => {
                                if (item.type === 'batch') {
                                    const { batch: b, status, date, count } = item;
                                    const bmod = MODULES[b.module] || MODULES['standard'];
                                    return (
                                        <li
                                            key={b.id}
                                            onClick={() => navigate(`/batch/${b.jobIds.join(',')}?module=${b.module}`)}
                                            className="flex items-center gap-3 px-5 py-3 hover:bg-slate-50/60 cursor-pointer transition-colors group"
                                        >
                                            <Package className="w-4 h-4 text-slate-400 shrink-0" />
                                            <div className="flex-1 min-w-0">
                                                <p className="text-sm font-medium text-slate-700">
                                                    Пакет: {count} документ{count === 1 ? '' : count < 5 ? 'а' : 'ов'}
                                                </p>
                                                <p className="text-xs text-slate-400">
                                                    {new Date(date).toLocaleString('ru-RU')}
                                                    {' · '}
                                                    <span className={`font-medium ${bmod.color}`}>{bmod.title}</span>
                                                </p>
                                            </div>
                                            <span className={`text-xs font-medium px-2 py-0.5 rounded-full ${
                                                status === 'done'  ? 'bg-emerald-100 text-emerald-700' :
                                                status === 'error' ? 'bg-red-100 text-red-600' :
                                                                     'bg-blue-100 text-blue-700'}`}>
                                                {statusLabel[status] || status}
                                            </span>
                                            <ChevronRight className="w-4 h-4 text-slate-300 group-hover:text-slate-500 transition-colors" />
                                        </li>
                                    );
                                }
                                const { job } = item;
                                const jmod = MODULES[job.module] || null;
                                return (
                                    <li
                                        key={job.id}
                                        onClick={() => navigate(`/result/${job.id}`)}
                                        className="flex items-center gap-3 px-5 py-3 hover:bg-slate-50/60 cursor-pointer transition-colors group"
                                    >
                                        <FileText className="w-4 h-4 text-slate-300 shrink-0" />
                                        <div className="flex-1 min-w-0">
                                            <p className="text-sm font-medium text-slate-700 truncate">
                                                {jobNames[job.id] || (
                                                    <span className="font-mono text-slate-400 text-xs">
                                                        {String(job.id).substring(0, 8)}…
                                                    </span>
                                                )}
                                            </p>
                                            <p className="text-xs text-slate-400">
                                                {new Date(job.created_at).toLocaleString('ru-RU')}
                                                {jmod && <span className={`ml-1.5 font-medium ${jmod.color}`}>· {jmod.title}</span>}
                                            </p>
                                        </div>
                                        <span className={`text-xs font-medium px-2 py-0.5 rounded-full ${
                                            job.status === 'done'  ? 'bg-emerald-100 text-emerald-700' :
                                            job.status === 'error' ? 'bg-red-100 text-red-600' :
                                                                     'bg-blue-100 text-blue-700'}`}>
                                            {statusLabel[job.status] || job.status}
                                        </span>
                                        <ChevronRight className="w-4 h-4 text-slate-300 group-hover:text-slate-500 transition-colors" />
                                    </li>
                                );
                            })}
                        </ul>
                    )}

                    {/* ── Pagination ── */}
                    {histPages > 1 && (
                        <div className="px-5 py-3.5 border-t border-slate-100 flex items-center justify-between bg-slate-50/40">
                            <p className="text-xs text-slate-400">
                                Страница {histPage} из {histPages} · показано {histJobs.length} из {histTotal}
                            </p>
                            <div className="flex items-center gap-1">
                                {/* Prev */}
                                <button
                                    onClick={() => goToPage(histPage - 1)}
                                    disabled={histPage === 1}
                                    className="px-2.5 py-1 text-xs font-medium border border-slate-200 rounded-lg
                                        text-slate-600 hover:bg-white disabled:opacity-30 disabled:cursor-not-allowed transition-colors"
                                >
                                    ←
                                </button>

                                {/* Page numbers */}
                                {Array.from({ length: histPages }, (_, i) => i + 1)
                                    .filter(p => p === 1 || p === histPages || Math.abs(p - histPage) <= 2)
                                    .reduce((acc, p, idx, arr) => {
                                        if (idx > 0 && p - arr[idx - 1] > 1) acc.push('…');
                                        acc.push(p);
                                        return acc;
                                    }, [])
                                    .map((p, i) => p === '…' ? (
                                        <span key={`dots-${i}`} className="px-1.5 text-xs text-slate-300">…</span>
                                    ) : (
                                        <button
                                            key={p}
                                            onClick={() => goToPage(p)}
                                            className={`w-7 h-7 text-xs font-medium rounded-lg transition-colors ${
                                                p === histPage
                                                    ? 'bg-slate-900 text-white'
                                                    : 'border border-slate-200 text-slate-600 hover:bg-white'
                                            }`}
                                        >
                                            {p}
                                        </button>
                                    ))
                                }

                                {/* Next */}
                                <button
                                    onClick={() => goToPage(histPage + 1)}
                                    disabled={histPage === histPages}
                                    className="px-2.5 py-1 text-xs font-medium border border-slate-200 rounded-lg
                                        text-slate-600 hover:bg-white disabled:opacity-30 disabled:cursor-not-allowed transition-colors"
                                >
                                    →
                                </button>
                            </div>
                        </div>
                    )}
                </div>
            )}
        </div>
    );
};

export default UserDashboard;
