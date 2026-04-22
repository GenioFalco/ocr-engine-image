import React, { useState, useEffect } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import api from '../api';
import { ArrowLeft, Check, Copy, AlertCircle, RefreshCw, FileText, Building, List, Download } from 'lucide-react';
import { exportClosingDocsToExcel } from '../utils/excel';

// ── re-used helpers (same as ResultViewer) ────────────────────────────────────
const formatCurrency = (value) => {
    if (value == null || value === '' || value === '-' || !Number(value)) return value || '-';
    return new Intl.NumberFormat('ru-RU', { style: 'currency', currency: 'RUB', minimumFractionDigits: 2 }).format(value);
};

const parseFields = (fieldsObj) => {
    const parsed = {};
    for (const [key, val] of Object.entries(fieldsObj)) {
        if (typeof val === 'string') {
            try { parsed[key] = JSON.parse(val); } catch { parsed[key] = val; }
        } else { parsed[key] = val; }
    }
    return parsed;
};

const Field = ({ fieldId, label, value, onCopy, copiedKey }) => {
    const displayVal = value === null || value === undefined || value === '' ? null : String(value);
    if (!displayVal) return null;
    return (
        <div className="group flex items-start gap-3 py-2.5 px-4 rounded-lg hover:bg-slate-50 transition-colors">
            <div className="flex-1 min-w-0">
                <p className="text-[11px] font-semibold uppercase tracking-wider text-slate-400 mb-0.5">{label}</p>
                <p className="text-sm text-slate-800 font-medium break-words">{displayVal}</p>
            </div>
            <button onClick={() => onCopy(fieldId, displayVal)}
                className="opacity-0 group-hover:opacity-100 transition-opacity p-1.5 rounded-md hover:bg-slate-200 text-slate-400 shrink-0">
                {copiedKey === fieldId ? <Check className="w-3.5 h-3.5 text-emerald-500" /> : <Copy className="w-3.5 h-3.5" />}
            </button>
        </div>
    );
};

const Card = ({ title, icon: Icon, children }) => (
    <div className="bg-white rounded-xl shadow-sm border border-slate-200 overflow-hidden mb-4">
        <div className="bg-slate-50/80 px-4 py-3 border-b border-slate-100 flex items-center gap-2">
            <Icon className="w-4 h-4 text-primary" />
            <h3 className="font-semibold text-slate-800 text-sm">{title}</h3>
        </div>
        <div className="divide-y divide-slate-50">{children}</div>
    </div>
);

