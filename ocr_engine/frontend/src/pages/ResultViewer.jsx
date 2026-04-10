import React, { useState, useEffect } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import api from '../api';
import { ArrowLeft, Check, Copy, AlertCircle, RefreshCw, FileText, Building2, Building, Package, Truck, Calculator, List, Star } from 'lucide-react';
import { toast } from '../components/Toast';

const formatCurrency = (value) => {
    if (value == null || value === '' || value === '-' || !Number(value)) return value || '-';
    return new Intl.NumberFormat('ru-RU', {
        style: 'currency',
        currency: 'RUB',
        minimumFractionDigits: 2
    }).format(value);
};

const ResultViewer = () => {
    const { jobId } = useParams();
    const navigate = useNavigate();
    const [result, setResult] = useState(null);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState('');
    const [copiedKey, setCopiedKey] = useState(null);
    const [rating, setRating] = useState(null);
    const [hoverRating, setHoverRating] = useState(0);
    const [submittingRating, setSubmittingRating] = useState(false);

    const fetchResult = async () => {
        try {
            setLoading(true);
            const { data } = await api.get(`/result/${jobId}`);
            setResult(data);
            if (data.rating) setRating(data.rating);
        } catch (err) {
            setError('Не удалось загрузить результаты. Возможно, вы не имеете доступа к этому документу.');
        } finally {
            setLoading(false);
        }
    };

    useEffect(() => {
        fetchResult();
    }, [jobId]);

    const copyToClipboard = (key, text) => {
        if (!text) return;
        navigator.clipboard.writeText(String(text));
        setCopiedKey(key);
        setTimeout(() => setCopiedKey(null), 2000);
    };

    const handleRating = async (val) => {
        if (submittingRating) return;
        setSubmittingRating(true);
        try {
            await api.post('/feedback', { job_id: jobId, rating: val });
            setRating(val);
            toast.success('Спасибо за вашу оценку!');
        } catch (err) {
            toast.error('Ошибка сохранения оценки.');
        } finally {
            setSubmittingRating(false);
        }
    };

    if (loading) {
        return (
            <div className="h-64 flex flex-col items-center justify-center space-y-4">
                <RefreshCw className="w-8 h-8 text-primary animate-spin" />
                <p className="text-slate-500 font-medium">Загрузка результатов...</p>
            </div>
        );
    }

    if (error) {
        return (
            <div className="max-w-2xl mx-auto mt-12 bg-red-50 p-6 rounded-2xl border border-red-100 flex items-start gap-4">
                <AlertCircle className="w-6 h-6 text-red-500 shrink-0 mt-0.5" />
                <div>
                    <h3 className="text-red-800 font-semibold mb-1">Ошибка доступа</h3>
                    <p className="text-red-600 text-sm mb-4">{error}</p>
                    <button onClick={() => navigate('/')} className="px-4 py-2 bg-white text-slate-700 text-sm font-medium rounded shadow-sm border border-slate-200 hover:bg-slate-50">
                        Вернуться назад
                    </button>
                </div>
            </div>
        );
    }

    const documents = result?.documents || [];
    const iframeUrl = `/api/preview/${jobId}?token=${localStorage.getItem('token')}`;

    // Helper to deeply parse the stingified JSON fields from API
    const parseFields = (fieldsObj) => {
        const parsed = {};
        for (const [key, val] of Object.entries(fieldsObj)) {
            const lowerKey = key.toLowerCase();
            if (typeof val === 'string') {
                try {
                    parsed[lowerKey] = JSON.parse(val);
                } catch (e) {
                    parsed[lowerKey] = { value: val };
                }
            } else {
                parsed[lowerKey] = val;
            }
        }
        return parsed;
    };

    const Card = ({ title, icon: Icon, children }) => (
        <div className="bg-white rounded-xl shadow-sm border border-slate-200 overflow-hidden mb-6">
            <div className="bg-slate-50/80 px-4 py-3 border-b border-slate-100 flex items-center gap-2">
                {Icon && <Icon className="w-4 h-4 text-primary" />}
                <h3 className="font-semibold text-slate-800 text-sm">{title}</h3>
            </div>
            <div className="p-4 grid grid-cols-1 md:grid-cols-2 gap-4">
                {children}
            </div>
        </div>
    );

    const Field = ({ label, value, fieldId }) => {
        const displayValue = value === null || value === undefined || value === '' ? '-' : String(value);
        const isEmpty = displayValue === '-';
        return (
            <div className="group flex flex-col justify-center p-2 rounded-lg hover:bg-slate-50 transition-colors relative">
                <div className="text-[11px] font-semibold uppercase tracking-widest text-slate-400 mb-1">{label}</div>
                <div className={`text-sm font-medium ${isEmpty ? 'text-slate-300 italic' : 'text-slate-900'}`}>{displayValue}</div>
                {!isEmpty && (
                    <button
                        onClick={() => copyToClipboard(fieldId, displayValue)}
                        className="absolute right-2 top-1/2 -translate-y-1/2 shrink-0 h-7 px-2 inline-flex items-center gap-1.5 text-xs font-medium text-slate-600 bg-white border border-slate-200 rounded-md hover:border-primary hover:text-primary transition-colors shadow-sm opacity-0 group-hover:opacity-100 focus:opacity-100"
                    >
                        {copiedKey === fieldId ? <Check className="w-3.5 h-3.5 text-emerald-500" /> : <Copy className="w-3.5 h-3.5" />}
                    </button>
                )}
            </div>
        );
    };

    const renderDocumentData = (doc, idx) => {
        const structured = parseFields(doc.fields || {});

        // Categorize dynamic fields
        const primitives = {};
        const objects = {};
        const arrays = {};

        for (const [key, val] of Object.entries(structured)) {
            if (Array.isArray(val)) {
                arrays[key] = val;
            } else if (typeof val === 'object' && val !== null && !('value' in val)) {
                objects[key] = val;
            } else {
                primitives[key] = val;
            }
        }

        const renderPrimitives = () => {
            const keys = Object.keys(primitives);
            if (keys.length === 0) return null;
            return (
                <Card title="Основная информация" icon={FileText}>
                    {keys.map(k => {
                        const v = primitives[k];
                        const val = typeof v === 'object' && v !== null && 'value' in v ? v.value : v;
                        return <Field key={k} fieldId={`prim-${idx}-${k}`} label={k.replace(/_/g, ' ')} value={val} />
                    })}
                </Card>
            );
        };

        const renderObjects = () => {
            return Object.entries(objects).map(([objKey, objVal]) => (
                <Card key={objKey} title={objKey.replace(/_/g, ' ').toUpperCase()} icon={Building}>
                    {Object.entries(objVal).map(([subKey, subVal]) => {
                        const val = typeof subVal === 'object' && subVal !== null && 'value' in subVal ? subVal.value : subVal;
                        return <Field key={subKey} fieldId={`obj-${idx}-${objKey}-${subKey}`} label={subKey.replace(/_/g, ' ')} value={val} />
                    })}
                </Card>
            ));
        };

        const renderArrays = () => {
            return Object.entries(arrays).map(([arrKey, arrVal]) => {
                if (!arrVal.length) return null;
                // Accumulate all distinct column names from objects within the array
                const cols = new Set();
                arrVal.forEach(item => {
                    if (typeof item === 'object' && item !== null) {
                        Object.keys(item).forEach(k => cols.add(k));
                    }
                });
                const colArray = Array.from(cols);

                return (
                    <div key={arrKey} className="bg-white rounded-xl shadow-sm border border-slate-200 overflow-hidden mb-6">
                        <div className="bg-slate-50/80 px-4 py-3 border-b border-slate-100 flex items-center gap-2">
                            <List className="w-4 h-4 text-primary" />
                            <h3 className="font-semibold text-slate-800 text-sm">{arrKey.replace(/_/g, ' ').toUpperCase()}</h3>
                        </div>
                        <div className="overflow-x-auto">
                            <table className="w-full text-left text-sm text-slate-600">
                                <thead className="bg-slate-50 border-b border-slate-100 text-slate-500 uppercase text-[10px] font-semibold">
                                    <tr>
                                        {colArray.map(c => <th key={c} className="px-4 py-3 whitespace-nowrap">{c.replace(/_/g, ' ')}</th>)}
                                    </tr>
                                </thead>
                                <tbody className="divide-y divide-slate-100">
                                    {arrVal.map((item, i) => (
                                        <tr key={i} className="hover:bg-slate-50/50">
                                            {colArray.map(c => {
                                                const subVal = item?.[c];
                                                const val = typeof subVal === 'object' && subVal !== null && 'value' in subVal ? subVal.value : subVal;
                                                const displayVal = val === null || val === undefined || val === '' ? '-' : String(val);

                                                return (
                                                    <td key={c} className="px-4 py-3 max-w-xs break-words">
                                                        {displayVal === '-' ? <span className="text-slate-300 italic">нет данных</span> : displayVal}
                                                    </td>
                                                );
                                            })}
                                        </tr>
                                    ))}
                                </tbody>
                            </table>
                        </div>
                    </div>
                );
            });
        };

        return (
            <div key={idx} className="mb-8">
                <div className="flex justify-between items-center mb-6">
                    <h2 className="text-xl font-bold tracking-tight text-slate-900">{doc.document_type || "Неизвестный тип"}</h2>
                    {doc.confidence && (
                        <span className="text-xs font-bold px-3 py-1.5 bg-emerald-100 text-emerald-800 rounded-full shadow-sm">
                            Точность: {(doc.confidence * 100).toFixed(0)}%
                        </span>
                    )}
                </div>

                {renderPrimitives()}
                {renderObjects()}
                {renderArrays()}
            </div>
        );
    };

    return (
        <div className="h-[85vh] flex flex-col pt-4 animate-in fade-in duration-500">
            <div className="flex items-center justify-between mb-4">
                <button
                    onClick={() => navigate('/')}
                    className="flex items-center gap-2 text-slate-500 hover:text-slate-900 transition-colors font-medium bg-white px-4 py-2 rounded-lg border border-slate-200 shadow-sm"
                >
                    <ArrowLeft className="w-4 h-4" /> Назад
                </button>
                <div className="flex flex-col items-end gap-2">
                    <div className="text-right">
                        <p className="text-xs text-slate-400 font-mono tracking-tight text-right uppercase">ID: {jobId}</p>
                        <p className="text-sm font-semibold text-slate-800 flex items-center justify-end gap-2 mt-0.5">
                            Статус: {result?.status === 'done' ? <span className="text-emerald-600 font-bold bg-emerald-50 px-2 rounded">Распознано</span> : result?.status}
                        </p>
                    </div>
                    {result?.status === 'done' && (
                        <div className="flex items-center gap-1.5 bg-slate-50 border border-slate-200 px-3 py-1.5 rounded-lg shadow-sm">
                            <span className="text-xs font-semibold text-slate-500 mr-1">Оценить результат:</span>
                            {[1, 2, 3, 4, 5].map(val => (
                                <button
                                    key={val}
                                    disabled={submittingRating}
                                    onClick={() => handleRating(val)}
                                    onMouseEnter={() => setHoverRating(val)}
                                    onMouseLeave={() => setHoverRating(0)}
                                    className="focus:outline-none transition-transform hover:scale-110 disabled:opacity-50"
                                >
                                    <Star 
                                        className={`w-4 h-4 transition-colors ${
                                            (hoverRating || rating) >= val 
                                                ? 'fill-amber-400 text-amber-400' 
                                                : 'text-slate-300'
                                        }`} 
                                    />
                                </button>
                            ))}
                        </div>
                    )}
                </div>
            </div>

            {/* Split Screen Layout */}
            <div className="flex-1 flex flex-col lg:flex-row gap-6 min-h-0">

                {/* Left Side: Document Preview (Uses Query Param for Auth since Iframes can't send Auth Headers) */}
                <div className="w-full lg:w-1/2 flex flex-col bg-white rounded-2xl border border-slate-200 shadow-sm overflow-hidden">
                    <div className="p-3 bg-slate-50 border-b border-slate-200 flex justify-between items-center">
                        <span className="text-sm font-semibold text-slate-700">Оригинал документа</span>
                        <a href={iframeUrl} target="_blank" rel="noreferrer" className="text-xs text-primary font-medium hover:underline">Открыть полноэкранно</a>
                    </div>
                    <div className="flex-1 bg-slate-100/50 p-2">
                        <iframe
                            src={iframeUrl}
                            className="w-full h-full rounded border border-slate-200 bg-white"
                            title="Document Preview"
                        />
                    </div>
                </div>

                {/* Right Side: Extracted JSON */}
                <div className="w-full lg:w-1/2 flex flex-col bg-slate-50 rounded-2xl border border-slate-200 shadow-sm overflow-hidden">
                    <div className="p-3 bg-white border-b border-slate-200">
                        <span className="text-sm font-semibold text-slate-700">Извлеченные данные</span>
                    </div>
                    <div className="flex-1 overflow-y-auto p-6 scroll-smooth">
                        {documents.length === 0 ? (
                            <div className="text-center text-slate-400 py-12 flex flex-col items-center gap-4">
                                <AlertCircle className="w-12 h-12 text-slate-300" />
                                <span>Нет извлеченных данных.</span>
                            </div>
                        ) : (
                            documents.map((doc, docIdx) => renderDocumentData(doc, docIdx))
                        )}
                    </div>
                </div>

            </div>
        </div>
    );
};

export default ResultViewer;
