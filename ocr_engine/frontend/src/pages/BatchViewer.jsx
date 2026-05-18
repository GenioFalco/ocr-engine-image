import React, { useState, useEffect } from 'react';
import { useParams, useNavigate, useSearchParams } from 'react-router-dom';
import api from '../api';
import { ArrowLeft, Check, Copy, AlertCircle, RefreshCw, FileText, Building, List, Download, ThumbsUp, ThumbsDown, MessageSquare, Send } from 'lucide-react';
import { exportClosingDocsToExcel } from '../utils/excel';

// ── Closing-docs helpers (same logic as ResultViewer / excel.js) ──────────────
const getValue = (flatData, keys) => {
    for (const key of keys) {
        const nk = key.toLowerCase().replace(/[^a-zа-яё0-9]/g, '');
        for (const [rk, val] of Object.entries(flatData)) {
            if (rk.toLowerCase().replace(/[^a-zа-яё0-9]/g, '') === nk && val != null && val !== '' && val !== 'null')
                return val;
        }
    }
    for (const key of keys) {
        const nk = key.toLowerCase().replace(/[^a-zа-яё0-9]/g, '');
        if (nk.length < 3) continue;
        for (const [rk, val] of Object.entries(flatData)) {
            if (rk.toLowerCase().replace(/[^a-zа-яё0-9]/g, '').includes(nk) && val != null && val !== '' && val !== 'null')
                return val;
        }
    }
    return '';
};

const flattenObj = (obj, prefix = '') => {
    const r = {};
    if (!obj || typeof obj !== 'object') return r;
    for (const [k, v] of Object.entries(obj)) {
        const key = prefix ? `${prefix} ${k}` : k;
        if (Array.isArray(v)) continue;
        if (v && typeof v === 'object' && 'value' in v) { if (v.value != null) r[key] = String(v.value); }
        else if (v && typeof v === 'object') Object.assign(r, flattenObj(v, key));
        else if (v != null) r[key] = String(v);
    }
    return r;
};

const findMainTable = (obj) => {
    let arr = [];
    const s = (x) => {
        if (Array.isArray(x)) { if (x.length > arr.length) arr = x; }
        else if (x && typeof x === 'object' && !('value' in x)) Object.values(x).forEach(s);
    };
    s(obj);
    return arr;
};

const parseFieldsSafe = (f) => {
    if (!f) return {};
    const r = {};
    for (const [k, v] of Object.entries(f)) {
        if (typeof v === 'string') { try { r[k] = JSON.parse(v); } catch { r[k] = v; } } else r[k] = v;
    }
    return r;
};

// ── re-used helpers (standard layout) ────────────────────────────────────────
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