const DocResult = ({ doc, idx, copiedKey, onCopy }) => {
    const structured = parseFields(doc.fields || {});
    const primitives = {}, objects = {}, arrays = {};
    for (const [key, val] of Object.entries(structured)) {
        if (Array.isArray(val)) arrays[key] = val;
        else if (typeof val === 'object' && val !== null && !('value' in val)) objects[key] = val;
        else primitives[key] = val;
    }

    return (
        <div>
            <div className="flex justify-between items-center mb-4">
                <h2 className="text-base font-bold text-slate-900">{doc.document_type || 'Документ'}</h2>
                {doc.confidence && (
                    <span className="text-xs font-bold px-2.5 py-1 bg-emerald-100 text-emerald-800 rounded-full">
                        {(doc.confidence * 100).toFixed(0)}%
                    </span>
                )}
            </div>
            {Object.keys(primitives).length > 0 && (
                <Card title="Основная информация" icon={FileText}>
                    {Object.entries(primitives).map(([k, v]) => {
                        const val = typeof v === 'object' && v !== null && 'value' in v ? v.value : v;
                        return <Field key={k} fieldId={`${idx}-${k}`} label={k.replace(/_/g, ' ')} value={val} onCopy={onCopy} copiedKey={copiedKey} />;
                    })}
                </Card>
            )}
            {Object.entries(objects).map(([objKey, objVal]) => (
                <Card key={objKey} title={objKey.replace(/_/g, ' ').toUpperCase()} icon={Building}>
                    {Object.entries(objVal).map(([sk, sv]) => {
                        const val = typeof sv === 'object' && sv !== null && 'value' in sv ? sv.value : sv;
                        return <Field key={sk} fieldId={`${idx}-${objKey}-${sk}`} label={sk.replace(/_/g, ' ')} value={val} onCopy={onCopy} copiedKey={copiedKey} />;
                    })}
                </Card>
            ))}
            {Object.entries(arrays).map(([arrKey, arrVal]) => {
                if (!arrVal.length) return null;
                const cols = [...new Set(arrVal.flatMap(item => typeof item === 'object' ? Object.keys(item) : []))];
                return (
                    <div key={arrKey} className="bg-white rounded-xl shadow-sm border border-slate-200 overflow-hidden mb-4">
                        <div className="bg-slate-50/80 px-4 py-3 border-b border-slate-100 flex items-center gap-2">
                            <List className="w-4 h-4 text-primary" />
                            <h3 className="font-semibold text-slate-800 text-sm">{arrKey.replace(/_/g, ' ').toUpperCase()}</h3>
                        </div>
                        <div className="overflow-x-auto">
                            <table className="w-full text-left text-xs text-slate-600">
                                <thead className="bg-slate-50 border-b border-slate-100 text-slate-400 uppercase text-[10px] font-semibold">
                                    <tr>{cols.map(c => <th key={c} className="px-4 py-2 whitespace-nowrap">{c.replace(/_/g, ' ')}</th>)}</tr>
                                </thead>
                                <tbody className="divide-y divide-slate-50">
                                    {arrVal.map((item, i) => (
                                        <tr key={i} className="hover:bg-slate-50/50">
                                            {cols.map(c => {
                                                const sv = item?.[c];
                                                const val = typeof sv === 'object' && sv !== null && 'value' in sv ? sv.value : sv;
                                                return <td key={c} className="px-4 py-2 max-w-[200px] truncate">{val ?? <span className="text-slate-300 italic">—</span>}</td>;
                                            })}
                                        </tr>
                                    ))}
                                </tbody>
                            </table>
                        </div>
                    </div>
                );
            })}
        </div>
    );
};

