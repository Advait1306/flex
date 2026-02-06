import axios from "axios";
import { getAuth, clearAuth } from "./auth";

export const api = axios.create({
  baseURL: process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000",
});

// Attach Basic Auth header to every request
api.interceptors.request.use((config) => {
  const token = getAuth();
  if (token) {
    config.headers.Authorization = `Basic ${token}`;
  }
  return config;
});

// On 401, clear credentials so AuthGate shows login form
api.interceptors.response.use(
  (response) => response,
  (error) => {
    if (error.response?.status === 401) {
      clearAuth();
    }
    return Promise.reject(error);
  }
);

export const fetcher = (url: string) => api.get(url).then((res) => res.data);
