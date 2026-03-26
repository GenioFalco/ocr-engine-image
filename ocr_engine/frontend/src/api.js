import axios from 'axios';

const api = axios.create({
    baseURL: '/api'
});

api.interceptors.request.use((config) => {
    const token = localStorage.getItem('token');
    if (token) {
        config.headers.Authorization = `Bearer ${token}`;
    }
    return config;
});

api.interceptors.response.use(
    (response) => response,
    (error) => {
        if (error.response && error.response.status === 401) {
            // Unauthorized: clear token and optionally redirect to login
            localStorage.removeItem('token');
            localStorage.removeItem('role');
            // window.location.href = '/login'; // Let the components handle the state shift.
        }
        return Promise.reject(error);
    }
);

export default api;