// ── BatchViewer page ──────────────────────────────────────────────────────────
const BatchViewer = () => {
    const { jobIds } = useParams();
    const navigate = useNavigate();
    const ids = jobIds ? jobIds.split(',').filter(Boolean) : [];

    const [selectedIdx, setSelectedIdx] = useState(0);
    const [results, setResults] = useState({}); // jobId → data
    const [loading, setLoading] = useState({});  // jobId → bool
    const [errors, setErrors] = useState({});    // jobId → string
    const [copiedKey, setCopiedKey] = useState(null);

    const onCopy = (key, text) => {
        navigator.clipboard.writeText(String(text));
        setCopiedKey(key); setTimeout(() => setCopiedKey(null), 2000);
    };

    const loadJob = async (jobId) => {
        if (results[jobId] || loading[jobId]) return;
        setLoading(l => ({ ...l, [jobId]: true }));
        try {
            const { data } = await api.get(`/result/${jobId}`);
            setResults(r => ({ ...r, [jobId]: data }));
        } catch { setErrors(e => ({ ...e, [jobId]: 'Ошибка загрузки' })); }
        finally { setLoading(l => ({ ...l, [jobId]: false })); }
    };

    useEffect(() => {
        ids.forEach(id => loadJob(id));
    }, [jobIds]);

    const currentId = ids[selectedIdx];
    const currentResult = results[currentId];
    const isLoading = loading[currentId];
    const isError = errors[currentId];
    const token = localStorage.getItem('token');
    const iframeUrl = currentId ? `/api/preview/${currentId}?token=${token}` : null;

    const handleExportExcel = () => {
        const allDocs = [];
        ids.forEach(id => {
            if (results[id] && results[id].documents) {
                allDocs.push(...results[id].documents);
            }
        });
        if (allDocs.length > 0) exportClosingDocsToExcel(allDocs);
    };

    return (
        <div className="flex flex-col h-[calc(100vh-64px)] -mx-4 sm:-mx-6 lg:-mx-8 -my-8">
            {/* Top bar */}
            <div className="bg-white border-b border-slate-200 px-6 py-3 flex items-center justify-between shrink-0">
                <div className="flex items-center gap-4">
                    <button onClick={() => navigate('/')} className="flex items-center gap-1.5 text-sm text-slate-500 hover:text-slate-800 font-medium transition-colors">
                        <ArrowLeft className="w-4 h-4" /> Назад
                    </button>
                    <span className="text-slate-200">|</span>
                    <p className="text-sm font-semibold text-slate-700">Пакет: {ids.length} документ(ов)</p>
                </div>
                
                <button 
                    onClick={handleExportExcel}
                    className="flex items-center gap-2 px-4 py-2 bg-emerald-50 text-emerald-700 text-sm font-semibold rounded-lg hover:bg-emerald-100 transition-colors border border-emerald-200 shadow-sm"
                >
                    <Download className="w-4 h-4" />
                    Экспорт в Excel
                </button>
            </div>

            <div className="flex flex-1 min-h-0">
                {/* File list sidebar */}
                <aside className="w-48 shrink-0 bg-slate-50 border-r border-slate-200 flex flex-col overflow-y-auto">
                    <div className="px-3 py-3">
                        <p className="text-[10px] font-bold uppercase tracking-widest text-slate-400">Файлы пакета</p>
                    </div>
                    <nav className="flex flex-col gap-1 px-2 pb-4">
                        {ids.map((id, i) => {
                            const res = results[id];
                            const docType = res?.documents?.[0]?.document_type || `Файл ${i + 1}`;
                            const isActive = i === selectedIdx;
                            return (
                                <button key={id} onClick={() => setSelectedIdx(i)}
                                    className={`text-left px-3 py-2.5 rounded-lg text-xs font-medium transition-colors w-full
                                        ${isActive ? 'bg-slate-900 text-white' : 'text-slate-600 hover:bg-white hover:text-slate-900 hover:shadow-sm'}`}>
                                    <div className="truncate">{docType}</div>
                                    <div className={`text-[10px] mt-0.5 truncate font-mono ${isActive ? 'text-slate-400' : 'text-slate-400'}`}>{id.substring(0, 8)}…</div>
                                    {loading[id] && <div className="mt-1 text-[10px] text-blue-400">загрузка…</div>}
                                    {errors[id] && <div className="mt-1 text-[10px] text-red-400">ошибка</div>}
                                </button>
                            );
                        })}
                    </nav>
                </aside>

                {/* PDF preview */}
                <div className="w-1/2 border-r border-slate-200 flex flex-col bg-slate-100">
                    <div className="px-4 py-2.5 bg-white border-b border-slate-100 flex items-center justify-between">
                        <span className="text-xs font-semibold text-slate-500 uppercase tracking-wide">Оригинал документа</span>
                        {iframeUrl && (
                            <a href={iframeUrl} target="_blank" rel="noreferrer" className="text-xs text-primary hover:underline">
                                Открыть полноэкранно ↗
                            </a>
                        )}
                    </div>
                    {iframeUrl
                        ? <iframe src={iframeUrl} className="flex-1 w-full border-0" title="PDF Preview" />
                        : <div className="flex-1 flex items-center justify-center text-slate-400 text-sm">Нет файла</div>}
                </div>

                {/* Results panel */}
                <div className="flex-1 overflow-y-auto bg-slate-50/40 p-6">
                    {isLoading && (
                        <div className="h-48 flex flex-col items-center justify-center gap-3">
                            <RefreshCw className="w-7 h-7 text-primary animate-spin" />
                            <p className="text-slate-500 text-sm">Загрузка результата…</p>
                        </div>
                    )}
                    {isError && (
                        <div className="bg-red-50 p-5 rounded-xl border border-red-100 flex items-center gap-3">
                            <AlertCircle className="w-5 h-5 text-red-500" />
                            <p className="text-red-700 text-sm">{isError}</p>
                        </div>
                    )}
                    {currentResult && !isLoading && (
                        (currentResult.documents || []).map((doc, idx) => (
                            <DocResult key={idx} doc={doc} idx={`${selectedIdx}-${idx}`} copiedKey={copiedKey} onCopy={onCopy} />
                        ))
                    )}
                </div>
            </div>
        </div>
    );
};

export default BatchViewer;
