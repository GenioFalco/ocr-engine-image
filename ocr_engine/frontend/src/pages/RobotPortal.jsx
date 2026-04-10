import React, { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { Bot, Key, LogOut, Code2, Copy, Check, AlertTriangle } from 'lucide-react';

const CodeBlock = ({ code }) => {
    const [copied, setCopied] = useState(false);
    const copy = () => { navigator.clipboard.writeText(code); setCopied(true); setTimeout(() => setCopied(false), 2000); };
    return (
        <div className="relative">
            <pre className="bg-slate-900 text-emerald-400 rounded-xl p-4 text-xs overflow-x-auto leading-relaxed font-mono whitespace-pre-wrap break-words">{code}</pre>
            <button onClick={copy} className="absolute top-3 right-3 p-1.5 rounded-md bg-slate-700 hover:bg-slate-600 text-slate-300 transition-colors">
                {copied ? <Check className="w-3.5 h-3.5 text-emerald-400" /> : <Copy className="w-3.5 h-3.5" />}
            </button>
        </div>
    );
};

const RobotPortal = ({ onLogout }) => {
    const username = localStorage.getItem('username') || 'robot';
    const apiBase = window.location.origin;

    // ── New secure flow: client_id → token ─────────────────────────────────
    const curlToken = `curl -s -X POST "${apiBase}/auth/token" \\
  -H "Content-Type: application/json" \\
  -d '{"client_id": "ВАШ_CLIENT_ID", "client_secret": "ВАШ_CLIENT_SECRET"}'`;

    const curlProcess = `# 1. Получить токен через client_id / client_secret:
TOKEN=$(curl -s -X POST "${apiBase}/auth/token" \\
  -H "Content-Type: application/json" \\
  -d '{"client_id":"CLIENT_ID","client_secret":"CLIENT_SECRET"}' \\
  | python3 -c "import sys,json; print(json.load(sys.stdin)['access_token'])")

# 2. Отправить файл:
curl -X POST "${apiBase}/process" \\
  -H "Authorization: Bearer $TOKEN" \\
  -F "file=@/путь/к/файлу.pdf"`;

    const psCode = `# PowerShell (Sherpa RPA — 2 шага)

# Шаг 1: Получить токен
$body = '{"client_id":"CLIENT_ID","client_secret":"CLIENT_SECRET"}'
$resp = Invoke-RestMethod -Uri "${apiBase}/auth/token" \`
    -Method POST -ContentType "application/json" -Body $body
$token = $resp.access_token

# Шаг 2: Отправить файл
$headers = @{ Authorization = "Bearer $token" }
$form = @{ file = Get-Item "C:\\путь\\к\\файлу.pdf" }
Invoke-RestMethod -Uri "${apiBase}/process" \`
    -Method POST -Headers $headers -Form $form`;

    // ── Legacy flow (login/password) ───────────────────────────────────────
    const curlLegacyLogin = `curl -X POST "${apiBase}/auth/login" \\
  -H "Content-Type: application/x-www-form-urlencoded" \\
  -d "username=${username}&password=ВАШ_ПАРОЛЬ"`;

    return (
        <div className="min-h-screen bg-gradient-to-br from-slate-50 to-slate-100 flex flex-col items-center py-16 px-4">
            <div className="w-full max-w-2xl space-y-5">
                {/* Header */}
                <div className="flex items-center justify-between">
                    <div className="flex items-center gap-3">
                        <div className="w-10 h-10 bg-violet-600 rounded-xl flex items-center justify-center shadow-lg">
                            <Bot className="w-5 h-5 text-white" />
                        </div>
                        <div>
                            <h1 className="text-xl font-bold text-slate-900">API Доступ</h1>
                            <p className="text-sm text-slate-500">Учётная запись: <span className="font-mono font-semibold text-violet-700">🤖 {username}</span></p>
                        </div>
                    </div>
                    <button onClick={onLogout} className="flex items-center gap-2 text-sm text-slate-500 hover:text-rose-600 px-3 py-2 rounded-lg hover:bg-rose-50 transition-colors font-medium">
                        <LogOut className="w-4 h-4" /> Выйти
                    </button>
                </div>

                {/* Info banner */}
                <div className="bg-violet-50 border border-violet-200 rounded-xl p-4 flex items-start gap-3">
                    <Key className="w-5 h-5 text-violet-600 shrink-0 mt-0.5" />
                    <div>
                        <p className="text-sm font-semibold text-violet-900">Учётная запись только для API</p>
                        <p className="text-xs text-violet-600 mt-0.5">Веб-интерфейс недоступен. Запросите у администратора <strong>Client ID</strong> и <strong>Client Secret</strong> для интеграции.</p>
                    </div>
                </div>

                {/* ── Secure flow ─────────────────────────────────────── */}
                <div className="bg-white rounded-xl border border-slate-200 shadow-sm overflow-hidden">
                    <div className="px-5 py-4 border-b border-slate-100 bg-emerald-50/40 flex items-center gap-2">
                        <span className="text-emerald-600 font-bold text-xs uppercase tracking-wide">✓ Рекомендуемый способ</span>
                    </div>

                    <div className="divide-y divide-slate-50">
                        <div className="p-5 space-y-3">
                            <div className="flex items-center gap-2">
                                <span className="w-5 h-5 rounded-full bg-slate-900 text-white text-[10px] font-bold flex items-center justify-center">1</span>
                                <h3 className="font-semibold text-slate-800 text-sm">Получить JWT через Client ID + Secret</h3>
                            </div>
                            <CodeBlock code={curlToken} />
                            <p className="text-xs text-slate-400">POST <code className="bg-slate-100 px-1 rounded">/auth/token</code> (JSON body) — токен действует 30 мин. Client ID и Secret выдаёт администратор.</p>
                        </div>

                        <div className="p-5 space-y-3">
                            <div className="flex items-center gap-2">
                                <span className="w-5 h-5 rounded-full bg-slate-900 text-white text-[10px] font-bold flex items-center justify-center">2</span>
                                <h3 className="font-semibold text-slate-800 text-sm">Отправить PDF на распознавание</h3>
                            </div>
                            <div className="space-y-2">
                                <p className="text-xs font-semibold text-slate-500 uppercase flex items-center gap-1"><Code2 className="w-3.5 h-3.5" />cURL (полный пример)</p>
                                <CodeBlock code={curlProcess} />
                                <p className="text-xs font-semibold text-slate-500 uppercase flex items-center gap-1 mt-3"><Code2 className="w-3.5 h-3.5" />PowerShell / Sherpa RPA</p>
                                <CodeBlock code={psCode} />
                            </div>
                        </div>
                    </div>
                </div>

                {/* ── Legacy flow ─────────────────────────────────────── */}
                <details className="bg-white rounded-xl border border-slate-200 shadow-sm overflow-hidden group">
                    <summary className="px-5 py-4 cursor-pointer flex items-center gap-2 text-sm text-slate-500 list-none">
                        <AlertTriangle className="w-4 h-4 text-amber-400" />
                        <span className="font-medium">Устаревший способ: логин + пароль</span>
                        <span className="ml-auto text-xs text-slate-400 group-open:hidden">показать</span>
                        <span className="ml-auto text-xs text-slate-400 hidden group-open:block">скрыть</span>
                    </summary>
                    <div className="border-t border-slate-100 p-5 space-y-3">
                        <p className="text-xs text-amber-600">Не рекомендуется — используйте Client ID / Secret выше.</p>
                        <CodeBlock code={curlLegacyLogin} />
                    </div>
                </details>

                {/* Swagger */}
                <div className="bg-white rounded-xl border border-slate-200 shadow-sm p-4 flex items-center justify-between">
                    <div>
                        <p className="text-sm font-semibold text-slate-800">Swagger UI — полная документация API</p>
                        <p className="text-xs text-slate-400 mt-0.5">Интерактивное тестирование всех эндпоинтов</p>
                    </div>
                    <a href={`${apiBase}/docs`} target="_blank" rel="noreferrer"
                        className="px-4 py-2 bg-slate-900 text-white text-sm font-medium rounded-lg hover:bg-slate-700 transition-colors">
                        Открыть →
                    </a>
                </div>
            </div>
        </div>
    );
};

export default RobotPortal;
