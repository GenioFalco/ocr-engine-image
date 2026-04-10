import React from 'react';
import { useNavigate } from 'react-router-dom';
import { FileText, Scale, ArrowRight, Layers, Scan } from 'lucide-react';

const MODULES = [
    {
        id: 'closing-docs',
        title: 'Закрывающие документы',
        subtitle: 'Счета-фактуры, акты, УПД, накладные',
        icon: FileText,
        gradient: 'from-sky-500 to-blue-600',
        lightBg: 'bg-sky-50',
        lightBorder: 'border-sky-200',
        lightText: 'text-sky-700',
        iconBg: 'bg-sky-100',
        examples: ['Счёт-фактура', 'Акт выполненных работ', 'УПД', 'ТОРГ-12'],
    },
    {
        id: 'enforcement',
        title: 'Исполнительные листы',
        subtitle: 'Судебные документы, исполнительное производство',
        icon: Scale,
        gradient: 'from-violet-500 to-purple-600',
        lightBg: 'bg-violet-50',
        lightBorder: 'border-violet-200',
        lightText: 'text-violet-700',
        iconBg: 'bg-violet-100',
        examples: ['Исполнительный лист', 'Судебный приказ', 'Постановление ФССП'],
    },
    {
        id: 'standard',
        title: 'Стандартный модуль',
        subtitle: 'Базовое распознавание любых документов',
        icon: Scan,
        gradient: 'from-emerald-500 to-teal-600',
        lightBg: 'bg-emerald-50',
        lightBorder: 'border-emerald-200',
        lightText: 'text-emerald-700',
        iconBg: 'bg-emerald-100',
        examples: ['Любой документ', 'Скан', 'Таблица', 'Текст'],
    },
];

const ModuleSelect = () => {
    const navigate = useNavigate();
    const username = localStorage.getItem('username') || 'Пользователь';

    return (
        <div className="max-w-4xl mx-auto">
            {/* Header */}
            <div className="mb-10">
                <div className="flex items-center gap-2 mb-1">
                    <img src="/logo.svg" alt="Logo" className="h-6 object-contain" />
                    <p className="text-sm text-slate-400 font-medium uppercase tracking-widest">CES OSR IDP</p>
                </div>
                <h1 className="text-3xl font-black text-slate-900 tracking-tight">
                    Добро пожаловать, {username}
                </h1>
                <p className="text-slate-400 mt-2 text-base">
                    Выберите модуль для распознавания документов
                </p>
            </div>

            {/* Module cards */}
            <div className="grid grid-cols-1 md:grid-cols-2 gap-5">
                {MODULES.map((mod) => {
                    const Icon = mod.icon;
                    return (
                        <button
                            key={mod.id}
                            onClick={() => navigate(`/module/${mod.id}`)}
                            className="group text-left bg-white rounded-2xl border border-slate-200 shadow-sm
                                hover:border-slate-300 hover:shadow-lg transition-all duration-200
                                overflow-hidden focus:outline-none focus:ring-2 focus:ring-primary focus:ring-offset-2"
                        >
                            {/* Top gradient bar */}
                            <div className={`h-1.5 w-full bg-gradient-to-r ${mod.gradient}`} />

                            <div className="p-6">
                                {/* Icon */}
                                <div className={`w-12 h-12 rounded-xl ${mod.iconBg} flex items-center justify-center mb-5 
                                    group-hover:scale-110 transition-transform duration-200`}>
                                    <Icon className={`w-6 h-6 ${mod.lightText}`} />
                                </div>

                                {/* Title */}
                                <h2 className="text-lg font-bold text-slate-900 mb-1 group-hover:text-slate-700 transition-colors">
                                    {mod.title}
                                </h2>
                                <p className="text-sm text-slate-400 mb-5 leading-relaxed">
                                    {mod.subtitle}
                                </p>

                                {/* Example doc types */}
                                <div className="flex flex-wrap gap-1.5 mb-6">
                                    {mod.examples.map(ex => (
                                        <span
                                            key={ex}
                                            className={`text-[11px] font-medium px-2 py-0.5 rounded-md ${mod.lightBg} ${mod.lightBorder} ${mod.lightText} border`}
                                        >
                                            {ex}
                                        </span>
                                    ))}
                                </div>

                                {/* CTA */}
                                <div className="flex items-center justify-between">
                                    <span className={`text-sm font-semibold ${mod.lightText}`}>
                                        Перейти к модулю
                                    </span>
                                    <div className={`w-8 h-8 rounded-full bg-gradient-to-br ${mod.gradient}
                                        flex items-center justify-center shadow-sm
                                        group-hover:translate-x-1 transition-transform duration-200`}>
                                        <ArrowRight className="w-4 h-4 text-white" />
                                    </div>
                                </div>
                            </div>
                        </button>
                    );
                })}
            </div>

            {/* Info note */}
            <div className="mt-8 p-4 bg-slate-50 border border-slate-200 rounded-xl flex items-start gap-3">
                <div className="w-5 h-5 rounded-full bg-slate-200 flex items-center justify-center shrink-0 mt-0.5">
                    <span className="text-[10px] font-bold text-slate-500">i</span>
                </div>
                <p className="text-sm text-slate-500">
                    Поддерживаемый формат файлов: <strong className="text-slate-700">PDF</strong>.
                    Результат распознавания доступен сразу после обработки.
                </p>
            </div>
        </div>
    );
};

export default ModuleSelect;
