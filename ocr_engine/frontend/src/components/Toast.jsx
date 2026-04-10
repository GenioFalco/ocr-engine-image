import React, { useState, useEffect } from 'react';
import { CheckCircle, AlertCircle, Info, X, AlertTriangle } from 'lucide-react';

// ── Event bus (module-level, works without Context) ──────────────────────────
let _toastId = 0;
const _listeners = new Set();

export const toast = {
    _emit(config) {
        const id = ++_toastId;
        _listeners.forEach(fn => fn({ ...config, id }));
        return id;
    },
    success: (message, duration = 3000) => toast._emit({ type: 'success', message, duration }),
    error:   (message, duration = 4500) => toast._emit({ type: 'error',   message, duration }),
    info:    (message, duration = 3000) => toast._emit({ type: 'info',    message, duration }),
    warning: (message, duration = 3500) => toast._emit({ type: 'warning', message, duration }),
};

// ── Styles ───────────────────────────────────────────────────────────────────
const CONFIG = {
    success: {
        bar:  'bg-emerald-500',
        wrap: 'bg-white border-emerald-200',
        icon: <CheckCircle className="w-4 h-4 text-emerald-500 shrink-0 mt-0.5" />,
    },
    error: {
        bar:  'bg-red-500',
        wrap: 'bg-white border-red-200',
        icon: <AlertCircle className="w-4 h-4 text-red-500 shrink-0 mt-0.5" />,
    },
    info: {
        bar:  'bg-sky-500',
        wrap: 'bg-white border-sky-200',
        icon: <Info className="w-4 h-4 text-sky-500 shrink-0 mt-0.5" />,
    },
    warning: {
        bar:  'bg-amber-400',
        wrap: 'bg-white border-amber-200',
        icon: <AlertTriangle className="w-4 h-4 text-amber-500 shrink-0 mt-0.5" />,
    },
};

// ── Single Toast item ─────────────────────────────────────────────────────────
const ToastItem = ({ t, onRemove }) => {
    const cfg = CONFIG[t.type] || CONFIG.info;
    const [visible, setVisible] = useState(false);

    useEffect(() => {
        // Trigger enter animation
        const enterTimer = setTimeout(() => setVisible(true), 10);
        // Start exit animation before removal
        const exitTimer = setTimeout(() => setVisible(false), t.duration - 350);
        const removeTimer = setTimeout(() => onRemove(t.id), t.duration);
        return () => {
            clearTimeout(enterTimer);
            clearTimeout(exitTimer);
            clearTimeout(removeTimer);
        };
    }, []);

    return (
        <div
            className={`
                relative flex items-start gap-3 px-4 py-3 rounded-xl border shadow-xl
                max-w-sm w-full overflow-hidden cursor-default select-none
                transition-all duration-300
                ${cfg.wrap}
                ${visible ? 'opacity-100 translate-x-0' : 'opacity-0 translate-x-6'}
            `}
            style={{ willChange: 'transform, opacity' }}
        >
            {/* Left accent bar */}
            <div className={`absolute left-0 top-0 bottom-0 w-1 ${cfg.bar} rounded-l-xl`} />

            {cfg.icon}

            <p className="text-sm font-medium text-slate-800 leading-snug flex-1 pl-0.5">
                {t.message}
            </p>

            <button
                onClick={() => onRemove(t.id)}
                className="shrink-0 p-0.5 rounded-md text-slate-400 hover:text-slate-700 hover:bg-slate-100 transition-colors"
            >
                <X className="w-3.5 h-3.5" />
            </button>

            {/* Progress bar */}
            <div
                className={`absolute bottom-0 left-0 h-0.5 ${cfg.bar} opacity-30`}
                style={{
                    animation: `toast-shrink ${t.duration}ms linear forwards`,
                }}
            />
        </div>
    );
};

// ── Container (place once in App.jsx) ────────────────────────────────────────
export const ToastContainer = () => {
    const [toasts, setToasts] = useState([]);

    useEffect(() => {
        const handler = (t) => setToasts(prev => [...prev, t]);
        _listeners.add(handler);
        return () => _listeners.delete(handler);
    }, []);

    const remove = (id) => setToasts(prev => prev.filter(x => x.id !== id));

    if (toasts.length === 0) return null;

    return (
        <>
            {/* Keyframe for progress bar */}
            <style>{`
                @keyframes toast-shrink {
                    from { width: 100%; }
                    to   { width: 0%; }
                }
            `}</style>

            <div className="fixed top-4 right-4 z-[9999] flex flex-col gap-2 pointer-events-none">
                {toasts.map(t => (
                    <div key={t.id} className="pointer-events-auto">
                        <ToastItem t={t} onRemove={remove} />
                    </div>
                ))}
            </div>
        </>
    );
};