// ── Shared UI components ──────────────────────────────────────────────────────
const FieldRow = ({ fieldId, label, value, onCopy, copiedKey }) => {
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

// ── Standard document result ──────────────────────────────────────────────────
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
                        return <FieldRow key={k} fieldId={`${idx}-${k}`} label={k.replace(/_/g, ' ')} value={val} onCopy={onCopy} copiedKey={copiedKey} />;
                    })}
                </Card>
            )}
            {Object.entries(objects).map(([objKey, objVal]) => (
                <Card key={objKey} title={objKey.replace(/_/g, ' ').toUpperCase()} icon={Building}>
                    {Object.entries(objVal).map(([sk, sv]) => {
                        const val = typeof sv === 'object' && sv !== null && 'value' in sv ? sv.value : sv;
                        return <FieldRow key={sk} fieldId={`${idx}-${objKey}-${sk}`} label={sk.replace(/_/g, ' ')} value={val} onCopy={onCopy} copiedKey={copiedKey} />;
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

// ── Closing-docs document result ──────────────────────────────────────────────
const ClosingDocResult = ({ doc, idx, copiedKey, onCopy }) => {
    const structured = parseFieldsSafe(doc.fields || {});
    const { visual_marks: _vm, ...fieldsData } = structured;
    const flat = flattenObj(fieldsData);

    // Prefer explicit 'items' key; fall back to findMainTable
    const table = (Array.isArray(fieldsData.items) && fieldsData.items.length > 0)
        ? fieldsData.items
        : findMainTable(fieldsData);

    const org        = getValue(flat, ['buyer_inn', 'buyer inn', 'инн_покупателя', 'инн_заказчика', 'покупатель_инн']);
    const contrName  = getValue(flat, ['seller_name', 'seller name', 'наименование_продавца', 'имя_продавца']);
    const contrINN   = getValue(flat, ['seller_inn', 'seller inn', 'инн_продавца', 'инн_исполнителя', 'продавца_инн', 'consignor_inn', 'consignor inn']);
    const docNum     = getValue(flat, ['document_number', 'номер_документа', 'номер_счета', 'номер']);
    // Сумма: total_with_vat должен быть раньше чем просто total (иначе subtotal матчится первым)
    const docSum     = getValue(flat, [
        'total_with_vat', 'amounts total_with_vat', 'итого_с_ндс', 'сумма_с_ндс',
        'total_amount', 'amount', 'итого', 'сумма_документа',
    ]);
    // Договор: basis_document → contract_*
    const basisType   = getValue(flat, ['basis_document type', 'basis document type']);
    const basisNumber = getValue(flat, ['basis_document number', 'basis document number', 'contract_number', 'номер_договора', 'договор_номер']);
    const basisDate   = getValue(flat, ['basis_document date', 'basis document date']);
    const contractTitle = getValue(flat, ['contract_title', 'договор', 'основание']);
    const contract    = contractTitle
        || [basisType, basisNumber, basisDate ? `от ${basisDate}` : ''].filter(Boolean).join(' ');
    const docDate     = getValue(flat, ['document_date', 'дата_документа', 'дата']);
    const vatRate     = getValue(flat, ['vat_rate', 'ставка_ндс', 'ндс_ставка'])
        || (table.length > 0 ? getValue(flattenObj(table[0]), ['vat_rate', 'ставка_ндс', 'ндс_ставка']) : '');

    // Маппинг типов → русские названия (как в excel.js)
    const DOC_TYPE_LABELS = {
        'UPD':             'Универсальный передаточный документ',
        'Act':             'Акт выполненных работ или оказание услуг',
        'Invoice':         'Счет на оплату или Invoice',
        'Invoice-Factura': 'Счет-фактура',
        'Torg12':          'Товарная накладная (ТОРГ-12)',
        'unknown':         'Неизвестный тип',
    };
    const docTypeLabel = DOC_TYPE_LABELS[doc.document_type] || doc.document_type || '-';

    const tableText = table.length > 0 ? table.map(item => {
        const f = flattenObj(item);
        const name  = getValue(f, ['name', 'description', 'наименование', 'товар', 'услуга']) || '-';
        const qty   = getValue(f, ['quantity', 'кол-во', 'количество', 'qty']) || '-';
        const price = getValue(f, ['price_without_vat', 'unit_price', 'price', 'цена']) || '-';
        const sub   = getValue(f, ['amount_without_vat', 'subtotal', 'сумма_без_ндс']) || '-';
        const vat   = getValue(f, ['vat_rate', 'ставка_ндс', 'ндс_ставка']) || '-';
        const tax   = getValue(f, ['vat_amount', 'сумма_налога', 'сумма_ндс', 'ндс']) || '-';
        const tot   = getValue(f, ['amount_with_vat', 'total_with_vat', 'total', 'итого']) || '-';
        return `Наименование: ${name}, Кол-во: ${qty}, Цена: ${price}, Без НДС: ${sub}, НДС%: ${vat}, НДС: ${tax}, Итого: ${tot}`;
    }).join(';\n') : '-';

    // Описание — единый блок как колонка «Описание» в Excel
    const descriptionLines = [
        contrName   ? `Контрагент: ${contrName}`       : null,
        contrINN    ? `ИНН продавца: ${contrINN}`      : null,
        docNum      ? `Номер документа: ${docNum}`     : null,
        docDate     ? `Дата документа: ${docDate}`     : null,
        docSum      ? `Сумма с НДС: ${docSum}`         : null,
        vatRate     ? `Ставка НДС: ${vatRate}`         : null,
        contract    ? `Договор: ${contract}`           : null,
        table.length > 0 ? `\n${tableText}`            : null,
    ].filter(Boolean).join('\n');

    const cols = [
        { label: 'Вид документа',               value: docTypeLabel,       id: `cd-type-${idx}` },
        { label: 'Организация (ИНН покупателя)', value: org || '-',         id: `cd-org-${idx}` },
        { label: 'Описание',                     value: descriptionLines || '-', id: `cd-desc-${idx}`, multi: true },
    ];

    return (
        <div className="mb-6">
            <div className="flex items-center justify-between mb-4">
                <h2 className="text-base font-bold text-slate-900">{docTypeLabel}</h2>
                {doc.confidence && (
                    <span className="text-xs font-bold px-2.5 py-1 bg-emerald-100 text-emerald-800 rounded-full">
                        Точность: {(doc.confidence * 100).toFixed(0)}%
                    </span>
                )}
            </div>
            <div className="space-y-2">
                {cols.map(col => (
                    <div key={col.id} className="bg-white rounded-xl border border-slate-200 px-4 py-3 flex items-start gap-3">
                        <div className="flex-1 min-w-0">
                            <div className="text-[10px] font-semibold uppercase tracking-widest text-slate-400 mb-1">{col.label}</div>
                            {col.multi ? (
                                <pre className="text-sm text-slate-800 whitespace-pre-wrap font-sans leading-relaxed">
                                    {col.value}
                                </pre>
                            ) : (
                                <div className="text-sm font-medium text-slate-800">{col.value}</div>
                            )}
                        </div>
                        <button
                            onClick={() => onCopy(col.id, col.value)}
                            className="shrink-0 h-6 px-2 inline-flex items-center gap-1 text-xs font-medium text-slate-500
                                bg-white border border-slate-200 rounded hover:border-sky-400 hover:text-sky-600
                                transition-colors shadow-sm"
                        >
                            {copiedKey === col.id ? <Check className="w-3 h-3 text-emerald-500" /> : <Copy className="w-3 h-3" />}
                        </button>
                    </div>
                ))}
            </div>
        </div>
    );
};

// ── BatchViewer page ──────────────────────────────────────────────────────────
const BatchViewer = () => {
    const { jobIds } = useParams();
    const [searchParams] = useSearchParams();
    const navigate = useNavigate();
    const ids = jobIds ? jobIds.split(',').filter(Boolean) : [];

    // Module is passed explicitly in URL (?module=closing-docs) — no need to infer from loaded data
    const batchModule = searchParams.get('module') || 'standard';
    const isClosingDocs = batchModule === 'closing-docs';

    const [selectedIdx, setSelectedIdx] = useState(0);
    const [results, setResults] = useState({}); // jobId → data
    const [loading, setLoading] = useState({});  // jobId → bool
    const [errors, setErrors] = useState({});    // jobId → string
    const [copiedKey, setCopiedKey] = useState(null);

    // ── Per-job ratings ───────────────────────────────────────────────────────
    const [ratings,   setRatings]   = useState({});   // jobId → 5|1
    const [comments,  setComments]  = useState({});   // jobId → string
    const [showCmt,   setShowCmt]   = useState({});   // jobId → bool
    const [submittingRating, setSubmittingRating] = useState({});

    const handleRating = async (jobId, val) => {
        if (submittingRating[jobId]) return;
        setSubmittingRating(r => ({ ...r, [jobId]: true }));
        try {
            await api.post('/feedback', { job_id: jobId, rating: val, comment: comments[jobId] || '' });
            setRatings(r => ({ ...r, [jobId]: val }));
        } catch { }
        finally { setSubmittingRating(r => ({ ...r, [jobId]: false })); }
    };

    const handleSaveComment = async (jobId) => {
        if (!ratings[jobId]) return;
        setSubmittingRating(r => ({ ...r, [jobId]: true }));
        try {
            await api.post('/feedback', { job_id: jobId, rating: ratings[jobId], comment: comments[jobId] || '' });
        } catch { }
        finally { setSubmittingRating(r => ({ ...r, [jobId]: false })); }
    };

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
            // Pre-fill existing rating if the job already has one
            if (data.rating)  setRatings(r  => ({ ...r,  [jobId]: data.rating }));
            if (data.comment) { setComments(c => ({ ...c, [jobId]: data.comment })); setShowCmt(s => ({ ...s, [jobId]: true })); }
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
        const jobNames = (() => { try { return JSON.parse(localStorage.getItem('ocr_job_names') || '{}'); } catch { return {}; } })();
        const jobResults = ids
            .filter(id => results[id]?.documents?.length)
            .map(id => ({
                jobId: id,
                filename: jobNames[id] || id,
                documents: results[id].documents,
            }));
        if (jobResults.length > 0) exportClosingDocsToExcel(jobResults);
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

                {isClosingDocs && (
                    <button
                        onClick={handleExportExcel}
                        className="flex items-center gap-2 px-4 py-2 bg-emerald-50 text-emerald-700 text-sm font-semibold rounded-lg hover:bg-emerald-100 transition-colors border border-emerald-200 shadow-sm"
                    >
                        <Download className="w-4 h-4" />
                        Экспорт в Excel
                    </button>
                )}
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
                            const jobRating = ratings[id] || 0;
                            const jobHover = hoverRating[id] || 0;
                            return (
                                <button key={id} onClick={() => setSelectedIdx(i)}
                                    className={`text-left px-3 py-2.5 rounded-lg text-xs font-medium transition-colors w-full
                                        ${isActive ? 'bg-slate-900 text-white' : 'text-slate-600 hover:bg-white hover:text-slate-900 hover:shadow-sm'}`}>
                                    <div className="truncate">{docType}</div>
                                    <div className={`text-[10px] mt-0.5 truncate font-mono ${isActive ? 'text-slate-400' : 'text-slate-400'}`}>{id.substring(0, 8)}…</div>
                                    {loading[id] && <div className="mt-1 text-[10px] text-blue-400">загрузка…</div>}
                                    {errors[id] && <div className="mt-1 text-[10px] text-red-400">ошибка</div>}
                                    {res && !loading[id] && !errors[id] && (
                                        <div className="flex items-center gap-1 mt-1.5" onClick={e => e.stopPropagation()}>
                                            <button disabled={submittingRating[id]} onClick={() => handleRating(id, 5)}
                                                className={`flex items-center gap-0.5 px-1.5 py-0.5 rounded text-[10px] font-semibold border transition-all
                                                    ${ratings[id] === 5 ? 'bg-emerald-500 text-white border-emerald-500' : 'text-emerald-600 border-emerald-200 bg-white hover:bg-emerald-50'}`}>
                                                <ThumbsUp className="w-2.5 h-2.5" /> OK
                                            </button>
                                            <button disabled={submittingRating[id]} onClick={() => handleRating(id, 1)}
                                                className={`flex items-center gap-0.5 px-1.5 py-0.5 rounded text-[10px] font-semibold border transition-all
                                                    ${ratings[id] === 1 ? 'bg-red-500 text-white border-red-500' : 'text-red-500 border-red-200 bg-white hover:bg-red-50'}`}>
                                                <ThumbsDown className="w-2.5 h-2.5" />
                                            </button>
                                        </div>
                                    )}
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
                <div className="flex-1 flex flex-col min-h-0 bg-slate-50/40">
                {/* Rating bar for current job */}
                {currentId && currentResult && !isLoading && (
                    <div className="px-5 py-2 bg-white border-b border-slate-100 flex flex-wrap items-center gap-2 shrink-0">
                        <span className="text-xs text-slate-400 font-medium">Оценить:</span>
                        <button disabled={submittingRating[currentId]} onClick={() => handleRating(currentId, 5)}
                            className={`flex items-center gap-1 px-2.5 py-1 rounded-lg text-xs font-semibold border transition-all disabled:opacity-50
                                ${ratings[currentId] === 5 ? 'bg-emerald-500 text-white border-emerald-500' : 'bg-white text-emerald-600 border-emerald-200 hover:bg-emerald-50'}`}>
                            <ThumbsUp className="w-3.5 h-3.5" /> Хорошо
                        </button>
                        <button disabled={submittingRating[currentId]} onClick={() => handleRating(currentId, 1)}
                            className={`flex items-center gap-1 px-2.5 py-1 rounded-lg text-xs font-semibold border transition-all disabled:opacity-50
                                ${ratings[currentId] === 1 ? 'bg-red-500 text-white border-red-500' : 'bg-white text-red-500 border-red-200 hover:bg-red-50'}`}>
                            <ThumbsDown className="w-3.5 h-3.5" /> Плохо
                        </button>
                        <button onClick={() => setShowCmt(s => ({ ...s, [currentId]: !s[currentId] }))}
                            className={`flex items-center gap-1 px-2 py-1 rounded-lg text-xs border transition-all
                                ${showCmt[currentId] ? 'bg-sky-100 text-sky-700 border-sky-200' : 'bg-white text-slate-400 border-slate-200 hover:bg-slate-50'}`}>
                            <MessageSquare className="w-3.5 h-3.5" /> Комментарий
                        </button>
                        {showCmt[currentId] && (
                            <div className="flex items-start gap-2 w-full mt-1">
                                <textarea
                                    value={comments[currentId] || ''}
                                    onChange={e => setComments(c => ({ ...c, [currentId]: e.target.value }))}
                                    placeholder="Что не так или что понравилось..."
                                    rows={2}
                                    className="flex-1 text-xs p-2 border border-slate-200 rounded-lg focus:ring-2 focus:ring-sky-400 outline-none resize-none bg-white"
                                />
                                <button onClick={() => handleSaveComment(currentId)} disabled={submittingRating[currentId]}
                                    className="p-2 bg-sky-500 text-white rounded-lg hover:bg-sky-600 disabled:opacity-50 transition-colors mt-0.5">
                                    <Send className="w-3.5 h-3.5" />
                                </button>
                            </div>
                        )}
                    </div>
                )}
                <div className="flex-1 overflow-y-auto p-6">
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
                        isClosingDocs
                            ? (currentResult.documents || []).map((doc, idx) => (
                                <ClosingDocResult key={idx} doc={doc} idx={`${selectedIdx}-${idx}`} copiedKey={copiedKey} onCopy={onCopy} />
                            ))
                            : (currentResult.documents || []).map((doc, idx) => (
                                <DocResult key={idx} doc={doc} idx={`${selectedIdx}-${idx}`} copiedKey={copiedKey} onCopy={onCopy} />
                            ))
                    )}
                </div>{/* overflow-y-auto */}
                </div>{/* flex-1 flex-col */}
            </div>
        </div>
    );
};

export default BatchViewer;
