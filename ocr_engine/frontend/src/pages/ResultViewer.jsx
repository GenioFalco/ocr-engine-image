import React, { useState, useEffect } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import api from '../api';
import { ArrowLeft, Check, Copy, AlertCircle, RefreshCw, FileText, Building2, Building, Package, Truck, Calculator, List, ThumbsUp, ThumbsDown, Download, AlignLeft, MessageSquare, Send } from 'lucide-react';
import { toast } from '../components/Toast';
import { exportClosingDocsToExcel } from '../utils/excel';

// ── Утилиты для closing-docs (дублируем логику из excel.js) ──────────────────
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
    const s = (x) => { if (Array.isArray(x)) { if (x.length > arr.length) arr = x; } else if (x && typeof x === 'object' && !('value' in x)) Object.values(x).forEach(s); };
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
    const [rating, setRating] = useState(null);   // 5=хорошо, 1=плохо, null=не оценено
    const [comment, setComment] = useState('');
    const [showComment, setShowComment] = useState(false);
    const [submittingRating, setSubmittingRating] = useState(false);

    const fetchResult = async () => {
        try {
            setLoading(true);
            const { data } = await api.get(`/result/${jobId}`);
            setResult(data);
            if (data.rating) setRating(data.rating);
            if (data.comment) { setComment(data.comment); setShowComment(true); }
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
            await api.post('/feedback', { job_id: jobId, rating: val, comment });
            setRating(val);
            toast.success(val >= 4 ? '👍 Спасибо! Отмечено как «Хорошо»' : '👎 Спасибо! Отмечено как «Плохо»');
        } catch {
            toast.error('Ошибка сохранения оценки.');
        } finally {
            setSubmittingRating(false);
        }
    };

    const handleSaveComment = async () => {
        if (!rating) { toast.error('Сначала поставьте оценку.'); return; }
        setSubmittingRating(true);
        try {
            await api.post('/feedback', { job_id: jobId, rating, comment });
            toast.success('Комментарий сохранён.');
        } catch {
            toast.error('Ошибка сохранения комментария.');
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

    const renderTextExtract = (doc, idx) => {
        const rawText = (doc.fields || {}).raw_text || '';
        return (
            <div key={idx} className="mb-4">
                <div className="flex items-center justify-between mb-4">
                    <div className="flex items-center gap-2">
                        <AlignLeft className="w-5 h-5 text-orange-500" />
                        <h2 className="text-lg font-bold text-slate-900">Извлечённый текст</h2>
                    </div>
                    <button
                        onClick={() => { navigator.clipboard.writeText(rawText); toast.success('Текст скопирован!'); }}
                        className="flex items-center gap-1.5 text-xs font-medium px-3 py-1.5 rounded-lg
                            bg-orange-50 border border-orange-200 text-orange-700 hover:bg-orange-100 transition-colors">
                        <Copy className="w-3.5 h-3.5" /> Копировать всё
                    </button>
                </div>
                <div className="bg-white rounded-xl border border-slate-200 shadow-sm overflow-hidden">
                    {rawText ? (
                        <pre className="p-5 text-sm text-slate-700 whitespace-pre-wrap font-sans leading-relaxed">
                            {rawText}
                        </pre>
                    ) : (
                        <p className="p-5 text-sm text-slate-400 italic">Текст не извлечён</p>
                    )}
                </div>
            </div>
        );
    };

    const CopyBtn = ({ id, text }) => (
        <button
            onClick={() => copyToClipboard(id, text)}
            className="shrink-0 h-6 px-2 inline-flex items-center gap-1 text-xs font-medium text-slate-500
                bg-white border border-slate-200 rounded hover:border-sky-400 hover:text-sky-600
                transition-colors shadow-sm"
        >
            {copiedKey === id ? <Check className="w-3 h-3 text-emerald-500" /> : <Copy className="w-3 h-3" />}
        </button>
    );

    // Маппинг типов документов → русские названия (совпадает с excel.js)
    const DOC_TYPE_LABELS = {
        'UPD':             'Универсальный передаточный документ',
        'Act':             'Акт выполненных работ или оказание услуг',
        'Invoice':         'Счет на оплату или Invoice',
        'Invoice-Factura': 'Счет-фактура',
        'unknown':         'Неизвестный тип',
    };
    const getDocTypeLabel = (type) => DOC_TYPE_LABELS[type] || type || '-';

    const renderClosingDoc = (doc, idx) => {
        const structured = parseFieldsSafe(doc.fields || {});
        const { visual_marks: _vm, ...fieldsData } = structured;
        const flat = flattenObj(fieldsData);
        const table = (Array.isArray(fieldsData.items) && fieldsData.items.length > 0)
            ? fieldsData.items
            : findMainTable(fieldsData);

        // ── Поля (логика полностью совпадает с excel.js) ─────────────────────
        const buyerINN  = getValue(flat, ['buyer_inn','buyer inn','инн_покупателя','инн_заказчика','покупатель_инн']);
        const sellerName= getValue(flat, ['seller_name','seller name','наименование_продавца','имя_продавца','исполнитель name','поставщик name']);
        const sellerINN = getValue(flat, ['seller_inn','seller inn','инн_продавца','инн_исполнителя','продавца_инн','consignor_inn','consignor inn']);
        const docNum    = getValue(flat, ['document_number','номер_документа','номер_счета','номер']);
        const docDate   = getValue(flat, ['document_date','дата_документа','дата']);
        const docSum    = getValue(flat, ['total_with_vat','amounts total_with_vat','итого_с_ндс','сумма_с_ндс','total_amount','amount','итого','сумма_документа']);
        const vatRate   = getValue(flat, ['vat_rate','ставка_ндс','ндс_ставка'])
            || (table.length > 0 ? getValue(flattenObj(table[0]), ['vat_rate','ставка_ндс','ндс_ставка']) : '');
        const basisType   = getValue(flat, ['basis_document type','basis document type','тип_основания']);
        const basisNumber = getValue(flat, ['basis_document number','basis document number','contract_number','номер_договора','договор_номер']);
        const basisDate   = getValue(flat, ['basis_document date','basis document date','дата_договора']);
        const contractTitle = getValue(flat, ['contract_title','договор','основание']);
        const contractStr = contractTitle
            || [basisType, basisNumber, basisDate ? `от ${basisDate}` : ''].filter(Boolean).join(' ');

        // ── Таблица товаров (формат совпадает с excel.js) ────────────────────
        const tableText = table.length > 0 ? table.map(item => {
            const f = flattenObj(item);
            const name  = getValue(f, ['name','description','наименование','товар','услуга']) || '-';
            const qty   = getValue(f, ['quantity','кол-во','количество','qty']) || '-';
            const price = getValue(f, ['price_without_vat','unit_price','price','цена']) || '-';
            const sub   = getValue(f, ['amount_without_vat','subtotal','сумма_без_ндс']) || '-';
            const vat   = getValue(f, ['vat_rate','ставка_ндс','ндс_ставка']) || '-';
            const tax   = getValue(f, ['vat_amount','сумма_налога','сумма_ндс','ндс']) || '-';
            const tot   = getValue(f, ['amount_with_vat','total_with_vat','total','итого']) || '-';
            return `Наименование: ${name}, Кол-во: ${qty}, Цена: ${price}, Без НДС: ${sub}, НДС%: ${vat}, НДС: ${tax}, Итого: ${tot}`;
        }).join(';\n') : '-';

        // ── Описание — единый блок, как колонка «Описание» в Excel ───────────
        const descriptionLines = [
            sellerName  ? `Контрагент: ${sellerName}`      : null,
            sellerINN   ? `ИНН продавца: ${sellerINN}`     : null,
            docNum      ? `Номер документа: ${docNum}`     : null,
            docDate     ? `Дата документа: ${docDate}`     : null,
            docSum      ? `Сумма с НДС: ${docSum}`         : null,
            vatRate     ? `Ставка НДС: ${vatRate}`         : null,
            contractStr ? `Договор: ${contractStr}`        : null,
            table.length > 0 ? `\n${tableText}`            : null,
        ].filter(Boolean).join('\n');

        // ── 3 карточки, как в Excel: Вид / ИНН покупателя / Описание ─────────
        const cols = [
            { label: 'Вид документа',               value: getDocTypeLabel(doc.document_type), id: `cd-type-${idx}` },
            { label: 'Организация (ИНН покупателя)', value: buyerINN || '-',                   id: `cd-org-${idx}` },
            { label: 'Описание',                     value: descriptionLines || '-',            id: `cd-desc-${idx}`, multi: true },
        ];

        return (
            <div key={idx} className="mb-6">
                <div className="flex items-center justify-between mb-4">
                    <h2 className="text-lg font-bold text-slate-900">{getDocTypeLabel(doc.document_type)}</h2>
                    {doc.confidence && (
                        <span className="text-xs font-bold px-3 py-1 bg-emerald-100 text-emerald-800 rounded-full">
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
                            <CopyBtn id={col.id} text={col.value} />
                        </div>
                    ))}
                </div>
            </div>
        );
    };

    const renderDocumentData = (doc, idx) => {
        if (doc.document_type === 'text-extract') {
            return renderTextExtract(doc, idx);
        }
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
                <div className="flex items-center gap-3">
                    <button
                        onClick={() => navigate('/')}
                        className="flex items-center gap-2 text-slate-500 hover:text-slate-900 transition-colors font-medium bg-white px-4 py-2 rounded-lg border border-slate-200 shadow-sm"
                    >
                        <ArrowLeft className="w-4 h-4" /> Назад
                    </button>
                    {result?.module === 'closing-docs' && result?.documents?.length > 0 && (
                        <button
                            onClick={() => {
                                const jobNames = (() => { try { return JSON.parse(localStorage.getItem('ocr_job_names') || '{}'); } catch { return {}; } })();
                                exportClosingDocsToExcel([{ jobId, filename: jobNames[jobId] || jobId, documents: result.documents }]);
                            }}
                            className="flex items-center gap-2 px-3 py-2 bg-emerald-50 text-emerald-700 text-sm font-semibold rounded-lg hover:bg-emerald-100 transition-colors border border-emerald-200 shadow-sm"
                        >
                            <Download className="w-4 h-4" /> Excel
                        </button>
                    )}
                </div>
                <div className="flex flex-col items-end gap-2">
                    <div className="text-right">
                        <p className="text-xs text-slate-400 font-mono tracking-tight text-right uppercase">ID: {jobId}</p>
                        <p className="text-sm font-semibold text-slate-800 flex items-center justify-end gap-2 mt-0.5">
                            Статус: {result?.status === 'done' ? <span className="text-emerald-600 font-bold bg-emerald-50 px-2 rounded">Распознано</span> : result?.status}
                        </p>
                    </div>
                    {result?.status === 'done' && (
                        <div className="flex flex-col gap-2 items-end">
                            <div className="flex items-center gap-2 bg-slate-50 border border-slate-200 px-3 py-1.5 rounded-lg shadow-sm">
                                <span className="text-xs font-semibold text-slate-500">Оценка:</span>
                                <button
                                    disabled={submittingRating}
                                    onClick={() => handleRating(5)}
                                    className={`flex items-center gap-1 px-2.5 py-1 rounded-lg text-xs font-semibold border transition-all disabled:opacity-50
                                        ${rating === 5
                                            ? 'bg-emerald-500 text-white border-emerald-500 shadow-sm'
                                            : 'bg-white text-emerald-600 border-emerald-200 hover:bg-emerald-50'}`}
                                >
                                    <ThumbsUp className="w-3.5 h-3.5" /> Хорошо
                                </button>
                                <button
                                    disabled={submittingRating}
                                    onClick={() => handleRating(1)}
                                    className={`flex items-center gap-1 px-2.5 py-1 rounded-lg text-xs font-semibold border transition-all disabled:opacity-50
                                        ${rating === 1
                                            ? 'bg-red-500 text-white border-red-500 shadow-sm'
                                            : 'bg-white text-red-500 border-red-200 hover:bg-red-50'}`}
                                >
                                    <ThumbsDown className="w-3.5 h-3.5" /> Плохо
                                </button>
                                <button
                                    onClick={() => setShowComment(c => !c)}
                                    className={`flex items-center gap-1 px-2 py-1 rounded-lg text-xs border transition-all
                                        ${showComment ? 'bg-sky-100 text-sky-700 border-sky-200' : 'bg-white text-slate-400 border-slate-200 hover:bg-slate-50'}`}
                                    title="Добавить комментарий"
                                >
                                    <MessageSquare className="w-3.5 h-3.5" />
                                </button>
                            </div>
                            {showComment && (
                                <div className="flex items-start gap-2 w-72">
                                    <textarea
                                        value={comment}
                                        onChange={e => setComment(e.target.value)}
                                        placeholder="Комментарий (что не так или что понравилось)..."
                                        rows={2}
                                        className="flex-1 text-xs p-2 border border-slate-200 rounded-lg focus:ring-2 focus:ring-sky-400 outline-none resize-none bg-white"
                                    />
                                    <button
                                        onClick={handleSaveComment}
                                        disabled={submittingRating}
                                        className="p-2 bg-sky-500 text-white rounded-lg hover:bg-sky-600 disabled:opacity-50 transition-colors mt-0.5"
                                        title="Сохранить комментарий"
                                    >
                                        <Send className="w-3.5 h-3.5" />
                                    </button>
                                </div>
                            )}
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
                        ) : result?.module === 'closing-docs' ? (
                            documents.map((doc, docIdx) => renderClosingDoc(doc, docIdx))
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
