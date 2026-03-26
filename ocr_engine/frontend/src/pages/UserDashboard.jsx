import React, { useState, useEffect } from 'react';
import api from '../api';
import { Upload, FileText, Clock, CheckCircle, XCircle, AlertCircle, Eye } from 'lucide-react';
import { useNavigate } from 'react-router-dom';

const UserDashboard = () => {
    const [jobs, setJobs] = useState([]);
    const [file, setFile] = useState(null);
    const [uploading, setUploading] = useState(false);
    const [error, setError] = useState('');
    const navigate = useNavigate();

    const fetchJobs = async () => {
        try {
            const { data } = await api.get('/jobs');
            setJobs(data);
        } catch (err) {
            console.error('Failed to fetch jobs', err);
        }
    };

    useEffect(() => {
        fetchJobs();
    }, []);

    const handleFileChange = (e) => {
        if (e.target.files && e.target.files[0]) {
            setFile(e.target.files[0]);
        }
    };

    const handleUpload = async (e) => {
        e.preventDefault();
        if (!file) return;

        setUploading(true);
        setError('');

        const formData = new FormData();
        formData.append('file', file);

        try {
            // Sync processing blocks until done (for small files / demo)
            const { data } = await api.post('/process', formData, {
                headers: { 'Content-Type': 'multipart/form-data' }
            });

            setFile(null);
            await fetchJobs();

            if (data.status === 'success') {
                navigate(`/result/${data.job_id}`);
            }
        } catch (err) {
            setError(err.response?.data?.detail || 'Ошибка при загрузке и распознавании файла');
        } finally {
            setUploading(false);
        }
    };

    const StatusIcon = ({ status }) => {
        switch (status) {
            case 'done': return <CheckCircle className="w-5 h-5 text-emerald-500" />;
            case 'failed': return <XCircle className="w-5 h-5 text-red-500" />;
            case 'processing': return <Clock className="w-5 h-5 text-blue-500 animate-spin" />;
            default: return <AlertCircle className="w-5 h-5 text-amber-500" />;
        }
    };

    return (
        <div className="space-y-8 animate-in fade-in duration-500">
            <div className="flex items-center justify-between">
                <div>
                    <h1 className="text-3xl font-bold tracking-tight text-slate-900">Мои Документы</h1>
                    <p className="text-slate-500 mt-1">Загрузите новый документ или просмотрите историю распознаваний.</p>
                </div>
            </div>

            <div className="bg-white rounded-2xl shadow-sm border border-slate-100 p-8">
                <h2 className="text-lg font-semibold text-slate-800 mb-6 flex items-center gap-2">
                    <Upload className="w-5 h-5 text-primary" />
                    Новое распознавание (Синхронно)
                </h2>

                {error && (
                    <div className="mb-6 p-4 bg-red-50 text-red-700 rounded-xl border border-red-100 text-sm flex items-center gap-3">
                        <AlertCircle className="w-5 h-5 shrink-0" />
                        {error}
                    </div>
                )}

                <div className="flex flex-col md:flex-row gap-4 items-start md:items-center">
                    <label className="flex-1 w-full relative h-32 flex flex-col items-center justify-center border-2 border-dashed border-slate-300 rounded-xl hover:bg-slate-50 hover:border-primary transition-colors cursor-pointer group bg-slate-50/50">
                        <div className="flex flex-col items-center justify-center pt-5 pb-6">
                            <FileText className="w-8 h-8 text-slate-400 group-hover:text-primary transition-colors mb-2" />
                            <p className="mb-1 text-sm text-slate-600">
                                <span className="font-semibold text-primary">Нажмите для выбора</span> или перетащите файл
                            </p>
                            <p className="text-xs text-slate-500">PDF, PNG, JPG или TIFF</p>
                        </div>
                        <input type="file" className="hidden" onChange={handleFileChange} accept=".pdf,image/*" />
                    </label>
                </div>

                {file && (
                    <div className="mt-4 flex items-center justify-between p-4 bg-sky-50 rounded-xl border border-sky-100">
                        <div className="flex items-center gap-3 overflow-hidden">
                            <FileText className="w-6 h-6 text-sky-600 shrink-0" />
                            <span className="text-sm font-medium text-slate-700 truncate">{file.name}</span>
                        </div>
                        <button
                            onClick={handleUpload}
                            disabled={uploading}
                            className="ml-4 px-6 py-2.5 bg-primary text-white text-sm font-medium rounded-lg hover:bg-sky-600 transition-colors shadow-sm disabled:opacity-50 flex items-center gap-2"
                        >
                            {uploading ? (
                                <><Clock className="w-4 h-4 animate-spin" /> Распознавание...</>
                            ) : (
                                'Начать'
                            )}
                        </button>
                    </div>
                )}
            </div>

            <div className="bg-white rounded-2xl shadow-sm border border-slate-100 overflow-hidden">
                <div className="p-6 border-b border-slate-100">
                    <h2 className="text-lg font-semibold text-slate-800">История документов</h2>
                </div>
                <div className="overflow-x-auto">
                    <table className="w-full text-left text-sm text-slate-600">
                        <thead className="bg-slate-50 border-b border-slate-100 text-slate-500 uppercase text-xs font-semibold">
                            <tr>
                                <th scope="col" className="px-6 py-4">ID / Дата</th>
                                <th scope="col" className="px-6 py-4 text-center">Статус</th>
                                <th scope="col" className="px-6 py-4 text-right">Действия</th>
                            </tr>
                        </thead>
                        <tbody className="divide-y divide-slate-100">
                            {jobs.length === 0 ? (
                                <tr>
                                    <td colSpan="3" className="px-6 py-8 text-center text-slate-400">
                                        Вы еще не загрузили ни одного файла.
                                    </td>
                                </tr>
                            ) : (
                                jobs.map((job) => (
                                    <tr key={job.id} className="hover:bg-slate-50/50 transition-colors">
                                        <td className="px-6 py-4 font-medium text-slate-900">
                                            <div className="font-mono text-xs text-slate-400 mb-1">{job.id}</div>
                                            <div className="text-sm">{new Date(job.created_at).toLocaleString()}</div>
                                            {job.error_message && (
                                                <div className="text-xs text-red-500 mt-1 line-clamp-1">{job.error_message}</div>
                                            )}
                                        </td>
                                        <td className="px-6 py-4">
                                            <div className="flex justify-center">
                                                <StatusIcon status={job.status} />
                                            </div>
                                        </td>
                                        <td className="px-6 py-4 text-right">
                                            {job.status === 'done' && (
                                                <button
                                                    onClick={() => navigate(`/result/${job.id}`)}
                                                    className="inline-flex items-center gap-2 px-3 py-1.5 text-sm font-medium text-primary bg-sky-50 rounded-lg hover:bg-sky-100 transition-colors"
                                                >
                                                    <Eye className="w-4 h-4" />
                                                    Результат
                                                </button>
                                            )}
                                        </td>
                                    </tr>
                                ))
                            )}
                        </tbody>
                    </table>
                </div>
            </div>
        </div>
    );
};

export default UserDashboard;
